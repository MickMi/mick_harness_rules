#!/bin/bash
set -uo pipefail

# ============================================================
# brain-search.sh — Search memories in the Brain
# Usage:
#   brain-search.sh "keyword"
#   brain-search.sh --layer global "coding style"
#   brain-search.sh --since 7d "Redis"
#   brain-search.sh --format compact "Prisma"
#   brain-search.sh --regex "ADR-0[0-9]+"
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

# --- Resolve harness repo root ---
# Can be called from:
#   1. Directly: /path/to/harness/brain-search.sh
#   2. Via symlink: .harness/brain-search.sh
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
# If called via symlink, resolve the real path
if [ -L "$0" ]; then
    REAL_SCRIPT="$(readlink "$0")"
    HARNESS_ROOT="$(cd "$(dirname "$REAL_SCRIPT")" && pwd)"
fi

BRAIN_DIR="$HARNESS_ROOT/brain"

# --- Default values ---
LAYER=""
PROJECT_SLUG=""
SINCE=""
FORMAT="context"
USE_REGEX=false
QUERY=""

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --layer)
            LAYER="$2"
            shift 2
            ;;
        --project)
            PROJECT_SLUG="$2"
            shift 2
            ;;
        --since)
            SINCE="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --regex)
            USE_REGEX=true
            shift
            ;;
        --help|-h)
            echo "Usage: brain-search.sh [OPTIONS] <query>"
            echo ""
            echo "Search memories in the Brain using ripgrep (with grep fallback)."
            echo ""
            echo "Options:"
            echo "  --layer <global|project|session>  Limit search to a specific layer"
            echo "  --project <slug>                  Limit to a specific project (implies --layer project)"
            echo "  --since <Nd|YYYY-MM-DD>           Filter sessions by date (e.g., 7d, 2026-04-01)"
            echo "  --format <compact|context|file>   Output format (default: context)"
            echo "    compact  — matching lines only"
            echo "    context  — matching lines with 3 lines of context"
            echo "    file     — list of matching files only"
            echo "  --regex                           Treat query as a regular expression"
            echo "  -h, --help                        Show this help message"
            echo ""
            echo "Examples:"
            echo "  brain-search.sh \"Redis cache\""
            echo "  brain-search.sh --layer global \"coding style\""
            echo "  brain-search.sh --project my-app \"database\""
            echo "  brain-search.sh --since 7d \"OAuth\""
            echo "  brain-search.sh --format compact \"Prisma\""
            echo "  brain-search.sh --regex \"ADR-0[0-9]+\""
            exit 0
            ;;
        -*)
            fail "Unknown option: $1"
            echo "Run 'brain-search.sh --help' for usage."
            exit 1
            ;;
        *)
            if [ -z "$QUERY" ]; then
                QUERY="$1"
            else
                QUERY="$QUERY $1"
            fi
            shift
            ;;
    esac
done

# --- Validate query ---
if [ -z "$QUERY" ]; then
    fail "No search query provided."
    echo "Usage: brain-search.sh [OPTIONS] <query>"
    echo "Run 'brain-search.sh --help' for more info."
    exit 1
fi

# --- Validate brain directory ---
if [ ! -d "$BRAIN_DIR" ]; then
    fail "Brain directory not found at: $BRAIN_DIR"
    echo "Make sure you're running this from the harness repo or via .harness/ symlink."
    exit 1
fi

# --- If --project is given, imply --layer project ---
if [ -n "$PROJECT_SLUG" ]; then
    LAYER="project"
fi

# --- Determine search directories based on layer ---
SEARCH_DIRS=()

case "$LAYER" in
    global)
        SEARCH_DIRS=("$BRAIN_DIR/global")
        ;;
    project)
        if [ -n "$PROJECT_SLUG" ]; then
            PROJECT_PATH="$BRAIN_DIR/projects/$PROJECT_SLUG"
            if [ ! -d "$PROJECT_PATH" ]; then
                fail "Project not found: $PROJECT_SLUG"
                echo "Available projects:"
                find "$BRAIN_DIR/projects" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sed 's/^/  - /'
                exit 1
            fi
            SEARCH_DIRS=("$PROJECT_PATH")
        else
            SEARCH_DIRS=("$BRAIN_DIR/projects")
        fi
        ;;
    session)
        SEARCH_DIRS=("$BRAIN_DIR/sessions")
        ;;
    "")
        # Search all layers, ordered by priority: global → project → session
        SEARCH_DIRS=("$BRAIN_DIR/global" "$BRAIN_DIR/projects" "$BRAIN_DIR/sessions")
        ;;
    *)
        fail "Invalid layer: $LAYER (must be global, project, or session)"
        exit 1
        ;;
esac

# --- Resolve --since filter for session directories ---
# Returns a date string YYYY-MM-DD that we filter against
SINCE_DATE=""
if [ -n "$SINCE" ]; then
    if [[ "$SINCE" =~ ^[0-9]+d$ ]]; then
        # Relative: Nd (e.g., 7d = 7 days ago)
        DAYS="${SINCE%d}"
        if date -v-1d +%Y-%m-%d &>/dev/null 2>&1; then
            # macOS date
            SINCE_DATE=$(date -v-"${DAYS}d" +%Y-%m-%d)
        else
            # GNU date
            SINCE_DATE=$(date -d "$DAYS days ago" +%Y-%m-%d)
        fi
    elif [[ "$SINCE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        # Absolute: YYYY-MM-DD
        SINCE_DATE="$SINCE"
    else
        fail "Invalid --since format: $SINCE (use Nd or YYYY-MM-DD)"
        exit 1
    fi
    info "Filtering sessions since: $SINCE_DATE"
fi

# --- Detect search engine ---
USE_RIPGREP=false
if command -v rg &>/dev/null; then
    USE_RIPGREP=true
fi

# --- Build search command arguments ---
build_rg_args() {
    local dir="$1"
    local args=()

    # File type filter: only search markdown files
    args+=(--type md)

    # Case insensitive by default
    args+=(--smart-case)

    # Format-specific options
    case "$FORMAT" in
        compact)
            args+=(--no-heading --line-number)
            ;;
        context)
            args+=(--context 3 --heading --line-number)
            ;;
        file)
            args+=(--files-with-matches)
            ;;
    esac

    # Regex or fixed string
    if [ "$USE_REGEX" = true ]; then
        args+=("$QUERY")
    else
        args+=(--fixed-strings "$QUERY")
    fi

    args+=("$dir")
    echo "${args[@]}"
}

build_grep_args() {
    local dir="$1"
    local args=()

    # Recursive
    args+=(-r)

    # Case insensitive
    args+=(-i)

    # Only search .md files
    args+=(--include="*.md")

    # Format-specific options
    case "$FORMAT" in
        compact)
            args+=(-n)
            ;;
        context)
            args+=(-n --context=3)
            ;;
        file)
            args+=(-l)
            ;;
    esac

    # Regex or fixed string
    if [ "$USE_REGEX" = true ]; then
        args+=("$QUERY")
    else
        args+=(-F "$QUERY")
    fi

    args+=("$dir")
    echo "${args[@]}"
}

# --- Filter session directories by date ---
filter_session_dir() {
    local dir="$1"

    # Only filter if --since is set and we're searching sessions
    if [ -z "$SINCE_DATE" ]; then
        return 0  # no filter, include all
    fi

    # Check if this is a session date directory (YYYY-MM-DD)
    local dirname
    dirname=$(basename "$dir")
    if [[ "$dirname" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        if [[ "$dirname" < "$SINCE_DATE" ]]; then
            return 1  # exclude: before since date
        fi
    fi

    return 0  # include
}

# --- Execute search ---
echo ""
echo "🔍 Brain Search"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${CYAN}Query${NC}:   $QUERY"
echo -e "  ${CYAN}Layer${NC}:   ${LAYER:-all}"
echo -e "  ${CYAN}Format${NC}:  $FORMAT"
echo -e "  ${CYAN}Engine${NC}:  $([ "$USE_RIPGREP" = true ] && echo "ripgrep" || echo "grep (fallback)")"
if [ -n "$SINCE_DATE" ]; then
    echo -e "  ${CYAN}Since${NC}:   $SINCE_DATE"
fi
echo ""

TOTAL_MATCHES=0
HAS_RESULTS=false

# Layer labels for output
get_layer_label() {
    local path="$1"
    if [[ "$path" == *"/brain/global/"* ]]; then
        echo -e "${GREEN}[global]${NC}"
    elif [[ "$path" == *"/brain/projects/"* ]]; then
        # Extract project slug
        local slug
        slug=$(echo "$path" | sed -n 's|.*/brain/projects/\([^/]*\)/.*|\1|p')
        echo -e "${MAGENTA}[project:$slug]${NC}"
    elif [[ "$path" == *"/brain/sessions/"* ]]; then
        # Extract date
        local date_str
        date_str=$(echo "$path" | sed -n 's|.*/brain/sessions/\([^/]*\)/.*|\1|p')
        echo -e "${YELLOW}[session:$date_str]${NC}"
    else
        echo "[brain]"
    fi
}

# Search each directory in priority order
for search_dir in "${SEARCH_DIRS[@]}"; do
    if [ ! -d "$search_dir" ]; then
        continue
    fi

    # For session layer with --since, we need to handle date filtering
    if [[ "$search_dir" == *"/sessions"* ]] && [ -n "$SINCE_DATE" ]; then
        # Search each date directory individually
        FOUND_SESSION_DIRS=false
        while IFS= read -r date_dir; do
            if filter_session_dir "$date_dir"; then
                FOUND_SESSION_DIRS=true
                if [ "$USE_RIPGREP" = true ]; then
                    RESULT=$(rg --type md --smart-case \
                        $([ "$FORMAT" = "compact" ] && echo "--no-heading --line-number" || true) \
                        $([ "$FORMAT" = "context" ] && echo "--context 3 --heading --line-number" || true) \
                        $([ "$FORMAT" = "file" ] && echo "--files-with-matches" || true) \
                        $([ "$USE_REGEX" = true ] && echo "" || echo "--fixed-strings") \
                        "$QUERY" "$date_dir" 2>/dev/null) || true
                else
                    RESULT=$(grep -r -i --include="*.md" \
                        $([ "$FORMAT" = "compact" ] && echo "-n" || true) \
                        $([ "$FORMAT" = "context" ] && echo "-n --context=3" || true) \
                        $([ "$FORMAT" = "file" ] && echo "-l" || true) \
                        $([ "$USE_REGEX" = true ] && echo "" || echo "-F") \
                        "$QUERY" "$date_dir" 2>/dev/null) || true
                fi

                if [ -n "$RESULT" ]; then
                    HAS_RESULTS=true
                    # Count matches
                    MATCH_COUNT=$(echo "$RESULT" | grep -c "." || true)
                    TOTAL_MATCHES=$((TOTAL_MATCHES + MATCH_COUNT))

                    # Print with layer label
                    LAYER_LABEL=$(get_layer_label "$date_dir/x")
                    echo -e "$LAYER_LABEL"
                    # Make paths relative to harness root for readability
                    echo "$RESULT" | sed "s|$HARNESS_ROOT/||g"
                    echo ""
                fi
            fi
        done < <(find "$search_dir" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)
    else
        # Normal search (global, project, or session without date filter)
        if [ "$USE_RIPGREP" = true ]; then
            RESULT=$(rg --type md --smart-case \
                $([ "$FORMAT" = "compact" ] && echo "--no-heading --line-number" || true) \
                $([ "$FORMAT" = "context" ] && echo "--context 3 --heading --line-number" || true) \
                $([ "$FORMAT" = "file" ] && echo "--files-with-matches" || true) \
                $([ "$USE_REGEX" = true ] && echo "" || echo "--fixed-strings") \
                "$QUERY" "$search_dir" 2>/dev/null) || true
        else
            RESULT=$(grep -r -i --include="*.md" \
                $([ "$FORMAT" = "compact" ] && echo "-n" || true) \
                $([ "$FORMAT" = "context" ] && echo "-n --context=3" || true) \
                $([ "$FORMAT" = "file" ] && echo "-l" || true) \
                $([ "$USE_REGEX" = true ] && echo "" || echo "-F") \
                "$QUERY" "$search_dir" 2>/dev/null) || true
        fi

        if [ -n "$RESULT" ]; then
            HAS_RESULTS=true
            MATCH_COUNT=$(echo "$RESULT" | grep -c "." || true)
            TOTAL_MATCHES=$((TOTAL_MATCHES + MATCH_COUNT))

            # Determine layer label from directory
            if [[ "$search_dir" == *"/global"* ]]; then
                echo -e "${GREEN}${BOLD}── Global Layer ──${NC}"
            elif [[ "$search_dir" == *"/projects"* ]]; then
                echo -e "${MAGENTA}${BOLD}── Project Layer ──${NC}"
            elif [[ "$search_dir" == *"/sessions"* ]]; then
                echo -e "${YELLOW}${BOLD}── Session Layer ──${NC}"
            fi

            # Make paths relative for readability
            echo "$RESULT" | sed "s|$HARNESS_ROOT/||g"
            echo ""
        fi
    fi
done

# --- Summary ---
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$HAS_RESULTS" = true ]; then
    ok "Found matches (~$TOTAL_MATCHES lines) for: \"$QUERY\""
else
    warn "No matches found for: \"$QUERY\""
    echo ""
    echo "  Tips:"
    echo "  - Try different keywords or broader terms"
    echo "  - Use --regex for pattern matching"
    echo "  - Check available layers: brain-search.sh --layer global \"...\""
fi
echo ""
