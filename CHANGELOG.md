# Changelog

Language: English | [简体中文](CHANGELOG.zh-CN.md)

All notable changes to Mick Agent Harness are documented in this file.

This project follows Semantic Versioning 2.0. Git tags in the form `vX.Y.Z`
are the release source of truth.

## [0.22.1] - 2026-09-03

### Update Runtime Reload Hotfix

- `harness update` now compares the installed revision before and after pull,
  fetches release tags, and reloads the single 6425 Observer only when a new
  revision was installed.
- A no-change update keeps the healthy service process intact and continues to
  use the existing idempotent service installation path.

Compatibility: no project, Agent, Brain, event, or dashboard migration is
required. This only corrects the installation lifecycle after an update.

## [0.22.0] - 2026-09-03

### Unified Diagnostics and Maintenance Closure

- **One deterministic Doctor**: `harness doctor [--json] [project]` combines
  installation, project injection, Code Agent, optional Brain, the single
  local Observer, and plan audit health without duplicating their underlying
  business logic. Each failure includes a fixed, reviewable next action.
- **Adapter Registry v2**: every known Agent declares support, rule loading,
  Skill, Hook, and repair capabilities independently. CLI and workbench use the
  same contract; static files still never count as runtime loading proof.
- **Isolated Brain fixtures**: repeatable tests cover configured ingestion,
  disabled Brain behavior, idempotent Claude hooks, proposal-only evolution,
  and project-local fallback. The fallback now reads the current project's
  audit log instead of the Harness repository's log.
- **Single demand source**: first use is reduced to install, project init, then
  Doctor. Stale README and TODO backlogs are retired, historical v0.19
  acceptance states are corrected from existing evidence, and
  `docs/VERSIONS.md` remains the only product demand source.

Compatibility: v0.21 projects, Agent loaders, Hook files, Brain modes, event
ledgers, and the single `127.0.0.1:6425` service remain compatible. Registry v2
is internal to this Harness version and requires no project migration.

Migration: run `harness update`, then `harness doctor`. Apply only the repair
commands reported for the user's actual machine; Brain remains optional.

Verification: 204 unittests, generated-rule consistency, complete
Shell/Python/JSON syntax checks, a temporary clean-home install path, real 6425
health comparison, and a browser-verified Agent page with seven adapters, no
horizontal overflow, and no console warnings or errors.

## [0.21.0] - 2026-08-30

### Lightweight Execution, Shared Commands, and Truthful Project Activity

- **Adaptive execution modes**: `auto`, `quick`, `standard`, and `e2e` choose
  the lightest workflow that can prove the result. Quick work avoids Plan and
  role ceremony; E2E confirms intent first and stops at a release candidate.
- **Cross-Agent command surface**: `harness plan`, `goal`, `brain`, and `e2e`
  share deterministic CLI contracts with thin Agent Skills. Existing Codex
  `/plan` and `/goal` commands are not overridden.
- **Explicit Brain states**: users choose disabled, local-only, or private
  remote memory. A missing remote does not create a false sync failure, and
  generic `~/.brain` defaults from v0.20.2 remain intact.
- **Bounded resident context**: detailed role procedures move to on-demand
  Skills while Kernel safety, verification, and escalation rules remain in the
  loader under automated byte and approximate-token budgets.
- **Execution transparency**: structured events record effective mode,
  selection and escalation reasons, user-decision state, round duration, Agent
  turns, and Harness commands. Unavailable generic tool-call counts are shown
  as unrecorded instead of inferred from conversation text.
- **Unified project identity**: a registered project may use one shallow nested
  Git repository as its code workspace, and uniquely matched ChatGPT/Codex
  mirrors contribute their real Agent activity to the same project. Commits and
  turns are evidence of activity, never fabricated requirements or completion.

Compatibility: v0.20 projects, event ledgers, Agent loaders, Brain modes, and
the single `127.0.0.1:6425` service remain compatible. Ambiguous nested
repositories or duplicate mirror names are deliberately not auto-linked.

Migration: run `harness update` to refresh the global installation, registered
project mounts, Agent adapters, command Skills, and Observer service.

Verification: 195 unittests, generated-rule consistency, Shell/Python/JSON
syntax, context-budget and public-release audits, a non-interactive temporary
install, plus a real-browser project path covering nested Git activity, Agent
mirror activity, responsive width, and console cleanliness.

## [0.20.2] - 2026-08-24

### Public Brain Defaults and Release Privacy

- New installations use the generic private-memory directory `~/.brain`.
  Existing installations continue to discover the legacy directory when the
  new path does not exist, without moving or deleting memory.
- The public configuration no longer includes a maintainer Brain remote or a
  tracked owner file. Brain identity now comes from the user's private Brain
  repository; local-only Brain uses the local system user.
- Owner mismatches preserve private memory by default. Destructive reset is
  available only through an explicit `--fresh` request.
- Generated Agent loaders reference private Capsule sources without copying
  their contents, and no longer contain a built-in maintainer persona.
- A repeatable public-release audit rejects personal paths, identities, project
  names, Brain remotes, legacy defaults outside compatibility code, and
  credential-shaped content.

Compatibility: no automatic data migration is performed. An existing legacy
Brain remains readable, explicit custom paths and private Git remotes continue
to work, and new installations create `~/.brain`.

Migration: run `harness update`. Optionally configure the user's private Brain
remote in `config/.brain-config.yaml`; no remote is required for local use.

Verification: 150 unittests, generated-rule consistency, complete Shell syntax,
fresh-install and legacy-upgrade smoke tests, public-release audit, and
`git diff --check`.

## [0.20.1] - 2026-08-24

### Overview Selection Restore Hotfix

- Preserve a current-version requirement selected through the `task` URL
  parameter when the project page reloads. Overview validation now uses the
  current version's requirement IDs instead of incorrectly rejecting them
  against the legacy Plan task table.
- When an overview URL has no valid requirement selection, choose the current
  version's in-progress or blocked requirement, then its first requirement,
  rather than leaking an unrelated active Plan step into the URL.

Compatibility: no schema, event, loader, or project-file migration is needed.
Run `harness update` to refresh the dashboard and the 6425 Observer service.

Verification: 142 unittests, generated-rule and diff checks, plus real-browser
selection, reload, drawer scope, desktop width, and console validation on the
installed 6425 service.

## [0.20.0] - 2026-08-24

### Requirement-level Product Gates and Task Offices

- **Deterministic requirement workflow**: each v0.20 requirement now advances
  independently through `PM → product review → development → QA → release
  ready`. A version-wide Plan, free-text handoff, or another requirement's
  activity can no longer advance the current requirement.
- **Pre-development product review**: Reviewer gains a dedicated
  `product_review` mode and the bundled `product-logic-review` Skill. It checks
  user paths, state changes, permissions, timing, failure recovery, and boundary
  cases before development, returning an explicit approval or change request.
- **Evidence-backed delivery gates**: development requires artifact and
  self-verification references; QA must independently record pass/fail evidence.
  High-risk work may add a separate post-QA `release_review`, while narrowly
  defined technical-only fixes use an auditable exception instead of bypassing
  the workflow silently.
- **Task-scoped role office**: every current-version requirement shows its own
  compact PM, Review, Development, QA, and Release path. Selecting a requirement
  expands its animated role office in place; role history, decisions, and
  artifacts stay scoped to that requirement, with Designer inserted only when
  it actually participated.
- **Truthful compatibility projection**: legacy events remain readable without
  fabricated approvals. Invalid role transitions and plan/status conflicts are
  retained for audit and explained in the workbench, but do not move the
  effective requirement stage.

Compatibility: existing projects, v0.19 event ledgers, Agent loaders, Brain
repositories, and the `127.0.0.1:6425` endpoint remain compatible. The runtime
event contract adds optional fields only, and no third-party dependency was
added.

Migration: run `harness update`. It refreshes the global Harness, registered
project mounts, Agent loaders, and the single 6425 Observer service. Historical
events remain visible; new product gates apply to requirements planned in
v0.20.0 or later.

Verification: 141 unittests, generated-rule consistency, Python, JavaScript,
Shell and JSON syntax, Skill validation, `git diff --check`, a non-interactive
temporary-project setup smoke test, and real-browser desktop/mobile validation
on the 6246 development service with requirement switching, scoped drawers,
zero page overflow, and no console errors or warnings.

## [0.19.0] - 2026-08-22

### Controlled Operations, Skill Governance, and Harness Evolution

- **Actionable project workbench**: the home page now exposes only audited
  Harness update, project injection/upgrade, and Agent repair operations. Every
  mutation uses preview, explicit confirmation, idempotency, a single-operation
  mutex, fixed argument lists, recovery state, and redacted audit output.
- **Reliable machine-wide Observer**: service installation reuses a matching
  healthy process and restores the previous service when replacement fails.
  Project registration and foreground/background scanning share one portfolio,
  while missing projects can be removed without deleting their files.
- **External Skill governance**: the workbench discovers built-in, personal,
  Agent, and project Skills without executing their scripts. Compatibility
  diagnostics surface role, Hook, completion-contract, loader, and unsafe
  instruction conflicts before users choose what to install or adapt.
- **Requirement command center**: the project home leads with current-version
  requirements. Each requirement shows its actual role path, current work,
  independent QA scope, evidence, blockers, and next step; completed work no
  longer carries a stale owner or role-transition suggestion.
- **Interactive role office**: PM, Designer, Developer, QA, and Reviewer use the
  compact jelly-character scene with real participation history. QA is an
  explicit quality gate, while Reviewer inspects declared artifacts and
  verification evidence instead of replacing testing.
- **Project issue to Harness improvement**: users can turn selected project
  memories into Rule, Skill, Checker, or Profile proposals. Single-project
  signals stay observed by default; cross-project/frequent signals or explicit
  submission enter approval. Approval creates an auditable proposal and never
  rewrites central Harness rules automatically.

Compatibility: existing projects, loaders, event ledgers, Brain repositories,
and the `127.0.0.1:6425` endpoint remain compatible. No third-party dependency
was added. Local mutation endpoints remain action-token protected, now reject
oversized operation bodies, and serialize Harness-improvement state changes.

Migration: run `harness update` after installing this release. It refreshes the
global Harness, registered project mounts, Agent loaders, and the single 6425
Observer service; project source files and Brain records are not deleted.

Verification: 129 unittests, generated-rule consistency, Python and JavaScript
syntax, `git diff --check`, independent QA for all six v0.19 requirements, and
real-browser verification on the 6246 development service with v0.19 shown as
6/6 and no stale completed-work flow.

## [0.18.0] - 2026-08-19

### Brain Memory Workbench and Controlled Synchronization

- **Deterministic project memory**: completed, accepted, and verified structured
  events from Claude, Codex, and generic Harness clients are redacted,
  deduplicated, and written locally without depending on SessionEnd. Session
  capture remains an optional, disabled-by-default backfill path.
- **Two explicit memory pipelines**: project facts write locally without an
  approval bottleneck and can be corrected, reverted, merged, or promoted;
  cross-project preferences and versioned Profiles remain visible candidates
  that users can edit, re-scope, merge, ignore, approve, reject, and retry.
- **Inspectable synchronization**: before any push, the workbench shows the
  effective repository, branch/upstream, grouped records, destinations,
  managed files, all ahead commits, and excluded content. Repository mismatch,
  remote divergence, or unrelated staged files blocks confirmation; execution
  rechecks the boundary to prevent state changes after preview.
- **Workbench information architecture**: project navigation, Brain settings,
  newest-first version planning, and Git visualization were rebuilt around one
  machine-wide service. A repository can expose multiple checked-out worktrees
  and work branches without pretending that every branch has an active Agent.
- **Human PRD and cost-aware verification**: `prd-for-humans` remains isolated
  from technical delivery contracts through a versioned Profile and
  contamination checks. `fast`, `subsystem`, and `release` verification tiers
  reuse a successful Gate only for the exact same code, environment, and
  command fingerprint.

Compatibility: existing Harness projects, event ledgers, loaders, Hooks, and
Brain repositories remain valid. No dependency was added. The workbench gains
authenticated localhost mutation routes, but Brain remote synchronization still
requires a generated preview and an explicit user confirmation.

Verification: 98 unittests, generated-rule consistency, shell syntax,
`git diff --check`, non-interactive first-run smoke setup, and real-browser
workbench paths with no console errors.

## [0.17.0] - 2026-08-13

### Reliable Agent Integration and Role Contracts

- **Five-layer Agent diagnostics**: a versioned registry discovers Claude Code,
  Codex, Cursor, Windsurf, Cline, Roo Code, and Trae without claiming unsupported
  lifecycle coverage. The workbench separates discovered, injected, loaded,
  execution-compliant, and feedback states.
- **Safe loader and Hook management**: `harness agents doctor|sync|migrate|hooks`
  provides dry runs, marker conflict detection, atomic replacement, backups, and
  idempotent Claude/Codex lifecycle configuration. Loader evidence never counts
  as proof that a live session loaded or followed the rules.
- **Recoverable structured feedback**: versioned ingest envelopes are queued
  before delivery, replayed after service recovery, deduplicated by stable keys,
  and reject prompt, transcript, secret, and environment content.
- **Concise role contracts**: PM, Planner, Executor, QA, Reviewer, optional
  Designer, and orchestration use small, project-independent responsibility
  contracts. Shared delivery mechanics live in orchestration; Reviewer may run
  minimal evidence checks without owning QA.
- **Audited design method**: Designer loads the bundled `designer-craft` Skill
  only for real design work. Pinned open-source projects are reviewed inputs,
  not runtime dependencies or alternate permission systems.
- **Private Brain boundary**: reusable findings become redacted, deduplicated
  candidates; project ledgers expose metadata only and Brain writes require
  explicit confirmation.

Compatibility: existing project mounts and runtime ledgers remain valid. Global
Claude/Codex loaders and lifecycle Hooks can be migrated independently; Codex
CLI command Hooks must be reviewed and trusted through `/hooks` before they run.

Verification: 71 unittests, shell/Python/JSON/JavaScript and generated-rule
checks, atomic migration and failure-injection coverage, live `127.0.0.1:6425`
portfolio/Agent APIs, Markdown and collapsible code readers, and browser console
with no errors.

Release evidence: a live Codex session completed the four-state lifecycle and a
Reviewer behavior sample scored 10/10. Claude Code retained verified loader and
partial session evidence, but its turn and behavior evaluation remain explicitly
unverified because the user signed out before the final sample.

## [0.16.0] - 2026-08-12

### Structured Artifact Stage Navigation

- **Traceable stage headings** (`rules/core.md`): evolving Markdown documents
  now use `## vX.Y.Z · YYYY-MM-DD · Stage title`. The version comes from
  `docs/VERSIONS.md`, the date is the actual discussion/decision date, and
  neither may be invented.
- **Deterministic parser** (`scripts/harness-observe.py`): new
  `parse_markdown_stages()` reads H2–H4 headings only — dates in body text or
  fenced code never create stage entries. Legacy headings with parenthesized
  or dashed dates remain navigable, keep every date, and are marked
  `traceable=false` with "未标版本" instead of a guessed version.
- **Dashboard**: the artifact page replaces event-based version/date filters
  with a stage outline that scrolls to the matching heading in the current
  document. Code artifacts keep the collapsible line-number reader and never
  show Markdown stages.

Compatibility: the artifact API gains an additive `stages` field; legacy
`artifact_mode` / `artifact_scope` URL parameters are ignored and removed on
the next state write. No new dependencies, no mutation endpoints.

Verification: 43 unittests, shell/Python/JSON/JavaScript syntax,
`generate.sh --check`, `git diff --check`, Harness Audit 8 PASS / 0 FAIL,
real sample mobile project parse (38 stages, multi-date legacy heading preserved).

## [0.15.0] - 2026-08-12

### Artifact Records by Version and Date

- Artifact metadata now aggregates **every work-round reference** for the
  same path (`records`, `versions`, `dates`) instead of deduplicating away
  delivery context.
- The artifact page shows each record's goal, result, role, date, and the
  key decisions of the linked requirement; Markdown readers gained a heading
  outline for in-document jumps.
- **Post-delivery correction**: version/date navigation scopes to the
  selected file's stage records only — the left file list is never filtered,
  and the page states clearly that the current file is not a historical
  snapshot.

Verification: 42 unittests, Harness Audit 8 PASS / 0 WARN / 0 FAIL,
installed runtime checksums match source, Observer `/healthz` ok.

## [0.14.0] - 2026-08-12

### Role Offices and Layered Goals

- **Three-layer goals**: the stable project goal lives in `docs/PROJECT.md`
  (new, PM-owned), version goals in `docs/VERSIONS.md`, and plan phase goals
  are no longer mislabeled as the overall goal.
- **Five role offices**: the project home shows PM / Designer / Executor /
  QA / Reviewer with real states (active / waiting / completed / idle)
  projected only from `work.round_*` and `handoff.created` events; Planner
  and Orchestrator fold into the PM group.
- **Real vs. suggested flow**: explicit handoffs and `next_role` suggestions
  render differently; a delivered version says "本版本已交付，等待 PM 定义下一版本"
  instead of a generic "current requirement undetermined".
- Role detail pages merge requirement context, execution summaries,
  artifacts, decisions, and history; the four duplicated home modules were
  removed.

Verification: 40 unittests, Harness Audit 8 PASS / 0 WARN / 0 FAIL, live
workspace API returns the stable project goal, five roles, and the real
`Reviewer → PM` suggested handoff.

## [0.13.0] - 2026-08-12

### From Rule Injector to Local Work Server + Unified Workbench

- **Observer V0**: append-only per-project event ledger
  (`.harness-runtime/`), plan/STATE collectors, deterministic snapshot
  replay, and a localhost read-only dashboard — observation only, no
  orchestration.
- **Portfolio**: `harness observe watch --all` aggregates every registered
  project with valid/invalid/missing states; project ids resolve only
  through the Harness registry.
- **Mick Harness Observer service**: launchd agent
  (`com.mick.harness.observer`) keeps a scanner alive on `127.0.0.1:6425`;
  `harness observe service install|start|stop|restart|status|logs|uninstall`
  manages the lifecycle.
- **Requirement navigation**: the default project view shows the overall
  goal, plan-derived requirements, and `定义 → 实现 → 验证 → 交付` nodes;
  raw events move to "技术记录".
- **Work server ingest**: the single mutation endpoint `POST /api/v1/events`
  (Bearer token, registry-scoped, idempotent) receives `work.round_started /
  work.round_completed / decision.recorded / handoff.created`; agents and the
  CLI fall back to the local ledger when the service is unreachable, without
  changing exit codes. Prompts, chat transcripts, command arguments, and
  secrets are never stored.
- **Artifact reading + PM version workbench**: authorized Markdown/code
  artifacts render in the dashboard (safe DOM, 512 KiB text cap, path
  escape/symlink/binary rejection); `docs/VERSIONS.md` becomes the PM-owned
  version plan, displayed against read-only Git branch/tag/HEAD/dirty facts.
- **Codex hook** (`scripts/harness-observe-hook.py`): lifecycle events are
  redacted to session/turn state, project id, and time; hook config is
  printed for review, never auto-installed.

Migration notes: the dashboard port moved from `4317` to **`127.0.0.1:6425`**;
run `harness observe service install` once to keep the observer alive across
terminals. All event-ledger, HTTP GET, and CLI surfaces stay backward
compatible.

Verification: 37 unittests at freeze, end-to-end two-project ingest →
aggregate → refresh → restart recovery, LaunchAgent health checks, installed
runtime checksums match source.

## [0.12.0] - 2026-07-16

### Kernel Uplift (`rules/core.md`) — Rebuttal Tables & Verification Gate

- **Rule 5 (撞墙熔断) — new "撞墙合理化反驳表"**: 6 rows of common
  self-rationalizations ("再试一次就好了" / "这次的原因不一样" / "改这里应该就行")
  paired with the required behavior. Triggers Debug Card instead of another
  guess-and-check cycle. Inspired by superpowers' "Common Rationalizations"
  pattern, localized to the actual failure modes seen in Chinese-language
  Executor sessions.
- **Rule 7 (完成必须验证) — new "验证 Gate" (5 steps)**: `IDENTIFY → RUN →
  READ → VERIFY → THEN claim`. Skipping any step = lying, not efficiency.
  Explicitly names the failure of trusting memory over fresh execution.
- **Rule 7 — new "完成话术反驳表"**: 7 rows of banned phrases ("应该好了" /
  "配置好了" / "只是警告不影响" / "Subagent 报告 success") paired with the
  reality (verify independently, evidence over claim).
- **Rule 7 — new "Claim / Requires / Not Sufficient" table**: 10 rows mapping
  claim types (test pass / build OK / bug fixed / config effective / UI works /
  deployed / requirement met) to their real evidence vs common fake evidence.
  Makes "what counts as proof" concrete instead of aspirational.

### Playbook Additions (`rules/extended.md`)

- **§3.4 Interaction QA — new "UI 完成话术反驳表"**: 6 rows targeting UI-specific
  failure modes ("按钮已加上了" / "开关切换正常" / "本地测通了") that don't
  fit under general verification. Complements the existing 五要素 checklist.

### SessionStart Hook (`hooks/session-start.sh`, `scripts/hook-adapters.sh`)

- **New Claude Code SessionStart hook** — fires on `startup|clear|compact`,
  injects Tripwire + Self-Test trigger conditions + turn-card format as
  `hookSpecificOutput.additionalContext`. Solves the "AGENTS.md may not be read
  by every tool on entry" problem that used to depend on convention alone.
- **Silent no-op outside Harness projects** — walks up 8 parent dirs looking
  for `.harness/`, `AGENTS.md`, or `CLAUDE.md` markers; exits 0 without JSON
  if none found, so the hook doesn't pollute unrelated sessions.
- **`hook-adapters.sh` extended** — new
  `install_claude_code_session_start_hook()`, `claude_session_start_status()`,
  `iter_claude_session_start_commands()`. `harness brain install` now installs
  both SessionEnd (brain-sync) and SessionStart (Tripwire injection) hooks.
- **Fix (SessionEnd status detection)** — `iter_claude_hook_commands()` and
  the new SessionStart iterator both switched from `python3 <<PY "$file"`
  to `python3 - "$file" <<PY`. The old form silently swallowed the JSON
  parse (python3 treated the path as a script file, not argv[1]),
  causing `harness brain status` to always report SessionEnd as "missing"
  even when the hook was installed correctly.

### Compatibility

- Fully backward compatible. All rule additions are new clauses; the tables
  surface only when their triggers appear (撞墙 signals / 完成 claims / UI QA).
- SessionStart hook is opt-in via `harness brain install` (already gated on
  `hooks.claude_code.enabled` in `config/.brain-config.yaml`).
- Fixed SessionEnd detection may cause `harness brain status` to change from
  "missing" to "installed" for users who had the hook installed but never saw
  it acknowledged — this is a bug fix, not a behavior change.

### Verification

- `hooks/session-start.sh` tested in three CWDs: harness project → valid JSON,
  home dir with CLAUDE.md → valid JSON, `/tmp` → silent exit 0.
- `harness brain status` now correctly reports
  `Claude Code : enabled (SessionEnd: installed, SessionStart: installed)`
  after install. Both entries verified in `~/.claude/settings.json`.
- `./generate.sh --check` passes; `dist/AGENTS.md` regenerated with new tables.

## [0.12.0] - 2026-07-16

### Kernel Uplift (`rules/core.md`) — Rebuttal Tables & Verification Gate

- **Rule 5 (撞墙熔断) — new "撞墙合理化反驳表"**: 6 rows of common
  self-rationalizations ("再试一次就好了" / "这次的原因不一样" / "改这里应该就行")
  paired with the required behavior. Triggers Debug Card instead of another
  guess-and-check cycle. Inspired by superpowers' "Common Rationalizations"
  pattern, localized to the actual failure modes seen in Chinese-language
  Executor sessions.
- **Rule 7 (完成必须验证) — new "验证 Gate" (5 steps)**: `IDENTIFY → RUN →
  READ → VERIFY → THEN claim`. Skipping any step = lying, not efficiency.
  Explicitly names the failure of trusting memory over fresh execution.
- **Rule 7 — new "完成话术反驳表"**: 7 rows of banned phrases ("应该好了" /
  "配置好了" / "只是警告不影响" / "Subagent 报告 success") paired with the
  reality (verify independently, evidence over claim).
- **Rule 7 — new "Claim / Requires / Not Sufficient" table**: 10 rows mapping
  claim types (test pass / build OK / bug fixed / config effective / UI works /
  deployed / requirement met) to their real evidence vs common fake evidence.
  Makes "what counts as proof" concrete instead of aspirational.

### Playbook Additions (`rules/extended.md`)

- **§3.4 Interaction QA — new "UI 完成话术反驳表"**: 6 rows targeting UI-specific
  failure modes ("按钮已加上了" / "开关切换正常" / "本地测通了") that don't
  fit under general verification. Complements the existing 五要素 checklist.

### SessionStart Hook (`hooks/session-start.sh`, `scripts/hook-adapters.sh`)

- **New Claude Code SessionStart hook** — fires on `startup|clear|compact`,
  injects Tripwire + Self-Test trigger conditions + turn-card format as
  `hookSpecificOutput.additionalContext`. Solves the "AGENTS.md may not be read
  by every tool on entry" problem that used to depend on convention alone.
- **Silent no-op outside Harness projects** — walks up 8 parent dirs looking
  for `.harness/`, `AGENTS.md`, or `CLAUDE.md` markers; exits 0 without JSON
  if none found, so the hook doesn't pollute unrelated sessions.
- **`hook-adapters.sh` extended** — new
  `install_claude_code_session_start_hook()`, `claude_session_start_status()`,
  `iter_claude_session_start_commands()`. `harness brain install` now installs
  both SessionEnd (brain-sync) and SessionStart (Tripwire injection) hooks.
- **Fix (SessionEnd status detection)** — `iter_claude_hook_commands()` and
  the new SessionStart iterator both switched from `python3 <<PY "$file"`
  to `python3 - "$file" <<PY`. The old form silently swallowed the JSON
  parse (python3 treated the path as a script file, not argv[1]),
  causing `harness brain status` to always report SessionEnd as "missing"
  even when the hook was installed correctly.

### Compatibility

- Fully backward compatible. All rule additions are new clauses; the tables
  surface only when their triggers appear (撞墙 signals / 完成 claims / UI QA).
- SessionStart hook is opt-in via `harness brain install` (already gated on
  `hooks.claude_code.enabled` in `config/.brain-config.yaml`).
- Fixed SessionEnd detection may cause `harness brain status` to change from
  "missing" to "installed" for users who had the hook installed but never saw
  it acknowledged — this is a bug fix, not a behavior change.

### Verification

- `hooks/session-start.sh` tested in three CWDs: harness project → valid JSON,
  home dir with CLAUDE.md → valid JSON, `/tmp` → silent exit 0.
- `harness brain status` now correctly reports
  `Claude Code : enabled (SessionEnd: installed, SessionStart: installed)`
  after install. Both entries verified in `~/.claude/settings.json`.
- `./generate.sh --check` passes; `dist/AGENTS.md` regenerated with new tables.

## [0.11.0] - 2026-07-06

### Kernel Uplift (`rules/core.md`)

- **Rule 1** renamed from "先读后改" to **"先读后改，新建前先查复用"** — before
  creating a new function/interface/service/UI component, Executor must grep for
  similar existing capability. Reuse is default; creating new requires explicit
  justification. Reverses the burden of proof for "new".
- **Rule 5** (Anti-Wall Debug Card) now requires a mandatory follow-up question
  after any fix: **"Can this be turned into an automated check?"** — routing to
  `verify.d/` checker (auto), Rule (semi-auto), or brain gotcha (manual). No more
  fix-and-forget.
- **Rule 7** (完成必须验证) adds **Baseline First** discipline and a
  `.harness/verify.sh` contract entry point — verify/debug/regression tasks must
  save a pre-change baseline and diff against it, so "not my bug / historical
  issue / just a warning" can no longer be answered verbally.

### Playbook Additions (`rules/extended.md`)

- **§3.1 Anti-Wall Debug Controller** — added two disciplines: *Baseline First*
  (report-diff over verbal excuses) and *修复后必问自动化* (fix-and-forget ban).
- **§10.3 Executor 自检 ritual** expanded from 5 steps to 7 — added "grep for
  reuse before creating new" and "verify tasks save baseline first". Both aim
  at the two most common Executor failure modes: reinventing wheels and
  scapegoating pre-existing failures.

### Skills Layer (`rules/skills/`)

- **New third layer between Kernel and Playbook** — Skills are runnable playbooks
  for high-frequency fixed actions (compile, test, post-verify, release, sign)
  that must not be improvised each time. Rule says "you must do this"; Skill
  says "here's exactly how".
- Harness ships **framework only, not content**: `rules/skills/README.md`
  (positioning, when to write, how to be referenced, evolution-including-deletion)
  and `rules/skills/_template.md` (frontmatter + 6 mandatory sections). Concrete
  skills (compile-what, test-what) are project-owned since tech stacks vary too
  widely for canned content.
- Three reference mechanisms: Rule points to Skill / plan step invokes Skill /
  role contract mandates Skill.
- Skills are subject to same evolution-with-deletion loop as Rules — 6-monthly
  review, retire long-untriggered ones.

### Verify Contract (`docs/VERIFY-CONTRACT.md`)

- Formalizes `.harness/verify.sh` (orchestrator) + `.harness/verify.d/*.sh`
  (pluggable checkers) + `.harness/verify.disabled/` (retired) architecture.
  One check per file, add/remove = add/remove file, orchestrator does no
  business logic.
- Checker naming convention: `NN-<category>-<what>.sh`. Exit codes: 0 pass /
  1 fail / 2 unknown / 77 skip. Supports `--profile`, `--changed`, `--only`,
  `--skip` flags.
- Explicitly wires the verify layer into the §10.9 self-evolution loop —
  checkers grow from real Debug Cards (fix → "can this be automated?" →
  `verify.d/NN-xxx.sh`), and long-untriggered ones retire to `verify.disabled/`
  every 6 months. Prevents both bloat and blind-spot regression.
- Project-tier bootstrap guidance: 3 checkers for personal / 10-15 for
  mid-size / 20+ profile-sharded for large multi-module.

### Compatibility

- Fully backward compatible. All changes are additive.
- Existing projects using Rules 1/5/7 continue to work; the additions are new
  clauses that surface only when their triggers appear (creating new code /
  Debug Card / verify tasks).
- Skills layer and verify.d/ are opt-in — projects without them behave exactly
  as before.

### Verification

- `./generate.sh` regenerated dist/AGENTS.md; `--check` passes.
- `bash -n` syntax check on `bin/harness scripts/*.sh generate.sh` passes.
- Kernel changes propagated to dist/AGENTS.md (verified via grep).

## [0.10.0] - 2026-07-06

### Product

- Renamed from "Mick Harness Rules" to **Mick Agent Harness** — a personal Agent
  collaboration layer that supplements, not overrides, code-agent capability.
- Rewrote README as a full product document covering install → init → sync →
  verify → Brain → evolution, with a new English translation (`README.en.md`).
- Clarified the guarantee boundary: Harness is prior injection + posterior checks
  + long-term memory + human gatekeeping, not a magic enforcement layer.

### Brain Architecture

- Introduced `ensure_brain_available` — Brain unavailability never blocks
  `harness init`, `harness check`, or the main Harness workflow. Falls back to a
  private local Brain when the configured remote is unreachable.
- Added `init_brain_skeleton` for consistent Brain directory structure.
- Refactored Brain resolution: `BRAIN_REMOTE_STATUS` tracks connectivity
  (connected / local / unavailable / none) separately from directory existence.

### Hook Adapters

- Extracted tool-specific hook logic into `scripts/hook-adapters.sh` so the
  command surface stays `harness brain install` and `harness brain status`.
- Added adapter registry in `config/.brain-config.yaml` — Claude Code defaults to
  enabled; Codex and generic adapters are opt-in.
- Added `scripts/brain-ingest.sh` as a tool-neutral ingestion endpoint supporting
  session digests, learnings, and failure signals from any tool.

### Rule Generation

- `generate.sh` now skips capsule injection when Brain source files contain only
  placeholder text (no meaningful user content).
- Added `generated_file_matches` with capsule-stripping so dist drift detection
  ignores harmless capsule-block differences.

### Harness Evolution

- `harness-evolve.sh` now aggregates optional signal files
  (`harness-failures.md`, `corrections.md`, `banned-patterns.md`) alongside the
  audit trail.
- Added nine new failure tags: `tripwire-missed`, `self-test-fake`,
  `fake-verification`, `plan-hijack`, `repeated-failure`, `under-asking`,
  `over-asking`, `executor-correction`, `banned-pattern`.

### Internal

- `scripts/*.sh` are now made executable on install and update.
- Brain commit fallback writes to the private Brain repo rather than the Harness
  repo.

## [0.9.1] - 2026-07-03

### Changed

- Refined the round card into five fixed one-line slots: current round, overall
  state, next step, context/status, and blocker.
- Moved reasoning depth into the current-round line instead of keeping it as a
  separate card row.
- Replaced optional SOS wording with a mandatory blocker row.
- Added a mandatory context load status format using either an approximate range
  with structural sources or a measured percentage with category distribution.

### Notes

- Approximate context status uses the format
  `上下文负载约 70-85%（长线程 + 多轮工具输出 + 多轮决策）`.
- Measured context status uses the format
  `上下文负载 72%（工具输出 38% / 对话 34% / 规则 18% / 文件 10%）`.
- The status line reports state only; any action belongs in the next-step line.

## [0.9.0] - 2026-07-03

### Status

Release candidate baseline for the first formal Harness version.

This version consolidates all repository history from the initial Vibe Coding
scaffold on 2026-03-30 through the Mick Agent Kernel work on 2026-07-01, plus
the currently uncommitted Feature Inventory knowledge changes that still need
owner confirmation before tagging.

### Added

- Initial Vibe Coding scaffold with engineering rules, TODO state, memory file,
  architecture template, and `vibe-init.sh`.
- PM, Designer, QA, Reviewer, Planner, Executor, and Orchestration role files.
- Git workflow, Conventional Commits, SemVer, PR expectations, CI/CD guardrails,
  and deploy environment separation.
- Three-layer Brain model: session, project, and global memory, with scripts for
  init, check, push, search, resolve, compound, migrate, and garbage collection.
- Dual-repo model separating public Harness rules from private Brain data.
- `setup.sh` one-step bootstrap, interactive configuration, bilingual setup
  prompts, and `.harness-config.yaml` generation.
- Single-source rule generator with `minimal`, `lean`, and `full` output
  profiles for different agent surfaces.
- Plan-Execute Protocol, including project-root `plan.md`, strong/weak model
  collaboration rules, Executor guardrails, Planner contracts, and rich plan
  templates.
- Harness Audit scanner and Harness Evolve proposal flow for rule compliance
  and rule evolution feedback loops.
- Harness Self-Test, Anti-Wall debugging discipline, Cross-System Preflight,
  Interaction QA, OD output limits, and round-card handoff protocol.
- Personal Mick Agent Capsule injection and Mick Agent Kernel, including
  evidence discipline, boundary control, completion verification, and feedback
  triage.
- PM requirement design improvements: adaptive PRD guidance, requirement
  hierarchy, AI evaluation sections, metrics, data source probes, exception and
  boundary handling, and phased delivery questioning.
- Proposed Feature Inventory guidance and `docs/FEATURES.template.md` for
  user-visible capability maps.

### Changed

- README repositioned from a long implementation guide to a coordination and
  governance entry point.
- Rules moved from tool-specific files into `rules/core.md` and
  `rules/extended.md` as the source of truth.
- Generated agent files moved under `dist/`; project-level files are produced
  by `generate.sh` instead of being hand-maintained.
- PM workflow changed from rigid gatekeeping to conversational intent discovery
  and adversarial requirement review.
- Plan precheck was elevated to Rule 0 and decoupled from Cursor-specific
  naming.
- `plan.md` location moved from `.harness/plan.md` to the project root.
- Claude Code profile adjusted from `minimal` to `lean` for non-native models.
- Constitution/Brain synchronization was integrated into generated rule output.
- `.gitignore` was expanded to avoid committing generated or local harness
  artifacts, including proposed `AGENTS.md`.

### Fixed

- Prevented Harness and Brain content from leaking into target project Git
  history.
- Restored non-interactive setup configuration generation and fixed unbound
  shell variables.
- Fixed `brain-resolve.sh` compatibility under `set -u`.
- Changed mount behavior so existing project files receive managed Harness
  injection instead of being skipped.
- Corrected generated profile routing and plan path references.
- Incorporated multiple PM template fixes from usage feedback.

### Release Notes

- This is the first formal release candidate. No previous Git tags exist, so
  `[0.9.0]` is a historical baseline rather than an incremental diff from an
  earlier tagged version.
- The repository currently reports `73705fd-dirty`; release tagging should wait
  until the current Feature Inventory changes are either committed or explicitly
  excluded.
- Before tagging, run the release checklist in `docs/RELEASE_CHECKLIST.md`.

## Historical Trace

### 2026-03-30 to 2026-03-31: Vibe Coding and agent roles

- Started the scaffold with core engineering rules, memory/TODO files, and
  initialization script.
- Added PM and Designer workflows.
- Added Reviewer and logic-auditor role support.

### 2026-04-09 to 2026-04-22: Workflow, Brain, and repository model

- Added Git, CI/CD, QA, orchestration, and role routing guardrails.
- Built the initial Brain scripts and three-layer memory model.
- Added license and tightened README positioning.
- Added privacy controls to keep Harness/Brain content out of target repos.
- Introduced Goal Discovery and then moved to the dual-repo Harness/Brain model.
- Added `setup.sh` as the one-step bootstrap path.

### 2026-06-03 to 2026-06-11: Configurable setup and Plan-Execute

- Added state-driven orchestration and interactive workflow configuration.
- Added bilingual setup and status-line observability.
- Refactored rules into a single-source generation system.
- Added multi-model profiles, strong/weak model role recognition, and Solo mode.
- Added Plan-Execute conflict resolution, Executor guidance, Planner/Executor
  contracts, and rich plan templates.
- Fixed setup and generated output compatibility issues.

### 2026-06-18 to 2026-06-25: Audit, evolution, and governance

- Added round-card navigation, compliance scanning, and faster onboarding.
- Added rule evolution loop driven by audit signals.
- Split generic PM PRD structure from personal style held in Brain.

### 2026-06-28 to 2026-07-01: PM refinement and Mick Agent Kernel

- Added Feedback Triage Protocol.
- Refined PM guidance for PRD boundaries, pain-point discovery, phased delivery,
  rule explanations, exception handling, metrics, AI evaluation, and data source
  probing.
- Clarified PM versus Planner branching.
- Merged personal agent quality gates and defined the Mick Agent Kernel.

### 2026-07-03: Proposed release hygiene

- Proposed formal versioning with `VERSION`, `CHANGELOG.md`, release process,
  and release checklist.
- Reviewed current uncommitted knowledge changes and marked Feature Inventory as
  suitable for inclusion in `v0.9.0` after owner confirmation.
