#!/bin/bash
set -euo pipefail

# ============================================================
# setup.sh — One-step project bootstrap (clone-in-place mode)
#
# Usage:
#   cd /path/to/your/project
#   git clone https://github.com/MickMi/mick_harness_rules.git .harness
#   .harness/setup.sh [OPTIONS]
#
# This script is designed for the "clone as subdirectory" workflow.
# It auto-detects the parent directory as the target project and
# performs all initialization in one step.
#
# Options:
#   --fresh     Start with a clean brain (for fork/clone users)
#   --no-vibe   Skip Vibe scaffold files (MEMORY.md, TODO.md, docs/)
#   -h, --help  Show this help message
#
# What it does:
#   1. Detect parent directory as target project
#   2. Symlink .cursorrules and .prompts/ into project root
#   3. Configure .gitignore to isolate harness files
#   4. Deploy Vibe scaffold files (skip if already exist)
#   5. Clone/connect brain repo (fallback to local if unavailable)
#   6. Run brain-check to verify integrity
# ============================================================

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()    { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail()  { echo -e "${RED}❌ $1${NC}"; }

# --- Resolve harness root (where this script lives) ---
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- Parse arguments ---
FRESH_MODE=false
SKIP_VIBE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --fresh)
            FRESH_MODE=true
            shift
            ;;
        --no-vibe)
            SKIP_VIBE=true
            shift
            ;;
        --help|-h)
            echo "Usage: .harness/setup.sh [OPTIONS]"
            echo ""
            echo "One-step project bootstrap. Run from your project root after cloning"
            echo "the harness repo as .harness/ subdirectory."
            echo ""
            echo "Options:"
            echo "  --fresh     Start with a clean brain (for new users who cloned/forked)"
            echo "  --no-vibe   Skip Vibe scaffold files (MEMORY.md, TODO.md, docs/)"
            echo "  -h, --help  Show this help message"
            echo ""
            echo "Quick start:"
            echo "  git clone https://github.com/MickMi/mick_harness_rules.git .harness"
            echo "  .harness/setup.sh"
            exit 0
            ;;
        -*)
            fail "Unknown option: $1"
            echo "Run '.harness/setup.sh --help' for usage."
            exit 1
            ;;
        *)
            fail "Unexpected argument: $1"
            echo "This script auto-detects the project directory (parent of .harness/)."
            echo "Run '.harness/setup.sh --help' for usage."
            exit 1
            ;;
    esac
done

# --- Auto-detect target project directory (parent of .harness/) ---
# The harness should be cloned as <project>/.harness/
TARGET_DIR="$(cd "$HARNESS_ROOT/.." && pwd)"

# --- Validate: harness should be inside a project directory ---
HARNESS_DIRNAME="$(basename "$HARNESS_ROOT")"
if [ "$HARNESS_DIRNAME" != ".harness" ]; then
    warn "Harness directory is named '$HARNESS_DIRNAME' instead of '.harness'."
    warn "Expected: git clone <url> .harness"
    echo ""
    echo -n "  Continue anyway? [y/N] "
    if [ -t 0 ]; then
        read -r answer
        answer=${answer:-N}
    else
        answer="N"
    fi
    if [[ ! "$answer" =~ ^[Yy] ]]; then
        fail "Aborted. Please clone as .harness/:"
        echo "  git clone https://github.com/MickMi/mick_harness_rules.git .harness"
        exit 1
    fi
fi

# --- Ensure we're not running in a bare harness repo ---
if [ "$TARGET_DIR" = "$HOME" ]; then
    fail "Target project resolved to \$HOME. This doesn't look right."
    echo "    Make sure you cloned the harness repo inside your project:"
    echo "    cd /path/to/your/project && git clone <url> .harness"
    exit 1
fi

echo ""
echo -e "${BOLD}🚀 Harness Setup — One-step project bootstrap${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Harness location: $HARNESS_ROOT"
echo "  Target project  : $TARGET_DIR"
echo "  Fresh mode      : $FRESH_MODE"
echo "  Skip vibe files : $SKIP_VIBE"
echo ""

# --- Make all scripts executable ---
info "Making harness scripts executable..."
chmod +x "$HARNESS_ROOT"/*.sh 2>/dev/null || true
ok "Scripts are executable."
echo ""

# ============================================================
# Phase 1: Symlink key files into project root
# ============================================================
info "Phase 1/6: Symlinking key files into project root..."

# .cursorrules → .harness/.cursorrules
CURSORRULES_LINK="$TARGET_DIR/.cursorrules"
if [ -L "$CURSORRULES_LINK" ]; then
    ok ".cursorrules symlink already exists. (idempotent)"
elif [ -f "$CURSORRULES_LINK" ]; then
    warn ".cursorrules already exists as a regular file. Keeping project's own version."
    warn "  (To use harness rules, remove it and re-run setup.sh)"
else
    ln -s "$HARNESS_ROOT/.cursorrules" "$CURSORRULES_LINK"
    ok ".cursorrules → .harness/.cursorrules"
fi

# .prompts/ → .harness/.prompts/
PROMPTS_LINK="$TARGET_DIR/.prompts"
if [ -L "$PROMPTS_LINK" ]; then
    ok ".prompts/ symlink already exists. (idempotent)"
elif [ -d "$PROMPTS_LINK" ]; then
    warn ".prompts/ already exists as a real directory. Keeping project's own version."
else
    ln -s "$HARNESS_ROOT/.prompts" "$PROMPTS_LINK"
    ok ".prompts/ → .harness/.prompts/"
fi

echo ""

# ============================================================
# Phase 2: Configure .gitignore isolation
# ============================================================
info "Phase 2/6: Configuring .gitignore isolation..."

GITIGNORE="$TARGET_DIR/.gitignore"
IGNORE_ENTRIES=(".harness/" ".harness" ".cursorrules" ".prompts/" ".prompts")

if [ ! -f "$GITIGNORE" ]; then
    touch "$GITIGNORE"
    info "Created .gitignore (didn't exist)"
fi

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

echo ""

# ============================================================
# Phase 3: Deploy Vibe scaffold files (skip if exist)
# ============================================================
if [ "$SKIP_VIBE" = false ]; then
    info "Phase 3/6: Deploying Vibe scaffold files (skip if already exist)..."

    # Create directory structure
    mkdir -p "$TARGET_DIR/docs"
    mkdir -p "$TARGET_DIR/docs/design"

    # MEMORY.md — project-specific
    if [ ! -f "$TARGET_DIR/MEMORY.md" ] && [ ! -L "$TARGET_DIR/MEMORY.md" ]; then
        cat << 'MEMORY_EOF' > "$TARGET_DIR/MEMORY.md"
# 项目记忆与经验库 (Memory & Learnings)

## 🏗️ 架构决策记录 (ADR)
*在这里记录我们在对话中决定引入的新库、核心数据结构变更或重大架构妥协。*

## ⚠️ 已知天坑与环境限制 (Gotchas)
- (暂无)

## 💡 设计原则备忘
*从历史讨论中提炼的核心设计原则。*
MEMORY_EOF
        ok "Generated: MEMORY.md"
    else
        ok "MEMORY.md already exists. Skipping."
    fi

    # TODO.md — project-specific
    if [ ! -f "$TARGET_DIR/TODO.md" ] && [ ! -L "$TARGET_DIR/TODO.md" ]; then
        cat << 'TODO_EOF' > "$TARGET_DIR/TODO.md"
# 项目待办与状态流转

## 🚧 当前进行中 (In Progress)
- [ ]

## 📋 待办清单 (Backlog)
- [ ] 编写核心业务逻辑
- [ ] 跑通基础自动化测试

## ✅ 已完成 (Done)
- [x] 初始化 Vibe Coding 脚手架
TODO_EOF
        ok "Generated: TODO.md"
    else
        ok "TODO.md already exists. Skipping."
    fi

    # docs/architecture.md — from blank template
    if [ ! -f "$TARGET_DIR/docs/architecture.md" ] && [ ! -L "$TARGET_DIR/docs/architecture.md" ]; then
        if [ -f "$HARNESS_ROOT/docs/architecture-template.md" ]; then
            cp "$HARNESS_ROOT/docs/architecture-template.md" "$TARGET_DIR/docs/architecture.md"
            ok "Generated: docs/architecture.md (from template)"
        else
            warn "architecture-template.md not found. Skipping."
        fi
    else
        ok "docs/architecture.md already exists. Skipping."
    fi

    echo ""
else
    info "Phase 3/6: Skipped (--no-vibe flag)."
    echo ""
fi

# ============================================================
# Phase 4: Multi-IDE rule injection
# ============================================================
info "Phase 4/6: Detecting and injecting multi-IDE rules..."

inject_brain_rules() {
    local target_file="$1"
    local ide_name="$2"

    if grep -q "Brain Auto-Write Protocol" "$target_file" 2>/dev/null; then
        ok "$ide_name: Brain auto-write rules already present. (idempotent)"
        return
    fi

    local template="$HARNESS_ROOT/brain-rules-template.md"
    if [ ! -f "$template" ]; then
        warn "brain-rules-template.md not found. Skipping $ide_name injection."
        return
    fi

    echo "" >> "$target_file"
    sed "s/<ide>/$ide_name/g" "$template" >> "$target_file"
    ok "$ide_name: Brain auto-write rules injected."
}

# Windsurf
WINDSURF_RULES="$TARGET_DIR/.windsurfrules"
if [ -f "$WINDSURF_RULES" ]; then
    inject_brain_rules "$WINDSURF_RULES" "windsurf"
fi

# Trae
TRAE_RULES_DIR="$TARGET_DIR/.trae"
if [ -d "$TRAE_RULES_DIR" ]; then
    for trae_file in "$TRAE_RULES_DIR/rules" "$TRAE_RULES_DIR/rules.md"; do
        if [ -f "$trae_file" ]; then
            inject_brain_rules "$trae_file" "trae"
            break
        fi
    done
fi

# VS Code Copilot
COPILOT_INSTRUCTIONS="$TARGET_DIR/.github/copilot-instructions.md"
if [ -f "$COPILOT_INSTRUCTIONS" ]; then
    inject_brain_rules "$COPILOT_INSTRUCTIONS" "copilot"
fi

# Add extra IDE files to .gitignore
EXTRA_IGNORE=()
[ -f "$WINDSURF_RULES" ] && EXTRA_IGNORE+=(".windsurfrules")
[ -d "$TRAE_RULES_DIR" ] && EXTRA_IGNORE+=(".trae/")

if [ ${#EXTRA_IGNORE[@]} -gt 0 ]; then
    for entry in "${EXTRA_IGNORE[@]}"; do
        if ! grep -qxF "$entry" "$GITIGNORE" 2>/dev/null; then
            echo "$entry" >> "$GITIGNORE"
            info "Added $entry to .gitignore"
        fi
    done
fi

ok "Multi-IDE detection complete."
echo ""

# ============================================================
# Phase 5: Brain repo — clone/connect
# ============================================================
info "Phase 5/6: Setting up Brain repository..."

# Source the shared brain resolver
source "$HARNESS_ROOT/brain-resolve.sh"
resolve_brain_dir "$HARNESS_ROOT"

if [ -n "$BRAIN_REPO_REMOTE" ]; then
    if [ -d "$BRAIN_REPO_LOCAL/.git" ]; then
        ok "Brain repo already cloned at: $BRAIN_REPO_LOCAL"
        info "Pulling latest brain data..."
        sync_brain_repo
        ok "Brain repo synced."
    else
        info "Attempting to clone brain repo: $BRAIN_REPO_REMOTE"
        info "  → $BRAIN_REPO_LOCAL"
        if clone_brain_repo "$HARNESS_ROOT"; then
            ok "Brain repo cloned successfully."
        else
            warn "Could not clone brain repo. This is normal for fork users."
            warn "Brain will use local fallback. You can configure your own brain repo later"
            warn "by editing .harness/.brain-config.yaml"
        fi
    fi

    # Re-resolve after potential clone
    resolve_brain_dir "$HARNESS_ROOT"

    # Create symlink: harness/brain/ → brain repo
    if [ "$BRAIN_IS_EXTERNAL" = "true" ]; then
        BRAIN_LINK="$HARNESS_ROOT/brain"
        if [ -L "$BRAIN_LINK" ]; then
            EXISTING_TARGET="$(readlink "$BRAIN_LINK")"
            if [ "$EXISTING_TARGET" = "$BRAIN_REPO_LOCAL" ]; then
                ok "brain/ symlink already correct. (idempotent)"
            else
                rm "$BRAIN_LINK"
                ln -s "$BRAIN_REPO_LOCAL" "$BRAIN_LINK"
                ok "brain/ symlink updated → $BRAIN_REPO_LOCAL"
            fi
        elif [ -d "$BRAIN_LINK" ]; then
            local_files=$(find "$BRAIN_LINK" -type f -not -name '.gitkeep' 2>/dev/null | wc -l | tr -d ' ')
            if [ "$local_files" -gt 0 ]; then
                warn "brain/ directory has $local_files file(s). Backing up to brain.local.bak/"
                mv "$BRAIN_LINK" "${BRAIN_LINK}.local.bak"
            else
                rm -rf "$BRAIN_LINK"
            fi
            ln -s "$BRAIN_REPO_LOCAL" "$BRAIN_LINK"
            ok "brain/ → $BRAIN_REPO_LOCAL"
        else
            ln -s "$BRAIN_REPO_LOCAL" "$BRAIN_LINK"
            ok "brain/ → $BRAIN_REPO_LOCAL"
        fi
    fi
else
    info "No brain_repo.remote configured. Using local brain/ directory."
    ok "Local brain mode (single-repo)."
fi

# --- Ensure brain directory structure exists ---
resolve_brain_dir "$HARNESS_ROOT"
mkdir -p "$BRAIN_DIR/global" "$BRAIN_DIR/projects" "$BRAIN_DIR/sessions"

# --- Brain global template files ---
if [ ! -f "$BRAIN_DIR/global/preferences.md" ]; then
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
    ok "Generated: brain/global/preferences.md"
fi

if [ ! -f "$BRAIN_DIR/global/gotchas.md" ]; then
    cat << 'GOTCHA_EOF' > "$BRAIN_DIR/global/gotchas.md"
# Global Gotchas (跨项目踩坑记录)

## ⚠️ Tool & Environment Pitfalls
<!-- Record cross-project tool/environment pitfalls here -->

## 🐛 Language & Framework Gotchas
<!-- Record language/framework-specific pitfalls that apply across projects -->

## 🔐 Security & Secrets
<!-- Record security-related lessons learned -->
GOTCHA_EOF
    ok "Generated: brain/global/gotchas.md"
fi

if [ ! -f "$BRAIN_DIR/MEMORY.md" ]; then
    cat << 'MEM_EOF' > "$BRAIN_DIR/MEMORY.md"
# 项目记忆与经验库 (Memory & Learnings)

## 🏗️ 架构决策记录 (ADR)
*在这里记录我们在对话中决定引入的新库、核心数据结构变更或重大架构妥协。*

## ⚠️ 已知天坑与环境限制 (Gotchas)
- (暂无)

## 💡 设计原则备忘
*从历史讨论中提炼的核心设计原则。*
MEM_EOF
    ok "Generated: brain/MEMORY.md"
fi

echo ""

# ============================================================
# Phase 5.5: Owner detection (reuse brain-init logic)
# ============================================================
info "Phase 5.5: Checking brain ownership..."

BRAIN_OWNER_FILE="$BRAIN_DIR/.brain-owner"

detect_current_owner() {
    local remote_url=""
    # Try harness repo remote first
    remote_url=$(git -C "$HARNESS_ROOT" remote get-url origin 2>/dev/null || echo "")
    if [ -z "$remote_url" ]; then
        echo ""
        return
    fi
    local owner=""
    if echo "$remote_url" | grep -qE '^https?://'; then
        owner=$(echo "$remote_url" | sed -E 's|https?://[^/]+/([^/]+)/.*|\1|')
    elif echo "$remote_url" | grep -qE '^git@'; then
        owner=$(echo "$remote_url" | sed -E 's|git@[^:]+:([^/]+)/.*|\1|')
    fi
    echo "$owner"
}

read_recorded_owner() {
    if [ -f "$BRAIN_OWNER_FILE" ]; then
        grep '^owner:' "$BRAIN_OWNER_FILE" 2>/dev/null | awk '{print $2}' | tr -d ' '
    else
        echo ""
    fi
}

detect_system_user() {
    whoami 2>/dev/null || echo ""
}

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

    cat << OWNER_EOF > "$BRAIN_OWNER_FILE"
# Brain Owner Identity
# Managed by setup.sh / brain-init.sh — DO NOT edit manually.
owner: $owner
repo: $new_repo
system_user: $sys_user
OWNER_EOF
}

reset_brain_for_new_owner() {
    local new_owner="$1"
    warn "Fork detected! Resetting brain data for new owner: $new_owner"

    # Clear sessions
    find "$BRAIN_DIR/sessions" -mindepth 1 -not -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
    touch "$BRAIN_DIR/sessions/.gitkeep"

    # Clear projects
    find "$BRAIN_DIR/projects" -mindepth 1 -not -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
    touch "$BRAIN_DIR/projects/.gitkeep"

    # Reset global templates
    cat << 'PREF_EOF' > "$BRAIN_DIR/global/preferences.md"
# Global Preferences (跨项目通用偏好)

## 🎨 Coding Style
## 🔧 Tool Chain
## 🗣️ Communication
## 📐 Architecture Principles
PREF_EOF

    cat << 'GOTCHA_EOF' > "$BRAIN_DIR/global/gotchas.md"
# Global Gotchas (跨项目踩坑记录)

## ⚠️ Tool & Environment Pitfalls
## 🐛 Language & Framework Gotchas
## 🔐 Security & Secrets
GOTCHA_EOF

    cat << 'MEM_EOF' > "$BRAIN_DIR/MEMORY.md"
# 项目记忆与经验库 (Memory & Learnings)

## 🏗️ 架构决策记录 (ADR)
## ⚠️ 已知天坑与环境限制 (Gotchas)
## 💡 设计原则备忘
MEM_EOF

    ok "Brain data reset for new owner: $new_owner"

    if [ "$BRAIN_IS_EXTERNAL" = "true" ]; then
        commit_brain_changes "brain: reset for new owner $new_owner" false 2>/dev/null || true
    fi
}

# --- Execute owner detection ---
CURRENT_OWNER=$(detect_current_owner)
RECORDED_OWNER=$(read_recorded_owner)
CURRENT_SYS_USER=$(detect_system_user)

if [ "$FRESH_MODE" = true ]; then
    EFFECTIVE_OWNER="${CURRENT_OWNER:-$CURRENT_SYS_USER}"
    reset_brain_for_new_owner "$EFFECTIVE_OWNER"
    record_owner "$EFFECTIVE_OWNER" "$CURRENT_SYS_USER"
elif [ -z "$RECORDED_OWNER" ]; then
    EFFECTIVE_OWNER="${CURRENT_OWNER:-$CURRENT_SYS_USER}"
    info "First-time setup. Recording owner: $EFFECTIVE_OWNER"
    record_owner "$EFFECTIVE_OWNER" "$CURRENT_SYS_USER"
    ok "Owner recorded."
elif [ -n "$CURRENT_OWNER" ] && [ "$CURRENT_OWNER" != "$RECORDED_OWNER" ]; then
    reset_brain_for_new_owner "$CURRENT_OWNER"
    record_owner "$CURRENT_OWNER" "$CURRENT_SYS_USER"
else
    ok "Owner verified: ${CURRENT_OWNER:-$CURRENT_SYS_USER}"
fi

echo ""

# ============================================================
# Phase 6: Verify — Run brain-check
# ============================================================
info "Phase 6/6: Running integrity check..."
echo ""

BRAIN_CHECK="$HARNESS_ROOT/brain-check.sh"
if [ -x "$BRAIN_CHECK" ]; then
    "$BRAIN_CHECK" "$TARGET_DIR"
    CHECK_EXIT=$?
else
    warn "brain-check.sh not found or not executable. Skipping verification."
    CHECK_EXIT=0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$CHECK_EXIT" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}🎉 Setup complete! Harness + Brain mounted successfully.${NC}"
else
    echo -e "${YELLOW}${BOLD}🎉 Setup completed with warnings. Please review above.${NC}"
fi
echo ""
echo "  What happened:"
echo "    ✅ .cursorrules → .harness/.cursorrules (AI coding rules)"
echo "    ✅ .prompts/    → .harness/.prompts/    (Agent role templates)"
echo "    ✅ .gitignore   updated (harness files isolated from project Git)"
if [ "$SKIP_VIBE" = false ]; then
    echo "    ✅ MEMORY.md, TODO.md, docs/architecture.md deployed"
fi
if [ "$BRAIN_IS_EXTERNAL" = "true" ]; then
    echo "    ✅ Brain repo connected: $BRAIN_REPO_LOCAL"
else
    echo "    ✅ Brain using local directory"
fi
echo ""
echo "  Next steps:"
echo "    1. Fill in Tech Stack Constraints in .cursorrules"
echo "    2. Start your first AI conversation — it will auto-detect the blank"
echo "       architecture.md and guide you through Goal Discovery."
echo "    3. Use '.harness/brain-push.sh' to write learnings."
echo "    4. Use '.harness/brain-search.sh <keyword>' to search memory."
echo ""
echo "  Update harness:"
echo "    cd .harness && git pull"
echo ""
