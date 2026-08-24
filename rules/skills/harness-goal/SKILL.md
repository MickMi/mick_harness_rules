---
name: harness-goal
description: Inspect or maintain the human long-term project goal through the deterministic Harness CLI. Use when the user explicitly asks for the Harness goal command or wants a stable product goal separated from version objectives, plans, and technical work.
---

# Harness Goal

1. Run `harness goal` to read the current human project goal.
2. When the user proposes a goal, preview it with `harness goal --set "<goal>"`.
3. Confirm it describes durable user value and product boundary, not a version, task list, implementation or AI delivery contract.
4. Add `--apply` only when the user explicitly requested the change or accepted the preview.
5. If the CLI rejects technical or version pollution, return the reason and help the user reframe the product value; do not bypass the check.

Only `docs/PROJECT.md` is in scope. Do not replace Codex `/goal`, edit `plan.md`, source code or release state.
