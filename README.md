# Mick Harness Rules

一套可被 N 个项目复用的 AI 编码协调层。引入即生效，不侵入项目代码，不污染项目仓库。

## 定位：在 Code Agent 已经很强的今天，它补的是哪一块

Claude Code / Cursor 这类 Agent 的"通用工程纪律"（先读后改、防御性编程、自我审查）正在被原生吸收——这部分 harness 主动让路，不重复造轮子。

harness 专注于**单一厂商结构上不会做、且工具越多越需要**的三件事：

| 能力 | 为什么厂商不做 | harness 怎么做 |
|------|---------------|---------------|
| **跨工具归一** | 没有厂商有动力帮你统一竞品的配置 | 一份 `core.md` → 自动生成 7 种 IDE 规则文件 |
| **跨模型编排** | "用 Claude 规划、用 DeepSeek 执行"本质是不锁定单一厂商 | Plan-Execute 协议 + 强弱模型分工 + 回合卡片导航 |
| **越权治理** | 没有 Agent 会审计自己有没有守规矩 | `harness-audit.sh` 站在所有 Agent 之上做合规扫描 |

> 一句话：harness 的价值不在"教 Agent 写好代码"（正在被吸收），而在"**协调多个 Agent + 把我的工作方式固化下来**"（没人能替你做）。目标用户是用**多工具 / 多模型**的人——单工具用户用 Agent 原生能力就够了。

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

### 更新

```bash
cd .harness && git pull && ./generate.sh
```

## 三大能力详解

### 1. 跨工具归一 — 单源规则体系

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

改一处 `core.md`，跑一次 `generate.sh`，所有工具同步更新。工具越多，这个价值越大。

### 2. 跨模型编排 — Plan-Execute Protocol

强模型负责"做什么"，弱模型负责"怎么写"，省钱且不被单一厂商绑定：

```
用户 → Claude（强模型）: "重构用户注册流程"
Claude(Planner): 写 plan.md（步骤、约束、验收标准、顶部状态行）

用户 → DeepSeek/MiniMax（弱模型）: "执行计划"
弱模型(Executor): 读 plan.md → 逐步执行 → 写结构化自检日志

用户 → Claude: "检查执行情况"
Claude(Reviewer): 审查代码 + plan.md，追加 Executor 指导
```

**回合卡片导航**：三方（强模型 / 弱模型 / Designer）来回切换时，用户是人肉消息总线，最容易失焦。每个角色每回合强制输出一张卡片，多线程切换也不串台：

```
━━━━━━ 回合卡片 · login-form 重构 ━━━━━━
✅ 本回合：完成步骤 5，新建 src/auth/validate.ts，跑通 register.spec.ts（12/12）
📍 整体：执行中 · plan 5/8 · 当前归属 弱模型(Executor)
➡️ 下一步：切到 Open Design，粘贴：「用 Designer 角色出 login-form 视觉稿」
🆘 卡住了：回 Claude(Planner)，说「步骤6设计依赖做不了，帮我调 plan」
```

`✅` 防遗忘 · `📍` 重新锚定 · `➡️` 可复制导航 · `🆘` 错误逃生线。

### 3. 越权治理 — 合规扫描

Executor 完成一轮执行后，扫描 plan.md 检测越权行为（站在 Agent 之上的治理层）：

```bash
.harness/harness-audit.sh --since HEAD~5         # 检查最近 5 个 commit
.harness/harness-audit.sh --since HEAD~5 --log   # 同时把违规信号写进 Brain（供自进化）
```

6 项检查：plan 完整性、自检覆盖率、验证证据、执行顺序、范围蔓延、文件对齐。输出 PASS/WARN/FAIL 报告。

加 `--log` 时，违规信号按类型写进 Brain（`global/evolution/audit-trail.md`），跨项目累积，喂给下面的自进化闭环。

### 规则自进化（信号回流，人工门禁）

真实执行的违规信号会回流，提议规则改动——但**绝不自动改规则**：

```bash
.harness/harness-evolve.sh --since 30d --threshold 3   # 聚合信号 → 生成提案
```

输出 `docs/evolution/proposal-YYYY-MM-DD.md`：哪条规则反复被违反、趋势是改善还是恶化、建议怎么改（含"删除贬值规则"）。你勾选接受/修改/拒绝，手动合并进 `rules/*.md` 再 `generate.sh`。同一问题的违规频次随时间下降 = 进化有效。

## Agent 角色

内置 7 个角色（`rules/roles/`，项目中映射为 `.prompts/`），显式点名调用：

| 角色 | 职责 | 唤起方式 |
|------|------|---------|
| PM | 对话式意图探索，输出 PRD | "用 PM 角色评审需求" |
| Designer | 设计代币、组件规格（OD 适配，拆回合输出） | "用 Designer 角色出设计" |
| QA | 测试策略、用例矩阵 | "用 QA 角色制定测试" |
| Reviewer | 代码审查、安全审计 | "用 Reviewer 角色审查" |
| Planner | 写 plan.md，分解任务 | 强模型自动识别 |
| Executor | 严格按 plan 执行，禁止越权 | 弱模型自动识别 |
| Dev | 编码实现（默认角色） | 默认 |

每个角色每回合结尾都输出回合卡片，`➡️`/`🆘` 对应它在状态机里的正常出边和错误出边。

## Brain（个人记忆，可选）

`--quick` 安装不含 Brain。完整安装会配置三层记忆：

| 层 | 位置 | 保留 | 来源 |
|----|------|------|------|
| Session | `brain/sessions/YYYY-MM-DD/` | 90 天 | AI 对话自动写入 |
| Project | `brain/projects/<slug>/` | 项目存续期 | 从 Session 蒸馏 |
| Global | `brain/global/` | 永久 | 从 Project 蒸馏 |

Brain 仓库（私有）与 Harness 仓库（公开）分离，fork 时不带个人记忆。

## 日常命令

```bash
.harness/generate.sh              # 重新生成所有 IDE 规则文件
.harness/harness-audit.sh         # 扫描 plan.md 合规性
.harness/harness-evolve.sh        # 聚合违规信号，生成规则进化提案
.harness/brain-search.sh <keyword> # 搜索记忆
.harness/brain-push.sh            # 写入记忆
.harness/brain-check.sh           # 验证脚手架完整性
.harness/setup.sh --reconfigure   # 重新配置工作流
```

## 设计原则

| 原则 | 说明 |
|------|------|
| 主动让路 | 原生覆盖的编码纪律持续收缩，专注编排/治理/归一 |
| `.env` 模式 | symlink 挂载 + `.gitignore` 隔离，零泄漏 |
| 单源多发 | 改一处规则，所有 IDE 同步 |
| 双仓库隔离 | Harness（公开）+ Brain（私有） |
| 弱模型优化 | 10 条铁律极短极硬，排在前面的最关键 |
| 幂等挂载 | 重复运行不出错 |
| Fork 即用 | 自动检测 fork 并重置 brain |
