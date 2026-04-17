#!/bin/bash
set -euo pipefail

# ============================================================
# vibe-init.sh — Initialize Vibe Coding scaffold in a target project
#
# Mode A (default): Load from harness repo templates (recommended)
#   Usage: /path/to/mick_harness_rules/vibe-init.sh [target_project_dir]
#
# Mode B (legacy): Inline mode — generate all files from script
#   Usage: /path/to/mick_harness_rules/vibe-init.sh --inline [target_project_dir]
#
# After scaffold setup, automatically calls brain-init.sh to mount brain.
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

# --- Resolve harness repo root (where this script lives) ---
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- Parse arguments ---
MODE="harness"
TARGET_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --inline)
            MODE="inline"
            shift
            ;;
        --help|-h)
            echo "Usage: vibe-init.sh [OPTIONS] [target_project_dir]"
            echo ""
            echo "Initialize Vibe Coding scaffold in a target project."
            echo ""
            echo "Options:"
            echo "  --inline    Use legacy inline mode (generate files from script)"
            echo "              Default mode loads from harness repo templates."
            echo "  -h, --help  Show this help message"
            echo ""
            echo "Examples:"
            echo "  vibe-init.sh                    # Init current dir from harness templates"
            echo "  vibe-init.sh /path/to/project   # Init specific project"
            echo "  vibe-init.sh --inline            # Use legacy inline mode"
            exit 0
            ;;
        -*)
            fail "Unknown option: $1"
            echo "Run 'vibe-init.sh --help' for usage."
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
echo -e "${BOLD}🚀 Vibe Init — Setting up Vibe Coding scaffold${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Harness repo : $HARNESS_ROOT"
echo "  Target project: $TARGET_DIR"
echo "  Mode          : $MODE"
echo ""

# ============================================================
# Helper: Copy a file from harness repo to target, with safety
# - If target already exists as a regular file, back it up
# - If target is a symlink (from brain-init), skip it
# ============================================================
safe_copy() {
    local src="$1"
    local dst="$2"
    local label="$3"

    if [ ! -f "$src" ]; then
        warn "Source template not found: $src — skipping $label"
        return 1
    fi

    # If destination is a symlink (e.g., from brain-init), don't overwrite
    if [ -L "$dst" ]; then
        ok "$label already symlinked (managed by brain-init). Skipping."
        return 0
    fi

    # If destination exists as a regular file, back it up
    if [ -f "$dst" ]; then
        warn "$label already exists. Backing up to ${dst}.bak"
        cp "$dst" "${dst}.bak"
    fi

    # Ensure parent directory exists
    mkdir -p "$(dirname "$dst")"

    cp "$src" "$dst"
    ok "Deployed: $label"
}

# ============================================================
# Helper: Copy a directory from harness repo to target
# ============================================================
safe_copy_dir() {
    local src_dir="$1"
    local dst_dir="$2"
    local label="$3"

    if [ ! -d "$src_dir" ]; then
        warn "Source template directory not found: $src_dir — skipping $label"
        return 1
    fi

    mkdir -p "$dst_dir"

    # Copy each file in the source directory
    local copied=0
    while IFS= read -r src_file; do
        local relative="${src_file#$src_dir/}"
        local dst_file="$dst_dir/$relative"
        safe_copy "$src_file" "$dst_file" "$label/$relative"
        ((copied++))
    done < <(find "$src_dir" -type f 2>/dev/null)

    if [ "$copied" -eq 0 ]; then
        warn "No files found in $src_dir"
    fi
}

# ============================================================
# HARNESS MODE: Load from repo templates
# ============================================================
run_harness_mode() {
    info "Phase 1/4: Creating directory structure..."
    mkdir -p "$TARGET_DIR/docs"
    mkdir -p "$TARGET_DIR/docs/design"
    mkdir -p "$TARGET_DIR/.github/workflows"
    ok "Directory structure created."
    info "Note: .cursorrules and .prompts/ will be symlinked by brain-init (not copied)."

    echo ""
    info "Phase 2/4: Deploying core scaffold files..."
    # Note: .cursorrules is NOT copied here — it will be symlinked by brain-init.sh
    # This ensures no harness content leaks into the target project's Git history.

    # MEMORY.md
    # MEMORY.md — project-specific, generate fresh template if not exists
    if [ ! -f "$TARGET_DIR/MEMORY.md" ] && [ ! -L "$TARGET_DIR/MEMORY.md" ]; then
        cat << 'MEMORY_EOF' > "$TARGET_DIR/MEMORY.md"
# 项目记忆与经验库 (Memory & Learnings)

## 🏗️ 架构决策记录 (ADR)
- [$(date +'%Y-%m-%d')] 初始状态：确立 Vibe Coding 护栏机制。

## ⚠️ 已知天坑与环境限制 (Gotchas)
- (暂无)
MEMORY_EOF
        ok "Generated: MEMORY.md (fresh template)"
    else
        ok "MEMORY.md already exists. Skipping."
    fi

    # TODO.md — project-specific, generate fresh template if not exists
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
        ok "Generated: TODO.md (fresh template)"
    else
        ok "TODO.md already exists. Skipping."
    fi

    # docs/architecture.md — from harness template
    safe_copy "$HARNESS_ROOT/docs/architecture.md" "$TARGET_DIR/docs/architecture.md" "docs/architecture.md"

    # Note: .prompts/ is NOT copied here — it will be symlinked by brain-init.sh
    # This ensures Agent role prompts don't leak into the target project's Git history.

    echo ""
    info "Phase 3/4: Deploying CI/CD & Git templates..."

    # .pre-commit-config.yaml
    if [ -f "$HARNESS_ROOT/.pre-commit-config.yaml" ]; then
        safe_copy "$HARNESS_ROOT/.pre-commit-config.yaml" "$TARGET_DIR/.pre-commit-config.yaml" ".pre-commit-config.yaml"
    else
        # Generate a default pre-commit config
        if [ ! -f "$TARGET_DIR/.pre-commit-config.yaml" ]; then
            cat << 'PRECOMMIT_EOF' > "$TARGET_DIR/.pre-commit-config.yaml"
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
PRECOMMIT_EOF
            ok "Generated: .pre-commit-config.yaml (default)"
        else
            ok ".pre-commit-config.yaml already exists. Skipping."
        fi
    fi

    # .github/PULL_REQUEST_TEMPLATE.md
    if [ -f "$HARNESS_ROOT/.github/PULL_REQUEST_TEMPLATE.md" ]; then
        safe_copy "$HARNESS_ROOT/.github/PULL_REQUEST_TEMPLATE.md" "$TARGET_DIR/.github/PULL_REQUEST_TEMPLATE.md" ".github/PULL_REQUEST_TEMPLATE.md"
    fi

    # .github/workflows/ci.yml
    if [ -f "$HARNESS_ROOT/.github/workflows/ci.yml" ]; then
        safe_copy "$HARNESS_ROOT/.github/workflows/ci.yml" "$TARGET_DIR/.github/workflows/ci.yml" ".github/workflows/ci.yml"
    fi

    echo ""
    info "Phase 4/4: Installing physical guardrails..."

    # Install pre-commit hooks
    if command -v pre-commit &> /dev/null; then
        cd "$TARGET_DIR"
        if [ -d ".git" ] || git init -q 2>/dev/null; then
            pre-commit install 2>/dev/null && ok "pre-commit hooks installed." || warn "pre-commit install failed."
        fi
        cd - > /dev/null
    else
        warn "pre-commit not found. Run 'brew install pre-commit' then 'pre-commit install'."
    fi
}

# ============================================================
# INLINE MODE: Legacy — generate all files from heredocs
# (Kept for backward compatibility)
# ============================================================
run_inline_mode() {
    warn "Running in legacy inline mode. Consider using default harness mode instead."
    echo ""

    # 1. Create directories
    mkdir -p "$TARGET_DIR/docs" "$TARGET_DIR/docs/design" "$TARGET_DIR/.prompts" "$TARGET_DIR/.github/workflows"
    ok "Directory structure created."

    # 2. .cursorrules
    cat << 'EOF' > "$TARGET_DIR/.cursorrules"
# Role & Vibe (角色与基调)
- 定位：你是一位拥有 10 年以上经验的资深全栈架构师。交付企业级代码。
- 态度：极其务实，极简主义，拒绝过度工程。
- 沟通约束：绝对禁止废话。禁止说"好的"、"我明白了"等。直接输出思考过程或代码。

# 核心认知框架
1. 强制反思与目标对齐：操作前确认最终业务目标，防偏离。
2. 主动反驳机制：若我的需求偏离目标或有更好方案，必须提出质疑，不要盲从。

# 执行路径
1. 谋定而后动：写代码前必须在 <thinking> 标签内简述实现逻辑、设计模式和边界风险。
2. 上下文隔离：修改已有文件前必须完整阅读。绝不凭猜测覆盖代码。
3. 测试即契约 (TDD)：接收意图 -> 编写测试和契约 -> 运行失败 -> 编写实现直到通过。
4. 分步交付：复杂任务先输出核心骨架，我确认后再填细节。

# 代码哲学
- 防御性编程：不信任外部输入，完善边界检查和 Try/Catch。
- 单一职责：函数超一屏强制拆分。
- 尽早返回 (Early Return)：杜绝深层 if-else 嵌套。
- 自解释优先：变量/函数名具业务含义，少写What注释，只写Why注释。

# 调试与排错
- 拒绝盲目试错：报错必须先分析 Error Traceback。
- 日志先行：复杂 Bug 先加结构化日志缩小排查范围。

# 技术栈约束 (Tech Stack Constraints) — 项目初始化时填写，锁定后禁止 AI 擅自更换
- Language: (例如: TypeScript 5.x / Python 3.12)
- Framework: (例如: Next.js 14 / FastAPI)
- Database: (例如: PostgreSQL 16 / MongoDB 7)
- ORM/ODM: (例如: Prisma 5.x / SQLAlchemy 2.x)
- Package Manager: (例如: pnpm / uv)
- 禁止使用 (Banned): (例如: var, any 类型, jQuery, lodash)
- 强制使用 (Enforced): (例如: strict TypeScript, ESM only)

# Git 工作流与版本管理
- 分支策略：遵循项目选定的分支模型。未填写时默认 GitHub Flow。
  - main 分支永远可部署，禁止直接 push。
  - 功能分支命名：feat/简短描述、fix/简短描述、chore/简短描述。
- Commit 规范：严格遵循 Conventional Commits。
  - 格式：<type>(<scope>): <description>
  - type 枚举：feat | fix | docs | style | refactor | perf | test | chore | ci | build | revert
- PR/MR 规范：标题遵循 Conventional Commits，描述包含 What/Why/How to test。
- 版本号策略：遵循 Semantic Versioning 2.0。
- Tag 与 Release：每次发布打 Git Tag (vX.Y.Z)，生成 CHANGELOG。

# CI/CD 护栏
- Pipeline 阶段：lint -> test -> build -> security -> deploy
- 质量门禁：测试覆盖率低于阈值、存在 Critical 安全漏洞、Lint 错误 > 0 时 Pipeline 中断。
- 环境隔离：dev / staging / production。
- 密钥管理：所有密钥通过 CI/CD Secrets 管理，绝对禁止硬编码。

# 状态管理与上下文护栏
- 架构决策记录：引入新库或遇环境坑，主动提示我更新到 docs/architecture.md 或 MEMORY.md。
- 活文档同步：重构后强制更新相关文档。
- 待办收尾：完成后主动清理 TODO.md，并输出 Conventional Commits 规范的提交信息。

# 智能角色路由 (Auto Role Routing)
当对话上下文中已加载了 .prompts/ 下的角色模板时，根据消息意图自动匹配角色回答。
回复开头用 [🎭 角色名] 标注当前激活的角色。
路由规则：
1. 显式指令优先：明确说了用某角色，无条件切换。
2. 意图匹配：需求/PRD/业务->PM, UI/设计->Designer, 测试/用例->QA, 审查/Review->Reviewer, 编码/调试->Dev(默认)。
3. 混合意图：以主要意图角色回答，末尾提示是否需要切换。
4. 角色惯性：连续工作流中保持当前角色，除非意图明显偏移。
EOF
    ok "Generated: .cursorrules (inline)"

    # 3. MEMORY.md
    cat << 'EOF' > "$TARGET_DIR/MEMORY.md"
# 项目记忆与经验库 (Memory & Learnings)

## 🏗️ 架构决策记录 (ADR)
- [$(date +'%Y-%m-%d')] 初始状态：确立 Vibe Coding 护栏机制。

## ⚠️ 已知天坑与环境限制 (Gotchas)
- (暂无)
EOF
    ok "Generated: MEMORY.md (inline)"

    # 4. TODO.md
    cat << 'EOF' > "$TARGET_DIR/TODO.md"
# 项目待办与状态流转

## 🚧 当前进行中 (In Progress)
- [ ]

## 📋 待办清单 (Backlog)
- [ ] 编写核心业务逻辑
- [ ] 跑通基础自动化测试

## ✅ 已完成 (Done)
- [x] 初始化 Vibe Coding 脚手架
EOF
    ok "Generated: TODO.md (inline)"

    # 5. docs/architecture.md (minimal inline version)
    cat << 'EOF' > "$TARGET_DIR/docs/architecture.md"
# 系统架构与业务上下文

## 🎯 业务最终目标
(用一两句话描述这个项目的最终形态和核心价值。)

## 🧩 核心模块划分
| 模块名 | 职责描述 | 对外暴露接口 | 依赖的其他模块 |
|--------|---------|-------------|---------------|
| (模块 A) | (描述职责) | (接口列表) | (依赖列表) |

## 🗄️ 核心数据模型
(描述核心实体及其关系。建议用 Mermaid ER 图。)

## 🔌 API 契约概览
| 端点 | 方法 | 用途 | 请求体摘要 | 响应体摘要 | 鉴权 |
|------|------|------|-----------|-----------|------|
| /api/v1/xxx | POST | (用途) | { ... } | { ... } | (Bearer / API Key / 无) |
EOF
    ok "Generated: docs/architecture.md (inline)"

    # 6. .pre-commit-config.yaml
    cat << 'EOF' > "$TARGET_DIR/.pre-commit-config.yaml"
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
EOF
    ok "Generated: .pre-commit-config.yaml (inline)"

    # 7. Install pre-commit
    if command -v pre-commit &> /dev/null; then
        cd "$TARGET_DIR"
        git init -q 2>/dev/null || true
        pre-commit install 2>/dev/null && ok "pre-commit hooks installed." || warn "pre-commit install failed."
        cd - > /dev/null
    else
        warn "pre-commit not found. Run 'brew install pre-commit' then 'pre-commit install'."
    fi

    # 8. .github/PULL_REQUEST_TEMPLATE.md
    mkdir -p "$TARGET_DIR/.github"
    cat << 'EOF' > "$TARGET_DIR/.github/PULL_REQUEST_TEMPLATE.md"
## What (做了什么)
<!-- 简述本次变更的内容 -->

## Why (为什么)
<!-- 说明变更的业务背景或技术原因 -->

## How to Test (如何测试)
<!-- 描述验证步骤，或说明已通过的自动化测试 -->

## Checklist
- [ ] 代码遵循项目 `.cursorrules` 中的编码规范
- [ ] 已编写/更新对应的测试用例
- [ ] 已更新相关文档 (architecture.md / MEMORY.md / TODO.md)
- [ ] 无新增 Lint 错误
- [ ] 已通过 Reviewer Agent 审查（或已提交审查请求）

## Related
<!-- 关联的 Issue / TODO 项 / 其他 PR -->
EOF
    ok "Generated: .github/PULL_REQUEST_TEMPLATE.md (inline)"

    # 9. .github/workflows/ci.yml
    mkdir -p "$TARGET_DIR/.github/workflows"
    cat << 'EOF' > "$TARGET_DIR/.github/workflows/ci.yml"
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  lint:
    name: "🧹 Lint"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run linter
        run: echo "TODO: replace with actual lint command"

  test:
    name: "🧪 Test"
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: echo "TODO: replace with actual test command"

  build:
    name: "📦 Build"
    runs-on: ubuntu-latest
    needs: [test]
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: echo "TODO: replace with actual build command"
EOF
    ok "Generated: .github/workflows/ci.yml (inline)"
}

# ============================================================
# MAIN EXECUTION
# ============================================================

case "$MODE" in
    harness)
        run_harness_mode
        ;;
    inline)
        run_inline_mode
        ;;
esac

echo ""
ok "Vibe Coding scaffold setup complete!"

# ============================================================
# AUTO-CHAIN: Call brain-init.sh to mount brain
# ============================================================
echo ""
echo -e "${BOLD}🧠 Chaining to Brain Init...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BRAIN_INIT="$HARNESS_ROOT/brain-init.sh"
if [ -x "$BRAIN_INIT" ]; then
    "$BRAIN_INIT" "$TARGET_DIR"
    BRAIN_EXIT=$?
else
    warn "brain-init.sh not found or not executable at: $BRAIN_INIT"
    warn "Skipping brain mount. Run 'brain-init.sh' manually later."
    BRAIN_EXIT=0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$BRAIN_EXIT" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}🎉 Vibe Init + Brain Mount complete! Start your flow.${NC}"
else
    echo -e "${YELLOW}${BOLD}🎉 Vibe Init complete, but Brain Mount had warnings. Review above.${NC}"
fi
echo ""
echo "  Next steps:"
echo "  1. Fill in Tech Stack Constraints in .cursorrules"
echo "  2. Describe your business goal in docs/architecture.md"
echo "  3. Start Vibe Coding — AI will follow your harness rules + brain memory."
echo ""