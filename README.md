# Mick Agent Harness

**中文** | [English](README.en.md)

让你的 AI 编码规则、个人偏好和项目纪律，在不同设备、项目和 Code Agent 之间持续生效。

Mick Agent Harness 是一套个人 Agent 协作层。它不是新的 Code Agent，也不是替代 Claude Code、Codex、Cursor 这类工具的编码能力。它的定位是：**补充 Agent 能力，而不是覆盖 Agent 能力**。AI Agent 的通用编码能力会持续进化，Harness 最有价值的部分是把你的工作方式、质量标准、验证习惯和长期记忆稳定地注入进去，让不同 Agent 都更像你。

当前实现仓库名是 `mick_harness_rules`；产品名是 **Mick Agent Harness**。

## 为什么需要它

当你只用一个 Agent、一个项目、一台电脑时，写几条规则也许够用。但一旦你开始同时使用 Claude Code、Codex、Cursor、IDE 插件，或者在公司电脑、个人电脑、不同项目之间切换，问题会很快出现：

- 你在 Claude 里反复强调过的偏好，Codex 不知道；
- A 项目踩过的坑，B 项目又重来；
- 新电脑上没有同一套规则和长期记忆；
- Agent 没读文件、没查 `plan.md`、没验证就开始交付；
- Self-Test 看起来通过，用户端真实路径仍然有 bug；
- 多轮调试都在给合理解释，但问题没有真正收敛。

Mick Agent Harness 解决的是这个断点：**让规则、上下文、验证纪律和长期记忆跨设备、跨项目、跨 Agent 延续。**

## 适合谁

Mick Agent Harness 适合这些用户：

- 同时使用 Claude Code、Codex、Cursor、IDE 插件或 API 调用；
- 经常在多台电脑或多个项目之间切换；
- 已经有项目被 AI 写过很多轮，想中途加上约束；
- 不只想让 Agent “能写代码”，还希望它持续遵守你的工作方式；
- 需要把踩坑、偏好、验证结果沉淀成长期记忆；
- 希望 Harness 可复用、低侵入、可验证，而不是每轮手动提醒 Agent。

如果你只是在一个一次性脚本里试用 AI，可能不需要它。它更适合重度 AI 编码用户和希望建立个人 Agent 工作流的人。

## 5 分钟开始

### 1. 每台机器安装一次

```bash
git clone https://github.com/MickMi/mick_harness_rules.git ~/.mick-harness
mkdir -p ~/.local/bin
ln -sf ~/.mick-harness/bin/harness ~/.local/bin/harness
~/.local/bin/harness install
```

如果已经安装过：

```bash
harness update
```

### 2. 每个项目初始化一次

在新项目或已有项目里都可以运行：

```bash
cd /path/to/your-project
harness init
```

它会在项目里放一个很小的入口，让 Agent 能找到全局 Harness。

需要 Brain 和完整检查时：

```bash
harness init --full
```

### 3. 让 Agent 读取规则

自动同步到本机支持的 Agent：

```bash
harness agents sync
```

不能自动管理的工具，用导出：

```bash
harness export codex
harness export agent
harness export ide
harness export api
```

### 4. 验证是否生效

对 Agent 说：

```text
请按 Harness Self-Test 用 5 句话证明你理解当前任务约束。
```

合格回答必须绑定当前任务，说明：

1. 当前模式；
2. 最高风险；
3. 如何证明完成；
4. 重复失败时如何停止；
5. 本轮不会做什么。

Self-Test 只证明 Agent 读到了约束，不等于功能完成。真实交付仍然必须给出测试命令、dry-run、截图、日志，或明确标注“未验证”。

## 成功后应该看到什么

项目里会出现：

```text
AGENTS.md
.harness/ -> ~/.mick-harness
```

Agent 应该知道：

- 改文件前先读文件；
- 改文件或生成交付物前检查 `plan.md`；
- 普通讨论不机械进入 plan；
- 交付必须带验证证据；
- 重复失败时停止乱试并输出 Debug Card；
- 交付、Self-Test、Harness 加载检查等工作流回合要输出回合卡片。

你可以随时检查：

```bash
harness check
harness report
harness metrics
```

## 它会改哪些文件

| 操作 | 可能写入的位置 | 目的 | 回滚方式 |
|---|---|---|---|
| `harness install` | `~/.mick-harness`、`~/.local/bin/harness` | 安装全局 Harness 和 CLI | 删除目录和 symlink |
| `harness agents sync` | `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md` | 注入 managed loader | 删除 `MICK-HARNESS-GLOBAL` 标记块 |
| `harness init` | 项目内 `AGENTS.md`、`.harness/`、`.gitignore` | 项目挂载 Harness | 删除 `.harness`；移除 `AGENTS.md` symlink 或 `HARNESS:BEGIN` 标记块 |
| `harness init --full` | 项目内 `.harness-config.yaml` | 启用完整配置和检查 | 删除该配置文件 |
| `harness brain install` | `~/.mick-brain`、可选 Claude hook/LaunchAgent | 创建 Brain 和启用同步 | 删除 Brain 目录或关闭对应 hook |

项目文件如果已有同名规则文件，Harness 会用标记块注入，不会直接丢弃原内容。

## 它能保证什么

Prompt 约束不能让任何模型 100% 服从。Mick Agent Harness 的保证边界是：

| 能力 | 是否支持 | 说明 |
|---|---|---|
| 统一规则入口 | 支持 | 通过全局 loader 和项目 `AGENTS.md`。 |
| 项目级挂载 | 支持 | 每个项目只保留小入口，不复制整套规则树。 |
| 强制模型一定服从 | 不承诺 | 模型仍可能忽略 prompt。 |
| 发现未加载/未验证 | 支持 | 通过 Self-Test、`harness check`、回合卡片和验证证据检查。 |
| 阻止所有错误代码合入 | 不承诺 | 需要结合测试、CI、review 或更硬的工程门禁。 |
| 长期记忆沉淀 | 支持 | 通过 Private Brain 和可选 hook adapter。 |
| 自动改写 Harness 规则 | 不支持 | 只生成进化提案，由人 review 后合并。 |

换句话说：Harness 不是魔法强制器，而是一套**先验注入 + 后验检查 + 长期记忆 + 人工门禁**的协作系统。

## 支持的入口

| 场景 | 推荐方式 | 当前状态 |
|---|---|---|
| Claude / Claude Code | `harness agents sync` | 自动 managed loader；Brain hook 支持最完整。 |
| Codex / Codex CLI | `harness agents sync` 或 `harness export codex` | 支持全局 loader；Brain 写入通过可选 adapter / ingest。 |
| 支持 `AGENTS.md` 的工具 | `harness init` | 项目级入口稳定。 |
| Cursor / IDE 插件 | `harness export ide` | 手动粘贴或由插件侧加载。 |
| 任意 Code Agent | `harness export agent` | 通用 prompt 契约。 |
| 纯 API 调用 | `harness export api` | 作为 system / developer message 使用。 |
| 自定义 hook | `bash scripts/brain-ingest.sh` | 工具无关写入入口。 |

弱模型、纯 API、无文件系统访问或高风险任务需要完整上下文时：

```bash
harness export api --full
harness export ide --full
```

## 工作原理

Mick Agent Harness 由四层组成：

| 层 | 作用 | 典型文件/命令 |
|---|---|---|
| Global Harness | 安装在本机的一套公共规则和工具 | `~/.mick-harness`、`harness install` |
| Agent Loader | 注入到 Code Agent 的全局入口 | `harness agents sync`、`harness export codex` |
| Project Manifest | 项目里的最小入口，指向全局 Harness | `AGENTS.md`、`.harness/` |
| Private Brain | 私有长期记忆和规则进化信号 | `~/.mick-brain`、`harness brain install` |

推荐形态：

```text
一台机器安装一次 Harness
  -> 每个项目运行一次 harness init
  -> 每个 Agent 通过 loader 或 export 读取同一套规则
  -> 交付时用 check / audit / verification 做后验约束
  -> 重要经验写入 Private Brain
  -> 周期性生成 Harness 规则进化提案
```

## 日常命令

日常使用只需要少量命令：

```bash
harness check
harness report
harness metrics
harness update
```

| 命令 | 用途 |
|---|---|
| `harness check [dir]` | 检查项目 Harness / Brain / 规则生成状态。 |
| `harness report [dir]` | 查看 `plan.md` 进度、阻塞和验证状态。 |
| `harness metrics [dir]` | 聚合完成率、验证覆盖率和 audit 信号。 |
| `harness update` | 更新全局 Harness、重新生成规则、刷新注册项目、同步 Agent loader。 |
| `harness agents scan` | 查看本机可自动管理的 Agent 入口。 |
| `harness agents sync` | 把 managed loader 同步到支持的 Agent 入口。 |

## Advanced: Private Brain

Brain 是私有长期记忆，默认放在 `~/.mick-brain`，也可以配置成私有 Git 仓库。

Brain 分三层：

| 层 | 保存什么 |
|---|---|
| Global | 跨项目偏好、沟通方式、常见踩坑、长期质量标准。 |
| Project | 项目级决策、架构背景、历史问题、业务上下文。 |
| Session | 单次对话摘要、执行结果、验证证据、失败信号。 |

安装或检查：

```bash
harness brain install
harness brain status
```

如果用户还没有 Brain，`harness brain install` 会自动创建本地 `~/.mick-brain` 骨架。若配置了私有仓库但暂时无法 clone，也会降级成本地 fallback，不阻断 `harness init --full`、`harness check` 或原有 Harness 工作流。

Brain 是私有数据，不应该提交到公开 Harness 仓库，也不应该混进业务项目仓库。

## Advanced: Hook Adapter

Hook adapter 用来把不同工具的会话摘要、失败信号和验证结果写入 Brain。它通过现有命令管理，不新增大量顶层命令：

```bash
harness brain install
harness brain status
```

默认配置在 `config/.brain-config.yaml`：

- `claude_code.enabled: true`：默认启用 Claude Code SessionEnd 和 daily sync；
- `codex.enabled: false`：可选开启 Codex inbox；
- `generic.enabled: false`：可选开启通用 command/inbox adapter。

工具无关写入入口：

```bash
printf '%s\n' "session summary" \
  | bash ~/.mick-harness/scripts/brain-ingest.sh --source codex --kind session
```

失败信号写入：

```bash
printf '%s\n' "Harness missed a required round card" \
  | bash ~/.mick-harness/scripts/brain-ingest.sh --source codex --kind failure
```

这使 Claude Code、Codex、IDE 插件和纯 API 调用都可以接入同一个 Brain 飞轮，但是否自动触发由用户配置决定。

## Advanced: Harness 自进化

Mick Agent Harness 不会静默修改自己的规则。它的进化路径是：

```text
Agent 执行
  -> 回合卡片 / audit / failure signal
  -> Private Brain evolution log
  -> harness brain evolve
  -> 生成规则进化提案
  -> 用户 review
  -> 接受后修改 rules/*.md
  -> generate / export / sync
  -> 后续同类失败下降
```

运行：

```bash
harness brain evolve
```

判断一次规则进化是否有效，不看规则写得是否更复杂，而看后续同类失败是否下降。

## 设计原则

- **可复用**：同一套 Harness 可以挂载到多个项目。
- **低侵入**：项目只保留小入口，不复制整套规则树。
- **工具中立**：优先抽象成 Agent 协作协议，而不是某个工具的私有配置。
- **默认简单**：安装、初始化、更新都尽量是一条命令。
- **证据驱动**：没验证不叫完成。
- **隐私优先**：公开 Harness 与私有 Brain 分离。
- **人工门禁进化**：自动收集信号，但规则合并由人确认。
- **上下文成本可控**：Core 默认加载，Extended 按风险加载。

## 当前限制

- Prompt 约束无法保证所有模型 100% 遵守，仍需要后验检查和用户 review。
- 自动 loader 管理目前主要覆盖文件型入口；部分 IDE 插件需要手动 export。
- Brain hook 自动化在 Claude Code 上最完整；Codex、IDE、API 通过可选 adapter / ingest 接入。
- `harness brain evolve` 生成的是提案，不会自动改写规则。
- 私有 Brain 的远程同步取决于用户自己的私有仓库权限和网络状态。

## 开发与验证

常用验证：

```bash
bash -n bin/harness scripts/*.sh generate.sh
./generate.sh --check
MICK_HARNESS_ROOT="$PWD" ./bin/harness version
MICK_HARNESS_ROOT="$PWD" ./bin/harness export codex
```

项目初始化验证：

```bash
tmp_project="$(mktemp -d)"
MICK_HARNESS_ROOT="$PWD" ./bin/harness init "$tmp_project" --full
```

Brain fallback 验证：

```bash
tmp_home="$(mktemp -d)"
HOME="$tmp_home" MICK_HARNESS_ROOT="$PWD" ./bin/harness brain install
HOME="$tmp_home" MICK_HARNESS_ROOT="$PWD" ./bin/harness brain status
```

## 下一版本重点

- 增加更统一的 `harness doctor`，一次性检查安装、项目、Agent loader、Brain、hook 和 audit。
- 完善 Adapter Registry，让每个工具的支持等级、加载方式和 hook 能力更明确。
- 增加 fixture 测试，覆盖 Brain ingest、hook adapter、`brain evolve` 和无 Brain fallback。
- 继续把产品路径压缩成：安装一次、项目 init 一次、Agent sync/export 一次、Brain 可选开启。
