# Mick Agent Harness

**中文** | [English](README.en.md)

一套可诊断、可恢复、可迁移的本地 Agent 协作工作系统：把「规则注入 → Agent 生效证明 → 结构化回写 → 角色契约 → 长期记忆」串成闭环，让你的 AI 编码规则、个人偏好和项目纪律，在不同设备、项目和 Code Agent 之间持续生效——并且你能看见它们到底有没有真的生效。

Mick Agent Harness 不是新的 Code Agent，也不替代 Claude Code、Codex、Cursor 这类工具的编码能力。它的定位是**补上 Agent 缺的那一层治理**：先验注入规则、后验验证回写、五层状态可诊断、角色边界可执行。AI 的通用编码能力会持续进化，Harness 最有价值的部分是把你的工作方式、质量标准、验证习惯和长期记忆稳定地注入进去，并证明它被加载、被执行、被回写，让不同 Agent 都更像你。

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

## 它由什么组成

Harness 围绕一条闭环工作，五层 Agent 状态每一层都可诊断：

| 层 | 回答的问题 | 对应能力 |
|---|---|---|
| 发现 | 本机有哪些 Code Agent | `harness agents scan`、Agent 注册表 |
| 注入 | 规则是否装进 Agent 入口 | `harness agents sync`、`harness export` |
| 加载 | Agent 新会话是否真的读了规则 | SessionStart Hook 回报规则版本 + 角色 digest |
| 遵守 | Agent 是否按角色边界执行 | 七段角色契约 + 行为评测 |
| 回写 | 工作是否结构化回到工作台 | `harness observe emit` + 生命周期 Hook |

角色契约只有七个段落——`触发 / 必读输入 / 职责 / 非职责 / 交付物 / 验收 / 交接`，覆盖 PM、Planner、Executor、QA、Reviewer 和可选 Designer。边界可执行、越界可回流，不把固定瀑布流程强加给小改动。

本地工作台（`127.0.0.1:6425`）统一展示项目目标、版本路线、五角色办公室和产物；Private Brain 沉淀长期记忆并驱动规则进化。

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

### 3. 一次检查，按提示修复

```bash
harness doctor
```

它会一起检查安装、当前项目、Code Agent、Brain、本地工作服务和项目审计。只有出现具体修复建议时才需要运行对应命令，例如：

```bash
harness agents sync --dry-run
harness agents hooks --dry-run
harness observe service install
```

不能自动管理的工具，诊断会明确标为“手动接入”或“暂不支持”；需要时再使用 `harness export ide` / `harness export api`。

### 4. 新会话验证是否生效

Codex 在 `/hooks` 信任 Hook，Claude 重开新会话，然后对 Agent 说：

```text
请按 Harness Self-Test 用 5 句话证明你理解当前任务约束。
```

合格回答必须绑定当前任务，说明：

1. 当前模式；
2. 最高风险；
3. 如何证明完成；
4. 重复失败时如何停止；
5. 本轮不会做什么。

新会话还会回报规则版本与角色 digest，作为「规则已加载」的证明。Self-Test 只证明 Agent 读到了约束，不等于功能完成。真实交付仍然必须给出测试命令、dry-run、截图、日志，或明确标注“未验证”。

### 5. 在本地工作台看进展

```bash
harness observe service install   # 常驻服务，127.0.0.1:6425
harness observe service status
```

打开 `http://127.0.0.1:6425/`，看项目目标、版本路线、五角色办公室和产物。

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
harness observe status
```

## 它会改哪些文件

| 操作 | 可能写入的位置 | 目的 | 回滚方式 |
|---|---|---|---|
| `harness install` | `~/.mick-harness`、`~/.local/bin/harness` | 安装全局 Harness 和 CLI | 删除目录和 symlink |
| `harness agents sync/migrate` | `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`、四个受管命令 Skill 链接 | 原子注入或迁移 managed loader，并让 Codex / Claude Code 发现 Harness 命令薄适配 | 使用同目录 `.mick-harness.bak`、删除 `MICK-HARNESS-GLOBAL` 标记块，或移除指向 Harness 的 `harness-*` Skill 链接 |
| `harness agents hooks` | `~/.claude/settings.json`、`~/.codex/hooks.json` | 接入 session/turn 生命周期回写 | 使用同目录 `.mick-harness.bak` 或删除命令含 `harness-observe-hook.py` 的 Harness Hook 项 |
| `harness init` | 项目内 `AGENTS.md`、`.harness/`、`.gitignore` | 项目挂载 Harness | 删除 `.harness`；移除 `AGENTS.md` symlink 或 `HARNESS:BEGIN` 标记块 |
| `harness init --full` | 项目内 `.harness-config.yaml` | 启用完整配置和检查 | 删除该配置文件 |
| `harness observe init` | 项目内 `.harness-runtime/` | 保存 Agent 工作事件账本和可重建 snapshot | 停止 `watch` 后删除 `.harness-runtime/` |
| `harness observe service install` | `~/Library/LaunchAgents/com.mick.harness.observer.plist`、`~/.local/state/mick-harness/observer/` | 在 `127.0.0.1:6425` 自动启动并保活本地工作服务器与统一项目工作台 | `harness observe service uninstall` |
| `harness brain install` | `~/.brain`、可选 Claude hook/LaunchAgent | 创建 Brain 和启用同步 | 删除 Brain 目录或关闭对应 hook |

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
| 跨项目统一进度 | 支持 | 所有 `harness init` 项目进入 6425 本地工作台。 |
| Agent 工作自动回写 | 条件支持 | Claude/Codex 执行 `harness agents hooks` 并在新会话确认 Hook 后自动回写；结构化角色工作仍由注入规则调用 `harness observe emit`，服务离线时进入本地队列。 |
| 自动改写 Harness 规则 | 不支持 | 只生成进化提案，由人 review 后合并。 |

换句话说：Harness 不是魔法强制器，而是一套**先验注入 + 后验检查 + 长期记忆 + 人工门禁**的协作系统。

## 支持的入口

| 场景 | 推荐方式 | 当前状态 |
|---|---|---|
| Claude / Claude Code | `harness agents sync` + `harness agents hooks` | Tier 1；支持 managed loader、生命周期回写和新会话加载证明。 |
| Codex / Codex CLI | `harness agents sync` + `harness agents hooks` | Tier 1；需在 `/hooks` 信任 Hook，之后由新会话提供加载证明。 |
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

Mick Agent Harness 由五层组成：

| 层 | 作用 | 典型文件/命令 |
|---|---|---|
| Global Harness | 安装在本机的一套公共规则和工具 | `~/.mick-harness`、`harness install` |
| Agent Loader | 注入到 Code Agent 的全局入口 | `harness agents sync`、`harness export codex` |
| Project Manifest | 项目里的最小入口，指向全局 Harness | `AGENTS.md`、`.harness/` |
| Local Work Server | 接收并聚合所有已注入项目的工作事件 | `127.0.0.1:6425`、`harness observe service` |
| Private Brain | 私有长期记忆和规则进化信号 | `~/.brain`、`harness brain install` |

推荐形态：

```text
一台机器安装一次 Harness
  -> 每个项目运行一次 harness init
  -> 每个 Agent 通过 loader 或 export 读取同一套规则
  -> Agent lifecycle 与结构化工作摘要回写本地工作服务器
  -> 在 6425 统一工作台查看项目目标、当前版本和五角色办公室
  -> 点击角色阅读需求上下文、决策、执行记录与交付物
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
harness observe service status
harness update
```

| 命令 | 用途 |
|---|---|
| `harness doctor [--json] [dir]` | 一次检查安装、项目、Agent、Brain、Observer 与 audit，并给出下一步。 |
| `harness check [dir]` | 检查项目 Harness / Brain / 规则生成状态。 |
| `harness report [dir]` | 查看 `plan.md` 进度、阻塞和验证状态。 |
| `harness metrics [dir]` | 聚合完成率、验证覆盖率和 audit 信号。 |
| `harness observe service status` | 检查自动启动的 Mick Harness 本地工作服务器、6425 统一工作台、接收与扫描状态；详见 [Observer 文档](docs/OBSERVE.md)。 |
| `harness observe service [install\|start\|stop\|restart\|status\|logs\|uninstall]` | 管理本地后台服务生命周期。 |
| `harness observe [init\|sync\|status\|replay\|watch\|hook-config\|emit]` | 整理项目目标与需求、重放进展、启动临时工作台、配置 Agent Hook 或回写结构化角色工作。 |
| `harness update` | 更新全局 Harness、重新生成规则、刷新注册项目、同步 Agent loader。 |
| `harness agents scan` | 查看本机可自动管理的 Agent 入口。 |
| `harness agents doctor [--json]` | 分层诊断发现、注入、Hook 配置和仍缺少的真实证据。 |
| `harness agents sync` | 原子同步 managed loader 与四个命令 Skill；同名用户 Skill 不覆盖，先用 `--dry-run` 预览。 |
| `harness agents migrate` | 清理旧 Harness marker 并迁移到当前 Loader；先用 `--dry-run`。 |
| `harness agents hooks` | 保留原配置并接入 Tier 1 生命周期回写；先用 `--dry-run`。 |

### 用角色办公室查看项目进展

项目首页把信息分成三层：`docs/PROJECT.md` 记录稳定项目目标，`docs/VERSIONS.md` 记录当前版本目标与需求归属，`plan.md` 保留技术执行步骤。这样版本变化不会覆盖项目的长期方向。

PM、设计、开发、测试、Review 五个角色固定显示在办公室中。角色状态只来自真实工作事件；当前流转会高亮，点击角色可以查看其需求上下文、关联决策、执行记录和交付物。真实 `handoff.created` 与 work round 的建议 `next_role` 会分别标明，不会把建议伪装成已经接手。

### 在工作台阅读产物与版本路线

Agent 交付文档、代码或报告时，可以把项目相对路径一并回写：

```bash
harness observe emit work.round_completed --ref task-39-turn-1 --role Executor \
  --requirement task-39 --summary "产物阅读器已验证" \
  --artifact docs/OBSERVE.md --artifact scripts/harness-observe.py
```

打开 `http://127.0.0.1:6425/`，进入项目后：

- “产物”页把 Markdown 渲染成阅读页面，把 Python 等源代码显示为可折叠、可滚动并带行号的代码块；
- “版本规划”页读取 PM 维护的 `docs/VERSIONS.md`，展示每个版本的目标和需求清单；
- 同一页面读取真实 Git 状态，显示当前分支、本地分支、Tag 和未提交改动，让不熟悉 Git 的用户也能理解项目所在位置。

工作台只读取已登记的项目内文本产物，拒绝路径穿越、项目外软链接、二进制文件和大文件。Git 能力也是只读的：不会创建、切换、合并或删除分支，不会打 Tag 或 push。完整格式和安全边界见 [Observer 文档](docs/OBSERVE.md)。

## Advanced: Private Brain

Brain 是私有长期记忆，默认放在 `~/.brain`，也可以配置成用户自己的私有 Git 仓库；公开 Harness 不预置任何人的 Brain 地址、身份或记忆内容。

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

如果用户还没有 Brain，`harness brain install` 会自动创建本地 `~/.brain` 骨架。若配置了私有仓库但暂时无法 clone，也会降级成本地 fallback，不阻断 `harness init --full`、`harness check` 或原有 Harness 工作流。升级前已经使用旧目录的安装会继续读取旧数据，但新安装不会再创建旧命名目录。

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
- lifecycle 自动化取决于各 Agent 的 Hook 能力；没有 Hook 的 Agent 通过注入规则调用 `harness observe emit` 回写结构化工作摘要。
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

## 需求与路线

正式版本、进行中需求和 Backlog 统一记录在 [版本规划](docs/VERSIONS.md)。README 不再维护第二份“下一版本重点”，避免同一需求出现两个互相冲突的状态源。
