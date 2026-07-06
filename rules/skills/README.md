# Skills 层

> Skill 是 Kernel 与 Playbook 之外的第三层：**把每次都要做、每次都不希望 AI 临场发挥的固定动作，做成剧本**。
> Rule 说"必须做"，Skill 说"具体怎么做"。

## 定位

| 层 | 语气 | 作用 |
|---|---|---|
| Kernel (`core.md`) | "什么绝对不能做" | 底线纪律 |
| Playbook (`extended.md`) | "高风险场景怎么应对" | 操作手册 |
| **Skills (`skills/`)** | **"这个动作每次这样跑"** | **可复用剧本** |
| Tooling（项目配置） | "机器怎么强制" | lint / test / CI |

Skill 不是"文档"，而是能被 Rule 引用、被 Executor 调用的可复用步骤集。核心特征：
- **动作固定**：每次都要做、命令基本不变
- **临场发挥有代价**：AI 每次自由拼命令 = 迟早出错
- **值得沉淀**：跨任务、跨需求、跨对话都用得上

编译、测试、事后验证、发布、签名、Preflight 检查——这些是 Skill 的典型选民。**"帮我优化下这段代码"不是 Skill**，那是任务。

## Harness 只提供框架，不提供内容

harness 仓库里**只放**：
- 本 README（Skill 是什么、怎么写、怎么被引用）
- `_template.md`（骨架）
- 按需的极少量通用 Skill（例如 secret-scan）

**具体 Skill（编译什么、测试什么、部署到哪）由项目自己在 `.harness/skills/` 或项目内 `rules/skills/` 里补**。技术栈差异太大，硬塞会变成噪音。

## 什么时候写 Skill

出现下面任一信号才写，不要预防性堆积：

- 同一个动作已经手写过 2 次以上
- AI 每次跑都要重新推导命令 / 路径 / 参数
- 出过一次因为"临场发挥"导致的事故
- 有明确的失败模式需要固定处理（例如"编译失败必须看 xxx 日志"）

**反面**：不要为"看起来重要"的动作写 Skill。没被反复踩过的 Skill 会变成没人维护的死文档。

## Skill 文件结构

见 [`_template.md`](_template.md)。要点：

- **一个 Skill 一个文件**：`skills/<action-name>.md`
- **命名用动词短语**：`compile.md` / `run-tests.md` / `post-verify.md` / `release-prod.md`
- **必备 6 段**：目的 / 何时触发 / 前置条件 / 执行步骤 / 成功判定 / 失败处理
- **Frontmatter 记版本和维护人**（可选，方便进化闭环追踪）

## Skill 如何被引用

Skill 不会自动生效——必须由某条 Rule / plan 步骤 / 角色契约显式引用它。三种主要方式：

### 1. Rule 引用（最常见）

在 `core.md` 或 `extended.md` 里点名：

```markdown
**7. 完成必须验证**：... 项目根若有 `.harness/verify.sh` 或等价入口，
Executor 完成一步必须调用 —— 具体步骤参见 `rules/skills/post-verify.md`。
```

### 2. Plan 步骤引用

Planner 写 plan.md 时直接写入：

```markdown
- [ ] 5. [运行] 执行 `rules/skills/run-tests.md` 里的完整测试流程，把结果贴回自检日志
```

### 3. 角色契约引用

在 `rules/roles/executor.md` 或类似角色文件里规定"完成本轮必须调用哪个 Skill"。

## Skill 与 verify.d 的关系

- **Skill = 人 / AI 读的剧本**：讲清楚"为什么这么做、失败怎么办、什么算过关"
- **verify.d/*.sh = 机器执行的检查项**：单一职责的可判定脚本，参见 [`docs/VERIFY-CONTRACT.md`](../../docs/VERIFY-CONTRACT.md)

一个 `post-verify.md` Skill 通常调用 `.harness/verify.sh`（它内部编排 verify.d/ 里的所有 checker）。**Skill 是入口和上下文，verify.d 是原子检查**。

## 进化：Skill 也要能删

跟 rules 一样（见 `extended.md §10.9`），Skill 长期没被引用 / 内容与实际操作脱节 / 项目已经把它替换成 CI 门禁 → 降级或删除。**只加不删 = Skill 目录臃肿到没人翻**。

半年一次 review：
- 每个 Skill 最近 3 个月被引用过吗？
- Skill 里的命令、路径、参数还是当前项目的真相吗？
- 有没有更硬的门禁（CI / hook / verify.d checker）已经覆盖了它？→ 可以退役

## 起步建议

**别一开始就写 5 个 Skill**。按顺序：

1. 挑一个**每次都痛、每次都想让 AI 别乱发挥**的动作
2. 写成 `skills/<name>.md`（照 `_template.md`）
3. 在最相关的一条 Rule 里加一句 "见 `rules/skills/<name>.md`"
4. 用两三次，看是否真的稳定下来
5. 稳了再写第二个

Skill 是长出来的，不是设计出来的。
