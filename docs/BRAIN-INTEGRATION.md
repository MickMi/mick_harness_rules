# Brain 交互边界

v0.17.0 把 Brain 定义为用户私有记忆库，而不是项目数据库或自动抄录器。

## 数据流

1. **读取**：Agent 先按当前任务关键词查询；只提炼直接相关的 gotcha、decision 或 preference，不把原文件整段塞进项目上下文。
2. **形成候选**：有复用价值的新经验先进入私有 `~/.mick-harness/state/brain-candidates/`，状态为 `pending_confirmation`。
3. **用户确认**：只有显式执行 `approve <candidate> --yes` 才调用现有 `brain-push.sh`。
4. **写入**：Brain 接收带 kind、layer 和来源的摘要；重复候选由稳定 digest 合并。
5. **审计**：项目或 Observer 只允许记录 candidate id、分类、层级、来源 digest 和状态，禁止记录候选正文。

## 分层规则

| 层 | 用途 | 默认写入策略 |
|---|---|---|
| session | 本轮临时经验和待验证线索 | 可形成候选，不自动写入 |
| project | 只对当前项目成立的约束和决策 | 用户确认后写入 |
| global | 跨项目稳定偏好和反复出现的坑 | 用户确认且证据充分后写入 |

## 隐私红线

- 不读取或持久化 Prompt、回复全文、transcript、环境变量。
- 候选会遮盖常见 token、API key、password/secret 字段、私钥头和用户 Home 绝对路径。
- `list` 和默认命令输出只显示元数据，不返回候选正文。
- 第三方 Skill 不得直接读写 Brain；必须经过本边界。
- 项目目录和事件账本不得出现 Brain 私人正文。

## 用户命令

```bash
python3 scripts/harness-brain-boundary.py candidate \
  --kind preference --layer project --project my-app \
  --summary "偏好简洁、可读的工作台"

python3 scripts/harness-brain-boundary.py list

python3 scripts/harness-brain-boundary.py approve memory_xxx --yes --dry-run
python3 scripts/harness-brain-boundary.py approve memory_xxx --yes
```

`--dry-run` 只显示去掉正文的调用结构；不会写 Brain。失败保持候选为待确认状态，可安全重试。
