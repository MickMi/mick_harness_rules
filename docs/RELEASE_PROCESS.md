# Release Process

Language: English | [简体中文](RELEASE_PROCESS.zh-CN.md)

This repository uses SemVer and Git tags as the release source of truth.

## Version Policy

- `MAJOR`: incompatible changes to installed project layout, rule contracts,
  generated file semantics, script flags, or mandatory agent behavior.
- `MINOR`: backward-compatible capabilities, new rules, new role guidance, new
  scripts, new templates, or additive generated output.
- `PATCH`: compatible fixes, wording improvements, script bug fixes, test
  improvements, and documentation corrections.

## Required Files

- `VERSION`: current intended release version without the leading `v`.
- `CHANGELOG.md`: human-readable release history.
- `CHANGELOG.zh-CN.md`: Simplified Chinese mirror of the same release facts.
- `docs/RELEASE_CHECKLIST.md`: pre-tag verification checklist.
- `docs/RELEASE_CHECKLIST.zh-CN.md`: Simplified Chinese mirror of the checklist.

Git tag `vX.Y.Z` is final. `VERSION`, `CHANGELOG.md`, and localized release
files must match the tag.

## Language Policy

- English files use the canonical name: `README.md`, `CHANGELOG.md`,
  `docs/RELEASE_PROCESS.md`, and `docs/RELEASE_CHECKLIST.md`.
- Simplified Chinese mirrors use `.zh-CN.md`.
- Each mirrored file must include a language switch link at the top.
- Localized files may adapt wording, but must not add, remove, or contradict
  release facts.

## Release Flow

1. Review current worktree.
   - Confirm every modified and untracked file belongs to the release.
   - Exclude or defer unrelated work before tagging.

2. Choose version.
   - Apply SemVer based on user-visible and compatibility impact.
   - Update `VERSION`, `CHANGELOG.md`, and localized mirrors.

3. Regenerate rule outputs.
   - Run `./generate.sh`.
   - Run `./generate.sh --check`.

4. Verify scripts and generated files.
   - Run syntax checks for shell scripts.
   - Run Harness audit where a target project has `plan.md`.
   - Smoke test install/bootstrap in a temporary directory.

5. Review release notes.
   - Include What changed, Compatibility impact, Migration notes, and
     Verification evidence.

6. Tag only after verification passes.
   - Use annotated tags: `git tag -a vX.Y.Z`.
   - Push commit and tag together after owner confirmation.

## Release Stop Conditions

Stop before tagging when any of these is true:

- Worktree has unexplained dirty or untracked files.
- `VERSION`, `CHANGELOG.md`, and intended tag disagree.
- Generated `dist/` files are stale.
- Setup smoke test fails.
- A release note contains unverified claims.
- A change would break existing project installs and has no migration note.

## First Formal Release Recommendation

Use `v0.9.0` as the first formal baseline unless the owner explicitly wants a
stable `v1.0.0` contract. The repository is already useful, but the release
process, changelog, and checklist are only being formalized now.
