#!/bin/bash
set -euo pipefail

# ============================================================
# harness-guard.sh — Unified Harness Gate
#
# Runs the checks that decide whether an Agent-produced result is
# acceptable for handoff/commit:
#   1. generated rule files are in sync with rules/*.md
#   2. harness shell scripts are syntactically valid
#   3. plan compliance audit passes, or warns in soft mode
#
# Usage:
#   .harness/harness-guard.sh [--since <commit>] [--strict|--soft]
# ============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

pass() { echo -e "  ${GREEN}PASS${NC}: $1"; ((PASS_COUNT++)) || true; }
warn() { echo -e "  ${YELLOW}WARN${NC}: $1"; ((WARN_COUNT++)) || true; }
fail() { echo -e "  ${RED}FAIL${NC}: $1"; ((FAIL_COUNT++)) || true; }

SINCE="HEAD~1"
MODE_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --since) shift; SINCE="${1:-HEAD~1}"; shift ;;
        --strict) MODE_OVERRIDE="strong"; shift ;;
        --soft) MODE_OVERRIDE="soft"; shift ;;
        -h|--help)
            echo "Usage: .harness/harness-guard.sh [--since <commit>] [--strict|--soft]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$HARNESS_ROOT/.." && pwd)"
CONFIG="$PROJECT_DIR/.harness-config.yaml"
PLAN="$PROJECT_DIR/plan.md"

read_strictness() {
    if [ -n "$MODE_OVERRIDE" ]; then
        echo "$MODE_OVERRIDE"
        return 0
    fi
    if [ ! -f "$CONFIG" ]; then
        echo "soft"
        return 0
    fi
    awk '
        /^[[:space:]]*strictness:/ { in_block=1; next }
        in_block && /^[^[:space:]]/ { in_block=0 }
        in_block && /^[[:space:]]*mode:/ {
            mode=$2
            gsub(/["'\'' ]/, "", mode)
            print mode
            exit
        }
    ' "$CONFIG"
}

STRICTNESS="$(read_strictness)"
[ -z "$STRICTNESS" ] && STRICTNESS="soft"

echo ""
echo -e "${BOLD}Harness Guard${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Project   : $PROJECT_DIR"
echo "  Strictness: $STRICTNESS"
echo "  Diff base : $SINCE"
echo ""

echo -e "${CYAN}Check 1: generated rules${NC}"
if [ -x "$HARNESS_ROOT/generate.sh" ]; then
    if "$HARNESS_ROOT/generate.sh" --check >/tmp/harness-guard-generate.$$ 2>&1; then
        pass "dist/ is in sync with rules/*.md"
    else
        fail "dist/ is out of sync; run .harness/generate.sh"
        sed 's/^/    /' /tmp/harness-guard-generate.$$
    fi
    rm -f /tmp/harness-guard-generate.$$
else
    fail "generate.sh is missing or not executable"
fi

echo -e "${CYAN}Check 2: shell syntax${NC}"
SCRIPT_FAILS=0
while IFS= read -r script; do
    [ -z "$script" ] && continue
    if ! bash -n "$script"; then
        ((SCRIPT_FAILS++)) || true
        fail "shell syntax failed: ${script#$HARNESS_ROOT/}"
    fi
done < <(find "$HARNESS_ROOT" -maxdepth 1 -type f -name '*.sh' | sort)

if [ "$SCRIPT_FAILS" -eq 0 ]; then
    pass "all root harness shell scripts pass bash -n"
fi

echo -e "${CYAN}Check 3: plan compliance${NC}"
if [ ! -f "$PLAN" ]; then
    pass "no plan.md found; plan audit skipped"
elif [ -x "$HARNESS_ROOT/harness-audit.sh" ]; then
    if "$HARNESS_ROOT/harness-audit.sh" --since "$SINCE"; then
        pass "harness-audit passed"
    else
        if [ "$STRICTNESS" = "strong" ]; then
            fail "harness-audit failed under strictness=strong"
        else
            warn "harness-audit failed but strictness=$STRICTNESS; treat as warning"
        fi
    fi
else
    fail "harness-audit.sh is missing or not executable"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
TOTAL=$((PASS_COUNT + WARN_COUNT + FAIL_COUNT))
echo -e "Summary: ${GREEN}$PASS_COUNT PASS${NC}, ${YELLOW}$WARN_COUNT WARN${NC}, ${RED}$FAIL_COUNT FAIL${NC} ($TOTAL checks)"
echo ""

[ "$FAIL_COUNT" -gt 0 ] && exit 1
exit 0
