# Verify Contract — 事后验证的可维护契约

> Harness 里"完成必须验证"的落地契约。核心不是"提供一个大脚本"，而是**约定一套架构 + 进化机制，让 verify 能力跟着项目一起长，而不是一次性写全**。
> 参见：`core.md 铁律 7`、`extended.md §3.1 Baseline First / §10.9 规则自进化闭环`。

## 为什么需要契约（先讲问题）

如果只丢一个 `verify.sh` 大脚本给项目，会经历三种典型退化：

1. **臃肿**：20 条检查变 200 条，跑一次 5 分钟，AI 开始想办法"局部跑"
2. **假阳性**：过时的检查项没人删，AI 学会说"这条 warning 可以忽略" → 又回到嘴解释
3. **漏检**：新功能上线没人加对应检查，AI 在检查盲区放飞

契约要解决的不是"怎么写脚本"，而是**如何让脚本长期与项目真相对齐**。

## 目录结构约定

```
项目根/
├── .harness/
│   ├── verify.sh              # orchestrator：只做调度、聚合、退出码
│   ├── verify.d/              # 每条检查一个独立脚本（活跃）
│   │   ├── 10-secrets.sh
│   │   ├── 20-compile.sh
│   │   ├── 30-test.sh
│   │   ├── 40-no-hardcoded-ui.sh
│   │   └── ...
│   ├── verify.disabled/       # 停用但不删（方便回溯 + 进化审计）
│   └── verify.stats           # 每次运行的 checker 触发统计（可选）
```

**核心分离**：`verify.sh` 只调度，不做业务判断；每一条业务检查是独立文件。加/删检查 = 加/删文件，不动主脚本。

## Checker 命名规范

`NN-<category>-<what>.sh`

- `NN`：两位数字，控制执行顺序（10/20/30... 留空隙插新的）
- `<category>`：`secrets` / `compile` / `test` / `lint` / `style` / `deps` / `docs`
- `<what>`：具体检查的东西

例：
- `10-secrets-scan.sh`
- `20-compile-main.sh`
- `30-test-unit.sh`
- `40-lint-xaml-cn.sh`
- `50-style-no-hardcoded-ui.sh`

## Checker 的执行契约

每个 `verify.d/*.sh` 必须遵守：

### 输入

- 无参数模式：整仓扫描
- `--changed`：只检查本次改动涉及的文件（Executor 单步验证时用）
- `--tier fast|subsystem|release`：可选，checker 决定是否响应；旧项目可继续把 `--profile` 作为兼容别名

### 输出

- **stdout**：人读的进度、通过项
- **stderr**：失败详情（供 orchestrator 汇总）
- **exit code**：
  - `0` — 通过
  - `1` — 失败（本 checker 判定不通过）
  - `2` — 无法判定（缺前置条件、环境问题）—— 由 orchestrator 决定是否阻塞
  - `77` — 跳过（此 profile 不适用）

### 单一职责

一个 checker 只判一类事。**不允许一个脚本里塞 5 种检查**——那会退化成不可维护的大脚本，违背了拆分的初衷。

## Orchestrator（`verify.sh`）契约

`.harness/verify.sh` 只做四件事：

1. 依次执行 `verify.d/` 下所有 `.sh` 文件（按文件名字典序）
2. 聚合每个 checker 的 exit code
3. 支持 `--tier fast|subsystem|release`、`--changed`、`--only <name>`、`--skip <name>` 等 flag
4. 输出汇总（哪个 checker 失败、失败详情摘要、总用时）
5. 汇总退出码：任一 checker 返回 `1` → orchestrator 返回 `1`；有 `2` 且 `--strict-unknown` → 返回 `2`

**orchestrator 不做业务判断，只做调度**。业务逻辑全在 checker 里。

## v0.18.0 · 2026-08-19 · 三档验证与 Gate 复用

验证档位按“这次声明需要多少证据”选择，而不是一律跑发布全套：

| 档位 | 何时使用 | 最小覆盖 | 不能证明 |
|---|---|---|---|
| `fast` | 单文件、小逻辑、改动中快速反馈 | 与当前改动直接相关的最小测试或 checker | 整个子系统稳定、版本可发布 |
| `subsystem` | 一个完整能力交付或跨文件交互 | 该子系统全部测试、接口/交互合同和关键错误路径 | 全仓无回归、生成文件与发布状态正确 |
| `release` | 合并、部署、发版或用户明确要求最终 Gate | 全仓测试、生成一致性、diff 与发布所需检查 | 生产部署已经成功；部署仍需真实环境证据 |

Harness 仓库使用：

```bash
python3 scripts/harness-verify.py fast --subsystem brain
python3 scripts/harness-verify.py subsystem --subsystem observe
python3 scripts/harness-verify.py release
```

成功 Gate 会记录在未提交的 `.harness-runtime/verification-gates.json`。只有以下四项全部相同才能复用：

1. Git 已追踪、暂存和未追踪文件的内容指纹；
2. 操作系统、机器架构与 Python 版本；
3. 档位和子系统；
4. 实际命令列表。

任一项变化、上次失败或使用 `--force` 都必须重新执行。复用时输出 `REUSED` 和指纹；不能靠 Agent 记忆“刚才跑过”或用旧会话结论跳过验证。脚本只保留命令、环境摘要、指纹、时间和通过状态，不采集 Prompt、回复、模型思考过程或完整成功日志；失败输出仅用于当前终端诊断。

## 与 Skill 层的关系

- `rules/skills/post-verify.md`（Skill）—— 讲"什么时候跑、失败怎么办、成功怎么判定"，给人和 AI 读
- `.harness/verify.sh` + `verify.d/*` —— 机器执行的原子检查

Executor 完成一个 plan 步骤后：
1. 按 `post-verify.md` Skill 的剧本走
2. Skill 内部调用 `bash .harness/verify.sh --changed`
3. 结果贴回 `## 自检日志`

## 进化机制（这是契约的重点）

单靠"写好检查项"撑不住项目变大。verify 层必须接入 `extended.md §10.9` 的自进化闭环。

### Checker 从哪里来

**不是一开始设计好的**，而是从真实失败里长出来。这是 Debug Card 收尾必问一句的落地：

```
真实 bug / Debug Card
  ↓
"这类问题能不能变成自动检查？"
  ├─ 能 → 写 verify.d/NN-xxx.sh
  ├─ 不能自动判定但有明确规则 → 落成 Rule
  └─ 都不行 → brain-push 成 gotcha
```

Debug Card 修完必须走完这一步（`core.md 铁律 5`），不允许修完就走。

### Checker 触发频次统计

可选但推荐：`verify.sh` 每次运行把每个 checker 的 exit code 追加到 `.harness/verify.stats`：

```
2026-07-06T10:23:15Z  10-secrets-scan.sh  0
2026-07-06T10:23:15Z  20-compile-main.sh  0
2026-07-06T10:23:15Z  30-test-unit.sh     1
```

统计价值：
- 长期 0 触发的 checker → 候选删除（能力可能已被 AI 原生覆盖，或规则贬值）
- 频繁触发同一 checker 但每次都是同一个假阳性 → checker 本身要修
- 从未失败过的 checker → 是不是根本没被真实调用过？

### 进化含删除（重要）

跟 core.md 里 rules 的删除原则一样。verify.d 长期堆积不删，两年后没人敢跑全量。

半年一次 review：

- 每个 checker 最近半年触发过失败吗？
- 触发的失败是真实 bug 还是假阳性？
- 有没有更硬的门禁（CI / IDE / hook）已经覆盖了它？→ 可以退役到 `verify.disabled/`
- checker 里的路径、命令、正则还是当前项目的真相吗？

**长期 0 触发 + AI 已能原生规避 = 移到 `verify.disabled/`**。不删，只是不跑，保留历史。

## 项目分层建议

不同规模的项目起点不同：

| 项目规模 | 起步 checker 数 | 覆盖范围 |
|---|---|---|
| 个人项目 / 小工具 | 3 条 | secret / build / test |
| 中型项目 | 10-15 条 | + lint / 硬编码 / 文件同步 / API 契约 |
| 大型项目（如多模块 UI 工程） | 20+，按 profile 分组 | 用 `--profile ui/backend/build` 分片跑 |

**不要贪大**。文章第八章那个"20+ 检查项的总验证脚本"不是终点，是长了很久才长成的样子。你从 3 条开始，每次 Debug Card 后加 1 条，一年后自然长到合适的规模。

## Baseline First 与 verify

这两者一起用最有效（见 `extended.md §3.1`）：

```bash
# 改前
bash .harness/verify.sh --tier fast > /tmp/verify.before.log 2>&1

# ... 改代码 ...

# 改后
bash .harness/verify.sh --tier fast > /tmp/verify.after.log 2>&1

# diff
diff /tmp/verify.before.log /tmp/verify.after.log
```

新增的 FAIL / WARN 才是本轮引入的。历史遗留的问题不再能当挡箭牌。

## Bootstrap（新项目怎么起步）

harness 不硬塞 verify.sh 到每个项目，因为技术栈差异太大。**建议流程**：

1. 项目 `harness init --full` 后，在 `.harness/` 里放一个 `verify.sh.example` 模板
2. 用户拷贝重命名为 `verify.sh`，按项目实际填 `verify.d/` 下的头 3 个 checker
3. 每次 Debug Card 后按闭环长新的 checker
4. 半年 review 一次，退役无用的

harness 后续可以加：`harness verify scaffold` 命令，一键生成 `verify.sh` orchestrator + `verify.d/` 骨架 + 3 个通用 checker。**但不预置项目专属 checker**——那是项目自己的事。

## 一句话总结

**verify 层不是一次性写全的大脚本，是一个「Debug Card → 自动化提问 → 加 checker」不断长出来、半年 review 一次退役无用项的活系统。** 契约管的是架构与进化机制，不管具体检查什么。
