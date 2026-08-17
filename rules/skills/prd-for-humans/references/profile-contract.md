# PRD Profile Contract

A PRD Profile stores stable writing preferences without turning them into a fixed template. The content is private by default; only its version and source may be shown in the Harness workspace.

## Resolution order

1. Current-turn explicit instruction.
2. Project profile: `docs/PRD-PROFILE.md`.
3. Private profile: `<brain>/global/profiles/prd/current.json` pointing to a version file in the same directory.
4. Bundled generic profile: `references/default-profile.md`.

A higher layer overrides only the rule it addresses. It does not erase compatible lower-layer guidance.

## Version file

Use Markdown with this frontmatter:

```yaml
---
profile: prd-for-humans
version: 1.0.0
status: active
updated: 2026-08-14
---
```

The body may describe audience, voice, decision style, stable preferences, prohibited patterns, and deprecated rules. It must not prescribe a universal chapter list. Create a new semantic version after the user confirms a stable preference; do not silently rewrite a released version.

## Private pointer

`current.json` contains only metadata:

```json
{
  "schema_version": "1",
  "profile": "prd-for-humans",
  "version": "1.0.0",
  "file": "v1.0.0.md"
}
```

The file must be a basename in the same directory, and its declared version must match the pointer. This makes rollback a pointer change rather than a rewrite.

## Project profile

Use the same frontmatter. Include only constraints that genuinely differ for the project, such as regulated wording or a project-specific review audience. Do not copy the whole private profile into every project.

## Privacy and display

- Agents may read the active file when producing a PRD.
- Harness events and dashboards may expose `source`, `version`, and availability only.
- Do not send profile text, personal examples, or Brain paths to the project ledger.
- Missing or invalid private data falls back to the generic profile and must be reported as a profile diagnostic, not guessed.
