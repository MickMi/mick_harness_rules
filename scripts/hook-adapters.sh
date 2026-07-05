#!/bin/bash
set -euo pipefail

# ============================================================
# hook-adapters.sh — Optional automation adapters for Brain hooks
#
# External command surface stays small: harness brain install/status.
# This file owns tool-specific hook setup behind that stable interface.
# ============================================================

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck disable=SC1091
source "$HARNESS_ROOT/scripts/brain-resolve.sh"

HOOK_CONFIG="$HARNESS_ROOT/config/.brain-config.yaml"

hook_adapter_enabled() {
    local adapter="$1"
    local default_value="${2:-false}"

    [ -f "$HOOK_CONFIG" ] || { echo "$default_value"; return 0; }

    awk -v adapter="$adapter" -v default_value="$default_value" '
        $0 ~ "^[[:space:]]{2}" adapter ":" { in_adapter=1; next }
        in_adapter && $0 ~ "^[[:space:]]{2}[A-Za-z0-9_-]+:" { in_adapter=0 }
        in_adapter && $1 == "enabled:" { print $2; found=1; exit }
        END { if (!found) print default_value }
    ' "$HOOK_CONFIG" | tr -d '"'
}

iter_claude_hook_commands() {
    local hook_file="$1"
    python3 <<'PY' "$hook_file" 2>/dev/null || true
import json, sys, os
path = sys.argv[1]
if not os.path.exists(path):
    sys.exit(0)
with open(path) as fh:
    data = json.load(fh)
hooks = data.get("hooks", {})
if isinstance(hooks, dict):
    entries = hooks.get("SessionEnd", [])
elif isinstance(hooks, list):
    entries = hooks
else:
    entries = []
if not isinstance(entries, list):
    entries = []
for entry in entries:
    if not isinstance(entry, dict):
        continue
    if entry.get("command"):
        print(entry["command"])
    for sub in entry.get("hooks", []):
        if isinstance(sub, dict) and sub.get("command"):
            print(sub["command"])
PY
}

claude_hook_status() {
    local hook_file="$HOME/.claude/settings.json"
    local brain_sync_path="$HARNESS_ROOT/scripts/brain-sync.sh"

    if [ ! -f "$hook_file" ]; then
        echo "missing"
        return 0
    fi

    if iter_claude_hook_commands "$hook_file" | grep -qxF "$brain_sync_path"; then
        echo "installed"
    elif iter_claude_hook_commands "$hook_file" | grep -q "brain-sync"; then
        echo "other"
    else
        echo "missing"
    fi
}

install_claude_code_hook() {
    local hook_file="$HOME/.claude/settings.json"
    local brain_sync_path="$HARNESS_ROOT/scripts/brain-sync.sh"

    mkdir -p "$(dirname "$hook_file")"

    HOOK_FILE="$hook_file" BRAIN_SYNC_PATH="$brain_sync_path" python3 <<'PY'
import json, os

path = os.environ["HOOK_FILE"]
brain_sync = os.environ["BRAIN_SYNC_PATH"]

data = {}
if os.path.exists(path) and os.path.getsize(path) > 0:
    with open(path) as fh:
        try:
            data = json.load(fh)
        except Exception:
            data = {}

raw_hooks = data.get("hooks", {})
if isinstance(raw_hooks, dict):
    hooks = raw_hooks
    session_end = hooks.get("SessionEnd", [])
elif isinstance(raw_hooks, list):
    hooks = {}
    session_end = raw_hooks
else:
    hooks = {}
    session_end = []

if not isinstance(session_end, list):
    session_end = []

def has_command(entry, command):
    if not isinstance(entry, dict):
        return False
    if entry.get("command") == command:
        return True
    for sub in entry.get("hooks", []):
        if isinstance(sub, dict) and sub.get("command") == command:
            return True
    return False

if not any(has_command(entry, brain_sync) for entry in session_end):
    session_end.append({
        "hooks": [{
            "type": "command",
            "command": brain_sync,
            "description": "Auto-distill session learnings to Brain"
        }]
    })

hooks["SessionEnd"] = session_end
data["hooks"] = hooks

with open(path, "w") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
PY
}

install_daily_sync() {
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist="$plist_dir/com.mick.brain-daily-distill.plist"
    mkdir -p "$plist_dir" "$HOME/.claude/logs"

    launchctl bootout "gui/$(id -u)" "$plist" 2>/dev/null || launchctl unload "$plist" 2>/dev/null || true

    cat > "$plist" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mick.brain-daily-distill</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HARNESS_ROOT/scripts/brain-sync-daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>7</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$HOME/.claude/logs/brain-sync-daily.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.claude/logs/brain-sync-daily.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLISTEOF

    launchctl bootstrap "gui/$(id -u)" "$plist" 2>/dev/null || launchctl load "$plist" 2>/dev/null || true
}

daily_sync_status() {
    local plist="$HOME/Library/LaunchAgents/com.mick.brain-daily-distill.plist"
    [ -f "$plist" ] || { echo "missing"; return 0; }
    if launchctl print "gui/$(id -u)/com.mick.brain-daily-distill" >/dev/null 2>&1; then
        echo "loaded"
    elif launchctl list 2>/dev/null | grep -q "com.mick.brain-daily-distill"; then
        echo "loaded"
    else
        echo "written"
    fi
}

install_inbox_adapter() {
    local adapter="$1"
    local inbox="$BRAIN_DIR/inbox/$adapter"
    mkdir -p "$inbox"
    cat > "$inbox/README.md" <<EOF
# $adapter Brain Inbox

Tools that support custom hooks can call:

\`\`\`bash
bash $HARNESS_ROOT/scripts/brain-ingest.sh --source $adapter --kind session --file <summary.md>
\`\`\`

For failure signals:

\`\`\`bash
printf '%s\n' "failure summary" | bash $HARNESS_ROOT/scripts/brain-ingest.sh --source $adapter --kind failure
\`\`\`
EOF
}

hook_adapters_install() {
    ensure_brain_available "$HARNESS_ROOT" >/dev/null 2>&1 || true

    local claude_enabled codex_enabled generic_enabled
    claude_enabled="$(hook_adapter_enabled claude_code true)"
    codex_enabled="$(hook_adapter_enabled codex false)"
    generic_enabled="$(hook_adapter_enabled generic false)"

    if [ "$claude_enabled" = "true" ]; then
        install_claude_code_hook
        install_daily_sync
    fi
    [ "$codex_enabled" = "true" ] && install_inbox_adapter "codex"
    [ "$generic_enabled" = "true" ] && install_inbox_adapter "generic"
    return 0
}

hook_adapters_status() {
    resolve_brain_dir "$HARNESS_ROOT"

    echo "  Hook adapters:"
    local claude_enabled codex_enabled generic_enabled
    claude_enabled="$(hook_adapter_enabled claude_code true)"
    codex_enabled="$(hook_adapter_enabled codex false)"
    generic_enabled="$(hook_adapter_enabled generic false)"

    if [ "$claude_enabled" = "true" ]; then
        echo "    Claude Code : enabled ($(claude_hook_status))"
    else
        echo "    Claude Code : disabled"
    fi

    if [ "$codex_enabled" = "true" ]; then
        echo "    Codex       : enabled (inbox: $BRAIN_DIR/inbox/codex)"
    else
        echo "    Codex       : disabled"
    fi

    if [ "$generic_enabled" = "true" ]; then
        echo "    Generic     : enabled (inbox: $BRAIN_DIR/inbox/generic)"
    else
        echo "    Generic     : disabled"
    fi

    echo "    Daily sync  : $(daily_sync_status)"
}
