#!/bin/bash
set -euo pipefail

# ============================================================
# brain-migrate.sh — Migrate brain data from harness repo to brain repo
#
# This is a one-time migration script for the dual-repo model (ADR-016).
# It copies existing brain data from the harness repo's brain/ directory
# to the external brain repository.
#
# Usage: brain-migrate.sh
# ============================================================

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()    { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail()  { echo -e "${RED}❌ $1${NC}"; }

# --- Resolve harness repo root ---
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- Source shared brain resolver ---
source "$HARNESS_ROOT/brain-resolve.sh"

echo ""
echo "🧠 Brain Migration — Harness → External Brain Repo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# --- Step 1: Read config ---
resolve_brain_dir "$HARNESS_ROOT"

if [ -z "$BRAIN_REPO_REMOTE" ]; then
    fail "No brain_repo.remote configured in .brain-config.yaml"
    echo "  Please add brain_repo configuration first."
    exit 1
fi

echo "  Harness repo  : $HARNESS_ROOT"
echo "  Brain remote   : $BRAIN_REPO_REMOTE"
echo "  Brain local    : $BRAIN_REPO_LOCAL"
echo ""

# --- Step 2: Check if brain/ is still a real directory (not yet migrated) ---
BRAIN_LOCAL_DIR="$HARNESS_ROOT/brain"

if [ -L "$BRAIN_LOCAL_DIR" ]; then
    fail "brain/ is already a symlink. Migration may have already been done."
    echo "  Symlink target: $(readlink "$BRAIN_LOCAL_DIR")"
    exit 1
fi

if [ ! -d "$BRAIN_LOCAL_DIR" ]; then
    fail "brain/ directory not found in harness repo."
    exit 1
fi

# --- Step 3: Clone brain repo if not present ---
if [ ! -d "$BRAIN_REPO_LOCAL/.git" ]; then
    info "Cloning brain repo..."
    if git clone "$BRAIN_REPO_REMOTE" "$BRAIN_REPO_LOCAL" 2>/dev/null; then
        ok "Brain repo cloned."
    else
        # Empty repo — initialize locally and set remote
        info "Remote appears to be empty. Initializing local brain repo..."
        mkdir -p "$BRAIN_REPO_LOCAL"
        git -C "$BRAIN_REPO_LOCAL" init --quiet
        git -C "$BRAIN_REPO_LOCAL" remote add origin "$BRAIN_REPO_REMOTE" 2>/dev/null || true
        # Create initial commit so we can push later
        touch "$BRAIN_REPO_LOCAL/.gitkeep"
        git -C "$BRAIN_REPO_LOCAL" add -A
        git -C "$BRAIN_REPO_LOCAL" commit -m "brain: initial setup" --quiet
        ok "Brain repo initialized locally (remote was empty)."
    fi
else
    ok "Brain repo already exists at: $BRAIN_REPO_LOCAL"
    info "Pulling latest..."
    git -C "$BRAIN_REPO_LOCAL" pull --rebase --autostash --quiet 2>/dev/null || true
fi

# --- Step 4: Copy brain data to brain repo ---
info "Copying brain data to brain repo..."

# Create directory structure
mkdir -p "$BRAIN_REPO_LOCAL/global"
mkdir -p "$BRAIN_REPO_LOCAL/projects"
mkdir -p "$BRAIN_REPO_LOCAL/sessions"

# Copy global files
if [ -d "$BRAIN_LOCAL_DIR/global" ]; then
    cp -r "$BRAIN_LOCAL_DIR/global/"* "$BRAIN_REPO_LOCAL/global/" 2>/dev/null || true
    ok "Copied global/ data"
fi

# Copy projects
if [ -d "$BRAIN_LOCAL_DIR/projects" ]; then
    # Copy everything except .gitkeep
    find "$BRAIN_LOCAL_DIR/projects" -mindepth 1 -maxdepth 1 -type d -exec cp -r {} "$BRAIN_REPO_LOCAL/projects/" \; 2>/dev/null || true
    ok "Copied projects/ data"
fi

# Copy sessions
if [ -d "$BRAIN_LOCAL_DIR/sessions" ]; then
    find "$BRAIN_LOCAL_DIR/sessions" -mindepth 1 -maxdepth 1 -type d -exec cp -r {} "$BRAIN_REPO_LOCAL/sessions/" \; 2>/dev/null || true
    ok "Copied sessions/ data"
fi

# Copy .brain-owner if exists
if [ -f "$BRAIN_LOCAL_DIR/../.brain-owner" ]; then
    cp "$BRAIN_LOCAL_DIR/../.brain-owner" "$BRAIN_REPO_LOCAL/.brain-owner" 2>/dev/null || true
    ok "Copied .brain-owner"
fi

# Copy MEMORY.md to brain repo (personal memory part)
if [ -f "$HARNESS_ROOT/MEMORY.md" ]; then
    cp "$HARNESS_ROOT/MEMORY.md" "$BRAIN_REPO_LOCAL/MEMORY.md"
    ok "Copied MEMORY.md to brain repo"
fi

# Ensure .gitkeep files exist
touch "$BRAIN_REPO_LOCAL/projects/.gitkeep"
touch "$BRAIN_REPO_LOCAL/sessions/.gitkeep"

# --- Step 5: Commit brain repo ---
info "Committing brain repo..."
cd "$BRAIN_REPO_LOCAL"
git add -A 2>/dev/null
git commit -m "brain: initial migration from harness repo (ADR-016)" --quiet 2>/dev/null || true

if git remote get-url origin &>/dev/null; then
    info "Pushing to remote..."
    # Use -u to set upstream (needed for first push to empty repo)
    git push -u origin HEAD --quiet 2>/dev/null && ok "Pushed to remote." || warn "Push failed. Committed locally."
fi

# --- Step 6: Replace brain/ directory with symlink ---
info "Replacing brain/ directory with symlink..."
cd "$HARNESS_ROOT"

# Backup original brain/ directory
mv "$BRAIN_LOCAL_DIR" "${BRAIN_LOCAL_DIR}.migrated.bak"
ok "Original brain/ backed up to brain.migrated.bak/"

# Create symlink
ln -s "$BRAIN_REPO_LOCAL" "$BRAIN_LOCAL_DIR"
ok "Created symlink: brain/ → $BRAIN_REPO_LOCAL"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "🧠 Migration complete!"
echo ""
echo "  Brain data is now in: $BRAIN_REPO_LOCAL"
echo "  Harness brain/ is a symlink to the brain repo."
echo ""
echo "  Next steps:"
echo "  1. Verify: brain-check.sh"
echo "  2. Clean up backup: rm -rf brain.migrated.bak/"
echo "  3. Commit harness repo changes (updated .gitignore, etc.)"
echo ""
