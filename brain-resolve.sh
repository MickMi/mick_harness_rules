#!/bin/bash
# ============================================================
# brain-resolve.sh — Resolve brain data directory path
#
# Shared utility sourced by all brain-*.sh scripts.
# Determines where brain data lives:
#   1. External brain repo (dual-repo model) — preferred
#   2. Local brain/ directory (fallback for backward compatibility)
#
# After sourcing, the following variables are available:
#   BRAIN_DIR       — absolute path to the brain data root
#   BRAIN_IS_EXTERNAL — "true" if using external brain repo
#   BRAIN_REPO_LOCAL — local clone path of brain repo (if external)
#   BRAIN_REPO_REMOTE — remote URL of brain repo (if configured)
# ============================================================

# Prevent double-sourcing
if [ -n "$BRAIN_RESOLVE_LOADED" ]; then
    return 0 2>/dev/null || true
fi
BRAIN_RESOLVE_LOADED=true

# --- Resolve brain repo configuration from .brain-config.yaml ---
resolve_brain_dir() {
    local harness_root="$1"
    local config_file="$harness_root/.brain-config.yaml"

    BRAIN_IS_EXTERNAL="false"
    BRAIN_REPO_LOCAL=""
    BRAIN_REPO_REMOTE=""

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
        BRAIN_REPO_LOCAL="$HOME/.mick-brain"
    fi

    # Check if external brain repo exists (must have .git directory)
    if [ -n "$BRAIN_REPO_REMOTE" ] && [ -d "$BRAIN_REPO_LOCAL/.git" ]; then
        BRAIN_DIR="$BRAIN_REPO_LOCAL"
        BRAIN_IS_EXTERNAL="true"
    elif [ -d "$harness_root/brain" ]; then
        # Fallback to local brain/ directory
        BRAIN_DIR="$harness_root/brain"
        BRAIN_IS_EXTERNAL="false"
    else
        # No brain directory found
        BRAIN_DIR="$harness_root/brain"
        BRAIN_IS_EXTERNAL="false"
    fi
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
        return 0
    else
        # Clone failed — likely an empty repo. Initialize locally and set remote.
        echo "Remote appears to be empty. Initializing local brain repo..."
        mkdir -p "$BRAIN_REPO_LOCAL"
        git -C "$BRAIN_REPO_LOCAL" init --quiet 2>/dev/null
        git -C "$BRAIN_REPO_LOCAL" remote add origin "$BRAIN_REPO_REMOTE" 2>/dev/null || true
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
        # Fallback: commit in harness repo
        local harness_root
        harness_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        cd "$harness_root"
        if [ -d ".git" ]; then
            git add brain/ 2>/dev/null
            git commit -m "$commit_msg" --quiet 2>/dev/null || true
            if [ "$no_sync" = false ]; then
                if git remote get-url origin &>/dev/null; then
                    git push --quiet 2>/dev/null && return 0 || return 1
                fi
            fi
        fi
    fi
    return 0
}
