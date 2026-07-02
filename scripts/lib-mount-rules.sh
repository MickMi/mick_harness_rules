#!/bin/bash
# ============================================================
# scripts/lib-mount-rules.sh — Shared rule-mounting logic (sourced, not executed)
#
# Single source of truth for how generated rule files get mounted into a
# target project. Sourced by both setup.sh (clone-in-place mode) and
# brain-init.sh (global-symlink mode) so the two entry points never drift.
#
# Exposes:
#   regenerate_rules <HARNESS_ROOT>
#       Runs generate.sh to (re)build dist/ from rules/core.md + extended.md.
#
#   mount_rule_files <HARNESS_ROOT> <TARGET_DIR>
#       Symlinks every generated rule file into the target project root and
#       projects rules/roles/ as .prompts/. Populates the global array
#       HARNESS_OWNED_FILES with the project-relative paths it owns, so the
#       caller can add exactly those (and no project-owned files) to .gitignore.
#
# Requires color helpers info/ok/warn/fail to be defined by the caller.
# ============================================================

# project-root-relative | dist-relative
HARNESS_RULE_LINKS=(
    "AGENTS.md|AGENTS.md"
    "CLAUDE.md|CLAUDE.md"
    ".cursorrules|.cursorrules"
    ".windsurfrules|.windsurfrules"
    ".clinerules|.clinerules"
    ".github/copilot-instructions.md|.github/copilot-instructions.md"
    ".trae/rules.md|.trae/rules.md"
)

regenerate_rules() {
    local harness_root="$1"
    local generate="$harness_root/generate.sh"
    if [ -x "$generate" ]; then
        if "$generate" --all >/dev/null; then
            ok "Rule files generated into .harness/dist/ (single source)."
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

# Populated by mount_rule_files. Caller reads this after the call.
HARNESS_OWNED_FILES=()

mount_rule_files() {
    local harness_root="$1"
    local target_dir="$2"
    HARNESS_OWNED_FILES=()

    local entry proj_rel dist_rel link src
    for entry in "${HARNESS_RULE_LINKS[@]}"; do
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

    # Agent role templates: project .prompts/ → .harness/rules/roles/ (back-compat)
    local prompts_link="$target_dir/.prompts"
    if [ -L "$prompts_link" ]; then
        ok ".prompts/ symlink already exists. (idempotent)"
    elif [ -d "$prompts_link" ]; then
        warn ".prompts/ already exists as a real directory. Keeping project's own version."
    else
        ln -s "$harness_root/rules/roles" "$prompts_link"
        ok ".prompts/ → .harness/rules/roles/"
    fi
}
