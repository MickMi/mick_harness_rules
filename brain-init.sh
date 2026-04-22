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

# --- Source shared brain resolver ---
source "$HARNESS_ROOT/brain-resolve.sh"

# --- Parse arguments ---
FRESH_MODE=false
TARGET_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fresh)
            FRESH_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: brain-init.sh [OPTIONS] [target_project_dir]"
            echo ""
            echo "Mount harness + brain into a target project."
            echo ""
            echo "Options:"
            echo "  --fresh     Start with a clean brain (reset all memory data)."
            echo "              Use this when you cloned/forked someone else's harness repo."
            echo "  -h, --help  Show this help message"
            exit 0
            ;;
        -*)
            fail "Unknown option: $1"
            echo "Run 'brain-init.sh --help' for usage."
            exit 1
            ;;
        *)
            TARGET_DIR="$1"
            shift
            ;;
    esac
done

# --- Resolve target project directory ---
TARGET_DIR="${TARGET_DIR:-$(pwd)}"
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
# Phase 0.5: Brain Repo — Clone/connect external brain repository
# ============================================================
info "Phase 0.5: Brain Repo — Setting up external brain repository..."

# Resolve brain config
resolve_brain_dir "$HARNESS_ROOT"

if [ -n "$BRAIN_REPO_REMOTE" ]; then
    if [ -d "$BRAIN_REPO_LOCAL/.git" ]; then
        ok "Brain repo already cloned at: $BRAIN_REPO_LOCAL"
        # Pull latest
        info "Pulling latest brain data..."
        sync_brain_repo
        ok "Brain repo synced."
    else
        info "Cloning brain repo: $BRAIN_REPO_REMOTE"
        info "  → $BRAIN_REPO_LOCAL"
        if clone_brain_repo "$HARNESS_ROOT"; then
            ok "Brain repo cloned successfully."
        else
            warn "Failed to clone brain repo. Will use local brain/ directory as fallback."
            warn "You can manually clone later: git clone $BRAIN_REPO_REMOTE $BRAIN_REPO_LOCAL"
        fi
    fi

    # Re-resolve after potential clone
    resolve_brain_dir "$HARNESS_ROOT"

    # Create symlink: harness/brain/ → brain repo
    if [ "$BRAIN_IS_EXTERNAL" = "true" ]; then
        BRAIN_LINK="$HARNESS_ROOT/brain"
        if [ -L "$BRAIN_LINK" ]; then
            EXISTING_BRAIN_TARGET="$(readlink "$BRAIN_LINK")"
            if [ "$EXISTING_BRAIN_TARGET" = "$BRAIN_REPO_LOCAL" ]; then
                ok "brain/ symlink already points to brain repo. (idempotent)"
            else
                warn "brain/ symlink points to: $EXISTING_BRAIN_TARGET"
                warn "Updating to point to: $BRAIN_REPO_LOCAL"
                rm "$BRAIN_LINK"
                ln -s "$BRAIN_REPO_LOCAL" "$BRAIN_LINK"
                ok "brain/ symlink updated."
            fi
        elif [ -d "$BRAIN_LINK" ]; then
            # brain/ is a real directory — migrate data then replace with symlink
            local_brain_files=$(find "$BRAIN_LINK" -type f -not -name '.gitkeep' 2>/dev/null | wc -l | tr -d ' ')
            if [ "$local_brain_files" -gt 0 ]; then
                warn "brain/ directory contains $local_brain_files file(s). Backing up to brain.local.bak/"
                mv "$BRAIN_LINK" "${BRAIN_LINK}.local.bak"
            else
                rm -rf "$BRAIN_LINK"
            fi
            ln -s "$BRAIN_REPO_LOCAL" "$BRAIN_LINK"
            ok "brain/ replaced with symlink → $BRAIN_REPO_LOCAL"
        else
            ln -s "$BRAIN_REPO_LOCAL" "$BRAIN_LINK"
            ok "brain/ symlink created → $BRAIN_REPO_LOCAL"
        fi
    fi
else
    info "No brain_repo.remote configured. Using local brain/ directory."
    ok "Local brain mode (single-repo)."
fi

echo ""

# ============================================================
# Phase 0: Owner Detection — Detect fork user & auto-reset brain
# ============================================================
info "Phase 0: Owner Detection — Checking brain ownership..."

BRAIN_OWNER_FILE="$BRAIN_DIR/.brain-owner"

# Extract current Git remote owner from harness repo
detect_current_owner() {
    local remote_url=""
    remote_url=$(git -C "$HARNESS_ROOT" remote get-url origin 2>/dev/null || echo "")

    if [ -z "$remote_url" ]; then
        echo ""
        return
    fi

    # Extract owner from various URL formats:
    # https://github.com/OWNER/REPO.git → OWNER
    # git@github.com:OWNER/REPO.git → OWNER
    local owner=""
    if echo "$remote_url" | grep -qE '^https?://'; then
        owner=$(echo "$remote_url" | sed -E 's|https?://[^/]+/([^/]+)/.*|\1|')
    elif echo "$remote_url" | grep -qE '^git@'; then
        owner=$(echo "$remote_url" | sed -E 's|git@[^:]+:([^/]+)/.*|\1|')
    fi
    echo "$owner"
}

# Read recorded owner from .brain-owner
read_recorded_owner() {
    if [ -f "$BRAIN_OWNER_FILE" ]; then
        grep '^owner:' "$BRAIN_OWNER_FILE" 2>/dev/null | awk '{print $2}' | tr -d ' '
    else
        echo ""
    fi
}

# Reset brain data to clean state for a new owner
reset_brain_for_new_owner() {
    local new_owner="$1"
    warn "Fork detected! Resetting brain data for new owner: $new_owner"
    echo ""

    # 1. Clear sessions (personal conversation digests)
    info "  Clearing brain/sessions/..."
    find "$BRAIN_DIR/sessions" -mindepth 1 -not -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
    touch "$BRAIN_DIR/sessions/.gitkeep"
    ok "  Sessions cleared."

    # 2. Clear projects (project-specific memories)
    info "  Clearing brain/projects/..."
    find "$BRAIN_DIR/projects" -mindepth 1 -not -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
    touch "$BRAIN_DIR/projects/.gitkeep"
    ok "  Projects cleared."

    # 3. Reset global memory files to empty templates
    info "  Resetting brain/global/ to empty templates..."
    cat << 'PREF_EOF' > "$BRAIN_DIR/global/preferences.md"
# Global Preferences (跨项目通用偏好)

## 🎨 Coding Style
<!-- Record your cross-project coding style preferences here -->

## 🔧 Tool Chain
<!-- Record your preferred tools and configurations -->

## 🗣️ Communication
<!-- Record your preferred interaction style with AI -->

## 📐 Architecture Principles
<!-- Record your cross-project architecture preferences -->
PREF_EOF

    cat << 'GOTCHA_EOF' > "$BRAIN_DIR/global/gotchas.md"
# Global Gotchas (跨项目踩坑记录)

## ⚠️ Tool & Environment Pitfalls
<!-- Record cross-project tool/environment pitfalls here -->

## 🐛 Language & Framework Gotchas
<!-- Record language/framework-specific pitfalls that apply across projects -->

## 🔐 Security & Secrets
<!-- Record security-related lessons learned -->
GOTCHA_EOF
    ok "  Global memory reset to empty templates."

    # 4. Reset MEMORY.md to fresh template
    info "  Resetting MEMORY.md..."
    cat << 'MEM_EOF' > "$BRAIN_DIR/MEMORY.md"
# 项目记忆与经验库 (Memory & Learnings)

## 🏗️ 架构决策记录 (ADR)
*在这里记录我们在对话中决定引入的新库、核心数据结构变更或重大架构妥协。*

## ⚠️ 已知天坑与环境限制 (Gotchas)
*在这里记录导致过 Bug 的环境配置问题、API 限制或特定语言的陷阱。*

## 💡 设计原则备忘
*从历史讨论中提炼的核心设计原则。*
MEM_EOF
    ok "  MEMORY.md reset to fresh template."

    # 5. Commit brain reset if external repo
    if [ "$BRAIN_IS_EXTERNAL" = "true" ]; then
        commit_brain_changes "brain: reset for new owner $new_owner" false
    fi

    # 6. Note: .brain-owner is updated by the caller (record_owner function)
    ok "  Brain data cleared. Owner file will be updated next."

    echo ""
    ok "🧹 Brain reset complete! You now have a clean brain to start fresh."
    echo ""
}

# --- Helper: detect system username ---
detect_system_user() {
    whoami 2>/dev/null || echo ""
}

# --- Helper: read recorded system user from .brain-owner ---
read_recorded_system_user() {
    if [ -f "$BRAIN_OWNER_FILE" ]; then
        grep '^system_user:' "$BRAIN_OWNER_FILE" 2>/dev/null | awk '{print $2}' | tr -d ' '
    else
        echo ""
    fi
}

# --- Helper: check if brain has existing data (non-empty) ---
brain_has_data() {
    local data_count=0
    # Count non-.gitkeep files in brain/
    data_count=$(find "$BRAIN_DIR" -type f -not -name '.gitkeep' -not -name '*.archive*' -not -name '.brain-owner' 2>/dev/null | wc -l | tr -d ' ')
    [ "$data_count" -gt 2 ]  # More than just the 2 empty template files
}

# --- Helper: record owner info ---
record_owner() {
    local owner="$1"
    local sys_user="$2"
    local new_repo=""
    local remote_url=""
    remote_url=$(git -C "$HARNESS_ROOT" remote get-url origin 2>/dev/null || echo "")
    if echo "$remote_url" | grep -qE '^https?://'; then
        new_repo=$(echo "$remote_url" | sed -E 's|https?://[^/]+/[^/]+/([^/.]+).*|\1|')
    elif echo "$remote_url" | grep -qE '^git@'; then
        new_repo=$(echo "$remote_url" | sed -E 's|git@[^:]+:[^/]+/([^/.]+).*|\1|')
    fi
    [ -z "$new_repo" ] && new_repo="unknown"

    # Ensure brain directory structure exists
    mkdir -p "$BRAIN_DIR/global" "$BRAIN_DIR/projects" "$BRAIN_DIR/sessions"

    cat << OWNER_EOF > "$BRAIN_OWNER_FILE"
# Brain Owner Identity
# This file records who owns this harness + brain instance.
# When a fork user runs brain-init.sh, the script detects the mismatch
# and automatically resets brain data to a clean state.
# DO NOT edit manually — managed by brain-init.sh.

owner: $owner
repo: $new_repo
system_user: $sys_user
OWNER_EOF
}

# --- Execute owner detection ---
CURRENT_OWNER=$(detect_current_owner)
RECORDED_OWNER=$(read_recorded_owner)
CURRENT_SYS_USER=$(detect_system_user)
RECORDED_SYS_USER=$(read_recorded_system_user)

# --- Fresh mode: unconditional reset ---
if [ "$FRESH_MODE" = true ]; then
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🆕 Fresh Mode — Starting with a clean brain${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    EFFECTIVE_OWNER="${CURRENT_OWNER:-$CURRENT_SYS_USER}"
    reset_brain_for_new_owner "$EFFECTIVE_OWNER"
    record_owner "$EFFECTIVE_OWNER" "$CURRENT_SYS_USER"

elif [ -z "$CURRENT_OWNER" ] && [ -z "$RECORDED_OWNER" ]; then
    # No Git remote and no recorded owner — likely a local-only setup
    if brain_has_data; then
        warn "Brain contains existing data but no owner is recorded."
        echo -e "  ${YELLOW}If this is someone else's harness repo, run with --fresh to start clean:${NC}"
        echo -e "  ${YELLOW}  $0 --fresh $TARGET_DIR${NC}"
        echo ""
    fi
    info "Recording owner as system user: $CURRENT_SYS_USER"
    record_owner "$CURRENT_SYS_USER" "$CURRENT_SYS_USER"
    ok "Owner recorded: $CURRENT_SYS_USER"

elif [ -z "$RECORDED_OWNER" ]; then
    # No .brain-owner file — first time setup
    if brain_has_data; then
        # Brain has data but no owner file — this is likely a clone of someone else's repo
        echo ""
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}  🤔 Existing brain data detected (no owner on record)${NC}"
        echo -e "${YELLOW}  ${NC}"
        echo -e "${YELLOW}  The brain/ directory contains memories from a previous user.${NC}"
        echo -e "${YELLOW}  Is this YOUR data, or did you clone someone else's repo?${NC}"
        echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        # Non-interactive: auto-reset if stdin is not a terminal
        if [ -t 0 ]; then
            echo -n "  Reset brain to start fresh? [Y/n] "
            read -r answer
            answer=${answer:-Y}
        else
            answer="Y"
            info "Non-interactive mode detected. Auto-resetting brain."
        fi

        if [[ "$answer" =~ ^[Yy] ]]; then
            reset_brain_for_new_owner "$CURRENT_OWNER"
        else
            info "Keeping existing brain data. Recording you as the owner."
        fi
    else
        info "First-time setup detected. Recording owner: $CURRENT_OWNER"
    fi
    record_owner "$CURRENT_OWNER" "$CURRENT_SYS_USER"
    ok "Owner recorded: $CURRENT_OWNER"

elif [ -n "$CURRENT_OWNER" ] && [ "$CURRENT_OWNER" != "$RECORDED_OWNER" ]; then
    # Git remote owner mismatch — this is a fork user!
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  🔀 Fork Detected!${NC}"
    echo -e "${YELLOW}  Recorded owner : $RECORDED_OWNER${NC}"
    echo -e "${YELLOW}  Current owner  : $CURRENT_OWNER${NC}"
    echo -e "${YELLOW}  ${NC}"
    echo -e "${YELLOW}  The brain data belongs to the original author.${NC}"
    echo -e "${YELLOW}  Auto-resetting to give you a clean brain...${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    reset_brain_for_new_owner "$CURRENT_OWNER"
    record_owner "$CURRENT_OWNER" "$CURRENT_SYS_USER"

elif [ -n "$CURRENT_SYS_USER" ] && [ -n "$RECORDED_SYS_USER" ] && [ "$CURRENT_SYS_USER" != "$RECORDED_SYS_USER" ]; then
    # Same Git remote but different system user — likely a direct clone (not fork)
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  👤 Different System User Detected!${NC}"
    echo -e "${YELLOW}  Recorded user : $RECORDED_SYS_USER${NC}"
    echo -e "${YELLOW}  Current user  : $CURRENT_SYS_USER${NC}"
    echo -e "${YELLOW}  ${NC}"
    echo -e "${YELLOW}  You appear to be a different person using this harness repo.${NC}"
    echo -e "${YELLOW}  The brain data may belong to someone else.${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    if [ -t 0 ]; then
        echo -n "  Reset brain to start fresh? [Y/n] "
        read -r answer
        answer=${answer:-Y}
    else
        answer="Y"
        info "Non-interactive mode detected. Auto-resetting brain."
    fi

    if [[ "$answer" =~ ^[Yy] ]]; then
        reset_brain_for_new_owner "$CURRENT_OWNER"
        record_owner "$CURRENT_OWNER" "$CURRENT_SYS_USER"
    else
        info "Keeping existing brain data. Updating system user record."
        record_owner "$RECORDED_OWNER" "$CURRENT_SYS_USER"
    fi

else
    ok "Owner verified: $CURRENT_OWNER (matches recorded owner)"
fi

echo ""

# ============================================================
# Phase 1: Load — Create symlink .harness/ → harness repo
# ============================================================
info "Phase 1/5: Load — Creating .harness/ symlink..."

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
info "Phase 2/5: Inject — Symlinking key files + injecting IDE rules..."

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

# .prompts/ — Symlink entire directory so Agent role templates are never copied
PROMPTS_LINK="$TARGET_DIR/.prompts"
if [ -L "$PROMPTS_LINK" ]; then
    ok ".prompts/ symlink already exists. (idempotent)"
elif [ -d "$PROMPTS_LINK" ]; then
    warn ".prompts/ already exists as a regular directory. Backing up to .prompts.bak/"
    mv "$PROMPTS_LINK" "${PROMPTS_LINK}.bak"
    ln -s "$HARNESS_ROOT/.prompts" "$PROMPTS_LINK"
    ok ".prompts/ symlinked (original backed up to .prompts.bak/)"
else
    ln -s "$HARNESS_ROOT/.prompts" "$PROMPTS_LINK"
    ok ".prompts/ symlinked to project root."
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
info "Phase 3/5: Activate — Ensuring .gitignore isolation..."

GITIGNORE="$TARGET_DIR/.gitignore"
IGNORE_ENTRIES=(".harness/" ".harness" ".cursorrules" ".prompts/" ".prompts")

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
info "Phase 4/5: Verify — Running brain check..."
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
if [ "$BRAIN_IS_EXTERNAL" = "true" ]; then
    echo ""
    echo "  🧠 Brain repo: $BRAIN_REPO_LOCAL (synced to $BRAIN_REPO_REMOTE)"
fi
echo ""
echo "  💡 If you cloned this from someone else, and brain wasn't auto-reset,"
echo "     run: $0 --fresh $TARGET_DIR"
echo ""
