# 外部 Skill 来源与治理

> v0.17.0 固定日期：2026-08-13。来源是能力参考，不拥有 Harness 的权限、调度、隐私或完成定义。

## 已引入

### prd-for-humans（Harness 原生 Skill）

- 路径：`rules/skills/prd-for-humans/`。
- 角色：PM，仅在用户明确要求 PRD 时加载。
- 用途：按需求体量自适应组织人类产品评审文档，加载版本化私有 Profile，并用确定性检查器阻止技术实现与 AI 交付契约混入 PRD。
- 安全边界：Profile 私人正文只由 Agent 在生成 PRD 时读取；工作台与事件仅允许记录来源和版本。Skill 不写 Brain、不自动生成 `AI-CONTRACT`、不调用网络或外部工具。
- 样例：三份 Harness 维护的结构样例覆盖小需求、数据需求和分期需求；样例用于回归结构弹性，不替代真实项目 PRD 的用户评审。

### designer-craft（Harness 适配 Skill）

- 路径：`rules/skills/designer-craft/`
- 角色：可选 Designer。
- 用途：设计方向、信息层级、视觉辨识度、交互状态、可访问性和有界批判。
- 安全边界：无脚本、无网络、无 Hook、无后台服务、无全局配置写入、无 Brain 直连。
- 更新方式：重新审计下方固定来源；通过后人工更新本适配 Skill 和行为评测，不做上游自动同步。
- 移除方式：删除该目录并移除 Designer 中的加载提示；不影响核心 Harness。

## 已审计来源

| 来源 | 固定 commit | 许可证 | 结论 | 使用方式 |
|---|---|---|---|---|
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `ae388ac58fb33aade50fc47e2be07c3192dcaabd` | Apache-2.0 | 设计判断强，但完整 Skill 含 Hook 管理、文件写入、localhost Live 服务、浏览器控制与外部图像 API | 只吸收通用设计方法；未复制或执行上游脚本/正文 |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | `97eb2a20032f0833e3d317162208a60385b0f96e` | MIT | 大型风格、配色、字体与技术栈资料库，适合查询，不适合成为第二个角色路由器 | 可选人工参考；未随 Harness 分发 |
| [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) | `4e799d45c17aec1498c269287a83b9dba22b966b` | MIT | 适合作为 Web 可访问性和界面质量 Gate，不足以单独定义审美 | 原则进入 Designer/QA 验收；未复制上游文件 |
| [anthropics/skills/frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | `f17010c9bb483898c1d9c9f42dde2b3a98889434` | Apache-2.0（仓库） | 简洁的差异化前端设计基准，与 Impeccable 主能力重叠 | 仅作行为对照；未同时注入以避免重复指令 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | `8b78b531ab965735c5dc74f6f7a219e1e37326df` | MIT | 方法质量高且强调小型、可组合 Skill，但整包安装会引入独立的 AGENTS/CLAUDE、CONTEXT/ADR、Issue Tracker、自动提交和子 Agent 工作流，与 Harness 调度、权限和 `plan.md` 有重叠 | v0.18 只适配 `grilling`、`domain-modeling`、`to-spec` 的对话综合、`to-tickets` 的垂直切片、`tdd`、`diagnosing-bugs`、`code-review` 与 `writing-for-agents` 的精简原则；不运行上游 setup，不整包注入 |

## 安全审查清单

候选进入 Harness 前必须满足：

1. 仓库、许可证、固定 commit 和角色用途可定位。
2. `SKILL.md`、脚本、Hook、网络、凭据、文件写入和后台进程均已检查。
3. 与现有角色重复的路由、完成定义和权限已删除或隔离。
4. 不读取 Prompt、回复、transcript、密钥、环境变量或 Brain 私人正文。
5. 有静态契约测试和至少一组真实任务行为评测；只通过文档检查时标为“契约通过”。

## v0.19 工作台治理

工作台“设置 → 能力与 Skill”提供本机只读清单和安装前兼容诊断。首页只显示已发现、已分配和需关注数量，完整来源、作用域、角色、加载证据与冲突原因在设置页展开，避免把能力管理重新做成首页信息墙。

工作台中的四个状态不可合并：

1. **已发现**：扫描器找到 `SKILL.md`。
2. **已安装**：文件已经位于受支持目录。
3. **已分配**：Skill 已作为某个 Harness 角色的方法附件登记。
4. **已验证加载**：真实 Agent 任务提供了运行证据。

文件存在不等于角色已分配，角色已分配也不等于 Agent 已加载。v0.19 首版只开放重新扫描、筛选和冲突展开，不开放任意 GitHub URL 安装、脚本执行或静默启用。未来安装动作必须复用工作台受控操作中心：固定来源与 commit → 静态诊断 → 用户确认影响 → 隔离安装 → 角色分配 → 新会话验证；任一步失败都不覆盖当前有效版本。

## 更新策略

- 每次更新先在临时审计目录通过 Skill Installer 拉取固定 commit，不直接覆盖项目或全局 Skills。
- commit、许可证或脚本能力改变时重新审计；未完成审计保持旧版本。
- 上游出现自动更新、自删除、自安装 Hook、远程 API 或高权限行为时默认不引入。
