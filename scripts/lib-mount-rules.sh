#!/bin/bash
# ============================================================
# scripts/lib-mount-rules.sh — Shared rule-mounting logic (sourced, not executed)
#
# Single source of truth for how generated rule files get mounted into a
# target project. Sourced by setup.sh, bin/harness, and brain-init.sh so the
# entry points never drift.
#
# Exposes:
#   regenerate_rules <HARNESS_ROOT> [single|all]
#       Runs generate.sh to (re)build dist/ from rules/core.md + extended.md.
#
#   mount_rule_files <HARNESS_ROOT> <TARGET_DIR> [single|all]
#       Default mode symlinks/injects only AGENTS.md. all mode adds legacy
#       tool-specific entry files and .prompts/. Populates the global array
#       HARNESS_OWNED_FILES with the project-relative paths it owns, so the
#       caller can add exactly those (and no project-owned files) to .gitignore.
#
# Requires color helpers info/ok/warn/fail to be defined by the caller.
# ============================================================

# project-root-relative | dist-relative
HARNESS_DEFAULT_RULE_LINKS=(
    "AGENTS.md|AGENTS.md"
)

HARNESS_COMPAT_RULE_LINKS=(
    "CLAUDE.md|CLAUDE.md"
    ".cursorrules|.cursorrules"
    ".windsurfrules|.windsurfrules"
    ".clinerules|.clinerules"
    ".github/copilot-instructions.md|.github/copilot-instructions.md"
    ".trae/rules.md|.trae/rules.md"
)

regenerate_rules() {
    local harness_root="$1"
    local mode="${2:-single}"
    local generate="$harness_root/generate.sh"

    if [ -x "$generate" ]; then
        if { [ "$mode" = "all" ] && "$generate" --all >/dev/null; } || { [ "$mode" != "all" ] && "$generate" >/dev/null; }; then
            if [ "$mode" = "all" ]; then
                ok "Rule files generated into .harness/dist/ (compatibility entries enabled)."
            else
                ok "Rule file generated into .harness/dist/AGENTS.md."
            fi
        else
            warn "generate.sh failed — using whatever already exists in dist/."
        fi
    else
        warn "generate.sh not found or not executable. Skipping generation."
    fi
}

# --- Marker-based injection for files that already exist ---
# When a project has its own CLAUDE.md / .cursorrules / etc., we can't symlink.
# Instead, we inject harness content at the top inside marker comments, and
# leave the project's own content untouched below.
HARNESS_MARKER_BEGIN="<!-- HARNESS:BEGIN — auto-injected by .harness, do not edit this block -->"
HARNESS_MARKER_END="<!-- HARNESS:END -->"

# Inject or update the harness block at the top of an existing file.
# Idempotent: if markers already exist, replaces the block; otherwise prepends.
#   $1 = target file path (must exist)
#   $2 = harness content file (dist/ source)
inject_harness_block() {
    local target="$1" source="$2"

    # Build the injection block into a temp file
    local block
    block="$(mktemp)"
    {
        echo "$HARNESS_MARKER_BEGIN"
        echo ""
        cat "$source"
        echo ""
        echo "$HARNESS_MARKER_END"
    } > "$block"

    if grep -qF "HARNESS:BEGIN" "$target" 2>/dev/null; then
        # Markers exist → strip old block, prepend new one (idempotent update).
        # awk: skip lines inside markers, then trim leading blank lines from remainder.
        local stripped
        stripped="$(mktemp)"
        awk -v begin="HARNESS:BEGIN" -v end="HARNESS:END" '
            index($0, begin) { skip=1; next }
            index($0, end)   { skip=0; next }
            !skip { print }
        ' "$target" | sed '/./,$!d' > "$stripped"

        {
            cat "$block"
            echo ""
            cat "$stripped"
        } > "$target"
        rm -f "$stripped"
    else
        # No markers yet → prepend block, then original content
        local original
        original="$(mktemp)"
        cp "$target" "$original"
        {
            cat "$block"
            echo ""
            cat "$original"
        } > "$target"
        rm -f "$original"
    fi
    rm -f "$block"
}

strip_harness_block() {
    local target="$1"

    if ! grep -qF "HARNESS:BEGIN" "$target" 2>/dev/null; then
        return 1
    fi

    local stripped
    stripped="$(mktemp)"
    awk -v begin="HARNESS:BEGIN" -v end="HARNESS:END" '
        index($0, begin) { skip=1; next }
        index($0, end)   { skip=0; next }
        !skip { print }
    ' "$target" | sed '/./,$!d' > "$stripped"

    mv "$stripped" "$target"
    return 0
}

resolve_mount_link() {
    local link_path="$1"
    local raw_target
    raw_target="$(readlink "$link_path")"
    if [[ "$raw_target" = /* ]]; then
        echo "$raw_target"
    else
        echo "$(cd "$(dirname "$link_path")" && pwd)/$raw_target"
    fi
}

is_active_rule_link() {
    local wanted="$1"
    shift
    local entry proj_rel dist_rel
    for entry in "$@"; do
        IFS='|' read -r proj_rel dist_rel <<< "$entry"
        if [ "$wanted" = "$proj_rel" ]; then
            return 0
        fi
    done
    return 1
}

cleanup_inactive_rule_mounts() {
    local harness_root="$1"
    local target_dir="$2"
    shift 2

    local all_links=("${HARNESS_DEFAULT_RULE_LINKS[@]}" "${HARNESS_COMPAT_RULE_LINKS[@]}")
    local entry proj_rel dist_rel link resolved

    for entry in "${all_links[@]}"; do
        IFS='|' read -r proj_rel dist_rel <<< "$entry"
        if is_active_rule_link "$proj_rel" "$@"; then
            continue
        fi

        link="$target_dir/$proj_rel"
        if [ -L "$link" ]; then
            resolved="$(resolve_mount_link "$link")"
            if [[ "$resolved" = "$harness_root/dist/"* ]]; then
                rm "$link"
                ok "$proj_rel stale harness symlink removed."
            fi
        elif [ -f "$link" ]; then
            if strip_harness_block "$link"; then
                ok "$proj_rel stale harness injection removed."
            fi
        fi
    done

    local prompts_link="$target_dir/.prompts"
    if [ -L "$prompts_link" ]; then
        resolved="$(resolve_mount_link "$prompts_link")"
        if [ "$resolved" = "$harness_root/rules/roles" ]; then
            rm "$prompts_link"
            ok ".prompts/ stale harness symlink removed."
        fi
    fi
}

# Populated by mount_rule_files. Caller reads this after the call.
HARNESS_OWNED_FILES=()

mount_rule_files() {
    local harness_root="$1"
    local target_dir="$2"
    local mode="${3:-single}"
    HARNESS_OWNED_FILES=()

    local active_links=("${HARNESS_DEFAULT_RULE_LINKS[@]}")
    if [ "$mode" = "all" ]; then
        active_links+=("${HARNESS_COMPAT_RULE_LINKS[@]}")
    fi

    cleanup_inactive_rule_mounts "$harness_root" "$target_dir" "${active_links[@]}"

    local entry proj_rel dist_rel link src
    for entry in "${active_links[@]}"; do
        IFS='|' read -r proj_rel dist_rel <<< "$entry"
        link="$target_dir/$proj_rel"
        src="$harness_root/dist/$dist_rel"

        if [ ! -f "$src" ]; then
            warn "$proj_rel: generated source missing ($src). Skipping."
            continue
        fi
        mkdir -p "$(dirname "$link")"
        if [ -L "$link" ]; then
            # Already a symlink (pure harness-owned) — nothing to do
            ok "$proj_rel symlink already exists. (idempotent)"
            HARNESS_OWNED_FILES+=("$proj_rel")
        elif [ -e "$link" ]; then
            # Project has its own file → inject harness block at top
            inject_harness_block "$link" "$src"
            ok "$proj_rel: harness rules injected into existing project file."
        else
            # No file exists → clean symlink
            ln -s "$src" "$link"
            ok "$proj_rel → .harness/dist/$dist_rel"
            HARNESS_OWNED_FILES+=("$proj_rel")
        fi
    done

    if [ "$mode" != "all" ]; then
        return 0
    fi

    # Agent role templates: project .prompts/ → .harness/rules/roles/ (compat mode)
    local prompts_link="$target_dir/.prompts"
    if [ -L "$prompts_link" ]; then
        ok ".prompts/ symlink already exists. (idempotent)"
        HARNESS_OWNED_FILES+=(".prompts")
        HARNESS_OWNED_FILES+=(".prompts/")
    elif [ -d "$prompts_link" ]; then
        warn ".prompts/ already exists as a real directory. Keeping project's own version."
    else
        ln -s "$harness_root/rules/roles" "$prompts_link"
        ok ".prompts/ → .harness/rules/roles/"
        HARNESS_OWNED_FILES+=(".prompts")
        HARNESS_OWNED_FILES+=(".prompts/")
    fi
}
