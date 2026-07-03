# Release Checklist

Language: English | [简体中文](RELEASE_CHECKLIST.zh-CN.md)

Use this checklist before every Harness release.

## 1. Scope Review

- [ ] `git status --short` reviewed.
- [ ] Every modified file is either included in this release or deliberately
      deferred.
- [ ] Untracked files are intentional.
- [ ] No private Brain data is included.
- [ ] No generated project-local files are accidentally committed.

## 2. Version Review

- [ ] SemVer bump chosen and explained.
- [ ] `VERSION` matches intended tag.
- [ ] `CHANGELOG.md` contains the release date and complete notes.
- [ ] `CHANGELOG.zh-CN.md` mirrors the same release facts.
- [ ] Compatibility impact is documented.
- [ ] Migration notes are documented when behavior changes.

## 2.1 Language Mirror Review

- [ ] Every English release document has a `.zh-CN.md` mirror when intended for
      public or user-facing consumption.
- [ ] Language switch links work in both directions.
- [ ] Version numbers, dates, headings, compatibility notes, and verification
      claims match across languages.
- [ ] Localized wording does not add or remove facts.

## 3. Generation Review

- [ ] `./generate.sh` ran successfully.
- [ ] `./generate.sh --check` passed.
- [ ] Generated files in `dist/` are consistent with `rules/core.md` and
      `rules/extended.md`.
- [ ] Root generated files such as `AGENTS.md` are ignored or intentionally
      handled.

## 4. Script Review

- [ ] Shell syntax check passed for `*.sh`.
- [ ] `setup.sh --non-interactive` smoke test passed in a temporary project.
- [ ] `vibe-init.sh` smoke test passed when relevant.
- [ ] Brain scripts are not leaking private data into the public repo.

## 5. Harness Behavior Review

- [ ] New project first-run behavior was checked.
- [ ] `plan.md` Executor behavior was checked.
- [ ] Harness Self-Test answer shape was checked.
- [ ] Round-card requirement was checked for delivery/workflow turns.
- [ ] Preflight and Interaction QA language remains available in
      `rules/extended.md`.

## 6. Tag Review

- [ ] Worktree is clean after release files and generated files are committed.
- [ ] Annotated tag is ready: `vX.Y.Z`.
- [ ] Tag message includes verification evidence.
- [ ] Owner explicitly approved tagging and push.

## Current v0.9.0 Candidate Notes

- [ ] Confirm current Feature Inventory changes are included:
  - `.gitignore`
  - `rules/extended.md`
  - `docs/FEATURES.template.md`
- [ ] Confirm `CHANGELOG.md`, `VERSION`, and release docs are added.
- [ ] Confirm Chinese mirror files and language links are added.
- [ ] Run the full verification set after files are placed in the Harness repo.
