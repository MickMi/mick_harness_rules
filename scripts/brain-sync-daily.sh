#!/bin/bash
set -uo pipefail

# ============================================================
# brain-sync-daily.sh — 3:00 AM batch brain sync
#
# Invoked by launchd at 3:00 AM daily.
#
# Flow:
#   1. Acquire lock (same as brain-sync.sh)
#   2. Find unsynced transcripts from past 48 hours
#   3. For each, run filter + claude -p distillation
#   4. Run brain-compound.sh (daily, +weekly on Sundays)
#   5. Push everything
#   6. Cleanup stale markers, release lock
# ============================================================

# --- Paths ---
HARNESS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Auto-detect: use env var or find most recent Claude Code project dir
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    TRANSCRIPT_DIR="$CLAUDE_PROJECT_DIR"
else
    TRANSCRIPT_DIR=$(ls -dt "$HOME"/.claude/projects/-Users-* 2>/dev/null | head -1 || echo "")
fi
SYNC_STATE="$HOME/.claude/.brain-sync-state"
SYNCED_DIR="$SYNC_STATE/synced"
ERROR_DIR="$SYNC_STATE/errors"
LOCK_DIR="$SYNC_STATE/lock"
LOG_FILE="$HOME/.claude/logs/brain-sync-daily.log"
BRAIN_REPO=""

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"; }

# --- Resolve brain ---
source "$HARNESS_ROOT/scripts/brain-resolve.sh""
resolve_brain_dir "$HARNESS_ROOT"
if [ -n "${BRAIN_REPO_LOCAL:-}" ]; then
    BRAIN_REPO="$BRAIN_REPO_LOCAL"
elif [ -n "${BRAIN_DIR:-}" ]; then
    BRAIN_REPO="$BRAIN_DIR"
else
    BRAIN_REPO="$HOME/.mick-brain"
fi

# --- Lock ---
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    if [ -d "$LOCK_DIR" ]; then
        LOCK_AGE=$(($(date +%s) - $(stat -f %m "$LOCK_DIR" 2>/dev/null || echo 0)))
        if [ "${LOCK_AGE:-0}" -gt 3600 ]; then
            log "Stale lock, removing and re-acquiring"
            rmdir "$LOCK_DIR" 2>/dev/null
            mkdir "$LOCK_DIR" 2>/dev/null || { log "Lock failed, exiting"; exit 0; }
        else
            log "Lock held, exiting"
            exit 0
        fi
    fi
fi

log "=== Daily Brain Sync START ==="

# --- Pull latest brain ---
if [ -d "$BRAIN_REPO/.git" ]; then
    git -C "$BRAIN_REPO" pull --rebase --quiet origin main 2>/dev/null || log "Pull failed (will try push later)"
else
    log "Brain repo not found at $BRAIN_REPO — attempting clone"
    if ! git clone --config http.proxy= --config https.proxy= "$BRAIN_REPO_REMOTE" "$BRAIN_REPO" 2>>"$LOG_FILE"; then
        log "Clone failed, exiting"
        rmdir "$LOCK_DIR" 2>/dev/null
        exit 1
    fi
fi

# --- Find unsynced transcripts ---
CUTOFF=$(date -v-2d +%s 2>/dev/null || echo 0)
PROCESSED=0
MAX_SESSIONS=10

find "$TRANSCRIPT_DIR" -maxdepth 1 -name "*.jsonl" -type f | sort -rn | while read -r f; do
    [ $PROCESSED -ge $MAX_SESSIONS ] && break

    BASENAME=$(basename "$f" .jsonl)
    SESSION_SHORT=$(echo "$BASENAME" | grep -oE '^[0-9a-f]{8}-[0-9a-f]{4}' | head -1)
    [ -z "$SESSION_SHORT" ] && continue

    # Skip if already synced
    [ -f "$SYNCED_DIR/$SESSION_SHORT" ] && continue

    # Skip if too old
    FILE_MTIME=$(stat -f %m "$f" 2>/dev/null || echo 0)
    [ "$FILE_MTIME" -lt "$CUTOFF" ] && continue

    # Check minimum user messages
    USER_COUNT=$(python3 -c "
import json
c = 0
with open('$f') as fh:
    for line in fh:
        try:
            obj = json.loads(line)
            if obj.get('message',{}).get('role') == 'user':
                c += 1
        except: pass
print(c)
" 2>/dev/null || echo "0")
    [ "${USER_COUNT:-0}" -lt 3 ] && continue

    log "Processing: $SESSION_SHORT ($USER_COUNT user msgs)"

    # --- Filter transcript ---
    FILTERED=$(TRANSCRIPT_FILE="$f" python3 << 'PYEOF' 2>/dev/null
import json, os
tf = os.environ.get('TRANSCRIPT_FILE', '')
MAX_CHARS = 30000
lines = []
with open(tf) as fh:
    for line in fh:
        try:
            obj = json.loads(line)
            msg = obj.get('message', {})
            role = msg.get('role', '')
            content = msg.get('content', '')
            if obj.get('type') == 'attachment': continue
            if role == 'user':
                text = content if isinstance(content, str) else ''
                if len(text) > 500: text = text[:500] + '...'
                lines.append(f"USER: {text}")
            elif role == 'assistant':
                if isinstance(content, list):
                    for blk in content:
                        if isinstance(blk, dict):
                            if blk.get('type') == 'text':
                                t = blk.get('text', '')
                                if len(t) > 300: t = t[:300] + '...'
                                lines.append(f"ASSISTANT: {t}")
                            elif blk.get('type') == 'tool_use':
                                lines.append(f"[Used: {blk.get('name','?')}]")
                            elif blk.get('type') == 'thinking':
                                lines.append(f"[Thinking: {blk.get('thinking','')[:200]}]")
                elif isinstance(content, str) and content:
                    if len(content) > 300: content = content[:300] + '...'
                    lines.append(f"ASSISTANT: {content}")
        except: pass
output = '\n'.join(lines)
if len(output) > MAX_CHARS:
    output = output[:MAX_CHARS] + '\n[...truncated...]'
print(output)
PYEOF
)

    if [ -z "$FILTERED" ] || [ $(echo "$FILTERED" | wc -c) -lt 100 ]; then
        log "  $SESSION_SHORT — filtered content too short, SKIP"
        continue
    fi

    # --- Distill ---
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
[One sentence]

---ACCOMPLISHED---
- [Achievement or "None"]

---DECISIONS---
- [Decision or "None"]

---ERRORS---
- [Error or "None"]

---LEARNINGS---
- [Insight, gotcha, or preference or "None"]

---PROJECT---
[project slug or "none"]

TRANSCRIPT:
PROMPTEOF
    echo "$FILTERED" >> "$TEMP_PROMPT"

    SUMMARY=$(timeout 300 claude -p --model opus --output-format text < "$TEMP_PROMPT" 2>/dev/null || echo "")
    rm -f "$TEMP_PROMPT"

    if [ -z "$SUMMARY" ] || ! echo "$SUMMARY" | grep -q "---GOAL---"; then
        log "  $SESSION_SHORT — distillation failed, saving to errors/"
        echo "$FILTERED" > "$ERROR_DIR/${SESSION_SHORT}.filtered.txt"
        [ -n "$SUMMARY" ] && echo "$SUMMARY" > "$ERROR_DIR/${SESSION_SHORT}.raw-summary.txt"
        continue
    fi

    # --- Write to brain ---
    TODAY=$(date +%Y-%m-%d)
    SESSION_DIR="$BRAIN_REPO/sessions/$TODAY"
    mkdir -p "$SESSION_DIR"

    GOAL=$(echo "$SUMMARY" | sed -n '/---GOAL---/,/---ACCOMPLISHED---/p' | grep -v '^---' | head -5)
    LEARNINGS=$(echo "$SUMMARY" | sed -n '/---LEARNINGS---/,/---PROJECT---/p' | grep -v '^---' | head -10)
    PROJECT=$(echo "$SUMMARY" | sed -n '/---PROJECT---/,$ p' | grep -v '^---' | head -1 | tr -d ' \n')

    {
        echo "# Session: $TODAY ($SESSION_SHORT)"
        echo ""
        echo "## Goal"
        echo "$GOAL"
        echo ""
        echo "## Learnings"
        echo "$LEARNINGS"
        [ -n "$PROJECT" ] && [ "$PROJECT" != "none" ] && echo "" && echo "## Project: $PROJECT"
    } > "$SESSION_DIR/claude-code-${SESSION_SHORT}.md"

    log "  $SESSION_SHORT — distilled to brain"

    # --- Push learnings ---
    PROJECT_SLUG=$(echo "$PROJECT" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    [ "$PROJECT_SLUG" = "none" ] && PROJECT_SLUG=""

    if [ -n "$LEARNINGS" ] && ! echo "$LEARNINGS" | grep -qi "none"; then
        while IFS= read -r line; do
            line=$(echo "$line" | sed 's/^- //' | tr -d '\n')
            [ -z "$line" ] && continue
            [ ${#line} -lt 5 ] && continue
            if [ -n "$PROJECT_SLUG" ]; then
                "$HARNESS_ROOT/scripts/brain-push.sh" --layer project --project "$PROJECT_SLUG" --source claude-code --no-sync "$line" 2>/dev/null || true
            else
                "$HARNESS_ROOT/scripts/brain-push.sh" --layer session --source claude-code --no-sync "$line" 2>/dev/null || true
            fi
        done <<< "$LEARNINGS"
    fi

    touch "$SYNCED_DIR/$SESSION_SHORT"
    PROCESSED=$((PROCESSED + 1))
    log "  $SESSION_SHORT — DONE ($PROCESSED/$MAX_SESSIONS)"

    # Small delay between API calls
    sleep 5
done

# --- Run brain-compound ---
log "Running brain-compound..."
"$HARNESS_ROOT/scripts/brain-compound.sh" --daily 2>>"$LOG_FILE" || log "brain-compound --daily had errors"

# Sunday: also run weekly
if [ "$(date +%u)" = "7" ]; then
    log "Sunday: running brain-compound --weekly"
    "$HARNESS_ROOT/scripts/brain-compound.sh" --weekly 2>>"$LOG_FILE" || log "brain-compound --weekly had errors"
fi

# --- Final push ---
git -C "$BRAIN_REPO" add -A 2>/dev/null
if ! git -C "$BRAIN_REPO" diff --cached --quiet 2>/dev/null; then
    git -C "$BRAIN_REPO" commit -m "brain: daily sync $(date +%Y-%m-%d)" --quiet 2>/dev/null
    git -C "$BRAIN_REPO" push --quiet origin main 2>>"$LOG_FILE" && log "Pushed to origin" || log "Push failed"
fi

# --- Cleanup stale markers ---
find "$SYNCED_DIR" -type f -mtime +90 -delete 2>/dev/null
find "$ERROR_DIR" -type f -mtime +30 -delete 2>/dev/null

# --- Release lock ---
rmdir "$LOCK_DIR" 2>/dev/null

log "=== Daily Brain Sync END ($PROCESSED sessions processed) ==="
