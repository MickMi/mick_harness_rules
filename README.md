# Mick Harness Rules

一套可被 N 个项目复用的 Vibe Coding 脚手架，引入即生效。不侵入项目代码，不污染项目仓库。像 `.env` 一样存在。

它围绕两个核心能力展开：

- **Harness（工程护栏）**
  - `.cursorrules` 全局编码规范
  - 多 Agent 角色协作（PM / Designer / QA / Reviewer / Dev）
  - 强制需求审查门禁
  - Git 工作流 + CI/CD 护栏
- **Brain（个人记忆）**
  - 三层记忆模型（Global / Project / Session）
  - 自动蒸馏 + 检索优先
  - 多 IDE 自动写入

## 这个项目解决什么问题

用 AI 写代码的时候，普遍会遇到三个问题：

1. **没有规范** — AI 写出的代码风格不一致，没有防御性编程，没有 TDD，没有架构约束
2. **没有记忆** — 每次对话都是从零开始，之前踩过的坑、做过的决策全部丢失
3. **没有流程** — 需求模糊就直接开始写代码，没有审查，没有角色分工

这个脚手架的设计是：

- **Harness 解决 1 和 3** — 通过规则文件和 Agent 角色模板，强制 AI 遵循编码规范和协作流程
- **Brain 解决 2** — 通过三层记忆模型，让经验跨对话、跨项目持久化

## Fork 即用

这个仓库支持 **fork 即开箱即用**。 fork 或 clone 到你的仓库，不需要手动清空 brain 数据或修改任何配置：

### 方式 A：Fork（推荐）

```bash
# 1. Fork 仓库到自己的 GitHub 账号
# 2. Clone 自己的 fork
git clone https://github.com/YOUR_NAME/mick_harness_rules.git ~/mick_harness_rules
chmod +x ~/mick_harness_rules/*.sh

# 3. 初始化到自己的项目（自动检测 fork 并重置 brain）
~/mick_harness_rules/vibe-init.sh /path/to/your/project
```

### 方式 B：直接 Clone + `--fresh`

如果不想 fork，直接 clone 原仓库也可以。用 `--fresh` 参数一键清空别人的记忆：

```bash
git clone https://github.com/MickMi/mick_harness_rules.git ~/mick_harness_rules
chmod +x ~/mick_harness_rules/*.sh

# --fresh 会无条件清空 brain 数据，给你一个干净的起点
~/mick_harness_rules/vibe-init.sh --fresh /path/to/your/project
```

### 自动检测机制

`brain-init.sh` 使用三层检测确保新用户拿到干净的 brain：

| 检测维度 | 触发条件 | 行为 |
|----------|----------|------|
| **`--fresh` 参数** | 用户显式传入 | 无条件清空 brain，记录新 owner |
| **Git remote owner** | `.brain-owner` 中的 owner 与当前 Git remote 不一致 | 自动清空 brain |
| **系统用户名** | `.brain-owner` 中的 system_user 与当前 `whoami` 不一致 | 交互式询问是否清空 |
| **首次运行 + 非空 brain** | 无 `.brain-owner` 但 brain 中有数据 | 交互式询问是否清空 |

整个过程零手动操作（或最多一次 Y/n 确认）。新用户拿到的是完整的 Harness 规范 + 干净的 Brain，可以立即开始积累自己的记忆。


## 一图看懂

```mermaid
flowchart TD
    subgraph Harness["🛡️ Harness（工程护栏）"]
        CR[".cursorrules<br/>编码规范 + 角色路由"]
        PM[".prompts/pm_agent.md<br/>需求审查门禁"]
        QA[".prompts/qa_agent.md<br/>测试策略"]
        RV[".prompts/reviewer_agent.md<br/>代码审查"]
        OC[".prompts/orchestration.md<br/>角色编排协议"]
    end

    subgraph Brain["🧠 Brain（个人记忆）"]
        S["Session 层<br/>原始对话摘要<br/>90 天归档"]
        P["Project 层<br/>项目专属决策<br/>项目存续期"]
        G["Global 层<br/>跨项目偏好<br/>永久保留"]
        S -->|"daily compound"| P
        P -->|"weekly compound"| G
    end

    User["👤 用户项目"] -->|"vibe-init.sh"| Init["🚀 一键初始化"]
    Init -->|"symlink .harness/"| Harness
    Init -->|"brain-init.sh"| Brain

    CR -->|"AI 遵循规范"| Code["⚙️ 代码实现"]
    PM -->|"需求审查 2-3 轮"| Code
    Brain -->|"brain-search.sh"| Code
    Code -->|"brain-push.sh"| S
```

## 核心架构

这个项目采用**双仓库模型**（ADR-016）：

| 仓库 | 可见性 | 回答的问题 | 对应内容 |
|------|--------|-----------|----------|
| **Harness**（`mick_harness_rules`） | 公开 | "怎么做" | `.cursorrules`、`.prompts/`、`docs/`、脚本工具 |
| **Brain**（`mick_brain`） | 私有 | "知道什么" | `global/`、`projects/`、`sessions/`、`MEMORY.md` |

挂载方式：

- Brain 仓库 clone 到 `~/.mick-brain/`，harness 中的 `brain/` 通过 symlink 指向它
- 通过 symlink（`.harness/`、`.cursorrules`、`.prompts/`）引入到目标项目，不复制文件
- `.gitignore` 自动隔离，所有脚手架内容不会出现在项目的 Git 历史中
- 独立于任何业务项目的发布节奏

```
mick_harness_rules/ (公开)         ~/.mick-brain/ (私有)
├── .cursorrules                   ├── global/preferences.md
├── .prompts/                      ├── global/gotchas.md
├── brain-init.sh                  ├── projects/<slug>/learnings.md
├── brain-push.sh                  ├── sessions/YYYY-MM-DD/
├── brain-resolve.sh               ├── MEMORY.md
├── brain/ → symlink               ├── .brain-owner
└── ...                            └── .gitkeep
```
## 三层记忆

### Session 层

- 位置：`brain/sessions/YYYY-MM-DD/`
- 保留：90 天后自动归档
- 内容：每次 AI 对话中产生的 gotcha、decision、preference、env 记录
- 写入：AI 自动触发或 `brain-push.sh` 手动写入

### Project 层

- 位置：`brain/projects/<slug>/`
- 保留：项目存续期
- 内容：项目专属的技术选型、架构决策、踩坑记录
- 来源：从 Session 层蒸馏（daily compound）

### Global 层

- 位置：`brain/global/`
- 保留：永久
- 内容：跨项目通用的编码偏好、工具链选择、通用踩坑记录
- 来源：从 Project 层蒸馏（weekly compound）

### 蒸馏

```
Session（原始素材）
    ↓ daily compound（≥5 条未蒸馏条目触发）
Project（项目级精华）
    ↓ weekly compound（本周 ≥3 条新增触发）
Global（跨项目通用经验）
```

由 `brain-compound.sh` 执行。支持智能触发、相似检测、合并策略、分类路由和 `--dry-run` 预览。

### 检索

不全量读取记忆文件。推荐顺序：

1. `brain-search.sh <keyword>` — ripgrep 精准搜索
2. 定向读取特定文件片段
3. 只有前面都不够时，才读完整文件

## Agent 角色

内置 5 个 Agent 角色，通过 `.cursorrules` 中的智能路由自动匹配：

| 角色 | 文件 | 职责 |
|------|------|------|
| **PM Agent** | `.prompts/pm_agent.md` | 需求审查、三轮追问、输出确认清单 |
| **Designer Agent** | `.prompts/designer_agent.md` | UI/UX 设计、设计代币、组件规格 |
| **QA Agent** | `.prompts/qa_agent.md` | 测试策略、用例矩阵、质量门禁 |
| **Reviewer Agent** | `.prompts/reviewer_agent.md` | 代码审查、逻辑完备性、安全审计 |
| **Dev Agent** | `.cursorrules` | 编码实现、调试、架构设计（默认角色） |

### 需求审查门禁

实质性需求（新功能、重构、架构变更）必须先经过 PM 角色的审查：

1. **第 1 轮**：目标与边界
2. **第 2 轮**：技术约束与风险
3. **第 3 轮**：输出结构化需求确认清单

用户确认清单前，禁止任何 Agent 编写实现代码。

豁免：单文件 Bug 修复、文档更新、格式化、用户明确说"跳过审查"。

## 仓库内容

```
mick_harness_rules/
├── .cursorrules              # 全局编码规范 + 智能角色路由 + Brain 自动写入协议
├── .brain-config.yaml        # Brain 配置（仓库地址、保留策略、搜索引擎）
├── .gitignore                # 忽略 brain 个人数据（双仓库隔离）
├── .prompts/                 # Agent 角色模板
│   ├── orchestration.md      # 角色编排协议
│   ├── pm_agent.md           # PM 角色（需求审查官）
│   ├── qa_agent.md           # QA 角色
│   └── reviewer_agent.md     # Reviewer 角色
├── brain/                    # → symlink 到 ~/.mick-brain/（私有 brain 仓库）
├── brain-init.sh             # 一键挂载 harness + brain 到目标项目
├── brain-resolve.sh          # 共享库：解析 brain 数据路径（双仓库/单仓库自动适配）
├── brain-migrate.sh          # 一次性迁移脚本（单仓库 → 双仓库）
├── brain-check.sh            # 验证脚手架完整性（12 项检查，含 brain 仓库连接）
├── brain-push.sh             # 向 brain 写入记忆（CLI / 剪贴板 / 交互模式）
├── brain-search.sh           # 基于 ripgrep 的记忆检索
├── brain-compound.sh         # 智能蒸馏（Session → Project → Global）
├── brain-gc.sh               # 容量治理（归档 + 清理）
├── brain-rules-template.md   # 多 IDE 通用的自动写入规则模板
├── vibe-init.sh              # Vibe Coding 脚手架初始化（自动链式调用 brain-init）
├── docs/
│   ├── architecture.md       # Harness 自身的系统架构文档
│   ├── architecture-template.md  # 新项目架构模板（init 时复制到目标项目）
│   └── ci_cd_templates.md    # CI/CD 模板库
├── MEMORY.md                 # 框架级架构决策记录（ADR）
└── TODO.md                   # 任务清单与状态流转
```



## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/MickMi/mick_harness_rules.git ~/mick_harness_rules
chmod +x ~/mick_harness_rules/*.sh
```

### 2. 初始化目标项目

```bash
# 完整初始化（Vibe 脚手架 + Brain 挂载）
~/mick_harness_rules/vibe-init.sh /path/to/your/project

# 新用户：清空原作者的 brain 数据 + 初始化
~/mick_harness_rules/vibe-init.sh --fresh /path/to/your/project

# 或者只挂载 Brain（项目已有自己的规范）
~/mick_harness_rules/brain-init.sh /path/to/your/project
~/mick_harness_rules/brain-init.sh --fresh /path/to/your/project  # 新用户
```

`brain-init.sh` 会自动：

1. **Phase 0.5**：检测 `.brain-config.yaml` 中的 brain 仓库配置，自动 clone 到 `~/.mick-brain/` 并建立 symlink
2. **Phase 0**：检测 brain 所有权，fork 用户自动重置
3. **Phase 1**：创建 `.harness/` symlink
4. **Phase 2**：注入 `.cursorrules`、`.prompts/` 等 IDE 规则
5. **Phase 3**：配置 `.gitignore` 隔离
6. **Phase 4**：运行 `brain-check.sh` 验证完整性（12 项检查）

`vibe-init.sh` 在此基础上额外部署 `docs/`、CI/CD 模板、`MEMORY.md`、`TODO.md` 等项目专属文件。

初始化是非破坏式的。已存在的文件备份为 `.bak`，symlink 不覆盖，重复运行不出错。

> **安全设计**：`.cursorrules`、`.prompts/` 等包含 Agent prompt 的文件全部通过 symlink 引用，并被 `.gitignore` 隔离。目标项目发布到 Git 时，不会携带任何脚手架内容。

### 3. 日常使用

```bash
# 搜索记忆
.harness/brain-search.sh "ripgrep"

# 写入记忆
.harness/brain-push.sh --layer session --source cursor "gotcha: xxx"

# 运行蒸馏
.harness/brain-compound.sh --mode auto

# 容量治理
.harness/brain-gc.sh --report

# 验证完整性
.harness/brain-check.sh
```

## 多 IDE 支持

`brain-init.sh` 会自动检测并注入自动写入规则：

| IDE | 规则文件 | 注入方式 |
|-----|---------|---------|
| Cursor | `.cursorrules` | symlink（`.gitignore` 隔离） |
| Agent Prompts | `.prompts/` | symlink（`.gitignore` 隔离） |
| Windsurf | `.windsurfrules` | 追加 |
| Trae | `.trae/rules` | 追加 |
| VS Code Copilot | `.github/copilot-instructions.md` | 追加 |

AI 会在以下事件发生时自动写入记忆：

- 🐛 **Gotcha** — 非显而易见的 Bug、API 怪癖、库限制
- 🏗️ **Decision** — 选择了某个库/方案，做了取舍
- 💡 **Preference** — 用户表达了编码风格、命名约定偏好
- ⚠️ **Environment** — OS 特定行为、CI/CD 约束、版本兼容问题

## 容量治理

`brain-gc.sh` 防止记忆无限膨胀：

- Session 超过 90 天自动归档到 `.archive/sessions/`
- MEMORY.md 超过 500 行自动归档旧条目到 `MEMORY.archive.md`
- `--report` 输出各层文件数、大小、过期状态

## 适合什么场景

- 一套可复用的 AI 编码规范，引入任何项目即生效
- 跨对话、跨项目的持久化记忆
- 多 Agent 角色协作，有需求审查门禁
- 本地优先、文件优先、不依赖云服务

它是一个 **file-first**、**local-first** 的个人基础设施。

## 设计原则

| 原则 | 说明 |
|------|------|
| `.env` 模式 | symlink 挂载，`.gitignore` 隔离，**零泄漏**——目标项目 Git 中不含任何脚手架内容 |
| 双仓库隔离 | Harness（公开）+ Brain（私有），fork 时天然不带个人记忆 |
| 验证闭环 | 加载 → 检查 → 拦截 → 报告 |
| 检索优先 | 禁止全量读取，优先 ripgrep |
| 优雅降级 | 有高级工具用高级工具，没有就回退；无 brain 仓库时 fallback 到本地目录 |
| 幂等挂载 | 重复运行不出错 |
| 需求先行 | 实质性需求必须经过多轮审查 |
| Fork 即用 | fork 用户首次 init 自动检测并重置 brain，零手动操作 |

---

## 附录 A：Brain 双仓库模型详解

### 为什么需要双仓库？

Brain 存储的是个人记忆（编码偏好、踩坑记录、项目经验），这些数据：
- **需要多机同步**：你可能在 MacBook、台式机、公司电脑上工作
- **不应公开**：fork 你的 harness 仓库的人不应该看到你的个人记忆

单仓库模型无法同时满足这两个需求。双仓库模型将 Harness（公开工具）和 Brain（私有记忆）分离，各自通过 Git 同步。

### Brain 仓库结构

```
mick_brain/ (私有仓库)
├── global/
│   ├── preferences.md    # 跨项目编码偏好
│   └── gotchas.md        # 跨项目踩坑记录
├── projects/
│   └── <slug>/
│       └── learnings.md  # 项目专属经验
├── sessions/
│   └── YYYY-MM-DD/
│       └── <source>.md   # 原始对话摘要
├── MEMORY.md             # 个人记忆与 ADR
├── .brain-owner          # 所有权标记
└── .gitkeep
```

### 连接机制

`brain-init.sh` 在 Phase 0.5 自动完成：

1. 读取 `.brain-config.yaml` 中的 `brain_repo.remote` 和 `brain_repo.local_path`
2. 如果 `~/.mick-brain/` 不存在，自动 `git clone`
3. 在 harness 仓库中创建 symlink：`brain/` → `~/.mick-brain/`
4. 所有 brain-*.sh 脚本通过 `brain-resolve.sh` 自动解析正确的路径

### 多机同步流程

```
机器 A                              机器 B
├── ~/project-x/                    ├── ~/project-y/
│   └── .harness/ → harness repo    │   └── .harness/ → harness repo
├── ~/mick_harness_rules/           ├── ~/mick_harness_rules/
│   └── brain/ → ~/.mick-brain/     │   └── brain/ → ~/.mick-brain/
└── ~/.mick-brain/ (git sync)       └── ~/.mick-brain/ (git sync)
         ↕                                    ↕
    github.com/MickMi/mick_brain (private)
```

每次 `brain-push.sh` 写入记忆后，自动 commit + push 到 brain 仓库。
在另一台机器上运行 `brain-init.sh` 时，自动 pull 最新数据。

### 向后兼容

如果 `.brain-config.yaml` 中没有配置 `brain_repo.remote`，所有脚本自动 fallback 到本地 `brain/` 目录（单仓库模式）。这意味着：
- Fork 用户不需要创建自己的 brain 仓库也能正常使用
- 只是记忆不会跨机器同步

### 新机器初始化步骤

在一台新机器上从零开始：

```bash
# 1. Clone harness 仓库（公开）
git clone https://github.com/MickMi/mick_harness_rules.git ~/mick_harness_rules
chmod +x ~/mick_harness_rules/*.sh

# 2. 初始化到你的项目（brain 仓库会自动 clone）
~/mick_harness_rules/brain-init.sh /path/to/your/project

# brain-init.sh 会自动：
#   - 读取 .brain-config.yaml 中的 brain_repo 配置
#   - Clone brain 仓库到 ~/.mick-brain/
#   - 创建 symlink: brain/ → ~/.mick-brain/
#   - Pull 最新记忆数据
#   - 完成所有初始化
```

你不需要手动 clone brain 仓库，`brain-init.sh` 会自动处理一切。
