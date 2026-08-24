---
name: harness-plan
description: Scan a Harness project and safely preview or establish its plan archive through the deterministic Harness CLI. Use when the user explicitly asks for the Harness plan command or wants current project facts turned into plan.md without overriding the host's native planning command.
---

# Harness Plan

Use the CLI as the fact and write engine; do not recreate its scan in prose.

1. Run `harness plan` in the target project, adding `--title` only when the user supplied a stable stage title.
2. Explain the detected version, plan state, conflict and proposed destination in user language.
3. Run `harness plan --apply` only after the user explicitly asked to create/update the plan or accepted the preview.
4. If an active plan conflict returns exit 2, stop. Do not overwrite, archive or merge plans on the user's behalf.
5. Report the written path and current verification; do not claim implementation started.

This Skill does not replace Codex `/plan`, edit source code, change Git, configure Brain or publish anything.
