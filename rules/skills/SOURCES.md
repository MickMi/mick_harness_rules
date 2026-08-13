# 外部 Skill 来源与治理

> v0.17.0 固定日期：2026-08-13。来源是能力参考，不拥有 Harness 的权限、调度、隐私或完成定义。

## 已引入

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

## 安全审查清单

候选进入 Harness 前必须满足：

1. 仓库、许可证、固定 commit 和角色用途可定位。
2. `SKILL.md`、脚本、Hook、网络、凭据、文件写入和后台进程均已检查。
3. 与现有角色重复的路由、完成定义和权限已删除或隔离。
4. 不读取 Prompt、回复、transcript、密钥、环境变量或 Brain 私人正文。
5. 有静态契约测试和至少一组真实任务行为评测；只通过文档检查时标为“契约通过”。

## 更新策略

- 每次更新先在临时审计目录通过 Skill Installer 拉取固定 commit，不直接覆盖项目或全局 Skills。
- commit、许可证或脚本能力改变时重新审计；未完成审计保持旧版本。
- 上游出现自动更新、自删除、自安装 Hook、远程 API 或高权限行为时默认不引入。
