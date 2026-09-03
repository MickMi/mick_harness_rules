# 需求状态入口

当前没有由本文件维护的独立待办。

进行中版本、正式需求与 Backlog 以 [docs/VERSIONS.md](docs/VERSIONS.md) 为唯一状态源；执行步骤和验证证据记录在 [plan.md](plan.md)。保留本文件只是兼容旧链接，避免旧的 Vibe/Brain 清单继续被工作台误判为未完成需求。

## 已关闭的旧清单

- 健康检查已由 `harness check`、项目 `.harness/scripts/harness-audit.sh` 和统一的 `harness doctor` 承担。
- 记忆分类已迁移到 Brain 的 Global / Project / Session 分层与版本化 Profile。
- 初始化幂等性由 `harness init`、原子 Loader 和安装回归测试覆盖。
- Prompt 与角色变化由 Git、`docs/VERSIONS.md` 和版本化角色 Skill 追踪。
- Git Brain 的初始化、检查、写入、搜索、蒸馏、多平台适配和容量治理均已交付。
