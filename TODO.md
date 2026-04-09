# 项目待办与状态流转

## 🚧 当前进行中 (In Progress)
- [ ] (无)

## 📋 待办清单 (Backlog)
- [ ] 增加 `vibe-check.sh` 健康检查脚本 (自动验证护栏完整性)
- [ ] 扩展 `MEMORY.md` 结构模板 (增加技术债务、性能基线等分类)
- [ ] 修复 `vibe-init.sh` 幂等性 (防止重复运行覆盖已有内容)
- [ ] 增加 `.prompts/CHANGELOG.md` (Prompt 迭代追溯)

## ✅ 已完成 (Done)
- [x] 初始化 Vibe Coding 护栏上下文结构
- [x] `.cursorrules` 增加 Tech Stack 槽位模板
- [x] 丰富 `docs/architecture.md` 模板结构 (API 契约、数据模型、NFR、部署拓扑、ADR 索引)
- [x] 补充 QA Agent 角色模板 (`.prompts/qa_agent.md`)
- [x] 补充 Agent 编排协议 (`.prompts/orchestration.md`)
- [x] 增加 Git 工作流与版本管理规范 (分支策略、Conventional Commits、SemVer、Tag)
- [x] 增加 CI/CD 护栏 (Pipeline 阶段、质量门禁、环境隔离、密钥管理)
- [x] 创建 CI/CD 模板库 (`docs/ci_cd_templates.md` + `.github/workflows/ci.yml`)
- [x] 创建 PR 模板 (`.github/PULL_REQUEST_TEMPLATE.md`)
- [x] 实现智能角色路由 (Auto Role Routing in `.cursorrules`)
- [x] 同步更新 `vibe-init.sh` 脚本