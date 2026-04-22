#!/bin/bash
set -uo pipefail

# ============================================================
# brain-check.sh — Verify harness + brain mount integrity
# Usage: /path/to/mick_harness_rules/brain-check.sh [target_project_dir]
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
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- Source shared brain resolver ---
source "$HARNESS_ROOT/brain-resolve.sh"
resolve_brain_dir "$HARNESS_ROOT"

# --- Resolve target project directory ---
TARGET_DIR="${1:-$(pwd)}"
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}❌ Target directory does not exist: $TARGET_DIR${NC}"
    exit 1
fi
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

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
    LINK_TARGET="$(readlink "$HARNESS_LINK")"
    if [ -d "$LINK_TARGET" ]; then
        check_pass ".harness/ → $LINK_TARGET (valid)"
    else
        check_fail ".harness/ symlink exists but target is broken: $LINK_TARGET"
    fi
elif [ -d "$HARNESS_LINK" ]; then
    check_warn ".harness/ exists as a real directory (not a symlink). Consider using symlink for sync."
else
    check_fail ".harness/ does not exist. Run 'brain-init.sh' first."
fi

# ============================================================
# Check 2: .cursorrules exists and is non-empty
# ============================================================
echo "📋 Check 2: .cursorrules"
CURSORRULES="$TARGET_DIR/.cursorrules"
if [ -L "$CURSORRULES" ] || [ -f "$CURSORRULES" ]; then
    if [ -s "$CURSORRULES" ]; then
        LINE_COUNT=$(wc -l < "$CURSORRULES" | tr -d ' ')
        check_pass ".cursorrules exists and is non-empty ($LINE_COUNT lines)"
    else
        check_fail ".cursorrules exists but is empty!"
    fi
else
    check_fail ".cursorrules does not exist. Run 'brain-init.sh' first."
fi

# ============================================================
# Check 3: .prompts/ symlink exists and is valid
# ============================================================
echo "📋 Check 3: .prompts/ symlink"
PROMPTS_LINK="$TARGET_DIR/.prompts"
if [ -L "$PROMPTS_LINK" ]; then
    PROMPTS_TARGET="$(readlink "$PROMPTS_LINK")"
    if [ -d "$PROMPTS_TARGET" ]; then
        check_pass ".prompts/ → $PROMPTS_TARGET (valid symlink)"
    else
        check_fail ".prompts/ symlink exists but target is broken: $PROMPTS_TARGET"
    fi
elif [ -d "$PROMPTS_LINK" ]; then
    check_warn ".prompts/ exists as a real directory (not a symlink). Agent prompts may leak into project Git."
else
    check_fail ".prompts/ does not exist. Run 'brain-init.sh' first."
fi

# ============================================================
# Check 4: .gitignore contains isolation entries
# ============================================================
echo "📋 Check 4: .gitignore isolation"
GITIGNORE="$TARGET_DIR/.gitignore"
if [ -f "$GITIGNORE" ]; then
    MISSING_ENTRIES=()
    for entry in ".harness/" ".harness" ".cursorrules" ".prompts/" ".prompts"; do
        if ! grep -qxF "$entry" "$GITIGNORE" 2>/dev/null; then
            MISSING_ENTRIES+=("$entry")
        fi
    done
    if [ ${#MISSING_ENTRIES[@]} -eq 0 ]; then
        check_pass ".gitignore contains all isolation entries"
    else
        check_warn ".gitignore missing entries: ${MISSING_ENTRIES[*]}"
        echo -e "         ${YELLOW}Auto-fixing: adding missing entries...${NC}"
        for entry in "${MISSING_ENTRIES[@]}"; do
            echo "$entry" >> "$GITIGNORE"
        done
        check_pass "Auto-fixed: added ${#MISSING_ENTRIES[@]} entries to .gitignore"
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
            check_warn "brain/ is a real directory, not a symlink. Run brain-init.sh to fix."
        fi
        # Check remote sync status
        if git -C "$BRAIN_REPO_LOCAL" remote get-url origin &>/dev/null; then
            check_pass "Brain repo has remote: $(git -C "$BRAIN_REPO_LOCAL" remote get-url origin 2>/dev/null)"
        else
            check_warn "Brain repo has no remote configured."
        fi
    else
        check_fail "Brain repo configured but not cloned at: $BRAIN_REPO_LOCAL"
        echo -e "         ${YELLOW}Run brain-init.sh to clone it.${NC}"
    fi
else
    if [ -n "$BRAIN_REPO_REMOTE" ]; then
        check_warn "Brain repo configured ($BRAIN_REPO_REMOTE) but not cloned. Run brain-init.sh."
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
BRAIN_CONFIG="$HARNESS_ROOT/.brain-config.yaml"
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
if [ -f "$HARNESS_ROOT/.brain-config.yaml" ]; then
    config_max=$(grep 'max_memory_file_lines:' "$HARNESS_ROOT/.brain-config.yaml" 2>/dev/null | awk '{print $2}' | tr -d ' ')
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
# Check 11: Brain auto-write rules present in .cursorrules
# ============================================================
echo "📋 Check 11: Brain auto-write rules"
if [ -f "$CURSORRULES" ] && grep -q "Brain Auto-Write Protocol" "$CURSORRULES" 2>/dev/null; then
    check_pass "Brain auto-write rules are present in .cursorrules"
else
    check_warn "Brain auto-write rules not found in .cursorrules. AI won't auto-push memories."
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
        check_fail "Brain owner mismatch! Recorded: $RECORDED_OWNER, Current: $CURRENT_OWNER. Run brain-init.sh to auto-reset."
    fi
else
    check_warn ".brain-owner file not found. Run brain-init.sh to initialize ownership."
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
