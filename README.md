# Mick Harness Rules

让你的 AI 编程助手按你的方式工作。不侵入项目、不依赖特定工具。

---

## 第一步：安装（全机器一次，30 秒）

打开终端，粘贴运行：

```bash
git clone https://github.com/MickMi/mick_harness_rules.git ~/.mick-harness && \
ln -s ~/.mick-harness/bin/harness ~/.local/bin/harness
```

验证安装成功：

```bash
harness version
```

---

## 第二步：加载到你的 AI 工具

**选你的工具，跑对应的命令，把输出粘贴进去。** 每个工具只需配一次。

### Codex / Zed / Aider

进入项目目录，一句话初始化：

```bash
harness init
```

之后 Agent 打开项目自动读取 `AGENTS.md`，无需额外配置。

### Claude Code

```bash
harness export agent >> ~/.claude/CLAUDE.md
```

（往 `~/.claude/CLAUDE.md` 追加 Harness Loader。需要完整 Playbook 时加 `--full`）

### WorkBuddy

```bash
harness export agent | pbcopy
```

粘贴到 WorkBuddy 的"自定义指令 / System Prompt"位置。

### Cursor

```bash
harness export ide | pbcopy
```

粘贴到 Cursor Settings → Rules for AI。

### Windsurf / Cline / Copilot / Trae

```bash
harness export agent | pbcopy
```

粘贴到工具的"自定义指令 / 全局规则 / System Prompt"位置。

### 纯 API 调用（OpenAI / Anthropic / 其他）

```bash
harness export api | pbcopy
```

粘贴到 API 请求的 system / developer message 字段。需要完整 Playbook：

```bash
harness export api --full | pbcopy
```

---

## 验证生效了？

对你的 AI 说这句话：

> 请按 Harness Self-Test 用 5 句话证明你理解当前任务约束。

**合格的回答**绑定当前任务——现在什么模式、最高风险在哪、怎么验证完成、撞墙了怎么停、不会做什么。**泛泛复述规则视为未通过。**

---

## 日常使用

| 命令 | 作用 |
|------|------|
| `harness init` | 新项目初始化（挂载 AGENTS.md） |
| `harness init --full` | 加上配置文件和 Brain 记忆连接 |
| `harness export <surface>` | 输出任意工具的 Loader 文本 |
| `harness update` | 更新 Harness + 刷新所有项目 |
| `harness report` | 查看当前项目 plan 状态与阻塞 |
| `harness metrics` | 任务完成率、验证覆盖率等指标 |
| `harness check` | 验证项目脚手架完整性 |

---

## 没有终端 / 不想装 CLI？

复制下面 3 句话，粘贴到你的 AI 工具的"自定义指令"位置。这是 Harness 的最小内核：

```text
1. 改动任何文件前，先读它的当前内容。凭记忆覆盖 = 违约。
2. 改动文件前检查 plan.md。存在且本轮要改文件 → 按 plan 执行。纯讨论无需检查。
3. 没验证 ≠ 完成。每条改动附带验证证据。禁止说"应该好了/可以了/完成了"。
```

---

## 它做了什么

Harness 解决 AI 编码的三个通病：**没判断标准**（AI 不会按你的证据纪律工作）、**没记忆**（每次对话从零开始）、**没闭环**（大功能能做出来，交互细节反复撞墙）。

它是一组**单源规则**（`rules/core.md`）+ 一套**脚本工具**（`harness` CLI）。改规则 → 跑 `harness update` → 所有项目同步。
