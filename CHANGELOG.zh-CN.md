# 更新日志

语言：[English](CHANGELOG.md) | 简体中文

Mick Agent Harness 的重要变更都会记录在本文件中。

本项目遵循 Semantic Versioning 2.0。形如 `vX.Y.Z` 的 Git tag 是最终发布事实源。

## [0.15.0] - 2026-08-12

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
`git diff --check`、Harness Audit 8 PASS / 0 FAIL，真实 RaliTennis 解析出 38 个
阶段并保留多日期旧标题。

## [0.14.0] - 2026-08-12

### 产物版本与日期记录

- 产物元数据聚合同一路径的**每一次工作回合引用**（`records`、`versions`、
  `dates`），不再因路径去重丢失交付上下文。
- 产物页展示每条记录的目标、结果、角色、日期以及关联需求的关键决策；Markdown
  阅读器新增标题目录，可在文档内跳转。
- **交付后修正**：版本/日期导航只作用于当前选中文件的阶段记录——左侧文件列表
  不再被筛选，页面明确提示当前读取的是现有文件而非历史快照。

验证：42 个 unittest、Harness Audit 8 PASS / 0 WARN / 0 FAIL、安装版与源码
校验一致、Observer `/healthz` 正常。

## [0.13.0] - 2026-08-12

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

## [0.12.0] - 2026-08-12

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
