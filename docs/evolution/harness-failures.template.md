# Harness 失效记录

> 当 Harness 规则未能阻止 Agent 犯错时记录。用于 evolve 信号回流。

## 失效类型

| 标签 | 含义 |
|------|------|
| `tripwire-missed` | Tripwire 3 条被忽略 |
| `self-test-fake` | Self-Test 回答泛泛，未绑定任务 |
| `fake-verification` | 声称验证通过，但用户端实际失败 |
| `plan-hijack` | 闲聊/讨论时机械进入 Executor |
| `scope-creep` | 改了 plan 范围外的文件 |
| `repeated-failure` | 同一错误 >= 3 轮未解决 |
| `under-asking` | 该问用户但脑补了 |
| `over-asking` | 低风险任务反复打断用户 |

## 记录格式

每条一行：`YYYY-MM-DD · <项目> · <标签> · <一句话描述>`
