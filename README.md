# Mick Harness Rules

让你的 AI 编程助手按你的方式工作。不侵入项目、不依赖特定工具。

---

## 阶段一：安装（新机器一次，30 秒）

```bash
harness install
harness version
```

如果你还没有 `harness` 命令，先手动引导一次：

```bash
git clone https://github.com/MickMi/mick_harness_rules.git ~/.mick-harness
mkdir -p ~/.local/bin
ln -sf ~/.mick-harness/bin/harness ~/.local/bin/harness
~/.local/bin/harness install
```

安装会自动扫描本机可用的文件型 Code Agent 入口，并注入 Harness loader。当前支持：

| Agent | 自动入口 |
|---|---|
| Claude / Claude Code | `~/.claude/CLAUDE.md` |
| Codex / Codex CLI | `~/.codex/AGENTS.md` |

扫描和注入也可以手动运行：

```bash
harness agents scan
harness agents sync
```

---

## 阶段二：加载到 AI 工具（默认自动）

`harness install`、`harness init`、`harness update` 都会自动执行 `harness agents sync`：

- 已识别且有文件型全局入口的 Agent，会自动注入或刷新 managed block。
- 已经由 Harness 管理的旧 block，会自动替换成最新版本。
- 不可安全识别的旧手工粘贴内容不会强删；先用 `harness agents scan` 看状态，再手动清理。

需要复制到不支持文件注入的工具时，再用手动导出：

| 场景 | 命令 |
|---|---|
| Codex loader | `harness export codex \| pbcopy` |
| 通用 Code Agent | `harness export agent \| pbcopy` |
| IDE Plugin | `harness export ide \| pbcopy` |
| 纯 API 调用 | `harness export api \| pbcopy` |
| 全部导出 | `harness export all` |

需要完整 Playbook 时加 `--full`：`harness export agent --full`

---

## 阶段三：项目初始化（每个项目一次）

```bash
cd my-project

harness init              # 最小：AGENTS.md + .harness/
harness init --full       # 加 .harness-config.yaml + Brain
harness init --all-rules  # 加 Cursor/Windsurf 等旧工具入口
```

项目多出三个文件：`.harness/`（symlink）、`AGENTS.md`（symlink）、`.harness-config.yaml`。前两个不占 git，只有 config 需要 commit。

如果项目之前装过旧版 Harness，不需要手动 `rm -rf`：

- `.harness/` 是兼容的旧 Harness checkout：`harness init` 会自动移到 `.harness.legacy-<timestamp>`，再挂载全局 symlink。
- `.harness/` 是未知目录：Harness 不会自动删除，只会提示你人工确认。
- 旧的 Harness 管理 symlink / 注入块会在 `harness init` 或 `harness update` 时自动刷新或清理。

---

## 阶段四：日常开发

```bash
harness report     # 看当前 plan 进度、阻塞、验证状态
harness metrics    # 看完成率、验证覆盖率、scope creep
harness check      # 验证脚手架完整性
harness update     # 拉新版 Harness → 刷新注册项目 → 自动扫描并注入本机 Agent
```

Agent 打开项目时自动读 `AGENTS.md`。Tripwire 第 11 行就位——改动文件前先读、先查 plan、没验证 ≠ 完成。闲聊不触发。

更新时的自动化顺序：

1. 拉取最新 Harness。
2. 重新生成规则。
3. 刷新所有注册项目的规则入口。
4. 自动扫描 Claude / Codex 等本机 Code Agent。
5. 自动注入或刷新可安全管理的全局 loader。

---

## 阶段五：Brain 记忆飞轮

```bash
harness brain status    # 看 Hook / 定时 / Audit 状态
harness brain install   # 一键装 SessionEnd + 每日定时同步
```

之后每次 Claude Code 会话结束 → 自动蒸馏到 Brain。每天凌晨 3:07 批处理兜底。Session → Project → Global 三层蒸馏周末自动运行。

```bash
harness brain sync      # 手动触发会话蒸馏
harness brain daily     # 手动触发日终批处理
```

---

## 阶段六：规则进化飞轮

```bash
# 1. 积累 audit 信号
harness-audit.sh --since HEAD~5 --log

# 2. 生成规则进化提案
harness brain evolve

# 3. 人工 review 提案 → 改 core.md → generate.sh → 部署
#    下次 audit 验证同 tag 频次下降
```

飞轮：使用 AI → 会话自动沉淀 → Brain 蒸馏 → 发现 Harness 失效模式 → 生成提案 → 人工合并 → 验证频次下降。

---

## 验证 Agent 是否生效

对你的 AI 说：

> 请按 Harness Self-Test 用 5 句话证明你理解当前任务约束。

合格回答绑定当前任务。**泛泛复述规则视为未通过。**

---

## 没有终端？

复制下面 3 句话，粘贴到 AI 工具的自定义指令位置：

```text
1. 改动任何文件前，先读它的当前内容。凭记忆覆盖 = 违约。
2. 改动文件前检查 plan.md。存在且本轮要改文件 → 按 plan 执行。纯讨论无需检查。
3. 没验证 ≠ 完成。每条改动附带验证证据。禁止说"应该好了/可以了/完成了"。
```

---

## 它做了什么

Harness 解决 AI 编码的三个通病：**没判断标准**（AI 不会按你的证据纪律工作）、**没记忆**（每次对话从零开始）、**没闭环**（交互细节和外部系统反复撞墙）。

它是一组**单源规则**（`rules/core.md`）+ 一套**脚本工具**（`harness` CLI）。改规则 → 跑 `harness update` → 所有项目同步。
