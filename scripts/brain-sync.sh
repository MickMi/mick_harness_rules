#!/bin/bash
set -uo pipefail

# ============================================================
# brain-sync.sh — SessionEnd hook handler
#
# Invoked by Claude Code SessionEnd hook or manually.
# Receives JSON on stdin with session_id, or accepts it as $1.
#
# Flow:
#   1. Parse session_id from stdin or args
#   2. Early-exit gates (lock, already-synced, min-size)
#   3. Filter transcript to plain text digest (inline Python)
#   4. Run claude -p to distill structured summary
#   5. Write entries to brain via brain-push.sh
#   6. Commit + push, mark synced, release lock
#
# Logs: ~/.claude/logs/brain-sync.log
# ============================================================

# --- Paths ---
HARNESS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Resolve transcript directory: use CLAUDE_PROJECT_DIR env var, or auto-detect from
# the standard Claude Code directory pattern.
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    TRANSCRIPT_DIR="$CLAUDE_PROJECT_DIR"
else
    # Auto-detect: find the most recent Claude Code project directory
    TRANSCRIPT_DIR=$(ls -dt "$HOME"/.claude/projects/-Users-* 2>/dev/null | head -1 || echo "")
fi

SYNC_STATE="$HOME/.claude/.brain-sync-state"
SYNCED_DIR="$SYNC_STATE/synced"
ERROR_DIR="$SYNC_STATE/errors"
LOCK_DIR="$SYNC_STATE/lock"
LOG_FILE="$HOME/.claude/logs/brain-sync.log"
BRAIN_REPO=""

# --- Resolve brain ---
source "$HARNESS_ROOT/scripts/brain-resolve.sh"
resolve_brain_dir "$HARNESS_ROOT"
if [ "${BRAIN_MODE:-disabled}" = "disabled" ]; then
    exit 0
fi
ensure_brain_available "$HARNESS_ROOT" >/dev/null 2>&1 || exit 0
BRAIN_REPO="${BRAIN_DIR:-$HOME/.brain}"

log()   { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; }

# --- Env check: ensure required directories and commands exist ---
mkdir -p "$SYNCED_DIR" "$ERROR_DIR" "$(dirname "$LOG_FILE")"

# Guard: claude CLI is required for distillation. If not available, exit silently.
if ! command -v claude >/dev/null 2>&1; then
    log "claude CLI not found; brain-sync requires it for distillation. Exiting."
    exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
    log "python3 not found; brain-sync requires it. Exiting."
    exit 0
fi

# Brain must never block the hook path. Private remote failures are handled
# by ensure_brain_available with a local fallback.
mkdir -p "$BRAIN_REPO"

# --- Parse session_id ---
SESSION_ID=""
# Try stdin JSON first (from hook)
if [ ! -t 0 ]; then
    STDIN_DATA=$(cat 2>/dev/null || true)
    SESSION_ID=$(echo "$STDIN_DATA" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id',''))" 2>/dev/null || true)
fi
# Fallback: command-line arg
if [ -z "$SESSION_ID" ] && [ $# -ge 1 ]; then
    SESSION_ID="$1"
fi
# Last resort: find most recent unsynced transcript
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(ls -t "$TRANSCRIPT_DIR"/*.jsonl 2>/dev/null | while read f; do
        sid=$(basename "$f" .jsonl)
        # Extract UUID prefix: 8-4 (e.g., a1b2c3d4-e5f6)
        sid=$(echo "$sid" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}' | head -1)
        [ -n "$sid" ] && [ ! -f "$SYNCED_DIR/$sid" ] && echo "$sid" && break
    done)
fi

if [ -z "$SESSION_ID" ]; then
    log "No session_id found, exiting"
    exit 0
fi

# Normalize to first 8+4 UUID segments
SESSION_SHORT=$(echo "$SESSION_ID" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}' | head -1)
[ -z "$SESSION_SHORT" ] && SESSION_SHORT="$SESSION_ID"

log "SessionEnd: $SESSION_SHORT — START"

# --- Gate 1: Lock ---
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    # Check if lock is stale (> 30 min)
    if [ -d "$LOCK_DIR" ]; then
        LOCK_AGE=$(($(date +%s) - $(stat -f %m "$LOCK_DIR" 2>/dev/null || echo 0)))
        if [ "${LOCK_AGE:-0}" -gt 1800 ]; then
            log "Stale lock ($LOCK_AGE seconds), removing and re-acquiring"
            rmdir "$LOCK_DIR" 2>/dev/null
            mkdir "$LOCK_DIR" 2>/dev/null || { log "Lock re-acquire failed, exiting"; exit 0; }
        else
            log "Lock held by another process (age: ${LOCK_AGE:-?}s), exiting"
            exit 0
        fi
    fi
fi

# --- Gate 2: Already synced? ---
if [ -f "$SYNCED_DIR/$SESSION_SHORT" ]; then
    log "SessionEnd: $SESSION_SHORT — already synced, SKIP"
    rmdir "$LOCK_DIR" 2>/dev/null
    exit 0
fi

# --- Find transcript ---
TRANSCRIPT_FILE=""
for f in "$TRANSCRIPT_DIR/${SESSION_SHORT}"*.jsonl; do
    [ -f "$f" ] && TRANSCRIPT_FILE="$f" && break
done

if [ -z "$TRANSCRIPT_FILE" ]; then
    log "SessionEnd: $SESSION_SHORT — transcript not found"
    rmdir "$LOCK_DIR" 2>/dev/null
    exit 0
fi

export TRANSCRIPT_FILE

# --- Gate 3: Minimum session size ---
USER_MSG_COUNT=$(python3 -c "
import json
count = 0
with open('$TRANSCRIPT_FILE') as f:
    for line in f:
        try:
            obj = json.loads(line)
            msg = obj.get('message', {})
            if msg.get('role') == 'user' and obj.get('type') not in ('attachment',):
                count += 1
        except: pass
print(count)
" 2>/dev/null || echo "0")

if [ "$USER_MSG_COUNT" -lt 3 ]; then
    log "SessionEnd: $SESSION_SHORT — too few user messages ($USER_MSG_COUNT), SKIP"
    rmdir "$LOCK_DIR" 2>/dev/null
    exit 0
fi

log "SessionEnd: $SESSION_SHORT — transcript: $(basename "$TRANSCRIPT_FILE") ($USER_MSG_COUNT user msgs)"

# --- Filter transcript ---
FILTERED=$(python3 << 'PYEOF'
import json, sys, os

transcript_file = os.environ.get('TRANSCRIPT_FILE', '')
MAX_CHARS = 30000

lines = []
with open(transcript_file) as f:
    for line in f:
        try:
            obj = json.loads(line)
            t = obj.get('type', '')
            msg = obj.get('message', {})
            role = msg.get('role', '')
            content = msg.get('content', '')

            if t == 'attachment':
                continue  # skip skill listings, system reminders

            if role == 'user':
                text = content if isinstance(content, str) else ''
                if len(text) > 500:
                    text = text[:500] + '...'
                lines.append(f"USER: {text}")

            elif role == 'assistant':
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get('type') == 'text':
                                txt = block.get('text', '')
                                if len(txt) > 300:
                                    txt = txt[:300] + '...'
                                lines.append(f"ASSISTANT: {txt}")
                            elif block.get('type') == 'tool_use':
                                lines.append(f"[Used: {block.get('name', '?')}]")
                            elif block.get('type') == 'thinking':
                                lines.append(f"[Thinking: {block.get('thinking', '')[:200]}]")
                elif isinstance(content, str) and content:
                    if len(content) > 300:
                        content = content[:300] + '...'
                    lines.append(f"ASSISTANT: {content}")
        except:
            pass

output = '\n'.join(lines)
if len(output) > MAX_CHARS:
    output = output[:MAX_CHARS] + '\n[...truncated...]'

print(output)
PYEOF
)

FILTERED_SIZE=$(echo "$FILTERED" | wc -c | tr -d ' ')
log "SessionEnd: $SESSION_SHORT — filtered to ${FILTERED_SIZE} chars"

if [ "$FILTERED_SIZE" -lt 100 ]; then
    log "SessionEnd: $SESSION_SHORT — filtered content too short, SKIP"
    rmdir "$LOCK_DIR" 2>/dev/null
    exit 0
fi

# --- Distill via claude -p ---
TEMP_PROMPT=$(mktemp /tmp/brain-sync-prompt.XXXXXX)
cat > "$TEMP_PROMPT" << 'PROMPTEOF'
You distill Claude Code session transcripts into structured knowledge for a personal knowledge base (brain).

Given the transcript below between a USER and an AI assistant (Claude Code), produce a summary.

RULES:
1. Extract only what is factually present in the transcript. Do not hallucinate.
2. Focus on reusable knowledge: technical decisions, gotchas, preferences, patterns discovered.
3. Ignore routine tool usage unless it reveals a key finding.
4. The LEARNINGS section is the most important — these are stored long-term.
5. Keep each bullet under 120 characters. Use English for technical terms, Chinese OK for context.
6. Use the EXACT section headers below. Output ONLY the structured format, no preamble.

OUTPUT FORMAT:

---GOAL---
[One sentence describing the user's main objective]

---ACCOMPLISHED---
- [What was achieved]
- [Or "None"]

---DECISIONS---
- [Technical decision and rationale]
- [Or "None"]

---ERRORS---
- [Error and resolution]
- [Or "None"]

---LEARNINGS---
- [Reusable insight, gotcha, preference, or pattern]
- [Or "None"]

---PROJECT---
[Project slug if focused on one, or "none"]

TRANSCRIPT:
PROMPTEOF

# Append filtered transcript
echo "$FILTERED" >> "$TEMP_PROMPT"

log "SessionEnd: $SESSION_SHORT — running claude -p for distillation..."
# macOS doesn't ship with GNU timeout. Use perl alarm as portable fallback.
if command -v timeout >/dev/null 2>&1; then
    SUMMARY=$(timeout 300 claude -p --model opus --output-format text < "$TEMP_PROMPT" 2>>"$LOG_FILE" || echo "")
else
    SUMMARY=$(perl -e 'alarm 300; exec @ARGV' claude -p --model opus --output-format text < "$TEMP_PROMPT" 2>>"$LOG_FILE" || echo "")
fi

rm -f "$TEMP_PROMPT"

if [ -z "$SUMMARY" ]; then
    log "SessionEnd: $SESSION_SHORT — claude -p returned empty or timed out"
    echo "$FILTERED" > "$ERROR_DIR/${SESSION_SHORT}.filtered.txt"
    rmdir "$LOCK_DIR" 2>/dev/null
    exit 1
fi

# Validate summary has expected headers
if ! echo "$SUMMARY" | grep -q "---GOAL---"; then
    log "SessionEnd: $SESSION_SHORT — claude -p output missing headers, saving raw to errors/"
    echo "$SUMMARY" > "$ERROR_DIR/${SESSION_SHORT}.raw-summary.txt"
    rmdir "$LOCK_DIR" 2>/dev/null
    exit 1
fi

log "SessionEnd: $SESSION_SHORT — distillation complete ($(echo "$SUMMARY" | wc -c | tr -d ' ') chars)"

# --- Parse sections ---
GOAL=$(echo "$SUMMARY" | sed -n '/---GOAL---/,/---ACCOMPLISHED---/p' | grep -v '^---' | head -5)
ACCOMPLISHED=$(echo "$SUMMARY" | sed -n '/---ACCOMPLISHED---/,/---DECISIONS---/p' | grep -v '^---' | head -10)
DECISIONS=$(echo "$SUMMARY" | sed -n '/---DECISIONS---/,/---ERRORS---/p' | grep -v '^---' | head -10)
ERRORS=$(echo "$SUMMARY" | sed -n '/---ERRORS---/,/---LEARNINGS---/p' | grep -v '^---' | head -10)
LEARNINGS=$(echo "$SUMMARY" | sed -n '/---LEARNINGS---/,/---PROJECT---/p' | grep -v '^---' | head -10)
PROJECT=$(echo "$SUMMARY" | sed -n '/---PROJECT---/,$ p' | grep -v '^---' | head -1 | tr -d ' \n')

# --- Determine target layer ---
PROJECT_SLUG=$(echo "$PROJECT" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
[ "$PROJECT_SLUG" = "none" ] || [ -z "$PROJECT_SLUG" ] && PROJECT_SLUG=""

# --- Pull latest brain ---
git -C "$BRAIN_REPO" pull --rebase --quiet origin main 2>/dev/null || true

# --- Write session digest to brain ---
TODAY=$(date +%Y-%m-%d)
SESSION_DIR="$BRAIN_REPO/sessions/$TODAY"
mkdir -p "$SESSION_DIR"
SESSION_FILE="$SESSION_DIR/claude-code-${SESSION_SHORT}.md"

{
    echo "# Session: $TODAY ($SESSION_SHORT)"
    echo ""
    echo "## Goal"
    echo "$GOAL"
    echo ""
    echo "## Accomplished"
    echo "$ACCOMPLISHED"
    echo ""
    echo "## Decisions"
    echo "$DECISIONS"
    echo ""
    echo "## Errors"
    echo "$ERRORS"
    echo ""
    echo "## Learnings"
    echo "$LEARNINGS"
    echo ""
    [ -n "$PROJECT_SLUG" ] && echo "## Project: $PROJECT_SLUG" || echo "## Project: none"
} > "$SESSION_FILE"

log "SessionEnd: $SESSION_SHORT — wrote session digest to brain/sessions/$TODAY/claude-code-${SESSION_SHORT}.md"

# --- Push learnings individually ---
if [ -n "$LEARNINGS" ] && ! echo "$LEARNINGS" | grep -qi "none"; then
    while IFS= read -r line; do
        line=$(echo "$line" | sed 's/^- //' | tr -d '\n')
        [ -z "$line" ] && continue
        [ ${#line} -lt 5 ] && continue

        if [ -n "$PROJECT_SLUG" ]; then
            "$HARNESS_ROOT/scripts/brain-push.sh" --layer project --project "$PROJECT_SLUG" --source claude-code --no-sync "$line" 2>>"$LOG_FILE" || true
        else
            "$HARNESS_ROOT/scripts/brain-push.sh" --layer session --source claude-code --no-sync "$line" 2>>"$LOG_FILE" || true
        fi
    done <<< "$LEARNINGS"
    log "SessionEnd: $SESSION_SHORT — pushed individual learnings"
fi

# --- Commit and push ---
git -C "$BRAIN_REPO" add -A 2>/dev/null
if git -C "$BRAIN_REPO" diff --cached --quiet 2>/dev/null; then
    log "SessionEnd: $SESSION_SHORT — no changes to commit"
else
    git -C "$BRAIN_REPO" commit -m "brain: session $TODAY ($SESSION_SHORT) — auto-distilled" --quiet 2>/dev/null
    if git -C "$BRAIN_REPO" push --quiet origin main 2>>"$LOG_FILE"; then
        log "SessionEnd: $SESSION_SHORT — pushed to origin"
    else
        log "SessionEnd: $SESSION_SHORT — push failed, committed locally"
    fi
fi

# --- Mark synced ---
touch "$SYNCED_DIR/$SESSION_SHORT"

# --- Release lock ---
rmdir "$LOCK_DIR" 2>/dev/null

log "SessionEnd: $SESSION_SHORT — DONE"
