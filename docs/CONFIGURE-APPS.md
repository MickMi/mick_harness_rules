# 配置 AI 入口加载 Harness

Harness 的正常形态不是“给每个工具生成一套自己的规则”，而是：

```text
单一规则源 rules/core.md + rules/extended.md
        ↓
项目入口 AGENTS.md
        ↓
按使用场景导出的 Loader
```

也就是说，项目里默认只需要 `AGENTS.md`。不同 Agent、纯 API、IDE 插件只是读取同一个 Harness 的不同入口。

## 最短使用流程

### 1. 项目里初始化一次

```bash
cd /path/to/project
harness init
```

这会在项目里放入：

- `.harness/`：指向全局 Harness
- `AGENTS.md`：项目级入口
- `.gitignore`：避免把脚手架提交进业务仓库

### 2. 给 AI 入口配置 Loader

按你使用的入口选一个：

```bash
harness export codex    # Codex / AGENTS.md 基线
harness export agent    # 任意 Code Agent 的全局指令
harness export api      # 纯 API 调用的 system/developer prompt
harness export ide      # IDE 插件自定义规则
```

把输出复制到对应工具的全局指令、自定义规则或 API system/developer message。

默认导出内联 `rules/core.md`，并指向 `rules/extended.md`。如果入口没有文件系统、模型较弱，或你希望一次性完整灌入 Playbook，用：

```bash
harness export api --full
harness export ide --full
```

## 四个加载面

| 场景 | 推荐命令 | 解决的问题 |
|---|---|---|
| Codex / 支持 `AGENTS.md` 的 Code Agent | `harness init` + `harness export codex` | 以项目 `AGENTS.md` 为基线，让 Agent 进入项目先读 Harness |
| 任意 Code Agent | `harness export agent` | 工具不一定天然知道 `AGENTS.md`，用全局 Loader 强制它寻找项目入口 |
| 纯 API 调用 | `harness export api` | 没有文件系统、shell、浏览器时，把 Harness 变成可注入 prompt，并禁止伪造验证 |
| IDE 插件 | `harness export ide` | 插件上下文不稳定时，要求先读工作区入口，无法验证就标注 pending |

## 放在哪里

| 工具/入口 | 推荐位置 |
|---|---|
| Codex | 全局指令 / Profile / 用户规则；项目根目录保留 `AGENTS.md` |
| Claude Code | `~/.claude/CLAUDE.md` 或全局自定义指令 |
| Cursor | 全局 Rules for AI；必要时再用 `harness init --all-rules` |
| Windsurf / Cline / Roo / Trae | 全局自定义规则或用户偏好 |
| 纯 API | system/developer message；同时把 `AGENTS.md`、`plan.md`、相关文件内容作为输入 |
| IDE 插件 | 插件的 custom instructions / rules / workspace rules |

## 什么时候用 --all-rules

默认项目只需要：

```bash
harness init
```

只有当某个工具无法通过 Loader 读取 `AGENTS.md`，才运行：

```bash
harness init --all-rules
```

这会额外挂载 `CLAUDE.md`、`.cursorrules`、`.windsurfrules` 等兼容入口。它是兼容层，不是默认心智模型。

## 生效边界

Harness 对 AI 的约束分两层：

- **先验加载**：`AGENTS.md` 和 `harness export ...` 让模型在回答前读到同一套规则。
- **后验检查**：`harness check`、`generate.sh --check`、`scripts/harness-guard.sh` 等脚本发现生成物、计划、验证记录是否偏离。

Prompt 不能保证模型 100% 不犯错；Harness 的价值是把“约束是否被加载、是否按约束交付、是否有验证证据”变成可观察、可追问、可复用的流程。

## 完整加载和成本

为了避免每轮都消耗大量上下文，默认 Loader 只内联 Core：

- Tripwire
- plan.md 进入条件
- Self-Test
- 验证纪律
- 回合卡片
- 反馈分级

Extended Playbook 默认按需读取。需要完整内联时使用 `--full`。这不会改变 Harness 意图，只是把“完整加载”从默认成本变成显式选择。

## 用户心智模型

```text
新电脑 / 新 Agent：配置一次 export loader
新项目 / 已存在项目：运行一次 harness init
日常更新：运行 harness update
日常使用：直接打开项目，Agent 读 AGENTS.md，必要时再读 core/extended
```
