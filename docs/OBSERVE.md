# Mick Harness：本地工作服务器与统一项目工作台

安装 Mick Harness 后会得到两个协同部分：项目侧通过 `harness init` 注入规则，让 AI Agent 按同一套目标、验证和交接纪律工作；本机常驻的 **Mick Harness Observer**（服务标识 `com.mick.harness.observer`）接收所有已注入项目的结构化工作事件，并在统一工作台中展示项目、需求、角色、决策与交付状态。

它是活动的本地工作服务器，但不是自动编排器：不会创建 Agent、派发消息、领取任务、替你审批，也不会改写 `plan.md`、`docs/STATE*.md` 或代码。

## 快速开始

macOS 安装或更新 Harness 时会安装用户级 LaunchAgent。也可以显式安装或修复服务：

```bash
harness observe service install
harness observe service status
```

`service install` 是幂等维护操作：现有配置一致且服务健康时保持当前进程，不先停止服务；确实需要替换配置时会保留旧 plist 和加载状态，新服务启动失败则恢复旧服务并在错误中报告恢复结果。

浏览器打开 `http://127.0.0.1:6425/`。服务只监听本机；读取接口使用 `GET` / `HEAD`，结构化回写只开放带本机令牌的 `POST /api/v1/events`。`6425` 对应电话键盘上的 `MICK`。

开发或排错时可以使用临时前台模式：

```bash
harness observe watch --all
```

也可以显式指定项目和端口：

```bash
harness observe init /path/to/project
harness observe watch /path/to/project --port 6426
```

前台端口只用于开发对照，不是第二套工作台。产品状态以 LaunchAgent 管理的 `6425` 为准；前台 `watch --all` 与后台服务读取同一份项目注册表并执行同一套扫描逻辑。

## v0.19.0 · 2026-08-20 · 工作台受控操作

工作台首页提供三项确定性操作：**更新 Harness**、**注入或升级项目**、**修复 Agent 接入**。它们不是交给 AI 临时组织命令，而是后端维护的固定白名单；浏览器不能提交命令名、参数数组、脚本正文或环境变量。

每项操作都经过同一条用户路径：

1. 用户选择动作；项目注入额外填写一个已存在的绝对目录。
2. 后端重新验证动作和参数，只读生成确认单，列出目标、影响、阻塞和恢复说明。此时不会写入。
3. 用户明确确认后，一次性确认单进入队列；同一确认单不能重复执行，同时只能有一个本机配置操作。
4. 独立 worker 调用固定 Harness CLI。刷新或关闭页面不会中断；工作台持续读取等待、执行、成功或失败状态。
5. 结果写入 `~/.local/state/mick-harness/operations/`，最近结果可在首页展开；审计只保留动作、目标、状态、时间和退出码，不保存密钥、完整命令输出或环境变量。

三项操作的实际边界：

| 操作 | 会做什么 | 不会做什么 |
|---|---|---|
| 更新 Harness | 拉取 `main` 已发布代码、刷新登记项目、同步 Agent，并由独立 worker 重启和确认 6425 | 不切换项目分支，不修改项目代码，不吞掉服务恢复错误 |
| 注入或升级项目 | 复用 `harness init` 挂载规则入口并登记项目；完整模式额外检查 Brain 配置 | 不覆盖不兼容的真实 `.harness/` 目录，不删除已有规则或 Git 历史 |
| 修复 Agent 接入 | 复用 `harness agents sync --quiet` 重新生成支持范围内的加载器与 Hook | 不安装未知 Agent，不接管外部 Skill，不把“文件存在”冒充“真实会话已生效” |

操作接口复用当前服务启动时生成的本机动作令牌。`GET /api/operations.json` 返回动作目录、当前任务、最近结果和页面会话令牌；`POST /api/operations/preview` 生成一次性确认单；`POST /api/operations/<id>/execute` 只接受该确认单。服务仅监听 `127.0.0.1`，但本机边界不等于无需鉴权：没有动作令牌的写请求仍返回 `401`。

更新期间旧页面可能短暂失去连接，因为产品端口会切换到新进程；worker 不依赖旧请求存活，完成后操作记录仍可读取。若更新或服务启动失败，页面显示脱敏错误并保留重试入口；LaunchAgent 的配置替换继续使用 task-133 的旧配置恢复机制。

## v0.19.0 · 2026-08-20 · 角色办公室与失联项目

角色办公室展示的是真实结构化回合，不是根据测试数量推测角色参与。Executor 运行自验、Reviewer 重跑测试和 QA 独立验收是三件不同的事：只有同需求、且时序上晚于开发交付的 QA 完成回合，才显示“QA 已参与”。UI/交互、外部系统、数据写入、故障恢复、共享契约和 plan 已定义验收的交付，流转顺序是 Executor/Designer → QA → Reviewer。

Reviewer 不是“再跑一次测试”的别名。它审查原始需求、受影响 diff/产物、QA 证据、findings 与剩余风险。角色历史会展示对应需求、审查对象和结论；事件未携带产物或验证引用时，工作台明确显示“未记录”。

左侧导航将可用项目与“连接异常”分开。不存在、不可读或缺少 Harness 入口的项目可以经二次确认“移出工作台”。这个动作只从 `registered-projects` 删除该路径，返回 `files_deleted=false`；它不访问、修改或删除项目目录及 `.harness-runtime/`。以后在该目录重新执行 `harness init` 即可再次登记。

## v0.19.0 · 2026-08-21 · 当前版本需求指挥台

项目主页先展示当前版本需求，不再用一个全局角色阶段解释整个版本。每条需求独立显示计划状态、实际参与角色、当前工作、QA 测试范围、显式验证证据、活动阻塞和下一步；点击需求后，角色办公室只突出该需求的参与和交接。

版本需求来自 `docs/VERSIONS.md`，执行事实来自同 `requirement_id` 的结构化工作回合、验证、阻塞与交接。没有 QA 回合时显示“尚未进入独立测试”；存在 QA 回合但没有目标或摘要时显示“测试范围未记录”。验证证据必须由 QA 回合显式引用，不能仅凭相同的 `task_id` 把旧 Plan 步骤自检混入当前需求。

项目导航使用“项目主页 / 版本记录 / 交付物”。项目主页负责当前版本行动，版本记录负责历史版本、分支、工作区和发布标签关系。

## v0.19.0 · 2026-08-22 · 项目问题回流 Harness

Brain 项目记忆和 Harness 改进是两条不同链路：项目记忆保存某个项目已经确认的事实；Harness 改进只处理“现有 Harness 没有阻止或发现的问题”。工作台不会自动把每条项目记忆都判成 Harness 缺陷，用户必须在项目记忆中明确点击“提交为 Harness 问题”，并选择建议落点：Rule、Skill、Checker 或 Profile。

候选先进入“项目观察中”。单个项目的一次问题默认留在项目层，不会自动送审；跨项目相似候选可以合并来源和频次，同一候选涉及至少两个项目或累计至少三次后才自动满足送审条件。用户也可以对单项目信号明确确认“仍然送审”，但它仍只进入人工审批。

批准候选只会在 `~/.local/state/mick-harness/harness-improvements/proposals/` 生成可审计 Markdown 提案，不会直接修改中央 Harness。后续真实开发完成 Rule、Skill、Checker 或 Profile 后，用户在工作台登记项目相对产物路径和落地前频次；再以 `improved`、`unchanged` 或 `regressed` 记录效果复验。只有同类问题频次下降，才显示“复验有效”。

所有候选写操作都使用当前 localhost action token。`GET /api/harness/improvements.json` 只读；创建、合并、送审、批准、拒绝、登记落地和效果复验使用 `POST /api/harness/improvements...`。原项目记忆、项目文件和中央 Harness 规则均不会因这些动作被删除或自动改写。

## 命令

| 命令 | 作用 |
|---|---|
| `harness observe init [project]` | 初始化或复用当前 run，并立即同步一次来源 |
| `harness observe sync [project]` | 读取发生变化的来源并追加事件；相同内容不会重复导入 |
| `harness observe status [project]` | 输出阶段、任务进度、阻塞、待验证数量和最后序号 |
| `harness observe replay [project]` | 从 `events.jsonl` 重新生成 snapshot |
| `harness observe watch [project] [--port N]` | 启动临时前台 Dashboard；默认端口为 `6425` |
| `harness observe watch --all [--port N]` | 从 Harness registry 聚合全部项目并启动 Portfolio |
| `harness observe service install` | 安装/升级并启动 `com.mick.harness.observer` LaunchAgent |
| `harness observe service start\|stop\|restart` | 控制后台服务生命周期 |
| `harness observe service status` | 同时检查 plist、launchd job 和 `/healthz` |
| `harness observe service logs` | 显示最近的标准输出与错误日志 |
| `harness observe service uninstall` | 停止服务并移除 LaunchAgent；不删除项目事件账本 |
| `harness observe hook-config codex` | 输出可审查的 Codex lifecycle Hook JSON，不自动安装 |
| `harness observe emit <event-type> ...` | 向本地工作服务器回写角色工作、决策或角色交接；服务离线时安全降级到项目账本 |

不传 `project` 时使用当前目录。

## 双层数据流

```text
项目中的 Agent + 注入规则
        │  lifecycle / work round / decision / handoff
        ▼
127.0.0.1:6425 本地接收服务
        │  校验项目、令牌、Schema 和幂等键
        ▼
项目 .harness-runtime/events.jsonl
        │  可重放投影 + 跨项目聚合
        ▼
统一项目工作台
```

服务不可达、项目尚未被旧服务识别或运行的是旧版只读服务时，客户端直接写入该项目账本作为降级；这不会改变 Agent 或 Harness 原命令的退出状态。服务恢复后，后台扫描会重新聚合这些事件。

## 数据从哪里来

Collector 只读扫描这些来源：

- `plan.md`
- `docs/STATE.md` 与 `docs/STATE-*.md`
- 项目内 `audit-log.md`

工作台还按用途读取三类 PM 事实源：

- `docs/PROJECT.md`：稳定的项目长期目标、目标用户和产品边界；只有长期定位改变时才更新。
- `docs/VERSIONS.md`：当前版本目标、需求归属和发布计划。
- `work.round_*` / `handoff.created` / `decision.recorded`：角色真实工作、交付、取舍和流转。

`plan.md` 只用于技术执行步骤和验证记录，不再充当项目长期目标。缺少某层事实源时，工作台显示对应空态，不从其他层猜一个替代答案。

全局 Portfolio 的项目名单来自 `~/.local/state/mick-harness/registered-projects`。`harness init` 会自动登记项目；目录不存在、不可读或缺少 Harness 入口时，Dashboard 保留该项目并显示失败原因，由用户决定是否只移除登记。

项目登记与服务安装彼此独立：`harness init <project>` 只注入规则并登记目录，不重装、不重启全局 Observer。一个已经运行的服务会在下一轮扫描自动发现新项目，因此接入项目不应造成 6425 中断或 PID 变化。

后台服务每 2 秒扫描一次所有 valid 项目，不需要打开 Dashboard 才会同步。导入过程按内容 digest 去重；单个项目失败只会让 `/healthz` 进入 `degraded` 并记录错误，不会终止服务。

在已注入项目目录中，每次执行 `harness` 都会优先向本地服务提交 `started` / `completed` 生命周期。只记录一级命令名与退出码，不记录参数、输出或环境变量。

注入给 Agent 的 Core Rules 要求执行型任务 best-effort 回写：

```bash
harness observe emit work.round_started --ref task-3-turn-1 --role Executor \
  --requirement task-3 --objective "实现本地事件接收"

harness observe emit work.round_completed --ref task-3-turn-1 --role Executor \
  --requirement task-3 --objective "实现本地事件接收" \
  --summary "接收、鉴权和持久化已验证" --next-role QA \
  --artifact docs/OBSERVE.md --artifact scripts/harness-observe.py
```

发生关键取舍时使用 `decision.recorded`，角色工作转交时使用 `handoff.created`。同一个事件引用默认形成稳定幂等键，重复提交不会重复写入。

`--artifact` 可以重复使用，只登记项目相对路径，不把文件正文复制进事件账本。Agent 交付 Markdown、代码或报告时应登记实际产物，工作台才会把它放进“产物”页供用户直接阅读。

checkbox Plan 的完成项只有在自检日志中存在 passing verification 时才投影为 `completed`；否则显示为 `verification_pending`。普通编号 Plan 会读取 `Current step: N / M`，把之前的需求显示为完成、当前需求显示为进行中、后续需求显示为待开始。所有投影都不会回写原始计划。

## 本地目录

观察数据只写入目标项目的 `.harness-runtime/`：

```text
.harness-runtime/
├── index.json
└── runs/
    └── <run-id>/
        ├── run.json
        ├── events.jsonl
        ├── snapshot.json
        └── imports/index.json
```

- `events.jsonl` 是 append-only 历史事实源。
- `snapshot.json` 是 Dashboard 使用的派生状态，可随时重建。
- `imports/index.json` 记录已导入来源的 digest，用于幂等同步。
- `index.json` 提供 run 列表和当前 snapshot 位置。

全局服务文件位于：

```text
~/Library/LaunchAgents/com.mick.harness.observer.plist
~/.local/state/mick-harness/observer/service.log
~/.local/state/mick-harness/observer/service.error.log
~/.local/state/mick-harness/observer/ingest-token
~/.local/state/mick-harness/harness-improvements/
```

`ingest-token` 首次启动时随机生成并固定为 mode `0600`，只用于 localhost 事件接收，不出现在健康状态、Dashboard 或日志中。

事件契约见 [`runtime-event-v0.schema.json`](runtime-event-v0.schema.json)。事件明确标注 `observed` 或 `inferred`；推断事件必须携带置信度。

## Dashboard 能看到什么

- 所有登记项目的有效性、阶段、当前角色和需求完成度
- 从 `docs/PROJECT.md` 读取的项目长期目标，以及单独展示的当前版本目标
- PM、设计、开发、测试、Review 五角色的场景化办公室；Planner / Orchestrator 归入 PM，不制造额外角色
- 当前真实交接或建议接手的高亮流转；历史流转留在办公室轨迹中
- hover/focus 任一角色查看最近动作，点击后看到该角色的需求上下文、执行摘要、关联决策、历史工作和已登记交付物
- 集中展示的“需要你处理”：活动阻塞、待验证需求和待审批事项
- Plan / STATE / 验证证据等已观察到的关键资料名称
- “产物”页直接阅读已登记的 Markdown、代码和文本报告；Markdown 使用文档阅读样式，代码使用可折叠、带行号的滚动区域
- “版本记录”页把 PM 维护的历史版本目标和需求归属，与真实 Git 当前分支、其他本地分支、Tag 和未提交改动并排展示
- “技术记录”中的 Plan 步骤、阶段、验证、阻塞、Agent、Harness 命令和审计事件

项目默认进入 `overview` 角色办公室。当前选择通过 URL 的 `project`、`run`、`view`、`role`、`task` 参数保存，刷新页面后可恢复；旧 `view=graph` 自动迁移为 `overview`。URL 指向 missing/invalid 项目时会自动回到项目总览并显示原因。

角色状态严格来自结构化事件：正在执行的 work round 为“正在工作”，最新流转的目标为“等待接手”，做过并完成工作为“已交付”，没有事件为“尚未参与”。开发交付已存在、但没有后续 QA 完成回合时，QA 显示“未独立验收”。`handoff.created` 是真实交接；已完成 work round 的 `next_role` 只是建议接手；质量门禁是后端根据同需求时序得出的缺口。三者在界面中明确区分。

没有当前需求时也不会统一显示“未确定”：当前版本需求全部完成时显示“本版本已交付，等待 PM 定义下一版本”；尚无版本计划时显示“PM 尚未规划版本”；只有确有未确认需求时才提示需要确认。

阶段的事实优先级是：`docs/STATE*.md` 当前阶段 > `plan.md` 顶部状态行 > 未完成任务推断。老项目没有 Harness 状态行时会显示 inferred 阶段，不会伪装成已观测事实。

## 产物阅读

工作台不是整个磁盘的文件浏览器。它只允许读取以下已授权来源中的项目相对路径：snapshot 已观察到的资料、`work.round_*` 事件通过 `--artifact` 登记的交付物，以及项目资料 `docs/PROJECT.md` 和版本计划 `docs/VERSIONS.md`。

“产物”页左侧始终列出当前项目中全部已授权文件。选择 Markdown 后，右侧阅读器同时显示“阶段导航”和“完整文档目录”；阶段导航来自文件自己的标题，不再使用 work round 日期筛选文件或生成阶段卡。

### 从产出到阅读

需要长期追加、以后按阶段回看的 Markdown（例如 `plan.md`、研究报告和版本记录），新阶段使用下面的标题：

```markdown
## v0.16.0 · 2026-08-12 · 结构化产物阶段导航
```

- **版本**必须来自真实版本计划，不能由 Agent 临时编造。
- **日期**是实际沟通或决策日期，不使用文件修改时间代替。
- **阶段标题**写用户能理解的目标或结果，不写“执行 Step 3”这类只有开发角色看得懂的动作。

Observer 只解析 H2–H4 标题，不扫描正文中的日期。artifact API 为 Markdown 返回 `stages`，每项包含标题行号、层级、版本、日期、全部更新时间、格式和是否完整可追踪；工作台按行号把阶段入口绑定到安全渲染后的正文标题。

旧项目中 `### 阶段名称（2026-07-13）` 或 `### 阶段名称 — 2026-07-13` 仍可进入导航。标题中有多个日期时全部保留、以最后一个作为最近更新；缺少版本会明确显示“未标版本 · 旧格式”，不会从事件或正文推断版本。没有阶段标题时仍显示完整文档目录，并提示下一次使用规范标题。

work round、角色、决策和交接继续保存在事件账本，并在角色工作和事件明细中阅读；它们不再冒充文档内部结构。同一路径始终对应一份当前文件，阶段导航也不是历史文件快照。如果旧正文被覆盖或删除，必须由未来的 Git blob 或显式快照能力恢复，不能把现有正文伪装成过去版本。

- Markdown：在浏览器中渲染标题、段落、列表、表格、引用和 fenced code block。
- Python、JavaScript、TypeScript、Shell、JSON、YAML、CSS、HTML 等代码：显示为可折叠代码块，保留注释和换行，可横向与纵向滚动。
- 其他 UTF-8 文本：按纯文本代码块显示。
- 安全限制：拒绝绝对路径、`..` 路径穿越、项目外软链接、二进制文件、非 UTF-8 文件以及超过 512 KiB 的文件。

对应只读接口为：

```text
GET /api/projects/<project-id>/workspace.json
GET /api/projects/<project-id>/artifact?path=<project-relative-path>&run=<run-id>
```

`workspace.json` 只返回可展示的产物元数据、版本计划与 Git 摘要；`artifact` 只返回已授权文件内容。接口不会修改文件。

## PM 版本规划与真实 Git

PM 在项目中维护 `docs/VERSIONS.md`，把“为什么做这个版本”和“哪些需求属于这个版本”写成人能理解的路线图；Git 仍是分支、Tag、HEAD 和工作区是否干净的事实源。两者并排显示，但工作台不会为了匹配计划自动创建或切换分支。

```markdown
# Version Plan

## 0.2.0
- status: in_progress
- branch: main
- tag: v0.2.0
- goal: 让用户在统一工作台查看项目产物和版本进度

### Requirements
- [x] `task-39` 产物阅读器
- [ ] `task-47` 浏览器真实路径验收
```

版本状态使用 `planned`、`in_progress`、`completed`、`released` 或 `paused`。`completed` 表示版本范围已经交付但尚未发布，只有真实 Tag / 发布事实成立后才使用 `released`。需求行使用 `- [ ]` / `- [x]` 表示计划中或已完成，真实 `task-*` id 放在反引号中以便和运行进度对照。新增需求若改变当前版本目标、风险或交付时间，PM 应把它放入下一版本，并在需求描述中留下迁移原因。

“版本规划”页会提示计划分支是否存在、当前是否位于该分支、Tag 是否存在，并列出没有归入任何版本的已观察需求。所有 Git 信息均通过只读命令获得；工作台不提供创建、切换、合并、删除分支、打 Tag 或 push 的操作。

## 记录 Codex 任务状态

Codex 官方 lifecycle Hook 会向命令脚本提供 session id、turn id、cwd 和事件类型。生成建议配置：

```bash
harness observe hook-config codex
```

将输出的 matcher groups 合并进 `~/.codex/hooks.json` 后，在 Codex 中使用 `/hooks` 审查并信任它。配置覆盖：

- `SessionStart` → session active
- `UserPromptSubmit` → turn in progress
- `Stop` → turn completed / waiting
- `SessionEnd` → session ended

适配器只在 Hook 的 cwd 已注入 Harness 时记录，并优先把 lifecycle 事件提交到常驻服务。它不会保存 prompt、assistant message、transcript path 或 model；Hook 失败也是 advisory，不会阻塞 Codex 工作。

## 隐私与安全边界

Observer 默认只保存项目相对路径、结构化目标/摘要、角色、决策、交接、退出码和内容 digest。产物正文按需从项目原文件读取，不复制进事件账本。Harness CLI activity 只增加一级命令名、状态和退出码；启用 Codex Hook 后额外保存 session/turn 标识、平台、状态和时间。它不采集命令参数、命令输出、Prompt、聊天全文、assistant message、transcript、model、密钥、环境变量或完整日志，也不会自动读取 Brain 私有内容。

结构化事件写入使用 `POST /api/v1/events` 和本机 Bearer token；工作台受控操作使用页面会话 action token。项目移除只接受 `POST /api/projects/<id>/unregister` + `{ "confirmed": true }`，只处理 registry 中的 invalid 项目。所有 `PUT`、`PATCH`、`DELETE` 均返回 `405`。不要把本地端口通过代理暴露到公网。

## 恢复与排错

- `status` 提示没有 run：先执行 `harness observe init`。
- `init` / `sync` 返回 exit `2`：未找到可观察来源；先创建 `plan.md` 或 `docs/STATE*.md`。
- snapshot 缺失或怀疑不一致：执行 `harness observe replay`，它会从事件账本确定性重建。
- 服务不可达：先运行 `harness observe service status`，再查看 `harness observe service logs`；可用 `service restart` 恢复。
- plist 存在但 `loaded=false`：运行 `harness observe service start` 重新挂载现有配置；如果发生在 install/update 后，保留命令错误中的主失败和 rollback 结果用于诊断。
- Agent 事件显示为 `local-fallback`：表示当时接收服务不可达或仍是旧版；事件已经写入项目账本，服务恢复扫描后会出现在工作台。
- 端口占用：后台产品端口固定为 `6425`；先释放冲突，或重新执行 `service install --port N` 明确迁移。
- 从旧版迁移：`4317` 是 OpenTelemetry OTLP/gRPC 的登记端口；新版默认迁移到 `6425`，旧书签请改为 `http://127.0.0.1:6425/`。
- 想完全移除观察数据：停止 `watch` 后删除该项目的 `.harness-runtime/`。这不会影响 Harness 原始工作流文件。

## 当前不做什么

- 不生成或启动多 Agent
- 不做 Agent 间消息路由、租约或抢占
- 不自动推进阶段、修改任务状态或解决阻塞
- 不执行审批和高风险动作
- 不提供跨机器控制面或远程共享服务
- 不自动修改或信任 Agent 软件的 Hook 配置
- 不把工作台变成任意文件系统浏览器，不展示未登记的项目文件
- 不通过工作台创建、切换、合并、删除 Git 分支，不打 Tag 或 push
- 不把角色包装成独立模拟经营系统；角色视图只展示真实工作轮次和交接
- 不根据聊天全文猜测需求、目标或角色状态

只有在 V0 的事件语义、幂等导入、验证状态和恢复路径稳定后，V1 才适合增加显式批准下的调度能力。即使进入 V1，事件账本仍应是可审计的事实源，Dashboard 的写操作也必须经过权限与审批边界。
