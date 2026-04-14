#!/bin/bash
set -uo pipefail

# ============================================================
# brain-gc.sh — Brain Garbage Collection & Capacity Governance
#
# Manages the health and size of the Brain memory system:
#   - Archive sessions older than retention period
#   - Control MEMORY.md file length
#   - Generate capacity reports
#
# Usage:
#   brain-gc.sh                    # Run all cleanup tasks
#   brain-gc.sh --sessions         # Only archive old sessions
#   brain-gc.sh --memory           # Only trim MEMORY.md
#   brain-gc.sh --report           # Only show capacity report
#   brain-gc.sh --dry-run          # Preview without changes
#   brain-gc.sh --days 60          # Custom retention period
# ============================================================

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()  { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()    { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail()  { echo -e "${RED}❌ $1${NC}"; }
header(){ echo -e "${BOLD}${MAGENTA}$1${NC}"; }

# --- Resolve harness repo root ---
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$HARNESS_ROOT/brain"
ARCHIVE_DIR="$BRAIN_DIR/.archive"

# --- Configuration defaults (can be overridden by .brain-config.yaml) ---
SESSION_TTL_DAYS=90
MEMORY_MAX_LINES=200
MEMORY_FILE="$HARNESS_ROOT/MEMORY.md"

# --- Try to read config from .brain-config.yaml ---
BRAIN_CONFIG="$HARNESS_ROOT/.brain-config.yaml"
if [ -f "$BRAIN_CONFIG" ]; then
    # Simple YAML parsing for our known keys
    config_ttl=$(grep 'session_ttl_days:' "$BRAIN_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d ' ')
    config_max_lines=$(grep 'max_memory_file_lines:' "$BRAIN_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d ' ')
    [ -n "$config_ttl" ] && SESSION_TTL_DAYS="$config_ttl"
    [ -n "$config_max_lines" ] && MEMORY_MAX_LINES="$config_max_lines"
fi

# --- Parse arguments ---
MODE="all"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sessions)
            MODE="sessions"
            shift
            ;;
        --memory)
            MODE="memory"
            shift
            ;;
        --report)
            MODE="report"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --days)
            SESSION_TTL_DAYS="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: brain-gc.sh [OPTIONS]"
            echo ""
            echo "Brain Garbage Collection & Capacity Governance."
            echo ""
            echo "Options:"
            echo "  --sessions       Only archive old sessions"
            echo "  --memory         Only trim MEMORY.md"
            echo "  --report         Only show capacity report (no changes)"
            echo "  --dry-run        Preview what would be done without making changes"
            echo "  --days <N>       Override session retention period (default: $SESSION_TTL_DAYS)"
            echo "  -h, --help       Show this help message"
            echo ""
            echo "Configuration is read from .brain-config.yaml:"
            echo "  session_ttl_days: $SESSION_TTL_DAYS"
            echo "  max_memory_file_lines: $MEMORY_MAX_LINES"
            exit 0
            ;;
        -*)
            fail "Unknown option: $1"
            echo "Run 'brain-gc.sh --help' for usage."
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
header "🧹 Brain GC — Capacity Governance"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Mode            : $MODE"
echo "  Dry run         : $DRY_RUN"
echo "  Session TTL     : $SESSION_TTL_DAYS days"
echo "  MEMORY.md limit : $MEMORY_MAX_LINES lines"
echo ""

# ============================================================
# Utility: Get date N days ago (macOS + Linux compatible)
# ============================================================
date_n_days_ago() {
    local days="$1"
    if date -v-1d +%Y-%m-%d &>/dev/null 2>&1; then
        # macOS
        date -v-${days}d +%Y-%m-%d
    else
        # Linux
        date -d "$days days ago" +%Y-%m-%d
    fi
}

# ============================================================
# Utility: Count files recursively in a directory
# ============================================================
count_files() {
    local dir="$1"
    if [ -d "$dir" ]; then
        find "$dir" -type f 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

# ============================================================
# Utility: Get directory size (human readable)
# ============================================================
dir_size() {
    local dir="$1"
    if [ -d "$dir" ]; then
        du -sh "$dir" 2>/dev/null | awk '{print $1}'
    else
        echo "0B"
    fi
}

# ============================================================
# Utility: Get oldest entry date from a directory of .md files
# ============================================================
oldest_entry_date() {
    local dir="$1"
    if [ -d "$dir" ]; then
        # Look for date patterns in filenames (session dirs) or entry lines
        local oldest_dir
        oldest_dir=$(find "$dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | head -1)
        if [ -n "$oldest_dir" ]; then
            basename "$oldest_dir"
            return
        fi
        # Fallback: look for date in file entries
        grep -rh '^\- \[' "$dir" 2>/dev/null | grep -o '\[[0-9-]*\]' | tr -d '[]' | sort | head -1
    fi
}

# ============================================================
# CAPACITY REPORT
# ============================================================
REPORT_SESSIONS_FILES=0
REPORT_SESSIONS_SIZE=""
REPORT_SESSIONS_OLDEST=""
REPORT_SESSIONS_EXPIRED=0
REPORT_PROJECTS_FILES=0
REPORT_PROJECTS_SIZE=""
REPORT_GLOBAL_FILES=0
REPORT_GLOBAL_SIZE=""
REPORT_MEMORY_LINES=0
REPORT_ARCHIVE_FILES=0
REPORT_ARCHIVE_SIZE=""

generate_report() {
    header "📊 Capacity Report"
    echo ""

    # Sessions
    REPORT_SESSIONS_FILES=$(count_files "$BRAIN_DIR/sessions")
    REPORT_SESSIONS_SIZE=$(dir_size "$BRAIN_DIR/sessions")
    REPORT_SESSIONS_OLDEST=$(oldest_entry_date "$BRAIN_DIR/sessions")

    # Count expired sessions
    local cutoff_date
    cutoff_date=$(date_n_days_ago "$SESSION_TTL_DAYS")
    REPORT_SESSIONS_EXPIRED=0

    while IFS= read -r session_dir; do
        local dirname
        dirname=$(basename "$session_dir")
        # Check if dirname is a date format and older than cutoff
        if [[ "$dirname" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && [[ "$dirname" < "$cutoff_date" ]]; then
            ((REPORT_SESSIONS_EXPIRED++))
        fi
    done < <(find "$BRAIN_DIR/sessions" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

    # Projects
    REPORT_PROJECTS_FILES=$(count_files "$BRAIN_DIR/projects")
    REPORT_PROJECTS_SIZE=$(dir_size "$BRAIN_DIR/projects")

    # Global
    REPORT_GLOBAL_FILES=$(count_files "$BRAIN_DIR/global")
    REPORT_GLOBAL_SIZE=$(dir_size "$BRAIN_DIR/global")

    # MEMORY.md
    if [ -f "$MEMORY_FILE" ]; then
        REPORT_MEMORY_LINES=$(wc -l < "$MEMORY_FILE" | tr -d ' ')
    fi

    # Archive
    REPORT_ARCHIVE_FILES=$(count_files "$ARCHIVE_DIR")
    REPORT_ARCHIVE_SIZE=$(dir_size "$ARCHIVE_DIR")

    # Print report table
    printf "  ${BOLD}%-14s  %6s  %8s  %-14s  %-20s${NC}\n" "Layer" "Files" "Size" "Oldest" "Status"
    printf "  %-14s  %6s  %8s  %-14s  %-20s\n" "──────────────" "──────" "────────" "──────────────" "────────────────────"

    # Sessions row
    local session_status="${GREEN}✅ OK${NC}"
    if [ "$REPORT_SESSIONS_EXPIRED" -gt 0 ]; then
        session_status="${YELLOW}⚠️  $REPORT_SESSIONS_EXPIRED expired${NC}"
    fi
    printf "  %-14s  %6s  %8s  %-14s  " "Sessions" "$REPORT_SESSIONS_FILES" "$REPORT_SESSIONS_SIZE" "${REPORT_SESSIONS_OLDEST:-n/a}"
    echo -e "$session_status"

    # Projects row
    printf "  %-14s  %6s  %8s  %-14s  " "Projects" "$REPORT_PROJECTS_FILES" "$REPORT_PROJECTS_SIZE" "—"
    echo -e "${GREEN}✅ OK${NC}"

    # Global row
    printf "  %-14s  %6s  %8s  %-14s  " "Global" "$REPORT_GLOBAL_FILES" "$REPORT_GLOBAL_SIZE" "—"
    echo -e "${GREEN}✅ OK${NC}"

    # MEMORY.md row
    local memory_status="${GREEN}✅ OK ($REPORT_MEMORY_LINES lines)${NC}"
    if [ "$REPORT_MEMORY_LINES" -gt "$MEMORY_MAX_LINES" ]; then
        memory_status="${YELLOW}⚠️  Over limit ($REPORT_MEMORY_LINES/$MEMORY_MAX_LINES)${NC}"
    fi
    printf "  %-14s  %6s  %8s  %-14s  " "MEMORY.md" "1" "$(du -sh "$MEMORY_FILE" 2>/dev/null | awk '{print $1}' || echo '0B')" "—"
    echo -e "$memory_status"

    # Archive row (if exists)
    if [ -d "$ARCHIVE_DIR" ] && [ "$REPORT_ARCHIVE_FILES" -gt 0 ]; then
        printf "  %-14s  %6s  %8s  %-14s  " "Archive" "$REPORT_ARCHIVE_FILES" "$REPORT_ARCHIVE_SIZE" "—"
        echo -e "${DIM}(archived)${NC}"
    fi

    echo ""

    # Recommendations
    local has_recommendation=false
    if [ "$REPORT_SESSIONS_EXPIRED" -gt 0 ]; then
        echo -e "  ${YELLOW}💡 Recommendation: Archive $REPORT_SESSIONS_EXPIRED expired session(s) (older than $SESSION_TTL_DAYS days)${NC}"
        has_recommendation=true
    fi
    if [ "$REPORT_MEMORY_LINES" -gt "$MEMORY_MAX_LINES" ]; then
        local excess=$((REPORT_MEMORY_LINES - MEMORY_MAX_LINES))
        echo -e "  ${YELLOW}💡 Recommendation: Trim MEMORY.md by ~$excess lines${NC}"
        has_recommendation=true
    fi
    if [ "$has_recommendation" = false ]; then
        echo -e "  ${GREEN}No action needed. Brain is healthy! 🧠${NC}"
    fi
    echo ""
}

# ============================================================
# SESSION ARCHIVAL
# ============================================================
ARCHIVED_COUNT=0

archive_sessions() {
    header "📦 Session Archival"
    echo ""

    local cutoff_date
    cutoff_date=$(date_n_days_ago "$SESSION_TTL_DAYS")
    info "Archiving sessions older than: $cutoff_date ($SESSION_TTL_DAYS days)"
    echo ""

    local candidates=()
    while IFS= read -r session_dir; do
        local dirname
        dirname=$(basename "$session_dir")
        # Only process date-formatted directories
        if [[ "$dirname" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && [[ "$dirname" < "$cutoff_date" ]]; then
            candidates+=("$session_dir")
        fi
    done < <(find "$BRAIN_DIR/sessions" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

    if [ ${#candidates[@]} -eq 0 ]; then
        ok "No sessions to archive. All sessions are within retention period."
        return
    fi

    info "Found ${#candidates[@]} session(s) to archive."
    echo ""

    for session_dir in "${candidates[@]}"; do
        local dirname
        dirname=$(basename "$session_dir")
        local file_count
        file_count=$(count_files "$session_dir")

        # Check if session was already distilled
        local distilled_marker="$session_dir/.distilled"
        local distilled_status=""
        if [ -f "$distilled_marker" ]; then
            distilled_status=" (already distilled ✅)"
        else
            distilled_status=" ${YELLOW}(NOT distilled — consider running brain-compound.sh first)${NC}"
        fi

        if [ "$DRY_RUN" = true ]; then
            echo -e "  ${YELLOW}[DRY RUN]${NC} Would archive: sessions/$dirname ($file_count files)$distilled_status"
        else
            # Create archive directory
            local archive_target="$ARCHIVE_DIR/sessions/$dirname"
            mkdir -p "$archive_target"

            # Move files to archive
            cp -r "$session_dir"/* "$archive_target/" 2>/dev/null || true
            cp "$session_dir"/.distilled "$archive_target/" 2>/dev/null || true

            # Remove original
            rm -rf "$session_dir"

            echo -e "  ${GREEN}[ARCHIVED]${NC} sessions/$dirname → .archive/sessions/$dirname ($file_count files)$distilled_status"
            ((ARCHIVED_COUNT++))
        fi
    done

    echo ""
    if [ "$DRY_RUN" = true ]; then
        info "Dry run: ${#candidates[@]} session(s) would be archived."
    else
        ok "Archived $ARCHIVED_COUNT session(s)."
    fi
}

# ============================================================
# MEMORY.md TRIMMING
# ============================================================
MEMORY_TRIMMED=false

trim_memory() {
    header "✂️  MEMORY.md Length Control"
    echo ""

    if [ ! -f "$MEMORY_FILE" ]; then
        info "MEMORY.md not found. Nothing to trim."
        return
    fi

    local current_lines
    current_lines=$(wc -l < "$MEMORY_FILE" | tr -d ' ')

    info "Current MEMORY.md: $current_lines lines (limit: $MEMORY_MAX_LINES)"

    if [ "$current_lines" -le "$MEMORY_MAX_LINES" ]; then
        ok "MEMORY.md is within limits. No trimming needed."
        return
    fi

    local excess=$((current_lines - MEMORY_MAX_LINES))
    info "Need to trim ~$excess lines."
    echo ""

    # Strategy: Keep the header (first section) and most recent entries.
    # Archive older entries to MEMORY.archive.md
    local archive_file="$HARNESS_ROOT/MEMORY.archive.md"

    if [ "$DRY_RUN" = true ]; then
        echo -e "  ${YELLOW}[DRY RUN]${NC} Would move oldest ~$excess lines to MEMORY.archive.md"
        echo -e "  ${YELLOW}[DRY RUN]${NC} MEMORY.md would be trimmed to ~$MEMORY_MAX_LINES lines"
        return
    fi

    # Find the split point: we want to keep the last MEMORY_MAX_LINES lines
    # But we need to be smart about it — don't split in the middle of a section

    # Step 1: Identify section headers (lines starting with ##)
    local section_lines=()
    local line_num=0
    while IFS= read -r line; do
        ((line_num++))
        if [[ "$line" == "## "* ]]; then
            section_lines+=("$line_num")
        fi
    done < "$MEMORY_FILE"

    # Step 2: Find the best split point — a section header that's closest to
    # keeping MEMORY_MAX_LINES lines at the end
    local target_split_line=$((current_lines - MEMORY_MAX_LINES))
    local best_split=1

    for section_line in "${section_lines[@]}"; do
        if [ "$section_line" -le "$target_split_line" ]; then
            best_split="$section_line"
        fi
    done

    # If best_split is 1 (no good section boundary found), use a simpler approach
    if [ "$best_split" -le 1 ]; then
        # Just keep the first 5 lines (header) + last (MEMORY_MAX_LINES - 5) lines
        local keep_tail=$((MEMORY_MAX_LINES - 5))

        # Archive the middle portion
        if [ ! -f "$archive_file" ]; then
            echo "# MEMORY.md Archive (auto-trimmed entries)" > "$archive_file"
            echo "" >> "$archive_file"
            echo "---" >> "$archive_file"
            echo "" >> "$archive_file"
        fi

        echo "## Archived on $(date +%Y-%m-%d)" >> "$archive_file"
        sed -n "6,$((current_lines - keep_tail))p" "$MEMORY_FILE" >> "$archive_file"
        echo "" >> "$archive_file"

        # Rebuild MEMORY.md: header + tail
        local tmp_file
        tmp_file=$(mktemp)
        head -5 "$MEMORY_FILE" > "$tmp_file"
        echo "" >> "$tmp_file"
        echo "*💡 Older entries archived to MEMORY.archive.md on $(date +%Y-%m-%d)*" >> "$tmp_file"
        echo "" >> "$tmp_file"
        tail -"$keep_tail" "$MEMORY_FILE" >> "$tmp_file"
        mv "$tmp_file" "$MEMORY_FILE"
    else
        # Archive everything before the split point
        if [ ! -f "$archive_file" ]; then
            echo "# MEMORY.md Archive (auto-trimmed entries)" > "$archive_file"
            echo "" >> "$archive_file"
            echo "---" >> "$archive_file"
            echo "" >> "$archive_file"
        fi

        echo "## Archived on $(date +%Y-%m-%d)" >> "$archive_file"
        # Keep the file header (line 1), archive from line 2 to split point
        sed -n "2,$((best_split - 1))p" "$MEMORY_FILE" >> "$archive_file"
        echo "" >> "$archive_file"

        # Rebuild MEMORY.md: header line + content from split point onward
        local tmp_file
        tmp_file=$(mktemp)
        head -1 "$MEMORY_FILE" > "$tmp_file"
        echo "" >> "$tmp_file"
        echo "*💡 Older entries archived to MEMORY.archive.md on $(date +%Y-%m-%d)*" >> "$tmp_file"
        echo "" >> "$tmp_file"
        sed -n "${best_split},\$p" "$MEMORY_FILE" >> "$tmp_file"
        mv "$tmp_file" "$MEMORY_FILE"
    fi

    local new_lines
    new_lines=$(wc -l < "$MEMORY_FILE" | tr -d ' ')
    ok "MEMORY.md trimmed: $current_lines → $new_lines lines"
    ok "Archived entries saved to: MEMORY.archive.md"
    MEMORY_TRIMMED=true
}

# ============================================================
# COMPOUND REPORT CLEANUP
# ============================================================
cleanup_old_reports() {
    # Clean up old compound reports (keep last 10)
    local report_count
    report_count=$(find "$BRAIN_DIR/sessions" -name ".compound-report-*.md" -type f 2>/dev/null | wc -l | tr -d ' ')

    if [ "$report_count" -gt 10 ]; then
        local to_remove=$((report_count - 10))
        if [ "$DRY_RUN" = true ]; then
            info "[DRY RUN] Would remove $to_remove old compound report(s)"
        else
            find "$BRAIN_DIR/sessions" -name ".compound-report-*.md" -type f 2>/dev/null | sort | head -"$to_remove" | while read -r f; do
                rm "$f"
            done
            info "Cleaned up $to_remove old compound report(s)"
        fi
    fi
}

# ============================================================
# MAIN EXECUTION
# ============================================================

case "$MODE" in
    report)
        generate_report
        ;;
    sessions)
        archive_sessions
        ;;
    memory)
        trim_memory
        ;;
    all)
        generate_report
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        archive_sessions
        echo ""
        trim_memory
        echo ""
        cleanup_old_reports
        ;;
esac

# --- Git commit if changes were made ---
if [ "$DRY_RUN" = false ] && { [ "$ARCHIVED_COUNT" -gt 0 ] || [ "$MEMORY_TRIMMED" = true ]; }; then
    echo ""
    info "Committing cleanup results..."
    cd "$HARNESS_ROOT"

    if [ -d ".git" ]; then
        git add -A 2>/dev/null

        local commit_parts=()
        [ "$ARCHIVED_COUNT" -gt 0 ] && commit_parts+=("archived $ARCHIVED_COUNT session(s)")
        [ "$MEMORY_TRIMMED" = true ] && commit_parts+=("trimmed MEMORY.md")

        local commit_msg="brain: gc — $(IFS=', '; echo "${commit_parts[*]}")"

        git commit -m "$commit_msg" --quiet 2>/dev/null || true
        ok "Committed: $commit_msg"

        if git remote get-url origin &>/dev/null; then
            git push --quiet 2>/dev/null && ok "Synced to remote." || warn "Push failed. Changes committed locally."
        fi
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Brain GC complete."
if [ "$DRY_RUN" = true ]; then
    echo -e "  ${YELLOW}This was a dry run. No files were modified.${NC}"
    echo "  Remove --dry-run to execute for real."
fi
echo ""
