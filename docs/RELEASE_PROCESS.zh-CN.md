# 发版流程

语言：[English](RELEASE_PROCESS.md) | 简体中文

本仓库使用 SemVer，并以 Git tag 作为发布事实源。

## 版本策略

- `MAJOR`：对已安装项目布局、规则契约、生成文件语义、脚本参数或强制 Agent 行为造成不兼容变化。
- `MINOR`：向后兼容的能力、新规则、新角色指导、新脚本、新模板或生成输出的新增内容。
- `PATCH`：兼容性修复、文案改进、脚本 bug 修复、测试改进和文档纠正。

## 必需文件

- `VERSION`：当前拟发布版本，不带前缀 `v`。
- `CHANGELOG.md`：英文发布历史。
- `CHANGELOG.zh-CN.md`：同一发布事实的简体中文镜像。
- `docs/RELEASE_CHECKLIST.md`：打 tag 前检查清单。
- `docs/RELEASE_CHECKLIST.zh-CN.md`：检查清单的简体中文镜像。

Git tag `vX.Y.Z` 是最终事实源。`VERSION`、`CHANGELOG.md` 和本地化发布文件必须与 tag 一致。

## 语言策略

- 英文文件使用标准文件名：`README.md`、`CHANGELOG.md`、`docs/RELEASE_PROCESS.md` 和 `docs/RELEASE_CHECKLIST.md`。
- 简体中文镜像使用 `.zh-CN.md` 后缀。
- 每个镜像文件顶部必须包含语言切换链接。
- 本地化文件可以调整表达，但不能新增、删除或违背发布事实。

## 发版流程

1. 审阅当前工作区。
   - 确认每个已修改和未跟踪文件都属于本次发布。
   - 打 tag 前排除或延后无关改动。

2. 选择版本。
   - 根据用户可见影响和兼容性影响应用 SemVer。
   - 更新 `VERSION`、`CHANGELOG.md` 和本地化镜像。

3. 重新生成规则输出。
   - 运行 `./generate.sh`。
   - 运行 `./generate.sh --check`。

4. 验证脚本和生成文件。
   - 对 shell 脚本运行语法检查。
   - 在目标项目存在 `plan.md` 时运行 Harness audit。
   - 在临时目录执行安装/bootstrap 冒烟测试。

5. 审阅发布说明。
   - 包含 What changed、Compatibility impact、Migration notes 和 Verification evidence。

6. 只在验证通过后打 tag。
   - 使用 annotated tag：`git tag -a vX.Y.Z`。
   - 经 owner 确认后，同时推送提交和 tag。

## 发版停止条件

出现任一情况时，停止打 tag：

- 工作区存在无法解释的 dirty 或 untracked 文件。
- `VERSION`、`CHANGELOG.md` 和拟发布 tag 不一致。
- 生成的 `dist/` 文件过期。
- setup 冒烟测试失败。
- 发布说明包含未验证声明。
- 某个改动会破坏现有项目安装，但没有迁移说明。

## 首个正式版本建议

除非 owner 明确希望承诺稳定的 `v1.0.0` 契约，否则首个正式基线使用 `v0.9.0`。当前系统已经可用，但发版流程、changelog 和 checklist 是这次才正式化。
