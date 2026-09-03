# 更新日志

语言：[English](CHANGELOG.md) | 简体中文

Mick Agent Harness 的重要变更都会记录在本文件中。

本项目遵循 Semantic Versioning 2.0。形如 `vX.Y.Z` 的 Git tag 是最终发布事实源。

## [0.22.1] - 2026-09-03

### 更新后运行进程重载修复

- `harness update` 现在比较 pull 前后的安装提交、取得发布标签，并且只在确实安装了
  新提交时重载唯一的 6425 Observer。
- 没有新提交时继续复用健康服务进程，保持既有幂等安装行为，不制造无意义重启。

兼容性：无需迁移项目、Agent、Brain、事件或工作台数据；本补丁只修正更新后的服务生命周期。

## [0.22.0] - 2026-09-03

### 统一诊断与维护需求收口

- **一条确定性 Doctor**：`harness doctor [--json] [project]` 聚合安装、项目注入、
  Code Agent、可选 Brain、唯一的本地 Observer 和 Plan audit，不复制各子系统的业务逻辑；
  每个失败项都给出固定、可审查的下一步。
- **Adapter Registry v2**：每个已知 Agent 分别声明支持、规则加载、Skill、Hook 和修复能力。
  CLI 与工作台读取同一合同；静态文件存在仍不会被当成运行时加载证明。
- **隔离 Brain fixture**：覆盖已配置写入、未启用不写入、Claude Hook 幂等、只生成提案的
  规则演进和项目本地回退。无 Brain 时的回退现在读取当前项目日志，不再误读 Harness 仓库日志。
- **唯一需求源**：首次使用压缩为安装、项目 init、Doctor；README 和 TODO 的失真待办被关闭，
  v0.19 历史验收状态按已有证据修正，`docs/VERSIONS.md` 保持为唯一产品需求源。

兼容性：v0.21 项目、Agent Loader、Hook 文件、Brain 模式、事件账本和唯一的
`127.0.0.1:6425` 服务继续兼容。Registry v2 是本版本内部合同，不需要迁移项目。

迁移说明：运行 `harness update`，再运行 `harness doctor`；只执行它针对当前机器实际状态
给出的修复命令。Brain 继续保持可选。

验证：204 个 unittest、生成规则一致性、全部 Shell/Python/JSON 语法检查、临时干净 HOME
安装路径、真实 6425 健康对照，以及浏览器验证的 7 Agent 适配页面；无横向溢出，控制台
0 条错误或警告。

## [0.21.0] - 2026-08-30

### 轻量执行、统一命令与真实项目活动

- **自适应执行模式**：`auto`、`quick`、`standard`、`e2e` 默认选择足以证明结果的
  最轻流程。Quick 不创建 Plan 或角色仪式；E2E 第一轮确认意图，并止于发布候选。
- **跨 Agent 通用入口**：`harness plan`、`goal`、`brain`、`e2e` 共用确定性 CLI
  合同和薄 Agent Skill，不覆盖 Codex 已有的 `/plan`、`/goal`。
- **明确的 Brain 三态**：用户可以选择暂不启用、仅本机或私有远端；没有远端不会
  被显示成同步失败，并完整保留 v0.20.2 的通用 `~/.brain` 默认值。
- **受预算约束的常驻上下文**：详细角色流程改为按需加载 Skill；Kernel 的安全、验证
  和升级规则继续常驻，并由字节与近似 Token 预算自动检查。
- **执行透明度**：结构化事件记录有效模式、选择与升级原因、待用户决策、轮次耗时、
  Agent 回合和 Harness 命令。宿主没有提供通用工具调用计数时显示“未记录”，不从对话猜测。
- **统一项目身份**：登记项目可以把唯一浅层子 Git 仓库作为代码工作区；唯一匹配的
  ChatGPT/Codex 镜像活动归入同一个项目。提交和回合只证明真实活动，不伪造需求或完成状态。

兼容性：v0.20 项目、事件账本、Agent Loader、Brain 模式和唯一的
`127.0.0.1:6425` 服务继续兼容。多个子仓库或重名镜像不会被自动关联。

迁移说明：运行 `harness update`，刷新全局安装、登记项目、Agent 适配、命令 Skill
和 Observer 服务。

验证：195 个 unittest、生成规则一致性、Shell/Python/JSON 语法、上下文预算与公开
发布审计、非交互临时安装，以及覆盖嵌套 Git、Agent 镜像、响应式宽度和控制台状态的
真实浏览器路径。

## [0.20.2] - 2026-08-24

### 通用 Brain 默认值与公开发布隐私

- 新安装使用通用私有记忆目录 `~/.brain`。升级时若新目录不存在，会继续发现旧目录，
  不自动搬移或删除记忆。
- 公开配置不再携带维护者的 Brain 远端或已跟踪 owner 文件。Brain 身份只从用户自己的
  私有 Brain 仓库推导；纯本地 Brain 使用本机用户。
- owner 不一致时默认保留私有记忆；只有用户显式传入 `--fresh` 才执行破坏性重置。
- 生成的 Agent Loader 只引用私有 Capsule 来源，不复制其正文，也不再内置维护者画像。
- 新增可重复运行的公开发布审计，阻止个人路径、身份、项目名、Brain 远端、兼容代码外
  的旧默认名和疑似凭据进入发布包。

兼容性：不会自动迁移数据。已有旧 Brain 继续可读，显式自定义路径和私有 Git 远端继续
生效；新安装创建 `~/.brain`。

迁移说明：运行 `harness update`。需要多机同步时，可在
`config/.brain-config.yaml` 配置用户自己的私有 Brain 远端；纯本地使用不需要远端。

验证：150 个 unittest、生成规则一致性、全部 Shell 语法、首次安装与旧目录升级冒烟、
公开发布审计和 `git diff --check`。

## [0.20.1] - 2026-08-24

### 项目首页选择恢复补丁

- 项目首页刷新时保留通过 `task` URL 参数选中的当前版本需求。首页现在使用当前版本
  的需求 ID 校验选择，不再错误地拿旧 Plan task 表否定需求 ID。
- 首页没有有效需求选择时，优先选择当前版本中进行中或阻塞的需求，再回落到第一条
  需求；不会把无关的活跃 Plan 步骤写进需求 URL。

兼容性：无需迁移 schema、事件、Loader 或项目文件。运行 `harness update` 刷新工作台
和 6425 Observer 服务即可。

验证：142 个 unittest、生成规则和 diff 检查，以及安装版 6425 上的真实浏览器选择、
刷新、角色详情范围、桌面宽度和控制台验收。

## [0.20.0] - 2026-08-24

### 需求级产品门禁与任务办公室

- **确定性的逐需求流程**：v0.20 的每条需求独立经过
  `PM → 产品审查 → 开发 → QA → 待发布`。版本级 Plan、自由文本交接或其他需求的
  角色活动，都不能再推进当前需求。
- **开发前产品审查**：Reviewer 新增明确的 `product_review` 模式，并配套内置
  `product-logic-review` Skill；在开发前检查用户路径、状态变化、权限、时序、失败
  恢复和边界情况，只能输出明确的批准或退回结论。
- **以证据推进的交付门禁**：开发交付必须引用实现产物和自验证据；QA 必须独立记录
  通过或失败证据。高风险工作可以在 QA 后增加独立的 `release_review`；范围严格的
  纯技术修复使用可审计例外，而不是静默绕过流程。
- **任务级角色办公室**：当前版本的每条需求都显示自己的 PM、Review、开发、测试和
  待发布路径；选中需求后在卡片内展开动画角色办公室。角色历史、决策和产物只读取
  当前需求，Designer 仅在真实参与时插入。
- **忠于事实的兼容投影**：旧事件继续可读，但不会被补造审批。非法角色跳转和计划/
  状态冲突会保留审计并在工作台解释，但不能推进有效需求阶段。

兼容性：已有项目、v0.19 事件账本、Agent Loader、Brain 仓库和
`127.0.0.1:6425` 地址继续兼容。运行事件合同只增加可选字段，没有新增第三方依赖。

迁移说明：运行 `harness update`，刷新全局 Harness、已登记项目挂载、Agent Loader
和唯一的 6425 Observer 服务。历史事件继续展示；新的产品门禁适用于 v0.20.0 及
后续版本规划的需求。

验证：141 个 unittest、生成规则一致性、Python/JavaScript/Shell/JSON 语法、Skill
校验、`git diff --check`、临时项目非交互安装冒烟，以及 6246 开发服务上的真实桌面/
窄屏浏览器验收；已验证需求切换、范围内角色抽屉、页面无溢出且控制台无错误或警告。

## [0.19.0] - 2026-08-22

### 受控操作、Skill 治理与 Harness 进化

- **可操作的项目工作台**：首页只开放经过审计的 Harness 更新、项目注入/升级和
  Agent 修复操作。所有写操作都经过预览、显式确认、幂等复用、单任务互斥、固定
  参数、恢复状态与脱敏审计，不提供任意命令入口。
- **可靠的本机全局 Observer**：服务安装会复用配置一致且健康的进程；替换失败时
  恢复旧服务。项目登记与前台/后台扫描共享同一份项目集合，失联项目可从工作台
  移除，但不会删除项目文件。
- **外部 Skill 治理**：工作台发现内置、个人、Agent 和项目 Skill，扫描过程中不
  执行其中脚本；安装或适配前展示角色、Hook、完成契约、Loader 与危险指令冲突，
  由用户决定采用方式。
- **需求指挥台**：项目首页优先展示当前版本需求；每条需求显示真实角色路径、当前
  工作、独立 QA 范围、验证证据、阻塞与下一步。已完成需求不再残留当前负责人或
  过期的角色流转建议。
- **互动角色办公室**：PM、设计、开发、测试和 Review 使用紧凑的软糖角色场景，
  并展示真实参与历史。QA 是明确的质量门禁；Reviewer 审查声明的产物和验证证据，
  不替代测试。
- **项目问题回流 Harness**：用户可把选定项目记忆提交为 Rule、Skill、Checker 或
  Profile 改进。单项目信号默认停留在观察层；跨项目/高频信号或用户明确送审后才
  进入审批。批准只生成可审计提案，绝不自动改写中央 Harness 规则。

兼容性：已有项目、Loader、事件账本、Brain 仓库和 `127.0.0.1:6425` 地址继续兼容，
没有新增第三方依赖。本地写接口继续使用 action token，并新增操作请求体大小限制和
Harness 改进状态写锁。

迁移说明：安装本版本后运行 `harness update`。它会刷新全局 Harness、已登记项目挂载、
Agent Loader 和唯一的 6425 Observer 服务；不会删除项目源码或 Brain 记录。

验证：129 个 unittest、生成规则一致性、Python/JavaScript 语法、`git diff --check`、
v0.19 六项需求的独立 QA，以及 6246 开发服务的真实浏览器验收；页面显示 6/6，且
已完成需求不再残留错误流转。

## [0.18.0] - 2026-08-19

### Brain 记忆工作台与受控同步

- **确定性的项目记忆**：Claude、Codex 与通用 Harness 客户端产生的已完成、已接受、
  已验证结构化事件会经过脱敏和去重后自动写入本地，不再依赖 SessionEnd；会话采集
  只保留为默认关闭的可选补漏路径。
- **两条明确的记忆流水线**：项目事实免审批写入本地，并可纠正、撤销、合并或提升；
  跨项目偏好与版本化 Profile 继续作为可见候选，由用户编辑、换层、合并、忽略、
  批准、拒绝或重试。
- **可检查的同步过程**：任何 push 之前，工作台展示实际仓库、分支与上游、分组记录、
  写入目标、受管文件、全部领先提交和明确排除项。仓库不一致、远端分叉或存在无关
  已暂存文件时禁止确认；真正执行时再次核对边界，避免预览后状态变化。
- **工作台信息架构**：围绕同一个本机全局服务重构项目导航、Brain 设置、版本倒序和
  Git 可视化。同一仓库可展示多个已检出 worktree 和工作分支，但不会把每条分支
  虚构成活跃 Agent。
- **人类 PRD 与低成本验证**：`prd-for-humans` 通过版本化 Profile 和技术污染检查，
  与 AI 技术交付合同保持隔离；`fast / subsystem / release` 三档验证只有在代码、
  环境和命令指纹完全一致时才复用成功 Gate。

兼容性：已有 Harness 项目、事件账本、Loader、Hook 与 Brain 仓库继续有效；没有新增
依赖。工作台新增经过认证的 localhost 操作接口，但 Brain 远端同步仍必须先生成清单，
再由用户显式确认。

验证：98 个 unittest、生成规则一致性、Shell 语法、`git diff --check`、非交互首次
安装 smoke test，以及真实浏览器工作台路径和无错误控制台。

## [0.17.0] - 2026-08-13

### 可靠 Agent 接入与精简角色契约

- **五层 Agent 诊断**：版本化注册表发现 Claude Code、Codex、Cursor、Windsurf、
  Cline、Roo Code 和 Trae，同时不夸大生命周期支持；工作台分开显示发现、注入、
  加载、执行遵循和回写状态。
- **安全 Loader 与 Hook 管理**：`harness agents doctor|sync|migrate|hooks` 提供
  dry-run、marker 冲突检查、原子替换、备份和幂等 Claude/Codex 生命周期配置；
  Loader 存在不再被当作真实会话已加载或已遵守的证据。
- **可恢复结构化回写**：带版本的事件在提交前先进入持久化队列；服务恢复后幂等
  重放，并拒绝 Prompt、transcript、密钥和环境变量正文。
- **精简角色契约**：PM、Planner、Executor、QA、Reviewer、可选 Designer 和编排
  协议使用小型、项目无关的职责合同；共享交付机制集中在编排层，Reviewer 可以做
  最小证据验证但不接管 QA。
- **经过审计的设计方法**：Designer 只在真实设计任务中按需加载内置
  `designer-craft`；固定版本的开源项目只是审计输入，不是运行依赖或另一套权限系统。
- **Private Brain 边界**：可复用经验先成为脱敏、去重候选；项目账本只暴露元数据，
  实际写入 Brain 必须显式确认。

兼容性：已有项目挂载与运行账本继续有效。Claude/Codex 全局 Loader 和生命周期
Hook 可独立迁移；Codex CLI 命令 Hook 运行前必须在 `/hooks` 中完成审查与信任。

验证：71 个 unittest、Shell/Python/JSON/JavaScript 和生成规则检查、原子迁移与故障
注入、真实 `127.0.0.1:6425` 项目/Agent API、Markdown 与折叠代码阅读器，以及无错误
的浏览器控制台。

发布证据：真实 Codex 会话完成四状态生命周期闭环，Reviewer 行为样本得到 10/10。
Claude Code 保留已验证的 Loader 与部分会话证据，但用户在最终样本前退出账号，因此
turn 闭环与行为评测明确保持“未验证”。

## [0.16.0] - 2026-08-12

### 结构化产物阶段导航

- **可追踪阶段标题**（`rules/core.md`）：持续演进的 Markdown 统一使用
  `## vX.Y.Z · YYYY-MM-DD · 阶段标题`。版本只能来自 `docs/VERSIONS.md`，日期是
  实际沟通/决策日期，两者都禁止编造。
- **确定性解析器**（`scripts/harness-observe.py`）：新增 `parse_markdown_stages()`，
  只读取 H2–H4 标题——正文和代码块里的日期不会生成阶段入口。旧格式标题（圆括号
  或破折号日期）保留全部日期、可导航，但标记 `traceable=false` 并显示"未标版本"，
  不做版本推断。
- **工作台**：产物页用阶段导航替换旧的版本/日期事件筛选，点击阶段直接定位当前
  文档对应标题；代码产物保留可折叠行号阅读器，不显示 Markdown 阶段。

兼容性：产物 API 新增向后兼容的 `stages` 字段；旧 `artifact_mode` /
`artifact_scope` URL 参数被忽略并在下次状态写回时移除。无新依赖，无新写接口。

验证：43 个 unittest、Shell/Python/JSON/JavaScript 语法、`generate.sh --check`、
`git diff --check`、Harness Audit 8 PASS / 0 FAIL，真实示例移动端项目解析出 38 个
阶段并保留多日期旧标题。

## [0.15.0] - 2026-08-12

### 产物版本与日期记录

- 产物元数据聚合同一路径的**每一次工作回合引用**（`records`、`versions`、
  `dates`），不再因路径去重丢失交付上下文。
- 产物页展示每条记录的目标、结果、角色、日期以及关联需求的关键决策；Markdown
  阅读器新增标题目录，可在文档内跳转。
- **交付后修正**：版本/日期导航只作用于当前选中文件的阶段记录——左侧文件列表
  不再被筛选，页面明确提示当前读取的是现有文件而非历史快照。

验证：42 个 unittest、Harness Audit 8 PASS / 0 WARN / 0 FAIL、安装版与源码
校验一致、Observer `/healthz` 正常。

## [0.14.0] - 2026-08-12

### 角色办公室与目标分层

- **三层目标**：稳定项目目标写入 `docs/PROJECT.md`（新建，PM 维护），版本目标
  仍在 `docs/VERSIONS.md`，plan 阶段目标不再被误标为总体目标。
- **五角色办公室**：项目首页固定展示 PM / 设计 / 开发 / 测试 / Review，状态
  （active / waiting / completed / idle）只来自真实 `work.round_*` 与
  `handoff.created` 事件；Planner 与 Orchestrator 归入 PM 组。
- **真实 vs 建议流转**：明确交接与 `next_role` 建议以不同样式展示；版本交付后
  显示"本版本已交付，等待 PM 定义下一版本"，不再笼统显示"当前需求尚未确定"。
- 角色详情页合并需求上下文、执行摘要、交付物、关联决策和历史工作；首页四个
  重复模块已移除。

验证：40 个 unittest、Harness Audit 8 PASS / 0 WARN / 0 FAIL，真实 workspace
API 返回稳定项目目标、五角色和真实的 `Reviewer → PM` 建议流转。

## [0.13.0] - 2026-08-12

### 从规则注入工具到本地工作服务器 + 统一工作台

- **Observer V0**：项目内 append-only 事件账本（`.harness-runtime/`）、
  plan/STATE 采集器、确定性 snapshot 重放和 localhost 只读看板——只观察，
  不做编排。
- **跨项目总览**：`harness observe watch --all` 聚合全部已注册项目，明确
  valid / invalid / missing 状态；project id 只通过 Harness registry 解析。
- **常驻服务**：launchd 代理（`com.mick.harness.observer`）在 `127.0.0.1:6425`
  保活定时扫描；`harness observe service install|start|stop|restart|status|logs|
  uninstall` 管理生命周期。
- **需求导航**：项目默认页展示总体目标、Plan 拆出的需求和 `定义 → 实现 → 验证 →
  交付` 四个节点；原始事件退到"技术记录"。
- **工作服务器接收**：唯一写接口 `POST /api/v1/events`（Bearer token、registry
  范围、幂等）接收 `work.round_started / work.round_completed / decision.recorded /
  handoff.created`；Agent 与 CLI 在服务不可达时回退项目本地账本，且不改变原命令
  退出码。Prompt、聊天全文、命令参数和密钥永不落盘。
- **产物阅读 + PM 版本工作台**：已授权 Markdown/代码产物在看板内阅读（安全 DOM、
  512 KiB 文本上限、拒绝路径越界/越界 symlink/二进制）；`docs/VERSIONS.md` 成为
  PM 维护的版本计划，与只读 Git 分支/标签/HEAD/dirty 事实对照展示。
- **Codex Hook**（`scripts/harness-observe-hook.py`）：生命周期事件脱敏为
  session/turn 状态、项目 id 和时间；Hook 配置只输出供审查，不自动安装。

迁移说明：看板端口从 `4317` 迁移到 **`127.0.0.1:6425`**；执行一次
`harness observe service install` 即可让 Observer 跨终端保活。事件账本、HTTP GET
路由和 CLI 保持向后兼容。

验证：冻结时 37 个 unittest、两个临时项目完成接收 → 聚合 → 刷新 → 重启恢复
端到端检查、LaunchAgent 健康检查、安装版与源码校验一致。

## [0.12.0] - 2026-07-16

### Kernel 强化 (`rules/core.md`) —— 反驳表和验证 Gate

- **铁律 5（撞墙熔断） —— 新增"撞墙合理化反驳表"**：6 行常见自我合理化话术
  （"再试一次就好了" / "这次的原因不一样" / "改这里应该就行"）配上必须触发的
  行为。想到左栏 = 已经在撞墙，直接进 Debug Card，不再靠感觉再试一次。灵感来自
  superpowers 的 "Common Rationalizations" 模式，本地化到中文 Executor 会话中
  真实出现的失败姿势。
- **铁律 7（完成必须验证） —— 新增"验证 Gate"（5 步）**：`识别 → 执行 →
  读取 → 核验 → 才能说"完成"`。跳过任一步 = 说谎，不是效率。明确点名"靠记忆
  代替真实执行"这种最常见的假验证。
- **铁律 7 —— 新增"完成话术反驳表"**：7 行禁止话术（"应该好了" / "配置好了" /
  "只是警告不影响" / "Subagent 报告 success"）配上现实（独立验证、证据优先于
  声明）。
- **铁律 7 —— 新增"Claim / Requires / Not Sufficient 表"**：10 行映射声明类型
  （测试通过 / 构建成功 / Bug 已修 / 配置生效 / UI 可用 / 部署上线 / 需求达成）
  到它的真实证据和常见假证据。把"什么算证明"变成具体的判定标准，不再是空泛
  提醒。

### Playbook 增补 (`rules/extended.md`)

- **§3.4 Interaction QA —— 新增"UI 完成话术反驳表"**：6 行针对 UI 特有的失败
  姿势（"按钮已加上了" / "开关切换正常" / "本地测通了"），不能被通用验证话术
  覆盖的场景。和现有的五要素 checklist 互补。

### SessionStart Hook（`hooks/session-start.sh` + `scripts/hook-adapters.sh`）

- **新增 Claude Code SessionStart hook**：在 `startup|clear|compact` 事件触发，
  把 Tripwire + Self-Test 触发条件 + 回合卡片格式作为
  `hookSpecificOutput.additionalContext` 注入。解决了"AGENTS.md 不一定被每个
  工具打开时读到"这个之前只靠约定的痛点。
- **非 Harness 项目静默 no-op**：向上 8 层父目录查找 `.harness/`、`AGENTS.md`、
  `CLAUDE.md` 标记，找不到就 exit 0 不输出 JSON。不会污染无关项目的会话上下文。
- **`hook-adapters.sh` 扩展**：新增 `install_claude_code_session_start_hook()`、
  `claude_session_start_status()`、`iter_claude_session_start_commands()`。
  `harness brain install` 现在同时挂载 SessionEnd（brain-sync）和 SessionStart
  （Tripwire 注入）两个 hook。
- **修复（SessionEnd 状态检测）**：`iter_claude_hook_commands()` 和新增的
  SessionStart iterator 都从 `python3 <<PY "$file"` 改成 `python3 - "$file" <<PY`。
  旧写法会让 python3 把路径当脚本文件打开（不是 argv[1]），静默吞掉解析，
  导致 `harness brain status` 一直误报 SessionEnd 为 "missing"，即使 hook
  实际已经装了。

### 兼容性

- 完全向后兼容。所有规则新增都是新增子句；表格只在触发条件出现时才会体现
  （撞墙 / 完成话术 / UI QA）。
- SessionStart hook 通过 `harness brain install` 选装（已由
  `config/.brain-config.yaml` 里的 `hooks.claude_code.enabled` 控制）。
- 修复的 SessionEnd 检测可能让 `harness brain status` 从"missing"变成
  "installed"，仅针对之前装了 hook 但状态一直没被识别的用户 —— 这是修 bug，
  不是行为变化。

### 验证

- `hooks/session-start.sh` 在三个 CWD 测过：harness 项目 → 合法 JSON、
  home 目录（有 CLAUDE.md）→ 合法 JSON、`/tmp` → 静默 exit 0。
- `harness brain status` 安装后正确显示
  `Claude Code : enabled (SessionEnd: installed, SessionStart: installed)`。
  两个 entry 在 `~/.claude/settings.json` 中确认。
- `./generate.sh --check` 通过；`dist/AGENTS.md` 已重新生成，包含新表格。

## [0.11.0] - 2026-07-06

### Kernel 强化 (`rules/core.md`)

- **铁律 1** 改名 "先读后改" → **"先读后改，新建前先查复用"**——新建函数/接口/服务/UI
  组件前，Executor 必须先 grep 项目里是否已有类似能力。默认复用，新建需要举证说明为
  什么不复用（把举证责任反过来）。
- **铁律 5** (Anti-Wall Debug Card) 收尾必问一句：**"这类问题能不能变成自动检查？"**
  ——三分支落地：能 → `verify.d/` checker；不能自动判定但有明确规则 → Rule；都不行 →
  brain-push 成 gotcha。禁止修完就走。
- **铁律 7** (完成必须验证) 新增 **Baseline First** 纪律 + `.harness/verify.sh`
  契约入口——verify / debug / 回归类任务动手前先跑一次留基线，改完做 diff。
  「不是我引入的 / 是历史遗留 / 只是警告不影响」不再能用嘴解释。

### Playbook 扩充 (`rules/extended.md`)

- **§3.1 Anti-Wall Debug Controller** 新增两条纪律：*Baseline First*（报告 diff
  代替嘴解释）+ *修复后必问自动化*（禁止修完就走）。
- **§10.3 Executor 自检 ritual** 从 5 步扩到 7 步——新增「动手前 grep 复用可能」
  和「verify 类步骤先留 baseline」。这两步专门拦 Executor 最常见的两种翻车方式：
  重复造轮子，以及把老问题当挡箭牌。

### Skills 层 (`rules/skills/`)

- **在 Kernel 和 Playbook 之间新增第三层**——Skill 是高频固定动作（编译、测试、
  事后验证、发布、签名）的可复用剧本，不允许 AI 每次临场发挥。Rule 说"必须做"，
  Skill 说"具体怎么做"。
- **Harness 只提供框架，不提供内容**：`rules/skills/README.md`（定位、何时写、
  如何被引用、进化含删除）+ `rules/skills/_template.md`（frontmatter + 6 段必备
  结构）。具体 Skill（编译什么、测试什么）由项目自己长——技术栈差异太大，硬塞
  会变成噪音。
- 三种引用机制：Rule 引用 Skill / plan 步骤调用 Skill / 角色契约强制 Skill。
- Skills 与 Rules 走同一条进化含删除闭环——半年 review 一次，长期未触发的退役。

### Verify 契约 (`docs/VERIFY-CONTRACT.md`)

- 形式化 `.harness/verify.sh` (orchestrator) + `.harness/verify.d/*.sh`
  （可插拔 checker）+ `.harness/verify.disabled/`（退役）架构。一条检查一个文件，
  加/删检查 = 加/删文件，orchestrator 不做业务判断。
- Checker 命名规范 `NN-<category>-<what>.sh`；退出码 0 通过 / 1 失败 / 2 无法判定 /
  77 跳过；支持 `--profile`、`--changed`、`--only`、`--skip` 参数。
- **显式接入 §10.9 自进化闭环**——checker 从真实 Debug Card 长出来（修复 →
  "能不能变成自动检查？" → `verify.d/NN-xxx.sh`），长期未触发的每半年退役到
  `verify.disabled/`。同时避免臃肿和漏检两种退化。
- 项目分层起步建议：个人项目 3 条 / 中型 10-15 条 / 大型 20+ 按 profile 分片。

### 兼容性

- 完全向后兼容，全部为增量能力。
- 使用铁律 1/5/7 的现有项目继续正常工作；新增内容只在对应触发条件出现时（新建代码 /
  Debug Card / verify 任务）才浮现。
- Skills 层和 verify.d/ 均为可选启用——未采用的项目行为与之前完全一致。

### 验证证据

- `./generate.sh` 重新生成 dist/AGENTS.md；`--check` 通过。
- `bin/harness scripts/*.sh generate.sh` 的 `bash -n` 语法检查通过。
- Kernel 变更已同步到 dist/AGENTS.md（grep 验证）。

## [0.10.0] - 2026-07-06

### 产品

- 从 "Mick Harness Rules" 更名为 **Mick Agent Harness**——定位为个人 Agent 协作层，补充而非覆盖 Code Agent 的编码能力。
- README 重写为完整产品文档，覆盖安装 → 初始化 → 同步 → 验证 → Brain → 进化六阶段，新增英文版 (`README.en.md`)。
- 明确保证边界：Harness 是先验注入 + 后验检查 + 长期记忆 + 人工门禁的协作系统，不是魔法强制器。

### Brain 架构

- 引入 `ensure_brain_available`——Brain 不可用时不再阻断 `harness init`、`harness check` 或主 Harness 工作流，自动降级为本地私有 Brain。
- 新增 `init_brain_skeleton` 统一 Brain 目录骨架创建。
- 重构 Brain 解析逻辑：`BRAIN_REMOTE_STATUS` 独立追踪远程连接状态（connected / local / unavailable / none）。

### Hook Adapter

- 将工具专属 hook 逻辑提取到 `scripts/hook-adapters.sh`，命令入口保持 `harness brain install` 和 `harness brain status`。
- 在 `config/.brain-config.yaml` 中新增 adapter registry——Claude Code 默认启用，Codex 和通用 adapter 需主动开启。
- 新增 `scripts/brain-ingest.sh` 作为工具无关的 Brain 写入端点，支持 session 摘要、learning 和 failure 信号。

### 规则生成

- `generate.sh` 现在会跳过仅含占位文本的 Brain 源文件，不再注入空胶囊。
- 新增 `generated_file_matches` 和 `strip_capsule_block`，使 dist 漂移检测忽略无害的胶囊块差异。

### Harness 进化

- `harness-evolve.sh` 现在除 audit trail 外还聚合可选信号文件（`harness-failures.md`、`corrections.md`、`banned-patterns.md`）。
- 新增 9 个失败标签：`tripwire-missed`、`self-test-fake`、`fake-verification`、`plan-hijack`、`repeated-failure`、`under-asking`、`over-asking`、`executor-correction`、`banned-pattern`。

### 内部

- 安装和更新时对 `scripts/*.sh` 统一设置可执行权限。
- Brain commit fallback 改为写入私有 Brain 仓库而非 Harness 仓库。

## [0.9.1] - 2026-07-03

### 变更

- 将回合卡片细化为五个固定单句槽位：本回合、整体、下一步、状态、阻塞。
- 将推理深度并入“本回合”行，不再作为独立行输出。
- 将可选 SOS 表达替换为必出的阻塞行。
- 增加必出的上下文负载状态格式：无真实数据时使用预估区间和结构来源，有真实数据时使用精确百分比和分类分布。

### 说明

- 预估上下文状态使用格式：`上下文负载约 70-85%（长线程 + 多轮工具输出 + 多轮决策）`。
- 实测上下文状态使用格式：`上下文负载 72%（工具输出 38% / 对话 34% / 规则 18% / 文件 10%）`。
- 状态行只报告状态；需要执行的动作放到“下一步”行。

## [0.9.0] - 2026-07-03

### 状态

首个正式 Harness 版本的发版候选基线。

这个版本汇总了从 2026-03-30 初始 Vibe Coding 脚手架，到 2026-07-01 Mick Agent Kernel 的完整仓库历史，并包含当前尚未提交、发布前仍需确认的 Feature Inventory 知识改动。

### 新增

- 初始 Vibe Coding 脚手架，包括工程规则、TODO 状态、记忆文件、架构模板和 `vibe-init.sh`。
- PM、Designer、QA、Reviewer、Planner、Executor 和 Orchestration 角色文件。
- Git 工作流、Conventional Commits、SemVer、PR 要求、CI/CD 护栏和部署环境隔离。
- 三层 Brain 模型：session、project、global 记忆，以及 init、check、push、search、resolve、compound、migrate、gc 脚本。
- 公共 Harness 规则与私有 Brain 数据分离的双仓库模型。
- `setup.sh` 一步引导、交互式配置、双语 setup 提示和 `.harness-config.yaml` 生成。
- 单源规则生成器，以及面向不同 Agent 表面的 `minimal`、`lean`、`full` 输出 profile。
- Plan-Execute Protocol，包括项目根目录 `plan.md`、强/弱模型协作规则、Executor 护栏、Planner 契约和富 plan 模板。
- Harness Audit 扫描器和 Harness Evolve 提案流程，用于规则合规检查和规则演化反馈闭环。
- Harness Self-Test、Anti-Wall 调试纪律、Cross-System Preflight、Interaction QA、OD 输出限制和回合卡片交接协议。
- Mick Agent Capsule 注入和 Mick Agent Kernel，包括证据纪律、边界控制、完成验证和反馈分级处理。
- PM 需求设计改进：自适应 PRD 指导、需求层级、AI 评估章节、指标、数据源探针、异常与边界处理、分期交付追问。
- Feature Inventory 指导和 `docs/FEATURES.template.md`，用于维护用户可见能力地图。

### 变更

- README 从长篇实现指南调整为协调与治理入口。
- 规则从工具专属文件迁移到 `rules/core.md` 和 `rules/extended.md` 作为事实源。
- 生成的 Agent 文件迁移到 `dist/`；项目级文件由 `generate.sh` 生成，不再手动维护。
- PM 工作流从固定门禁调整为对话式意图探索和对抗式需求审查。
- `plan.md` 前置检查提升为 Rule 0，并从 Cursor 专属命名中解耦。
- `plan.md` 位置从 `.harness/plan.md` 移到项目根目录。
- Claude Code 中非原生模型的 profile 从 `minimal` 调整为 `lean`。
- Constitution/Brain 同步集成进生成规则输出。
- `.gitignore` 扩展为忽略生成或本地 Harness 产物，包括拟议的 `AGENTS.md`。

### 修复

- 防止 Harness 和 Brain 内容泄漏进目标项目 Git 历史。
- 恢复非交互 setup 配置生成，并修复未绑定 shell 变量问题。
- 修复 `brain-resolve.sh` 在 `set -u` 下的兼容性。
- 调整挂载行为：对已有项目文件注入受控 Harness 内容，而不是直接跳过。
- 修正生成 profile 路由和 plan 路径引用。
- 合并多项来自使用反馈的 PM 模板修复。

### 发布说明

- 这是首个正式发布候选。之前没有 Git tag，所以 `[0.9.0]` 是历史基线，不是相对某个已发布版本的增量 diff。
- 当前仓库状态为 `73705fd-dirty`；发布打 tag 前，需要先确认当前 Feature Inventory 改动是纳入还是排除。
- 打 tag 前必须执行 `docs/RELEASE_CHECKLIST.md` 中的发版检查。

## 历史追溯

### 2026-03-30 至 2026-03-31：Vibe Coding 与 Agent 角色

- 初始化脚手架，包含核心工程规则、记忆/TODO 文件和初始化脚本。
- 增加 PM 与 Designer 工作流。
- 增加 Reviewer 和逻辑审计角色支持。

### 2026-04-09 至 2026-04-22：工作流、Brain 与仓库模型

- 增加 Git、CI/CD、QA、编排和角色路由护栏。
- 构建初始 Brain 脚本和三层记忆模型。
- 增加 license，并收敛 README 定位。
- 增加隐私控制，避免 Harness/Brain 内容进入目标仓库。
- 引入 Goal Discovery，随后迁移到 Harness/Brain 双仓库模型。
- 增加 `setup.sh` 作为一步引导路径。

### 2026-06-03 至 2026-06-11：可配置 setup 与 Plan-Execute

- 增加状态驱动编排和交互式工作流配置。
- 增加双语 setup 与状态行可观测性。
- 将规则重构为单源生成体系。
- 增加多模型 profile、强/弱模型角色识别和 Solo mode。
- 增加 Plan-Execute 冲突解决、Executor 指导、Planner/Executor 契约和富 plan 模板。
- 修复 setup 和生成输出兼容问题。

### 2026-06-18 至 2026-06-25：审计、演化与治理

- 增加回合卡片导航、合规扫描和快速开箱体验。
- 增加由审计信号驱动的规则演化闭环。
- 将通用 PM PRD 结构与 Brain 中的个人风格拆分。

### 2026-06-28 至 2026-07-01：PM 细化与 Mick Agent Kernel

- 增加 Feedback Triage Protocol。
- 细化 PM 指导：PRD 边界、痛点挖掘、分期交付、规则说明、异常处理、指标、AI 评估和数据源探针。
- 明确 PM 与 Planner 的分支关系。
- 合并个人 Agent 质量门禁，并定义 Mick Agent Kernel。

### 2026-07-03：拟议发版治理

- 拟议正式版本管理：`VERSION`、`CHANGELOG.md`、发版流程和发版 checklist。
- 审阅当前未提交知识改动，并将 Feature Inventory 标记为适合在 owner 确认后纳入 `v0.9.0`。
