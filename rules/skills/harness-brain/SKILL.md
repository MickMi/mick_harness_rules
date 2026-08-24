---
name: harness-brain
description: Inspect or configure Harness Brain as disabled, local-only, or connected to a private remote. Use when the user explicitly asks for the Harness Brain command, its write destination, synchronization scope, or connection health.
---

# Harness Brain

Start with `harness brain status`; report mode, effective config source, local write path, configured remote, actual origin and synchronization scope.

For a change:

1. Preview `harness brain configure --mode local|remote|disabled` with the requested local path or private remote.
2. Never put credentials in the remote URL; use the system credential manager.
3. Add `--apply` only after explicit approval. Configuration alone does not create, clone, delete or synchronize data.
4. Run `harness brain install` only when the user also asked to establish the configured local repository/adapters.
5. Run `harness brain sync` only for remote mode and after the destination and upload manifest are confirmed.

Disabling Brain preserves existing data. Do not include Prompt text, transcripts, secrets, environment variables or full logs in memory events.
