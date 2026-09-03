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
- [x] `task-75` 完成安装同步、服务重启和 sample application 真实验收

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

- Status: released
- Branch: main
- Tag: v0.18.0
- Work Branches: feat/v0.18-brain, feat/design-refactor
- Goal: 让 Brain 不再依赖会话结束和单一 Agent：项目细节由 Claude、Codex 与通用 Harness 的结构化事件自动沉淀，全局偏好和版本化 Profile 经过审批；本地写入与远端同步分开呈现，失败可见、可重试且不丢信息。

### Requirements

- [x] `task-94` 在工作台展示 Brain 分层健康度：仓库连通、Agent 覆盖、最近尝试、最近成功、最近错误、定时任务、待确认候选与远端同步，不用单一“已连接”掩盖回写故障
- [x] `task-95` 让 Claude、Codex 与通用 Harness 的结构化事件进入统一识别、脱敏和去重入口；SessionEnd 只负责可选压缩与补漏，不再是写入前提
- [x] `task-96` 将确认过的需求、版本阶段、决策、验证经验、完成结果、评审结论、交接和关键产物自动写入项目 Brain；拒绝推断、原始日志、重复进度、敏感信息和无项目归属内容
- [x] `task-97` 在工作台提供两条流水线：项目记忆活动流支持纠正、撤销、合并和提升为全局候选；全局偏好与 Profile 审批箱支持批准、编辑后批准、换层、合并、拒绝、忽略同类和重试
- [x] `task-98` 以 `fast / subsystem / release` 三档验证约束本版本开发成本，同一代码和环境下不重复发布 Gate，不采集或展示模型私有思维过程
- [x] `task-101` 保留已实现的 `prd-for-humans` 和版本化 PRD Profile，作为 Profile 审批、来源元数据与版本差异展示的首个真实用例；PRD 功能范围在本版本冻结
- [x] `task-102` 修正工作台信息层级：Brain 作为项目总览中的记忆服务入口；版本从新到旧排列；Git 用工作区、分支、版本和标签关系图展示真实开发现场
- [x] `task-103` 展示 Brain 实际本地仓库、远端、分支和写入来源/目标，并在工作台提供受控同步、确认和真实结果反馈
- [x] `task-104` 区分项目记录待同步与全局/Profile 待审批，精简仓库生效信息，并把确定性 Brain 行为从 Prompt/Hook 约束迁到常驻服务代码

## 0.19.0

- Status: released
- Branch: main
- Tag: v0.19.0
- Work Branches: feat/v0.19-service-reliability
- Goal: 把工作台从只读观察器升级为受控的 Harness 操作与进化中心，让用户可以安全完成注入、升级、能力适配，并把跨项目反复出现的问题转化为可审批、可验证、可撤销的 Harness 改进。

### Requirements

- [x] `task-130` 在首页提供 Harness update、项目注入/升级、Agent 接入修复等白名单操作，并建立幂等、互斥、恢复和审计的任务执行层
- [x] `task-131` 提供外部 Skill 安装前兼容诊断，并继续选择性吸收高质量开源 Skill 的方法；禁止整包静默接管角色、Hook、文档或完成定义
- [x] `task-132` 建立“项目问题 → Harness 改进候选 → 跨项目合并与频次 → 人工审批 → Rule/Skill/Checker/Profile → 效果复验”的工作台闭环；单次问题默认留在项目层，中央 Harness 规则不得自动改写
- [x] `task-133` 保证本机唯一的全局 Observer 在项目接入、Harness 安装与升级期间持续可用：同配置重复安装必须幂等，替换失败必须恢复旧服务，6425 与前台 watch 使用同一项目注册和扫描语义
- [x] `task-134` 纠正 QA / Reviewer 的真实参与与交接语义，把项目角色办公室改为可交互的场景与历史记录，并让用户安全地将失联项目移出工作台（不删除项目文件）
- [x] `task-135` 将项目主页重构为当前版本需求指挥台，让每条需求都能看清实际参与角色、当前工作、测试范围、验证证据、阻塞和下一步；版本页改为历史版本记录

## 0.21.0

- Status: released
- Branch: main
- Tag: v0.21.0
- Work Branches: feat/v0.21-command-surface
- Goal: 让 Harness 默认用最轻流程完成明确任务，只有复杂需求才展开可见流程；用户无需记命令，也能看见、介入并通过跨 Agent 统一入口管理计划、目标、Brain 和端到端交付。

### Requirements

- [x] `task-197` 建立跨 Agent 的 Harness 命令合同：底层统一为稳定 CLI，上层按 Codex、Claude Code 等宿主能力提供薄 Skill 或命令适配；不覆盖 Codex 已有的 `/plan` 与 `/goal`
- [x] `task-198` 提供计划与目标入口：扫描项目事实、预览冲突后创建或更新 `plan.md`，并把稳定长期目标写入项目目标文件而不是当前版本或技术计划
- [x] `task-199` 提供 Brain 首次配置和日常管理入口，明确区分“仅本机 / 私有远端 / 暂不启用”，展示写入位置、同步范围和真实连接状态
- [x] `task-200` 提供绑定单一需求的端到端交付入口；第一轮确认意图后自主推进到发布候选，只有偏离原意、高风险操作和正式发布才重新交给用户裁决
- [x] `task-201` 压缩常驻 Loader，把详细角色与工作流迁移到按需 Skill 和确定性脚本，为全局与项目指令建立可测试的 Token / 字节预算
- [x] `task-202` 在工作台展示命令能力、执行预览、当前阶段和结果，并完成跨 Agent 兼容、Brain 降级、上下文预算及真实用户路径验证
- [x] `task-203` 建立 `auto / quick / standard / e2e` 机器合同：默认选择足以证明结果的最轻流程，用户不需要先输入模式命令
- [x] `task-204` 将 Quick 变成 Kernel 默认轻量路径：不创建 plan、不启动角色流、不展示 Self-Test 或回合卡片，同时保留危险确认、撞墙熔断和完成验证
- [x] `task-205` 让 Agent 和本地事件记录有效模式、选择原因与升级原因，避免工作台只能从 Prompt 或角色摘要猜测
- [x] `task-206` 在工作台展示模式、耗时、可结构化证明的往返和待用户决策；同时把嵌套代码仓库与 ChatGPT/Codex 项目镜像的真实活动归入同一登记项目

## 0.20.2

- Status: released
- Branch: main
- Tag: v0.20.2
- Goal: 让公开 Harness 使用通用 Brain 身份与 `~/.brain` 默认目录，不携带维护者的私有 Brain 配置，同时兼容既有旧目录数据。

### Requirements

- [x] `task-197` 审计 v0.20.1 安装面与发布包中的个人路径、身份、Brain remote 和密钥形态
- [x] `task-198` 新安装默认使用 `~/.brain`，旧安装继续发现已有旧目录且不搬移、不删除记忆
- [x] `task-199` 移除公开实例 owner 和个人 Brain remote，并加入公共发布污染检查器
- [x] `task-200` 完成版本事实、全量 Release Gate、main 合并和 v0.20.2 发布

## 0.20.1

- Status: released
- Branch: main
- Tag: v0.20.1
- Work Branches: fix/v0.20.1-overview-task-restore
- Goal: 修复项目首页刷新后丢失当前需求选择的问题，让 URL、任务办公室和角色详情始终指向同一条当前版本需求。

### Requirements

- [x] `task-194` 当前版本需求通过 URL 选中后，刷新仍保持同一需求；无有效选择时只在当前版本需求内回落，并提供自动回归与真实 6425 证据

## 0.20.0

- Status: released
- Branch: main
- Tag: v0.20.0
- Work Branches: feat/v0.20-requirement-gates
- Goal: 把角色协作从“事件出现过哪些角色”升级为逐需求、可执行的产品交付门禁：开发前由 Reviewer 审查产品逻辑，开发后由 QA 独立验证，高风险交付再进行发布审查；非法跳转可见但不能推进有效状态。

### Requirements

- [x] `task-178` 固定结构化审查模式、门禁结果、受控例外、非法跳转和旧事件兼容合同
- [x] `task-179` 为 Reviewer 提供 `product-logic-review` Skill，按风险模拟用户路径、状态变化与边界情况，输出批准或退回结论
- [x] `task-180` 为每条需求建立 `PM → 产品审查 → 开发 → QA → 发布准备` 的确定性状态机，并支持产品审查后的 Planner / Designer 插入与高风险发布审查
- [x] `task-181` 让 PM、Reviewer、Executor、QA 的角色规则与状态机共享输入、交付物、门禁和回退语义
- [x] `task-182` 在项目主页让每条需求自带任务小队，并在选中需求内展开角色办公室，展示有效阶段、允许下一角色、门禁原因和被拒绝的跳转
- [x] `task-183` 通过全仓回归、Skill 校验、生成一致性和 6246 真实交互证明流程有效且旧项目兼容

## 0.22.0

- Status: released
- Branch: main
- Tag: v0.22.0
- Work Branches: feat/v0.22-maintenance-doctor
- Goal: 用一条确定性诊断路径收拢安装、项目、Agent、Brain、Observer 与 audit 状态，补齐真实 fixture，并清理失真的旧待办，让当前需求列表回到单一、可信、可清零的状态源。

### Requirements

- [x] `task-207` 提供顶层 `harness doctor`，聚合六类真实状态并给出可执行修复建议
- [x] `task-208` 完善 Agent Adapter Registry 的支持等级、加载方式、Hook 能力与限制合同
- [x] `task-209` 增加 Brain ingest、hook adapter、`brain evolve` 与无 Brain fallback 的隔离 fixture
- [x] `task-210` 压缩首次使用路径并清理 README、TODO 与历史验收状态冲突
- [x] `task-211` 完成全量、生成、语法、安装与真实 6425 验收，形成发布候选

## Backlog

> 对话中冒出的「新价值」需求先落这里；每个版本立项时从这里挑需求组成下一版本的 Goal 与 Requirements。每条写「一句话需求 + 它服务的未来 Goal 方向」。
