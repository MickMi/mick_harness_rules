# 更新日志

语言：[English](CHANGELOG.md) | 简体中文

Mick Harness Rules 的重要变更都会记录在本文件中。

本项目遵循 Semantic Versioning 2.0。形如 `vX.Y.Z` 的 Git tag 是最终发布事实源。

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
