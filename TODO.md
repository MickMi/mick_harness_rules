# 项目待办与状态流转

## 🚧 当前进行中 (In Progress)
- [ ] 🧠 Git Brain 架构落地（详见下方 Brain 任务拆解）

## 📋 待办清单 (Backlog)

### 原有待办
- [ ] 增加 `vibe-check.sh` 健康检查脚本 (自动验证护栏完整性)
- [ ] 扩展 `MEMORY.md` 结构模板 (增加技术债务、性能基线等分类)
- [ ] 修复 `vibe-init.sh` 幂等性 (防止重复运行覆盖已有内容)
- [ ] 增加 `.prompts/CHANGELOG.md` (Prompt 迭代追溯)

### 🧠 Git Brain 任务拆解
| 优先级 | 任务 | 说明 | 状态 |
|--------|------|------|------|
| **P0** | 创建 Brain 仓库基础结构 | `brain/global/` + `brain/projects/` + `brain/sessions/` 三层目录 + `.brain-config.yaml` | ✅ |
| **P1** | 编写 `brain init` 脚本 | 一键加载 harness + brain，注入到项目，自动验证 | ✅ |
| **P1** | 编写 `brain check` 验证脚本 | 确保脚手架真正生效（验证闭环） | ✅ |
| **P2** | 编写 `brain push` 回写脚本 | 从项目中向 brain 写入经验（支持 CLI 快速写入） | ✅ |
| **P2** | 编写 `brain search` 检索脚本 | 基于 ripgrep 的记忆检索，避免全量读取 | ✅ |
| **P3** | 改造 `vibe-init.sh` | 从"内联所有内容"改为"从 harness 仓库加载" + 集成 `brain mount` | ✅ |
| **P3** | Daily/Weekly compound 蒸馏脚本 | Session → Project → Global 的自动蒸馏流程 | ✅ |
| **P4** | 多平台适配 | Cursor 自动写入规则、多 IDE 注入、brain-rules-template.md | ✅ |
| **P4** | 记忆容量治理 | Session 层 90 天归档、MEMORY.md 最大长度控制、brain-gc.sh | ✅ |

## ✅ 已完成 (Done)
- [x] 🔍 强制需求审查协议落地（pm_agent.md + .cursorrules 门禁 + orchestration.md 流程更新）
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
- [x] 🧠 将 Git Brain 架构决策记录到 MEMORY.md（ADR-001 ~ ADR-006）
- [x] 🧠 将 Git Brain 任务拆解更新到 TODO.md