# Version Plan

> PM 使用这份文件记录“每个版本要证明什么、包含哪些需求”。Git 分支和标签仍以仓库真实状态为准，工作台会将两者对照展示。

## 版本范围怎么定

- **锚点是 Goal，不是需求清单**：Goal 立项时定死，之后不变；Requirements 是达成 Goal 的路径，可在实现中被澄清或补充，但必须服务于 Goal。
- **状态机**：`draft`（草拟）→ `locked`（冻结）→ `in_progress`（执行）→ `released`（发布）。`locked` 之后 Requirements 默认只接受「缺口」补充，不接受「新价值」。
- **新增需求先分三类再定归属**：
  - **缺口 gap**：不做它，Goal 就证明不了 → 进当前版本，但要警惕 Goal 当初是否定义完整；
  - **澄清 clarification**：本就在 Goal 范围内、只是没写清 → 进当前版本，更新描述，不算范围变更；
  - **新价值 new value**：服务于另一个 Goal → 进底部 Backlog，属于未来版本。
- **三问判定**：① 它属于哪一层（项目方向 / 版本 Goal / 需求）？② 当前版本冻结了吗？③ 不做它，Goal 还能不能证明？
- **归属可追溯**：每个「新需求进哪」的决定回写 `decision.recorded`（summary 写「需求 X 是 gap/clarification/new value，进 Y」），不散落在对话里。

## 0.11.0

- Status: released
- Branch: main
- Tag: v0.11.0
- Goal: 建立可验证的 Harness Kernel、Playbook、Skills 和统一验证契约。

### Requirements

- [x] Kernel 升级：先查复用、Anti-Wall 自动化回流和 Baseline First
- [x] 建立 Skills 层和 `.harness/verify.sh` 验证契约
- [x] 保持旧项目的向后兼容

## 0.12.0

- Status: released
- Branch: main
- Tag: v0.12.0
- Goal: 用反驳表和验证 Gate 固化 Kernel 证据纪律，并通过 SessionStart Hook 保证规则注入。

### Requirements

- [x] Kernel 反驳表：撞墙合理化、完成话术、Claim/Requires 证据分层表
- [x] 验证 Gate 五步与 UI 完成话术反驳表
- [x] Claude Code SessionStart Hook 自动注入 Tripwire 与回合卡片契约

## 0.13.0

- Status: released
- Branch: main
- Tag: v0.13.0
- Goal: 把 Harness 从规则注入工具升级为统一本地工作台，可以看进度、角色、产物和版本路线。

### Requirements

- [x] `task-20` 建立常驻 localhost 服务和跨项目总览
- [x] `task-25` 把默认看板改成用户能看懂的需求导航
- [x] `task-35` 接收真实角色工作、决策、交接和跨项目聚合
- [x] `task-39` 在工作台内阅读 Markdown 和代码产物
- [x] `task-40` 让 PM 管理版本目标、需求归属和 Git 对照
- [x] `task-47` 完成安装版、服务重启和真实浏览器验收

## 0.14.0

- Status: released
- Branch: main
- Tag: v0.14.0
- Goal: 用项目目标、当前版本和五角色办公室，让用户看懂当前由谁负责、工作如何流转以及关键产物在哪里。

### Requirements

- [x] `task-49` 建立稳定项目目标，不再把阶段 Plan 当作总体目标
- [x] `task-50` 投影 PM、设计、开发、测试、Review 的真实状态与流转
- [x] `task-51` 用角色办公室替代重复的需求、角色、决策和交接模块
- [x] `task-52` 让 PM 维护项目、版本和需求三层目标
- [x] `task-58` 完成安装版、服务重启和本机工作台验收

## 0.15.0

- Status: released
- Branch: main
- Tag: v0.15.0
- Goal: 让用户按版本或日期浏览项目产物，快速回到对应阶段的目标、讨论摘要、结果和文档章节。

### Requirements

- [x] `task-59` 固定产物多阶段记录与导航契约
- [x] `task-60` 投影产物版本、日期和重复交付记录
- [x] `task-61` 实现版本/日期筛选、阶段上下文和 Markdown 目录
- [x] `task-62` 记录导航使用方式与历史正文边界
- [x] `task-63` 完成安装版、服务重启和 localhost 验收

## 0.16.0

- Status: released
- Branch: main
- Tag: v0.16.0
- Goal: 建立从 AI 产出可追踪标题、Observer 确定性解析到用户阶段阅读导航的完整链路。

### Requirements

- [x] `task-67` 固定阶段标题、正文日期忽略和新版阅读导航契约
- [x] `task-68` 约束 AI 使用版本、实际沟通日期和用户可读阶段标题
- [x] `task-69` 解析规范标题并兼容旧项目单日期与多日期标题
- [x] `task-70` 用阶段目录替换无效的事件筛选和阶段卡
- [x] `task-71` 记录产出、解析、展示和历史正文边界
- [x] `task-74` 生成并验证规则分发文件
- [x] `task-75` 完成安装同步、服务重启和 RaliTennis 真实验收

## 0.17.0

- Status: released
- Branch: main
- Tag: v0.17.0
- Goal: 把规则注入、Agent 生效证明、结构化回写和 Brain 交互做成可诊断、可恢复、可迁移的本地工作系统，并用精简角色契约与行为评测证明各角色真实有效。

### Requirements

- [x] `task-79` 建立现状基线、威胁模型和端到端可靠性验收合同
- [x] `task-80` 建立 Code Agent 注册表、支持等级和本机诊断能力
- [x] `task-81` 实现幂等、原子、可回滚的规则注入与旧格式迁移
- [x] `task-82` 证明规则已经被 Agent 加载，并补齐 Claude Code / Codex 生命周期接入（Claude 完整 turn 验证按用户决定列为发布例外）
- [x] `task-83` 建立离线可恢复、去重且可迁移的结构化工作回写链路
- [x] `task-84` 固定 Brain 读取、写入、隐私、来源与审计边界
- [x] `task-85` 精简 PM、Planner、Executor、QA、Reviewer 与可选 Designer 的角色契约
- [x] `task-86` 建立开源 Skill 的来源、许可证、安全、版本固定与去重机制
- [x] `task-87` 用确定性契约测试和 Tier 1 Agent 行为样本验证角色有效性（Codex Reviewer 10/10；Claude 未评测）
- [x] `task-88` 在工作台展示发现、注入、加载、遵守和回写五层真实状态
- [x] `task-89` 完成兼容迁移、产品文档和支持矩阵
- [x] `task-90` 通过故障注入、重启恢复、隐私和端到端发布 Gate

## 0.18.0

- Status: in_progress
- Branch: main
- Goal: 把本地工作台从只读观察页升级为安全、可恢复的 Harness 操作中心，并让 Brain 的连接、触发、候选、同步与故障状态对用户真实可见。

### Requirements

- [ ] `task-91` 定义工作台操作边界：仅开放 update、项目注入/更新、Agent 接入修复等白名单动作，并为每个动作提供预检、影响说明、确认、进度、结果和审计记录
- [ ] `task-92` 建立服务端任务执行层，支持幂等、单任务互斥、失败恢复和可追踪状态，禁止把任意命令执行能力暴露给浏览器
- [ ] `task-93` 在首页增加“操作中心”，可视化完成 Harness 更新、项目注入/升级和 Agent 修复，并清楚区分待处理、执行中、成功、失败与可恢复状态
- [ ] `task-94` 在工作台展示 Brain 分层健康度：仓库连通、Agent 覆盖、最近尝试、最近成功、最近错误、定时任务、待确认候选与远端同步，不用单一“已连接”掩盖回写故障
- [ ] `task-95` 修复 Brain 回写链路：解决 Claude SessionEnd transcript 定位失败，补齐 Codex/通用入口，并以 Harness 结构化事件作为不依赖聊天正文的可靠来源
- [ ] `task-96` 建立有节制的触发策略：在任务完成、关键决策、已验证经验和会话结束时生成去重候选，使用防抖与批处理，避免每轮提交造成噪音和隐私风险
- [ ] `task-97` 在工作台提供 Brain 候选的查看、确认、拒绝与重试入口，并通过权限、隐私、服务重启、离线恢复和端到端发布 Gate

## Backlog

> 对话中冒出的「新价值」需求先落这里；每个版本立项时从这里挑需求组成下一版本的 Goal 与 Requirements。每条写「一句话需求 + 它服务的未来 Goal 方向」。

_（当前为空）_
