---
skill: <skill-name>          # 与文件名一致，kebab-case
version: 0.1                 # 每次不兼容修改 +0.1
maintainer: <who>            # 谁负责这个 Skill 的更新
last_verified: YYYY-MM-DD    # 最后一次跑通、确认还有效的日期
---

# Skill: <一句话说清这个 Skill 干什么>

> 一句话摘要：读者看这一行就知道要不要继续读。
> 例："在项目根跑完整验证脚本，把 exit code 和关键错误行贴回自检日志。"

## 目的

为什么要有这个 Skill——它替代了什么"AI 临场发挥"的坏行为？

例：
> 以前每次让 AI"跑测试"，它可能自己拼 `pnpm test` / `npm test` / `jest`，
> 每次命令都不一样、日志格式不一样、失败判定标准不一样。
> 这个 Skill 把测试流程固定下来，Executor 只需要"照剧本执行"，不需要重新推导。

## 何时触发

明确列出触发条件，不要写"必要时"这种模糊话。

例：
- Executor 完成 plan.md 的一个步骤后
- Reviewer 收到 Executor 完成汇报，验证前
- CI 里作为 verify 阶段的一部分

## 前置条件

执行前必须满足什么，否则会失败或误报：

- 项目根有 `.harness/verify.sh`（不存在 → 阻塞，不要"顺手创建")
- 已完成 `pnpm install` 或等价依赖安装
- 环境变量 `XXX` 已设置

## 执行步骤

**必须写具体命令，不写"运行测试"这种描述**。每步一行，可复制。

```bash
# 1. 进入项目根（如果 Executor 已经在项目根，跳过）
cd "$(git rev-parse --show-toplevel)"

# 2. 保存 baseline（如果这是"改前基线"跑法）
bash .harness/verify.sh --tier fast > /tmp/verify.baseline.log 2>&1
echo "baseline exit: $?" >> /tmp/verify.baseline.log

# 3. 改代码 ...（这一段留给 plan 步骤本身）

# 4. 跑改后验证
bash .harness/verify.sh --tier fast > /tmp/verify.after.log 2>&1
after_exit=$?

# 5. diff 输出
diff /tmp/verify.baseline.log /tmp/verify.after.log > /tmp/verify.diff.log
```

## 成功判定

**必须可机器判定**，不能是"看起来通过了"。

- exit code == 0
- diff 里没有新增 `FAIL` / `ERROR` 行
- 关键行满足特定 pattern（贴出正则或示例）

## 失败处理

失败时的强制动作。**不允许静默跳过或"先继续"**：

- exit code != 0：把最后 20 行错误 + 命令原文贴到 `## 自检日志` 或 `## 阻塞`
- diff 有新增失败：不要说"这不是我引入的"，参见 `extended.md §3.1 Baseline First`
- 前置条件不满足：写阻塞，不要顺手补前置

## 常见反模式（可选段）

列出这个 Skill 历史上被误用的方式，帮后来者避坑：

- ❌ 只跑一次不留 baseline，改完拿 exit code 说事
- ❌ 用 `fast` 的结果声称子系统或发布 Gate 已通过（三档覆盖面不同）
- ❌ 失败时改 `.harness/verify.d/` 里的 checker 让它变绿

## 变更历史（可选段）

- 2026-01-15：v0.1 初版
- 2026-02-03：v0.2 加入 baseline diff 步骤（见 issue #xxx）
