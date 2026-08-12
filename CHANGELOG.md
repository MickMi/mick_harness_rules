# Changelog

Language: English | [简体中文](CHANGELOG.zh-CN.md)

All notable changes to Mick Agent Harness are documented in this file.

This project follows Semantic Versioning 2.0. Git tags in the form `vX.Y.Z`
are the release source of truth.

## [0.15.0] - 2026-08-12

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
real RaliTennis parse (38 stages, multi-date legacy heading preserved).

## [0.14.0] - 2026-08-12

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

## [0.13.0] - 2026-08-12

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

## [0.12.0] - 2026-08-12

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
