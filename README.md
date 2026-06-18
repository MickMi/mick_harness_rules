# Mick Harness Rules

一套可被 N 个项目复用的 AI 编码脚手架。引入即生效，不侵入项目代码，不污染项目仓库。

## 它解决什么问题

| 问题 | 解决方案 |
|------|---------|
| AI 写代码没有规范 | **Harness** — 10 条铁律 + 完整工程规范，自动注入 7 种 IDE |
| 每次对话从零开始 | **Brain** — 三层记忆（Session → Project → Global），跨对话持久化 |
| 需求模糊就开始写 | **角色协作** — PM / Designer / QA / Reviewer / Planner / Executor |
| 强弱模型协作混乱 | **Plan-Execute Protocol** — 强模型写计划，弱模型按计划执行，合规可扫描 |

## 快速开始

### 极速安装（推荐，零问题）

```bash
cd /path/to/your/project
git clone https://github.com/MickMi/mick_harness_rules.git .harness && .harness/setup.sh --quick
```

你会获得：7 种 IDE 的规则文件 + Plan-Execute 协议 + Agent 角色模板。5 秒完成。

### 完整安装（带 Brain 记忆 + 工作流配置）

```bash
git clone https://github.com/MickMi/mick_harness_rules.git .harness && .harness/setup.sh
```

额外获得：跨对话记忆（Brain）、MEMORY.md / TODO.md / docs/ 脚手架、13 项完整性检查。

### 合规扫描

Executor 完成一轮执行后，扫描 plan.md 检测越权行为：

```bash
.harness/harness-audit.sh --since HEAD~5         # 检查最近 5 个 commit
.harness/harness-audit.sh --since HEAD~5 --log   # 同时记录到 audit-log.md
```

### 更新

```bash
cd .harness && git pull && ./generate.sh
```

## 核心架构

### 单源规则体系

```
rules/core.md       10 条铁律（弱模型优化，所有工具都读）
rules/extended.md   完整工程规范 + 角色协作 + Plan-Execute Protocol
        ↓ generate.sh
dist/CLAUDE.md      [lean] core 内联 + extended 指针
dist/AGENTS.md      [lean] 同上（Codex / Zed / Aider）
dist/.cursorrules   [full] core + extended 全量内联
dist/.windsurfrules [full] 同上
dist/.clinerules    [full] 同上
dist/.github/copilot-instructions.md  [lean]
dist/.trae/rules.md                   [lean]
```

改一处 `core.md`，跑一次 `generate.sh`，所有工具同步更新。

### Plan-Execute Protocol（强弱模型协作）

```
用户 → Claude（强模型）: "设计用户注册流程的重构"
Claude: 写 plan.md（步骤、约束、验收标准）

用户 → DeepSeek/MiniMax（弱模型）: "执行计划"
弱模型: 读 plan.md → 逐步执行 → 写结构化自检日志

用户 → Claude: "检查执行情况"
Claude: 审查代码 + plan.md，追加 Executor 指导

用户: .harness/harness-audit.sh --since HEAD~5
脚本: 6 项合规检查 → PASS/WARN/FAIL 报告
```

### Brain（个人记忆，可选）

`--quick` 安装不含 Brain。完整安装会配置三层记忆：

| 层 | 位置 | 保留 | 来源 |
|----|------|------|------|
| Session | `brain/sessions/YYYY-MM-DD/` | 90 天 | AI 对话自动写入 |
| Project | `brain/projects/<slug>/` | 项目存续期 | 从 Session 蒸馏 |
| Global | `brain/global/` | 永久 | 从 Project 蒸馏 |

Brain 仓库（私有）与 Harness 仓库（公开）分离，fork 时不带个人记忆。

## Agent 角色

内置 7 个角色（`rules/roles/`，项目中映射为 `.prompts/`），显式点名调用：

| 角色 | 职责 | 唤起方式 |
|------|------|---------|
| PM | 对话式意图探索，输出 PRD | "用 PM 角色评审需求" |
| Designer | 设计代币、组件规格（OD 适配） | "用 Designer 角色出设计" |
| QA | 测试策略、用例矩阵 | "用 QA 角色制定测试" |
| Reviewer | 代码审查、安全审计 | "用 Reviewer 角色审查" |
| Planner | 写 plan.md，分解任务 | 强模型自动识别 |
| Executor | 严格按 plan 执行，禁止越权 | 弱模型自动识别 |
| Dev | 编码实现（默认角色） | 默认 |

## 日常命令

```bash
.harness/generate.sh              # 重新生成所有 IDE 规则文件
.harness/harness-audit.sh         # 扫描 plan.md 合规性
.harness/brain-search.sh <keyword> # 搜索记忆
.harness/brain-push.sh            # 写入记忆
.harness/brain-check.sh           # 验证脚手架完整性
.harness/setup.sh --reconfigure   # 重新配置工作流
```

## 设计原则

| 原则 | 说明 |
|------|------|
| `.env` 模式 | symlink 挂载 + `.gitignore` 隔离，零泄漏 |
| 单源多发 | 改一处规则，所有 IDE 同步 |
| 双仓库隔离 | Harness（公开）+ Brain（私有） |
| 弱模型优化 | 10 条铁律极短极硬，排在前面的最关键 |
| 幂等挂载 | 重复运行不出错 |
| Fork 即用 | 自动检测 fork 并重置 brain |
