#!/bin/bash
set -euo pipefail

# ============================================================
# brain-init.sh — Mount harness + brain into a target project
# Usage: /path/to/mick_harness_rules/brain-init.sh [target_project_dir]
# If no target dir is given, uses current working directory.
# ============================================================

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()    { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail()  { echo -e "${RED}❌ $1${NC}"; }

# --- Resolve harness repo root (where this script lives) ---
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- Resolve target project directory ---
TARGET_DIR="${1:-$(pwd)}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

# --- Safety check: don't init inside the harness repo itself ---
if [ "$TARGET_DIR" = "$HARNESS_ROOT" ]; then
    fail "Cannot init inside the harness repo itself."
    echo "    Please run this script from your target project directory,"
    echo "    or pass the target project path as an argument."
    exit 1
fi

echo ""
echo "🧠 Brain Init — Mounting harness + brain into project"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Harness repo : $HARNESS_ROOT"
echo "  Target project: $TARGET_DIR"
echo ""

# ============================================================
# Phase 1: Load — Create symlink .harness/ → harness repo
# ============================================================
info "Phase 1/4: Load — Creating .harness/ symlink..."

HARNESS_LINK="$TARGET_DIR/.harness"

if [ -L "$HARNESS_LINK" ]; then
    # Symlink already exists — check if it points to the right place
    EXISTING_TARGET="$(readlink "$HARNESS_LINK")"
    if [ "$EXISTING_TARGET" = "$HARNESS_ROOT" ]; then
        ok "Symlink .harness/ already exists and points to correct location. (idempotent)"
    else
        warn "Symlink .harness/ exists but points to: $EXISTING_TARGET"
        warn "Updating to point to: $HARNESS_ROOT"
        rm "$HARNESS_LINK"
        ln -s "$HARNESS_ROOT" "$HARNESS_LINK"
        ok "Symlink .harness/ updated."
    fi
elif [ -e "$HARNESS_LINK" ]; then
    fail ".harness/ exists but is not a symlink. Please remove it manually and retry."
    exit 1
else
    ln -s "$HARNESS_ROOT" "$HARNESS_LINK"
    ok "Symlink created: .harness/ → $HARNESS_ROOT"
fi

# ============================================================
# Phase 2: Inject — Symlink key files + multi-IDE rule injection
# ============================================================
info "Phase 2/4: Inject — Symlinking key files + injecting IDE rules..."

# --- Helper: Inject brain rules into an IDE rule file ---
# Appends brain auto-write rules from template if not already present
inject_brain_rules() {
    local target_file="$1"
    local ide_name="$2"

    # Check if brain rules already injected
    if grep -q "Brain Auto-Write Protocol" "$target_file" 2>/dev/null; then
        ok "$ide_name rules: Brain auto-write rules already present. (idempotent)"
        return
    fi

    local template="$HARNESS_ROOT/brain-rules-template.md"
    if [ ! -f "$template" ]; then
        warn "brain-rules-template.md not found. Skipping brain rules injection for $ide_name."
        return
    fi

    # Replace <ide> placeholder with actual IDE name
    echo "" >> "$target_file"
    sed "s/<ide>/$ide_name/g" "$template" >> "$target_file"
    ok "$ide_name rules: Brain auto-write rules injected."
}

# .cursorrules — Cursor IDE only reads from project root
CURSORRULES_LINK="$TARGET_DIR/.cursorrules"
if [ -L "$CURSORRULES_LINK" ]; then
    ok ".cursorrules symlink already exists. (idempotent)"
elif [ -f "$CURSORRULES_LINK" ]; then
    warn ".cursorrules already exists as a regular file. Backing up to .cursorrules.bak"
    mv "$CURSORRULES_LINK" "$CURSORRULES_LINK.bak"
    ln -s "$HARNESS_ROOT/.cursorrules" "$CURSORRULES_LINK"
    ok ".cursorrules symlinked (original backed up to .cursorrules.bak)"
else
    ln -s "$HARNESS_ROOT/.cursorrules" "$CURSORRULES_LINK"
    ok ".cursorrules symlinked to project root."
fi

# --- Multi-IDE Rule Injection ---
# Detect and inject brain rules into other IDE rule files

# Windsurf: .windsurfrules
WINDSURF_RULES="$TARGET_DIR/.windsurfrules"
if [ -f "$WINDSURF_RULES" ]; then
    inject_brain_rules "$WINDSURF_RULES" "windsurf"
fi

# Trae: .trae/rules or .trae/rules.md
TRAE_RULES_DIR="$TARGET_DIR/.trae"
if [ -d "$TRAE_RULES_DIR" ]; then
    for trae_file in "$TRAE_RULES_DIR/rules" "$TRAE_RULES_DIR/rules.md"; do
        if [ -f "$trae_file" ]; then
            inject_brain_rules "$trae_file" "trae"
            break
        fi
    done
fi

# VS Code Copilot: .github/copilot-instructions.md
COPILOT_INSTRUCTIONS="$TARGET_DIR/.github/copilot-instructions.md"
if [ -f "$COPILOT_INSTRUCTIONS" ]; then
    inject_brain_rules "$COPILOT_INSTRUCTIONS" "copilot"
fi

# Add IDE rule files to .gitignore if they exist
EXTRA_IGNORE_ENTRIES=()
[ -f "$WINDSURF_RULES" ] && EXTRA_IGNORE_ENTRIES+=(".windsurfrules")
[ -d "$TRAE_RULES_DIR" ] && EXTRA_IGNORE_ENTRIES+=(".trae/")

if [ ${#EXTRA_IGNORE_ENTRIES[@]} -gt 0 ]; then
    GITIGNORE="$TARGET_DIR/.gitignore"
    [ ! -f "$GITIGNORE" ] && touch "$GITIGNORE"
    for entry in "${EXTRA_IGNORE_ENTRIES[@]}"; do
        if ! grep -qxF "$entry" "$GITIGNORE" 2>/dev/null; then
            echo "$entry" >> "$GITIGNORE"
            info "Added $entry to .gitignore"
        fi
    done
fi

# ============================================================
# Phase 3: Activate — Ensure .gitignore isolates harness files
# ============================================================
info "Phase 3/4: Activate — Ensuring .gitignore isolation..."

GITIGNORE="$TARGET_DIR/.gitignore"
IGNORE_ENTRIES=(".harness/" ".harness" ".cursorrules")

# Create .gitignore if it doesn't exist
if [ ! -f "$GITIGNORE" ]; then
    touch "$GITIGNORE"
    info "Created .gitignore (didn't exist)"
fi

# Add missing entries
ADDED_COUNT=0
for entry in "${IGNORE_ENTRIES[@]}"; do
    if ! grep -qxF "$entry" "$GITIGNORE" 2>/dev/null; then
        echo "$entry" >> "$GITIGNORE"
        ((ADDED_COUNT++))
    fi
done

if [ "$ADDED_COUNT" -gt 0 ]; then
    ok "Added $ADDED_COUNT entries to .gitignore"
else
    ok ".gitignore already contains all isolation entries. (idempotent)"
fi

# ============================================================
# Phase 4: Verify — Run brain-check to confirm everything works
# ============================================================
info "Phase 4/4: Verify — Running brain check..."
echo ""

BRAIN_CHECK="$HARNESS_ROOT/brain-check.sh"
if [ -x "$BRAIN_CHECK" ]; then
    "$BRAIN_CHECK" "$TARGET_DIR"
    CHECK_EXIT=$?
else
    warn "brain-check.sh not found or not executable. Skipping verification."
    warn "Run 'chmod +x $BRAIN_CHECK' to enable verification."
    CHECK_EXIT=0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$CHECK_EXIT" -eq 0 ]; then
    ok "🧠 Brain Init complete! Harness + Brain mounted successfully."
else
    warn "🧠 Brain Init completed with warnings. Please review above."
fi
echo ""
echo "  Next steps:"
echo "  1. Start coding in your project — AI will follow your harness rules."
echo "  2. Use 'brain push' to write learnings back to the brain."
echo "  3. Use 'brain search <keyword>' to search your memory."
echo ""
