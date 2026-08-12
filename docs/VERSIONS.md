# Version Plan

> PM 使用这份文件记录“每个版本要证明什么、包含哪些需求”。Git 分支和标签仍以仓库真实状态为准，工作台会将两者对照展示。

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
- Goal: 把 Harness 从规则注入工具升级为统一本地工作台，可以看进度、角色、产物和版本路线。

### Requirements

- [x] `task-20` 建立常驻 localhost 服务和跨项目总览
- [x] `task-25` 把默认看板改成用户能看懂的需求导航
- [x] `task-35` 接收真实角色工作、决策、交接和跨项目聚合
- [x] `task-39` 在工作台内阅读 Markdown 和代码产物
- [x] `task-40` 让 PM 管理版本目标、需求归属和 Git 对照
- [x] `task-47` 完成安装版、服务重启和真实浏览器验收

## 0.13.0

- Status: released
- Branch: main
- Tag: v0.13.0
- Goal: 用项目目标、当前版本和五角色办公室，让用户看懂当前由谁负责、工作如何流转以及关键产物在哪里。

### Requirements

- [x] `task-49` 建立稳定项目目标，不再把阶段 Plan 当作总体目标
- [x] `task-50` 投影 PM、设计、开发、测试、Review 的真实状态与流转
- [x] `task-51` 用角色办公室替代重复的需求、角色、决策和交接模块
- [x] `task-52` 让 PM 维护项目、版本和需求三层目标
- [x] `task-58` 完成安装版、服务重启和本机工作台验收

## 0.14.0

- Status: released
- Branch: main
- Tag: v0.14.0
- Goal: 让用户按版本或日期浏览项目产物，快速回到对应阶段的目标、讨论摘要、结果和文档章节。

### Requirements

- [x] `task-59` 固定产物多阶段记录与导航契约
- [x] `task-60` 投影产物版本、日期和重复交付记录
- [x] `task-61` 实现版本/日期筛选、阶段上下文和 Markdown 目录
- [x] `task-62` 记录导航使用方式与历史正文边界
- [x] `task-63` 完成安装版、服务重启和 localhost 验收

## 0.15.0

- Status: released
- Branch: main
- Tag: v0.15.0
- Goal: 建立从 AI 产出可追踪标题、Observer 确定性解析到用户阶段阅读导航的完整链路。

### Requirements

- [x] `task-67` 固定阶段标题、正文日期忽略和新版阅读导航契约
- [x] `task-68` 约束 AI 使用版本、实际沟通日期和用户可读阶段标题
- [x] `task-69` 解析规范标题并兼容旧项目单日期与多日期标题
- [x] `task-70` 用阶段目录替换无效的事件筛选和阶段卡
- [x] `task-71` 记录产出、解析、展示和历史正文边界
- [x] `task-74` 生成并验证规则分发文件
- [x] `task-75` 完成安装同步、服务重启和 RaliTennis 真实验收
