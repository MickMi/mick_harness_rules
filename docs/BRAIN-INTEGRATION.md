# Brain 交互边界

v0.18.0 把 Brain 定义为本地优先的分层记忆服务，而不是自动抄录器。结构化 Harness 事件是主来源；SessionEnd 转录提炼只是关闭默认的可选补漏。

## 自动化优先

- **常驻服务负责可靠性**：项目扫描、状态识别、去重、落盘、队列、重试、仓库核对和同步保护都由确定性代码执行，不依赖 Agent 记得某段 Prompt。
- **Hook 只是采集适配器**：不同 Code Agent 的 Hook 只把会话节点转换成最小结构化事件；Hook 缺失或 Agent 不支持 Hook 时，文件与 Git 等可观察事实仍由服务端扫描补齐。
- **Prompt 只做语义工作**：角色判断、摘要和“这是否是跨项目稳定偏好”等需要理解上下文的工作才交给 AI；AI 结果仍要经过 Schema、脱敏、幂等与权限边界。
- **远端写入保留用户控制**：项目事实可自动写入本地 Brain，但远端推送继续由工作台显式确认；全局偏好与 Profile 在本地写入前也必须审批。

判断原则：能用状态机、文件事实、Git 结果或固定规则证明的事情必须写成代码；只有无法由确定性规则表达的语义判断才允许依赖 Prompt。

## 数据流

1. **结构化事件**：Claude、Codex 或通用 Harness 在完成、决策、验证、交付与交接节点回写最小事件；原始聊天、Prompt 和工具日志不进入该链路。
2. **识别与去重**：Brain 边界只接受已完成、已接受或已验证的项目事实，并按项目与事件幂等键去重。
3. **项目自动记忆**：项目事实立即写入本地 Brain 与私有活动索引，不要求用户逐条审批，也不等待会话结束。
4. **全局/Profile 候选**：跨项目偏好和 Profile 变化进入 `~/.local/state/mick-harness/brain-candidates/`；用户在 6425 工作台查看差异并决定是否发布。
5. **本地优先同步**：写入本地与同步远端是两个状态。远端失败时保留本地内容和重试线索，不把“已批准”冒充“已同步”。
6. **可选补漏**：SessionEnd/每日转录提炼默认关闭；即使启用，也不能替代结构化事件主链。

## 分层规则

| 层 | 用途 | 默认写入策略 |
|---|---|---|
| session | 本轮临时经验和待验证线索 | 不进入长期项目记忆；可作为可选补漏输入 |
| project | 已确认的项目需求、阶段、决策、验证、结果、交接和关键产物 | 自动写入，可在活动流撤销或提升 |
| global | 跨项目稳定偏好和反复出现的坑 | 必须审批，可编辑、拒绝和重试 |
| profile | PRD 风格等专用、版本化个人能力 | 必须先展示当前版本、新版本与差异，再发布新版本 |

## 隐私红线

- 结构化主链不读取或持久化 Prompt、回复全文、transcript、模型私有思维、环境变量。
- 候选会遮盖常见 token、API key、password/secret 字段、私钥头和用户 Home 绝对路径。
- CLI `list` 默认只显示元数据；候选正文只通过本机 6425 同源工作台展示，不进入项目 API 或事件账本。
- 第三方 Skill 不得直接读写 Brain；必须经过本边界。
- 项目目录和事件账本不得出现 Brain 私人正文。

## 用户命令

```bash
python3 scripts/harness-brain-boundary.py candidate \
  --kind preference --layer global --project my-app \
  --summary "跨项目偏好简洁、可读的工作台"

python3 scripts/harness-brain-boundary.py list

python3 scripts/harness-brain-boundary.py approve memory_xxx --yes --dry-run
python3 scripts/harness-brain-boundary.py approve memory_xxx --yes
python3 scripts/harness-brain-boundary.py reject memory_xxx --reason "只适用于本项目"
python3 scripts/harness-brain-boundary.py retry memory_xxx
python3 scripts/harness-brain-boundary.py project-list --project my-app
python3 scripts/harness-brain-boundary.py health
```

`--dry-run` 只显示去掉正文的调用结构或 Profile 版本预览；不会写 Brain。失败会进入 `write_failed`/`sync_failed`，工作台可以重试。

## 工作台白名单

6425 只提供候选批准/拒绝/重试、项目记忆撤销/提升等明确动作。每次服务启动生成独立动作令牌，浏览器必须同源读取并在请求头携带；Observer 的事件写入令牌不会暴露给页面。服务端不接受任意 Shell 命令、任意路径或任意文件正文。
