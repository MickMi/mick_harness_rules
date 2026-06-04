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
#   --fresh           Start with a clean brain (for fork/clone users)
#   --no-vibe         Skip Vibe scaffold files (MEMORY.md, TODO.md, docs/)
#   --reconfigure     Re-run interactive workflow configuration (overwrites .harness-config.yaml)
#   --non-interactive Skip interactive questions, use defaults (or values from --profile)
#   --profile FILE    Load answers from a YAML profile file (for CI / repeatable setup)
#   -h, --help        Show this help message
#
# What it does:
#   1. Detect parent directory as target project
#   2. Symlink .cursorrules and .prompts/ into project root
#   3. Configure .gitignore to isolate harness files
#   4. Deploy Vibe scaffold files (skip if already exist)
#   5. ✨ Interactive workflow configuration → .harness-config.yaml
#   6. Inject multi-IDE rules
#   7. Clone/connect brain repo (fallback to local if unavailable)
#   8. Run brain-check to verify integrity
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
RECONFIGURE=false
NON_INTERACTIVE=false
PROFILE_FILE=""

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
        --reconfigure)
            RECONFIGURE=true
            shift
            ;;
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --profile)
            shift
            PROFILE_FILE="${1:-}"
            if [ -z "$PROFILE_FILE" ]; then
                fail "--profile requires a file path argument"
                exit 1
            fi
            shift
            ;;
        --help|-h)
            echo "Usage: .harness/setup.sh [OPTIONS]"
            echo ""
            echo "One-step project bootstrap. Run from your project root after cloning"
            echo "the harness repo as .harness/ subdirectory."
            echo ""
            echo "Options:"
            echo "  --fresh             Start with a clean brain (for new users who cloned/forked)"
            echo "  --no-vibe           Skip Vibe scaffold files (MEMORY.md, TODO.md, docs/)"
            echo "  --reconfigure       Re-run interactive workflow configuration (overwrites .harness-config.yaml)"
            echo "  --non-interactive   Skip interactive questions, use defaults"
            echo "  --profile FILE      Load answers from a YAML profile file"
            echo "  -h, --help          Show this help message"
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
echo "  Reconfigure     : $RECONFIGURE"
echo "  Non-interactive : $NON_INTERACTIVE"
[ -n "$PROFILE_FILE" ] && echo "  Profile file    : $PROFILE_FILE"
echo ""

# --- Make all scripts executable ---
info "Making harness scripts executable..."
chmod +x "$HARNESS_ROOT"/*.sh 2>/dev/null || true
ok "Scripts are executable."
echo ""

# ============================================================
# Phase 1: Symlink key files into project root
# ============================================================
info "Phase 1/7: Symlinking key files into project root..."

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
info "Phase 2/7: Configuring .gitignore isolation..."

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
    info "Phase 3/7: Deploying Vibe scaffold files (skip if already exist)..."

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
    info "Phase 3/7: Skipped (--no-vibe flag)."
    echo ""
fi

# ============================================================
# Phase 4: Workflow Configuration (interactive Q&A)
# ============================================================
info "Phase 4/7: Workflow configuration..."

CONFIG_FILE="$TARGET_DIR/.harness-config.yaml"
TEMPLATE_FILE="$HARNESS_ROOT/.harness-config.template.yaml"

# Setup interaction language (en | zh) — chosen via Q0 below.
# Resolution order:
#   1. SETUP_LANG environment variable (highest, for CI / scripted runs)
#   2. Pre-existing .harness-config.yaml meta.language (so --reconfigure remembers)
#   3. Q0 interactive prompt
#   4. Default "en" if all above unavailable (non-interactive mode)
SETUP_LANG="${SETUP_LANG:-en}"
if [ -f "$CONFIG_FILE" ] && [ -z "${SETUP_LANG_FROM_ENV:-}" ]; then
    EXISTING_LANG=$(grep -E '^\s*language:\s*"(en|zh)"' "$CONFIG_FILE" 2>/dev/null | head -1 | sed -E 's/.*"(en|zh)".*/\1/')
    [ -n "$EXISTING_LANG" ] && SETUP_LANG="$EXISTING_LANG"
fi
# Mark whether SETUP_LANG was supplied externally (so Q0 won't override it in NON_INTERACTIVE)
[ -n "${SETUP_LANG_EXTERNAL:-}" ] || SETUP_LANG_EXTERNAL=false
if [ -n "${SETUP_LANG_PRESET:-}" ]; then
    SETUP_LANG="$SETUP_LANG_PRESET"
    SETUP_LANG_EXTERNAL=true
fi

# --- i18n helper: pick string based on SETUP_LANG ---
# Usage: t "english string" "中文字符串"
t() {
    if [ "$SETUP_LANG" = "zh" ]; then
        echo "$2"
    else
        echo "$1"
    fi
}

# --- Helper: ask language (Q0, bilingual prompt) ---
ask_language() {
    # If SETUP_LANG was supplied externally (env var / preset), skip Q0.
    if [ "$SETUP_LANG_EXTERNAL" = true ]; then
        info "Language preset: $SETUP_LANG (from environment / preset)"
        return
    fi

    echo ""
    echo -e "${BOLD}🌐 Choose language / 选择语言${NC}"
    if [ "$SETUP_LANG" = "zh" ]; then
        echo "     [1] English"
        echo "   ▶ [2] 中文 (Simplified Chinese)"
    else
        echo "   ▶ [1] English"
        echo "     [2] 中文 (Simplified Chinese)"
    fi
    echo ""
    local default_idx=1
    [ "$SETUP_LANG" = "zh" ] && default_idx=2
    echo -n "   Choose / 选择 [1-2, default=$default_idx]: "

    if [ "$NON_INTERACTIVE" = true ] || [ ! -t 0 ]; then
        echo "$default_idx (default)"
        return
    fi

    local input
    read -r input
    input="${input:-$default_idx}"
    case "$input" in
        2) SETUP_LANG="zh" ;;
        1) SETUP_LANG="en" ;;
        *) ;;  # invalid → keep current default
    esac
}

# --- Helper: ask a single-choice question ---
# Usage: ask_choice "Question?" "default_value" "label1:value1" "label2:value2" ...
# Sets global variable ASK_RESULT
ask_choice() {
    local question="$1"
    local default="$2"
    shift 2
    local -a labels=()
    local -a values=()
    for pair in "$@"; do
        labels+=("${pair%%:*}")
        values+=("${pair#*:}")
    done

    echo ""
    echo -e "${BOLD}❓ $question${NC}"
    local i=1
    local default_idx=1
    for ((j=0; j<${#labels[@]}; j++)); do
        local marker="  "
        if [ "${values[$j]}" = "$default" ]; then
            marker=" ▶"
            default_idx=$((j+1))
        fi
        echo "  $marker [$((j+1))] ${labels[$j]}"
    done
    echo ""
    local prompt_choose
    prompt_choose=$(t "Choose" "选择")
    local prompt_default
    prompt_default=$(t "default" "默认")
    echo -n "  $prompt_choose [1-${#labels[@]}, $prompt_default=$default_idx]: "

    if [ "$NON_INTERACTIVE" = true ] || [ ! -t 0 ]; then
        echo "$default_idx ($(t 'non-interactive default' '非交互模式默认值'))"
        ASK_RESULT="$default"
        return
    fi

    local input
    read -r input
    input="${input:-$default_idx}"

    if [[ ! "$input" =~ ^[0-9]+$ ]] || [ "$input" -lt 1 ] || [ "$input" -gt "${#labels[@]}" ]; then
        warn "$(t "Invalid input '$input', using default." "无效输入 '$input'，使用默认值。")"
        ASK_RESULT="$default"
        return
    fi

    ASK_RESULT="${values[$((input-1))]}"
}

# --- Helper: ask a free-text question (with default) ---
ask_text() {
    local question="$1"
    local default="$2"
    echo ""
    echo -e "${BOLD}❓ $question${NC}"
    if [ -n "$default" ]; then
        echo -n "  $(t 'Answer' '回答') [$(t 'default' '默认'): $default]: "
    else
        echo -n "  $(t 'Answer (leave blank to skip)' '回答（留空跳过）'): "
    fi

    if [ "$NON_INTERACTIVE" = true ] || [ ! -t 0 ]; then
        echo "$default ($(t 'non-interactive' '非交互'))"
        ASK_RESULT="$default"
        return
    fi

    local input
    read -r input
    ASK_RESULT="${input:-$default}"
}

# --- Decide whether to run the Q&A ---
RUN_INTERACTIVE_CONFIG=false
if [ ! -f "$CONFIG_FILE" ]; then
    info "No .harness-config.yaml found. Running first-time configuration..."
    RUN_INTERACTIVE_CONFIG=true
elif [ "$RECONFIGURE" = true ]; then
    info "--reconfigure specified. Re-running workflow configuration..."
    RUN_INTERACTIVE_CONFIG=true
else
    ok ".harness-config.yaml already exists. Use --reconfigure to change. (idempotent)"
fi

if [ "$RUN_INTERACTIVE_CONFIG" = true ]; then
    # --- Profile file (CI / repeatable setup) ---
    if [ -n "$PROFILE_FILE" ] && [ -f "$PROFILE_FILE" ]; then
        info "Loading answers from profile: $PROFILE_FILE"
        cp "$PROFILE_FILE" "$CONFIG_FILE"
        ok "Generated: .harness-config.yaml (from profile)"
    else
        # Q0: language (bilingual prompt — Q0 itself is shown in both languages)
        ask_language

        echo ""
        if [ "$SETUP_LANG" = "zh" ]; then
            echo "━━━ 工作流配置 (5 个问题) ━━━"
            echo "  按回车键采用默认值；--non-interactive 全部用默认。"
        else
            echo "━━━ Workflow Configuration (5 questions) ━━━"
            echo "  Skip with Enter to accept defaults; --non-interactive uses all defaults."
        fi
        echo ""

        # Q1: Brain
        if [ "$SETUP_LANG" = "zh" ]; then
            ask_choice "1/5 启用 Brain（跨对话记忆）？" "true" \
                "是（推荐）— 自动记录踩坑 / 决策:true" \
                "否 — 在本项目禁用 Brain:false"
        else
            ask_choice "1/5 Use Brain (cross-conversation memory)?" "true" \
                "Yes (recommended) — auto-record gotchas / decisions:true" \
                "No — disable Brain for this project:false"
        fi
        BRAIN_ENABLED="$ASK_RESULT"

        # Q2: Design mode
        if [ "$SETUP_LANG" = "zh" ]; then
            ask_choice "2/5 你的设计是怎么做的？" "html" \
                "AI 出 HTML 视觉稿（无独立设计师）:html" \
                "AI 出 spec.json 喂给 Figma Maker / OpenDesign / ClaudeIsland 等:ai_tool_spec" \
                "AI 出设计简报给真人设计师（Figma）:designer_brief" \
                "纯后端 / CLI — 跳过设计阶段:skip"
        else
            ask_choice "2/5 How is your design work done?" "html" \
                "AI outputs HTML mockup (no separate designer):html" \
                "AI outputs spec.json for Figma Maker / OpenDesign / ClaudeIsland etc.:ai_tool_spec" \
                "AI outputs design brief for a human designer (Figma):designer_brief" \
                "Pure backend / CLI — skip design phase:skip"
        fi
        DESIGN_MODE="$ASK_RESULT"

        DESIGN_AI_TOOL="generic"
        if [ "$DESIGN_MODE" = "ai_tool_spec" ]; then
            if [ "$SETUP_LANG" = "zh" ]; then
                ask_choice "  └─ 用哪个 AI 设计工具？" "generic" \
                    "通用（兼容性最好）:generic" \
                    "Figma Maker:figma_maker" \
                    "OpenDesign:open_design" \
                    "ClaudeIsland:claude_island"
            else
                ask_choice "  └─ Which AI design tool?" "generic" \
                    "Generic (most compatible):generic" \
                    "Figma Maker:figma_maker" \
                    "OpenDesign:open_design" \
                    "ClaudeIsland:claude_island"
            fi
            DESIGN_AI_TOOL="$ASK_RESULT"
        fi

        # Q3: Dev scope
        if [ "$SETUP_LANG" = "zh" ]; then
            ask_choice "3/5 开发范围？" "fullstack" \
                "全栈（后端 + 前端）:fullstack" \
                "仅后端:backend_only" \
                "仅前端:frontend_only" \
                "移动端 / 桌面客户端（Swift / Kotlin / RN / Flutter）:mobile" \
                "CLI / 库:cli_lib"
        else
            ask_choice "3/5 Dev scope?" "fullstack" \
                "Full-stack (backend + frontend):fullstack" \
                "Backend only:backend_only" \
                "Frontend only:frontend_only" \
                "Mobile / desktop client (Swift / Kotlin / RN / Flutter):mobile" \
                "CLI / library:cli_lib"
        fi
        DEV_SCOPE="$ASK_RESULT"

        # Q4: Testing
        if [ "$SETUP_LANG" = "zh" ]; then
            ask_choice "4/5 测试投入？" "critical_path" \
                "严格 TDD（覆盖率 ≥80%，测试先行）:strict_tdd" \
                "关键路径覆盖（覆盖率 ≥50%，仅 P0 用例）:critical_path" \
                "仅冒烟（核心场景手测）:smoke_only" \
                "不写测试（跳过 QA Agent）:none"
        else
            ask_choice "4/5 Testing strictness?" "critical_path" \
                "Strict TDD (≥80% coverage, tests-first):strict_tdd" \
                "Critical path only (≥50% coverage, P0 cases):critical_path" \
                "Smoke only (manual key flows):smoke_only" \
                "No tests (skip QA Agent):none"
        fi
        TESTING_MODE="$ASK_RESULT"

        # Q5: Strictness
        if [ "$SETUP_LANG" = "zh" ]; then
            ask_choice "5/5 流程严格度？" "soft" \
                "强门禁（PRD 不锁定不让动代码）:strong" \
                "软提示（推荐 — 警告但允许跳过）:soft" \
                "自由（用户主导，AI 不主动拦截）:free"
        else
            ask_choice "5/5 Workflow strictness?" "soft" \
                "Strong gate (PRD must be locked before any code):strong" \
                "Soft hint (recommended — warn but allow override):soft" \
                "Free (user-driven, AI never blocks):free"
        fi
        STRICTNESS_MODE="$ASK_RESULT"

        # --- Render config from template ---
        if [ -f "$TEMPLATE_FILE" ]; then
            cp "$TEMPLATE_FILE" "$CONFIG_FILE"
            # Patch the answers in (sed in-place; macOS-compatible)
            SED_INPLACE=(-i '')
            if sed --version >/dev/null 2>&1; then
                SED_INPLACE=(-i)
            fi
            sed "${SED_INPLACE[@]}" -E "s/^(  language:) \"en\".*/\\1 \"${SETUP_LANG}\"/" "$CONFIG_FILE"
            sed "${SED_INPLACE[@]}" -E "s/^(  enabled:) .*/\\1 ${BRAIN_ENABLED}/" "$CONFIG_FILE"
            sed "${SED_INPLACE[@]}" -E "s/^(  mode:) \"html\".*/\\1 \"${DESIGN_MODE}\"/" "$CONFIG_FILE"
            sed "${SED_INPLACE[@]}" -E "s/^(  ai_tool:) \"generic\".*/\\1 \"${DESIGN_AI_TOOL}\"/" "$CONFIG_FILE"
            sed "${SED_INPLACE[@]}" -E "s/^(  scope:) \"fullstack\".*/\\1 \"${DEV_SCOPE}\"/" "$CONFIG_FILE"
            sed "${SED_INPLACE[@]}" -E "s/^(  mode:) \"critical_path\".*/\\1 \"${TESTING_MODE}\"/" "$CONFIG_FILE"
            sed "${SED_INPLACE[@]}" -E "s/^(  mode:) \"soft\".*/\\1 \"${STRICTNESS_MODE}\"/" "$CONFIG_FILE"
            ok "$(t 'Generated: .harness-config.yaml' '生成: .harness-config.yaml')"
        else
            warn ".harness-config.template.yaml not found. Writing minimal config..."
            cat > "$CONFIG_FILE" <<EOF
version: 1
meta: { language: "${SETUP_LANG}" }
brain: { enabled: ${BRAIN_ENABLED}, path: "~/.mick-brain" }
design: { mode: "${DESIGN_MODE}", ai_tool: "${DESIGN_AI_TOOL}" }
dev: { scope: "${DEV_SCOPE}", tech_stack: { language: "", framework: "", database: "", package_manager: "" } }
testing: { mode: "${TESTING_MODE}", coverage_threshold: 50 }
strictness: { mode: "${STRICTNESS_MODE}", pm_max_rounds: 3 }
EOF
            ok "Generated: .harness-config.yaml (minimal)"
        fi

        # --- Update STATE.md if design.mode = skip ---
        STATE_FILE="$TARGET_DIR/docs/STATE.md"
        if [ "$DESIGN_MODE" = "skip" ] && [ -f "$STATE_FILE" ]; then
            info "$(t 'design.mode=skip → reminder: review docs/STATE.md and remove the Designer line' \
                       'design.mode=skip → 提醒：请检查 docs/STATE.md 并移除 Designer 阶段那一行')"
        fi

        echo ""
        if [ "$SETUP_LANG" = "zh" ]; then
            echo "  📋 配置概要："
            echo "    meta.language    = ${SETUP_LANG}"
            echo "    brain.enabled    = ${BRAIN_ENABLED}"
            echo "    design.mode      = ${DESIGN_MODE} (${DESIGN_AI_TOOL})"
            echo "    dev.scope        = ${DEV_SCOPE}"
            echo "    testing.mode     = ${TESTING_MODE}"
            echo "    strictness.mode  = ${STRICTNESS_MODE}"
            echo ""
            echo "  💡 随时编辑：\$EDITOR .harness-config.yaml"
            echo "  💡 重跑问答：.harness/setup.sh --reconfigure"
        else
            echo "  📋 Configuration summary:"
            echo "    meta.language    = ${SETUP_LANG}"
            echo "    brain.enabled    = ${BRAIN_ENABLED}"
            echo "    design.mode      = ${DESIGN_MODE} (${DESIGN_AI_TOOL})"
            echo "    dev.scope        = ${DEV_SCOPE}"
            echo "    testing.mode     = ${TESTING_MODE}"
            echo "    strictness.mode  = ${STRICTNESS_MODE}"
            echo ""
            echo "  💡 Edit anytime: \$EDITOR .harness-config.yaml"
            echo "  💡 Re-run Q&A:   .harness/setup.sh --reconfigure"
        fi
    fi
fi

echo ""

# ============================================================
# Phase 4: Multi-IDE rule injection
# ============================================================
info "Phase 5/7: Detecting and injecting multi-IDE rules..."

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
info "Phase 6/7: Setting up Brain repository..."

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
info "Phase 7/7: Running integrity check..."
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
if [ -f "$CONFIG_FILE" ]; then
    echo "    ✅ .harness-config.yaml ready (workflow config — commit to project)"
fi
if [ "$BRAIN_IS_EXTERNAL" = "true" ]; then
    echo "    ✅ Brain repo connected: $BRAIN_REPO_LOCAL"
else
    echo "    ✅ Brain using local directory"
fi
echo ""
echo "  Next steps:"
echo "    1. Review .harness-config.yaml (or run --reconfigure to redo Q&A)"
echo "    2. Fill in Tech Stack Constraints in .cursorrules (or in config's dev.tech_stack)"
echo "    3. Start your first AI conversation — it will read STATE.md + config."
echo "    4. Use '.harness/brain-push.sh' to write learnings."
echo ""
echo "  Update harness:"
echo "    cd .harness && git pull"
echo ""
