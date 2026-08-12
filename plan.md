> 🧭 状态：已完成 | 进度 75/75 | 当前归属：PM | 最近卡点：无

# Plan: Company Runtime V0 → Portfolio V0.2

## 目标

在不自动创建 Agent、不修改现有 `plan.md` / `docs/STATE*.md` / 代码状态的前提下，为 Mick Agent Harness 增加本地只读的运行观察能力：把现有计划、状态和验证证据导入 append-only 事件账本，生成可重放 snapshot，并通过 CLI 与 localhost Dashboard 展示任务、验证、阻塞和事件因果链。

用户已在 2026-08-10 明确要求“执行V0”，本 plan 视为已锁定。

## 约束

- 保持 V0 为 Observer，不实现 Agent spawn、消息派发、任务租约、自动审批或自动改写项目文件。
- 只写目标项目的 `.harness-runtime/`；Collector 对 `plan.md`、`docs/STATE*.md` 和 audit 来源只读。
- 不引入第三方依赖；运行时使用现有 Bash CLI + Python 3 标准库，Dashboard 使用原生 HTML/CSS/JavaScript。
- 不改变现有 `harness report`、`harness metrics`、`harness-audit.sh` 的输出和退出码。
- 事件默认只保存项目相对路径、摘要、退出码和 digest，不保存 Prompt、聊天全文、密钥、环境变量或完整日志。
- Dashboard 默认只允许绑定 `127.0.0.1`。
- 不修改 `rules/*.md`、`generate.sh` 或生成文件；本功能不改变 Harness 规则契约。

## 文件级 API 契约

### `docs/runtime-event-v0.schema.json`（新建）

- 职责：定义 V0 append-only 事件的 Draft 2020-12 JSON Schema。
- 必须包含：run、workflow、task、artifact、verification、block、approval、audit、collector 事件类型。
- 必须区分：`observation_kind=observed|inferred`；inferred 必须携带 `confidence`。
- 路径字段只允许项目相对路径。

### `scripts/harness-observe.py`（新建）

- 职责：实现 V0 ledger、collector、projector、CLI 和只读 HTTP server。
- 仅使用 Python 3 标准库。

| 函数 | 入参 | 出参 | 边界与错误处理 |
|---|---|---|---|
| `resolve_project(value)` | `str | None` | `Path` | 目录不存在 → CLI exit 64 |
| `init_runtime(project)` | `Path` | `dict` run | 幂等复用 active run；只写 `.harness-runtime/` |
| `sync_runtime(project)` | `Path` | `dict` summary | 未发现来源 → collector warning + exit 2；同一 digest 不重复写事件 |
| `collect_plan(project, snapshot)` | `Path, dict` | `list[dict]` | 未知格式输出 warning，不修改 plan |
| `collect_states(project, snapshot)` | `Path, dict` | `list[dict]` | 支持 `STATE.md` 与 `STATE-*.md` |
| `append_events(run_dir, events)` | `Path, list[dict]` | `int` | 原子写入；失败时不更新 snapshot/import index |
| `project_events(events)` | `list[dict]` | `dict` snapshot | 从空状态确定性重放 |
| `replay_runtime(project)` | `Path` | `dict` summary | 重建 snapshot 并返回 digest 是否变化 |
| `serve_runtime(project, port)` | `Path, int` | `None` | host 固定 `127.0.0.1`；只提供 GET/HEAD |
| `main(argv)` | `list[str]` | exit code | `init/sync/status/replay/watch` 子命令 |

### `web/observe-dashboard.html`（新建）

- 职责：只读展示运行列表、任务图/列表、泳道时间线、事件记录和任务详情。
- 数据源：`/api/index.json`、`/api/runs/<run-id>/snapshot.json`、`/api/runs/<run-id>/events.jsonl`。
- URL 状态：`run`、`view`、`task` 参数；刷新后恢复选择。
- 禁止 mutation endpoint、外部 CDN、raw HTML 注入。

### `tests/test_harness_observe.py`（新建）

- 职责：使用 `unittest` + 临时目录覆盖 init、幂等 sync、状态变化、未验证完成、block、STATE、多次 replay 和 HTTP 只读行为。
- 不访问用户真实项目、Brain 或网络。

### `tests/__init__.py`（新建）

- 职责：确保计划锁定的 `python3 -m unittest tests/test_harness_observe.py` 在当前 Python 环境解析本仓库测试包，而不是同名第三方 package。
- 内容保持空文件，不承载运行逻辑。

### `bin/harness`（修改）

- 新增 `cmd_observe()`，转交 `$HARNESS_GLOBAL/scripts/harness-observe.py`。
- 新增 `harness observe [init|sync|status|replay|watch]` 路由与 help 文案。
- Python 3 缺失时明确失败，exit 1。

### `docs/OBSERVE.md`（新建）

- 职责：说明产品边界、目录、事件流、命令、隐私、故障恢复与 V1 进入条件。
- 明确 V0 不是自动编排器。

### `README.md`（修改）

- 日常命令区增加 `harness observe` 入口。
- 链接 `docs/OBSERVE.md`，不改 README 现有定位。

## 步骤

- [x] 1. 新建 `docs/runtime-event-v0.schema.json`，固定事件类型、公共字段、类型 payload 和示例。
  - 已定义 13 类事件、observed/inferred 契约、类型化 payload 和 3 条示例。
- [x] 2. 新建 `scripts/harness-observe.py`，实现 runtime 初始化、事件校验、幂等 ledger、Plan/STATE Collector、snapshot projector、status/replay/watch。
  - 已实现标准库运行时、原子事件账本、digest 去重、collector、确定性 replay、状态摘要和 localhost 只读服务。
- [x] 3. 新建 `web/observe-dashboard.html`，实现只读运行、任务、时间线、事件和详情视图。
  - 已实现无外部资源的响应式 Dashboard，支持 URL 状态恢复、任务详情和 observed/inferred 事件展示。
- [x] 4. 新建 `tests/test_harness_observe.py`，覆盖关键路径和错误路径。
  > ⚡ 修订：允许同时新建空的 `tests/__init__.py`，保证锁定的 unittest 命令解析本仓库测试包。
- [x] 5. 修改 `bin/harness`，接入 observe 命令并保持现有命令兼容。
- [x] 6. 新建 `docs/OBSERVE.md`，记录 V0 使用方式、数据边界、恢复方式和非目标。
- [x] 7. 修改 `README.md`，增加 observe 入口；运行完整验证并记录结果。

## Preflight

- 系统边界：本机文件系统、Python 3、localhost HTTP；不访问远端服务。
- 版本与格式：Python 3 标准库；JSON Schema Draft 2020-12 作为外部契约，运行时执行项目内最小校验。
- 权限与执行位置：只需读取目标项目并写入目标项目 `.harness-runtime/`；开发改动位于当前 Harness 仓库。
- 状态源：`events.jsonl` 是历史事实源，`snapshot.json` 是可重建派生状态，Dashboard 只读 snapshot/events。
- 最小 dry-run：在临时项目运行 `init → sync → status → replay`，确认只新增 `.harness-runtime/`。
- 回滚方式：删除目标项目 `.harness-runtime/` 即移除观察数据；功能代码可按普通 Git revert 回退。

## Interaction QA

- 交互状态机：无 run / observing / active / blocked / verification pending / completed / collector warning。
- 用户路径：`harness observe init` → `harness observe watch` → 选择 run → 选择 task → 查看验证或阻塞来源 → 刷新恢复选择。
- 状态一致性验证：Dashboard task 状态必须与 `snapshot.json` 一致；事件详情必须能定位对应 sequence。
- 失败态：无来源、Schema 版本不支持、JSONL 损坏、snapshot 缺失、端口占用。
- 证据要求：CLI 输出、HTTP 响应、unittest、snapshot/events 文件内容；浏览器预览可用时再补真实点击证据。

## 禁止项

- 不要引入 Flask、FastAPI、Node package、AJV 或其他第三方依赖。
- 不要让 Dashboard 修改 plan、STATE、审批或任务状态。
- 不要从 Brain 自动导入私有内容。
- 不要监听 `0.0.0.0`。
- 不要修改 `rules/`、`dist/`、`generate.sh`、VERSION 或 CHANGELOG。
- 不要把 `.harness-runtime/` 加入本 Harness 仓库的已跟踪内容。

## 完成判定

- [x] `bash -n bin/harness scripts/*.sh generate.sh` exit 0。
- [x] `python3 -m unittest tests/test_harness_observe.py` 0 failures，exit 0。
- [x] `python3 -m json.tool docs/runtime-event-v0.schema.json` exit 0。
- [x] 临时项目连续两次 sync，第二次 appended events 为 0。
- [x] 删除 snapshot 后 replay，重建 digest 与删除前一致。
- [x] completed step 无 passing verification 时显示 `verification_pending`。
- [x] HTTP server 对 `/api/index.json`、snapshot、events 返回 200，对非 GET/HEAD 返回 405。
- [x] `MICK_HARNESS_ROOT="$PWD" ./bin/harness observe --help` 和现有 `report/metrics` 均可运行。
- [x] `./generate.sh --check` exit 0。

## 来自 Brain 的相关约束

- 本次搜索 `multi-agent orchestration event ledger dashboard` 无匹配。

## 自检日志

### Step 1 — 2026-08-10 19:15
- files: docs/runtime-event-v0.schema.json
- verify: `python3 -m json.tool docs/runtime-event-v0.schema.json` passed; embedded example contract check passed (3 examples, 13 event types)

### Step 2 — 2026-08-10 19:24
- files: scripts/harness-observe.py
- verify: Python compile check passed; temporary-project dry-run passed (`first=3`, `second=0`, `replay_changed=False`)

### Step 3 — 2026-08-10 19:27
- files: web/observe-dashboard.html
- verify: Python `HTMLParser` parse passed; extracted inline JavaScript passed `node --check`

### Step 4 — 2026-08-10 19:30
- files: `tests/__init__.py`, `tests/test_harness_observe.py`, `scripts/harness-observe.py`
- verify: `python3 -m unittest tests/test_harness_observe.py` passed (7 tests, 0 failures, exit 0); localhost HTTP test ran with approved local bind
- notes: Tests exposed a missing multiline flag in the Plan Collector; fixed after a focused Debug Card probe.

### Step 5 — 2026-08-10 19:32
- files: `bin/harness`
- verify: `bash -n bin/harness` passed; `harness observe --help`, existing `harness report`, and existing `harness metrics` all exited 0
- notes: The new command is a thin Python 3 dispatcher; existing command implementations were not changed.

### Step 6 — 2026-08-10 19:33
- files: `docs/OBSERVE.md`
- verify: documentation contract check passed (5 CLI commands, balanced code fences, schema link target present)
- notes: The guide explicitly separates V0 observation from future orchestration and documents privacy, recovery, and localhost boundaries.

### Step 7 — 2026-08-10 19:37
- files: `README.md`, `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: shell syntax, Python compile, JSON parse, HTML parse, JavaScript syntax, CLI help/report/metrics, `generate.sh --check`, and `git diff --check` all exited 0; unittest passed (8 tests, 0 failures, exit 0)
- notes: Reviewer probe found and fixed a false active-block projection for sections containing a Planner resolution. Current project probe now reports the historical block as inactive. Browser click QA remains unavailable because the app policy blocks localhost, so HTTP endpoint and frontend syntax evidence are used instead.

## 阻塞 #1（步骤 4）
发现：锁定的 unittest 命令把 `tests` 解析成环境中的同名第三方 package，而不是本仓库测试目录。
证据：
- `python3 -m unittest tests/test_harness_observe.py` → `ModuleNotFoundError: No module named 'tests.test_harness_observe'`
- 当前仓库原先没有 `tests/__init__.py`
建议方案（请 Planner 裁决）：
A. 增加空的 `tests/__init__.py`，保留锁定命令
B. 修改完成判定为 unittest discover
C. 当前 plan 实际可行，是 Executor 误读

Planner 回复：采用 A；这是测试入口兼容文件，不改变产品范围、依赖或运行时设计，已在步骤 4 和文件契约中保留修订记录。

## Post-delivery Review — 2026-08-10 22:10

- symptom: `http://127.0.0.1:4317/` could not connect after V0 delivery.
- root cause: no `watch` process was running, and the user-facing `harness` command still pointed to an older `~/.mick-harness` installation without the observe route.
- files: `tests/test_harness_observe.py`; installed runtime `/Users/mickmi/.mick-harness/bin/harness`, `/Users/mickmi/.mick-harness/scripts/harness-observe.py`, `/Users/mickmi/.mick-harness/web/observe-dashboard.html`
- verify: installed `harness observe --help` passed; installed `harness observe watch` is listening on `127.0.0.1:4317`; `/healthz`, `/`, and `/api/index.json` returned 200; `python3 -B -m unittest tests/test_harness_observe.py` passed (9 tests, 0 failures, exit 0)
- automation: added a CLI routing regression test so source-level removal of the `observe` command fails the suite.

## Phase 2：Global Portfolio 与 Agent Activity

### 新目标

让一个 Dashboard 汇总所有通过 `harness init` 注册的项目，明确显示项目有效性、当前阶段、任务进度、验证、阻塞和 Agent 活动；Codex 通过官方 lifecycle Hook 显式回写 session/turn 状态，不读取聊天正文或私有数据库。

### 新约束

- `harness observe watch` 保持当前单项目行为；新增 `--all` 启用全局 Portfolio。
- 项目来源只读取 Harness registry；不存在、未注入 Harness 或不可读的目录保留为 invalid 项目，不静默丢失。
- Portfolio API 不接受任意文件系统路径；project id 必须解析到 registry 中的项目。
- 阶段优先级：`STATE*.md` 当前阶段 > `plan.md` 状态行 > 任务推断。
- Codex Hook 只保存 `session_id`、`turn_id`、`cwd` 对应的 project id、事件状态和时间；不保存 prompt、assistant message、transcript 或 model。
- Hook 配置只生成可审查片段，不自动修改 `~/.codex/hooks.json`；用户信任后才启用。

### 新文件级契约

- `scripts/harness-observe.py`：新增 registry validation、portfolio projection、project-scoped API、plan stage 投影和 agent activity projector。
- `scripts/harness-observe-hook.py`：读取 Codex Hook stdin JSON，验证 cwd 已注入 Harness，再向对应项目追加脱敏 activity 事件。
- `docs/runtime-event-v0.schema.json`：增加 `agent.session_observed`、`agent.turn_observed` 事件契约。
- `web/observe-dashboard.html`：新增 Portfolio 总览、项目选择器、项目阶段与 Agent activity 指标；URL 新增 `project` 参数。
- `bin/harness`：`observe watch --all` 透传；新增 `observe hook-config codex` 输出可审查配置。
- `tests/test_harness_observe.py`：覆盖 registry valid/invalid、跨项目路由、阶段优先级、Hook 脱敏和 CLI。
- `docs/OBSERVE.md`、`README.md`：补充全局看板与 Codex Hook 的权限/信任边界。

### 新步骤

- [x] 8. 扩展事件与 Portfolio 数据契约，补 registry / stage / hook 测试骨架。
- [x] 9. 实现注册项目校验、Portfolio 聚合和 project-scoped 只读 API。
- [x] 10. 实现 `plan.md` / `STATE` 阶段优先级和 Agent activity 投影。
- [x] 11. 升级 Dashboard 为 Portfolio 总览、项目切换和 Agent activity 视图。
- [x] 12. 实现 Codex Hook 脱敏回写适配器与可审查配置输出。
- [x] 13. 更新文档和安装版，完成多项目、Hook、HTTP、刷新恢复与全量回归验证。

### Phase 2 完成判定

- [x] registry 中 valid、invalid、missing-Harness 项目均有明确状态和原因。
- [x] `watch --all` 的 Portfolio API 只能访问 registry 内项目，未知 project id 返回 404。
- [x] Dashboard 可切换项目，URL 刷新后恢复 `project/run/view/task`。
- [x] 项目卡显示阶段、当前角色、任务完成率、阻塞、待验证和 Agent 活动。
- [x] Codex Hook 输入不把 prompt、assistant message、transcript 或 model 写入 ledger。
- [x] SessionStart/UserPromptSubmit/Stop/SessionEnd 可形成 session/turn 状态往返。
- [x] 现有单项目 API、只读 405、replay 与 9 项 baseline 不回归。
- [x] 安装版 `harness observe watch --all` 与 `harness observe hook-config codex` 可运行。

### Step 8 — 2026-08-10 22:23
- files: `docs/runtime-event-v0.schema.json`, `tests/test_harness_observe.py`, `plan.md`
- verify: JSON parse passed; schema contract reports 15 event types including agent session/turn; registry, stage-priority, and Hook-redaction test cases added
- notes: Hook payload intentionally excludes prompt, response, transcript path, and model.

### Step 9 — 2026-08-10 22:27
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: registry and stage probes passed; Portfolio HTTP test passed with valid + missing projects, registered project index 200, unknown project id 404
- notes: project ids now hash canonical paths so macOS `/var` and `/private/var` aliases do not duplicate projects.

### Step 10 — 2026-08-10 22:29
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: plan-header stage, STATE-over-plan priority, and existing idempotent sync tests passed (3 tests, 0 failures)
- notes: legacy plans without a status line infer execution/completion at confidence 0.8; agent activity is projected separately from plan task completion.

### Step 11 — 2026-08-10 22:32
- files: `web/observe-dashboard.html`, `plan.md`
- verify: HTML parser accepted the document and extracted JavaScript passed `node --check`
- notes: Portfolio overview shows valid/invalid projects; project-scoped URLs persist `project/run/view/task`; agent sessions render in a separate lane.

### Step 12 — 2026-08-10 22:35
- files: `scripts/harness-observe.py`, `scripts/harness-observe-hook.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: redaction, session/turn lifecycle round-trip, reviewable Hook JSON, and top-level CLI routing tests passed (4 tests, 0 failures)
- notes: Hook errors are advisory and never block Codex; Stop returns `{\"continue\": true}` as required by the lifecycle contract.

### Step 13 — 2026-08-10 22:39
- files: `README.md`, `docs/OBSERVE.md`, `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`; installed runtime under `/Users/mickmi/.mick-harness`
- verify: 19 unittests passed; shell/Python/JSON/HTML/JavaScript/generate/diff checks passed; real registry returned 5 projects (4 valid, 1 missing); `mick_harness_rules` resolved to Reviewer, 13/13 tasks; final Portfolio and Dashboard returned 200, POST returned 405; installed runtime/hook/dashboard checksums match source
- notes: Numbered plan steps are the only task source; legacy completion-criteria tasks are marked abandoned and excluded, with a versioned collector signature forcing one safe re-import after parser upgrades. The live service runs `harness observe watch --all` on PID 86441. Browser automation policy still prevents DOM control of localhost, so refresh/click visual QA remains user-confirmed rather than automated.

### Step 14 — 2026-08-11 11:17
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`; installed Dashboard under `/Users/mickmi/.mick-harness`
- verify: 20 unittests passed (0 failures); Dashboard JavaScript syntax passed; live 4317 HTML contains retry/reconnect controls; Portfolio API and page returned 200; source and installed Dashboard match; generate and diff checks passed
- notes: A transient localhost fetch failure previously left the one-shot loader permanently stuck. Network requests now retry three times and the error state provides a manual reconnect action plus the exact service command. The regression contract is automated in `test_dashboard_can_recover_from_transient_network_failure`.

## Phase 3：Mick Harness Observer 产品化

### 新目标

把临时 `watch` 进程升级为稳定的本地产品服务 **Mick Harness Observer**：由 macOS `launchd` 自动启动和保活，持续扫描全部已注册 Harness 项目；每次本地调用 `harness` 都把脱敏的命令生命周期回写到项目事件账本，并通过固定 localhost 端口提供 Dashboard 和健康状态。

### 新约束

- 服务名固定为 `Mick Harness Observer`，LaunchAgent label 固定为 `com.mick.harness.observer`。
- 默认监听 `127.0.0.1:6425`；`6425` 当前未在 IANA Service Name and Transport Protocol Port Number Registry 中登记，且不属于动态端口区间。旧 `4317` 只作为迁移说明。
- LaunchAgent 只安装到当前用户域，不使用 `sudo`；`RunAtLoad` 与 `KeepAlive` 开启，日志写入 Harness state 目录。
- 后端每 2 秒扫描 registry 中的 valid 项目；单项目同步失败只更新服务告警，不终止服务。
- CLI 回写只保存命令名、cwd 对应项目、开始/结束状态、时间和退出码；不保存参数、Prompt、环境变量或命令输出。
- CLI 回写为 best-effort，任何 Observer 故障不得改变原 Harness 命令退出码。
- 继续只绑定 localhost，HTTP mutation 保持 405，不引入第三方依赖。
- Dashboard URL 指向 missing/invalid 项目时自动回到 Portfolio 总览并显示说明。

### 新文件级契约

- `scripts/harness-observe.py`：新增产品常量、持续扫描线程、服务健康状态、Harness CLI activity 事件、LaunchAgent install/start/stop/restart/status/uninstall 命令。
- `bin/harness`：在每次命令入口和退出时 best-effort 调用 Observer activity，不记录参数；`harness observe service ...` 透传服务生命周期命令。
- `docs/runtime-event-v0.schema.json`：增加 `harness.command_observed` 事件类型与最小 payload 契约。
- `web/observe-dashboard.html`：默认服务提示改为 `6425`；失效 URL 自动回到总览并提示原因。
- `tests/test_harness_observe.py`：覆盖端口/服务契约、持续扫描容错、CLI activity 脱敏、LaunchAgent plist、失效 URL 回退和现有只读 HTTP 行为。
- `docs/OBSERVE.md`、`README.md`：把后台服务安装、生命周期、日志、健康检查、迁移与故障恢复写成正式产品说明。

### 新步骤

- [x] 15. 增加 Phase 3 失败用例和事件 schema 契约。
- [x] 16. 实现 Observer 持续扫描、健康状态和固定 `6425` 服务端口。
- [x] 17. 实现 Harness CLI 命令生命周期脱敏回写。
- [x] 18. 实现 macOS LaunchAgent 生命周期管理。
- [x] 19. 实现 Dashboard 失效 URL 回退与产品化服务提示。
- [x] 20. 更新文档、同步安装版并完成安装/重启/回写/页面端到端验证。

### Phase 3 完成判定

- [x] `harness observe service install` 后 `launchctl` 显示 `com.mick.harness.observer`，退出终端后服务仍监听 `127.0.0.1:6425`。
- [x] `GET /healthz` 返回服务名、端口、启动时间、最近扫描、项目数和最近错误；页面与 Portfolio API 返回 200，POST 返回 405。
- [x] 修改任一已注册项目的 Harness 状态源后，无需打开页面也会在后台扫描周期内反映到 snapshot。
- [x] 在已注入项目中执行 Harness 命令会产生 started/completed activity，原命令退出码不变，ledger 不含参数和输出。
- [x] URL 指向 missing 项目时自动回到 Portfolio 总览并保留可见提示。
- [x] `service restart` 后 PID 变化且健康检查恢复；日志和状态命令能定位失败。
- [x] 全量单元测试、Shell/Python/JSON/HTML/JavaScript、generate、diff 与真实端到端检查通过。

### Step 15 — 2026-08-11
- files: `docs/runtime-event-v0.schema.json`, `tests/test_harness_observe.py`, `plan.md`
- verify: passed — Phase 3 red baseline exposed the expected 8 unmet service contracts, and the final suite passed 29 tests with all new contracts green
- notes: Added `harness.command_observed` without command arguments or output; port selection was checked against the current IANA registry and local listeners.

### Step 16 — 2026-08-11 19:59
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: passed — background monitor test changed plan state and observed a completed snapshot without any Dashboard/API refresh; health contract returned service identity, port and scan state
- notes: `ThreadingHTTPServer` remains localhost-only; scan failures degrade health but do not terminate the process.

### Step 17 — 2026-08-11 19:59
- files: `scripts/harness-observe.py`, `bin/harness`, `docs/runtime-event-v0.schema.json`, `tests/test_harness_observe.py`, `plan.md`
- verify: direct and end-to-end CLI activity tests passed; started/completed events projected correctly; a supplied secret argument was absent from the ledger; original command exit remained 0
- notes: CLI instrumentation is best-effort and can be disabled with `MICK_HARNESS_ACTIVITY=0` for isolated tests.

### Step 18 — 2026-08-11 19:59
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: LaunchAgent contract test passed with label, `RunAtLoad`, `KeepAlive`, port 6425, global watch arguments and state-directory logs
- notes: Lifecycle commands are install/start/stop/restart/status/logs/uninstall; real user-domain installation is reserved for Step 20 end-to-end verification.

### Step 19 — 2026-08-11 19:59
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: invalid URL fallback and 6425 service guidance contract passed; full suite passed 26 tests with 0 failures
- notes: Harness command activity is visible as a dedicated lane and metric; manual selection of an invalid project still shows its validation reason.

### Step 20 — 2026-08-11 20:08
- files: `README.md`, `docs/OBSERVE.md`, `bin/harness`, `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`; installed runtime and LaunchAgent under the user account
- verify: 29 unittests passed; Bash/Python/JSON/JavaScript/generate/diff checks passed; service install returned installed/loaded/healthy; restart changed PID 43238 → 44914 → 50844; health reported 4/5 valid projects, 128 ms scan and no error; page/API returned 200 and POST returned 405; real `harness version` activity projected completed/0 and discarded its argument
- notes: Browser automation policy blocked navigation from the built-in localhost error page, so the HTTP/UI contract is automated and the final rendered visual remains a manual user confirmation at `http://127.0.0.1:6425/`. Client disconnects are treated as normal and covered by a regression test instead of polluting service logs.

## Phase 4：简化需求导航 V1

### 新目标

把 Dashboard 从面向内部的监控页改成用户可感知的项目导航页：用户进入项目后只需要看到总体目标、Plan 拆出的需求、当前负责人、`定义 → 实现 → 验证 → 交付` 四个关键节点、阻塞和下一步；原始事件与时间线退到“技术记录”，不再作为默认入口。

用户已在 2026-08-12 明确选择“先试试”的轻量实现，本阶段不制作独立设计稿，也不建设角色工作台、复杂文档目录或模拟经营系统。

### 新约束

- 默认项目视图固定为 `overview`（需求导航）；旧 `graph` URL 兼容迁移到 `overview`，`timeline` / `events` 保留在“技术记录”。
- Plan 解析同时支持 Harness checkbox 步骤与 `## Steps` / `## 步骤` 下的普通编号步骤；不能把完成判定等其他编号列表误识别为需求。
- 总体目标只从 `## Objective` / `## 目标` 的首段提取；没有明确目标时显示缺失，不使用 AI 猜测。
- 普通编号 Plan 的当前项优先读取 `Current step: N / M`；在当前项之前显示完成、当前项显示进行中、之后显示待开始。
- 四节点是用户语言投影，不新增自动调度：任务进行中对应实现，待验证对应验证，完成对应交付；角色只在真实阶段需要时显示。
- 关键资料 V1 只展示已观察到的 Plan / STATE / 验证证据，不开放任意文件系统读取接口。
- 继续不保存 Prompt、聊天全文、命令参数或完整日志；不新增第三方依赖，不开放 mutation endpoint。

### 新文件级契约

- `docs/runtime-event-v0.schema.json`：新增 `plan.summary_observed` 与 `plan` subject，payload 只包含标题、总体目标、当前需求和来源路径。
- `scripts/harness-observe.py`：新增纯函数 `parse_plan_steps()` 与 `parse_plan_summary()`；Collector 将两种步骤格式投影成既有 task，并把 Plan 摘要投影到 snapshot `plan`。
- `web/observe-dashboard.html`：新增默认需求导航、总体目标卡、需求列表、四节点进度和“需要你处理”；技术记录保留时间线与事件表。
- `tests/test_harness_observe.py`：覆盖 RaliTennis 风格 Plan 的 3/5 投影、目标提取、非 Steps 编号排除、Dashboard 默认视图与关键节点文案。
- `docs/OBSERVE.md`、`README.md`：将用户入口描述改为需求导航，说明技术记录和推断边界。

### 新步骤

- [x] 21. 增加 Phase 4 失败用例与 `plan.summary_observed` schema 契约，固定 RaliTennis 风格 Plan 的期望投影。
- [x] 22. 实现 Plan 语义解析、摘要事件、任务状态与 snapshot 投影，并确保旧 checkbox Plan 不回归。
- [x] 23. 将 Dashboard 项目默认页改成简化需求导航，保留技术记录与 URL 刷新恢复。
- [x] 24. 更新产品文档、同步安装版，并让后台服务重新载入新运行时。
- [x] 25. 运行全量回归、真实 RaliTennis 同步和浏览器端到端验证，记录页面状态、交互与刷新证据。

### Phase 4 完成判定

- [x] RaliTennis snapshot 显示总体目标、5 条需求、当前第 3 条；前 2 条完成、第 3 条进行中、后 2 条待开始。
- [x] 项目默认页面首屏显示总体目标、需求进度和需要用户处理的阻塞，不显示原始事件指标。
- [x] 当前需求卡显示 `定义 → 实现 → 验证 → 交付`，并高亮真实当前节点与负责人。
- [x] timeline / events 仍可访问，旧 `view=graph` URL 自动显示需求导航，刷新后选择保持。
- [x] 旧 checkbox Plan、STATE 优先级、Hook 脱敏、只读 HTTP 和后台服务测试不回归。
- [x] 源码与安装版校验一致；重启服务后 `healthz`、页面和 Portfolio API 返回 200。
- [x] 真实浏览器完成项目进入、需求选择、技术记录切换和刷新恢复检查。

### Step 21 — 2026-08-12
- files: `docs/runtime-event-v0.schema.json`, `tests/test_harness_observe.py`, `plan.md`
- verify: `python3 -m json.tool docs/runtime-event-v0.schema.json` exit 0；Phase 4 聚焦测试按预期红灯，分别暴露缺少 snapshot `plan` 投影和 Dashboard 默认 `overview` 视图
- notes: 失败用例使用与真实 RaliTennis 相同的 `Current step: 3 / 5` + `## Steps` 编号格式，并验证其他编号章节不会被误识别。

### Step 22 — 2026-08-12
- files: `scripts/harness-observe.py`, `docs/runtime-event-v0.schema.json`, `plan.md`
- verify: `python3 -B -m unittest` 聚焦运行编号 Plan、checkbox Plan、待验证与非 Steps 排除共 4 项，全部通过；Python 编译首次因仓库禁止写 `__pycache__` 被环境阻止，已保留到最终验证用临时缓存路径复跑
- notes: Collector 升级到 0.3.0；总体目标缺失时保持空值，普通编号 Plan 只解析 `## Steps` / `## 步骤`，不猜测其他章节。

### Step 23 — 2026-08-12
- files: `web/observe-dashboard.html`, `plan.md`
- verify: inline JavaScript 通过 Node 语法解析；Phase 4 Dashboard 契约、编号 Plan、重连与失效 URL 共 4 项聚焦测试通过
- notes: 默认视图改为 `overview`，旧 `graph` 自动兼容；主页面去除 Agent/Harness 原始指标，只保留总体目标、需求进度、待处理和四节点详情。

### Step 24 — 2026-08-12
- files: `docs/OBSERVE.md`, `README.md`, `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`; installed runtime under `/Users/mickmi/.mick-harness`
- verify: 源码与安装版 5 个文件 SHA-1 逐对一致；服务重启后 PID 41434，`health.status=ok`、4/5 项目有效、4 个项目同步、`last_scan_error=null`
- notes: 首次重启由真实健康检查发现 block 解析覆盖 Plan 摘要，新增回归后修复并再次重启恢复健康；没有把降级状态当作完成。

### Step 25 — 2026-08-12
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`; installed runtime and live service
- verify: 32 个 unittest 通过、0 failures、exit 0；Bash/Python/JSON/JavaScript、`generate.sh --check`、`git diff --check` 均 exit 0；服务 `health.status=ok`、页面/Portfolio/Rali snapshot 均 HTTP 200
- notes: 真实 RaliTennis 显示总体目标、2/5 已交付、当前 Watch-only 第 3 条、5 条需求和四节点；浏览器选择需求 4、切换技术记录、刷新后保持 `view=timeline&task=task-4`，最终返回 `overview&task=task-3`。真实验证还发现已裁决阻塞的 import-cache 迁移问题，已用 Collector 0.3.1 安全重导入并新增回归，最终 `active_blocks=0`。

## Phase 5：Meek Harness 本地工作服务器

### 新目标

把 Mick Harness Observer 从“扫描项目文件的只读看板”升级为安装 Harness 后持续运行的本地工作服务器：项目注入负责给 AI Agent 加载规则并回写结构化工作事件；常驻服务负责接收、校验、持久化和聚合所有已注册项目；统一工作台以真实事件展示需求进度、角色工作轮次、决策和交付物。

用户已在 2026-08-12 明确确认该双层产品模型并要求开始实现。默认保存结构化工作摘要，不保存 Prompt、聊天全文、assistant message 或 transcript。

### 新约束

- 保留 `127.0.0.1:6425`、LaunchAgent、registry、项目内 append-only ledger 和定时扫描，不引入第三方依赖。
- mutation 只开放 `POST /api/v1/events`；其他 POST、PUT、PATCH、DELETE 继续返回 405。
- 接收接口只接受 registry 中 validation=valid 的 project id；不接受客户端提交的任意文件系统路径。
- 接口使用 Observer state 目录内 mode `0600` 的随机 token；Bearer token 错误返回 401，JSON/Schema 错误返回 400/413/415/422。
- Agent 与 CLI 优先向常驻服务提交；服务不可达时回退到项目本地账本，不能改变原 Agent 或 Harness 命令退出状态。
- 默认事件只包含目标、角色、动作摘要、决策、交付物相对路径、验证、阻塞和下一角色；不采集完整对话正文、命令参数、环境变量或完整日志。
- Dashboard 的角色归属只来自真实 work round / handoff；没有真实角色事件时明确显示“尚未回写”，不再根据完成或待验证状态猜测角色。
- 文档内容读取不在本阶段开放；工作台只展示已记录资料的名称、相对路径、摘要与存在状态，避免把事件接收升级扩大成任意文件浏览器。

### 文件级 API 契约

- `docs/runtime-event-v0.schema.json`：新增 `work.round_started`、`work.round_completed`、`decision.recorded`、`handoff.created` 及对应 payload；artifact 增加可选标题、摘要、角色与任务关联。
- `scripts/harness-observe.py`：新增 token 管理、事件 envelope 校验、`POST /api/v1/events`、通用 `emit` CLI、HTTP 优先/本地回退、work/decision/handoff snapshot 投影和健康指标。
- `scripts/harness-observe-hook.py`：Agent lifecycle 通过本地接收接口回写，服务不可达时使用现有本地写入降级；继续丢弃聊天正文和 transcript。
- `bin/harness`：现有命令生命周期改为调用服务接收链路；帮助中增加 `harness observe emit` 入口。
- `.harness/rules/core.md`：交付回合在本机提供 Harness CLI 时，要求 best-effort 发送结构化 `work.round_completed`，并明确回写失败不阻塞任务。
- `web/observe-dashboard.html`：Portfolio 显示真实活跃角色与最近工作；项目页增加角色工作轮次、关键决策和交接，角色与需求使用真实关联。
- `tests/test_harness_observe.py`：覆盖鉴权、项目范围、Schema、幂等、服务接收、离线降级、Hook 脱敏、角色投影、跨项目聚合、重启恢复和旧只读路由。
- `docs/OBSERVE.md`、`README.md`、`docs/FEATURES.md`：更新双层架构、自动回写边界、Agent 接入、隐私、故障恢复和用户可见能力状态。

### 新步骤

- [x] 26. [修改] `tests/test_harness_observe.py` — 增加 Phase 5 接收服务、鉴权、事件投影、离线降级和工作台契约的失败用例，并保留 32 项 baseline。
- [x] 27. [修改] `docs/runtime-event-v0.schema.json` — 固定 work round、decision、handoff 和扩展 artifact 的结构化事件契约。
- [x] 28. [修改] `scripts/harness-observe.py` — 实现 token、单一接收接口、通用 emit、HTTP 优先/本地回退、幂等持久化和新 snapshot 投影。
- [x] 29. [修改] `scripts/harness-observe-hook.py` — 将 Agent lifecycle 接到常驻服务并验证脱敏与离线降级。
- [x] 30. [修改] `bin/harness` — 将 Harness 命令 activity 接到服务链路并公开结构化 emit 帮助。
- [x] 31. [修改] `rules/core.md` — 把交付回合的结构化回写加入注入规则，再运行生成器同步各 Agent 入口。
  > ⚡ 修订：`generate.sh` 的真实 `CORE` 指向 `rules/core.md`；本步骤改为修改 `rules/core.md`，撤回误改的项目内 `.harness/rules/core.md`，再运行生成器验证 `dist/AGENTS.md` 含回写规则。
- [x] 32. [修改] `web/observe-dashboard.html` — 以真实 work round、decision、handoff 展示角色工作与项目最近活动。
- [x] 33. [修改] `docs/OBSERVE.md` — 记录本地工作服务器架构、事件协议、隐私和故障恢复。
- [x] 34. [修改] `README.md` 与 `docs/FEATURES.md` — 更新安装后的两部分能力、统一工作台入口和能力成熟度。
  > ⚡ 修订：仓库没有 `docs/FEATURES.md`，只有 `docs/FEATURES.template.md`；按模板创建正式功能清单，不修改模板。
- [x] 35. [运行] 全量验证、同步安装版、重启服务，并用两个临时项目完成接收 → 聚合 → 刷新 → 重启恢复端到端检查。
- [x] 36. [修改] `scripts/harness-audit.sh` — 修正编号步骤识别与 `0 failures` 误报，再用当前完整 plan 复跑审计。

### Phase 5 完成判定

- [x] 未授权、未知项目、非 JSON、超限 body 和非法 payload 均被拒绝且不产生 ledger 事件。
- [x] 同一个 `idempotency_key` 重复提交只写入一次，响应明确返回 appended=0。
- [x] Agent lifecycle 和 `harness observe emit` 正常路径都经过 6425 服务；服务不可达时本地降级仍留下可扫描事件。
- [x] snapshot 能投影 work rounds、decisions、handoffs，并按 requirement id 关联角色、交付物和验证。
- [x] Portfolio 能同时聚合至少两个注册项目，展示各项目真实活跃角色与最近工作摘要。
- [x] 服务重启后项目、事件、角色和决策仍可读取，浏览器刷新不丢失当前项目选择。
- [x] ledger、日志和 snapshot 不含测试注入的 prompt、assistant message、transcript、secret 或命令参数。
- [x] 旧 GET/HEAD 路由保持可用；除 `/api/v1/events` 外所有 mutation endpoint 继续返回 405。
- [x] 全量 unittest、Shell/Python/JSON/HTML/JavaScript、generate、diff 和真实 LaunchAgent 健康检查通过。

### Phase 5 Preflight

- 当前 baseline：32 个 unittest 全部通过；真实 `com.mick.harness.observer` 已安装、loaded、healthy，监听 `127.0.0.1:6425`，registry 有 5 个项目，其中 4 个有效。
- 真实状态源：项目 `events.jsonl` 是历史事实源，`snapshot.json` 是可重放投影，`/healthz` 是服务状态源，Dashboard 只消费服务 API。
- 权限：开发改动位于 Harness 源仓库；安装版与 LaunchAgent 只在 Step 35 同步和重启，不使用 sudo。
- 回滚：接收接口可通过回退到上一安装版关闭；既有 ledger 保持向后兼容，新事件不会修改项目业务文件。

### Phase 5 Interaction QA

- 用户路径：安装 Harness → init 两个项目 → Agent 开始/完成工作 → 统一工作台出现两个项目和真实角色活动 → 打开项目查看需求关联、决策与交接 → 刷新和重启后仍存在。
- 失败路径：服务停止时 Agent 正常结束且事件本地保存；服务恢复后扫描可见；token 错误在控制台外明确返回未授权，不把请求写入项目。
- 状态一致性：工作台的角色、进度和交接必须能追溯到事件 sequence；没有真实回写时显示缺失，不做启发式角色映射。

### Step 26 — 2026-08-12
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 改动前 32 个 unittest 全部通过；Phase 5 的 5 个聚焦契约按预期红灯，暴露缺少四类事件、token、服务接收/离线降级和真实角色 UI
- notes: HTTP 用例同时固定了 401、404、422、幂等 appended=0、旧 mutation 405 和敏感字段不落盘。

### Step 27 — 2026-08-12
- files: `docs/runtime-event-v0.schema.json`, `plan.md`
- verify: `python3 -m json.tool docs/runtime-event-v0.schema.json` exit 0；schema 包含 4 类新事件、3 类新 subject、role 定义和扩展 artifact 字段
- notes: 结构化摘要上限固定为 4000 字符；默认事件契约没有 Prompt、assistant message 或 transcript 字段。

### Step 28 — 2026-08-12
- files: `scripts/harness-observe.py`, `plan.md`
- verify: Phase 5 的 token、work projection、离线降级和 HTTP 接收 4 项聚焦测试全部通过；服务验证了 Bearer 鉴权、registry 范围、幂等与敏感字段拒绝
- notes: 只开放 `POST /api/v1/events`；token 文件固定 mode 0600；客户端正常走服务，连接失败才直接写项目 append-only ledger。

### Step 29 — 2026-08-12
- files: `scripts/harness-observe-hook.py`, `scripts/harness-observe.py`, `plan.md`
- verify: Codex Hook 脱敏、session/turn 往返和离线回退 3 项聚焦测试通过；测试数据中的 Prompt、assistant message、transcript 和 model 仍未写入 ledger
- notes: 开发期间真实运行的旧 6425 服务返回 405，客户端识别为旧版本并降级本地账本；新服务安装后会自动改走接收接口。

### Step 30 — 2026-08-12
- files: `bin/harness`, `plan.md`
- verify: `bash -n bin/harness` exit 0；`harness observe emit --help` exit 0 并列出 work round、decision、handoff 四类结构化回写及角色/需求参数
- notes: 原 Harness 命令 activity 仍保持 best-effort 和原退出码，现在由 Python 接收客户端优先提交到 6425 服务。

## 阻塞 #2（步骤 31）
发现：计划把 `.harness/rules/core.md` 当作生成器单一来源，但真实生成器读取 `rules/core.md`，导致首次 generate 成功却没有把回写规则写入 `dist/AGENTS.md`。
证据：
- `generate.sh` 中 `CORE="$HARNESS_ROOT/rules/core.md"`
- `rg "本地工作服务器回写" dist/AGENTS.md` 无匹配，而 `.harness/rules/core.md` 有匹配
建议方案（请 Planner 裁决）：采用真实生成入口 `rules/core.md`，撤回本轮对 `.harness/rules/core.md` 的误改并重新生成。

Planner 回复：采用建议方案；这是对既有生成器事实的纠正，不改变 Phase 5 产品范围、隐私边界或验收标准，已在步骤 31 下保留修订记录。

### Step 31 — 2026-08-12
- files: `rules/core.md`, `dist/AGENTS.md`, `plan.md`
- verify: `./generate.sh` 与 `./generate.sh --check` exit 0；`rules/core.md` 和 `dist/AGENTS.md` 均能定位“本地工作服务器回写”规则
- notes: 首次按错误路径生成未生效，已通过阻塞 #2 的 Planner 修订纠正；项目内 `.harness/rules/core.md` 已恢复，不保留重复规则源。

### Step 32 — 2026-08-12
- files: `web/observe-dashboard.html`, `plan.md`
- verify: 真实角色工作 Dashboard 契约与既有需求导航/重连 3 项测试通过；内联 JavaScript 经 Node 解析通过
- notes: 项目总览增加最近角色工作，项目页增加角色工作、关键决策、角色交接；需求负责人只读取 work round / handoff，没有数据时明确显示“尚未回写”。

### Step 33 — 2026-08-12
- files: `docs/OBSERVE.md`, `plan.md`
- verify: 文档代码围栏平衡，且双层数据流、`POST /api/v1/events`、`work.round_completed`、token 和 local-fallback 契约检查通过
- notes: 文档已从“只读 Observer”改为“项目注入 + 本地工作服务器 + 统一工作台”，同时保留不自动编排、不保存聊天全文的边界。

## 阻塞 #3（步骤 34）
发现：计划要求更新 `docs/FEATURES.md`，但该文件不存在，仓库只有 `docs/FEATURES.template.md`。
证据：`ls docs/FEATURES.md docs/FEATURES.template.md` 返回前者不存在、后者存在。
建议方案（请 Planner 裁决）：以现有模板为格式创建 `docs/FEATURES.md`，记录当前用户可见能力和成熟度，不修改模板。

Planner 回复：采用建议方案；正式能力清单属于本阶段约定的用户可见交付，不扩大产品功能范围。

### Step 34 — 2026-08-12
- files: `README.md`, `docs/FEATURES.md`, `plan.md`
- verify: README 的五层架构、统一工作台和 emit 命令契约检查通过；正式功能清单包含跨项目总览、真实角色回写、资料阅读缺口和非目标
- notes: `docs/FEATURES.md` 按既有模板新建；角色回写标为“需调整”，因为不同 Agent 的 Hook 能力和规则遵守度仍是现实边界。

### Step 35 — 2026-08-12
- files: source and installed runtime files, temporary project ledgers, `plan.md`
- verify: 37 个 unittest、Shell/Python/JSON/JavaScript、generate、diff 全部 exit 0；服务 PID 282→3770 后 health=ok；两个项目经 service transport 聚合为 QA/PM，重复提交 appended=0，重启和浏览器刷新后角色、决策、交接与 URL 均恢复
- notes: 源码与安装版 10 个文件 checksum 一致；两个临时项目已从正式 registry 移除，最终服务恢复 5 个登记项目、4 个有效项目。

## 阻塞 #4（步骤 36）
发现：`harness-audit.sh` 把 Phase 完成判定的普通 checkbox 当作 Plan 步骤，并把 `0 failures` 中的 `failures` 当作失败证据。
证据：当前 plan 有 34 个已完成编号步骤和 34 个自检日志，但 audit 报 41 对 34；失败匹配发生在含 `0 failures` 的验证行。
建议方案（请 Planner 裁决）：步骤正则只接受编号/层级编号，失败判断先移除 `0 failure(s)` 与 `no failures` 再匹配真实失败。

Planner 回复：采用建议方案；这修复的是本轮真实执行触发的错误门禁，不改变工作服务器功能范围。

### Step 36 — 2026-08-12
- files: `scripts/harness-audit.sh`, `plan.md`; installed audit runtime
- verify: 当前完整 plan 的 Harness Audit 从 2 FAIL 修复为 7 PASS、1 WARN、0 FAIL；编号步骤与自检日志覆盖一致，`0 failures` 不再误报
- notes: 剩余 scope warning 来自工作树中未纳入本 plan 的既有文件变化，审计没有自动清理或覆盖这些用户改动。

## Phase 6：产物阅读与 PM 版本工作台

### 新目标

让用户在统一工作台内直接阅读 Agent 产物，并用非 Git 专业语言理解“版本要做什么、需求放在哪个版本、真实分支和发布状态是什么”。Markdown 以阅读器展示，代码以可折叠、可滚动的源文本展示；PM 通过项目内 `docs/VERSIONS.md` 维护版本范围，工作台将其与真实 Git 分支、标签和未提交改动对照展示。

### 新约束

- 产物读取只允许 registry 中有效项目，且路径必须已被 snapshot artifact、work round `artifact_refs` 或版本规划显式记录。
- 路径必须是项目根内的实际普通文件；拒绝绝对路径、`..`、越界 symlink、二进制文件和超过 512 KiB 的文件。
- 工作台只读 Git 信息，不在浏览器内创建/切换/删除分支，不 commit、merge、tag 或 push。
- `docs/VERSIONS.md` 是 PM 的人类可读版本计划事实源；Git 是分支、标签、HEAD 和工作树状态的事实源，两者矛盾时工作台明确标出，不自动修复。
- 项目没有 Git 或没有 `docs/VERSIONS.md` 时显示可理解空态，不伪造版本或分支。
- 不引入第三方依赖；后端继续使用 Python 标准库，前端使用安全 DOM 构建，不把 Markdown 作为 raw HTML 注入。
- 保留当前只读 Dashboard 和唯一事件回写接口边界；本阶段不新增 Git mutation endpoint。

### 文件级 API 契约

- `scripts/harness-observe.py`：新增安全产物授权/读取、Git 只读概要、`docs/VERSIONS.md` 解析、workspace API，并让 emit CLI 支持重复 `--artifact <relative-path>`。
- `web/observe-dashboard.html`：新增“产物”和“版本规划”视图，Markdown 阅读器、代码折叠滚动阅读器、版本需求清单、真实分支/标签对照和不一致提示。
- `tests/test_harness_observe.py`：增加路径越界、未授权文件、Markdown/Python 内容、Git 分支/标签、版本规划解析、Dashboard 安全渲染和 URL 恢复契约。
- `rules/roles/pm.md`：新增 PM 版本管理职责，要求使用 `docs/VERSIONS.md` 记录版本目标、真实分支、需求归属和变更原因。
- `rules/core.md`：执行回写发生交付物时同步携带项目相对路径，不回写文件正文。
- `docs/VERSIONS.md`：作为当前 Harness 项目的首份 PM 版本计划及解析格式参考。
- `docs/OBSERVE.md`、`README.md`、`docs/FEATURES.md`：更新产物阅读、版本可视化、只读 Git 边界与使用方式。

### 新步骤

- [x] 37. [修改] `tests/test_harness_observe.py` — 增加 Phase 6 产物内容、安全路径、Git/版本投影和 Dashboard 契约红灯用例，并隔离现有 CLI activity 测试与真实 6425 服务。
  - 红灯契约已固定：后端缺少 `artifact_refs`/workspace 投影，前端缺少产物与版本视图；两项聚焦用例均按预期失败。
- [x] 38. [修改] `scripts/harness-observe.py` — 实现 workspace snapshot、安全产物读取 API、Git 只读状态、版本计划解析与 emit `--artifact`。
  - 已增加 512 KiB UTF-8 文本上限、项目内路径与显式产物授权，以及 `workspace.json`/`artifact` 只读路由。
- [x] 39. [修改] `web/observe-dashboard.html` — 实现产物阅读器、版本路线与真实 Git 分支视图，保留 URL 状态和失败反馈。
  - 已新增“产物”/“版本规划”页签，安全 DOM Markdown 解析、可折叠行号代码阅读、版本需求和 Git 对照卡。
- [x] 40. [修改] `rules/roles/pm.md` — 增加 PM 版本分期、需求迁移和 Git 对照职责。
  - PM 现在先定义版本目标，再分配需求；需求跨版本需记录原因，Git 变更仍需用户授权后由 Executor 执行。
- [x] 41. [修改] `rules/core.md` — 交付回写时要求将产物相对路径加入 `artifact_refs`，不携带正文。
  - 交付回合产生文档、代码或报告时，Agent 现在会用可重复 `--artifact` 记录项目相对路径，不将文件内容写入事件。
- [x] 42. [运行] `generate.sh` — 重新生成并验证 `dist/AGENTS.md` 含产物回写规则。
  - 生成产物已与 `rules/core.md` 同步，`--check` 通过。
- [x] 43. [创建] `docs/VERSIONS.md` — 写入 0.11.0 已发布事实与 0.12.0 工作台计划，标明需求、分支和状态。
  - 当前 Harness 已有首份可被 PM、Git 和工作台共同读取的版本路线。
- [x] 44. [修改] `docs/OBSERVE.md` — 记录产物阅读、workspace API、版本计划格式和 Git 只读边界。
- [x] 45. [修改] `README.md` — 补充统一工作台的产物阅读和版本路线入口。
- [x] 46. [修改] `docs/FEATURES.md` — 更新用户可见能力与成熟度。
- [x] 47. [运行] 全量验证、同步安装版、重启服务，并用真实浏览器完成 Markdown、Python、版本需求和分支对照端到端检查。

### Phase 6 完成判定

- [x] 点击已记录 Markdown 产物后在工作台内显示标题、段落、列表、表格和代码块，不执行文档中 HTML/Script。
- [x] 点击 Python 或其他文本代码产物后显示可折叠、可纵向/横向滚动的源码与行号，失败时显示原因。
- [x] 未登记项目、未授权路径、路径越界、越界 symlink、二进制或超限文件无法通过产物 API 读取。
- [x] 版本页能展示 `docs/VERSIONS.md` 中的每个版本目标、需求、状态与分支，并与真实 Git HEAD、local branch、tag、dirty 状态对照。
- [x] 计划分支不存在、当前工作不在规划分支、需求未分配版本时，工作台给出人类可理解的提示。
- [x] 项目没有 Git 或没有版本计划时显示明确空态，项目其他进度和角色视图不回归。
- [x] 全量 unittest、Shell/Python/JSON/JavaScript、generate、diff 和 Harness Audit 通过；安装版与源码一致，服务重启后真实浏览器路径可用。

### Phase 6 Preflight

- 当前 baseline：37 个 unittest 中 33 个在 sandbox 内通过，4 个因禁止 localhost bind 报权限错误；允许 localhost 后 35 个通过、2 个 CLI activity 用例被真实 6425 服务干扰，属测试隔离缺口。
- 真实状态源：artifact/work round snapshot 决定哪些产物可读；`docs/VERSIONS.md` 决定 PM 版本分配；Git 命令只读返回分支、tag、HEAD 和 dirty 状态。
- 权限：开发文件在 Harness 源仓库；仅 Step 47 同步安装版并重启当前用户 LaunchAgent，不使用 sudo。
- 回滚：回退 workspace/artifact GET 路由和 Dashboard 新视图即可；不修改项目 Git 或事件账本。

### Phase 6 Interaction QA

- 用户路径：选项目 → 进“产物” → 选 Markdown/Python → 阅读/折叠/滚动 → 切“版本规划” → 查 0.11/0.12 需求和真实分支/标签 → 刷新恢复选择。
- 失败路径：文件删除/超限/不可读时不显示假内容；版本规划与 Git 不一致时保留两个事实并提示 PM 处理。
- 状态一致：产物列表与 workspace API 一致；版本卡与 `docs/VERSIONS.md` 一致；分支卡与当前 Git 命令输出一致。

### Step 37 — 2026-08-12
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: Phase 6 两项聚焦用例按预期红灯；后端报 `build_work_envelope()` 不支持 `artifact_refs`，Dashboard 报缺少“版本规划”及阅读器契约
- notes: 同时将两个 CLI activity 测试固定到不可达端口，避免真实 6425 服务干扰临时项目的本地降级断言。

### Step 38 — 2026-08-12
- files: `scripts/harness-observe.py`, `plan.md`
- verify: workspace/Git/版本/产物聚焦用例与两项 CLI activity 隔离用例全部通过（3 tests, 0 failures）；`PYTHONPYCACHEPREFIX=/private/tmp/mick-harness-pycache python3 -m py_compile scripts/harness-observe.py` exit 0
- notes: Git 只使用 `GIT_OPTIONAL_LOCKS=0` 的只读命令；产物 API 只读 snapshot/work round/版本计划已授权的项目相对文件。

### Step 39 — 2026-08-12
- files: `web/observe-dashboard.html`, `plan.md`
- verify: Phase 6 Dashboard 契约、既有需求导航契约与重连契约共 3 项聚焦测试通过；抽取内联 JavaScript 经 `node --check` 通过
- notes: Markdown 只通过 `document.createElement`/`textContent` 生成节点，未引入 `innerHTML` 或第三方解析器；文件与版本选择写入 URL 以便刷新恢复。

### Step 40 — 2026-08-12
- files: `rules/roles/pm.md`, `plan.md`
- verify: `rg` 确认 PM 角色文件包含版本管理职责、`docs/VERSIONS.md` 事实源、需求迁移规则、Git 对照边界和可解析模板
- notes: PM 可维护版本计划，但不获得未授权的 branch/tag/push 写操作权限。

### Step 41 — 2026-08-12
- files: `rules/core.md`, `plan.md`
- verify: `rg -- '--artifact <项目相对路径>' rules/core.md` 命中本地工作服务器回写规则
- notes: 规则仅增加产物路径引用，不扩大 Prompt/对话/日志的采集边界。

### Step 42 — 2026-08-12
- files: `dist/AGENTS.md`, `plan.md`
- verify: `./generate.sh` 生成 lean AGENTS，`./generate.sh --check` 报“All generated rule files are up to date”；`rg` 在 `dist/AGENTS.md:156` 命中 `--artifact <项目相对路径>`
- notes: 首次在 sandbox 内因目标目录写权拒绝未生效，随后在获准的项目写入环境中用同一生成器完成，没有手改生成文件。

### Step 43 — 2026-08-12
- files: `docs/VERSIONS.md`, `plan.md`
- verify: 使用真实 `parse_versions_markdown()` 读取文件，返回 `0.11.0/released/main/3 requirements` 与 `0.12.0/in_progress/main/6 requirements`
- notes: 0.11.0 的 tag 与已发布状态来自现有 Git/CHANGELOG；0.12.0 只记录本轮和前置已确认工作台范围，未发散未确认后续版本。

### Step 44 — 2026-08-12
- files: `docs/OBSERVE.md`, `plan.md`
- verify: 文档覆盖 repeatable `--artifact`、两个只读 API、512 KiB/路径/类型限制、`docs/VERSIONS.md` 格式和 Git 只读边界
- notes: 产物内容按需读取原文件，不复制进事件账本；工作台不是任意磁盘浏览器。

### Step 45 — 2026-08-12
- files: `README.md`, `plan.md`
- verify: 快速使用路径包含产物回写示例、Markdown/代码阅读、PM 版本路线和真实 Git 状态说明
- notes: README 保留 Mick Agent Harness 原有定位，只扩展统一工作台的用户入口。

### Step 46 — 2026-08-12
- files: `docs/FEATURES.md`, `plan.md`
- verify: 功能清单将安全产物阅读更新为成熟，并新增 PM 版本路线与只读 Git 状态两项成熟能力
- notes: 跨机器协作和自动 Git 操作仍明确不在当前产品边界。

### Step 47 — 2026-08-12
- files: `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `docs/OBSERVE.md`, `docs/VERSIONS.md`, installed runtime, `plan.md`
- verify: 全量 unittest 39 tests / 0 failures；Shell/Python/JSON/JavaScript/generate/diff 静态检查通过；Harness Audit 8 PASS / 0 WARN / 0 FAIL；LaunchAgent 重启后 `/healthz` 为 healthy；真实浏览器完成 Markdown 阅读、Python 2881 行源码展开/折叠、0.11/0.12 版本与 main/tag/dirty 对照、URL 刷新恢复
- notes: 浏览器验收发现并修复 Markdown 粗体原样显示，以及旧 abandoned task 覆盖 PM 已完成状态两个问题；最终页面保留 PM 版本事实与实时 Git/任务事实的清晰边界。

## Phase 7：角色办公室与目标分层

### 新目标

把项目首页从“Plan 步骤监控”重构为“项目目标 → 当前版本 → 五角色办公室 → 角色执行详情与交付物”。首页只呈现用户需要把控的关键节点；Plan 技术步骤下沉到技术记录，关键决策合并进关联需求，角色交接合并进角色图谱并动态高亮真实流转。

### 新约束

- 项目长期目标、版本目标和当前需求目标必须分层展示，禁止再把 `plan.md` 第一段阶段目标标成总体目标。
- `docs/PROJECT.md` 是 PM 维护的稳定项目目标事实源；`docs/VERSIONS.md` 是版本目标和需求归属事实源；Plan 只提供执行细节。
- 首页固定五个用户角色：PM、设计、开发、测试、Review；Planner 与 Orchestrator 归入 PM 展示组，不增加第六个办公室角色。
- 角色状态只来自真实 `work.round_*`、`handoff.created` 和明确 `next_role`，不从 task status 猜角色工作。
- `handoff.created` 显示为真实交接；`next_role` 显示为建议接手。当前流转高亮，历史流转弱化，不制造不存在的并行 Agent 活动。
- “没有当前任务”必须区分“版本已交付、等待 PM”“版本尚未规划”和“确有未确认需求”，禁止统一显示“当前需求尚未确定”。
- 首页移除独立的“需求进度 / 角色工作 / 关键决策 / 角色交接”四块重复模块；版本全量需求仍保留在“版本规划”，技术步骤仍保留在“技术记录”。
- 不增加第三方前端依赖、不使用 SVG 办公室插画、不新增 Git 或工作流 mutation endpoint，继续保持 localhost 只读工作台。

### 文件级 API 契约

- `docs/PROJECT.md`（新建）：提供 `# Project Profile` 与首个 `## Goal` 段落，内容是稳定项目长期目标，不写当前版本或技术步骤。
- `scripts/harness-observe.py`（修改）：新增 `parse_project_profile(value) -> dict`、`project_profile_snapshot(project) -> dict`、`organization_snapshot(snapshot) -> dict`；workspace JSON 新增 `project` 与 `organization`，角色分组固定为 PM/Designer/Executor/QA/Reviewer。
- `web/observe-dashboard.html`（修改）：URL 新增 `role`；overview 新增项目目标、当前版本摘要、五角色办公室、当前流转和角色详情；删除旧四模块与合成的“定义/实现/验证/交付”主视图。
- `tests/test_harness_observe.py`（修改）：覆盖项目目标与阶段目标分离、五角色映射、active/waiting/completed/idle 状态、真实/建议交接、版本已交付文案、角色 URL 和旧模块移除。
- `rules/roles/pm.md`（修改）：新增 `docs/PROJECT.md` 维护职责，明确项目目标只在长期定位改变时更新，版本变化不覆盖项目目标。
- `dist/AGENTS.md`（生成）：只能由 `generate.sh` 从规则源重新生成。
- `docs/OBSERVE.md`、`README.md`、`docs/FEATURES.md`、`docs/VERSIONS.md`（修改）：更新角色办公室、目标层级、数据来源和 0.13.0 版本范围。

### 新步骤

- [x] 48. [修改] `tests/test_harness_observe.py` — 写入 Phase 7 后端与 Dashboard 红灯契约，并记录 39 项既有基线。
- [x] 49. [创建] `docs/PROJECT.md` — 写入 Mick Agent Harness 的稳定项目目标。
- [x] 50. [修改] `scripts/harness-observe.py` — 实现项目目标与五角色组织投影，接入 workspace JSON。
- [x] 51. [修改] `web/observe-dashboard.html` — 将 overview 重构为项目/版本/角色办公室与角色详情，合并决策和交接。
- [x] 52. [修改] `rules/roles/pm.md` — 增加项目目标维护职责与项目/版本/需求三层边界。
- [x] 53. [运行] `generate.sh` — 重新生成并验证 `dist/AGENTS.md`。
- [x] 54. [修改] `docs/OBSERVE.md` — 记录角色办公室交互和事实源层级。
- [x] 55. [修改] `README.md` — 更新统一工作台用户路径。
- [x] 56. [修改] `docs/FEATURES.md` — 将角色办公室与目标分层加入用户能力清单。
- [x] 57. [修改] `docs/VERSIONS.md` — 将本轮范围放入 0.13.0，不回写或伪造 Git Tag。
- [x] 58. [运行] 全量验证、Harness Audit、同步安装版、重启服务，并打开更新后的本地工作台供用户验收。

### Phase 7 完成判定

- [x] Mick Harness 首页显示稳定项目目标，0.13.0 版本目标单独展示，不再把 Observer V0 阶段目标标为总体目标。
- [x] 当前版本需求全部完成时显示“本版本已交付，等待 PM 定义下一版本”，不显示“当前需求尚未确定”。
- [x] 首页固定显示 PM、设计、开发、测试、Review 五个角色，并按真实事件显示 active / waiting / completed / idle。
- [x] Reviewer 明确 `next_role=PM` 时，首页高亮“Review → PM”的建议接手，PM 显示等待接手；没有事件时不伪造流转。
- [x] 点击角色后能看到该角色的需求上下文、执行摘要、交付物、关联决策和历史工作；决策与交接不再占用独立首页模块。
- [x] “版本规划”“产物”“技术记录”“事件明细”既有路径不回归，URL 刷新可恢复 `project/run/view/role`。
- [x] 全量 unittest、Shell/Python/JSON/JavaScript、generate、diff 和 Harness Audit 通过；安装版与源码一致，Observer 服务健康。

### Phase 7 Preflight

- baseline：`python3 -m unittest tests/test_harness_observe.py` 在允许 localhost 后为 39 tests / 0 failures。
- 真实状态源：项目目标看 `docs/PROJECT.md`；版本看 `docs/VERSIONS.md`；角色工作与流转看 work round/handoff 事件；Git 继续只读。
- 权限：源码修改在当前 Harness 仓库；最终只同步明确文件到 `~/.mick-harness` 并重启当前用户 LaunchAgent，不使用 sudo。
- 回滚：overview 可回退到 Phase 6 渲染；新增 workspace 字段为向后兼容扩展，不改变事件账本或原 API 字段。

### Phase 7 Interaction QA

- 状态机：idle（无事件）/ active（存在 active round）/ waiting（最新流转目标）/ completed（已有完成工作且非当前目标）。
- 用户路径：选择项目 → 看到项目与版本目标 → 查看高亮流转 → 点击角色 → 阅读执行详情/需求决策/交付物 → 刷新恢复角色。
- 失败态：缺 `docs/PROJECT.md` 显示 PM 尚未建立项目目标；缺版本计划显示尚未规划；角色无事件显示尚未参与，不猜测工作。
- 状态一致：办公室节点和连线必须可追溯到 workspace organization 的 sequence/kind；角色产物必须来自已授权 artifact 列表。

### Phase 7 Planner Lock — 2026-08-12
- files: `plan.md`
- verify: 用户在上一轮已确认五角色办公室、目标分层、角色详情、决策并入需求和交接高亮的结构，并明确回复“开始”；39 项 baseline 全绿
- notes: 本次无 Brain 相关命中；“开始”视为对上一轮已展示结构的执行授权，Phase 7 直接进入 Executor，不重复要求一次形式确认。

### Step 48 — 2026-08-12
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 既有 baseline 为 39 tests / 0 failures；新增 3 项聚焦契约按预期红灯，分别暴露缺少 `parse_project_profile`/组织投影和旧 Dashboard 四模块仍存在
- notes: 测试固定五角色顺序、Planner→PM 映射、Review→PM 建议接手、真实 handoff、角色 URL 与旧合成流程移除。

### Step 49 — 2026-08-12
- files: `docs/PROJECT.md`, `plan.md`
- verify: 文档包含唯一 `## Goal` 稳定目标，并把 audience 与 product boundary 独立于版本/Plan 技术目标表达
- notes: 项目目标来自 README 已有产品定位，没有把 0.12/0.13 工作台范围写入长期目标。

### Step 50 — 2026-08-12
- files: `scripts/harness-observe.py`, `plan.md`
- verify: Phase 7 组织投影与 Phase 6 workspace 回归共 2 tests / 0 failures；Python compile exit 0
- notes: workspace 新增向后兼容的 `project`/`organization` 字段；Planner/Orchestrator 归入 PM，真实 handoff 与建议 next_role 保留不同 kind。

### Step 51 — 2026-08-12
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: Dashboard 内联 JavaScript 语法通过；角色图谱、导航、Phase 6 产物与重连共 4 tests / 0 failures
- notes: overview 已移除旧四模块和合成四阶段流程；五角色可点击，当前流转区分真实/建议，角色详情合并需求决策、执行记录和产物，`role` 写入 URL。

### Step 52 — 2026-08-12
- files: `rules/roles/pm.md`, `plan.md`
- verify: `rg` 命中 `docs/PROJECT.md`、项目/版本/需求三层目标、版本需求确认口径和“本版本已交付”语义
- notes: PM 只在长期定位改变时更新项目目标；新增版本或阶段不再覆盖项目目标。

### Step 53 — 2026-08-12
- files: `dist/AGENTS.md`, `plan.md`
- verify: `./generate.sh` 完成 lean AGENTS 生成，`./generate.sh --check` 返回“All generated rule files are up to date”
- notes: 额外 `rg` 查 PM 专属段未命中并使组合命令 exit 1；这是因为 lean `dist/AGENTS.md` 只包含 Core、不内联角色文件，生成与一致性检查本身均通过。

### Step 54 — 2026-08-12
- files: `docs/OBSERVE.md`, `plan.md`
- verify: 文档检索命中 `docs/PROJECT.md`、五角色办公室、真实交接/建议接手、角色 URL、已交付空态和五种版本状态
- notes: 事实源层级固定为项目目标 / 版本目标 / 角色事件 / Plan 技术记录，缺失时显示空态而不跨层猜测。

### Step 55 — 2026-08-12
- files: `README.md`, `plan.md`
- verify: 推荐数据流和工作台入口包含项目/版本/需求三层、五角色办公室、角色详情与流转语义
- notes: 用户首页路径不再以 Plan 步骤和四个重复模块为核心。

### Step 56 — 2026-08-12
- files: `docs/FEATURES.md`, `plan.md`
- verify: 功能清单新增三层目标、五角色动态流转和角色执行详情三项成熟能力
- notes: lifecycle 与结构化事件回写仍保留“需调整”，没有把 Agent 遵守规则的概率包装成强保证。

### Step 57 — 2026-08-12
- files: `scripts/harness-observe.py`, `web/observe-dashboard.html`, `docs/VERSIONS.md`, `plan.md`
- verify: 真实版本解析返回 `0.11.0/released`、`0.12.0/completed`、`0.13.0/in_progress`；Python compile 与 Dashboard JavaScript syntax 均通过
- notes: 新增 `completed` 区分“范围已交付但尚未发布”，避免把没有真实 Tag 的 0.12.0 伪装成 released；当前版本选择最新 in_progress。

### Step 58 — 2026-08-12
- files: `docs/VERSIONS.md`, installed runtime, `.harness-runtime/`, `plan.md`
- verify: 全量 unittest 40 tests / 0 failures；Shell/Python/JSON/HTML/JavaScript/generate/diff 检查通过；Harness Audit 8 PASS / 0 WARN / 0 FAIL；9 个安装文件 SHA-256 与源码一致；LaunchAgent 重启后 `/healthz` 为 ok，workspace API 返回稳定项目目标、五角色、0.13.0 和 `Reviewer → PM` 建议流转
- notes: PM 决策、Executor 交付和 Reviewer 验收已通过 localhost 服务真实回写；工作台页面已更新，最终视觉观感由用户在已打开页面中确认。

## Phase 8：产物版本与日期导航

### 新目标

让用户在“产物”页按版本或日期切换阶段，看到该阶段的目标、工作结果、角色和关联决策，并在 Markdown 阅读器中通过标题目录快速跳转；同一文件被多个阶段重复交付时保留每次引用，不再只显示一条失去时间上下文的路径。

### 新约束

- 版本归属只来自 `docs/VERSIONS.md` 的需求映射；日期只来自结构化工作事件或文件修改时间，不从标题猜测。
- 同一路径可以拥有多条交付记录，记录保留版本、日期、角色、需求、目标、结果与 sequence。
- Markdown 标题目录只导航当前文件内容；Observer 不保存文件历史全文，不把当前正文伪装成过去版本快照。
- 关联决策来自同一 requirement 的 `decision.recorded`，没有事件时显示无记录，不从文档内容猜测讨论。
- 继续使用原生 HTML/CSS/JavaScript 与 Python 标准库，不增加依赖或写接口。

### 文件级 API 契约

- `scripts/harness-observe.py`：artifact metadata 新增 `records`、`versions`、`dates` 与 `latest_recorded_at`；同一路径聚合全部 work round 引用，workspace 先生成版本投影再映射产物。
- `web/observe-dashboard.html`：URL 新增 `artifact_mode=version|date` 与 `artifact_scope`；产物页增加版本/日期导航、阶段上下文、关联决策和 Markdown 标题目录。
- `tests/test_harness_observe.py`：覆盖重复产物记录、需求到版本映射、日期分组、URL 恢复、旧阅读器安全边界与无历史正文声明。
- `docs/OBSERVE.md`、`docs/FEATURES.md`、`docs/VERSIONS.md`：记录导航能力、历史正文边界和 0.14.0 范围。

### 新步骤

- [x] 59. [修改] `tests/test_harness_observe.py` — 固定产物记录聚合、版本/日期导航和 Markdown 目录契约。
- [x] 60. [修改] `scripts/harness-observe.py` — 投影产物多阶段记录、版本和日期元数据。
- [x] 61. [修改] `web/observe-dashboard.html` — 实现版本/日期筛选、阶段上下文与 Markdown 标题目录。
- [x] 62. [修改] `docs/OBSERVE.md`、`docs/FEATURES.md`、`docs/VERSIONS.md` — 补充使用方式、历史正文边界和 0.14.0 版本范围。
- [x] 63. [运行] 全量验证、Harness Audit、同步安装版、重启服务并打开 RaliTennis 产物页。

### Phase 8 完成判定

- [x] 产物页可在“按版本 / 按日期”之间切换，并通过 URL 刷新恢复筛选状态。
- [x] 同一产物在多个 work round 被引用时显示多条阶段记录，不因路径去重丢失历史上下文。
- [x] 版本筛选严格根据 requirement 在 `docs/VERSIONS.md` 中的归属；未归属内容进入“未归档”。
- [x] 选择产物后显示当时目标、结果、角色、日期与同需求关键决策。
- [x] Markdown 阅读器显示标题目录并可跳到文档内对应章节；代码阅读器不伪造目录。
- [x] 页面明确提示当前读取的是现有文件，不是历史全文快照。
- [x] 全量测试、静态检查、Harness Audit、安装一致性与 localhost workspace API 通过。

### Phase 8 Preflight

- baseline：Phase 7 全量 unittest 40 tests / 0 failures；Observer 服务健康。
- 真实状态源：版本来自 `docs/VERSIONS.md`；日期/角色/目标/结果来自 work round；当前正文来自项目文件。
- 回滚：新增 artifact metadata 为向后兼容字段，前端可回退到现有平铺列表，不改变事件账本。

### Phase 8 Interaction QA

- 用户路径：进入产物 → 按版本选择阶段 → 选择产物 → 阅读当时目标/结果/决策 → 用标题目录跳转；切到按日期后重复路径。
- 空态：无版本记录时显示“未归档”；无事件记录时使用文件修改日期；非 Markdown 不显示标题目录。
- 状态一致：筛选选项必须能追溯到 artifact records，正文仍通过既有授权 API 读取。

### Phase 8 Planner Lock — 2026-08-12
- files: `plan.md`
- verify: 用户明确要求给每个产物增加按版本或日期切换的导航，以快速查看当时目标、讨论和结果；现有 workspace 已确认 work round 含时间/需求/目标/摘要，版本计划可提供需求归属
- notes: 第一版展示结构化讨论摘要和决策，不新增历史正文快照；这是当前隐私与事件账本边界内的最小可用闭环。

### Step 59 — 2026-08-12
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 两项 Phase 8 聚焦契约按预期红灯；后端缺少 artifact `versions`，前端缺少“按版本”导航
- notes: 契约覆盖同一路径两次交付、需求到版本映射、日期降序、URL 状态、阶段上下文、关联决策和 Markdown 目录。

### Step 60 — 2026-08-12
- files: `scripts/harness-observe.py`, `plan.md`
- verify: Python compile 通过；Phase 8 metadata 与 Phase 6 workspace 回归共 2 tests / 0 failures
- notes: artifact descriptor 现在累积每个 work round 引用；版本只由 requirement 映射，日期优先结构化事件，文件修改时间仅作退化。

### Step 61 — 2026-08-12
- files: `web/observe-dashboard.html`, `plan.md`
- verify: Dashboard JavaScript syntax 通过；Phase 8 导航、Phase 6 安全阅读器和 metadata 共 3 tests / 0 failures
- notes: URL 保存 `artifact_mode`/`artifact_scope`；Markdown 目录通过安全 DOM 与 scrollIntoView 导航，不使用 raw HTML。

### Step 62 — 2026-08-12
- files: `docs/OBSERVE.md`, `docs/FEATURES.md`, `docs/VERSIONS.md`, `plan.md`
- verify: 文档检索命中按版本/按日期、重复阶段记录、Markdown 目录、当前文件非历史快照边界；0.14.0 解析为 in_progress 且 4/5 已交付
- notes: 历史完整正文明确保留为后续能力，不以当前文件内容伪装历史版本。

### Step 63 — 2026-08-12
- files: installed `scripts/harness-observe.py`, `web/observe-dashboard.html`, `docs/OBSERVE.md`, `docs/FEATURES.md`, `docs/VERSIONS.md`; `.harness-runtime/`; `plan.md`
- verify: 全量 unittest 42 tests / 0 failures；Shell/Python/JSON/HTML/JavaScript/generate/diff 检查通过；Harness Audit 8 PASS / 0 WARN / 0 FAIL；Observer 重启后 `/healthz` 为 ok；真实 workspace API 确认 RaliTennis 有 v0.1.0 导航、Plan 日期记录与可读 Markdown，Harness 重复产物保留 2–3 条跨 0.12/0.13/0.14 记录
- notes: 页面按 Sites 规范未做自动 DOM 点击或截图检查，已通过真实 API、前端契约与脚本语法验证并打开给用户检查视觉交互。

## Phase 8 Post-delivery Correction：筛选作用域

用户截图确认 Phase 8 的交互对象理解错误：产物路径始终是一份，版本/日期不应过滤左侧文件列表；它们只应切换当前选中文件内部的阶段记录，并在正文有对应标题时定位章节。顶部“项目产物”说明卡没有有效信息，删除。

### 修正约束

- 左侧始终显示全部已授权产物，不随版本或日期变化。
- 版本/日期导航只在选择产物后出现在右侧，计数只统计该产物自己的阶段记录。
- 切换导航不清空当前产物；阶段卡按范围过滤，Markdown 目录尝试定位包含该版本或日期的标题。
- 正文没有匹配标题时保留全文和完整目录，不隐藏内容、不伪造历史正文。

### 修正步骤

- [x] 64. [修改] `tests/test_harness_observe.py` — 固定“文件列表不筛选、导航属于选中文件、删除无效顶部卡”的回归契约。
- [x] 65. [修改] `web/observe-dashboard.html`、`docs/OBSERVE.md` — 修正导航位置、计数、作用域和正文定位语义。
- [x] 66. [运行] 聚焦与全量验证、同步安装版、重启服务并打开 RaliTennis 产物页。

### 修正完成判定

- [x] 无论选择哪个版本或日期，左侧产物数量和顺序不变。
- [x] 未选择产物时不显示版本/日期导航；选择后导航只展示该文件拥有的阶段。
- [x] 版本/日期切换仅过滤阶段目标、结果和决策，并在 Markdown 有匹配标题时定位对应章节。
- [x] 顶部无效“项目产物”说明卡消失。
- [x] 全量验证、安装一致性与 Observer 健康检查通过。

### Correction Lock — 2026-08-12
- files: `plan.md`
- verify: 用户明确指出“产物不是按日期或版本存成多份，它始终是同一份”，截图证实当前日期筛选同时改变左侧产物列表
- notes: 这是对 Phase 8 信息架构的局部纠正；后端多阶段记录仍有效，不需修改事件账本或 workspace API。

### Step 64 — 2026-08-12
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 新增前端契约后按预期红灯，暴露缺少正文标题定位；实现后产物导航、既有安全阅读器和 metadata 共 3 tests / 0 failures
- notes: 契约明确禁止 `artifactMatchesNavigation` 和左侧 `.filter(...)`，并要求导航接收当前 artifact、顶部说明卡不再渲染。

### Step 65 — 2026-08-12
- files: `web/observe-dashboard.html`, `docs/OBSERVE.md`, `docs/FEATURES.md`, `plan.md`
- verify: Dashboard JavaScript syntax 与 HTML parse 通过；聚焦 3 tests / 0 failures；文档明确“左侧文件不筛选、右侧阶段记录筛选、正文匹配标题时定位”
- notes: 同一路径仍是一份当前文件；版本/日期只是阶段上下文，未引入历史全文快照或后端 API 变化。

### Step 66 — 2026-08-12
- files: installed `web/observe-dashboard.html`, `docs/OBSERVE.md`, `docs/FEATURES.md`; project `.harness/` 同步副本；`plan.md`
- verify: 全量 unittest 42 tests / 0 failures；Shell/Python/JSON/HTML/JavaScript/generate/diff 检查通过；三个安装位置 SHA-256 逐项一致；Observer 重启后 `health.status=ok`、5 个登记项目/4 个有效项目；RaliTennis workspace 返回稳定的 3 份产物
- notes: sandbox 首次全量测试有 4 项因禁止 localhost bind 报 PermissionError，授权本机回环后同一套 42 项全部通过；服务重启前健康检查失败，重启并端到端读取页面/API 后恢复。

## v0.15.0 · 2026-08-12 · 结构化产物阶段导航

### 新目标

把产物页从“工作事件筛选器”改成真正的文档阅读导航：AI 为持续演进的 Markdown 写入可追踪阶段标题，Observer 只按标题契约解析阶段，用户通过阶段名称、版本和实际沟通日期直接跳到正文；交付事件仍保留在事件账本，但不再冒充文档内容索引。

### 新约束

- 推荐标题格式固定为 `## vX.Y.Z · YYYY-MM-DD · 阶段标题`；日期表示实际沟通或决策日期，版本表示内容归属。
- 解析器只读取 Markdown 标题，不扫描正文中的日期；正文里的测试日期、文件日期和日志日期不得生成阶段入口。
- 兼容旧项目：标题末尾圆括号或破折号中的日期可作为 legacy 阶段，多个日期全部保留并以最后一个作为最近更新，但缺少版本时明确显示“未标版本”，不得推断。
- artifact API 返回当前文件的结构化 `stages`；阶段记录不是历史正文快照，也不改变 append-only 事件账本。
- 产物页删除“按版本 / 按日期 / 全部记录”以及阶段事件卡；Markdown 左侧导航展示阶段名称、版本、日期和格式状态，点击定位当前正文对应标题。
- 代码与纯文本产物不生成阶段导航；旧 URL 的 `artifact_mode` / `artifact_scope` 可被忽略并在下一次状态写回时移除。
- 本阶段显式允许修改 `rules/core.md` 并运行 `generate.sh`，覆盖 V0 初始阶段的规则不变约束；不增加第三方依赖，不自动改写用户项目文档。

### 文件级 API 契约

- `rules/core.md`：新增持续演进 Markdown 的最小阶段标题规则，约束版本、实际沟通日期和用户可读标题。
- `scripts/harness-observe.py`：新增 `parse_markdown_stages(value)`；每项包含 `line`、`level`、`title`、`version`、`date`、`dates`、`format=structured|legacy` 与 `traceable`，并由 artifact API 返回。
- `web/observe-dashboard.html`：移除事件筛选 UI；`renderDocumentOutline` 同时渲染结构化阶段导航与完整文档目录，阶段按钮按 API 行号定位标题。
- `tests/test_harness_observe.py`：证明规范标题、legacy 标题、多日期标题、正文日期忽略、代码无阶段以及前端无旧筛选器。

### 新步骤

- [x] 67. [修改] `tests/test_harness_observe.py` — 固定阶段标题解析、artifact API 和新版阅读导航契约，并保存预期红灯。
- [x] 68. [修改] `rules/core.md` — 增加持续演进 Markdown 的可追踪阶段标题规则。
- [x] 69. [修改] `scripts/harness-observe.py` — 实现严格标题解析、legacy 兼容和 artifact `stages` 投影。
- [x] 70. [修改] `web/observe-dashboard.html` — 用阶段导航替换旧事件筛选器，按行号定位正文标题。
- [x] 71. [修改] `docs/OBSERVE.md` — 记录产物生成、解析、展示的完整链路和历史正文边界。
- [x] 72. [修改] `docs/FEATURES.md` — 更新产物阶段导航能力与旧项目兼容状态。
- [x] 73. [修改] `docs/VERSIONS.md` — 新增 v0.15.0 的目标和需求清单。
- [x] 74. [运行] `generate.sh` — 重新生成规则分发文件并验证标题契约进入安装产物。
- [x] 75. [运行] 聚焦与全量验证、真实 RaliTennis 解析、同步安装版、重启 Observer 并打开产物页。

### Phase 9 完成判定

- [x] 推荐格式标题被解析为可追踪阶段，版本、日期、标题和行号准确。
- [x] legacy 标题可导航但明确缺失字段；正文里的日期不生成阶段入口。
- [x] 产物页不再出现旧版事件筛选区和阶段事件卡，阶段导航显示用户可理解的标题并点击定位正文。
- [x] 无阶段文档显示写作提示但仍可阅读完整目录；代码阅读器不显示 Markdown 阶段。
- [x] RaliTennis `plan.md` 的历史阶段标题可被识别，包含多个日期的旧标题不丢失更新时间。
- [x] 全量测试、静态检查、Harness Audit、安装一致性和 Observer localhost API 通过。

### Phase 9 Preflight

- baseline：改动前全量 unittest 42 tests / 0 failures；Observer 6425 服务已安装。
- 真实状态源：阶段来自当前 Markdown 标题；交付时间与角色来自事件账本；两者分开展示，不互相推断。
- 旧项目样本：RaliTennis `plan.md` 有大量 `### Step ...（YYYY-MM-DD）` 标题，并有一个含两个日期的更新标题；正文同样包含其他日期。
- 回滚：artifact `stages` 是兼容新增字段；前端可回退完整文档目录，事件账本与原文件均不修改。

### Phase 9 Interaction QA

- 用户路径：选择 `plan.md` → 在“阶段导航”看到标题/版本/日期 → 点击阶段 → 正文对应标题滚入视图 → 仍可使用完整文档目录。
- 准确性：规范标题显示“可追踪”；legacy 缺版本显示“未标版本”；多个 legacy 日期展示最新日期和更新次数；正文日期不进入导航。
- 空态：没有阶段标题时提示推荐格式，不隐藏正文；代码文件维持折叠代码阅读器。
- 状态往返：更换产物后阶段导航来自新文件；刷新后恢复产物，但旧筛选参数不再影响页面。

### Phase 9 Planner Lock — 2026-08-12
- files: `plan.md`
- verify: 用户确认执行“产物写作规范 → 确定性解析 → 阶段目录阅读”闭环；基线全量 unittest 42 tests / 0 failures
- notes: 现有事件账本、产物授权和 Markdown 安全渲染继续复用；不再扩展旧筛选器，不自动迁移或改写 RaliTennis 文档。

### Step 67 — 2026-08-12
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: Phase 9 三项聚焦契约按预期红灯：缺少 `parse_markdown_stages`、artifact `stages` 和“阶段导航”，旧事件筛选器仍存在
- notes: 用例覆盖规范标题、正文日期忽略、legacy 单/多日期、代码空阶段以及前端彻底移除旧 URL/筛选函数。

### Step 68 — 2026-08-12
- files: `rules/core.md`, `plan.md`
- verify: `rg` 命中可追踪 Markdown 阶段、规范标题、实际沟通日期与禁止编造版本四项契约
- notes: 规则只约束已进入版本计划且需回看的新阶段；不要求自动重写旧文档，也不允许用文件时间代替沟通日期。

### Step 69 — 2026-08-12
- files: `scripts/harness-observe.py`, `plan.md`
- verify: Phase 9 parser 与既有代码产物 API 共 2 tests / 0 failures；真实 RaliTennis `plan.md` 识别 38 个标题阶段，并保留 Step 3ak 的 2026-08-04 / 2026-08-10 两次日期
- notes: 解析器跳过 fenced code 和正文日期；规范标题可追踪，legacy 标题不推断版本并标记 `traceable=false`。

### Step 70 — 2026-08-12
- files: `web/observe-dashboard.html`, `plan.md`
- verify: Dashboard JavaScript syntax 通过；Phase 9 阶段导航、解析结果与既有安全 Markdown 阅读器共 3 tests / 0 failures
- notes: 删除旧事件筛选、事件卡和两个 URL 参数；阶段按钮使用 API 行号映射安全生成的标题 id，点击滚动并高亮正文。

### Step 71 — 2026-08-12
- files: `docs/OBSERVE.md`, `plan.md`
- verify: 文档检索命中产出到阅读、规范标题、H2–H4 限定、legacy 缺版本状态和事件/正文结构分离五项契约
- notes: 文档明确阶段导航读取当前文件，不恢复被覆盖的历史正文，也不把 work round 日期当作内容索引。

### Step 72 — 2026-08-12
- files: `docs/FEATURES.md`, `plan.md`
- verify: 功能清单命中可追踪标题、正文日期忽略、旧项目兼容和“未标版本 · 旧格式”边界
- notes: 原“按版本/按日期筛选事件记录”能力已由标题驱动的阶段导航替代。

### Step 73 — 2026-08-12
- files: `docs/VERSIONS.md`, `plan.md`
- verify: 真实 `parse_versions_markdown()` 返回 v0.15.0/in_progress、7 项需求，其中 5 项已交付、2 项待完成
- notes: v0.15.0 目标覆盖产出规范、确定性解析和用户阅读三个环节，不包含历史全文快照。

### Step 74 — 2026-08-12
- files: `dist/AGENTS.md`, `plan.md`
- verify: `./generate.sh` 生成 lean AGENTS；`./generate.sh --check` 返回全部最新；分发文件命中规范标题与实际沟通日期契约
- notes: 首次生成被 workspace sandbox 禁止写 `dist/AGENTS.md`，授权相同生成命令后成功，不属于生成器逻辑错误。

### Step 75 — 2026-08-12
- files: installed `scripts/harness-observe.py`, `web/observe-dashboard.html`, `rules/core.md`, `dist/AGENTS.md`, `docs/OBSERVE.md`, `docs/FEATURES.md`, `docs/VERSIONS.md`; project `.harness/` 同步副本；`tests/test_harness_observe.py`; `plan.md`
- verify: 全量 unittest 43 tests / 0 failures；Shell/Python/JSON/HTML/JavaScript/generate/diff 检查通过；Observer 重启后 `health.status=ok`；真实 RaliTennis artifact API 返回 38 个阶段并保留 Step 3ak 的两个日期；真实 Harness `plan.md` 返回 v0.15.0 规范阶段；页面源码无旧事件筛选器
- notes: Sites 规范禁止未被用户明确要求的自动 DOM 点击与截图，因此交互采用 API、前端契约和脚本语法验收，并将真实页面打开给用户复核。
