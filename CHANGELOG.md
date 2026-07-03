# Changelog

Language: English | [简体中文](CHANGELOG.zh-CN.md)

All notable changes to Mick Harness Rules are documented in this file.

This project follows Semantic Versioning 2.0. Git tags in the form `vX.Y.Z`
are the release source of truth.

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
