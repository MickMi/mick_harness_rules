#!/bin/bash
# ============================================================
# brain-resolve.sh — Resolve brain data directory path
#
# Shared utility sourced by all brain-*.sh scripts.
# Determines where brain data lives:
#   1. External brain repo (dual-repo model) — preferred
#   2. ~/.brain local repo (private local fallback)
#   3. Existing ~/.mick-brain repo (legacy compatibility only)
#   4. Local harness/brain directory (legacy fallback only)
#
# After sourcing, the following variables are available:
#   BRAIN_DIR       — absolute path to the brain data root
#   BRAIN_IS_EXTERNAL — "true" if using a configured external brain repo
#   BRAIN_REMOTE_STATUS — connected | local | unavailable | none
#   BRAIN_REPO_LOCAL — local clone path of brain repo (if external)
#   BRAIN_REPO_REMOTE — remote URL of brain repo (if configured)
# ============================================================

# Prevent double-sourcing (guard against set -u: default to empty if unset)
if [ -n "${BRAIN_RESOLVE_LOADED:-}" ]; then
    return 0 2>/dev/null || true
fi
BRAIN_RESOLVE_LOADED=true

# --- Resolve brain repo configuration from .brain-config.yaml ---
resolve_brain_dir() {
    local harness_root="$1"
    local config_file="$harness_root/config/.brain-config.yaml"

    BRAIN_IS_EXTERNAL="false"
    BRAIN_REMOTE_STATUS="none"
    BRAIN_REPO_LOCAL=""
    BRAIN_REPO_REMOTE=""
    BRAIN_USING_LEGACY_PATH="false"

    if [ -f "$config_file" ]; then
        # Parse brain_repo.remote
        BRAIN_REPO_REMOTE=$(grep '^\s*remote:' "$config_file" 2>/dev/null | head -1 | sed 's/^[^"]*"//;s/"[^"]*$//' | tr -d ' ')
        # Parse brain_repo.local_path
        BRAIN_REPO_LOCAL=$(grep '^\s*local_path:' "$config_file" 2>/dev/null | head -1 | sed 's/^[^"]*"//;s/"[^"]*$//' | tr -d ' ')
    fi

    # Expand ~ to $HOME
    BRAIN_REPO_LOCAL="${BRAIN_REPO_LOCAL/#\~/$HOME}"

    # Default local path
    if [ -z "$BRAIN_REPO_LOCAL" ]; then
        BRAIN_REPO_LOCAL="$HOME/.brain"
    fi

    # v0.20.2 changed the public default to ~/.brain. Existing installations
    # continue to use the legacy directory when it already contains data and
    # the new default has not been created yet.
    if [ "$BRAIN_REPO_LOCAL" = "$HOME/.brain" ] \
        && [ ! -e "$HOME/.brain" ] \
        && [ -d "$HOME/.mick-brain" ]; then
        BRAIN_REPO_LOCAL="$HOME/.mick-brain"
        BRAIN_USING_LEGACY_PATH="true"
    fi

    # Prefer the configured/private brain path when it already exists.
    # Remote connectivity is tracked separately so a local-only brain does not
    # block the Harness main flow.
    if [ -d "$BRAIN_REPO_LOCAL/.git" ]; then
        BRAIN_DIR="$BRAIN_REPO_LOCAL"
        if [ -n "$BRAIN_REPO_REMOTE" ] && git -C "$BRAIN_REPO_LOCAL" remote get-url origin >/dev/null 2>&1; then
            BRAIN_IS_EXTERNAL="true"
            BRAIN_REMOTE_STATUS="connected"
        else
            BRAIN_IS_EXTERNAL="false"
            BRAIN_REMOTE_STATUS="local"
        fi
    elif [ -z "$BRAIN_REPO_REMOTE" ] && [ -d "$harness_root/brain" ]; then
        # Legacy fallback for older installs that stored brain/ inside Harness.
        BRAIN_DIR="$harness_root/brain"
        BRAIN_IS_EXTERNAL="false"
        BRAIN_REMOTE_STATUS="local"
    else
        # No brain exists yet. Point to the private local path; callers that
        # need a usable Brain should call ensure_brain_available.
        BRAIN_DIR="$BRAIN_REPO_LOCAL"
        BRAIN_IS_EXTERNAL="false"
        if [ -n "$BRAIN_REPO_REMOTE" ]; then
            BRAIN_REMOTE_STATUS="unavailable"
        else
            BRAIN_REMOTE_STATUS="none"
        fi
    fi
}

# Brain identity comes from the private Brain repository itself. The public
# Harness repository is shared by every user and is never an identity source.
brain_remote_url() {
    local brain_dir="${1:-${BRAIN_DIR:-}}"
    local remote_url=""

    if [ -n "$brain_dir" ] && [ -d "$brain_dir/.git" ]; then
        remote_url=$(git -C "$brain_dir" remote get-url origin 2>/dev/null || true)
    fi
    [ -n "$remote_url" ] || remote_url="${BRAIN_REPO_REMOTE:-}"
    printf '%s\n' "$remote_url"
}

brain_remote_owner() {
    local remote_url=""
    remote_url=$(brain_remote_url "${1:-${BRAIN_DIR:-}}")

    case "$remote_url" in
        http://*|https://*)
            printf '%s\n' "$remote_url" | sed -E 's|https?://[^/]+/([^/]+)/.*|\1|'
            ;;
        git@*:*)
            printf '%s\n' "$remote_url" | sed -E 's|git@[^:]+:([^/]+)/.*|\1|'
            ;;
        *)
            printf '\n'
            ;;
    esac
}

brain_remote_repo() {
    local remote_url=""
    remote_url=$(brain_remote_url "${1:-${BRAIN_DIR:-}}")

    if [ -z "$remote_url" ]; then
        printf 'local\n'
        return
    fi
    remote_url="${remote_url%/}"
    remote_url="${remote_url%.git}"
    printf '%s\n' "${remote_url##*/}"
}

init_brain_skeleton() {
    local brain_dir="$1"

    mkdir -p \
        "$brain_dir/global/evolution" \
        "$brain_dir/projects" \
        "$brain_dir/sessions" \
        "$brain_dir/inbox/codex" \
        "$brain_dir/inbox/generic"

    [ -f "$brain_dir/global/preferences.md" ] || cat > "$brain_dir/global/preferences.md" <<'EOF'
# Global Preferences

Record cross-project user preferences here.
EOF

    [ -f "$brain_dir/global/gotchas.md" ] || cat > "$brain_dir/global/gotchas.md" <<'EOF'
# Global Gotchas

Record cross-project pitfalls here.
EOF

    [ -f "$brain_dir/MEMORY.md" ] || cat > "$brain_dir/MEMORY.md" <<'EOF'
# Brain Memory

Private long-term memory for Agent collaboration.
EOF

    touch \
        "$brain_dir/global/evolution/audit-trail.md" \
        "$brain_dir/global/evolution/harness-failures.md" \
        "$brain_dir/global/evolution/corrections.md" \
        "$brain_dir/global/evolution/banned-patterns.md" \
        "$brain_dir/projects/.gitkeep" \
        "$brain_dir/sessions/.gitkeep" \
        "$brain_dir/inbox/codex/.gitkeep" \
        "$brain_dir/inbox/generic/.gitkeep"
}

ensure_brain_available() {
    local harness_root="$1"

    resolve_brain_dir "$harness_root"

    if [ -d "$BRAIN_DIR" ]; then
        init_brain_skeleton "$BRAIN_DIR"
        if [ ! -d "$BRAIN_DIR/.git" ]; then
            git -C "$BRAIN_DIR" init --quiet 2>/dev/null || true
        fi
        resolve_brain_dir "$harness_root"
        return 0
    fi

    if [ -n "$BRAIN_REPO_REMOTE" ] && command -v git >/dev/null 2>&1; then
        if git clone --quiet "$BRAIN_REPO_REMOTE" "$BRAIN_REPO_LOCAL" 2>/dev/null; then
            BRAIN_DIR="$BRAIN_REPO_LOCAL"
            init_brain_skeleton "$BRAIN_DIR"
            resolve_brain_dir "$harness_root"
            return 0
        fi
    fi

    mkdir -p "$BRAIN_REPO_LOCAL"
    git -C "$BRAIN_REPO_LOCAL" init --quiet 2>/dev/null || true
    BRAIN_DIR="$BRAIN_REPO_LOCAL"
    BRAIN_IS_EXTERNAL="false"
    if [ -n "$BRAIN_REPO_REMOTE" ]; then
        BRAIN_REMOTE_STATUS="unavailable"
    else
        BRAIN_REMOTE_STATUS="local"
    fi
    init_brain_skeleton "$BRAIN_DIR"
    return 0
}

# --- Clone brain repo if not present ---
clone_brain_repo() {
    local harness_root="$1"

    # Re-resolve to get config
    resolve_brain_dir "$harness_root"

    if [ -z "$BRAIN_REPO_REMOTE" ]; then
        return 1  # No remote configured
    fi

    if [ -d "$BRAIN_REPO_LOCAL/.git" ]; then
        return 0  # Already cloned
    fi

    echo "Cloning brain repo: $BRAIN_REPO_REMOTE → $BRAIN_REPO_LOCAL"
    if git clone "$BRAIN_REPO_REMOTE" "$BRAIN_REPO_LOCAL" 2>/dev/null; then
        # Clone succeeded
        init_brain_skeleton "$BRAIN_REPO_LOCAL"
        return 0
    else
        # Clone failed. Do not block Harness; create a private local Brain.
        echo "Brain remote is unavailable. Initializing local brain repo..."
        mkdir -p "$BRAIN_REPO_LOCAL"
        git -C "$BRAIN_REPO_LOCAL" init --quiet 2>/dev/null
        init_brain_skeleton "$BRAIN_REPO_LOCAL"
        return 0
    fi
}

# --- Sync brain repo (pull latest) ---
sync_brain_repo() {
    if [ "$BRAIN_IS_EXTERNAL" = "true" ] && [ -d "$BRAIN_REPO_LOCAL/.git" ]; then
        git -C "$BRAIN_REPO_LOCAL" pull --rebase --autostash --quiet 2>/dev/null || true
    fi
}

# --- Commit and push changes in brain repo ---
commit_brain_changes() {
    local commit_msg="$1"
    local no_sync="${2:-false}"

    if [ "$BRAIN_IS_EXTERNAL" = "true" ] && [ -d "$BRAIN_REPO_LOCAL/.git" ]; then
        cd "$BRAIN_REPO_LOCAL"
        git add -A 2>/dev/null
        git commit -m "$commit_msg" --quiet 2>/dev/null || true

        if [ "$no_sync" = false ]; then
            if git remote get-url origin &>/dev/null; then
                git push --quiet 2>/dev/null && return 0 || return 1
            fi
        fi
    else
        if [ -d "$BRAIN_DIR/.git" ]; then
            cd "$BRAIN_DIR"
            git add -A 2>/dev/null
            git commit -m "$commit_msg" --quiet 2>/dev/null || true
            if [ "$no_sync" = false ] && git remote get-url origin &>/dev/null; then
                git push --quiet 2>/dev/null && return 0 || return 1
            fi
        else
            # Last legacy fallback: commit harness/brain if it exists.
            local harness_root
            harness_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
            cd "$harness_root"
            if [ -d ".git" ] && [ -d "brain" ]; then
                git add brain/ 2>/dev/null
                git commit -m "$commit_msg" --quiet 2>/dev/null || true
                if git remote get-url origin &>/dev/null; then
                    git push --quiet 2>/dev/null && return 0 || return 1
                fi
            fi
        fi
    fi
    return 0
}
