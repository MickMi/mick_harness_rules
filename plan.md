> 🧭 状态：v0.22.1 验证中 | 进度 213/214 | 当前归属：QA | 最近交付：update 已按提交变化获取标签并条件重载 6425

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
- files: `tests/test_harness_observe.py`; installed runtime `~/.mick-harness/bin/harness`, `~/.mick-harness/scripts/harness-observe.py`, `~/.mick-harness/web/observe-dashboard.html`
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
- files: `README.md`, `docs/OBSERVE.md`, `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`; installed runtime under `~/.mick-harness`
- verify: 19 unittests passed; shell/Python/JSON/HTML/JavaScript/generate/diff checks passed; real registry returned 5 projects (4 valid, 1 missing); `Harness project` resolved to Reviewer, 13/13 tasks; final Portfolio and Dashboard returned 200, POST returned 405; installed runtime/hook/dashboard checksums match source
- notes: Numbered plan steps are the only task source; legacy completion-criteria tasks are marked abandoned and excluded, with a versioned collector signature forcing one safe re-import after parser upgrades. The live service runs `harness observe watch --all` on PID 86441. Browser automation policy still prevents DOM control of localhost, so refresh/click visual QA remains user-confirmed rather than automated.

### Step 14 — 2026-08-11 11:17
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`; installed Dashboard under `~/.mick-harness`
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
- `tests/test_harness_observe.py`：覆盖 sample application 风格 Plan 的 3/5 投影、目标提取、非 Steps 编号排除、Dashboard 默认视图与关键节点文案。
- `docs/OBSERVE.md`、`README.md`：将用户入口描述改为需求导航，说明技术记录和推断边界。

### 新步骤

- [x] 21. 增加 Phase 4 失败用例与 `plan.summary_observed` schema 契约，固定 sample application 风格 Plan 的期望投影。
- [x] 22. 实现 Plan 语义解析、摘要事件、任务状态与 snapshot 投影，并确保旧 checkbox Plan 不回归。
- [x] 23. 将 Dashboard 项目默认页改成简化需求导航，保留技术记录与 URL 刷新恢复。
- [x] 24. 更新产品文档、同步安装版，并让后台服务重新载入新运行时。
- [x] 25. 运行全量回归、真实 sample application 同步和浏览器端到端验证，记录页面状态、交互与刷新证据。

### Phase 4 完成判定

- [x] sample application snapshot 显示总体目标、5 条需求、当前第 3 条；前 2 条完成、第 3 条进行中、后 2 条待开始。
- [x] 项目默认页面首屏显示总体目标、需求进度和需要用户处理的阻塞，不显示原始事件指标。
- [x] 当前需求卡显示 `定义 → 实现 → 验证 → 交付`，并高亮真实当前节点与负责人。
- [x] timeline / events 仍可访问，旧 `view=graph` URL 自动显示需求导航，刷新后选择保持。
- [x] 旧 checkbox Plan、STATE 优先级、Hook 脱敏、只读 HTTP 和后台服务测试不回归。
- [x] 源码与安装版校验一致；重启服务后 `healthz`、页面和 Portfolio API 返回 200。
- [x] 真实浏览器完成项目进入、需求选择、技术记录切换和刷新恢复检查。

### Step 21 — 2026-08-12
- files: `docs/runtime-event-v0.schema.json`, `tests/test_harness_observe.py`, `plan.md`
- verify: `python3 -m json.tool docs/runtime-event-v0.schema.json` exit 0；Phase 4 聚焦测试按预期红灯，分别暴露缺少 snapshot `plan` 投影和 Dashboard 默认 `overview` 视图
- notes: 失败用例使用与真实 sample application 相同的 `Current step: 3 / 5` + `## Steps` 编号格式，并验证其他编号章节不会被误识别。

### Step 22 — 2026-08-12
- files: `scripts/harness-observe.py`, `docs/runtime-event-v0.schema.json`, `plan.md`
- verify: `python3 -B -m unittest` 聚焦运行编号 Plan、checkbox Plan、待验证与非 Steps 排除共 4 项，全部通过；Python 编译首次因仓库禁止写 `__pycache__` 被环境阻止，已保留到最终验证用临时缓存路径复跑
- notes: Collector 升级到 0.3.0；总体目标缺失时保持空值，普通编号 Plan 只解析 `## Steps` / `## 步骤`，不猜测其他章节。

### Step 23 — 2026-08-12
- files: `web/observe-dashboard.html`, `plan.md`
- verify: inline JavaScript 通过 Node 语法解析；Phase 4 Dashboard 契约、编号 Plan、重连与失效 URL 共 4 项聚焦测试通过
- notes: 默认视图改为 `overview`，旧 `graph` 自动兼容；主页面去除 Agent/Harness 原始指标，只保留总体目标、需求进度、待处理和四节点详情。

### Step 24 — 2026-08-12
- files: `docs/OBSERVE.md`, `README.md`, `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`; installed runtime under `~/.mick-harness`
- verify: 源码与安装版 5 个文件 SHA-1 逐对一致；服务重启后 PID 41434，`health.status=ok`、4/5 项目有效、4 个项目同步、`last_scan_error=null`
- notes: 首次重启由真实健康检查发现 block 解析覆盖 Plan 摘要，新增回归后修复并再次重启恢复健康；没有把降级状态当作完成。

### Step 25 — 2026-08-12
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`; installed runtime and live service
- verify: 32 个 unittest 通过、0 failures、exit 0；Bash/Python/JSON/JavaScript、`generate.sh --check`、`git diff --check` 均 exit 0；服务 `health.status=ok`、页面/Portfolio/Rali snapshot 均 HTTP 200
- notes: 真实 sample application 显示总体目标、2/5 已交付、当前 Watch-only 第 3 条、5 条需求和四节点；浏览器选择需求 4、切换技术记录、刷新后保持 `view=timeline&task=task-4`，最终返回 `overview&task=task-3`。真实验证还发现已裁决阻塞的 import-cache 迁移问题，已用 Collector 0.3.1 安全重导入并新增回归，最终 `active_blocks=0`。

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
- [x] 63. [运行] 全量验证、Harness Audit、同步安装版、重启服务并打开 sample application 产物页。

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
- verify: 全量 unittest 42 tests / 0 failures；Shell/Python/JSON/HTML/JavaScript/generate/diff 检查通过；Harness Audit 8 PASS / 0 WARN / 0 FAIL；Observer 重启后 `/healthz` 为 ok；真实 workspace API 确认 sample application 有 v0.1.0 导航、Plan 日期记录与可读 Markdown，Harness 重复产物保留 2–3 条跨 0.12/0.13/0.14 记录
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
- [x] 66. [运行] 聚焦与全量验证、同步安装版、重启服务并打开 sample application 产物页。

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
- verify: 全量 unittest 42 tests / 0 failures；Shell/Python/JSON/HTML/JavaScript/generate/diff 检查通过；三个安装位置 SHA-256 逐项一致；Observer 重启后 `health.status=ok`、5 个登记项目/4 个有效项目；sample application workspace 返回稳定的 3 份产物
- notes: sandbox 首次全量测试有 4 项因禁止 localhost bind 报 PermissionError，授权本机回环后同一套 42 项全部通过；服务重启前健康检查失败，重启并端到端读取页面/API 后恢复。

## v0.16.0 · 2026-08-12 · 结构化产物阶段导航

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
- [x] 75. [运行] 聚焦与全量验证、真实 sample application 解析、同步安装版、重启 Observer 并打开产物页。

### Phase 9 完成判定

- [x] 推荐格式标题被解析为可追踪阶段，版本、日期、标题和行号准确。
- [x] legacy 标题可导航但明确缺失字段；正文里的日期不生成阶段入口。
- [x] 产物页不再出现旧版事件筛选区和阶段事件卡，阶段导航显示用户可理解的标题并点击定位正文。
- [x] 无阶段文档显示写作提示但仍可阅读完整目录；代码阅读器不显示 Markdown 阶段。
- [x] sample application `plan.md` 的历史阶段标题可被识别，包含多个日期的旧标题不丢失更新时间。
- [x] 全量测试、静态检查、Harness Audit、安装一致性和 Observer localhost API 通过。

### Phase 9 Preflight

- baseline：改动前全量 unittest 42 tests / 0 failures；Observer 6425 服务已安装。
- 真实状态源：阶段来自当前 Markdown 标题；交付时间与角色来自事件账本；两者分开展示，不互相推断。
- 旧项目样本：sample application `plan.md` 有大量 `### Step ...（YYYY-MM-DD）` 标题，并有一个含两个日期的更新标题；正文同样包含其他日期。
- 回滚：artifact `stages` 是兼容新增字段；前端可回退完整文档目录，事件账本与原文件均不修改。

### Phase 9 Interaction QA

- 用户路径：选择 `plan.md` → 在“阶段导航”看到标题/版本/日期 → 点击阶段 → 正文对应标题滚入视图 → 仍可使用完整文档目录。
- 准确性：规范标题显示“可追踪”；legacy 缺版本显示“未标版本”；多个 legacy 日期展示最新日期和更新次数；正文日期不进入导航。
- 空态：没有阶段标题时提示推荐格式，不隐藏正文；代码文件维持折叠代码阅读器。
- 状态往返：更换产物后阶段导航来自新文件；刷新后恢复产物，但旧筛选参数不再影响页面。

### Phase 9 Planner Lock — 2026-08-12
- files: `plan.md`
- verify: 用户确认执行“产物写作规范 → 确定性解析 → 阶段目录阅读”闭环；基线全量 unittest 42 tests / 0 failures
- notes: 现有事件账本、产物授权和 Markdown 安全渲染继续复用；不再扩展旧筛选器，不自动迁移或改写 sample application 文档。

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
- verify: Phase 9 parser 与既有代码产物 API 共 2 tests / 0 failures；真实 sample application `plan.md` 识别 38 个标题阶段，并保留 Step 3ak 的 2026-08-04 / 2026-08-10 两次日期
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
- verify: 全量 unittest 43 tests / 0 failures；Shell/Python/JSON/HTML/JavaScript/generate/diff 检查通过；Observer 重启后 `health.status=ok`；真实 sample application artifact API 返回 38 个阶段并保留 Step 3ak 的两个日期；真实 Harness `plan.md` 返回 v0.15.0 规范阶段；页面源码无旧事件筛选器
- notes: Sites 规范禁止未被用户明确要求的自动 DOM 点击与截图，因此交互采用 API、前端契约和脚本语法验收，并将真实页面打开给用户复核。

## Phase 10：导航树重构与办公室视觉（v0.17.0 前瞻 · 纯前端）

### 目标

左侧导航改为「总览 → 项目（可折叠）→ 五个视图」的真实两级树，删除泄漏内部概念的“进展记录” run 列表；主区角色办公室增强状态灯、流转动线与工位卡质感。不改动 API、事件账本或功能行为。

### 约束

- run 仍自动选择最新，URL `run` 参数保留兼容；五个视图标签文案不变（需求导航/产物/版本规划/技术记录/事件明细）。
- 导航项去卡片化：文本树 + 当前项左侧强调条；invalid 项目保留可见与原因。
- 办公室增强只用既有 workspace/snapshot 字段，DOM 安全构建，无第三方依赖。
- 既有 43 项测试不回归；新契约先红后绿。

### 步骤

- [x] 76. [修改] `tests/test_harness_observe.py` — 固定导航树与办公室视觉契约（无“进展记录”/run-list，有 nav-tree 与状态灯）。
- [x] 77. [修改] `web/observe-dashboard.html` — 两级树导航、删除 run 列表与 tabs 迁移、办公室状态灯与流转动线。
- [x] 78. [运行] 全量验证、同步 `~/.mick-harness` 与项目 `.harness/` 副本，打开真实页面给用户复核。

### Step 76 — 2026-08-13
- files: `tests/test_harness_observe.py`
- verify: 新契约按预期红灯（`nav-tree` 缺失），实现后转绿

### Step 77 — 2026-08-13
- files: `web/observe-dashboard.html`
- verify: HTML parse OK；抽取内联 JavaScript `node --check` exit 0；无 `run-list`/`renderTabs`/`role-dot` 等旧引用残留
- notes: 左侧改为 总览 → 项目（▸/▾ 折叠）→ 五视图 两级树，当前项 inset 强调条；需求导航带真实阻塞徽章；tabs 从主区迁入树；办公室 role-dot 升级为呼吸状态灯 role-light，当前流转改为带流动点动画的 flow-line（建议接手为虚线）。

### Step 78 — 2026-08-13
- files: installed `web/observe-dashboard.html`（`~/.mick-harness` 与项目 `.harness/`）；`plan.md`
- verify: 全量 unittest 44 tests / 0 failures；`git diff --check` 与 schema JSON 校验 exit 0；三处副本 SHA-256 一致；线上页面含 `nav-tree`、无“进展记录”；`/healthz` status=ok
- notes: 静态页面按请求从安装目录读取，无需重启服务；真实视觉与交互由用户在已打开页面复核。

## v0.17.0 · 2026-08-13 · 注入回写工业化与角色有效性

### 目标

把 Harness 从“能够注入规则并记录部分事件”升级为可诊断、可恢复、可迁移、可验证的本地 Agent 工作系统；同时将角色规则精简为稳定职责契约，用契约测试和真实 Agent 行为样本证明它们有效。

“工业级”不表述为“绝对不出错”，而是：**不静默失败、不损坏原配置和事件数据、失败可定位、中断可恢复、升级可迁移、行为可验证**。

### 用户可见结果

- 用户能在一处看到每个 Code Agent 的五层真实状态：`已发现 → 已注入 → 已加载 → 执行合格 → 已回写`。
- 诊断结果必须指明故障发生在 Agent 发现、规则文件、Hook、本地服务、项目注入还是事件投影。
- 规则更新和旧项目迁移可重复执行；失败时保留最后一份有效配置，不留半写文件。
- 服务离线或重启不丢失已接收事件；重复投递不制造重复记录。
- Brain 的读取与写入有明确授权、来源、摘要和隐私边界，不把私人正文注入项目或事件账本。
- 用户点开某个角色时，看到的职责、交付物、完成条件和流转边界与 Agent 实际执行一致。

### 支持边界

- Tier 1：Claude Code 与 Codex，完成自动发现、规则注入、加载证明、生命周期回写和诊断。
- Tier 2：Cursor、Windsurf、Cline、Roo、Trae 等已知入口，提供尽力发现、可注入能力说明和明确的不支持项；本版不伪造完整生命周期支持。
- “发现所有 Code Agent”不作为可验收承诺；可验收的是注册表中已知 Agent 在 PATH、macOS App、配置目录和编辑器扩展四类信号上的可重现检测。
- 不存储 Prompt、回复全文、transcript、密钥、环境变量或 Brain 私人正文。
- 不自动安装未知 Agent、IDE 扩展或第三方 Skill；不在无用户确认时改写 Agent 自有配置。

### 文件级契约

- `config/agent-registry.json`（新建）：已知 Agent 的标识、检测信号、注入目标、Hook 能力、支持等级和安全边界；注册表是能力事实源，不从界面文案推断。
- `scripts/harness-agent-manager.py`（新建）：提供可测试的 scan / sync / doctor / migrate 内核；写入使用同目录临时文件、fsync 和原子替换，保留必要的可审查备份。
- `bin/harness`（修改）：保留 `agents scan/sync`，新增 `agents doctor` 与 `agents migrate`，作为 Python 内核的稳定薄入口。
- `scripts/harness-observe.py` 与 `scripts/harness-observe-hook.py`（修改）：增加带 schema/version/idempotency key 的可恢复事件提交、本地暂存、重放与脱敏校验。
- `docs/runtime-event-v0.schema.json`（修改）：增加注入诊断、规则加载证明、Brain 交互元数据和回写恢复事件，不允许私密正文字段。
- `rules/roles/*.md` 与 `rules/roles/orchestration.md`（修改）：统一为角色触发、必读输入、职责、非职责、交付物、验收、交接七段契约；长模板与行业示例下沉到按需资料。
- `rules/skills/SOURCES.md`（新建）：记录外部 Skill 的仓库、许可证、固定 commit、引入理由、安全审查、适用角色和更新/移除方式；审查不通过时可以保持空清单。
- `tests/test_harness_agents.py` 与 `tests/test_role_contracts.py`（新建）：覆盖注入、迁移、故障注入、隐私、契约结构和角色行为样本；不读写用户真实配置。
- `web/observe-dashboard.html`（修改）：展示五层 Agent 状态、最后证据、失败原因和最小修复动作，不从文件存在推断已加载或执行合格。
- `docs/AGENT-SUPPORT.md`、`docs/BRAIN-INTEGRATION.md`、`docs/ROLE-CONTRACTS.md`（新建）：分别记录兼容矩阵、Brain 数据流与角色有效性评测方法。

### 实施步骤

- [x] 79. [基线] 对现有 agents scan/sync、全局/项目 Loader、Hook、Observer、Brain 和角色规则建立端到端状态图、威胁模型与失效用例基线。
- [x] 80. [测试先行] 固定 Agent 注册表、支持等级、多信号检测和 `agents doctor --json` 契约。
- [x] 81. [注入] 实现原子同步、干跑、冲突识别、旧 marker 迁移、保守备份和中断回滚。
- [x] 82. [加载证明] 为 Claude Code / Codex 完成可审查 Hook 安装、规则版本回报与 session/turn 生命周期闭环；第一步先把“已写未接入”的 `harness-observe-hook.py` 真正挂进真实 Agent 配置（Claude Code SessionStart/SessionEnd + Codex lifecycle），并让 `session-start.sh` 注入文本携带可核验的规则版本号，使“已加载”从静态文本提醒升级为可回写、可核验状态。
- [x] 83. [可靠回写] 实现服务离线降级、持久化暂存、幂等重放、账本锁恢复和 schema 迁移，用故障注入验证；同时把 session/turn 生命周期从“仅 CLI 手动 emit”补齐为 hook 自动回写，并证明真实账本出现非 CLI 来源的 `agent.session_observed` / `agent.turn_observed` 事件。
- [x] 84. [Brain] 实现分层读取、写入候选、确认策略、来源 digest、去重和脱敏事件，阻断私人正文进入项目/账本。
- [x] 85. [角色契约] 清理冲突与过时调度，精简 PM / Planner / Executor / QA / Reviewer，Designer 保持可选，重新生成并校验分发文件；以实测缺陷为靶子（PM 412 行过长、Executor 僵硬、QA 重复绝对化、Reviewer 偏 Mock、orchestration 与 Kernel 过时冲突），统一为七段契约结构。
- [x] 86. [Skill 治理] 调研外部开源 Skill，完成来源、许可证、安全、重复性与适用性评审；只引入能填补明确行为缺口的候选。
- [x] 87. [行为评测] 建立角色测试集与评分卡，分开“静态契约合格”与“真实 Agent 样本合格”，不用文档存在代替效果证据。
- [x] 88. [工作台] 接入 Agent 五层状态、规则/角色版本、诊断证据和最小修复指引。
- [x] 89. [迁移与文档] 完成旧全局 Loader、已注入项目、旧 Hook 和旧事件 schema 的向后兼容说明与迁移演练。
- [x] 90. [发布 Gate] 运行安装/重复同步/半写中断/服务离线/重启重放/隐私红线/真实 Tier 1 Agent 全链路验收，更新发布文档但不在未获授权时打 Tag。

### 完成判定

- **接入验证（本阶段地基）**：回写 hook 以“真实 Agent 配置中的引用 + 真实 session 产生事件”为准，不以“脚本存在 / 单测通过”为准；`~/.claude/settings.json` 与 Codex lifecycle 中必须能定位到回写 hook，且真实账本出现非 CLI 来源的 `agent.session_observed` / `agent.turn_observed` 事件。
- 同一 Agent 连续两次 sync 后目标文件字节一致；注入中断后旧文件仍可用，无半写 managed block。
- 现有 Codex 重复 legacy block 可被 doctor 准确报告、migrate 一次清理，再次迁移为幂等 no-op。
- Tier 1 Agent 能形成 session start → turn start/stop → session end 往返，并携带可核验的规则与角色版本；缺任一段不显示“已回写”。
- 服务离线、进程被中断和重复投递用例中，最终 ledger 无丢失的已确认事件、无重复幂等键，replay digest 稳定。
- 隐私测试向 Hook、回写和 Brain 边界注入 prompt / transcript / secret / env / 私人正文，持久化文件与 API 均不得出现原文。
- 每个标准角色都通过七段契约结构检查；PM / Planner / Executor / QA / Reviewer 各至少有 3 个正向和 2 个越界/回流用例。
- 真实 Claude Code 与 Codex 样本分别记录加载、职责、交付、验证、交接五项评分；未执行真实样本时只能标注“契约测试通过”。
- 外部 Skill 没有完整来源记录或安全评审时不进入分发文件；无合适候选时“不引入”是合格结果。
- 全量单元、故障注入、迁移、端到端、`./generate.sh --check`、Harness Audit 和本机工作台真实路径全部提供本次证据。

### 立项时已确认的基线缺口

- `harness agents scan/sync` 当前只对 Claude Code 和 Codex 建模，不是本机全 Agent 注册表；`config/agent-registry.json` 尚不存在，Tier 2 能力无事实源。
- 项目注入通过现有 18 项核心检查，但 Codex 全局 Loader（`~/.codex/AGENTS.md`）存在 `MICK-HARNESS-GLOBAL` legacy managed block，正文停留在“Manifest: not found”，且全局 Loader 不会随 `rules/core.md` 源规则实时刷新。
- **Hook 已写但未接入（2026-08-13 实测）**：`scripts/harness-observe-hook.py` 逻辑完整且单测通过，但 `~/.claude/settings.json`、`~/.claude/hooks/`、`~/.codex/config.toml` 三处均无任何引用；Claude Code SessionStart 的 `hooks/session-start.sh` 只注入静态 Tripwire 文本、无回写逻辑，SessionEnd 走 brain-sync/narc 而非 harness 回写。
- **加载证明缺失**：注入的 Tripwire 文本不含规则版本号，系统无法核验“本轮加载的是哪一版规则”；现有账本中 `agent.session_observed` / `agent.turn_observed` 均为 0 条，“文件已注入”尚不能证明“本轮已加载并执行”。
- **结构化回写半真**：账本现有 22 条 harness-agent 事件（work.round/decision/handoff）全部来自 `harness observe emit` CLI 手动回写，session/turn 生命周期自动回写为 0；Observer 服务健康但接收的是 CLI 提交而非 hook 自动提交。
- 本次立项已被 `docs/VERSIONS.md` 真实解析为 12 项待办，但当前 Plan Collector 只读取首个 H2 `步骤` 区块，因此运行 snapshot 仍显示旧的 7/7；这是 task-79 必须固定、task-88 必须在工作台消除的真实断链。
- 角色规则缺陷实测：`rules/roles/pm.md` 412 行（过长）、`executor.md` 81 行（僵硬）、`qa.md` 142 行（重复与绝对化）、`reviewer.md` 122 行（偏向 Mock）、`orchestration.md` 256 行（与当前 Kernel 过时冲突）；五份角色文件无统一七段契约，且“是否有效”只有文档存在、无行为评测证明。

> 补充规划（2026-08-13 · Planner）：以上基线缺口已由实测交叉验证（注入链路 / 三个 Agent 配置 / 本地账本事件分布 / 角色文件规模 / 服务运行态），并据此把 task-82/83/85 与完成判定精确到“可核验的证据锚点”。本阶段的关键升级不是“再写一个脚本”，而是把“已写未接入”的 hook 真正挂进真实 Agent 配置，并把“脚本存在 / 单测通过”与“真实接入 / 真实产生事件”分成两个验收层。

### Preflight 与停止条件

- 开始实现前先复现并固定当前 Claude/Codex 注入、Hook、Observer 与 Brain 数据流；每个修复都保留改前/改后报告。
- 所有 Agent 配置写入先在临时 HOME 与伪造应用目录测试；未通过迁移测试前不动用户真实配置。
- 真实 Agent 行为评测若产生费用、需要登录、发起外部请求或修改全局配置，执行前单独获得用户授权。
- 外部 Skill 候选只读调研；许可证不明、包含危险命令、需要私密数据或与现有契约冲突时立即停止引入。
- 同一错误指纹重复两次进入 Debug Card；事件账本、Brain 私密内容或真实 Agent 配置存在损坏风险时停止本阶段。

### Step 79 — 2026-08-13
- files: `docs/AGENT-SUPPORT.md`, `plan.md`
- verify: `harness agents scan` exit 0，Claude/Codex 均被发现；真实配置只读探针确认两者 Observer Hook 均未接入、Codex 同时存在 global/legacy 区块；Observer 基线在允许 localhost 的环境中 44 tests / 0 failures；Harness Check 18 PASS / 1 optional warning / 0 FAIL
- notes: 五层状态被固定为相互独立的证据门；本轮未改写任何真实 Agent 配置，也未读取或持久化聊天正文。

### Step 80 — 2026-08-13
- files: `config/agent-registry.json`, `scripts/harness-agent-manager.py`, `bin/harness`, `tests/test_harness_agents.py`, `plan.md`
- verify: 验证通过：新测试在 manager/registry 不存在时 4 errors；实现后 `python3 -B -m unittest tests/test_harness_agents.py` 4 tests / 0 failures；真实 `agents doctor --json` 解析成功并报告 7 个注册 Agent、4 个已发现入口
- notes: Tier 1 仅 Claude Code/Codex；Cursor/Windsurf/Cline/Roo/Trae 只提供多信号发现和能力缺口，不承诺完整回写。

### Step 81 — 2026-08-13
- files: `scripts/harness-agent-manager.py`, `tests/test_harness_agents.py`, `plan.md`
- verify: 验证通过：`python3 -B -m unittest tests/test_harness_agents.py` 8 tests / 0 failures；覆盖 dry-run 不写入、连续 sync 字节幂等、用户正文保留、备份、legacy marker 迁移幂等、未闭合 marker 拒写、替换故障保留旧文件并清理临时文件
- notes: 所有写入在同目录完成 flush/fsync 后原子替换；迁移只识别 Harness 明确 marker。本轮仍未写真实 Agent 配置。

### Step 82/83（实现完成，真实接入待授权）— 2026-08-13
- files: `scripts/harness-agent-manager.py`, `scripts/harness-observe-hook.py`, `scripts/harness-observe.py`, `hooks/session-start.sh`, `docs/runtime-event-v0.schema.json`, `tests/test_harness_agents.py`, `tests/test_harness_observe.py`
- verify: 隔离 HOME 中 Hook 合并保留原配置且连续执行幂等；Codex/Claude 四生命周期 round-trip 通过；服务离线 + 本地账本暂不可写时事件保留在 outbox，恢复后重放一次入账、再次重放为 no-op；全量 66 tests / 0 failures
- notes: 真实 `~/.claude`、`~/.codex` 和 6425 安装部署被安全门要求用户对四个配置目标显式授权，因此 task-82/83 暂不勾选，也不把隔离测试表述为真实 Agent 已接入。

### Step 84 — 2026-08-13
- files: `scripts/harness-brain-boundary.py`, `docs/BRAIN-INTEGRATION.md`, `tests/test_harness_agents.py`
- verify: 验证通过：候选记忆稳定去重，secret 与 HOME 路径脱敏，公开元数据不含正文；实际写入必须显式 `--yes`，dry-run 无写入；相关测试纳入全量 66 tests / 0 failures
- notes: Brain 私人正文默认只在个人状态目录，项目/工作台只接触类型、层级、digest 与脱敏元数据。

### Step 85 — 2026-08-13
- files: `rules/roles/*.md`, `rules/roles/orchestration.md`, `tests/fixtures/role-behaviors.json`, `tests/test_role_contracts.py`
- verify: 六个角色均使用七段契约且少于 100 行；五个标准角色各 3 个正向 + 2 个边界用例；旧绝对化、Mock 偏置和供应商绑定断言均通过
- notes: 角色只在真实触发条件下进入；普通解释不再被 orchestration 强制切角色。

### Step 86 — 2026-08-13
- files: `rules/skills/designer-craft/SKILL.md`, `rules/skills/SOURCES.md`, `rules/roles/designer.md`, `tests/test_role_contracts.py`
- verify: 验证通过：Skill Creator `quick_validate.py` → `Skill is valid!`；来源固定到 4 个 commit；测试确认适配 Skill 无 scripts 目录且包含禁止 Hook/全局配置/外部 API 的安全边界
- notes: 以 Impeccable 为主要设计方法参考，UI UX Pro Max 仅作资料参考，Vercel guidelines 用于质量 Gate，Anthropic frontend-design 作行为基准；不复制或执行上游高权限能力。

### Step 87（契约完成，真实样本待授权）— 2026-08-13
- files: `docs/ROLE-CONTRACTS.md`, `tests/fixtures/role-behaviors.json`, `tests/test_role_contracts.py`
- verify: 评分卡固定加载、职责、交付、验证、交接五维，契约测试通过；文档明确 Claude Code/Codex 真实样本均为待授权
- notes: 工作台继续把“执行遵循”显示为未验证，不用静态文档或测试冒充真实模型行为。

### Step 88 — 2026-08-13
- files: `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_observe.py`
- verify: `/api/agents.json` 端到端返回 7 个注册 Agent；带当前 `rule_version` 的 runtime 事件才点亮“加载”；页面脚本语法通过，API 与五层 UI 契约测试纳入全量 66 tests / 0 failures
- notes: API 不暴露 session_ref、命令路径或配置正文；仅返回检测种类、分层状态、计数、项目名和修复提示。

### Step 89 — 2026-08-13
- files: `README.md`, `docs/AGENT-SUPPORT.md`, `docs/BRAIN-INTEGRATION.md`, `docs/ROLE-CONTRACTS.md`, `bin/harness`
- verify: 真实 HOME 的 doctor 与 migrate/hooks dry-run 均 exit 0；准确报告 7 个注册、4 个已发现 Agent、Codex 1 个 legacy 区块、Claude/Codex 0/4 Observer Hook；Shell/JSON 语法与 `./generate.sh --check` 通过
- notes: 文档固定 doctor → migrate dry-run → hooks dry-run → 应用 → 新会话验证路径；应用动作未获显式授权，没有改写真实配置。

### Step 82/83/90 — 2026-08-13 · 真实部署阶段
- files: `~/.mick-harness`, `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.claude/settings.json`, `~/.codex/hooks.json`, `scripts/harness-observe.py`, `bin/harness`, `tests/test_harness_agents.py`, `tests/test_harness_observe.py`
- verify: 用户明确授权后完成全局安装备份、Loader 迁移、4/4 生命周期 Hook 合并和 6425 重启；二次 migrate/hooks dry-run 均 changed=false；服务 health=ok、5 个登记/4 个有效项目；全量 68 tests / 0 failures；真实浏览器显示 7 个 Agent 五层状态且 console 0 errors
- notes: 安装备份位于 `~/.local/state/mick-harness/backups/v0.17-preinstall-20260813`；Claude/Codex 当前显示“加载待真实会话”是正确状态。当前任务启动早于 Hook 安装，必须由新会话产生规则版本事件后才能勾选 task-82/83；真实行为评分仍待单独授权。

### Step 88 修正 — 2026-08-13
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `bin/harness`
- verify: 验证通过：Collector 0.4.0 会按顶部进度范围选择当前版本的 79-90 步骤，并把解析器版本纳入计划事件幂等键；产品版本由 `VERSION` 显示为 0.17.0，旧 Git revision 仅作附加证据；全量 68 tests / 0 failures
- notes: 修复前真实工作台仍显示旧首段 7/7；修复后同一 plan 会通过 append-only 新事件重新投影，不覆盖历史账本。

### Step 87 审查 — 2026-08-13
- files: `docs/VERSIONS.md`, `plan.md`
- verify: 七份角色文件均为 48–50 行且无已知项目名或技术栈绑定；`python3 -B -m unittest tests/test_role_contracts.py` 为 6 tests / 0 failures；真实 `/api/agents.json` 显示 Claude Code 已有加载与回写证据、Codex 仍只有配置证据；`harness brain status` 显示 Brain 仓库和 Claude/Daily 接入可用，但 Codex/Generic 仍未接入
- notes: v0.17 角色结构优化已完成，但真实 Agent 行为评测尚未完成，因此 task-87 保持未勾选；Reviewer 的验证边界、Designer 的通用审美边界及跨角色重复流程语句列为收尾项。Brain 当前属于“连接健康、触发覆盖与回写可靠性不足”，相关产品化改造已立项到 v0.18.0。

### Step 87 角色收尾 — 2026-08-13
- files: `rules/roles/*.md`, `rules/roles/orchestration.md`, `docs/ROLE-CONTRACTS.md`, `tests/test_role_contracts.py`, installed `~/.mick-harness/rules/roles/*.md`, installed `~/.mick-harness/docs/ROLE-CONTRACTS.md`
- verify: 新增约束先得到 3 个预期失败；修正后角色测试 9 tests / 0 failures，全量 71 tests / 0 failures，`./generate.sh --check` 与 `git diff --check` 通过；源文件和安装副本逐文件一致
- notes: Reviewer 可为 finding 执行最小验证但不接管 QA；Designer 角色只保留通用职责，具体审美方法由内置、按需加载的 `designer-craft` 提供，外部 Skill 仅作已审计上游参考；共享回合卡片和 handoff 机制只在 orchestration 定义一次。task-87 仍等待真实 Claude Code/Codex 行为样本，不因静态测试通过而勾选。

### Step 90 发布审查 — 2026-08-13
- files: `.gitignore`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `docs/AGENT-SUPPORT.md`, `plan.md`
- verify: 全量 71 tests / 0 failures；Shell/Python/JSON、`./generate.sh --check`、`git diff --check` 通过；Harness Check 18 PASS / 1 optional warning / 0 FAIL；真实 6425 服务重启后 health=ok、outbox_remaining=0；浏览器验证总览、角色办公室、版本规划、Markdown/代码阅读，console 0 errors
- notes: 发布审查未发现代码级 blocking finding；已补双语 v0.17 changelog、部署后支持状态与 Python cache 忽略。发布仍停止在两个外部 Gate：Codex 命令 Hook 必须由用户在 `/hooks` 信任后启动新会话形成真实事件；GitHub CLI 当前未登录（无效 `GITHUB_TOKEN`，移除变量后仍显示未登录）。未提交、未推送、未打 Tag，v0.17 保持 in_progress。

### Step 82/83/87 验收补证 — 2026-08-13
- files: `docs/AGENT-SUPPORT.md`, `docs/ROLE-CONTRACTS.md`, `tests/test_role_contracts.py`, `plan.md`, `docs/VERSIONS.md`
- verify: Codex CLI 四类 Hook 已由用户信任；同一真实 session 产生 SessionStart → TurnStart → TurnCompleted → SessionEnd，事件均携带 `rule_version=0.17.0` 与角色 digest；真实 Reviewer 样本五维均 2/2，总分 10/10；全量 71 tests / 0 failures
- notes: Claude Code 已有真实 Loader 与 session start/end 证据，但用户于 2026-08-13 退出账号并决定继续发布，完整 turn 与行为样本明确列为发布例外并保持“未验证”；不以 Codex 样本代替 Claude 状态，也不再次发起 Claude 登录或模型调用。

### Step 90 发布 Gate 完成 — 2026-08-13
- files: `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `docs/VERSIONS.md`, `docs/AGENT-SUPPORT.md`, `docs/ROLE-CONTRACTS.md`, `plan.md`
- verify: 全量 71 tests / 0 failures；Shell/Python/JSON、`./generate.sh --check`、`git diff --check` 均通过；Harness Check 18 PASS / 1 optional warning / 0 FAIL；6425 service status 为 healthy、outbox_remaining=0；发布提交 `8b8e94e` 已快进到远端 `main`
- notes: v0.17.0 已发布并进入 Tag 收尾，v0.18.0 同步切为 in_progress；Claude 完整评测例外已写入结构化决策和支持文档，不影响 Codex 全链路证据，也不被表述为 Claude 已通过。

## v0.18.0 · 2026-08-17 · Brain 可靠写入与工作台闭环

### 版本目标

让 Brain 不再依赖用户结束会话或某一个 Agent 的转录文件。Claude、Codex 和通用 Harness 入口都以结构化事件作为可靠来源：项目内已经确认的需求、决策、验证、交付与交接自动沉淀到项目 Brain；跨项目偏好与版本化 Profile 先进入工作台审批箱。所有记录都先在本机保存，再异步同步远端，并分别展示“已识别、已写入本地、待同步、同步成功、同步失败”，避免用单一“已连接”掩盖故障。

### 产品边界

- 项目记忆默认免审批，因为项目细节数量大且人的注意力难以持续跟踪；工作台提供纠正、撤销、合并和提升为全局候选的入口。
- 全局 Brain 与版本化 Profile 必须审批，支持编辑后批准、调整目标层级、合并、拒绝、忽略同类和失败重试。
- SessionEnd 只做可选压缩与补漏；用户不关闭会话也不能造成项目记忆长期不写入。
- 原始对话、模型私有思维、Prompt、完整工具日志、密钥和无法归属项目的内容不得进入 Brain。
- 6425 只开放明确的 Brain 白名单动作，不向浏览器暴露任意命令或任意文件写入。

### 实施步骤

- [x] 94. [真实健康] 展示 Brain 仓库、本地写入、远端同步、Agent 事件覆盖、最近尝试/成功/错误、定时补漏与候选积压，状态必须来自真实文件、进程与 Git 结果。
- [x] 95. [统一入口] 让 Claude、Codex 与通用 Harness 的结构化事件进入同一识别、脱敏、去重链；移除主链对 SessionEnd transcript 的依赖，并把旧转录提炼降级为默认关闭的补漏来源。
- [x] 96. [项目自动记忆] 已确认的项目需求、版本阶段、决策、验证经验、完成结果、评审结论、交接和关键产物自动写入项目 Brain；推断、原始日志、重复进度与敏感信息必须被拒绝。
- [x] 97. [全局审批箱] 全局偏好和 Profile 变更进入 6425 审批箱，支持批准、编辑后批准、换层、合并、拒绝、忽略同类和重试；项目自动记忆另有可撤销活动流。
- [x] 98. [工程预算] 采用 `fast / subsystem / release` 三档验证，同一代码和环境下不重复发布 Gate；预算是 0.18 的工程约束，不扩展为独立产品功能。
- [x] 101. [首个 Profile 消费者] 保留已经实现的 `prd-for-humans` 与 PRD Profile，作为版本化 Profile 审批、元数据展示和差异预览的首个真实用例，不在本版本继续扩张 PRD 功能范围。
- [x] 102. [工作台层级] 将 Brain 降为项目总览中的记忆服务入口；版本规划按语义版本从新到旧排列；Git 用“工作区—分支—版本—标签”关系图替代重复状态文字。
- [x] 103. [Brain 可视化同步] 展示实际 Brain 本地仓库、配置/实际远端、当前分支和写入来源/目标；为待同步状态提供受控、可确认、可审计的同步动作与成功/失败反馈。
- [x] 104. [自动化优先与信息精简] 将 Brain 工作台的待同步与全局/Profile 待审批明确分开，仓库只突出配置目标和生效状态；确立“服务端自动化主链、Hook 仅采集、Prompt 仅语义辅助”的实现边界。

外部 Skill 兼容诊断、`mattpocock/skills` 的进一步角色适配，以及通用 Harness 更新/注入操作中心移入 v0.19 候选，不占用本版本 Brain 主线。

### 成本与兼容验收

- 不保存或展示模型 chain-of-thought；有平台 Token 计数时记录输入/输出总量，没有时只记录可见上下文字节、工具输出字节、测试数量和耗时作为代理指标。
- 用五类代表任务建立 v0.17 基线，v0.18 的中位可见上下文与工具输出至少下降 30%，同时不得降低需求覆盖或验证通过率；完整发布 Gate 每个候选提交最多执行一次，除非代码、环境或 Gate 自身发生变化。
- 外部 Skill 的安装预览必须明确显示“可共存 / 需适配 / 冲突阻止”；`mattpocock/skills` 整包在当前 Harness 下应判为“需适配”，不能直接判为安全共存。
- 角色文件继续保持精简，只存职责、边界和 Skill 指针；任何外部方法不得覆盖用户授权、Harness Tripwire、`plan.md`、回合回写或完成验证。
- PRD 风格资料目前判定为“内容保留、触发退化”：Brain 与 Git 历史仍有完整规则，但当前 PM 仅有弱提示；2026-08-14 用户已裁决冲突——PRD 只服务人类产品评审，不包含技术细节或任何 AI 交付内容，旧 Profile 中相反规则必须在迁移时废止而不是继续参与优先级竞争。

### v0.18 补充需求审查 — 2026-08-13
- files: `docs/VERSIONS.md`, `rules/skills/SOURCES.md`, `plan.md`
- verify: 只读审查 `mattpocock/skills@8b78b531ab965735c5dc74f6f7a219e1e37326df` 的 MIT License、setup 与 15 个核心候选 Skill；检索当前 PM/Planner、Brain PRD Profile、历史 v0.16 PM 规则和 v0.18 版本范围；本轮仅修改规划文档，采用聚焦 Markdown/diff 检查，不运行无关全量端到端测试
- notes: 上游强调小型可组合 Skill、领域语言与紧反馈环，方向与 Harness 相容；冲突集中在安装入口、文档所有权、Issue Tracker、自动提交/子 Agent、无上限访谈和完成定义，因此采用固定版本的选择性方法适配，而非整包加载。

### v0.18.0 · 2026-08-14 · PRD 只面向人类产品评审

- decision: PRD 的用途是让产品、业务、设计和研发等人类参与者评审“为什么做、为谁做、做什么、做到哪里、如何判断成立”；它不是开发指南，也不是给 Agent 的执行输入。
- hard-fail: PRD 出现文件路径、函数/类/组件、接口/字段、数据库、框架版本、CSS/像素、System Prompt、Reasoning Pipeline、模型参数、Data Contract、机器输出格式或 Agent 操作步骤时，默认判定为技术污染；产品自身的业务阈值、规则公式和用户可见状态不属于技术污染。
- artifact-boundary: AI 功能需要实现约束时，单独创建 `docs/AI-CONTRACT-<feature>.md`；只有用户明确要求 AI 交付契约时才生成，PRD 不附赠、不内嵌、不链接尚不存在的契约。
- architecture: PM 角色只负责需求探索与产品判断；显式请求 PRD 时再加载按需 `prd-for-humans` Skill；个人风格存在 Private Brain 的版本化 Profile，公开 Harness 只保留通用人类评审结构和加载协议。
- regression: 以至少 3 份用户认可的真实 PRD 建立黄金样例，并加入技术污染反例；先检查产品判断是否完整，再检查风格一致性，禁止用“章节齐全”代替质量。
- feedback-loop: 用户对 PRD 的纠正先记录为候选差异，区分一次性内容修改与稳定写作偏好；只有用户确认是长期偏好后才升级 Profile 版本，避免每次反馈让模板漂移。
- verify-plan: 对同一需求做“当前链路输出 / 新 Skill 输出”盲评，比较人类可读性、产品判断、范围清晰度、需求覆盖和风格一致性；任一技术污染项命中即不合格，不用总分抵消。

### Step 101 实现进展 — 2026-08-14
- files: `rules/skills/prd-for-humans/`, `rules/roles/pm.md`, `rules/skills/SOURCES.md`, `tests/test_prd_for_humans.py`, `tests/fixtures/prd-for-humans/technical-pollution.md`, Private Brain `global/profiles/prd/` 与 `global/preferences.md`
- verify: 新增测试先以 3 failures / 4 errors 形成基线，并对无效 Profile 降级补充 1 个预期失败；实现后聚焦测试 17 tests / 0 failures，Skill Creator validator 返回 `Skill is valid!`，三份结构样例均通过技术污染检查，真实 Private Profile 解析为 `private_brain v1.0.0` 且无诊断错误
- notes: PRD Profile 已从固定骨架改为“严格产物边界 + 自适应章节”；三份 Harness 维护样例覆盖小需求、数据需求和分期需求，检查器明确允许业务公式、阈值与用户可见状态。task-101 暂不勾选：仍需用户选择或认可 3 份真实 PRD 做盲评，并把 Profile 版本/来源元数据接入工作台，期间不得展示私人正文。

### v0.18.0 · 2026-08-17 · Brain 主链与项目自动记忆
- files: `scripts/harness-brain-boundary.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`, `config/.brain-config.yaml`, `docs/BRAIN-INTEGRATION.md`, `tests/test_harness_agents.py`, `tests/test_harness_observe.py`, installed `~/.mick-harness` runtime files
- verify: Brain/Observer/PRD 子系统 77 tests / 0 failures，Shell/Python、`./generate.sh --check` 与 `git diff --check` 通过；真实 6425 重启后 5 个登记/4 个有效项目、outbox 0；浏览器 `?view=brain` 显示本地写入、远端同步、项目记忆、审批箱和 Profile，console 0 errors
- notes: 结构化事件成为 Claude/Codex/通用入口的共同主链，SessionEnd 转录提炼默认关闭且仅作为旧补漏；项目记忆自动本地写入并支持纠正、撤销、提升，历史回填从 1037 条事件按语义合并为 162 条可读记忆。task-97 保持未勾选：候选合并/忽略同类与远端重试尚未完成，其中远端推送涉及私有内容外发，需要用户对目标仓库与范围单独授权。

### v0.18.0 · 2026-08-17 · 工作台信息层级与 Git 关系图
- files: `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `docs/VERSIONS.md`, `plan.md`, installed `~/.mick-harness` runtime files
- verify: 新增四项契约先得到 4 个预期失败；实现后全量 87 tests / 0 failures，Python/HTML/JavaScript、`./generate.sh --check` 与 `git diff --check` 均通过；6425 重启后 health=ok、5 个登记/4 个有效项目；真实浏览器确认侧栏无并列 Brain 导航、总览内可进入并返回 Brain、版本首项为 v0.18.0、Git 关系图只显示一次 14 处待提交状态，页面日志 0 条
- notes: Brain 管理能力仍保留独立页面，但它的产品层级属于项目总览；版本排序使用语义版本而非字符串或文件顺序；Git 图按分支归组版本和发布标签，未关联版本的真实分支继续显示。

### v0.18.0 · 2026-08-17 · Brain 写入路径与可视化同步
- files: `scripts/harness-brain-boundary.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_agents.py`, `tests/test_harness_observe.py`, `docs/VERSIONS.md`, `plan.md`, installed `~/.mick-harness` runtime files
- verify: 全量 89 tests / 0 failures；Python、HTML、JavaScript、`./generate.sh --check` 与 `git diff --check` 均通过；6425 重启后 health=ok、5 个登记/4 个有效项目；真实浏览器显示本地仓库、配置/实际远端、分支、四类写入路径与来源，页面日志 0 条
- notes: 同步只允许当前 Brain 仓库的 upstream，配置远端与实际 origin 不一致、远端领先、存在管理范围外的已暂存文件或未确认时都会拒绝；首次浏览器验收时自动化环境接受了系统确认框，已把当时 1065 条底层记录同步为 Brain 提交 `efb0672`，目标确认为 `configured private Brain origin` 的 `main`。随后已改为页面内“立即同步 → 确认并同步/取消同步”两步操作，消除系统确认被自动接受的风险。

### v0.18.0 · 2026-08-17 · 自动化优先与 Brain 信息精简
- files: `scripts/harness-brain-boundary.py`, `web/observe-dashboard.html`, `docs/BRAIN-INTEGRATION.md`, `tests/test_harness_agents.py`, `tests/test_harness_observe.py`, `docs/VERSIONS.md`, `plan.md`, installed `~/.mick-harness` runtime files
- verify: 新增契约先得到 1 failure / 1 error；实现后聚焦测试 2 tests / 0 failures、全量 89 tests / 0 failures，Python/JavaScript、`./generate.sh --check` 与 `git diff --check` 通过；6425 重启后 health=ok；真实浏览器确认总览分别显示项目记录待同步与全局/Profile 待审批，Brain 仓库只显示配置目标、生效状态和当前分支，空审批箱解释审批范围，页面日志 0 条
- notes: 可确定的项目扫描、状态识别、去重、落盘、队列、重试、仓库核对和同步保护由常驻服务代码负责；Hook 只将不同 Agent 节点适配为结构化事件，Prompt 只用于摘要与跨项目语义判断。计划、版本与 Git 等可观察事实不因 Hook 或会话未关闭而停止沉淀；仅存在于对话中的语义事实仍需事件适配或后续服务端语义处理，远端推送和全局/Profile 发布保留用户控制。

## v0.18.0 · 2026-08-18 · 工作台与项目概览设计修正

### 用户目标

保留 DS 分支已经建立的全局/项目导航结构，但重做工作台和项目概览的视觉层级与内容表达：用户进入页面后先看见待处理事项、当前推进项目、当前版本、负责人和下一步，而不是平均权重的卡片、后台表格或大段原始事件摘要。

### 设计方向

- 页面模式为 **Operate**：第一注意力是“现在该处理什么”，第二层是“哪些项目正在推进”，系统诊断退居背景。
- 视觉气质采用安静、克制的个人工作指挥台；以排版、空间和对比建立层级，不靠渐变、卡片矩阵、过量胶囊或装饰动画。
- 全局导航与项目列表分层：全局导航保持稳定，项目列表只承担切换，不重复展示首页已有的完整项目状态。
- 用户语言优先：默认界面不展示内部 task/seq、原始事件类型或未经整理的英文/技术摘要；真实事实保持不变，技术细节可在诊断层查看。

### 范围与禁止项

- 只修改 `web/observe-dashboard.html`、`tests/test_harness_observe.py` 和本段 `plan.md`；不修改后端 API、事件投影、版本/产物/Brain 页面业务，不新增依赖。
- 只在 `feat/design-refactor` 上开发并使用 `127.0.0.1:6246` 验收；不修改 main，不安装到 `~/.mick-harness`，不重启 6425 服务。
- 工作台不得继续使用承载长段落的六列表格；项目概览不得把版本目标拆成同权重的六格卡片。
- 不虚构项目优先级、角色状态或下一步；缺少可确定信息时显示简短空态，不从事件文本猜测。

### 实施步骤

- [x] 105. [修改] `tests/test_harness_observe.py` — 固定工作台首屏层级、精简项目行、项目概览主次关系、角色流转语义、窄屏与无障碍设计契约，并记录当前设计分支基线。
- [x] 106. [修改] `web/observe-dashboard.html` — 重构工作台和项目概览的布局、排版、内容摘要、交互反馈与响应式状态；保留 DS 导航架构及既有数据来源。
- [x] 107. [运行] 聚焦与全量验证，在 6246 完成工作台 → 项目概览 → 角色详情 → 返回/刷新真实路径，并检查桌面与窄屏截图；不部署 6425。

### Interaction QA

- 工作台：首屏按“待处理 → 推进项目 → 最近交付 → 系统状态”建立明确层级，项目行可进入真实项目，长摘要被压缩为可扫读下一步。
- 项目概览：首屏同时可识别当前版本、完成度、负责人、下一步和阻塞；长期项目目标为辅助信息，角色流转只高亮真实来源与建议目标。
- 状态往返：工作台进入项目、打开角色详情、关闭详情、返回工作台与刷新后 URL/选择保持正确。
- 响应式：1440×900、1024 宽度和约 390 宽度均不出现关键操作溢出、六列硬挤或只能横向滚动才能理解的主内容。
- 可访问性：交互项具备语义、可见焦点与键盘路径；状态不只依赖颜色，动画遵守 reduced-motion。

### 完成判定

- [x] 1440×900 首屏无需滚动即可看见主要待处理、至少三个推进项目及进入项目的动作。
- [x] 用户可在项目概览五秒内指出当前版本、负责人、下一步和阻塞；页面不再出现六格同权重信息墙。
- [x] 项目长摘要在默认列表中保持两行以内，完整内容进入详情或辅助文本，不破坏真实状态。
- [x] 角色状态明确区分当前负责、等待接手、建议下一步、已交付和未参与，箭头起点/终点含义唯一。
- [x] 聚焦测试、全量 unittest、HTML/JavaScript、`git diff --check` 均通过；6246 真实页面 console 无 error。

### Step 105 设计契约基线 — 2026-08-18
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 原导航/角色投影聚焦测试 2 tests / 0 failures；新增工作台与项目概览设计契约按预期得到 1 failure，首个缺失标记为 `nav-section-label`
- notes: 契约要求用可扫读项目行替代后台表格、用主版本叙事替代六格信息墙，同时固定两行摘要、窄屏和 reduced-motion 边界；本轮只证明旧布局尚未达标，尚未声明页面完成。

### Step 106 页面实现 — 2026-08-18
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 新设计契约与原导航、角色工作、项目目标投影聚焦测试 4 tests / 0 failures；HTML 标准解析与 JavaScript 语法检查均通过；`git diff --check` 通过
- notes: 工作台改为待处理优先带 + 可扫读项目行 + 次要交付/系统区；项目概览改为版本主叙事 + 负责人/下一步/阻塞命令区 + 辅助长期目标 + 明确语义的角色流转。全量测试首次在受限沙箱内得到 49 pass / 1 failure / 4 permission errors，其中 failure 为旧文案契约且已修正，4 个 error 均为测试无法绑定本地临时端口，需在允许本地端口的环境复跑。

### Step 107 真实交互与回归验收 — 2026-08-18
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 全仓 90 tests / 0 failures；HTML、JavaScript、`./generate.sh --check`、`git diff --check` 均通过；6246 真实数据完成工作台 → 项目概览 → 设计角色详情 → 关闭 → 返回工作台 → 刷新，桌面 1440×900 与窄屏 390×844 截图通过，console 0 warning / 0 error
- notes: 窄屏首次验收发现项目侧栏把主内容推离首屏，已改为全局导航横排、项目概览只聚焦当前项目；角色流转历史按来源/目标/类型去重，保留五条不同语义记录。当前修正版仅存在 `feat/design-refactor` 工作区，未安装到用户目录、未重启 6425、未修改 main。

## v0.18.0 · 2026-08-18 · 工作台审批闭环与 Brain 精简

### 用户裁决

- 全局“项目”与“工作台”内容重复，移除“项目”；独立“待处理”也不再作为一级页面。
- 项目阻塞与待验证状态合并进工作台项目行；Brain 待同步、全局偏好与 Profile 候选必须能从工作台或本地写入路径直接进入对应操作区。
- Brain 仓库默认只展示配置仓库与生效状态；分支继续参与同步安全校验和最终确认，但不占用普通阅读层级。

### 实施步骤

- [x] 108. [修改] `tests/test_harness_observe.py` — 固定精简导航、项目行待处理、Brain 聚焦跳转、可操作写入路径和单行仓库契约，并记录旧页面预期失败。
- [x] 109. [修改] `web/observe-dashboard.html` — 移除重复入口与独立待处理页，把项目事项归入项目行，为同步/审批/记忆活动提供直达操作，并压缩 Brain 仓库。
- [x] 110. [运行] 聚焦与全量回归，在 6246 验证工作台项目事项 → Brain 同步确认、审批区、写入路径和返回工作台；不执行真实远端同步，不修改 main/6425。

### 完成判定

- [x] 一级导航只保留“工作台”和“设置”，旧 `view=projects|inbox` 自动回到工作台。
- [x] 每个项目行显示自己的阻塞/待验证数量并可进入项目；跨项目的同步与审批项可直接跳到 Brain 对应操作区。
- [x] Brain 顶部待同步、待审批和项目记忆指标可点击；本地写入路径提供与其真实权限一致的动作，不制造不可执行按钮。
- [x] Brain 仓库压缩为一行，只显示配置仓库和生效状态；分支只在同步确认与安全诊断中出现。
- [x] 6246 真实浏览器完成状态往返，console 0 error；全仓测试、HTML/JavaScript 与 diff 检查通过。

### Step 108 交互契约基线 — 2026-08-18
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 新增导航与 Brain 操作闭环契约按预期得到 1 failure，首个缺口是旧导航仍包含 `[“projects”, “项目”]`
- notes: 契约同时固定了项目行待验证/阻塞提示、Brain 区域直达、写入路径动作与单行仓库；本步只证明旧页面尚未闭环。

### Step 109 页面闭环实现 — 2026-08-18
- files: `web/observe-dashboard.html`, `plan.md`
- verify: 新契约 1 test / 0 failures，HTML 标准解析与 JavaScript 语法检查通过；6246 真实页面只剩“工作台 / 设置”两个全局入口
- notes: 项目阻塞/待验证已进入各自项目行；Brain 指标与写入路径直达项目记忆、审批或同步区；仓库收缩为“配置仓库 + 生效状态”单行，分支只留在同步二次确认中。

### Step 110 全量与真实交互验收 — 2026-08-18
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 全仓 91 tests / 0 failures；HTML、JavaScript、`./generate.sh --check` 与 `git diff --check` 全部 exit 0；6246 真实页面 console 0 warning / 0 error
- notes: 已验证旧 `view=projects` 回落工作台、项目行与失效项目诊断进入、项目记忆/审批/同步聚焦及刷新恢复、同步二次确认后取消和返回工作台；未点击“确认并同步”，未改动 main/6425。

## v0.18.0 · 2026-08-18 · 单一服务下的多分支开发现场

### 用户目标

本机始终只有一个 Harness 后端服务和一个工作台。项目以 Git 仓库为身份；不同 worktree、分支与 Agent 开发现场只是同一项目下的子状态，不能要求用户为每条分支启动另一套服务，也不能把 worktree 误登记成多个项目。

### 范围与禁止项

- 本轮先交付可验证的 V0 投影：识别同仓库的全部 worktree、已检出分支和工作区状态，并允许版本同时声明“集成目标分支”和多个“工作分支”。
- 保留现有 `project_id` 与历史运行数据的兼容性；新增仓库级身份，不在本轮迁移历史事件目录或合并多个已登记项目的数据。
- 只修改 `scripts/harness-observe.py`、`tests/test_harness_observe.py`、`docs/VERSIONS.md`、`web/observe-dashboard.html` 和本段 `plan.md`；不新增依赖。
- 只在 `feat/design-refactor` 与 6246 预览服务验收；不切换/删除真实分支，不修改 main，不安装到 `~/.mick-harness`，不重启 6425，不执行远端同步。
- “已检出工作区”只表示 Git worktree 存在，不推断 Agent 正在运行；Agent 活跃度必须等待真实 session/heartbeat 证据。

### 实施步骤

- [x] 111. [修改] `tests/test_harness_observe.py` — 用临时 Git 仓库和多个 worktree 固定仓库身份、工作区状态、目标分支/工作分支关联与页面语义，先记录旧实现的预期失败。
- [x] 112. [修改] `scripts/harness-observe.py` — 从 Git common dir 生成稳定仓库身份，读取 `git worktree list --porcelain`，投影每个工作区的分支、HEAD、脏状态，并解析版本的多个工作分支。
- [x] 113. [修改] `docs/VERSIONS.md` — 为 v0.18.0 明确 `main` 是集成目标，`feat/v0.18-brain` 与 `feat/design-refactor` 是当前工作分支。
- [x] 114. [修改] `web/observe-dashboard.html` — 在同一项目的 Git 图中展示多个已检出工作区，并区分集成目标、工作分支和普通分支；不把它们渲染成多个项目。
- [x] 115. [运行] 聚焦与全量回归，使用临时多 worktree 仓库验证后端投影，并在 6246 验证真实项目页面和刷新路径。

### Interaction QA

- 用户在一个项目页面内看到仓库身份、全部已检出工作区、每个工作区所在分支和待提交状态。
- 同一个版本可同时关联一个集成目标分支和多个工作分支；`main` 不再被误解为“当前所有开发都发生在这里”。
- 没有 worktree 的本地分支仍可见，但明确显示为“未检出”；工作区存在不等于 Agent 活跃。
- 从工作台进入项目、切到版本规划并刷新后，项目与视图选择保持正确；console 无 error。

### 完成判定

- [x] 从同一仓库的两个 worktree 调用快照时得到相同 `repository_id`，且两处工作区只归属于同一仓库。
- [x] v0.18.0 同时关联 `main` 集成目标与两条工作分支，当前 design 工作区不再触发错误的分支冲突提示。
- [x] 页面将 worktree 称为“已检出工作区”，不虚构“活跃 Agent”；每个工作区只显示一次自己的脏状态。
- [x] 聚焦测试、全量 unittest、HTML/JavaScript、`./generate.sh --check` 与 `git diff --check` 通过；6246 真实页面 console 无 error。

### Step 111 多工作区契约基线 — 2026-08-18
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 新增 2 项聚焦契约得到预期的 1 error / 1 failure；后端首个缺口为快照没有 `repository_id`，页面首个缺口为没有“同一仓库”语义
- notes: 测试只创建并回收临时 Git 仓库和 worktree，不切换或修改真实项目分支；契约明确“已检出工作区”不等于“活跃 Agent”。

### Step 112–113 仓库投影与版本归属 — 2026-08-18
- files: `scripts/harness-observe.py`, `docs/VERSIONS.md`, `plan.md`
- verify: 临时双 worktree 后端契约与原 Git/版本契约共 3 tests / 0 failures；两个入口产生相同 `repository_id`，design 工作区识别 1 处未提交状态，v0.18.0 当前分支不再被误报冲突
- notes: `main` 继续作为集成目标，`feat/v0.18-brain` 与 `feat/design-refactor` 显式登记为工作分支；后端只确认 worktree 已检出，不推断 Agent 在线。

### Step 114–115 页面与真实路径验收 — 2026-08-18
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 全仓 93 tests / 0 failures；Python、HTML、JavaScript、`./generate.sh --check` 与 `git diff --check` 全部 exit 0；6246 刷新后保留版本 URL，识别 1 个仓库、1 个已检出工作区、2 条工作分支、1 个集成目标，旧分支冲突提示为 false，console 0 warning / 0 error
- notes: 真实仓库当前只有 `feat/design-refactor` 一个 worktree，因此 `feat/v0.18-brain` 正确显示为“未检出”；临时双 worktree 测试已证明增加第二个 worktree 后会自动归入同一仓库和工作台。当前实现未迁移旧 `project_id` 或聚合多个已登记 worktree 的历史事件，这一兼容迁移留给后续阶段。

## v0.18.0 · 2026-08-18 · Brain 连接与同步透明化

### 用户目标

把 Brain 从一个过重的独立工作台收敛为“设置 → 记忆与同步”。用户在操作前必须看懂本地记录在哪里、远端连接到哪里、哪些内容会进入本次同步、哪些内容明确不会上传，并按“待同步 → 全局审批 → 项目记忆 → 连接与高级设置”的顺序完成操作。

### 产品边界

- 本地写入与远端同步继续分离；本轮不执行真实同步，也不修改用户 Brain 仓库、远端地址或凭据。
- 项目事实仍免审批写入本地；全局偏好与 Profile 仍先审批；Session 只作为默认关闭的补漏来源，不作为正式记忆层。
- 同步前必须由后端生成真实清单，包含目标仓库/分支、按范围和项目分组的记录、涉及文件、当前待推送提交以及明确排除的内容。
- 页面不得根据数量猜同步内容；清单无法生成、仓库不匹配、远端领先或存在异常时，不得出现可执行的最终同步确认。
- 只在 `feat/design-refactor` 和 6246 验收；不合并 main，不安装到 `~/.mick-harness`，不重启 6425，不执行 Git push。

### 实施步骤

- [x] 116. [修改] `tests/test_harness_agents.py` 与 `tests/test_harness_observe.py` — 固定同步清单、范围/项目分组、待推送提交、隐私排除项、页面优先级、默认折叠与 Profile 降级契约，并记录旧实现预期失败。
- [x] 117. [修改] `scripts/harness-brain-boundary.py` — 扩展只读同步预览，返回真实目标、记录摘要、项目分组、涉及文件、待推送提交和安全说明，不改变确认同步的保护条件。
- [x] 118. [修改] `web/observe-dashboard.html` — 将页面改为“记忆与同步”，顶部展示可操作同步清单，其后依次为全局审批、默认折叠的项目记忆和默认折叠的连接/写入规则；Profile 只在审批或高级状态出现。
- [x] 119. [修改] `docs/BRAIN-INTEGRATION.md` — 面向用户说明收集范围、本地路径、审批规则、同步目标、Git push 边界、明确排除项和仅本地模式。
- [x] 120. [运行] 聚焦与全量回归，6246 完成“查看同步清单 → 展开记录/文件/提交 → 取消 → 审批 → 展开项目记忆 → 刷新”路径；不得点击最终同步。

### 完成判定

- [x] 用户在首次操作前能回答：连接到哪里、这次上传什么、不会上传什么、为什么需要审批、如何取消。
- [x] “查看同步清单”只执行 dry-run；最终确认只能在清单成功生成后出现，且清单明确说明 Git 会推送当前分支全部领先提交。
- [x] 页面顺序固定为待同步、全局审批、项目记忆、连接与高级设置；项目记忆和连接详情默认收起。
- [x] Profile 无候选时不再占据独立大卡片；有候选时在全局审批中展示版本差异。
- [x] 后端聚焦测试、全仓测试、HTML/JavaScript、`./generate.sh --check` 与 `git diff --check` 通过；6246 console 无 error。

### 验证记录

- Step 116 基线：聚焦测试按预期暴露旧实现缺口——后端同步预览缺少 `destination`（1 error），页面仍使用旧标题与旧层级（1 failure）；证明新契约能够捕获本轮目标，而不是由既有实现误通过。
- Step 117-119：聚焦合同 2 tests / 0 failures；同步预览返回真实仓库/上游、23 条项目记录、涉及文件、领先提交和明确排除项，页面与说明文档使用同一边界。
- Step 120：全仓 93 tests / 0 failures；`./generate.sh --check` 与 `git diff --check` 通过；6246 完成查看清单、展开记录/文件/提交、取消、展开两类折叠区与刷新，确认最终同步按钮存在但未点击，刷新后两类详情默认收起，console 0 error。

## v0.18.0 · 2026-08-19 · 审批动作与验证成本收口

### 版本归属决策

- “项目问题回流并修正中央 Harness”属于 **new value**：v0.18 的 Brain 分层写入、审批和同步目标不依赖它即可成立，因此正式分配到 draft `v0.19.0 / task-132`，不继续扩张 v0.18。
- v0.18 本轮只收口已在版本计划中的 `task-97`、`task-98` 与 `task-101`：补全已有审批流水线，减少同一代码/环境下重复发布验证，并用现有 PRD Profile 证明版本化 Profile 链路。

### 产品边界

- 审批动作只作用于 Brain 候选和项目记忆，不直接修改中央 Harness 规则；候选合并、忽略同类和换层都必须由用户显式触发并保留状态。
- 相似项只能由确定性规则提供建议，不能自动合并；合并前用户能看见目标摘要和涉及条目。
- 验证分为 `fast / subsystem / release` 三档；只有相同代码指纹、相同环境与相同命令集的成功 Gate 可以复用，失败或代码变化必须重跑。
- PRD 功能继续冻结：不新增章节模板或技术交付内容，只验证 `prd-for-humans`、Profile 来源/版本和差异审批已经贯通。
- 继续只在 `feat/design-refactor` 与 6246 验收；不合并 main、不安装到 `~/.mick-harness`、不重启 6425、不执行 Brain 远端同步。

### 实施步骤

- [x] 121. [版本规划] `docs/VERSIONS.md` — 正式建立 draft v0.19.0，并把 Harness 改进闭环分配为 `task-132`；记录它不进入 v0.18 的原因。
- [x] 122. [测试基线] `tests/test_harness_agents.py`、`tests/test_harness_observe.py` 与 `tests/test_harness_verify.py` — 固定候选换层/合并/忽略同类、项目记录合并、三档验证与成功 Gate 复用合同，并记录旧实现预期失败。
- [x] 123. [Brain 动作] `scripts/harness-brain-boundary.py` 与 `scripts/harness-observe.py` — 实现显式候选更新、确定性相似建议、合并/忽略同类和项目记录合并，保留审计状态并限制操作范围。
- [x] 124. [工作台交互] `web/observe-dashboard.html` — 为真实可用动作补齐换层、合并同类、忽略同类和项目记录合并入口；无建议时不展示无效按钮。
- [x] 125. [验证与 Profile] `scripts/harness-verify.py`、`docs/VERIFY-CONTRACT.md` 与现有 PRD/Profile 契约 — 实现 fast/subsystem/release 三档和指纹复用；验证 PRD Profile 来源、版本差异与发布链路后冻结功能范围。
- [x] 126. [验收] 聚焦与全量回归，在 6246 完成审批动作和刷新路径；只生成同步 dry-run，不执行最终同步。

### 完成判定

- [x] 项目记录和全局/Profile 候选的每个可见动作都能在工作台完成并得到刷新后的真实状态；不再只有说明文字或断点按钮。
- [x] “合并”和“忽略同类”都由用户确认；相似建议错误不会自动改变任何记录。
- [x] 同一 release 指纹第二次验证明确复用成功结果，代码、环境或命令变化后不复用。
- [x] `prd-for-humans` 仍只在用户明确要求 PRD 时加载；工作台只显示 Profile 来源、版本和差异，不泄露私人正文。
- [x] 全仓测试、生成文件、diff 检查与 6246 真实路径通过；未执行 Brain push、未部署 6425。

### 验证记录

- Step 121：`docs/VERSIONS.md` 已建立 draft v0.19.0；项目问题回流以 `task-132` 进入新版本，单次项目问题默认不改写中央 Harness。
- Step 122 基线：新增合同在旧实现上得到候选相似字段与项目记忆相似字段 2 errors、页面合同 1 failure、验证器缺失 2 errors；真实页面进一步复现 `prompt() is not supported`，随后补入禁止原生 prompt/confirm 的回归断言。
- Step 123-124：候选换层/合并/忽略同类、项目记忆合并与 HTTP 动作接口通过；页面改为内嵌表单与二次确认，不再依赖浏览器原生 prompt/confirm。
- Step 125：`fast / subsystem / release` 三档验证与成功 Gate 指纹复用测试通过；PRD 子系统验证覆盖 `prd-for-humans`、Profile 来源、版本与发布链路，功能范围保持冻结。
- Step 126：相关子系统 89 tests / 0 failures；发布 Gate 的全仓测试、`./generate.sh --check`、`git diff --check` 均通过，同一 release 指纹第二次返回 `REUSED`；6246 真实页面完成项目记录合并表单、纠正表单、同步清单、取消与刷新，console 0 warning / 0 error，未点击确认合并、确认同步或其他真实写入动作。

### Step 121 — 2026-08-19
- verify: passed — v0.19.0 draft 与 task-132 版本归属已由版本解析合同确认。

### Step 122 — 2026-08-19
- verify: passed — 新增测试先复现相似字段、验证器与原生弹窗缺口，再由回归断言固定。

### Step 123 — 2026-08-19
- verify: passed — Brain 候选与项目记忆动作通过单元及 HTTP 集成测试。

### Step 124 — 2026-08-19
- verify: passed — 6246 页面内合并与纠正表单可打开和取消，刷新后状态稳定，console 0 warning / 0 error。

### Step 125 — 2026-08-19
- verify: passed — PRD 子系统通过，release Gate 在相同最终指纹下返回 REUSED。

### Step 126 — 2026-08-19
- verify: passed — 全仓测试、生成一致性、diff 检查与 6246 真实路径均通过，未执行 Brain push 或 6425 部署。

## v0.19.0 · 2026-08-19 · 全局工作服务与项目接入可靠性

### 用户裁决

- 新项目接入后，前台 6246 能读取项目而产品端口 6425 消失；这不是可接受的预览差异，而是 v0.19 发布前必须消除的主服务可靠性缺口。
- 本机只能有一个全局 Harness 后端服务。项目、worktree、分支和 Agent 都接入同一服务，不能依赖用户手动维持另一套预览进程。
- 本问题以独立 `task-133` 进入 v0.19，作为 `task-130` 可视化注入/升级操作中心的前置 Gate。

### 已验证事实

- `main`、`~/.mick-harness` 与 6246 预览使用的 `scripts/harness-observe.py`、`bin/harness` 哈希一致；差异不在扫描代码版本，而在前台 `watch` 与 LaunchAgent 服务生命周期。
- 2026-08-19 18:24:41 新项目登记，18:24:45 服务最后正常响应，18:24:47 LaunchAgent 配置被重写；随后配置仍存在，但 `loaded=false`、`healthy=false`、6425 无监听。
- `install_service()` 当前总是先 `bootout`，再写入/启动新服务；重复安装没有健康短路，启动失败没有恢复旧配置和旧服务。

### 产品与工程边界

- 本阶段只修全局服务的幂等安装、失败恢复、项目接入保持在线和可复现验证；不提前实现 `task-131` Skill 兼容或 `task-132` Harness 改进审批闭环。
- 复用现有 Python 标准库、LaunchAgent 和 Observer 状态接口，不新增依赖，不新建第二套后台服务。
- 单元测试不得操作用户真实 LaunchAgent；真实 6425 验收放在代码测试通过之后，执行前保留现有 plist，并验证恢复路径。
- 不把 6246 可访问当作产品完成证据；发布声明必须来自 6425 LaunchAgent、项目组合 API 和重启后的真实状态。

### 实施步骤

- [x] 127. [测试基线] `tests/test_harness_observe.py` — 固定两条失败合同：健康且配置相同的服务重复安装不得 `bootout`；配置替换后的启动失败必须恢复旧 plist 并重新挂回旧服务。
- [x] 128. [生命周期修复] `scripts/harness-observe.py` — 将服务安装改为幂等事务：健康同配置直接复用；需要替换时保留旧配置和加载状态；任一步失败都尝试恢复并返回可诊断错误。
- [x] 129. [接入契约] `tests/test_harness_observe.py` — 固定新项目进入注册表后，已运行的全局服务不需要重装即可在下一轮扫描发现项目；前台 watch 与 LaunchAgent 使用同一注册表语义。
- [x] 130. [版本与使用说明] `docs/VERSIONS.md`、`docs/OBSERVE.md` — 将 `task-133` 标为 v0.19 阻断项，说明 init 只登记项目、install/update 如何安全维护全局服务及失败反馈。
- [x] 131. [真实验收] 运行聚焦与全量回归，再用临时注册项目验证 6425 在接入前后保持同一服务、项目可见、重启后仍健康；不发布、不推送。

### 完成判定

- [x] 对健康且配置相同的服务调用 install/update，不发生 `bootout`，PID 不变化，6425 持续可访问。
- [x] 模拟新配置 bootstrap 或健康检查失败时，旧 plist 被恢复；此前已运行的旧服务重新加载，错误中同时区分主失败与恢复结果。
- [x] `harness init <new-project>` 只登记项目；全局 Observer 下一轮自动发现它，不要求重装或另启端口。
- [x] 聚焦测试、全仓测试、生成一致性与 diff 检查通过；真实 6425 在接入、刷新和重启路径上健康。

### Step 127 — 2026-08-19
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_harness_observe.ObserveRuntimeTests.test_install_service_reuses_matching_healthy_service tests.test_harness_observe.ObserveRuntimeTests.test_install_service_restores_previous_service_when_bootstrap_fails` 得到预期 2 failures；旧实现重复安装调用 4 次 launchctl，bootstrap 失败后未恢复旧 plist
- notes: 基线只使用临时 HOME 与 mock launchctl，没有操作用户真实 LaunchAgent。

### Step 128 — 2026-08-19
- files: `scripts/harness-observe.py`, `plan.md`
- verify: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_harness_observe.ObserveRuntimeTests.test_install_service_reuses_matching_healthy_service tests.test_harness_observe.ObserveRuntimeTests.test_install_service_restores_previous_service_when_bootstrap_fails tests.test_harness_observe.ObserveRuntimeTests.test_launch_agent_plist_keeps_observer_alive` passed，3 tests / 0 failures
- notes: `start_service()` 不能恢复旧 plist 或旧加载状态，因此新增窄职责 `restore_previous_service()`；失败错误同时保留主错误与 rollback 结果。

### Step 129 — 2026-08-19
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_harness_observe.ObserveRuntimeTests.test_portfolio_monitor_syncs_without_dashboard_request` passed，1 test / 0 failures
- notes: 测试在 Observer 已运行后才写入新项目，随后确认同一进程仍存活、组合 API 出现新项目且后续 plan 变化继续同步；没有调用 service install。

### Step 130 — 2026-08-19
- files: `docs/VERSIONS.md`, `docs/OBSERVE.md`, `plan.md`
- verify: `parse_versions_markdown()` 读取真实 `docs/VERSIONS.md` 后确认 v0.19 为 `in_progress`、分支为 `feat/v0.19-service-reliability` 且包含 `task-133`；`git diff --check` passed
- notes: 文档明确 6246/6426 等前台端口只作开发对照，产品 Gate 始终是唯一的 6425 LaunchAgent。

### Step 131 — 2026-08-19
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `docs/VERSIONS.md`, `docs/OBSERVE.md`, `plan.md`
- verify: 全仓 `100 tests / 0 failures`；`./generate.sh --check`、Python syntax、`git diff --check` passed；真实 6425 首次启动与重复 install 的 PID 均为 `80473`，Portfolio 识别 `narc_for_mac` 为 valid；恢复原 plist 后 6425 PID `81270` 健康且新项目仍为 valid
- notes: 真实验收临时让 LaunchAgent 指向功能分支，结束后已恢复 `~/.mick-harness`；未发布、未推送、未保留第二套后台服务。

## v0.19.0 · 2026-08-20 · 工作台受控操作中心

### 用户目标

- 用户不再需要回到终端完成 Harness 更新、项目注入或 Agent 修复；工作台先解释将修改什么，再由用户确认执行。
- 这些确定性工作由固定脚本完成，不依赖 Agent 是否记得 Prompt，也不允许前台拼接或提交任意命令。
- 操作必须有明确的等待、执行、成功和失败状态；重复点击不能重复改写，多个操作不能并发破坏同一份本机配置。

### 产品与安全边界

- v0.19 首批白名单仅包含 Harness 更新、项目注入/升级和 Agent 接入同步；不开放任意命令、删除项目、卸载服务或修改 Git 历史。
- 项目路径必须是本机已存在的绝对目录；服务端重新验证参数，不能信任前台传值。
- 所有写操作先生成一次性确认单，确认后由独立 worker 执行；结果只保留脱敏摘要、退出码和时间，不保存密钥、环境变量或完整命令行。
- Harness 更新完成后由 worker 恢复唯一的 6425 服务；复用 task-133 的幂等安装与失败恢复能力。

### 实施步骤

- [x] 132. [测试基线] `tests/test_harness_observe.py` — 固定操作目录、参数校验、一次性确认、幂等复用、互斥执行、动作令牌与前台入口合同，并在旧实现上得到预期失败。
- [x] 133. [任务执行层] `scripts/harness-observe.py` — 增加操作记录、预检、确认、独立 worker、互斥锁、审计与固定动作映射；更新后安全恢复 6425。
- [x] 134. [HTTP 闭环] `tests/test_harness_observe.py` — 覆盖操作列表、预检、未授权拒绝、确认执行和状态查询；测试只调用受控假执行器，不改真实 Harness。
- [x] 135. [工作台交互] `web/observe-dashboard.html` — 首页增加 Harness 操作区、项目路径输入、影响说明、二次确认、运行进度与最近结果；不用原生 prompt/confirm。
- [x] 136. [使用说明] `docs/OBSERVE.md` — 说明三类操作的输入、影响、确认、恢复、审计和失败处理。
- [x] 137. [版本验收] `docs/VERSIONS.md` — 对照 task-130 更新真实完成状态与剩余边界，不提前关闭 task-131/132。
- [x] 138. [真实验收] 聚焦测试、全仓测试、生成与 diff 检查，再在 6246 完成预检、取消、刷新和状态读取；不执行真实更新/注入，不部署、不合并 main。

### 完成判定

- [x] 工作台可以为三类白名单动作生成用户可读确认单，并在确认前不产生项目或全局配置写入。
- [x] 同一确认单只能执行一次；执行中的第二个任务被明确拒绝，不发生并发写入。
- [x] 后端不接受任意 action、相对路径、缺失目录或无令牌请求；审计结果不包含密钥和完整环境信息。
- [x] 更新任务由独立 worker 执行并恢复唯一 6425；失败状态可读且保留安全重试入口。
- [x] 6246 真实用户路径与全仓 Gate 通过；不以按钮存在代替交互闭环证据。

### Step 132 — 2026-08-20
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 4 个聚焦合同在旧实现上得到预期 `4 errors`：`operation_catalog`、`prepare_operation`、`operation_mutex` 均不存在
- notes: 基线只在临时状态目录运行，没有触发真实 Harness 更新、项目注入、Agent 同步或服务重启。

### Step 133 — 2026-08-20
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: 操作目录、校验、确认、幂等、互斥、固定参数 worker 与错误脱敏共 `6 tests / 0 failures`
- notes: 更新动作固定为 `harness update` 后由独立 worker 执行 service restart；请求进程即使被 6425 重启终止，操作记录和 worker 仍保留。

### Step 134 — 2026-08-20
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: 隔离 HOME、状态目录和项目目录的 HTTP 集成测试 `1 test / 0 failures`；覆盖列表、401、预检、确认、worker、状态查询、产物与审计
- notes: 集成确认执行的是临时项目注入，并显式关闭 Observer 自动安装；没有写入真实 HOME、注册表或 LaunchAgent。

### Step 135 — 2026-08-20
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 操作区与既有工作台合同共 `8 tests / 0 failures`；包含三类入口、内嵌表单、影响确认、当前任务轮询与最近结果
- notes: 操作区位于待关注摘要和项目进度之间；移动端降为单列，长路径与确认说明可换行，不使用原生 prompt/confirm。

### Step 136 — 2026-08-20
- files: `docs/OBSERVE.md`, `plan.md`
- verify: 文档明确三类白名单动作、五步用户路径、一次性确认、单任务互斥、状态与审计目录、401 鉴权和更新时服务恢复边界；`git diff --check` 待最终 Gate 一并验证
- notes: 文档不把工作台描述为任意命令面板，也不把 Agent 配置文件存在等同于真实 Agent 已生效。

### Step 137 — 2026-08-20
- files: `docs/VERSIONS.md`, `plan.md`
- verify: v0.19 仅将 `task-130` 与既有 `task-133` 标为完成；`task-131` 外部 Skill 兼容和 `task-132` Harness 改进候选闭环保持未完成
- notes: 本轮完成的是操作中心，不等同于 v0.19 整体可发布。

### Step 138 — 2026-08-20
- files: `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `docs/OBSERVE.md`, `docs/VERSIONS.md`, `plan.md`
- verify: 全仓 `108 tests / 0 failures`；`./generate.sh --check`、CLI import/help、`git diff --check` 均 exit 0；6246 完成项目路径输入、预检确认单、取消、刷新与状态读取，console `0 warning / 0 error`；390px 视口 `scrollWidth = innerWidth = 390`
- notes: 浏览器只生成并取消确认单，没有点击确认执行；未运行真实 update、项目注入或 Agent 修复，未部署 6425、未合并 main、未发布版本。

## v0.19.0 · 2026-08-20 · 外部 Skill 可视化治理

### 用户目标

- 外部 Skill 在工作台中可发现、可理解、可追踪来源；用户能看见它属于哪个角色、可能改动什么、与 Harness 哪些边界冲突。
- “文件存在”“已安装”“已分配给角色”“已由 Agent 在真实任务中加载”必须是四种不同状态，工作台不得合并或误报。
- 第三方 Skill 接入前先由确定性代码完成静态诊断；不能依赖 Agent 阅读 Prompt 后自行判断是否安全。

### 产品与安全边界

- 本阶段只读取 Harness 内置 Skill、Codex 全局 Skill、通用 Agent Skill 与项目级 `.harness/skills`；不联网、不下载、不运行第三方脚本、不修改用户 Skill 目录。
- 外部 Skill 只能作为角色的方法附件，不能接管角色路由、Hook、全局 Loader、Brain 写入、权限或完成定义。
- 静态诊断输出 `compatible / review_required / blocked`，并列出可定位证据；静态通过不等于真实 Agent 已加载。
- 工作台首页只展示 Skill 健康摘要和需关注数量；完整清单、来源、范围、角色和冲突进入“设置 → 能力与 Skill”。

### 实施步骤

- [x] 139. [测试基线] `tests/test_harness_skills.py` — 固定内置/外部/项目 Skill 发现、四态语义、正常/需审查/阻断样例和不执行脚本合同，并在旧实现上记录预期失败。
- [x] 140. [诊断器] `scripts/harness-skill-manager.py` — 用标准库实现受限目录发现、Frontmatter/资源解析、来源与角色映射、冲突证据和兼容结论；只读且有数量/大小上限。
- [x] 141. [服务 API] `scripts/harness-observe.py`、`tests/test_harness_observe.py` — 提供只读 `/api/skills.json`，返回清单、状态摘要和诊断结果，不开放任意路径读取或安装端点。
- [x] 142. [工作台交互] `web/observe-dashboard.html`、`tests/test_harness_observe.py` — 设置页增加“记忆与同步 / 能力与 Skill”切换，展示筛选、来源、角色、兼容状态和冲突详情；首页只保留紧凑摘要。
- [x] 143. [治理说明] `docs/AGENT-SUPPORT.md`、`rules/skills/SOURCES.md` — 说明发现、安装、分配、验证生效的区别，以及外部 Skill 的审计、固定版本、更新和移除机制。
- [x] 144. [版本状态] `docs/VERSIONS.md` — 对照真实能力更新 `task-131`，不提前关闭 `task-132`。
- [x] 145. [真实验收] 运行聚焦与全量回归、生成与 diff 检查，并在 6246 验证设置切换、筛选、展开冲突、重新扫描和页面边界；不安装或执行任何外部 Skill。

### 完成判定

- [x] 工作台能列出本机受支持目录中的 Skill，并明确来源、作用域、角色、文件状态、是否已分配以及是否有真实加载证据。
- [x] 含 Hook/全局 Loader/角色接管/完成定义/危险命令的样例被定位并标为需审查或阻断；检查过程不执行样例脚本。
- [x] API 不接受用户路径参数，不泄露 Skill 正文、凭据或任意本机文件；页面只展示摘要和冲突证据。
- [x] 全仓测试、生成一致性、diff 检查与 6246 真实路径通过；未写用户 Skill 目录、未部署 6425、未合并 main、未发布版本。

### Step 139 — 2026-08-20
- files: `tests/test_harness_skills.py`, `plan.md`
- verify: 旧实现因缺少 `scripts/harness-skill-manager.py` 得到预期 `FileNotFoundError`，证明新增合同不是既有功能误通过
- notes: 样例覆盖 Harness 内置、本机外部、项目级、角色/Hook/完成定义冲突、危险命令、脚本资源和逃逸 symlink。

### Step 140 — 2026-08-20
- files: `scripts/harness-skill-manager.py`, `tests/test_harness_skills.py`, `plan.md`
- verify: `5 tests / 0 failures`；真实本机只读扫描得到 `45` 个 Skill、`30` 个可兼容、`15` 个需审查、`0` 个阻断、`2` 个已分配角色、`0` 个已验证加载
- notes: 扫描器限制目录、数量和文件大小，跳过逃逸 symlink；多行 Frontmatter 描述已通过回归测试。

### Step 141 — 2026-08-20
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: 隔离 Observer HTTP 测试通过；`GET /api/skills.json` 返回只读边界，携带任意 query/path 得到 `400`
- notes: API 只输出摘要、显示路径、资源文件名和诊断代码，不返回 `SKILL.md` 正文或任意绝对路径读取能力。

### Step 142 — 2026-08-20
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 页面聚焦合同与 JavaScript syntax 通过；6246 显示 45/2/15/0 摘要，可切换兼容筛选、展开冲突、重新扫描并在记忆与 Skill 设置间往返
- notes: 首页只新增一行 Skill 健康摘要；完整治理在设置页，默认先展示需关注项目，不把 45 个 Skill 堆到首页。

### Step 143 — 2026-08-20
- files: `docs/AGENT-SUPPORT.md`, `rules/skills/SOURCES.md`, `plan.md`
- verify: 文档固定已发现、已安装、已分配、已验证加载四态，以及固定来源、静态诊断、人工审计、真实会话验证边界
- notes: 首版不开放任意 GitHub URL 安装；未来安装必须进入受控操作中心，不由前台或 Prompt 直接执行。

### Step 144 — 2026-08-20
- files: `docs/VERSIONS.md`, `plan.md`
- verify: v0.19 `task-131` 标记完成，`task-132` 项目问题到 Harness 改进审批闭环仍保持未完成
- notes: Skill 治理完成不等于 v0.19 整体可发布。

### Step 145 — 2026-08-20
- files: `scripts/harness-skill-manager.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_skills.py`, `tests/test_harness_observe.py`, `docs/AGENT-SUPPORT.md`, `rules/skills/SOURCES.md`, `docs/VERSIONS.md`, `plan.md`
- verify: 全仓 `114 tests / 0 failures`；`./generate.sh --check`、dashboard JavaScript syntax、`git diff --check` 均 exit 0；6246 设置切换、筛选、冲突展开、刷新通过，页面日志 0 条，1280px 视口 `scrollWidth = innerWidth = 1280`
- notes: 未联网、未运行第三方脚本、未写用户 Skill 目录、未执行 Skill 安装、未部署 6425、未合并 main、未发布版本。

## v0.19.0 · 2026-08-20 · 角色协作真相与场景化办公室

### 用户目标

- 让用户看懂 QA 是否真正做了独立验收，不再把开发自验或 Reviewer 跑测试当成 QA 参与。
- 让 Reviewer 的审查对象、证据、发现和结论可追溯，而不只显示一句泛化摘要。
- 用一张可交互的公司场景替代五角色表格；hover 看近期动作，点击查看该角色的历史任务、交付物与结论。
- 让用户能将不存在、不可读或未注入 Harness 的项目移出工作台，同时绝不删除任何项目文件。

### 产品与安全边界

- 角色参与只来自结构化 `work.round_*` / `handoff.created` 事件；没有 QA 回合就显示“未独立验收”，不根据测试数量脑补。
- UI、高风险或已定义 QA 用例的开发交付，建议流转必须先到 QA；QA 有同需求的后续完成回合后，才建议到 Reviewer。
- “移出工作台”只原子改写 Harness registry；不访问、删除或修改目标项目目录及 `.harness-runtime/`。
- 不新增第三方前端依赖或图片服务；角色形象用可访问、可缩放的原生 HTML/CSS 场景实现。
- 本阶段只在当前 v0.19 分支与 6246 验收；不合并 main、不部署 6425、不发布。

### 实施步骤

- [x] 146. [测试基线] `tests/test_harness_observe.py` — 固定角色历史、QA 缺口、Reviewer 审查对象、registry 移除和新导航/办公室的失败合同。
- [x] 147. [角色投影] `scripts/harness-observe.py` — 输出角色时间线、审查范围和 QA 缺口，使用同需求的时序证据给出下一角色建议。
- [x] 148. [安全移除] `scripts/harness-observe.py` — 增加受 action token 保护的项目移除 API，原子更新 registry 并返回 `files_deleted=false` 证据。
- [x] 149. [导航重构] `web/observe-dashboard.html` — 将全局、有效项目、连接异常和项目内导航重新分层；为失联项目提供内嵌确认与真实反馈。
- [x] 150. [场景化办公室] `web/observe-dashboard.html` — 用五个角色工位、状态光和流转高亮替换表格，hover 预览，点击打开可追溯历史。
- [x] 151. [角色契约] `rules/roles/executor.md`、`rules/roles/qa.md`、`rules/roles/reviewer.md`、`rules/roles/orchestration.md` — 明确 UI/高风险交付的 Executor → QA → Reviewer 门禁，并区分自验、独立验收与审查。
- [x] 152. [版本与文档] `docs/VERSIONS.md`、`docs/OBSERVE.md` — 记录 `task-134` 真实完成状态、角色语义和项目移除边界。
- [x] 153. [视觉验收反馈] 用户在 6246 提供真实截图，确认角色形象同质化，角色名/状态/徽标发生重叠，底部流转装饰抢占空间；QA 判定不通过并退回 Executor。
- [x] 154. [参考与设计约束] 研究 Marvis Office 的公开界面，提取角色个性、状态动作和日志降级原则；不复制品牌素材，不引入外部资源。
- [x] 155. [办公室重构] `web/observe-dashboard.html` — 用五种独立轮廓、姿势和职业道具替换同脸方块人，分离场景层与文字层，并压缩顶部流转信息。
- [x] 156. [布局防线] `tests/test_harness_observe.py` — 增加角色结构、字号层级、禁止重叠样式和响应式边界合同，并复跑全仓回归。
- [x] 157. [方向确认] 用户确认采用 A「软糖精灵」：更 Q、更抽象，当前执行角色需要具有类似 GIF 的持续工作动作。
- [x] 158. [软糖角色系统] `web/observe-dashboard.html` — 将五种人形角色替换为统一世界观下的五种软糖轮廓、表情和职业道具。
- [x] 159. [状态动画] `web/observe-dashboard.html`、`tests/test_harness_observe.py` — 将 active / waiting / completed / missing 映射为工作、等待、庆祝和异常动作，只有真实 active 角色持续工作，并支持 reduced-motion。
- [x] 160. [真实验收] 用户确认极简软糖方向并继续进入项目主页评审；保留真实状态驱动、hover 和点击历史，不真实移除用户项目。

### 完成判定

- [x] 没有 QA 回合时，办公室明确显示“未独立验收”；UI/高风险交付不会跳过 QA 直接建议 Reviewer。
- [x] Reviewer 历史至少显示对应需求、审查对象/证据和结论；缺少对象时坦率显示未记录。
- [x] 办公室不再以五行表格呈现；五个工位支持 hover/focus 预览和点击历史，当前流转在场景中可见。
- [x] 失联项目可通过二次确认移出 registry，刷新后消失；测试证明目标路径未被删除或修改。
- [x] 全仓测试、生成一致性、diff 检查和 6246 真实路径通过；未部署 6425、未合并 main、未发布。

### 历史验收状态修正 — 2026-09-03

- 以上五项已分别由 Step 147–160 的自动化、真实 API、6246 交互与用户视觉确认完成，并随 v0.19.0 发布；本次只修正遗留复选框，不改变历史实现或发布事实。

### Step 146 — 2026-08-20
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 新合同在旧实现上得到 `2 errors + 2 failures`：缺角色参与/审查范围、缺 registry 移除、缺场景化办公室与前台删除闭环。

### Step 147 — 2026-08-20
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: 角色投影聚焦测试通过；6246 真实 API 返回当前 `Executor → QA`、QA `missing_independent_validation`、Reviewer 7 条历史和 22 条历史 QA 缺口。

### Step 148 — 2026-08-20
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: 直接函数测试证明 registry 记录移除但项目哨兵文件保留；HTTP 集成测试证明无 token 为 401、确认后刷新消失且 `files_deleted=false`。

### Step 149 — 2026-08-20
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 导航合同通过；全局仅保留工作台/设置，项目内为项目主页/版本与需求/交付物，失联项目独立分组并使用非原生二次确认。

### Step 150 — 2026-08-20
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: HTML parse、JavaScript syntax 和场景合同通过；五工位、CSS 角色形象、hover/focus 预览、流转高亮和点击历史已落地。

### Step 151 — 2026-08-20
- files: `rules/roles/executor.md`, `rules/roles/qa.md`, `rules/roles/reviewer.md`, `rules/roles/orchestration.md`, `plan.md`
- verify: 角色契约明确 UI/高风险门禁、QA 独立回合与 Reviewer 审查对象要求；`./generate.sh --check` passed。

### Step 152 — 2026-08-20
- files: `docs/VERSIONS.md`, `docs/OBSERVE.md`, `plan.md`
- verify: 版本仍将 `task-134` 保持为未完成；文档记录 QA/Reviewer 语义、导航和“只移除登记”边界。

## 历史阻塞 #2（原步骤 153）
发现：6246 服务已健康并返回新 API，但应用内浏览器的 URL 安全策略拒绝自动控制 localhost，无法在本轮获取 hover/点击视觉证据。
证据：
- 全仓回归 `118 tests / 0 failures`；新增回归确保 active QA 不会提前建议交接 Reviewer。
- 6246 `/healthz` 返回 `status=ok`、PID `67965`、`project_count=7`；真实工作区显示当前角色 `QA`、当前门禁 `Executor → QA`，而不是尚未发生的 `QA → Reviewer`。
- 应用内浏览器拒绝该 localhost 页面的自动控制；按安全契约不使用其他浏览器或间接手段绕过。
建议方案（请 QA/用户验收）：
A. 用户在已打开的 6246 页面刷新，hover 五个角色并点击 QA/Reviewer，再打开失联项目的“移出工作台”后点“取消”。
B. 若视觉或交互不通过，回 Executor 修正；通过后勾选步骤 153 并将 `task-134` 标记完成。

### QA 结论 — 2026-08-20

- 结果：不通过，已回 Executor。
- 用户证据：6246 截图中五个角色共用同一面孔和站姿；角色名、状态、徽标与人物/桌面发生覆盖；流转高亮以大面积底部弧线出现，信息层级失衡。
- 修正边界：重做角色办公室内部结构与样式，不改变角色数据模型、历史抽屉、项目导航、main、6425 或发布状态。

### Step 154 — 2026-08-20
- evidence: Marvis 公开界面与体验资料将 Agent 呈现为有动作的同事，空闲/工作状态直接映射到办公室活动，详细过程折叠为日志；本项目只吸收这些原则，不复制形象或素材。

### Step 155 — 2026-08-20
- files: `web/observe-dashboard.html`, `plan.md`
- verify: 五个角色分别使用 lead / creative / builder / detective / auditor 原型，具有不同发型、肤色、姿势和职业道具；文字进入独立 `role-card-meta`，人物与工位固定在 `role-visual`。
- notes: 删除人物胸前缩写徽标与大面积底部流转弧线；顶部流转去掉重复 DEV/QA 徽章，只保留角色名和方向。

### Step 156 — 2026-08-20
- files: `tests/test_harness_observe.py`, `web/observe-dashboard.html`, `plan.md`
- verify: 新结构在旧实现上预期失败；实现后办公室/导航/信息层级 `3 tests / 0 failures`，dashboard JavaScript syntax exit 0，全仓 `119 tests / 0 failures`。
- notes: 结构测试锁定视觉层与文字层分离、五种角色原型、无胸前徽标、无 station 底部 box-shadow 高亮和响应式文本换行。

### Step 157 — 2026-08-20
- decision: 用户从软糖精灵、像素小队、模块机器人、工作精灵四个方向中选择 A「软糖精灵」。
- boundary: 使用可由真实角色状态驱动的原生矢量/CSS 动画，不引入 GIF、外部图片、动画库或新的运行时依赖。

### Step 158 — 2026-08-20
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 旧人形结构已删除；PM / Designer / Executor / QA / Reviewer 分别映射 planner / creative / builder / inspector / reviewer 五种软糖形态，结构契约 `2 tests / 0 failures`。
- notes: 角色名、职责和状态继续放在独立信息层；软糖只承担角色识别与状态反馈，不重新堆叠文字。

### Step 159 — 2026-08-20
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 仅 `active` 角色循环动画，开发打字、测试巡检、Review 翻阅、设计绘制、PM 规划均由真实角色状态驱动；全仓 `119 tests / 0 failures`，JavaScript syntax exit 0，`generate.sh --check` 与 `git diff --check` passed。
- service: 仅重启 6246 设计服务；`/healthz` 返回 `status=ok`、PID `88383`、7 个项目，实际页面已包含 `role-jelly` / `jelly-active` / `renderRoleJelly`。
- pending: Step 160 需要在真实页面确认五种形象、动画节奏、窄屏边界与角色历史点击体验；main、6425 与发布状态均未改变。

### QA 视觉纠正 — 2026-08-21
- evidence: 用户提供设计稿与 6246 实现截图；当前实现增加了桌子、显示器、职业道具、渐变描边与三层状态卡，明显偏离设计稿的单色软糖、需求卡和单行角色名。
- classification: 🟡纠正；保留真实角色状态、点击历史和流转数据，只重做角色办公室的表现层。
- target: 五个角色按蓝 / 橙 / 绿 / 粉 / 紫固定识别；仅 active 角色显示“角色 · 工作中”并执行挤压、弹跳与搬卡动作，其他角色静止。
- implementation: 移除桌面、显示器、嘴、职业道具、渐变描边、光泽、状态灯和三层状态卡；角色历史继续通过 hover 与点击进入，不占用主画面。
- verify: 新视觉契约先在旧实现上失败，修正后聚焦 `2 tests / 0 failures`，全仓 `119 tests / 0 failures`，JavaScript syntax、`generate.sh --check` 与 `git diff --check` passed；6246 `/healthz` 为 `status=ok`，页面已加载五个指定色值与 `jelly-carry` 动画。
- pending: 应用内浏览器的本地 URL 安全策略阻止自动截图对照，Step 160 仍需用户在 6246 刷新后做最终视觉确认。

### Step 160 — 2026-08-21
- evidence: 用户认可极简软糖办公室并开始评审项目主页，视为本轮视觉方向通过；`task-134` 已在版本计划中完成。
- boundary: 本次确认只接受角色办公室的方向与交互入口，不代表 main、6425、v0.19 发布或其他页面完成。

## v0.19.0 · 2026-08-21 · 当前版本需求指挥台

### 用户目标

- 项目主页首先回答“当前版本正在做哪些需求”，而不是只显示一个无法解释的总进度和全局角色状态。
- 每条需求独立呈现实际执行路径；用户能看清当前由谁负责、正在做什么、QA 测试什么、有哪些证据、是否阻塞以及下一步是什么。
- 角色是查看需求执行事实的视角，不是与需求并列的另一套进度；没有角色事件、测试范围或证据时明确显示未记录。
- “版本与需求”改为“版本记录”，承担历史版本与 Git 关系阅读；当前版本的行动信息前置到项目主页。

### 产品与数据边界

- 版本需求清单以 `docs/VERSIONS.md` 为计划真相；需求执行事实只来自同 `requirement_id` 的结构化工作回合、验证、阻塞与交接事件。
- 不把版本总完成比例等同于当前角色阶段；`3/5` 只表示三个版本需求已确认完成，不能推出剩余需求都处于测试。
- 不为每条需求强制补齐 PM、设计、开发、QA、Reviewer；执行路径只显示真实参与或被明确交接的角色。
- QA 范围优先读取同需求 QA 回合的目标、摘要和验证引用；缺少结构化信息时显示“测试范围未记录”或“尚未进入独立测试”。
- 本阶段不增加需求删除、后移或改写版本文件的操作；只完成真实数据投影、阅读路径和需求选择联动。
- 仅在 `feat/v0.19-service-reliability` 与 6246 验收；不修改 main、6425 或发布状态。

### 实施步骤

- [x] 161. [失败契约] `tests/test_harness_observe.py` — 固定当前版本逐需求状态、真实角色路径、QA 范围/证据缺失语义以及首页/版本导航结构。
- [x] 162. [需求投影] `scripts/harness-observe.py` — 将版本计划与同需求工作回合、验证、阻塞、交接合成为 `current_version`，不混入无关需求或全局角色状态。
- [x] 163. [主页重构] `web/observe-dashboard.html` — 首页改为逐需求指挥台，支持选择需求并联动角色办公室；“版本与需求”改为“版本记录”。
- [x] 164. [真实验收] 聚焦测试、全仓回归、生成一致性、JavaScript/diff 检查和 6246 真实 API；完成桌面与窄屏真实视觉路径确认。

### 完成判定

- [x] 当前版本总览分别显示需求总数、已完成、进行中和待开始，且计数可追溯到需求卡。
- [x] 每条需求卡显示标题、有效状态、实际角色路径、当前工作、测试范围/证据、阻塞和下一步；未知内容不脑补。
- [x] 选择某条需求后，角色办公室只突出该需求的实际角色状态与历史；未参与角色保持静默，不伪造交接。
- [x] 项目内导航使用“项目主页 / 版本记录 / 交付物”，历史版本仍按新到旧展示。
- [x] 全仓验证与 6246 真实 API 通过；未部署 6425、未合并 main、未发布。

### Step 161 — 2026-08-21
- files: `tests/test_harness_observe.py`, `plan.md`
- verify: 新合同在旧实现上得到 `1 error + 1 failure`：缺 `current_version` 逐需求投影，页面缺需求指挥台与“版本记录”导航；实现后聚焦 `4 tests / 0 failures`。

### Step 162 — 2026-08-21
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: 人工快照证明 `Executor → QA` 只属于同一需求，其他需求的 Reviewer 不会串入；真实项目暴露并修复结构化 evidence ref 的兼容问题。
- evidence boundary: 只有 QA 回合显式引用的验证才进入该需求的测试证据；旧 Plan 步骤产生的同号验证不会因 `task_id` 碰撞被误认。

### Step 163 — 2026-08-21
- files: `web/observe-dashboard.html`, `docs/VERSIONS.md`, `docs/OBSERVE.md`, `plan.md`
- verify: 首页加载“当前版本需求”、逐需求角色路径/测试范围/证据/下一步和选择联动；项目导航改为“项目主页 / 版本记录 / 交付物”。
- runtime: 6246 真实 API 返回 v0.19 `4 completed / 1 in_progress / 1 planned / 0 blocked`；`task-134` QA 已完成，`task-135` 为 `Executor completed → QA waiting`，未测试需求明确显示“尚未进入独立测试”。

### Step 164 — 2026-08-22（真实视觉验收完成）
- defect: 点击 `task-134` 的 QA 历史时发现同编号旧 Plan Step 抢占需求标题；新增失败契约后修正为优先读取当前版本需求标题，避免角色历史串线。
- verify: 全仓 `122 tests / 0 failures`；`generate.sh --check`、Python/JavaScript syntax 均 exit 0；6246 桌面端完成需求切换、角色办公室联动和 QA 历史抽屉路径，console `0 warning / 0 error`。
- responsive: 390×844 下 6 张需求卡均为单列，长标题 `white-space: normal`、`overflow-wrap: anywhere`，页面 `scrollWidth = innerWidth = 390`；恢复默认视口后结束验收。
- boundary: 未修改 main、6425 或发布状态；v0.19 仍有 `task-132` 未实现。

## v0.19.0 · 2026-08-22 · 项目问题回流 Harness

### 用户目标

- 用户能把任一项目里的真实问题明确提交为 Harness 改进信号，而不是只能写入 Brain 记忆或依赖 Agent 猜测。
- 工作台能按问题类型、来源项目、重复频次和相似候选聚合，并让用户决定它最终应进入 Rule、Skill、Checker 或 Profile。
- 单个项目的一次性问题默认保留在项目观察层；只有跨项目重复、同类高频或用户明确送审后才进入中央 Harness 审批。
- 审批不会直接改写中央规则；先生成可审计提案，落地后登记实际产物，再以同类问题频次是否下降完成效果复验。

### 产品与安全边界

- 复用现有项目记忆作为可选择的证据来源，不把所有项目记忆自动判定为 Harness 缺陷。
- Harness 改进候选独立于 Brain 全局偏好/Profile 审批箱，避免“个人偏好”和“工具规则缺陷”混为一谈。
- 所有写操作使用 localhost action token；候选、合并、审批、落地和复验均保留来源与状态，不删除原项目记录。
- 批准只生成本地提案，不自动修改 `rules/`、Skill、Checker 或 Profile；实际产物必须由后续受控开发落地并登记。
- 仍只在 `feat/v0.19-service-reliability` 与 6246 验收；不修改 main、6425，不发布，不执行远端同步。

### 实施步骤

- [x] 165. [失败契约] `tests/test_harness_agents.py`、`tests/test_harness_observe.py` — 固定项目问题候选、跨项目相似项/频次、人工送审、目标类型、提案、落地与复验状态，以及鉴权 HTTP/UI 入口。
- [x] 166. [候选模型] `scripts/harness-brain-boundary.py` — 在独立本地目录维护 Harness 改进生命周期，复用项目记忆证据但不进入 Brain 候选审批。
- [x] 167. [服务 API] `scripts/harness-observe.py` — 提供只读清单与受 action token 保护的创建、合并、送审、批准/拒绝、登记落地和效果复验接口。
- [x] 168. [工作台交互] `web/observe-dashboard.html` — 设置新增“Harness 改进”入口；项目记忆可提交问题，改进页显示来源、频次、相似项、目标、审批、落地和复验动作。
- [x] 169. [说明与版本状态] `docs/OBSERVE.md`、`docs/VERSIONS.md` — 写清 Brain 记忆与 Harness 改进的区别、用户路径和不自动改规则边界。
- [x] 170. [真实验收] 聚焦与全仓回归、生成/语法/diff 检查，并在 6246 走完“项目问题 → 改进候选 → 审批预览”的安全路径；不批准真实中央规则改动。
- [x] 171. [Review 修正] `scripts/harness-observe.py`、`tests/test_harness_observe.py` — 已完成 QA 回合没有专门 verification 事件时，以 QA 回写摘要作为可见的兜底证据；没有 QA 的旧需求继续如实显示无证据。
- [x] 172. [证据补齐] 对 task-130、task-131、task-133 分别执行独立 QA 并回写范围与结论；`web/observe-dashboard.html` 不再给已完成需求显示陈旧的“建议下一步”流转。

### 完成判定

- [x] 项目记忆卡可明确提交为 Harness 问题并选择 Rule / Skill / Checker / Profile；原项目记忆仍保留。
- [x] 改进页能解释候选来自哪些项目、出现多少次、有哪些相似项，以及为何尚未进入审批。
- [x] 单项目一次信号默认不自动送审；跨项目合并或用户明确确认后才进入审批箱。
- [x] 批准生成可审计提案但不直接修改中央 Harness；可登记实际产物并记录 improved / unchanged / regressed 复验结果。
- [x] HTTP 写操作均鉴权，错误路径可达；全仓验证与 6246 真实路径通过。

### Step 165 — 2026-08-22
- files: `tests/test_harness_agents.py`, `tests/test_harness_observe.py`, `plan.md`
- verify: 旧实现得到候选模型 `2 errors` 与工作台合同 `1 failure`，证明项目问题回流、独立审批域和 UI/API 均尚不存在。

### Step 166 — 2026-08-22
- files: `scripts/harness-brain-boundary.py`, `tests/test_harness_agents.py`
- verify: `2 tests / 0 failures`；单项目信号保持 `observed`，跨项目合并后进入 `pending_approval`，批准只生成本地提案，登记产物后可记录效果复验。

### Step 167 — 2026-08-22
- files: `scripts/harness-observe.py`, `tests/test_harness_observe.py`
- verify: localhost 集成测试证明未授权创建返回 `401`；授权后可创建、明确送审、批准并从只读清单读取提案路径。

### Step 168 — 2026-08-22
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`
- verify: 设置新增独立“Harness 改进”页；项目记忆的提交表单展示 Rule / Skill / Checker / Profile，候选页按状态提供合并、送审、审批、登记已落地与效果复验动作。

### Step 169 — 2026-08-22
- files: `docs/OBSERVE.md`, `docs/VERSIONS.md`, `plan.md`
- verify: 文档明确 Brain 项目事实与 Harness 改进的边界、频次门槛、提案目录及“不自动改中央 Harness”。

### Step 170 — 2026-08-22
- verify: 全仓 `128 tests / 0 failures`；Python/JavaScript syntax、`generate.sh --check`、`git diff --check` 均 exit 0。
- release hardening: Harness 改进的 8 个状态变更入口使用同一写锁；并发回归证明两个 Agent 同时提交同一问题只实际落盘一次。Brain/Harness 操作接口统一限制 `16 KiB` 请求体，超限集成测试返回 `413 body-too-large`。
- interaction: 6246 完成“设置 → Harness 改进空态 → 记忆与同步 → 展开项目记忆 → 打开提交表单 → 检查四类目标 → 取消 → 返回改进页”；真实候选仍为 0，未污染用户数据，console `0 warning / 0 error`。
- responsive: 390×844 下页面 `scrollWidth = innerWidth = 390`，三个设置标签与四项摘要无横向溢出；验收后已恢复默认视口。
- service note: 旧 6246 进程收到正常终止后由现有守护链自动以新 PID 拉起并加载当前代码；未继续强杀，也未触碰 6425。

### Step 171 — 2026-08-22
- failure evidence: 真实 6246 页面中 task-132 已有 QA 与 Review 回合，但“验证证据”仍显示空；新增回归在旧逻辑稳定复现 `evidence_count 0 != 1`。
- verify: 修复后聚焦 `2 tests / 0 failures`，全仓 `128 tests / 0 failures`；现有显式 verification 证据计数不变。
- interaction: 6246 重新加载当前分支后，task-132 显示 `1 条 · QA 回写：126项测试、桌面与390px页面路径通过…`；task-134、task-135 同样展示各自真实 QA 摘要，未参与 QA 的旧需求仍显示“尚无验证证据”。

### Step 172 — 2026-08-22
- QA: task-130 `7 tests / 0 failures`（白名单、路径安全、幂等确认、互斥、固定参数、脱敏、鉴权 HTTP）；task-131 `5 tests / 0 failures`（发现、冲突、危险指令、脚本隔离、元数据）；task-133 `4 tests / 0 failures`（断连、保活、幂等复用、失败恢复）。
- verify: 全仓 `129 tests / 0 failures`；JavaScript syntax、`generate.sh --check`、`git diff --check` 均 exit 0。
- interaction: 6246 当前版本保持 `6/6`；六条需求均显示实际测试角色、测试范围与 QA 回写证据；已完成 task-130 显示“当前负责人：未分配”“当前没有角色流转”，历史开发→测试路径仍保留。

### Step 83 — 2026-08-13
- files: `scripts/harness-observe-hook.py`, `scripts/harness-observe.py`, `tests/test_harness_agents.py`, `tests/test_harness_observe.py`
- verify: 对应联合记录 `Step 82/83/90`；真实 Loader/Hook 部署后 4/4 生命周期配置、离线 outbox 重放与 68 tests / 0 failures 均有记录。

### Step 94 — 2026-08-19
- files: `scripts/harness-brain-boundary.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`
- verify: v0.18 发布 Gate 的 98 tests / 0 failures 与真实 6425 页面验证覆盖 Brain 分层健康状态。

### Step 95 — 2026-08-19
- files: `scripts/harness-observe-hook.py`, `scripts/harness-brain-boundary.py`, `tests/test_harness_agents.py`
- verify: 结构化事件统一入口、脱敏去重和 SessionEnd 非主链合同纳入 v0.18 全量 98 tests / 0 failures。

### Step 96 — 2026-08-19
- files: `scripts/harness-brain-boundary.py`, `tests/test_harness_agents.py`, `docs/BRAIN-INTEGRATION.md`
- verify: 项目事实自动写入、噪音拒绝、纠正与撤销路径纳入 v0.18 全量 98 tests / 0 failures。

### Step 97 — 2026-08-19
- files: `scripts/harness-brain-boundary.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`
- verify: 全局/Profile 候选的编辑、换层、合并、忽略、批准、拒绝与重试在 6246 真实路径和 98 tests / 0 failures 中验收。

### Step 98 — 2026-08-19
- files: `scripts/harness-verify.py`, `tests/test_harness_verify.py`, `docs/VERIFY-CONTRACT.md`
- verify: fast/subsystem/release 三档与同指纹 Gate 复用合同通过，v0.18 全量为 98 tests / 0 failures。

### Step 102 — 2026-08-19
- files: `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_observe.py`
- verify: 工作台导航、语义版本倒序和工作区—分支—版本—标签图通过真实 6246 路径及 v0.18 Release Gate。

### Step 103 — 2026-08-19
- files: `scripts/harness-brain-boundary.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`
- verify: 同步清单展示真实仓库、分支、写入来源和目标；真实页面只完成预览与取消，未越过最终确认边界。

### Step 104 — 2026-08-19
- files: `scripts/harness-brain-boundary.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`
- verify: 项目待同步与全局/Profile 待审批已分离，确定性服务主链合同纳入 98 tests / 0 failures。

### Step 113 — 2026-08-18
- files: `docs/VERSIONS.md`, `scripts/harness-observe.py`, `tests/test_harness_observe.py`
- verify: 对应联合记录 `Step 112–113`；临时双 worktree 的 3 tests / 0 failures 证明 main 集成目标与两条工作分支归属正确。

### Step 115 — 2026-08-18
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`
- verify: 对应联合记录 `Step 114–115`；全仓 93 tests / 0 failures，6246 展示同仓库工作区且 console 0 warning / 0 error。

### Step 116 — 2026-08-18
- files: `tests/test_harness_agents.py`, `tests/test_harness_observe.py`, `tests/test_harness_verify.py`
- verify: 契约基线稳定暴露同步预览与页面层级缺口，随后由 Step 117–120 的聚焦合同闭环。

### Step 117 — 2026-08-18
- files: `scripts/harness-brain-boundary.py`, `tests/test_harness_agents.py`
- verify: 同步预览返回真实仓库/上游、项目分组、涉及文件、领先提交和排除项；聚焦合同 2 tests / 0 failures。

### Step 118 — 2026-08-18
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`
- verify: 页面按待同步、全局审批、项目记忆、连接设置排序，项目记忆与高级详情刷新后默认收起。

### Step 119 — 2026-08-18
- files: `docs/BRAIN-INTEGRATION.md`, `tests/test_harness_agents.py`
- verify: 用户文档与后端合同对齐收集范围、审批、同步目标、Git push 边界、排除项和仅本地模式。

### Step 120 — 2026-08-18
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `plan.md`
- verify: 全仓 93 tests / 0 failures；6246 完成同步清单、记录/文件/提交展开、取消与刷新，console 0 error，未执行最终同步。

### Step 153 — 2026-08-20
- files: `web/observe-dashboard.html`, `plan.md`
- verify: 用户提供的 6246 截图明确记录角色同质化、文字重叠和装饰抢占空间，QA 据此退回 Executor 并进入 Step 154–160 修正链。

## v0.19.0 · 2026-08-22 · 正式发布

### 发布步骤

- [x] 173. [发布事实] `VERSION`、`CHANGELOG.md`、`CHANGELOG.zh-CN.md`、`docs/VERSIONS.md` — 版本、日期、兼容性、迁移说明和标签统一为 v0.19.0。
- [x] 174. [Release Gate] 全量测试、生成规则、Python/JavaScript/Shell/JSON 语法、安装 smoke、Harness audit、敏感信息和 diff 检查全部通过。
- [x] 175. [提交与合并] 将 `feat/v0.19-service-reliability` 的完整范围提交，fast-forward 合并到本地 main，并确认工作树干净。
- [x] 176. [本机部署] 更新 `~/.mick-harness`，同步 Agent loader，重启并验证唯一的 6425 服务；不覆盖用户未受管配置。
- [x] 177. [远端发布] 推送 main 与 annotated `v0.19.0` 标签，核对 GitHub 远端分支、标签和本地安装版本一致。

### Step 173 — 2026-08-22
- files: `VERSION`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `docs/VERSIONS.md`, `plan.md`
- verify: `VERSION=0.19.0`；中英文 Changelog 均包含 `0.19.0 / 2026-08-22`；版本记录为 `released / main / v0.19.0`，并明确 `harness update` 迁移方式。

### Step 174 — 2026-08-22
- files: `generate.sh`, `setup.sh`, `scripts/*.sh`, `scripts/*.py`, `web/observe-dashboard.html`, `tests/`, `plan.md`
- verify: 首轮全仓 `130 tests / 0 failures`；真实 6425 发现 1345 条项目记忆令首页阻塞后，将健康快照改为线性统计、项目活动限制为最近 100 条，并补 2 项回归测试；最终全仓 `132 tests / 0 failures`，真实数据计时由约 25 秒降至 health `0.353s`、list100 `0.236s`；`generate.sh --check`、Shell/Python/JavaScript/JSON 语法、临时项目 `setup.sh --non-interactive`、版本一致性、敏感信息扫描和 `git diff --check` 全部 exit 0；Harness Audit `8 PASS / 0 WARN / 0 FAIL`。

### Step 175 — 2026-08-22
- files: Git branch `feat/v0.19-service-reliability`, Git branch `main`, `plan.md`
- verify: 发布候选提交 `7ddfded` 创建成功；远端 `origin/main` 与本地发布基线均为 `4f6035c`；`git merge --ff-only feat/v0.19-service-reliability` 成功，main 无合并提交且仅领先远端发布提交。

### Step 176 — 2026-08-22
- files: installed `~/.mick-harness`, `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, `~/Library/LaunchAgents/com.mick.harness.observer.plist`, `scripts/harness-brain-boundary.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`, `tests/test_harness_agents.py`, `plan.md`
- verify: 安装版本为 `0.19.0`；Claude/Codex 受管 Loader 均标记 `Harness-Version: 0.19.0`；用户未跟踪的 `verify.sh` 与 `verify.d/` 保留；只有 PID `58533` 监听 `127.0.0.1:6425`，health 为 `status=ok / 8 projects / 7 valid / last_scan_error=null`；真实浏览器完成工作台加载并显示 7/8 项目、Harness 操作、项目进度、系统状态，console `0 error / 0 warning`。

### Step 177 — 2026-08-22
- files: GitHub branch `main`, annotated Git tag `v0.19.0`, installed `~/.mick-harness`, `plan.md`
- verify: GitHub 已接受发布 main 基线 `4f6035c..26bb2dc`；最终发布记录与 annotated `v0.19.0` 使用原子推送，发布后以 `git ls-remote` 核对 main、tag object 与 tag peeled commit，并再次运行本机 `harness update` 对齐最终提交。

### 发布停止条件

- 任一 Release Gate 失败，或发现无法解释的文件、私有 Brain 数据、密钥、版本不一致时，停止在打标签之前。
- 合并后本机部署失败时不推送标签；远端推送失败时保留本地提交和标签并明确报告真实状态。

## v0.20.0 · 2026-08-22 · 需求级角色门禁

### 用户目标

- 每条需求拥有独立、可解释的执行链，不再让一次 Plan 或一条自由文本交接把整个版本直接推进到测试或 Reviewer。
- 产品开发前由 Reviewer 做产品逻辑审查：模拟用户路径、状态变化和边界情况；有阻塞问题时退回 PM，批准后才允许进入开发。
- 开发完成后必须有独立 QA 证据才能进入发布准备；高风险交付可在 QA 后再次触发 Reviewer 的发布审查。
- 工作台区分“Agent 声称做了什么”和“门禁认可的有效阶段”，非法跳转保留审计记录但不推进需求状态。

### 产品与流程边界

- 主路径为 `PM → Reviewer(product_review) → Executor → QA → Release`；复杂设计或技术方案可在产品审查后插入 Planner / Designer。
- Reviewer 是一个角色、两种明确模式：开发前 `product_review` 必选，QA 后 `release_review` 仅在高风险或用户要求时启用；两者不能靠摘要文本猜测。
- 纯技术修复在不改变产品行为且有明确复现证据时，可记录受控例外 `Executor → QA → Release`；例外必须结构化声明并保留原因。
- 版本允许多条需求处于不同阶段；版本总进度不代表某个统一角色阶段，角色办公室按选中需求展示有效链路。
- 旧事件继续可读；未携带 v0.20 门禁字段的历史事件不反向伪造产品审查结论。
- Skill 只提供 Reviewer 的产品逻辑审查方法，不接管 Harness 权限、调度、完成定义，也不把审查附件混入面向人类的 PRD。

### 实施步骤

- [x] 178. [失败契约] 固定结构化审查模式、门禁结果、非法跳转、逐需求状态与工作台解释性 UI；保存 132 项发布基线。
- [x] 179. [产品逻辑 Skill] 新增 `product-logic-review`，提供按风险缩放的用户路径模拟、边界检查、发现分级和批准/退回合同。
- [x] 180. [事件契约] 扩展工作回合的结构化 `review_mode`、`gate_result` 与受控例外字段，保持旧事件兼容并拒绝非法组合。
- [x] 181. [需求状态机] 用确定性投影计算每条需求的有效阶段、允许下一角色、门禁原因和被拒绝的跳转；自由文本只作展示，不推进状态。
- [x] 182. [角色合同] 收紧 PM、Reviewer、Executor、QA 与编排规则，使角色交接、交付物和回退条件与状态机一致。
- [x] 183. [工作台] 在当前版本需求卡和角色办公室展示有效流程、当前门禁、阻塞原因及非法跳转审计，不用版本级角色覆盖需求级事实。
- [x] 184. [验证] 完成聚焦测试、全仓回归、Skill 校验、生成一致性、语法/diff 检查与 6246 真实桌面/窄屏路径。
- [x] 185. [Review] 对状态机兼容性、门禁绕过、UI 可用性和发布范围做独立复核，确认是否具备合并条件。
- [x] 186. [失败契约] 固定“每条需求自带任务小队、选中需求内联展开办公室、主流程与可选 Designer 分离”的页面合同。
- [x] 187. [任务办公室] 将项目级角色办公室下沉到当前版本的每条需求卡，按需求状态驱动角色动作、交接、历史与详情。
- [x] 188. [交互验收] 完成全仓回归，并在 6246 验证多需求切换、角色详情、刷新恢复和窄屏边界。

### 完成判定

- [x] Reviewer 的产品逻辑审查在开发前运行，输出结构化批准或退回；发布审查与产品审查在数据和页面上可区分。
- [x] PM → QA、PM → release Reviewer、未交付的 Executor → QA 等跳转不会推进有效阶段，且用户能看到原因和原事件。
- [x] 同一版本的不同需求可分别停在 PM、产品审查、开发、QA、发布准备，并拥有独立角色历史。
- [x] QA 只验证已通过产品门禁且有开发交付的需求；测试范围和证据能回溯到同一 `requirement_id`。
- [x] 旧项目和旧事件仍可展示，不因缺少新字段崩溃或被错误判为已通过门禁。
- [x] 全仓回归、规则生成、Skill 校验和 6246 真实路径均提供本次证据；不部署 6425、不合并 main、不发布。

### Step 178 — 2026-08-22
- baseline: `python3 -B -m unittest` → 132 tests / 0 failures / exit 0；`./generate.sh --check` → 生成物一致 / exit 0。
- branch: `feat/v0.20-requirement-gates` 从已发布的 main 建立；本阶段不修改 main。

### Step 179 — 2026-08-23
- artifact: `rules/skills/product-logic-review/SKILL.md` 与独立审查产物 `docs/reviews/v0.20-requirement-gates-product-review.md`。
- verify: Skill Creator `quick_validate.py` 返回 `Skill is valid!`；Reviewer 行为合同覆盖 `approved`、`changes_requested` 和私有思维过程边界。

### Step 180 — 2026-08-23
- files: `docs/runtime-event-v0.schema.json`、`scripts/harness-observe.py`、`tests/test_harness_observe.py`。
- verify: 服务拒绝角色与 `review_mode` / `gate_result` 的非法组合；旧 `0.2.0` envelope 与历史投影继续兼容。

### Step 181 — 2026-08-23
- projection: 同一版本六条需求分别按 PM → product Reviewer → Executor → QA 回写；API 逐条显示独立 stage、角色路径、证据和零 rejected transition。
- boundary: 纯技术例外仍需原因、开发产物、自检和 QA；范围变化会使旧产品审查失效。

### Step 182 — 2026-08-23
- files: `rules/roles/{orchestration,pm,reviewer,executor,qa}.md`、`rules/core.md`、`dist/AGENTS.md`。
- verify: 10 项角色合同通过；生成 Loader 与源规则一致；Reviewer 的 `product_review` / `release_review` 不再混用。

### Step 183 — 2026-08-23
- interaction: 6246 真实页面依次显示 PM 等待、Reviewer → Executor 需求门禁、Executor → QA 质量门禁和最终 6/6；完成后负责人为“未分配”，角色路径保留 PM → Review → 开发 → 测试。
- responsive: 390×844 下 `scrollWidth = innerWidth = 390`，需求卡单列且控制台 `0 error / 0 warning`；视口已恢复。

### Step 184 — 2026-08-23
- verify: 最终 `python3 -B -m unittest` → 140 tests / 0 failures / exit 0；JavaScript syntax、JSON、`generate.sh --check`、Skill 校验与 `git diff --check` 均 exit 0。
- service: 6246 `health.status=ok`，8 个登记项目 / 7 个有效项目；六条 v0.20 需求均有独立 QA evidence ref。

### Step 185 — 2026-08-23
- review finding: 初版允许 `docs/VERSIONS.md` 完成勾选覆盖门禁；新增失败合同并修正为只有 `release_ready + checkbox` 才确认完成，提前勾选显示 `plan_conflict` 且不推进。
- result: 无 blocking finding；分支具备合并候选条件，但本轮未提交、未合并 main、未部署 6425、未发布或打 Tag。

### Step 186 — 2026-08-23
- scope change: 用户要求工作台使用最新角色流程，并让每个小 task 与角色办公室直接结合；重新打开 `task-182` 的页面范围，不改变后端门禁语义。
- interaction contract: 默认卡片显示任务小队；选中后在同一卡片内展开该需求的办公室与交接，禁止在页面下方保留可能指向另一需求的全局办公室。

### Step 187 — 2026-08-23
- files: `web/observe-dashboard.html`、`tests/test_harness_observe.py`、`docs/VERSIONS.md`。
- result: 每条需求卡默认显示 PM → Review → 开发 → 测试 → 待发布任务小队；Designer 仅在真实参与时插入；选中需求在卡片内展开五角色办公室，角色抽屉只读取同一 requirement 的历史、决策和交付物。
- regression: 真实点击发现开发抽屉混入 task-111 / task-35 历史，已收紧 `scope_requirement_id` 与产物路径过滤并复验不再混入。

### Step 188 — 2026-08-23
- verify: `python3 -B -m unittest` → 141 tests / 0 failures / exit 0；HTML、JavaScript、生成一致性和 diff 检查均通过。
- interaction: 6246 依次切换 task-182 / task-183，URL、唯一展开办公室和角色抽屉同步；task-182 最终有效路径为 PM → Reviewer → Executor → QA，2 条 QA 证据、0 rejected transition。
- responsive: 390×844 下 `scrollWidth = innerWidth = 390`，任务办公室内部横向浏览角色但不撑破页面；桌面视口已恢复，控制台 0 error / 0 warning。
- service probe: 受限终端的 localhost 检查曾产生假失败；真实健康源确认 PID 5242、6246 status=ok，未重启已有设计服务。

## v0.20.0 · 2026-08-24 · 正式发布

### 发布步骤

- [x] 189. [发布事实] `VERSION`、中英文 Changelog、`docs/VERSIONS.md` 与计划统一为 v0.20.0，并写明兼容性和迁移方式。
- [x] 190. [Release Gate] 重跑全仓测试、规则生成、脚本/JSON/Skill 校验、安装冒烟、敏感信息与 diff 检查。
- [x] 191. [提交与合并] 提交 `feat/v0.20-requirement-gates`，fast-forward 合并本地 main，并在合并后的真实代码上复验。
- [x] 192. [本机部署] 更新 `~/.mick-harness`、Agent Loader 和唯一 6425 服务，并用真实浏览器验收需求级任务办公室。
- [x] 193. [远端发布] 原子推送 main 与 annotated `v0.20.0`，核对远端分支、标签和本机安装提交一致。

### 发布停止条件

- 任一 Release Gate 失败，或发现无法解释的文件、私有 Brain 数据、密钥、版本不一致时，停止在打标签之前。
- 合并后本机部署失败时不推送标签；远端推送失败时保留本地提交并明确报告真实状态。

### Step 189 — 2026-08-24
- files: `VERSION`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `docs/VERSIONS.md`, `plan.md`
- verify: `VERSION=0.20.0`；中英文 Changelog 均包含 `0.20.0 / 2026-08-24`，兼容性、`harness update` 迁移方式和验证事实一致；版本记录为 `released / main / v0.20.0`。

### Step 190 — 2026-08-24
- files: `generate.sh`, `setup.sh`, `scripts/`, `rules/skills/product-logic-review/`, `tests/`, `web/observe-dashboard.html`, `plan.md`
- verify: `python3 -B -m unittest` → 141 tests / 0 failures / exit 0；`generate.sh` 与 `--check`、Python/JavaScript/Shell/JSON 语法、Skill Creator 校验、`git diff --check` 全部 exit 0；临时项目非交互 setup smoke 通过并已清理。
- notes: 敏感信息扫描仅命中 `tests/test_harness_agents.py:301` 的脱敏测试假密钥，未发现其他匹配；首轮安装断言误把生成标题限定为 Loader 文案，读取真实软链接和生成文件后改为项目实际合同并复验通过，未修改安装实现。

### Step 191 — 2026-08-24
- files: Git branch `feat/v0.20-requirement-gates`, Git branch `main`, `plan.md`
- verify: 发布候选提交 `17e0217` 创建成功；合并前本地 main 与 `origin/main` 均为 `64a64f1`；`git merge --ff-only feat/v0.20-requirement-gates` 成功，main 指向同一提交；合并后再次运行 141 tests / 0 failures、`generate.sh --check` 和 `git diff --check`，全部 exit 0。

### Step 192 — 2026-08-24
- files: installed `~/.mick-harness`, `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, `~/Library/LaunchAgents/com.mick.harness.observer.plist`, `plan.md`
- verify: 安装版与本地 main 均为 `7058059 / VERSION 0.20.0`；Claude/Codex 受管 Loader 均标记 `Harness-Version: 0.20.0`；用户未跟踪的 `verify.sh` 与 `verify.d/` 保留；6425 从 PID `58533` 切换为 `15239`，health 为 `status=ok / 8 projects / 7 valid / last_scan_error=null`。
- interaction: 真实 6425 显示 v0.20.0 为 6/6；切换到 task-182 后仅展开一个任务办公室，开发详情只读取 task-182，不含 task-111/task-35；390×844 下 `scrollWidth=innerWidth=390`，角色区内部可横向浏览，桌面视口已恢复，控制台 0 error / 0 warning。
- remaining risk: `harness update` 对使用 legacy all-rules 模式的项目提示 CLAUDE/Cursor 等兼容生成源缺失，但未删除或覆盖项目文件；全局 Claude/Codex Loader 与默认 AGENTS 入口已更新。本次不把既有兼容入口警告误报为 v0.20 门禁阻塞，后续版本应让 update 按登记项目模式生成相应兼容文件。

### Step 193 — 2026-08-24
- files: GitHub branch `main`, annotated Git tag `v0.20.0`, installed `~/.mick-harness`, `plan.md`
- verify: GitHub 已接受 v0.20 发布基线 `64a64f1..0a670f3`；最终发布记录与 annotated `v0.20.0` 使用原子推送，发布后以 `git ls-remote` 核对 main、tag object 与 tag peeled commit，并再次运行本机 `harness update` 对齐最终提交。

## v0.20.1 · 2026-08-24 · 项目首页刷新恢复

### 用户目标

- 从 URL 打开或点击某条当前版本需求后，刷新仍停留在同一需求、同一任务办公室和同一角色上下文。
- 首页不得把最新 Plan 步骤误当成版本需求；没有有效需求参数时，只在当前版本需求内选择合理默认项。

### 实施步骤

- [x] 194. [修复] 让项目首页用当前版本需求集合校验和恢复 `task` 参数，并为无选择状态建立需求内默认规则。
- [x] 195. [验证与部署] 增加自动回归，运行全仓门禁，部署 6425，并在真实浏览器验证选择、刷新和角色详情范围。
- [x] 196. [发布] 更新补丁版本事实，合并 main，发布 annotated `v0.20.1`，并对齐远端与本机安装。

### 停止条件

- 刷新后 URL、展开办公室或角色抽屉任一仍指向不同需求时停止发布。
- v0.20.0 标签不得移动、覆盖或删除；补丁只能发布为新的 v0.20.1。

### Step 194 — 2026-08-24
- files: `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `VERSION`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `docs/VERSIONS.md`, `plan.md`
- verify: 先在真实 6425 复现 `task=task-182` 刷新后被移除并回到 task-178；定位为 `selectRun()` 只用 legacy `snapshot.tasks` 校验需求 ID。修复后新增自动合同检查；`python3 -B -m unittest` → 142 tests / 0 failures，JavaScript/Python 语法、`generate.sh --check`、版本与 diff 检查全部 exit 0。

### Step 195 — 2026-08-24
- files: installed `~/.mick-harness`, `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `docs/VERSIONS.md`, `plan.md`
- verify: 安装版升到 `613b084 / VERSION 0.20.1`，6425 从 PID `15239` 切换到 `30909` 并保持 health ok；task-194 按 PM → product Review → Executor → QA 回写，显示等待发布且有 2 条独立 QA 证据。
- interaction: 真实浏览器打开 task-194 后执行 reload，URL 继续包含 `task=task-194`、页面仍展开唯一 task-194 任务办公室且当前查看一致；开发角色详情包含 task-194、不含 task-182；桌面 `scrollWidth=innerWidth=1280`，控制台 0 error / 0 warning。

### Step 196 — 2026-08-24
- files: GitHub branch `main`, annotated Git tag `v0.20.1`, installed `~/.mick-harness`, `plan.md`
- verify: GitHub 已接受补丁发布基线 `6837929..2b6b727`；最终发布记录与 annotated `v0.20.1` 使用原子推送，发布后核对远端 main、tag object、peeled commit，并运行本机 update 与显式 tag fetch 对齐最终提交。

## v0.20.2 · 2026-08-24 · Brain 公共默认值与对外发布清理

- result: 新安装使用通用 `~/.brain`，旧目录保持兼容；公开配置、Loader 和发布包不再携带维护者身份、个人远端或个人画像。
- verify: 150 tests / 0 failures；Shell、生成一致性、首次安装、旧目录升级和公开发布污染审计全部通过。
- release: `main` 与 annotated tag `v0.20.2` 已发布；本次 v0.21 合并保留该补丁全部边界。

## v0.21.0 · 2026-08-24 · 通用命令与上下文瘦身

### 用户目标

- 用户不需要记住分散的脚本和角色话术，就能主动发起“扫描并建立计划、建立长期目标、配置 Brain、端到端完成单条需求”四类核心工作。
- 同一意图在不同 Code Agent 中使用相同的数据和完成定义；宿主不支持自定义 `/` 命令时，仍可通过 Harness CLI 或显式 Skill 使用。
- 没有 Brain 远端的用户能明确选择仅保存在本机或暂不启用，不会把本地模式误显示为同步故障。
- Harness 日常加载只保留高价值 Kernel；详细角色、场景流程和外部方法按需加载，避免短任务承担完整 Playbook 的 Token 成本。

### 已确认产品决策

- Codex 已有 `/plan` 和 `/goal` 保持原语义，Harness 不覆盖宿主命令；统一底层入口命名为 `harness plan|goal|brain|e2e`，上层使用宿主支持的 Skill、命令菜单或自定义 Prompt 适配。
- “通用命令”保证意图、状态源、写入结果和验证合同一致，不承诺每个 Agent 都支持完全相同的斜杠语法。
- `harness e2e` 必须绑定一个明确的 `requirement_id`，按需求级状态机推进；默认交付到发布候选，不自动合并、推送、打标签或发布。
- Brain 默认支持三种清晰状态：仅本机、已连接私有远端、暂不启用；普通 `harness init` 不强制创建 Brain，显式配置或 `--full` 才建立本地骨架。
- 常驻上下文以字节和近似 Token 双预算约束；详细 Skill 使用渐进式加载，确定性扫描、写入、校验和状态迁移优先由代码完成。

### 范围与边界

- 不修改 Codex、Claude Code 或其他宿主已有的保留命令语义。
- 不把端到端交付解释为无条件自主发布；外部权限、不可逆操作、需求歧义和正式发布继续经过用户门禁。
- 不把项目源代码、Prompt、聊天全文、密钥、环境变量或 Brain 私人正文放入命令事件或工作台预览。
- 不为实现快捷入口复制四套业务逻辑；CLI/服务端是事实源，Skill 和宿主命令只负责收集意图、展示预览与调用稳定接口。
- 不以扩大模型上下文换取可靠性；能被脚本、Schema、状态机或测试确定的行为不长期占用 Prompt。

### 实施步骤

- [x] 197. [合同与基线] 固定四类命令的输入、预览、确认、产物、错误和宿主兼容合同；记录当前 CLI、Brain 降级路径、Loader 字节预算及回归基线。
- [x] 198. [Plan / Goal] 实现项目事实扫描、冲突预览、计划档案写入与长期目标维护；已有活跃计划、缺少稳定目标和历史文件迁移均有明确处理。
- [x] 199. [Brain] 实现 `status / configure / install / sync` 的统一配置体验，支持仅本机、私有远端、暂不启用三态，并让工作台解释写入位置和同步范围。
- [x] 200. [E2E] 实现以单条需求为单位的受控编排，复用 v0.20 门禁投影，输出当前关卡、缺失证据、停止原因和发布候选结果。
- [x] 201. [上下文瘦身] 将常驻 Loader 压缩到可审计预算，把角色详细流程迁移为按需 Skill / reference，并为生成物上限、截断和关键 Kernel 保留建立自动检查。
- [x] 202. [工作台与验证] 提供命令发现、预览、执行反馈和历史结果入口；完成跨 Agent 适配、Brain 无远端路径、Token 预算、全仓回归和真实用户路径审查。

### 完成判定

- [x] CLI 在不依赖特定 Agent 的情况下可发现和执行四类能力；Codex `/plan`、`/goal` 原生命令不被覆盖或误导。
- [x] Plan / Goal 写入前均有预览；不会覆盖不相关的活跃计划，也不会把版本目标写成项目长期目标。
- [x] 无 Brain 远端时可选择仅本机或暂不启用，工作台不显示虚假的“待同步”；配置私有远端后能验证真实仓库与同步结果。
- [x] E2E 无 `requirement_id` 时拒绝执行；任何门禁缺失都停止在正确角色，只有 QA 证据完整时进入发布候选。
- [x] 全局加项目常驻 Loader 明显低于 Codex 默认 32 KiB 指令发现上限，并有自动预算测试；详细 Skill 只在触发时加载。
- [x] 工作台能说明命令会读取什么、写到哪里、需要哪些确认，并能展示成功、失败、取消和可恢复状态。
- [x] 全量测试、规则生成、脚本语法、安装冒烟、跨 Agent 兼容、Brain 本地降级和真实工作台路径均提供本次证据。

### Preflight 与停止条件

- 首先冻结当前 v0.20.1 的 CLI、Loader、Brain 和需求门禁行为作为基线；实现期间不直接在已发布的 `main` 上开发。
- 任何宿主命令能力以当前官方文档和真实应用行为为准；宿主不允许覆盖保留命令时使用 Skill 或命名空间，不做未验证的注入技巧。
- 所有计划、目标和 Brain 写入先在临时项目或临时 HOME 验证预览、确认、幂等和恢复，再触碰用户真实项目或配置。
- Loader 瘦身必须证明 Tripwire、完成验证、回合卡片和按需加载链仍可发现；只比较文件更小而不验证行为不算完成。
- 同一错误指纹重复两次进入 Debug Card；出现计划覆盖、Brain 数据误发、宿主配置损坏或门禁绕过时立即停止后续步骤。

### Planner Lock — 2026-08-24

- files: `docs/VERSIONS.md`, `plan.md`
- verify: 用户已确认采用统一 CLI、Agent 薄适配、Brain 三态、`/e2e` 默认止于发布候选和常驻上下文瘦身，并明确要求“立项”。
- notes: 本轮只建立版本目标、边界和六步计划；未修改 `VERSION`、发布记录、运行代码、用户 Agent 配置或 Brain 数据。

### Step 197 — 2026-08-24

- files: `config/command-registry.json`, `docs/COMMANDS.md`, `tests/test_harness_commands.py`, `plan.md`
- verify: `python3 -B -m unittest tests.test_harness_commands` → 7 passed；`python3 -m json.tool config/command-registry.json`、`git diff --check` 通过；允许 localhost 后运行 `python3 -B -m unittest` → 149 passed。
- notes: 固定 `harness plan|goal|brain|e2e` 的预览、显式写入、停止原因和错误码；Codex `/plan`、`/goal` 明确列为宿主保留命令，E2E 默认止于发布候选；记录瘦身前 32,640 bytes 常驻 Loader 基线。

### Step 198 — 2026-08-24

- files: `bin/harness`, `scripts/harness-command.py`, `tests/test_harness_commands.py`, `plan.md`
- verify: `python3 -B -m unittest tests.test_harness_commands` → 14 passed；无缓存 Python compile、`bash -n bin/harness`、`git diff --check` 通过；允许 localhost 后运行 `python3 -B -m unittest` → 156 passed。
- notes: `harness plan` 默认扫描并预览，显式 `--apply` 才创建或追加计划档案，活跃计划冲突以 exit 2 停止；`harness goal` 只维护 `docs/PROJECT.md` 的人类长期目标，版本号、需求编号、实施任务与技术细节会被拒绝，写入采用同目录原子替换。

### Step 199 — 2026-08-24

- files: `bin/harness`, `scripts/harness-command.py`, `scripts/brain-resolve.sh`, Brain 写入/同步/维护脚本，`scripts/harness-brain-boundary.py`, `web/observe-dashboard.html`, 命令与工作台测试，`plan.md`
- verify: Brain 定向测试初次因测试夹具错误追加项目参数出现 3 条同因失败，按 Debug Card 只修夹具后 `python3 -B -m unittest tests.test_harness_commands` → 18 passed；工作台合同定向测试通过；无缓存 Python compile、12 个 Shell `bash -n`、`git diff --check` 通过；允许 localhost 后 `python3 -B -m unittest` → 160 passed；真实只读 `harness brain status --json` 确认旧配置远端与实际 origin 一致。
- notes: 新用户配置位于 `~/.config/mick-harness/brain.json`（支持 XDG / 测试覆盖），默认无配置时不创建 Brain；`local` 不产生虚假待同步，`remote` 核对配置仓库与实际 origin，`disabled` 阻止直接写入、采集、压缩和 Hook 安装且不删除旧数据；旧 `.brain-config.yaml` 继续只读兼容，只有用户显式 `configure --apply` 才迁移到新配置。

### Step 200 — 2026-08-24

- files: `bin/harness`, `scripts/harness-command.py`, `tests/test_harness_commands.py`, `plan.md`
- verify: `python3 -B -m unittest tests.test_harness_commands` → 21 passed；无缓存 Python compile、`bash -n bin/harness`、`git diff --check` 通过；允许 localhost 后 `python3 -B -m unittest` → 163 passed。
- notes: `harness e2e` 必须绑定当前版本的一条 requirement，默认只读已有 runtime 并复用 v0.20 `requirement_workflow_snapshot`；`--run` 只追加一条最小命令请求，未满足门禁时以 exit 2 等待真实角色，绝不伪造角色完成或自动 spawn Agent；只有产品审查、开发产物与自检、独立 QA 证据齐全时记录 `release_candidate`，正式发布仍需用户确认。

### Step 201 — 2026-08-24

- files: `rules/core.md`, `generate.sh`, `dist/AGENTS.md`, `scripts/harness-context-budget.py`, `tests/test_context_budget.py`, four `rules/skills/harness-*` adapters, Skill governance docs, `plan.md`
- verify: 四个新 Skill 经 Skill Creator `quick_validate.py` 均返回 `Skill is valid!`；上下文预算在 4 KiB Capsule 最坏常规输入下仍低于 `28 KiB` 合计上限，关键 Kernel marker 全部保留；全仓 `165 tests / 0 failures`，`generate.sh --check`、Python/Shell/JSON/Skill 校验与 `git diff --check` 通过。
- notes: 常驻入口相比 v0.20.1 的 `32,640 bytes` 基线显著降低；删去 Core 与生成器中的重复解释但保留 Tripwire、验证 Gate、Debug Card、回合卡片和按需 Extended 链路；个人 Capsule 设为 4 KiB UTF-8 安全上限；四类 Agent 入口是默认禁止隐式触发的薄 Skill，底层事实与写入仍由 CLI 控制，Codex 原生 `/plan`、`/goal` 未被覆盖。

### Step 202 — 2026-08-24

- files: `scripts/harness-observe.py`, `web/observe-dashboard.html`, Agent/Skill/Brain 适配脚本与注册表、命令文档、全套自动测试、`docs/VERSIONS.md`, `plan.md`
- verify: `178 tests / 0 failures`；发布级 Gate 同时通过全仓回归、`generate.sh --check` 与 `git diff --check`；四个命令 Skill 均通过 `quick_validate.py`，上下文预算为 Core `8,825/10,240`、项目 Loader `15,221/16,384`、全局 Loader `11,076/12,288`、合计 `26,297/28,672 bytes`；隔离项目 `setup.sh --non-interactive` 无警告，隔离 HOME 下 Codex/Claude Loader 与四个 Skill 首次同步、再次幂等同步通过；无用户配置时 Brain 为 `disabled/default` 且未创建目录，现有 Mick Brain 仍核对为 `connected` 且远端一致。
- interaction: 6246 真实工作台展示 3 个系统操作与 4 个通用命令；已有活跃 Plan 的预检以 `已安全停止` 记录且不写入，长期目标确认单可取消并在历史查看结果；390px 视口下页面 `scrollWidth=390`，弹窗 `scrollWidth=clientWidth=348`，控制台 0 error / 0 warning。
- notes: 工作台操作全部使用服务端白名单参数和固定 CLI 数组，不执行用户拼接的 Shell；公开仓库的旧 Brain 远端只兼容已经存在本地 Brain 的老用户，新用户不会继承作者远端；跨 Agent 已证明文件与 Skill 适配幂等，宿主真实加载仍应在发布安装后的新 Codex/Claude 会话做最终确认。

## v0.21.0 · 2026-08-24 · 默认轻量执行与可介入流程

### 用户目标

- Harness 默认让明确、低风险、易验证的任务直接完成，不把 Self-Test、角色流转和回合仪式暴露给用户。
- 完整需求才进入 E2E：第一轮先说明理解、范围、关键假设和验收方式，用户确认后自主执行到发布候选；只有偏离原意或遇到高风险决策时才重新打断。
- 用户无需记命令；自动判断是默认入口，显式模式只作为覆盖，工作台后续能说明当前模式、升级原因、耗时和是否需要用户决定。

### 已确认产品决策

- 默认模式为 `auto`，优先选择最轻量且足以证明结果的流程。
- 明确、可恢复、无产品方向判断且验证路径清楚的任务进入 `quick`；不创建 plan、不启动角色流程、不展示 Self-Test 或六槽回合卡片，只在异常、超出原意或需要权限时打断。
- `standard` 用于普通多文件开发或少量产品判断；`e2e` 用于完整需求，并固定止于发布候选。
- 模式是交互强度，不降低先读后改、危险操作确认、撞墙熔断和完成验证；安全护栏默认后台运行。
- 快速路径发现范围扩大时不得静默增加流程，必须说明升级原因；`standard → e2e` 必须由用户确认。

### 实施步骤

- [x] 203. [模式合同] 在机器可读命令合同、用户说明和合同测试中定义 `auto / quick / standard / e2e` 的选择、可见输出、升级与发布边界。
- [x] 204. [Kernel 轻量路径] 调整 Core / Extended：简单任务静默执行安全检查，Self-Test 与回合卡片只在用户需要导航或真实高风险时可见；生成 Loader 并验证上下文预算。
- [x] 205. [运行投影] 让 Agent 适配与本地事件记录当前有效模式、选择原因和升级原因，不以 Prompt 猜测替代结构化状态。
- [x] 206. [工作台与验收] 在工作台展示模式、耗时、可证明的往返和待用户决策；完成三条模式路径验收，并让同一项目的登记目录、嵌套 Git 仓库和 Agent 镜像归并为一个项目身份。

### 本轮开发边界

- 本轮只执行 Step 203–204，形成可评审的模式合同和 Kernel 行为；不继续实现工作台或部署到用户全局配置。
- 完成 Step 204 后暂停，由用户检查“简单任务是否足够安静、E2E 是否仍保持可介入”，确认后再进入 Step 205。

### Step 203 — 2026-08-24
- files: `config/command-registry.json`, `docs/COMMANDS.md`, `docs/VERSIONS.md`, `tests/test_harness_commands.py`, `plan.md`
- verify: `python3 -m json.tool config/command-registry.json` exit 0；`python3 -B -m unittest tests.test_harness_commands tests.test_context_budget` → 29 passed。
- notes: 默认 `auto`，Quick 不建 plan/角色流且不展示 Self-Test/回合卡片；E2E 第一轮确认意图后自主到发布候选，方向变化或高风险动作才重新询问。

### Step 204 — 2026-08-24
- files: `rules/core.md`, `rules/extended.md`, `dist/AGENTS.md`, `tests/test_context_budget.py`, `plan.md`
- verify: `./generate.sh --check`、`git diff --check` exit 0；上下文预算 Core `9,379/10,240`、项目 Loader `15,775/16,384`、全局 Loader `11,630/12,288`、合计 `27,405/28,672 bytes`，status passed。
- notes: Self-Test 改为默认内部检查；Quick 交付只给结果与验证，Standard/E2E 才使用可见导航；本轮按约定暂停，不进入 Step 205–206。

### Step 205 — 2026-08-25
- files: `scripts/harness-observe.py`, `docs/runtime-event-v0.schema.json`, `docs/OBSERVE.md`, `rules/core.md`, `tests/test_harness_observe.py`, `docs/VERSIONS.md`, `plan.md`
- verify: `python3 -B -m unittest tests.test_harness_observe tests.test_context_budget` → 100 passed；`./generate.sh --check`、JSON 语法与 `git diff --check` exit 0；上下文预算 Core `9,558/10,240`、项目 Loader `15,954/16,384`、全局 Loader `11,809/12,288`、合计 `27,763/28,672 bytes`，status passed。
- notes: 新事件显式记录请求模式、有效模式和选择原因；升级必须记录原模式与事实原因，需要用户裁决可单独标记。旧事件保持兼容，服务端不读取 Prompt 推断模式；本轮暂停，不进入 Step 206 工作台改造。

### Step 206 — 2026-08-30
- files: `scripts/harness-observe.py`, `scripts/harness-observe-hook.py`, `web/observe-dashboard.html`, `tests/test_harness_observe.py`, `docs/OBSERVE.md`, `docs/VERSIONS.md`, `plan.md`
- verify: Observer 定向回归 `101 tests / 0 failures`；合并 v0.20.2 后最终全仓 `195 tests / 0 failures`，生成一致性、Shell/Python/JSON、上下文预算、公开发布审计、`git diff --check` 与非交互临时安装全部通过；源码工作台在真实浏览器读取 `hiring-system-74507438d8`，展示 21 个 Agent 回合、7 个 Git 提交、代码仓库 `~/Desktop/hiring-system/site`，不再出现 `vundefined`，桌面宽度无横向溢出且控制台 0 error / 0 warning。
- notes: 登记目录继续是稳定项目身份；唯一浅层子 Git 仓库作为代码工作区，ChatGPT/Codex 镜像按声明标题唯一匹配并归入同一项目。Git 与 Agent 活动只证明真实工作发生，不伪造版本、需求或 PM 状态；宿主未提供通用工具调用计数时明确显示“未记录”。

## v0.22.0 · 2026-09-03 · 维护诊断与需求清零

### 用户目标

- 把散落在 README、旧 TODO、Agent 诊断、Brain 与 Observer 状态里的维护事项收拢成一份可执行、可验证的诊断结果。
- 清空当前真实需求列表：实现仍有价值的维护能力，明确关闭已被替代的旧待办，并避免历史验收勾选状态继续制造假进度。

### 已确认事实

- `main`、`origin/main` 与 `v0.21.0` 均指向 `741f4af`；GitHub 当前没有开放 Issue。
- `docs/VERSIONS.md` 的正式版本需求全部完成，Backlog 为空；README 仍列有 4 项下一版本重点。
- 根目录 `TODO.md` 把已经完成的 Git Brain 架构继续标为进行中，并保留 4 条早期实现待办，已不再是可信状态源。
- 开发前全量基线在允许绑定 localhost 的环境为 `195 tests / 0 failures`；受限沙箱内的 6 个错误均为临时端口权限，不是产品回归。

### 范围与边界

- 不新增第三方依赖，不重新设计工作台，不修改 Brain 私人数据，不自动发布或推送。
- 顶层 `harness doctor` 只聚合确定性状态源，不复制 Agent、Brain、Observer 或 audit 的业务逻辑。
- Adapter Registry 只补齐机器可读的支持状态、加载方式、生命周期能力和限制，不虚构未验证的 Agent 支持。
- 旧 TODO 若已被现有能力替代，记录替代关系后关闭；不为了清零而重复实现过时脚本。

### 实施步骤

- [x] 207. [测试与实现] 增加顶层 `harness doctor [--json] [project]`，聚合安装、项目、Agent loader、Brain、Observer 与 audit，并对不可用项给出可执行下一步。
- [x] 208. [注册表] 升级 Agent Adapter Registry 的能力字段与文档，让支持等级、规则加载、Skill、Hook、自动修复和已知限制可被 CLI 与工作台一致读取。
- [x] 209. [Fixture] 增加 Brain ingest、hook adapter、`brain evolve` 与无 Brain fallback 的隔离测试，禁止读写用户真实 Brain 或 Agent 配置。
- [x] 210. [收口] 压缩 README 首次使用路径，纠正 `TODO.md`、历史验收勾选和“下一版本重点”，使 `docs/VERSIONS.md` 成为唯一产品需求源。
- [x] 211. [验证] 运行全量测试、生成一致性、Shell/Python/JSON 校验、安装冒烟与真实 6425 Doctor/工作台检查，形成干净发布候选并复查剩余需求数为 0。

### 完成判定

- [x] 用户运行一条 `harness doctor` 就能知道 Harness 是否安装、当前项目是否接入、Agent 是否加载、Brain 是否启用、6425 是否健康、audit 是否通过，以及失败时下一步做什么。
- [x] Registry 对每个 Agent 明确区分 detected / managed / manual / unsupported，且不会把文件存在误报为运行时已加载。
- [x] 四类 Brain/Hook fixture 在临时 HOME 和临时项目中可重复运行，测试后不留下用户目录副作用。
- [x] README、TODO、plan 与版本 Backlog 不再互相冲突；当前需求清单只有本版本步骤，完成后为 0。
- [x] 全量回归本次为 0 failures，真实产品服务状态和 Doctor 输出相互一致；未获得发布授权前停在发布候选。

### Step 207 — 2026-09-03
- files: `bin/harness`, `scripts/harness-doctor.py`, `tests/test_harness_doctor.py`, `README.md`
- verify: 顶层 CLI 与六组件报告聚焦测试通过；JSON 输出可机器读取，Brain 未启用时标为 optional，Observer 或远端配置异常时返回 blocked 和固定修复动作。

### Step 208 — 2026-09-03
- files: `config/agent-registry.json`, `scripts/harness-agent-manager.py`, `scripts/harness-observe.py`, `web/observe-dashboard.html`, `docs/AGENT-SUPPORT.md`, `tests/test_harness_agents.py`, `tests/test_harness_observe.py`
- verify: Registry schema v2、CLI 报告、Observer API 与工作台支持标签聚焦测试通过；七个 Agent 均声明 support/loading/skills/hooks/repair，运行时加载状态仍只来自真实事件。

### Step 209 — 2026-09-03
- files: `tests/test_brain_workflows.py`, `scripts/harness-evolve.sh`
- verify: 5 个隔离 fixture 全部通过，覆盖配置 Brain 写入、无配置不写入、Claude Hook 幂等、Brain 演进只产提案、无 Brain 时读取当前项目日志；测试全部使用临时 HOME/配置/项目。

### Step 210 — 2026-09-03
- files: `README.md`, `TODO.md`, `docs/AGENT-SUPPORT.md`, `plan.md`, `tests/test_harness_doctor.py`
- verify: README 首次路径改为 install → init → doctor；旧 TODO 不含未完成复选框，README 不再维护“下一版本重点”，v0.19 五项历史验收按已有 Step 147–160 证据修正为完成；需求源合同测试通过。

### Step 211 — 2026-09-03
- files: `VERSION`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `dist/AGENTS.md`, `docs/VERSIONS.md`, `plan.md`
- verify: 最终 v0.22.0 指纹全仓 `204 tests / 0 failures`；`generate.sh --check`、全部 Shell/Python/JSON 语法与 `git diff --check` 通过；临时 HOME 完成 init、Agent sync/hooks 和 Doctor；真实 6425 `status=ok`、10/10 项目可用，Doctor 同样判定 Observer 正常。
- ui: 临时 6247 源码工作台真实显示 7 个 Agent 的自动管理/手动接入/暂不支持状态；1280px 视口 `scrollWidth = innerWidth = 1280`，浏览器控制台 0 error / 0 warning；验收后临时服务已停止。
- boundary: 形成 v0.22.0 发布候选；未合并 main、未打标签、未推送、未部署到 `~/.mick-harness`。

### 正式发布 — 2026-09-03
- files: `docs/VERSIONS.md`, `plan.md`, Git branch `main`, annotated Git tag `v0.22.0`, installed `~/.mick-harness`
- verify: 发布候选已快进合并到 main；main 再次通过 `204 tests / 0 failures` 和生成一致性，随后以 annotated tag 发布并用远端引用、安装版本、6425 健康状态和安装版 `harness doctor` 复核。
- boundary: 保留用户未跟踪的 `narc_for_mac/`；正式发布不修改 Brain 私人内容。

## v0.22.1 · 2026-09-03 · 更新后真实重载服务

### 用户目标

- `harness update` 不仅更新磁盘文件，还要让唯一的 6425 常驻进程实际加载新代码，并让本机版本描述取得对应发布标签。

### 已验证问题

- v0.22.0 更新后 `VERSION` 与安装提交均已变化，但 6425 PID 和启动时间保持不变，证明仍运行更新前的 Python 进程。
- GitHub 已存在 `v0.22.0`，本机安装 clone 未取得该标签，导致 `harness version` 显示 `v0.21.0-2-g...`。

### 边界

- 只修改 update 生命周期；无新版本时继续复用健康服务，不因重复 update 无谓重启。
- 不改变 Observer 的幂等 install 语义，不修改项目、Brain 数据或用户未跟踪文件。

### 实施步骤

- [x] 212. [失败合同] 固定 update 必须取得发布标签，并且只在安装提交变化时显式重启 Observer。
- [x] 213. [修复] 在 pull 前后比较提交；更新后获取 tags、刷新项目和 Agent，再重启唯一 6425；无变化时沿用幂等 install。
- [ ] 214. [发布] 完成回归、v0.22.1 发布、本机更新和 PID/版本/Doctor 真实复核。

### 完成判定

- [ ] 有新提交时，update 后 6425 PID 或启动时间变化且 `/healthz` 正常；安装版 `harness version` 显示当前 tag。
- [ ] 无新提交时，重复 update 不重启健康服务。
- [ ] 全量回归、生成一致性、公开发布审计和安装版 Doctor 通过。

### Step 212 — 2026-09-03
- files: `tests/test_harness_doctor.py`, `plan.md`
- verify: 新合同在 v0.22.0 实现上按预期失败，明确缺少更新前后提交比较、tag 获取和 Observer 条件重启。

### Step 213 — 2026-09-03
- files: `bin/harness`, `VERSION`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `docs/VERSIONS.md`, `plan.md`
- verify: 聚焦合同与 `bash -n bin/harness` 通过；更新路径只在 before/after revision 不同时调用 `service restart`，无变化时继续调用幂等 `service install`。

### Step 214 发布验证检查点 — 2026-09-03
- verify: 修复已快进到 `main`；main 上 `205 tests / 0 failures`，生成一致性、Shell/Python/JSON 语法、公开发布审计和 `git diff --check` 均通过。
- transition: 从 v0.22.0 更新器拉取 v0.22.1 修复后，旧进程仍未恢复；已显式重启一次完成过渡，6425 恢复为 `status=ok`。后续必须由新更新器自行证明“有提交才重载、无提交不重启”。
- pending: 发布标签、安装版增量更新 PID 对照、无变化更新 PID 对照和最终 Doctor 仍待验证，因此 `task-214` 保持未完成。
