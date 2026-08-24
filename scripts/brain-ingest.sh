#!/bin/bash
set -euo pipefail

# ============================================================
# brain-ingest.sh — Tool-neutral Brain ingestion endpoint
#
# This is intentionally an internal script, not a top-level harness command.
# Any tool hook can call it with markdown/text on stdin or --file.
# ============================================================

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck disable=SC1091
source "$HARNESS_ROOT/scripts/brain-resolve.sh"
if ! ensure_brain_available "$HARNESS_ROOT" >/dev/null 2>&1; then
    echo "Brain is disabled; ingestion skipped." >&2
    exit 2
fi

SOURCE="generic"
PROJECT=""
KIND="session"
INPUT_FILE=""
NO_SYNC=false

usage() {
    cat <<'EOF'
Usage: brain-ingest.sh [--source NAME] [--project SLUG] [--kind session|learning|failure] [--file PATH] [--no-sync]

Reads content from --file or stdin and writes it into Private Brain.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)
            shift; SOURCE="${1:-generic}"; shift ;;
        --project)
            shift; PROJECT="${1:-}"; shift ;;
        --kind)
            shift; KIND="${1:-session}"; shift ;;
        --file)
            shift; INPUT_FILE="${1:-}"; shift ;;
        --no-sync)
            NO_SYNC=true; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1 ;;
    esac
done

case "$KIND" in
    session|learning|failure) ;;
    *)
        echo "Invalid --kind: $KIND" >&2
        exit 1 ;;
esac

if [ -n "$INPUT_FILE" ]; then
    [ -f "$INPUT_FILE" ] || { echo "Input file not found: $INPUT_FILE" >&2; exit 1; }
    CONTENT="$(cat "$INPUT_FILE")"
else
    CONTENT="$(cat)"
fi

if [ -z "$(printf '%s' "$CONTENT" | tr -d '[:space:]')" ]; then
    echo "No content to ingest." >&2
    exit 0
fi

safe_name() {
    printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g; s/--*/-/g; s/^-//; s/-$//'
}

DATE_TODAY="$(date '+%Y-%m-%d')"
STAMP="$(date '+%Y%m%d-%H%M%S')"
SAFE_SOURCE="$(safe_name "$SOURCE")"
SAFE_PROJECT="$(safe_name "${PROJECT:-none}")"

case "$KIND" in
    session)
        OUT_DIR="$BRAIN_DIR/sessions/$DATE_TODAY"
        mkdir -p "$OUT_DIR"
        OUT_FILE="$OUT_DIR/${SAFE_SOURCE}-${STAMP}.md"
        {
            echo "# Session Digest — $SOURCE"
            echo ""
            echo "- date: $DATE_TODAY"
            echo "- source: $SOURCE"
            [ -n "$PROJECT" ] && echo "- project: $PROJECT"
            echo ""
            echo "## Content"
            echo ""
            printf '%s\n' "$CONTENT"
        } > "$OUT_FILE"
        ;;
    learning)
        if [ -n "$PROJECT" ]; then
            OUT_DIR="$BRAIN_DIR/projects/$SAFE_PROJECT"
            mkdir -p "$OUT_DIR"
            OUT_FILE="$OUT_DIR/learnings.md"
        else
            OUT_FILE="$BRAIN_DIR/global/gotchas.md"
        fi
        {
            echo ""
            echo "- $DATE_TODAY · $SOURCE · ${PROJECT:-global} · $(printf '%s' "$CONTENT" | tr '\n' ' ' | sed 's/[[:space:]][[:space:]]*/ /g')"
        } >> "$OUT_FILE"
        ;;
    failure)
        OUT_FILE="$BRAIN_DIR/global/evolution/harness-failures.md"
        mkdir -p "$(dirname "$OUT_FILE")"
        {
            echo "$DATE_TODAY · ${PROJECT:-unknown-project} · ${SOURCE:-generic} · $(printf '%s' "$CONTENT" | tr '\n' ' ' | sed 's/[[:space:]][[:space:]]*/ /g')"
        } >> "$OUT_FILE"
        ;;
esac

if [ "$NO_SYNC" = false ]; then
    commit_brain_changes "brain: ingest $KIND from $SOURCE" false >/dev/null 2>&1 || true
fi

echo "$OUT_FILE"
