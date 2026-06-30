#!/bin/bash
set -euo pipefail

# ============================================================
# harness-audit.sh — Plan Compliance Scanner
#
# Scans plan.md and git diff to detect Executor violations:
#   1. Step-file alignment (files changed but not in plan)
#   2. Self-check coverage (completed steps vs log entries)
#   3. Verification evidence (verify: line present and meaningful)
#      - Flags completed steps whose verify line admits no verification or a failed check
#   4. Preflight / Interaction QA hints for risky plans
#   5. Step order (timestamps monotonically increasing)
#   6. Scope creep (files in diff not mentioned in any plan step)
#   7. Plan integrity (required sections exist)
#
# Usage:
#   .harness/harness-audit.sh [--since <commit>] [--log]
#
# Run from your project root (parent of .harness/).
# ============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

PASS_COUNT=0; WARN_COUNT=0; FAIL_COUNT=0
# Structured findings for the evolution signal: each entry "LEVEL\tTAG\tdetail"
LOG_ENTRIES=()

pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; ((PASS_COUNT++)) || true; }
# warn_check / fail_check take a machine TAG first, then the human message.
# The TAG is what harness-evolve.sh aggregates across projects.
warn_check() { local tag="$1"; shift; echo -e "  ${YELLOW}⚠️  WARN${NC}: $1"; ((WARN_COUNT++)) || true; LOG_ENTRIES+=("WARN	$tag	$1"); }
fail_check() { local tag="$1"; shift; echo -e "  ${RED}❌ FAIL${NC}: $1"; ((FAIL_COUNT++)) || true; LOG_ENTRIES+=("FAIL	$tag	$1"); }

# --- Parse arguments ---
SINCE="HEAD~1"
LOG_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --since) shift; SINCE="${1:-HEAD~1}"; shift ;;
        --log) LOG_MODE=true; shift ;;
        -h|--help)
            echo "Usage: .harness/harness-audit.sh [--since <commit>] [--log]"
            echo ""
            echo "Options:"
            echo "  --since <commit>  Git diff base (default: HEAD~1)"
            echo "  --log             Append structured findings to the evolution signal"
            echo "                    (Brain: global/evolution/audit-trail.md, or per-project fallback)"
            echo "  -h, --help        Show this help"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Resolve paths ---
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$HARNESS_ROOT/.." && pwd)"
PLAN="$PROJECT_DIR/plan.md"

# --- Pre-checks ---
if [ ! -f "$PLAN" ]; then
    echo -e "${YELLOW}No plan.md found. Nothing to audit.${NC}"
    exit 0
fi

# --- Count steps ---
TOTAL_STEPS=$(grep -cE '^\- \[[ x]\] [0-9]+\.' "$PLAN" 2>/dev/null || true)
COMPLETED_STEPS=$(grep -cE '^\- \[x\] [0-9]+\.' "$PLAN" 2>/dev/null || true)
TOTAL_STEPS=${TOTAL_STEPS:-0}
COMPLETED_STEPS=${COMPLETED_STEPS:-0}

# --- Get git diff files ---
DIFF_FILES=""
if git -C "$PROJECT_DIR" rev-parse --verify "$SINCE" >/dev/null 2>&1; then
    DIFF_FILES=$(git -C "$PROJECT_DIR" diff --name-only "$SINCE"..HEAD 2>/dev/null || echo "")
fi

echo ""
echo -e "${BOLD}🔍 Harness Audit — Plan Compliance Report${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Project  : $PROJECT_DIR"
echo "  Plan     : plan.md ($COMPLETED_STEPS/$TOTAL_STEPS steps completed)"
echo "  Diff base: $SINCE"
echo ""

# ============================================================
# Check 1: Plan integrity — required sections
# ============================================================
echo -e "${CYAN}📋 Check 1: Plan integrity${NC}"
MISSING_SECTIONS=""
for section in "## 目标" "## 步骤"; do
    if ! grep -qF "$section" "$PLAN"; then
        MISSING_SECTIONS="$MISSING_SECTIONS $section"
    fi
done
if [ -z "$MISSING_SECTIONS" ]; then
    pass "Required sections (## 目标, ## 步骤) present"
else
    fail_check "plan-integrity" "Missing required sections:$MISSING_SECTIONS"
fi

# ============================================================
# Check 2: Self-check coverage
# ============================================================
echo -e "${CYAN}📋 Check 2: Self-check coverage${NC}"
SELFCHECK_ENTRIES=$(grep -cE '^### Step [0-9]+' "$PLAN" 2>/dev/null || true)
SELFCHECK_ENTRIES=${SELFCHECK_ENTRIES:-0}

if [ "$COMPLETED_STEPS" -eq 0 ]; then
    pass "No completed steps yet — nothing to check"
elif [ "$SELFCHECK_ENTRIES" -ge "$COMPLETED_STEPS" ]; then
    pass "All $COMPLETED_STEPS completed steps have self-check entries"
else
    MISSING=$((COMPLETED_STEPS - SELFCHECK_ENTRIES))
    fail_check "missing-selfcheck" "$COMPLETED_STEPS steps completed but only $SELFCHECK_ENTRIES self-check entries (missing $MISSING)"
fi

# ============================================================
# Check 3: Verification evidence
# ============================================================
echo -e "${CYAN}📋 Check 3: Verification evidence${NC}"
if [ "$SELFCHECK_ENTRIES" -eq 0 ]; then
    pass "No self-check entries to verify"
else
    NO_VERIFY=0
    VAGUE_VERIFY=0
    UNVERIFIED_VERIFY=0
    FAILED_VERIFY=0
    IN_SELFCHECK=false
    CURRENT_STEP=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^###\ Step\ ([0-9]+) ]]; then
            if [ -n "$CURRENT_STEP" ] && [ "$HAS_VERIFY" = false ]; then
                ((NO_VERIFY++))
            fi
            CURRENT_STEP="${BASH_REMATCH[1]}"
            HAS_VERIFY=false
        elif [[ "$line" =~ ^-\ verify: ]]; then
            HAS_VERIFY=true
            verify_content="${line#*verify: }"
            verify_lower=$(echo "$verify_content" | tr '[:upper:]' '[:lower:]')
            if [[ "$verify_lower" =~ ^(完成|done|ok|通过)$ ]]; then
                ((VAGUE_VERIFY++))
            fi
            if [[ "$verify_lower" =~ (未验证|待验证|无法验证|未运行|没跑|未执行|未测试|not[[:space:]]+run|not[[:space:]]+tested|skipped|skip|n/a) ]]; then
                ((UNVERIFIED_VERIFY++))
            fi
            if [[ "$verify_lower" =~ (failed|failure|失败|未通过|not[[:space:]]+pass|exit[[:space:]]+code[[:space:]]+[1-9]) ]]; then
                ((FAILED_VERIFY++))
            fi
        fi
    done < <(sed -n '/^## 自检日志/,/^## [^自]/p' "$PLAN")

    if [ -n "$CURRENT_STEP" ] && [ "$HAS_VERIFY" = false ]; then
        ((NO_VERIFY++))
    fi

    if [ "$NO_VERIFY" -eq 0 ] && [ "$VAGUE_VERIFY" -eq 0 ] && [ "$UNVERIFIED_VERIFY" -eq 0 ] && [ "$FAILED_VERIFY" -eq 0 ]; then
        pass "All self-check entries have meaningful verify evidence"
    else
        [ "$NO_VERIFY" -gt 0 ] && warn_check "verify-missing" "$NO_VERIFY entries missing verify: line"
        [ "$VAGUE_VERIFY" -gt 0 ] && warn_check "verify-vague" "$VAGUE_VERIFY entries have vague verify (just '完成'/'done')"
        [ "$UNVERIFIED_VERIFY" -gt 0 ] && fail_check "verify-unverified" "$UNVERIFIED_VERIFY completed-step verify lines admit no real verification"
        [ "$FAILED_VERIFY" -gt 0 ] && fail_check "verify-failed" "$FAILED_VERIFY completed-step verify lines report failed verification"
    fi
fi

# ============================================================
# Check 4: Preflight / Interaction QA hints
# ============================================================
echo -e "${CYAN}📋 Check 4: Preflight / Interaction QA hints${NC}"
EXTERNAL_PATTERN='(server|remote|api|cli|sudo|permission|token|config|migration|database|db|network|proxy|browser|service|daemon|plist|launchd|ci|deploy|version|版本|权限|配置|远程|服务|网络|代理|浏览器|数据库|迁移|部署)'
INTERACTION_PATTERN='(ui|interaction|button|toggle|switch|menu|modal|form|toast|state|status|loading|empty|error|click|hover|交互|按钮|菜单|开关|切换|弹窗|表单|状态|加载|空态|错误态)'

if grep -Eiq "$EXTERNAL_PATTERN" "$PLAN"; then
    if grep -Eiq '(preflight|前置核对|前置检查|版本兼容|权限核对|dry-run|dry run)' "$PLAN"; then
        pass "External-system plan includes preflight-style checks"
    else
        warn_check "preflight-missing" "Plan appears to touch external systems/config/permissions but lacks an explicit Preflight section or check"
    fi
else
    pass "No obvious external-system risk keywords in plan"
fi

if grep -Eiq "$INTERACTION_PATTERN" "$PLAN"; then
    if grep -Eiq '(interaction qa|交互状态|真实状态源|用户路径|状态源|screenshot|截图|dom|e2e)' "$PLAN"; then
        pass "Interaction plan includes state-source or user-path QA"
    else
        warn_check "interaction-qa-missing" "Plan appears to touch UI/interaction/state but lacks explicit Interaction QA evidence"
    fi
else
    pass "No obvious UI/interaction risk keywords in plan"
fi

# ============================================================
# Check 5: Step order (timestamp monotonicity)
# ============================================================
echo -e "${CYAN}📋 Check 5: Step execution order${NC}"
TIMESTAMPS=()
while IFS= read -r line; do
    if [[ "$line" =~ ^###\ Step\ [0-9]+\ —\ ([0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}) ]]; then
        TIMESTAMPS+=("${BASH_REMATCH[1]}")
    fi
done < "$PLAN"

if [ "${#TIMESTAMPS[@]}" -le 1 ]; then
    pass "Not enough timestamps to check order"
else
    ORDER_OK=true
    for ((i=1; i<${#TIMESTAMPS[@]}; i++)); do
        prev="${TIMESTAMPS[$((i-1))]}"
        curr="${TIMESTAMPS[$i]}"
        if [[ "$curr" < "$prev" ]]; then
            ORDER_OK=false
            break
        fi
    done
    if [ "$ORDER_OK" = true ]; then
        pass "Step timestamps are in chronological order"
    else
        warn_check "step-order" "Step timestamps are NOT in order — possible out-of-sequence execution"
    fi
fi

# ============================================================
# Check 6: Scope creep — files in diff not in any plan step
# ============================================================
echo -e "${CYAN}📋 Check 6: Scope creep detection${NC}"
if [ -z "$DIFF_FILES" ]; then
    pass "No git diff to check (or invalid --since ref)"
else
    # Extract file paths mentioned in plan steps (backtick-quoted)
    PLAN_FILES=$(grep -E '^\- \[[ x]\] [0-9]+\.' "$PLAN" | grep -oE '`[^`]+`' | tr -d '`' | sort -u || true)
    # Also extract from self-check files: lines
    SELFCHECK_FILES=$(grep -E '^- files:' "$PLAN" | sed 's/^- files: //' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sort -u || true)
    ALL_PLAN_FILES=$(echo -e "$PLAN_FILES\n$SELFCHECK_FILES" | sort -u | grep -v '^$' || true)

    CREEP_FILES=""
    while IFS= read -r diff_file; do
        [ -z "$diff_file" ] && continue
        # Skip plan.md itself and harness files
        [[ "$diff_file" == "plan.md" ]] && continue
        [[ "$diff_file" == .harness/* ]] && continue

        FOUND=false
        while IFS= read -r plan_file; do
            [ -z "$plan_file" ] && continue
            if [[ "$diff_file" == *"$plan_file"* ]] || [[ "$plan_file" == *"$diff_file"* ]]; then
                FOUND=true
                break
            fi
        done <<< "$ALL_PLAN_FILES"

        if [ "$FOUND" = false ]; then
            CREEP_FILES="$CREEP_FILES\n    - $diff_file"
        fi
    done <<< "$DIFF_FILES"

    if [ -z "$CREEP_FILES" ]; then
        pass "All changed files are mentioned in plan steps"
    else
        warn_check "scope-creep" "Files changed but NOT in any plan step:$CREEP_FILES"
    fi
fi

# ============================================================
# Check 7: Step-file alignment (completed steps vs self-check files)
# ============================================================
echo -e "${CYAN}📋 Check 7: Step-file alignment${NC}"
if [ "$SELFCHECK_ENTRIES" -eq 0 ]; then
    pass "No self-check entries to cross-reference"
else
    NO_FILES=0
    while IFS= read -r line; do
        if [[ "$line" =~ ^###\ Step ]]; then
            HAS_FILES=false
        elif [[ "$line" =~ ^-\ files: ]]; then
            HAS_FILES=true
            files_content="${line#*files: }"
            if [ -z "$files_content" ] || [ "$files_content" = "(none)" ]; then
                ((NO_FILES++))
            fi
        fi
    done < <(sed -n '/^## 自检日志/,/^## [^自]/p' "$PLAN")

    if [ "$NO_FILES" -eq 0 ]; then
        pass "All self-check entries have files: lines"
    else
        warn_check "files-missing" "$NO_FILES self-check entries missing or empty files: line"
    fi
fi

# ============================================================
# Summary
# ============================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL=$((PASS_COUNT + WARN_COUNT + FAIL_COUNT))
echo -e "Summary: ${GREEN}$PASS_COUNT PASS${NC}, ${YELLOW}$WARN_COUNT WARN${NC}, ${RED}$FAIL_COUNT FAIL${NC} ($TOTAL checks)"
echo ""

# --- Optional: append structured findings to the evolution signal ---
# Signal goes to Brain (cross-project, git-synced) so harness-evolve.sh can
# aggregate patterns across all projects. Falls back to per-project if no Brain.
if [ "$LOG_MODE" = true ]; then
    PROJECT_NAME=$(basename "$PROJECT_DIR")
    PLAN_REF=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo "no-git")

    # Resolve Brain dir if available
    TRAIL_FILE=""
    if [ -f "$HARNESS_ROOT/brain-resolve.sh" ]; then
        # shellcheck disable=SC1091
        source "$HARNESS_ROOT/brain-resolve.sh"
        if resolve_brain_dir "$HARNESS_ROOT" 2>/dev/null && [ -n "${BRAIN_DIR:-}" ] && [ -d "$BRAIN_DIR" ]; then
            mkdir -p "$BRAIN_DIR/global/evolution"
            TRAIL_FILE="$BRAIN_DIR/global/evolution/audit-trail.md"
        fi
    fi
    # Fallback: per-project log (no cross-project evolution, but still recorded)
    [ -z "$TRAIL_FILE" ] && TRAIL_FILE="$HARNESS_ROOT/audit-log.md"

    {
        echo ""
        echo "## $(date '+%Y-%m-%d %H:%M') · $PROJECT_NAME · plan $PLAN_REF"
        echo "- summary: $PASS_COUNT PASS, $WARN_COUNT WARN, $FAIL_COUNT FAIL ($COMPLETED_STEPS/$TOTAL_STEPS steps)"
        for entry in "${LOG_ENTRIES[@]}"; do
            level="${entry%%	*}"; rest="${entry#*	}"
            tag="${rest%%	*}"; detail="${rest#*	}"
            echo "- $level: $tag ($detail)"
        done
    } >> "$TRAIL_FILE"

    echo -e "${CYAN}Findings appended to: ${TRAIL_FILE/#$HOME/~}${NC}"
    echo ""
fi

# Exit with failure if any FAIL
[ "$FAIL_COUNT" -gt 0 ] && exit 1
exit 0
