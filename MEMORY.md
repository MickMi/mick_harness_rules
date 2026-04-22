# 项目记忆与经验库 (Memory & Learnings)

## 🏗️ 架构决策记录 (ADR)
*在这里记录我们在对话中决定引入的新库、核心数据结构变更或重大架构妥协。*

- [2026-03-30] 初始状态：确立 Vibe Coding 护栏机制。
- [2026-04-09] ADR-001: 引入三层记忆模型（参考 three-layer-memory-skill 项目）
  - Session 层：每次对话的原始摘要（`sessions/YYYY-MM-DD/`），保留 90 天
  - Project 层：项目专属上下文与决策（`projects/<slug>/`），保留项目存续期
  - Global 层：跨项目通用偏好与经验（`global/`），永久保留
  - 蒸馏流程：Session → Daily Compound → Project → Weekly Compound → Global
- [2026-04-09] ~~ADR-002: 确立"个人基础设施层"双仓库模型~~ → **已被 ADR-007 取代**
- [2026-04-14] ADR-007: 确立"单仓库双职能"模型（取代 ADR-002）
  - **Harness Rules**（工程护栏）= "怎么做" + **Git Brain**（个人记忆）= "知道什么" → **合并为同一仓库**
  - Brain 以 `brain/` 子目录形式存在于 harness 仓库中（`brain/global/`、`brain/projects/`、`brain/sessions/`）
  - 整个仓库以 `.env` 模式挂载到项目中（`.gitignore` 隔离，不对外公开）
  - 统一版本管理，独立于任何业务项目的发布节奏
  - 变更原因：避免双仓库同步复杂度，harness + brain 本质上服务同一目标
- [2026-04-09] ADR-003: 确立 `brain init` 一键加载 + 验证闭环流程
  - 加载（Load）→ 注入（Inject）→ 激活（Activate）→ 验证（Verify）
  - 验证闭环是核心：防止"加载了脚手架但没真正起作用"
  - `brain check` 自动检查：.cursorrules 非空、pre-commit 已挂载、.gitignore 包含隔离项等
- [2026-04-09] ADR-004: 全局记忆只放"采控记录"（跨项目通用的个人偏好和经验）
  - ✅ 放：编码风格偏好、通用工具链选择、跨项目踩坑记录
  - ❌ 不放：项目特有的技术选型、数据库配置、API 前缀等
- [2026-04-09] ADR-005: 检索优先原则（Search-First）
  - 禁止全量读取 MEMORY.md 或 memory/ 目录
  - 优先用 ripgrep 搜索 → 定向片段获取 → 最后才全量读取
  - 当记忆文件增长后，全量读取会浪费大量 context window
- [2026-04-14] ADR-006: 多平台写入策略
  - IDE 内 AI（Cursor/Trae/Windsurf）：AI 直接通过 shell 命令写入
  - Web AI（Claude/ChatGPT）：通过 `brain push` CLI 手动/半自动提交
  - API 调用：对话结束后触发 Webhook 写入
- [2026-04-14] ADR-008: vibe-init.sh 改造为双模式（harness 加载 + inline 兼容）
  - 默认模式：从 harness 仓库 copy 模板文件到目标项目（单一数据源，不再维护内联副本）
  - `--inline` 模式：保留旧的内联生成方式，作为向后兼容
  - 串行链式调用：vibe-init.sh 执行完毕后自动调用 brain-init.sh 挂载 brain
  - 幂等安全：已存在的文件备份为 .bak，symlink 文件不覆盖
- [2026-04-14] ADR-009: 智能蒸馏策略（brain-compound.sh）
  - 智能触发：Session 层 ≥5 条未蒸馏条目触发 daily，Project 层本周 ≥3 条新增触发 weekly
  - 相似检测：基于关键词重叠度（≥3 个共享关键词）判断条目相似性
  - 合并策略：相似条目追加为子项（merged），非相似条目直接 append
  - 分类路由：基于关键词启发式分类（gotcha 关键词 → gotchas.md，preference 关键词 → preferences.md）
  - 蒸馏报告：每次 daily compound 生成 .compound-report 文件，记录路由决策
  - 支持 --dry-run 预览模式
- [2026-04-14] ADR-010: 多平台 IDE 自动写入规则（P4-多平台适配）
  - 通用规则模板：`brain-rules-template.md`，IDE 无关的 Prompt 指令
  - 触发条件：gotcha/decision/preference/env 四类事件自动触发 brain push
  - 去重机制：写入前先 brain-search 检查是否已存在相似条目
  - 多 IDE 注入：brain-init.sh 自动检测 Cursor/Windsurf/Trae/Copilot 并注入规则
  - .cursorrules 已内置完整的 Brain Auto-Write Protocol 段落
- [2026-04-14] ADR-011: 记忆容量治理（P4-brain-gc.sh）
  - Session 归档：超过 TTL（默认 90 天）的 Session 移至 `.archive/sessions/`
  - 归档前检查：未蒸馏的 Session 会发出警告，建议先运行 brain-compound.sh
  - MEMORY.md 长度控制：超过阈值（默认 500 行）自动归档旧条目到 MEMORY.archive.md
  - 容量报告：`brain-gc.sh --report` 输出各层文件数、大小、过期状态
  - brain-check.sh 新增 Check 8（MEMORY.md 容量）和 Check 9（自动写入规则检测）
- [2026-04-14] ADR-012: 强制需求审查协议（Mandatory Requirement Review Protocol）
  - 触发条件：新功能开发、系统重构、架构变更、多模块联动修改
  - 豁免条件：单文件 Bug 修复、文档更新、格式化、用户明确说"跳过审查"
  - 三轮递进式追问：第 1 轮（目标与边界）→ 第 2 轮（技术约束与风险）→ 第 3 轮（结构化确认清单）
  - 执行门禁：用户确认需求清单前，禁止任何 Agent 编写实现代码
  - 落地位置：`.prompts/pm_agent.md`（完整协议）+ `.cursorrules`（门禁规则）+ `.prompts/orchestration.md`（流程图更新）
- [2026-04-21] ADR-013: Fork 自动检测与 Brain 重置（Fork Auto-Detection & Brain Reset）
  - 新增 `.brain-owner` 文件记录仓库所有者标识（owner + repo + system_user）
  - 三层检测机制：`--fresh` 参数（无条件重置）→ Git remote owner 不一致（自动重置）→ 系统用户名不一致（交互确认）
  - `brain-init.sh` / `vibe-init.sh` 均支持 `--fresh` 参数，新用户一条命令开箱即用
  - 首次运行 + brain 非空时交互式询问是否清空（防止直接 clone 而非 fork 的场景）
  - 非交互模式（如 CI/CD）自动选择重置
  - `brain-check.sh` Check 11 验证 brain 所有权
  - 设计目标：fork/clone 即开箱即用，最多一次 Y/n 确认
- [2026-04-22] ADR-014: Architecture 模板与实例分离（Template vs Instance Separation）
  - `docs/architecture.md` 保留为 Harness 仓库自身的架构文档（填入真实的模块划分、数据模型、数据流）
  - 新增 `docs/architecture-template.md` 作为新项目的空白架构模板
  - `vibe-init.sh` harness 模式改为复制 `architecture-template.md` → 目标项目的 `docs/architecture.md`
  - `vibe-init.sh` inline 模式优先使用 template 文件，fallback 到内联生成
  - 新项目不再继承 Harness 的业务目标，拿到的是干净的待填写模板
  - 解决问题：之前 `safe_copy` 会把 Harness 自身的「业务最终目标」复制到新项目，导致 AI 对齐错误的业务方向

- [2026-04-22] ADR-015: Goal Discovery Protocol（业务目标发现协议）
  - 触发条件：AI 读取 `docs/architecture.md` 时检测到 `<!-- GOAL_PLACEHOLDER -->` 标记或业务目标为空/占位符
  - 三轮质询流程：第 0 轮（AI 自动扫描仓库结构并输出理解）→ 第 1 轮（核心目标确认）→ 第 2 轮（边界与约束）→ 第 3 轮（结构化输出写入 architecture.md）
  - 落地位置：`.cursorrules`（触发规则）+ `.prompts/pm_agent.md`（完整协议）+ `docs/architecture-template.md`（占位符标记）
  - 设计目标：新项目首次对话时 AI 主动引导用户明确业务方向，而非依赖用户手动填写空白模板
  - 豁免条件：用户明确说"跳过目标设定"、用户已完成过 Goal Discovery、业务目标已填写非占位符内容
  - 优先级：高于需求审查门禁——目标未锚定时，一切需求审查都无意义

## ⚠️ 已知天坑与环境限制 (Gotchas)
*💡 可检索的详细记忆请查阅 `brain/global/` 目录，本文件侧重于决策日志。*

- [2026-04-09] qmd（语义检索工具）是小众项目，生态风险高，不应强依赖。优先用 ripgrep 做检索，语义检索作为可选增强。
- [2026-04-09] three-layer-memory-skill 的 `weekly_memory_finalize.sh` 用 `git pull --rebase --autostash || true` 静默忽略冲突，可能导致记忆丢失。我们的实现需要有冲突处理机制。

## 💡 设计原则备忘
*从历史讨论中提炼的核心设计原则。*

- **`.env` 模式**：个人基础设施以 symlink 挂载到项目，`.gitignore` 隔离，绝不污染项目仓库
- **单仓库双职能**：Harness（护栏）+ Brain（记忆）合并为同一仓库，统一版本管理，独立于业务项目发布
- **验证闭环**：加载 → 检查 → 强制拦截 → 状态报告，四步确保脚手架真正生效
- **优雅降级**：有高级工具用高级工具，没有就自动回退到基础方案（如 qmd → ripgrep）
- **幂等挂载**：`brain init` / `brain mount` 重复运行不会出错
- **需求先行**：实质性需求必须经过多轮审查确认后才能开始执行，防止"需求模糊导致返工"