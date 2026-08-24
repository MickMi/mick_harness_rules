---
name: harness-e2e
description: Inspect and request controlled delivery for one Harness requirement through product review, development, independent QA, and release readiness. Use when the user explicitly asks for the Harness e2e command and provides one requirement ID.
---

# Harness E2E

1. Require one current-version requirement ID; never combine multiple requirements silently.
2. Run `harness e2e --requirement <id>` and explain the current gate, accepted evidence, rejected jumps, responsible role and stop reason.
3. Add `--run` only after the user explicitly asks to proceed or accepts the preview.
4. A waiting request does not mean an Agent was spawned or a role completed. Hand the named role the missing work and preserve the same requirement ID.
5. Treat `release_candidate` as ready for the user's release decision, not permission to merge, push, tag, deploy or publish.

Do not fabricate gate events, test evidence or role participation. The CLI's v0.20 requirement state machine is the source of truth.
