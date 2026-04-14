#!/bin/bash
set -uo pipefail

# ============================================================
# brain-compound.sh — Smart distillation of memories
#
# Distills knowledge upward through the three-layer memory model:
#   Session → Project → Global
#
# Smart trigger conditions:
#   - Session → Project: when session entries exceed threshold
#   - Project → Global:  when project entries have new additions this week
#
# Usage:
#   brain-compound.sh                    # Auto-detect what needs distilling
#   brain-compound.sh --daily            # Force Session → Project distillation
#   brain-compound.sh --weekly           # Force Project → Global distillation
#   brain-compound.sh --all              # Force both directions
#   brain-compound.sh --dry-run          # Preview without writing
# ============================================================

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()    { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail()  { echo -e "${RED}❌ $1${NC}"; }
header(){ echo -e "${BOLD}${MAGENTA}$1${NC}"; }

# --- Resolve harness repo root ---
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$HARNESS_ROOT/brain"

# --- Configuration defaults ---
SESSION_ENTRY_THRESHOLD=5       # Min entries in session to trigger daily compound
SESSION_AGE_THRESHOLD_DAYS=1    # Min age of session (days) before distilling
PROJECT_NEW_ENTRY_THRESHOLD=3   # Min new project entries to trigger weekly compound
SIMILARITY_THRESHOLD=3          # Min shared keywords to consider entries "similar"

# --- Parse arguments ---
MODE="auto"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --daily)
            MODE="daily"
            shift
            ;;
        --weekly)
            MODE="weekly"
            shift
            ;;
        --all)
            MODE="all"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: brain-compound.sh [OPTIONS]"
            echo ""
            echo "Smart distillation of memories through the three-layer model."
            echo ""
            echo "Options:"
            echo "  --daily      Force Session → Project distillation"
            echo "  --weekly     Force Project → Global distillation"
            echo "  --all        Force both daily and weekly distillation"
            echo "  --dry-run    Preview candidates without writing"
            echo "  -h, --help   Show this help message"
            echo ""
            echo "Auto mode (default) checks smart trigger conditions:"
            echo "  - Daily:  session has ≥ $SESSION_ENTRY_THRESHOLD entries"
            echo "  - Weekly: project has ≥ $PROJECT_NEW_ENTRY_THRESHOLD new entries this week"
            exit 0
            ;;
        -*)
            fail "Unknown option: $1"
            echo "Run 'brain-compound.sh --help' for usage."
            exit 1
            ;;
        *)
            shift
            ;;
    esac
done

# --- Validate brain directory ---
if [ ! -d "$BRAIN_DIR" ]; then
    fail "Brain directory not found at: $BRAIN_DIR"
    exit 1
fi

echo ""
header "🧪 Brain Compound — Smart Memory Distillation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Mode    : $MODE"
echo "  Dry run : $DRY_RUN"
echo ""

# ============================================================
# Utility: Count entries (lines starting with "- [") in a file
# ============================================================
count_entries() {
    local file="$1"
    if [ -f "$file" ]; then
        grep -c '^- \[' "$file" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# ============================================================
# Utility: Extract entry text (strip timestamp and source prefix)
# ============================================================
extract_entry_text() {
    local entry="$1"
    # Strip "- [YYYY-MM-DD] (source: xxx) " prefix
    echo "$entry" | sed 's/^- \[[0-9-]*\] *\(([^)]*) *\)\?//'
}

# ============================================================
# Utility: Extract keywords from text (words ≥ 3 chars, lowercased)
# ============================================================
extract_keywords() {
    local text="$1"
    echo "$text" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '\n' | awk 'length >= 3' | sort -u
}

# ============================================================
# Utility: Check if two entries are similar (share enough keywords)
# ============================================================
entries_are_similar() {
    local text1="$1"
    local text2="$2"

    local kw1
    local kw2
    kw1=$(extract_keywords "$text1")
    kw2=$(extract_keywords "$text2")

    # Count shared keywords
    local shared
    shared=$(comm -12 <(echo "$kw1") <(echo "$kw2") | wc -l | tr -d ' ')

    [ "$shared" -ge "$SIMILARITY_THRESHOLD" ]
}

# ============================================================
# Utility: Find similar entry in target file, return line number
# Returns empty string if no similar entry found
# ============================================================
find_similar_entry() {
    local new_text="$1"
    local target_file="$2"

    if [ ! -f "$target_file" ]; then
        echo ""
        return
    fi

    local line_num=0
    while IFS= read -r line; do
        ((line_num++))
        # Only compare entry lines
        if [[ "$line" == "- ["* ]]; then
            local existing_text
            existing_text=$(extract_entry_text "$line")
            if entries_are_similar "$new_text" "$existing_text"; then
                echo "$line_num"
                return
            fi
        fi
    done < "$target_file"

    echo ""
}

# ============================================================
# Utility: Append or merge entry into target file
# - If similar entry exists: append as sub-item (merge)
# - If no similar entry: append at end of file
# ============================================================
write_or_merge_entry() {
    local entry="$1"
    local target_file="$2"
    local entry_text
    entry_text=$(extract_entry_text "$entry")

    local similar_line
    similar_line=$(find_similar_entry "$entry_text" "$target_file")

    if [ -n "$similar_line" ]; then
        # Similar entry found — append as sub-item after that line
        local existing_entry
        existing_entry=$(sed -n "${similar_line}p" "$target_file")

        if [ "$DRY_RUN" = true ]; then
            echo -e "  ${YELLOW}[MERGE]${NC} Similar to line $similar_line: $(echo "$existing_entry" | head -c 80)..."
            echo -e "         Would append: $(echo "$entry" | head -c 80)..."
        else
            # Insert the new entry as an indented sub-item after the similar line
            local sub_entry="  - (merged) $entry_text"
            sed -i '' "${similar_line}a\\
${sub_entry}
" "$target_file"
            echo -e "  ${GREEN}[MERGED]${NC} Appended under existing entry at line $similar_line"
        fi
    else
        # No similar entry — append at end
        if [ "$DRY_RUN" = true ]; then
            echo -e "  ${CYAN}[APPEND]${NC} $(echo "$entry" | head -c 100)..."
        else
            echo "$entry" >> "$target_file"
            echo -e "  ${GREEN}[ADDED]${NC} $(echo "$entry" | head -c 100)..."
        fi
    fi
}

# ============================================================
# DAILY COMPOUND: Session → Project
#
# Logic:
# 1. Scan all session files from the past N days
# 2. For each entry, determine if it's project-specific or general
# 3. Project-specific entries → project/<slug>/learnings.md
# 4. General entries → candidates for weekly compound
# ============================================================
DAILY_CANDIDATES=0
DAILY_WRITTEN=0

run_daily_compound() {
    header "📅 Daily Compound: Session → Project"
    echo ""

    local today
    today=$(date +%Y-%m-%d)

    # Find session directories
    local session_dirs=()
    while IFS= read -r dir; do
        [ -d "$dir" ] && session_dirs+=("$dir")
    done < <(find "$BRAIN_DIR/sessions" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

    if [ ${#session_dirs[@]} -eq 0 ]; then
        info "No session directories found. Nothing to distill."
        return
    fi

    # Collect all session entries
    local all_entries=()
    local all_sources=()

    for session_dir in "${session_dirs[@]}"; do
        local dirname
        dirname=$(basename "$session_dir")

        # Check age threshold (skip today's sessions unless forced)
        if [ "$MODE" != "daily" ] && [ "$MODE" != "all" ]; then
            if [ "$dirname" = "$today" ]; then
                info "Skipping today's session (still active): $dirname"
                continue
            fi
        fi

        # Check if already distilled (marker file)
        local marker="$session_dir/.distilled"
        if [ -f "$marker" ]; then
            info "Session $dirname already distilled. Skipping."
            continue
        fi

        # Read entries from all files in this session
        while IFS= read -r session_file; do
            local source_name
            source_name=$(basename "$session_file" .md)

            while IFS= read -r entry; do
                if [[ "$entry" == "- ["* ]]; then
                    all_entries+=("$entry")
                    all_sources+=("$source_name")
                    ((DAILY_CANDIDATES++))
                fi
            done < "$session_file"
        done < <(find "$session_dir" -name "*.md" -type f 2>/dev/null)
    done

    if [ "$DAILY_CANDIDATES" -eq 0 ]; then
        info "No undistilled session entries found."
        return
    fi

    info "Found $DAILY_CANDIDATES candidate entries from sessions."
    echo ""

    # Check smart trigger: enough entries?
    if [ "$MODE" = "auto" ] && [ "$DAILY_CANDIDATES" -lt "$SESSION_ENTRY_THRESHOLD" ]; then
        info "Below threshold ($DAILY_CANDIDATES < $SESSION_ENTRY_THRESHOLD). Skipping daily compound."
        info "Use --daily to force distillation."
        return
    fi

    # Determine target: check if any project directories exist
    local existing_projects=()
    while IFS= read -r pdir; do
        existing_projects+=("$(basename "$pdir")")
    done < <(find "$BRAIN_DIR/projects" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

    # Generate distillation report
    local report_file="$BRAIN_DIR/sessions/.compound-report-$(date +%Y%m%d-%H%M%S).md"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY RUN] Would generate distillation report:${NC}"
        echo ""
    fi

    # Build report content
    local report_content="# Compound Report — $(date '+%Y-%m-%d %H:%M')

## Session Entries to Distill

"

    for i in "${!all_entries[@]}"; do
        local entry="${all_entries[$i]}"
        local source="${all_sources[$i]}"
        local entry_text
        entry_text=$(extract_entry_text "$entry")

        report_content+="### Entry $((i+1)) (source: $source)
- **Original**: $entry
- **Extracted**: $entry_text
- **Suggested target**: "

        # Simple heuristic: if entry mentions a known project, route to project layer
        local routed=false
        for proj in "${existing_projects[@]}"; do
            if echo "$entry_text" | grep -qi "$proj"; then
                report_content+="project/$proj/learnings.md
"
                # Actually write it
                local target_file="$BRAIN_DIR/projects/$proj/learnings.md"
                echo -e "  Routing to ${MAGENTA}project/$proj${NC}:"
                write_or_merge_entry "$entry" "$target_file"
                ((DAILY_WRITTEN++))
                routed=true
                break
            fi
        done

        if [ "$routed" = false ]; then
            report_content+="(general — candidate for weekly global compound)
"
            echo -e "  ${CYAN}[GENERAL]${NC} $(echo "$entry_text" | head -c 80)... → kept for weekly compound"
        fi

        report_content+="
"
    done

    # Write report
    if [ "$DRY_RUN" = false ]; then
        echo "$report_content" > "$report_file"
        ok "Distillation report saved: ${report_file#$HARNESS_ROOT/}"

        # Mark sessions as distilled
        for session_dir in "${session_dirs[@]}"; do
            local dirname
            dirname=$(basename "$session_dir")
            if [ "$dirname" != "$today" ] || [ "$MODE" = "daily" ] || [ "$MODE" = "all" ]; then
                local marker="$session_dir/.distilled"
                if [ ! -f "$marker" ]; then
                    touch "$marker"
                fi
            fi
        done
    fi

    echo ""
    ok "Daily compound: $DAILY_CANDIDATES candidates → $DAILY_WRITTEN written to project layer."
}

# ============================================================
# WEEKLY COMPOUND: Project → Global
#
# Logic:
# 1. Scan all project learnings files for recent entries
# 2. Identify entries that are cross-project applicable
# 3. Route to global/preferences.md or global/gotchas.md
# 4. Detect similar existing entries and merge
# ============================================================
WEEKLY_CANDIDATES=0
WEEKLY_WRITTEN=0

run_weekly_compound() {
    header "📆 Weekly Compound: Project → Global"
    echo ""

    # Calculate date threshold (7 days ago)
    local since_date
    if date -v-1d +%Y-%m-%d &>/dev/null 2>&1; then
        since_date=$(date -v-7d +%Y-%m-%d)
    else
        since_date=$(date -d "7 days ago" +%Y-%m-%d)
    fi

    info "Scanning project entries since: $since_date"

    # Collect recent project entries
    local project_entries=()
    local project_sources=()

    while IFS= read -r project_dir; do
        local project_slug
        project_slug=$(basename "$project_dir")

        # Check for learnings file
        local learnings_file="$project_dir/learnings.md"
        if [ ! -f "$learnings_file" ]; then
            continue
        fi

        # Read entries and filter by date
        while IFS= read -r entry; do
            if [[ "$entry" == "- ["* ]]; then
                # Extract date from entry
                local entry_date
                entry_date=$(echo "$entry" | grep -o '\[[0-9-]*\]' | head -1 | tr -d '[]')

                if [ -n "$entry_date" ] && [[ "$entry_date" > "$since_date" || "$entry_date" = "$since_date" ]]; then
                    project_entries+=("$entry")
                    project_sources+=("$project_slug")
                    ((WEEKLY_CANDIDATES++))
                fi
            fi
        done < "$learnings_file"
    done < <(find "$BRAIN_DIR/projects" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

    # Also check undistilled general entries from session compound reports
    while IFS= read -r report_file; do
        if grep -q "(general — candidate for weekly global compound)" "$report_file" 2>/dev/null; then
            # Extract the original entries marked as general
            while IFS= read -r line; do
                if [[ "$line" == "- **Original**: - ["* ]]; then
                    local entry
                    entry=$(echo "$line" | sed 's/^- \*\*Original\*\*: //')
                    project_entries+=("$entry")
                    project_sources+=("session-general")
                    ((WEEKLY_CANDIDATES++))
                fi
            done < "$report_file"
        fi
    done < <(find "$BRAIN_DIR/sessions" -name ".compound-report-*.md" -type f 2>/dev/null | sort -r | head -7)

    if [ "$WEEKLY_CANDIDATES" -eq 0 ]; then
        info "No recent project entries found for global distillation."
        return
    fi

    info "Found $WEEKLY_CANDIDATES candidate entries."
    echo ""

    # Check smart trigger
    if [ "$MODE" = "auto" ] && [ "$WEEKLY_CANDIDATES" -lt "$PROJECT_NEW_ENTRY_THRESHOLD" ]; then
        info "Below threshold ($WEEKLY_CANDIDATES < $PROJECT_NEW_ENTRY_THRESHOLD). Skipping weekly compound."
        info "Use --weekly to force distillation."
        return
    fi

    # Categorize and route entries
    # Heuristic: keywords that suggest gotchas vs preferences
    local gotcha_keywords="bug|error|fail|crash|pitfall|gotcha|issue|broken|fix|workaround|warning|caution|avoid|never|don't|不要|注意|坑|问题|报错"
    local preference_keywords="prefer|style|convention|always|use|recommend|habit|偏好|习惯|风格|规范|建议"

    for i in "${!project_entries[@]}"; do
        local entry="${project_entries[$i]}"
        local source="${project_sources[$i]}"
        local entry_text
        entry_text=$(extract_entry_text "$entry")

        local target_category="preferences"  # default

        # Determine category by keyword matching
        if echo "$entry_text" | grep -qiE "$gotcha_keywords"; then
            target_category="gotchas"
        elif echo "$entry_text" | grep -qiE "$preference_keywords"; then
            target_category="preferences"
        fi

        local target_file="$BRAIN_DIR/global/${target_category}.md"

        echo -e "  From ${MAGENTA}$source${NC} → ${GREEN}global/$target_category${NC}:"
        write_or_merge_entry "$entry" "$target_file"
        ((WEEKLY_WRITTEN++))
    done

    echo ""
    ok "Weekly compound: $WEEKLY_CANDIDATES candidates → $WEEKLY_WRITTEN written to global layer."
}

# ============================================================
# AUTO MODE: Check conditions and decide what to run
# ============================================================
run_auto_mode() {
    info "Auto mode: checking smart trigger conditions..."
    echo ""

    # Check daily trigger: count undistilled session entries
    local session_entry_count=0
    while IFS= read -r session_dir; do
        if [ ! -f "$session_dir/.distilled" ]; then
            while IFS= read -r session_file; do
                local count
                count=$(count_entries "$session_file")
                session_entry_count=$((session_entry_count + count))
            done < <(find "$session_dir" -name "*.md" -type f 2>/dev/null)
        fi
    done < <(find "$BRAIN_DIR/sessions" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

    local should_daily=false
    local should_weekly=false

    if [ "$session_entry_count" -ge "$SESSION_ENTRY_THRESHOLD" ]; then
        info "Daily trigger: $session_entry_count undistilled session entries (threshold: $SESSION_ENTRY_THRESHOLD) → TRIGGERED"
        should_daily=true
    else
        info "Daily trigger: $session_entry_count undistilled session entries (threshold: $SESSION_ENTRY_THRESHOLD) → not triggered"
    fi

    # Check weekly trigger: count recent project entries
    local since_date
    if date -v-1d +%Y-%m-%d &>/dev/null 2>&1; then
        since_date=$(date -v-7d +%Y-%m-%d)
    else
        since_date=$(date -d "7 days ago" +%Y-%m-%d)
    fi

    local project_entry_count=0
    while IFS= read -r project_dir; do
        local learnings_file="$project_dir/learnings.md"
        if [ -f "$learnings_file" ]; then
            while IFS= read -r entry; do
                if [[ "$entry" == "- ["* ]]; then
                    local entry_date
                    entry_date=$(echo "$entry" | grep -o '\[[0-9-]*\]' | head -1 | tr -d '[]')
                    if [ -n "$entry_date" ] && [[ "$entry_date" > "$since_date" || "$entry_date" = "$since_date" ]]; then
                        ((project_entry_count++))
                    fi
                fi
            done < "$learnings_file"
        fi
    done < <(find "$BRAIN_DIR/projects" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

    if [ "$project_entry_count" -ge "$PROJECT_NEW_ENTRY_THRESHOLD" ]; then
        info "Weekly trigger: $project_entry_count recent project entries (threshold: $PROJECT_NEW_ENTRY_THRESHOLD) → TRIGGERED"
        should_weekly=true
    else
        info "Weekly trigger: $project_entry_count recent project entries (threshold: $PROJECT_NEW_ENTRY_THRESHOLD) → not triggered"
    fi

    echo ""

    if [ "$should_daily" = false ] && [ "$should_weekly" = false ]; then
        ok "No distillation needed at this time. Use --daily or --weekly to force."
        return
    fi

    if [ "$should_daily" = true ]; then
        run_daily_compound
        echo ""
    fi

    if [ "$should_weekly" = true ]; then
        run_weekly_compound
    fi
}

# ============================================================
# MAIN EXECUTION
# ============================================================

case "$MODE" in
    auto)
        run_auto_mode
        ;;
    daily)
        run_daily_compound
        ;;
    weekly)
        run_weekly_compound
        ;;
    all)
        run_daily_compound
        echo ""
        run_weekly_compound
        ;;
esac

# --- Git commit if changes were made ---
if [ "$DRY_RUN" = false ] && [ "$((DAILY_WRITTEN + WEEKLY_WRITTEN))" -gt 0 ]; then
    echo ""
    info "Committing distillation results..."
    cd "$HARNESS_ROOT"

    if [ -d ".git" ]; then
        git add brain/ 2>/dev/null

        local commit_msg="brain: compound distillation"
        case "$MODE" in
            daily)  commit_msg="brain: daily compound (session→project, $DAILY_WRITTEN entries)" ;;
            weekly) commit_msg="brain: weekly compound (project→global, $WEEKLY_WRITTEN entries)" ;;
            all)    commit_msg="brain: full compound (daily:$DAILY_WRITTEN + weekly:$WEEKLY_WRITTEN entries)" ;;
            auto)   commit_msg="brain: auto compound (daily:$DAILY_WRITTEN + weekly:$WEEKLY_WRITTEN entries)" ;;
        esac

        git commit -m "$commit_msg" --quiet 2>/dev/null || true
        ok "Committed: $commit_msg"

        if git remote get-url origin &>/dev/null; then
            git push --quiet 2>/dev/null && ok "Synced to remote." || warn "Push failed. Changes committed locally."
        fi
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Brain Compound complete."
echo ""
echo "  Summary:"
echo "    Daily  (Session → Project): $DAILY_CANDIDATES candidates → $DAILY_WRITTEN written"
echo "    Weekly (Project → Global):  $WEEKLY_CANDIDATES candidates → $WEEKLY_WRITTEN written"
echo ""
if [ "$DRY_RUN" = true ]; then
    echo -e "  ${YELLOW}This was a dry run. No files were modified.${NC}"
    echo "  Remove --dry-run to execute for real."
    echo ""
fi
