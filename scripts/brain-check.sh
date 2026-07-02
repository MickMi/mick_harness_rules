#!/bin/bash
set -uo pipefail

# ============================================================
# brain-check.sh — Verify harness + brain mount integrity
# Usage: /path/to/mick_harness_rules/scripts/brain-check.sh [target_project_dir]
# If no target dir is given, uses current working directory.
#
# Exit codes:
#   0 = all checks passed (or only warnings)
#   1 = critical check failed
# ============================================================

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Counters ---
PASS=0
WARN=0
FAIL=0

check_pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; ((PASS++)); }
check_warn() { echo -e "  ${YELLOW}⚠️  WARN${NC}: $1"; ((WARN++)); }
check_fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; ((FAIL++)); }

# --- Resolve harness repo root ---
HARNESS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --- Source shared brain resolver ---
source "$HARNESS_ROOT/scripts/brain-resolve.sh"
resolve_brain_dir "$HARNESS_ROOT"

# --- Resolve target project directory ---
TARGET_DIR="${1:-$(pwd)}"
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}❌ Target directory does not exist: $TARGET_DIR${NC}"
    exit 1
fi
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

resolve_link_target() {
    local link_path="$1"
    local raw_target
    raw_target="$(readlink "$link_path")"
    if [[ "$raw_target" = /* ]]; then
        echo "$raw_target"
    else
        echo "$(cd "$(dirname "$link_path")" && pwd)/$raw_target"
    fi
}

echo "🔍 Brain Check — Verifying harness + brain integrity"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Harness repo : $HARNESS_ROOT"
echo "  Target project: $TARGET_DIR"
echo ""

# ============================================================
# Check 1: .harness/ symlink exists and is valid
# ============================================================
echo "📋 Check 1: .harness/ symlink"
HARNESS_LINK="$TARGET_DIR/.harness"
if [ -L "$HARNESS_LINK" ]; then
    LINK_TARGET="$(resolve_link_target "$HARNESS_LINK")"
    if [ -d "$LINK_TARGET" ]; then
        check_pass ".harness/ → $LINK_TARGET (valid)"
    else
        check_fail ".harness/ symlink exists but target is broken: $LINK_TARGET"
    fi
elif [ -d "$HARNESS_LINK" ]; then
    check_warn ".harness/ exists as a real directory (not a symlink). Consider using symlink for sync."
else
    check_fail ".harness/ does not exist. Run 'harness init' or '.harness/setup.sh' first."
fi

# ============================================================
# Check 2: AGENTS.md exists and is non-empty
# ============================================================
echo "📋 Check 2: AGENTS.md"
AGENTS_MD="$TARGET_DIR/AGENTS.md"
if [ -L "$AGENTS_MD" ] || [ -f "$AGENTS_MD" ]; then
    if [ -s "$AGENTS_MD" ]; then
        LINE_COUNT=$(wc -l < "$AGENTS_MD" | tr -d ' ')
        check_pass "AGENTS.md exists and is non-empty ($LINE_COUNT lines)"
    else
        check_fail "AGENTS.md exists but is empty!"
    fi
else
    check_fail "AGENTS.md does not exist. Run 'harness init' or '.harness/setup.sh' first."
fi

# ============================================================
# Check 3: .prompts/ symlink is valid when compatibility mode uses it
# ============================================================
echo "📋 Check 3: .prompts/ compatibility symlink"
PROMPTS_LINK="$TARGET_DIR/.prompts"
if [ -L "$PROMPTS_LINK" ]; then
    PROMPTS_TARGET="$(resolve_link_target "$PROMPTS_LINK")"
    if [ -d "$PROMPTS_TARGET" ]; then
        check_pass ".prompts/ → $PROMPTS_TARGET (valid symlink)"
    else
        check_fail ".prompts/ symlink exists but target is broken: $PROMPTS_TARGET"
    fi
elif [ -d "$PROMPTS_LINK" ]; then
    check_warn ".prompts/ exists as a real directory (not a symlink). Agent prompts may leak into project Git."
else
    check_pass ".prompts/ not mounted (OK in default single-entry mode)"
fi

# ============================================================
# Check 4: .gitignore contains isolation entries
# ============================================================
echo "📋 Check 4: .gitignore isolation"
GITIGNORE="$TARGET_DIR/.gitignore"
if [ -f "$GITIGNORE" ]; then
    MISSING_ENTRIES=()
    REQUIRED_IGNORE_ENTRIES=(".harness/" ".harness")
    for owned in "AGENTS.md" "CLAUDE.md" ".cursorrules" ".windsurfrules" ".clinerules" ".github/copilot-instructions.md" ".trae/rules.md" ".prompts" ".prompts/"; do
        if [ -L "$TARGET_DIR/$owned" ]; then
            REQUIRED_IGNORE_ENTRIES+=("$owned")
        fi
    done
    for entry in "${REQUIRED_IGNORE_ENTRIES[@]}"; do
        if ! grep -qxF "$entry" "$GITIGNORE" 2>/dev/null; then
            MISSING_ENTRIES+=("$entry")
        fi
    done
    if [ ${#MISSING_ENTRIES[@]} -eq 0 ]; then
        check_pass ".gitignore contains all isolation entries"
    else
        check_warn ".gitignore missing entries: ${MISSING_ENTRIES[*]}"
        echo -e "         ${YELLOW}Run 'harness init' or '.harness/setup.sh' to update it.${NC}"
    fi
else
    check_warn ".gitignore does not exist. Harness files may leak into project git."
fi

# ============================================================
# Check 5: Brain repository connection (dual-repo model)
# ============================================================
echo "📋 Check 5: Brain repository"
if [ "$BRAIN_IS_EXTERNAL" = "true" ]; then
    if [ -d "$BRAIN_REPO_LOCAL/.git" ]; then
        check_pass "External brain repo connected: $BRAIN_REPO_LOCAL"
        # Check if brain/ is a symlink to the brain repo
        BRAIN_LINK="$HARNESS_ROOT/brain"
        if [ -L "$BRAIN_LINK" ]; then
            LINK_TARGET="$(readlink "$BRAIN_LINK")"
            if [ "$LINK_TARGET" = "$BRAIN_REPO_LOCAL" ]; then
                check_pass "brain/ symlink → $BRAIN_REPO_LOCAL (correct)"
            else
                check_warn "brain/ symlink points to $LINK_TARGET (expected $BRAIN_REPO_LOCAL)"
            fi
        elif [ -d "$BRAIN_LINK" ]; then
            check_warn "brain/ is a real directory, not a symlink. Run '.harness/setup.sh --full' to fix."
        fi
        # Check remote sync status
        if git -C "$BRAIN_REPO_LOCAL" remote get-url origin &>/dev/null; then
            check_pass "Brain repo has remote: $(git -C "$BRAIN_REPO_LOCAL" remote get-url origin 2>/dev/null)"
        else
            check_warn "Brain repo has no remote configured."
        fi
    else
        check_fail "Brain repo configured but not cloned at: $BRAIN_REPO_LOCAL"
        echo -e "         ${YELLOW}Run '.harness/setup.sh --full' to clone it.${NC}"
    fi
else
    if [ -n "$BRAIN_REPO_REMOTE" ]; then
        check_warn "Brain repo configured ($BRAIN_REPO_REMOTE) but not cloned. Run '.harness/setup.sh --full'."
    else
        check_pass "Using local brain/ directory (single-repo mode)"
    fi
fi

# ============================================================
# Check 6: Brain directory structure is intact
# ============================================================
echo "📋 Check 6: Brain directory structure"
BRAIN_DIRS=("global" "projects" "sessions")
MISSING_DIRS=()
for dir in "${BRAIN_DIRS[@]}"; do
    FULL_PATH="$BRAIN_DIR/$dir"
    if [ ! -d "$FULL_PATH" ]; then
        MISSING_DIRS+=("$dir")
    fi
done

if [ ${#MISSING_DIRS[@]} -eq 0 ]; then
    check_pass "Brain three-layer structure intact (global/projects/sessions)"
else
    check_fail "Missing brain directories: ${MISSING_DIRS[*]}"
fi

# ============================================================
# Check 7: .brain-config.yaml exists
# ============================================================
echo "📋 Check 7: .brain-config.yaml"
BRAIN_CONFIG="$HARNESS_ROOT/config/.brain-config.yaml"
if [ -f "$BRAIN_CONFIG" ]; then
    check_pass ".brain-config.yaml exists"
else
    check_warn ".brain-config.yaml not found in harness repo"
fi

# ============================================================
# Check 8: Global memory files exist
# ============================================================
echo "📋 Check 8: Global memory files"
GLOBAL_FILES=("global/preferences.md" "global/gotchas.md")
MISSING_FILES=()
for file in "${GLOBAL_FILES[@]}"; do
    if [ ! -f "$BRAIN_DIR/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    check_pass "Global memory files present (preferences.md, gotchas.md)"
else
    check_warn "Missing global memory files: ${MISSING_FILES[*]}"
fi

# ============================================================
# Check 9: pre-commit installed (optional)
# ============================================================
echo "📋 Check 9: pre-commit hooks (optional)"
if [ -d "$TARGET_DIR/.git" ]; then
    if [ -f "$TARGET_DIR/.git/hooks/pre-commit" ]; then
        check_pass "pre-commit hook is installed"
    else
        check_warn "pre-commit hook not installed. Run 'pre-commit install' for physical guardrails."
    fi
else
    check_warn "Not a git repository. pre-commit check skipped."
fi

# ============================================================
# Check 10: MEMORY.md capacity (optional)
# ============================================================
echo "📋 Check 10: MEMORY.md capacity"
MEMORY_FILE="$BRAIN_DIR/MEMORY.md"
MEMORY_MAX_LINES=200

# Try to read config
if [ -f "$HARNESS_ROOT/config/.brain-config.yaml" ]; then
    config_max=$(grep 'max_memory_file_lines:' "$HARNESS_ROOT/config/.brain-config.yaml" 2>/dev/null | awk '{print $2}' | tr -d ' ')
    [ -n "$config_max" ] && MEMORY_MAX_LINES="$config_max"
fi

if [ -f "$MEMORY_FILE" ]; then
    MEMORY_LINES=$(wc -l < "$MEMORY_FILE" | tr -d ' ')
    if [ "$MEMORY_LINES" -gt "$MEMORY_MAX_LINES" ]; then
        check_warn "MEMORY.md is $MEMORY_LINES lines (limit: $MEMORY_MAX_LINES). Consider running brain-gc.sh"
    else
        check_pass "MEMORY.md is $MEMORY_LINES lines (limit: $MEMORY_MAX_LINES)"
    fi
else
    check_pass "MEMORY.md not found in harness repo (OK if project-specific)"
fi

# ============================================================
# Check 11: Brain auto-write rules present in AGENTS.md
# ============================================================
echo "📋 Check 11: Brain auto-write rules"
EXTENDED_RULES="$HARNESS_ROOT/rules/extended.md"
if { [ -f "$AGENTS_MD" ] && grep -q "Brain Auto-Write Protocol" "$AGENTS_MD" 2>/dev/null; } || { [ -f "$EXTENDED_RULES" ] && grep -q "Brain Auto-Write Protocol" "$EXTENDED_RULES" 2>/dev/null; }; then
    check_pass "Brain auto-write rules are reachable from project Harness"
else
    check_warn "Brain auto-write rules not found. AI won't auto-push memories."
fi

# ============================================================
# Check 12: Brain ownership (fork detection)
# ============================================================
echo "📋 Check 12: Brain ownership"
BRAIN_OWNER_FILE="$BRAIN_DIR/.brain-owner"
if [ -f "$BRAIN_OWNER_FILE" ]; then
    RECORDED_OWNER=$(grep '^owner:' "$BRAIN_OWNER_FILE" 2>/dev/null | awk '{print $2}' | tr -d ' ')
    CURRENT_REMOTE=$(git -C "$HARNESS_ROOT" remote get-url origin 2>/dev/null || echo "")
    CURRENT_OWNER=""
    if echo "$CURRENT_REMOTE" | grep -qE '^https?://'; then
        CURRENT_OWNER=$(echo "$CURRENT_REMOTE" | sed -E 's|https?://[^/]+/([^/]+)/.*|\1|')
    elif echo "$CURRENT_REMOTE" | grep -qE '^git@'; then
        CURRENT_OWNER=$(echo "$CURRENT_REMOTE" | sed -E 's|git@[^:]+:([^/]+)/.*|\1|')
    fi

    if [ -z "$CURRENT_OWNER" ]; then
        check_warn "Could not detect Git remote owner. Ownership check skipped."
    elif [ "$CURRENT_OWNER" = "$RECORDED_OWNER" ]; then
        check_pass "Brain owner verified: $CURRENT_OWNER"
    else
        check_fail "Brain owner mismatch! Recorded: $RECORDED_OWNER, Current: $CURRENT_OWNER. Run '.harness/setup.sh --full --fresh' to auto-reset."
    fi
else
    check_warn ".brain-owner file not found. Run '.harness/setup.sh --full' to initialize ownership."
fi

# ============================================================
# Check 13: Single-source rule generation (dist/ sync)
# ============================================================
echo "📋 Check 13: Single-source rule generation"
GENERATE="$HARNESS_ROOT/generate.sh"
if [ -x "$GENERATE" ]; then
    if "$GENERATE" --check >/dev/null 2>&1; then
        check_pass "dist/ rule files are up to date with rules/core.md + extended.md"
    else
        check_warn "dist/ is out of date. Run '.harness/generate.sh' to regenerate."
    fi
    # AGENTS.md is the primary cross-tool output — verify it's mounted
    if [ -L "$TARGET_DIR/AGENTS.md" ] || [ -f "$TARGET_DIR/AGENTS.md" ]; then
        check_pass "AGENTS.md is mounted in project root"
    else
        check_warn "AGENTS.md not mounted. Run setup.sh to symlink generated rule files."
    fi
else
    check_warn "generate.sh not found. Single-source generation unavailable."
fi

# ============================================================
# Check 14: Harness Self-Test prompt present in the default entry
# ============================================================
echo "📋 Check 14: Harness Self-Test prompt"
SELFTEST_MISSING=()
for dist_target in "AGENTS.md"; do
    DIST_FILE="$HARNESS_ROOT/dist/$dist_target"
    if [ ! -f "$DIST_FILE" ] || ! grep -q "Harness Self-Test" "$DIST_FILE" 2>/dev/null; then
        SELFTEST_MISSING+=("$dist_target")
    fi
done
if [ ${#SELFTEST_MISSING[@]} -eq 0 ]; then
    check_pass "Harness Self-Test prompt is present in generated rule files"
else
    check_warn "Harness Self-Test prompt missing from generated rule files: ${SELFTEST_MISSING[*]}. Run '.harness/generate.sh'."
    echo "         Ask the current Agent to answer: '请按 Harness Self-Test 用 5 句话证明你理解当前任务约束。'"
fi

# ============================================================
# Check 15: Constitution ↔ Harness staleness
# ============================================================
echo "📋 Check 15: Constitution ↔ Harness staleness"
CONSTITUTION_FILE="$BRAIN_DIR/constitution.md"
if [ -f "$CONSTITUTION_FILE" ]; then
    STALE=false
    CAPSULE_PRESENT=true
    CAPSULE_SOURCES=(
        "$BRAIN_DIR/global/agent-capsule.md"
        "$BRAIN_DIR/constitution.md"
        "$BRAIN_DIR/global/persona.md"
        "$BRAIN_DIR/global/preferences.md"
        "$BRAIN_DIR/global/collaboration-style.md"
        "$BRAIN_DIR/global/gotchas.md"
    )
    for dist_target in "AGENTS.md"; do
        DIST_FILE="$HARNESS_ROOT/dist/$dist_target"
        if [ ! -f "$DIST_FILE" ]; then
            CAPSULE_PRESENT=false
            continue
        fi
        if ! grep -q "Mick Agent Capsule" "$DIST_FILE" 2>/dev/null; then
            CAPSULE_PRESENT=false
        fi
        for src in "${CAPSULE_SOURCES[@]}"; do
            if [ -f "$src" ] && [ "$src" -nt "$DIST_FILE" ]; then
                STALE=true
            fi
        done
    done

    if [ "$CAPSULE_PRESENT" = false ]; then
        check_warn "Personal Agent Capsule sources exist, but generated rule files do not contain the capsule. Run '.harness/generate.sh'."
    elif [ "$STALE" = true ]; then
        check_warn "Personal Agent Capsule sources are newer than dist/ rule files. Run '.harness/generate.sh' to sync."
    else
        check_pass "Personal Agent Capsule is injected and in sync"
    fi
else
    check_pass "No Personal Agent Capsule source found (OK for non-Mick users)"
fi

# ============================================================
# Check 16: Harness Guard available
# ============================================================
echo "📋 Check 16: Harness Guard"
GUARD="$HARNESS_ROOT/scripts/harness-guard.sh"
if [ -x "$GUARD" ]; then
    check_pass "harness-guard.sh is available and executable"
else
    check_warn "harness-guard.sh is missing or not executable. Run 'chmod +x .harness/scripts/harness-guard.sh'."
fi

# ============================================================
# Summary
# ============================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL=$((PASS + WARN + FAIL))
echo -e "  ${GREEN}✅ Passed: $PASS${NC}  ${YELLOW}⚠️  Warnings: $WARN${NC}  ${RED}❌ Failed: $FAIL${NC}  (Total: $TOTAL)"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo -e "  ${RED}Some critical checks failed. Please fix the issues above.${NC}"
    exit 1
else
    if [ "$WARN" -gt 0 ]; then
        echo ""
        echo -e "  ${YELLOW}All critical checks passed, but there are warnings to review.${NC}"
    else
        echo ""
        echo -e "  ${GREEN}All checks passed! Harness + Brain is fully operational. 🎉${NC}"
    fi
    exit 0
fi
