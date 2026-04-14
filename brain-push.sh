#!/bin/bash
set -euo pipefail

# ============================================================
# brain-push.sh — Write a memory entry to the Brain
# Usage:
#   brain-push.sh "your memory text"
#   brain-push.sh --layer global --category gotchas "some pitfall"
#   brain-push.sh --from-clipboard --source claude-web
#   brain-push.sh  (interactive mode)
# ============================================================

# --- Color helpers ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()    { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
fail()  { echo -e "${RED}❌ $1${NC}"; }

# --- Resolve harness repo root (where this script lives) ---
HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- Default values ---
LAYER="session"
CATEGORY=""
PROJECT_SLUG=""
SOURCE="cli"
FROM_CLIPBOARD=false
NO_SYNC=false
MESSAGE=""

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --layer)
            LAYER="$2"
            shift 2
            ;;
        --category)
            CATEGORY="$2"
            shift 2
            ;;
        --project)
            PROJECT_SLUG="$2"
            shift 2
            ;;
        --source)
            SOURCE="$2"
            shift 2
            ;;
        --from-clipboard)
            FROM_CLIPBOARD=true
            shift
            ;;
        --no-sync)
            NO_SYNC=true
            shift
            ;;
        --help|-h)
            echo "Usage: brain-push.sh [OPTIONS] [MESSAGE]"
            echo ""
            echo "Write a memory entry to the Brain."
            echo ""
            echo "Options:"
            echo "  --layer <global|project|session>  Target layer (default: session)"
            echo "  --category <name>                 Category within global layer"
            echo "                                    (preferences, gotchas, or custom)"
            echo "  --project <slug>                  Project slug (required for project layer)"
            echo "  --source <name>                   Source identifier (default: cli)"
            echo "                                    (e.g., cursor, claude-web, chatgpt)"
            echo "  --from-clipboard                  Read message from clipboard (pbpaste)"
            echo "  --no-sync                         Only commit locally, don't git push"
            echo "  -h, --help                        Show this help message"
            echo ""
            echo "Examples:"
            echo "  brain-push.sh \"Redis connection pool maxIdle should be >= 10\""
            echo "  brain-push.sh --layer global --category gotchas \"npm audit false positives in CI\""
            echo "  brain-push.sh --layer project --project my-app \"Uses Next.js 14 + Prisma\""
            echo "  brain-push.sh --from-clipboard --source claude-web"
            echo "  brain-push.sh  # interactive mode"
            exit 0
            ;;
        -*)
            fail "Unknown option: $1"
            echo "Run 'brain-push.sh --help' for usage."
            exit 1
            ;;
        *)
            # Positional argument = message
            if [ -z "$MESSAGE" ]; then
                MESSAGE="$1"
            else
                MESSAGE="$MESSAGE $1"
            fi
            shift
            ;;
    esac
done

# --- Read from clipboard if requested ---
if [ "$FROM_CLIPBOARD" = true ]; then
    if command -v pbpaste &>/dev/null; then
        CLIPBOARD_CONTENT="$(pbpaste)"
    elif command -v xclip &>/dev/null; then
        CLIPBOARD_CONTENT="$(xclip -selection clipboard -o)"
    elif command -v xsel &>/dev/null; then
        CLIPBOARD_CONTENT="$(xsel --clipboard --output)"
    else
        fail "No clipboard tool found (pbpaste/xclip/xsel). Please install one or pass message directly."
        exit 1
    fi

    if [ -z "$CLIPBOARD_CONTENT" ]; then
        fail "Clipboard is empty."
        exit 1
    fi

    if [ -n "$MESSAGE" ]; then
        # If both clipboard and message provided, append clipboard content
        MESSAGE="$MESSAGE\n$CLIPBOARD_CONTENT"
    else
        MESSAGE="$CLIPBOARD_CONTENT"
    fi
    info "Read from clipboard (${#CLIPBOARD_CONTENT} chars)"
fi

# --- Interactive mode if no message ---
if [ -z "$MESSAGE" ]; then
    echo ""
    echo "🧠 Brain Push — Interactive Mode"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Select layer
    echo "Select target layer:"
    echo "  1) session  (default — raw daily notes)"
    echo "  2) project  (project-specific learnings)"
    echo "  3) global   (cross-project preferences & gotchas)"
    read -rp "Layer [1]: " LAYER_CHOICE
    case "${LAYER_CHOICE:-1}" in
        1) LAYER="session" ;;
        2) LAYER="project" ;;
        3) LAYER="global" ;;
        *) LAYER="session" ;;
    esac

    # If project layer, ask for project slug
    if [ "$LAYER" = "project" ]; then
        # List existing projects
        EXISTING_PROJECTS=$(find "$HARNESS_ROOT/brain/projects" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort)
        if [ -n "$EXISTING_PROJECTS" ]; then
            echo ""
            echo "Existing projects:"
            echo "$EXISTING_PROJECTS" | sed 's/^/  - /'
        fi
        read -rp "Project slug: " PROJECT_SLUG
        if [ -z "$PROJECT_SLUG" ]; then
            fail "Project slug is required for project layer."
            exit 1
        fi
    fi

    # If global layer, ask for category
    if [ "$LAYER" = "global" ]; then
        echo ""
        echo "Select category:"
        echo "  1) preferences  (coding style, tool chain, communication)"
        echo "  2) gotchas      (pitfalls, environment issues)"
        echo "  3) custom       (enter a custom category name)"
        read -rp "Category [1]: " CAT_CHOICE
        case "${CAT_CHOICE:-1}" in
            1) CATEGORY="preferences" ;;
            2) CATEGORY="gotchas" ;;
            3)
                read -rp "Custom category name: " CATEGORY
                if [ -z "$CATEGORY" ]; then
                    CATEGORY="preferences"
                fi
                ;;
            *) CATEGORY="preferences" ;;
        esac
    fi

    # Ask for source
    read -rp "Source [cli]: " SOURCE_INPUT
    SOURCE="${SOURCE_INPUT:-cli}"

    # Ask for message
    echo ""
    echo "Enter your memory (press Enter to finish):"
    read -rp "> " MESSAGE
    if [ -z "$MESSAGE" ]; then
        fail "Message cannot be empty."
        exit 1
    fi

    echo ""
fi

# --- Validate layer ---
case "$LAYER" in
    global|project|session) ;;
    *)
        fail "Invalid layer: $LAYER (must be global, project, or session)"
        exit 1
        ;;
esac

# --- Validate project slug for project layer ---
if [ "$LAYER" = "project" ] && [ -z "$PROJECT_SLUG" ]; then
    fail "Project slug is required for project layer. Use --project <slug>"
    exit 1
fi

# --- Determine target file ---
TODAY=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d)

case "$LAYER" in
    global)
        # Default category is preferences
        CATEGORY="${CATEGORY:-preferences}"
        TARGET_FILE="$HARNESS_ROOT/brain/global/${CATEGORY}.md"

        # If the file doesn't exist, create it with a header
        if [ ! -f "$TARGET_FILE" ]; then
            mkdir -p "$(dirname "$TARGET_FILE")"
            echo "# Global ${CATEGORY^} (跨项目通用)" > "$TARGET_FILE"
            echo "" >> "$TARGET_FILE"
            info "Created new global category file: ${CATEGORY}.md"
        fi
        ;;
    project)
        PROJECT_DIR="$HARNESS_ROOT/brain/projects/$PROJECT_SLUG"
        TARGET_FILE="$PROJECT_DIR/learnings.md"

        # Create project directory and file if needed
        if [ ! -d "$PROJECT_DIR" ]; then
            mkdir -p "$PROJECT_DIR"
            info "Created project directory: brain/projects/$PROJECT_SLUG/"
        fi
        if [ ! -f "$TARGET_FILE" ]; then
            echo "# Project: $PROJECT_SLUG — Learnings" > "$TARGET_FILE"
            echo "" >> "$TARGET_FILE"
            info "Created project learnings file."
        fi
        ;;
    session)
        SESSION_DIR="$HARNESS_ROOT/brain/sessions/$TODAY"
        TARGET_FILE="$SESSION_DIR/${SOURCE}.md"

        # Create session date directory and file if needed
        if [ ! -d "$SESSION_DIR" ]; then
            mkdir -p "$SESSION_DIR"
            info "Created session directory: brain/sessions/$TODAY/"
        fi
        if [ ! -f "$TARGET_FILE" ]; then
            echo "# Session: $TODAY (source: $SOURCE)" > "$TARGET_FILE"
            echo "" >> "$TARGET_FILE"
            info "Created session file: $TODAY/${SOURCE}.md"
        fi
        ;;
esac

# --- Write the memory entry ---
ENTRY="- [$TIMESTAMP] (source: $SOURCE) $MESSAGE"
echo "$ENTRY" >> "$TARGET_FILE"

echo ""
ok "Memory written to: ${TARGET_FILE#$HARNESS_ROOT/}"
echo -e "  ${CYAN}Layer${NC}:    $LAYER"
echo -e "  ${CYAN}Source${NC}:   $SOURCE"
echo -e "  ${CYAN}Entry${NC}:    $ENTRY"

# --- Git commit in harness repo ---
cd "$HARNESS_ROOT"

# Check if we're in a git repo
if [ -d ".git" ]; then
    RELATIVE_PATH="${TARGET_FILE#$HARNESS_ROOT/}"
    git add "$RELATIVE_PATH" 2>/dev/null

    COMMIT_MSG="brain: push to $LAYER"
    case "$LAYER" in
        global)  COMMIT_MSG="brain: push to global/$CATEGORY (source: $SOURCE)" ;;
        project) COMMIT_MSG="brain: push to project/$PROJECT_SLUG (source: $SOURCE)" ;;
        session) COMMIT_MSG="brain: push to session/$TODAY (source: $SOURCE)" ;;
    esac

    git commit -m "$COMMIT_MSG" --quiet 2>/dev/null || true
    ok "Committed to local git."

    # Sync to remote unless --no-sync
    if [ "$NO_SYNC" = false ]; then
        if git remote get-url origin &>/dev/null; then
            git push --quiet 2>/dev/null && ok "Synced to remote." || warn "Push failed. Changes are committed locally."
        else
            warn "No remote configured. Changes are committed locally only."
        fi
    else
        info "Skipping remote sync (--no-sync)."
    fi
else
    warn "Not a git repository. Memory written to file but not committed."
fi

echo ""
