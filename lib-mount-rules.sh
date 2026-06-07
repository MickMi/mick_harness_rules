#!/bin/bash
# ============================================================
# lib-mount-rules.sh — Shared rule-mounting logic (sourced, not executed)
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
        if "$generate" >/dev/null; then
            ok "Rule files generated into .harness/dist/ (single source)."
        else
            warn "generate.sh failed — using whatever already exists in dist/."
        fi
    else
        warn "generate.sh not found or not executable. Skipping generation."
    fi
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
            ok "$proj_rel symlink already exists. (idempotent)"
            HARNESS_OWNED_FILES+=("$proj_rel")
        elif [ -e "$link" ]; then
            warn "$proj_rel already exists as a real file. Keeping project's own version."
            warn "  (To use harness rules, remove it and re-run setup.)"
        else
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
