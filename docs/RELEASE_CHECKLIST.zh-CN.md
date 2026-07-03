# 发版检查清单

语言：[English](RELEASE_CHECKLIST.md) | 简体中文

每次 Harness 发版前使用这份清单。

## 1. 范围审阅

- [ ] 已审阅 `git status --short`。
- [ ] 每个已修改文件都确认纳入本次发布，或明确延后。
- [ ] 未跟踪文件都是有意加入。
- [ ] 没有包含私有 Brain 数据。
- [ ] 没有意外提交生成的项目本地产物。

## 2. 版本审阅

- [ ] 已选择并解释 SemVer bump。
- [ ] `VERSION` 与拟发布 tag 一致。
- [ ] `CHANGELOG.md` 包含发布日期和完整说明。
- [ ] `CHANGELOG.zh-CN.md` 镜像同一发布事实。
- [ ] 已记录兼容性影响。
- [ ] 行为变化时已记录迁移说明。

## 2.1 语言镜像审阅

- [ ] 面向公开或用户使用的英文发布文档都有 `.zh-CN.md` 镜像。
- [ ] 语言切换链接双向可用。
- [ ] 版本号、日期、标题层级、兼容性说明和验证声明在两种语言中一致。
- [ ] 本地化表达没有新增或删除事实。

## 3. 生成审阅

- [ ] `./generate.sh` 运行成功。
- [ ] `./generate.sh --check` 通过。
- [ ] `dist/` 中的生成文件与 `rules/core.md` 和 `rules/extended.md` 一致。
- [ ] 根目录生成文件，例如 `AGENTS.md`，已被 ignore 或明确处理。

## 4. 脚本审阅

- [ ] `*.sh` shell 语法检查通过。
- [ ] `setup.sh --non-interactive` 在临时项目中冒烟测试通过。
- [ ] 相关时，`vibe-init.sh` 冒烟测试通过。
- [ ] Brain 脚本不会把私有数据泄漏到公开仓库。

## 5. Harness 行为审阅

- [ ] 已检查新项目首次运行行为。
- [ ] 已检查 `plan.md` Executor 行为。
- [ ] 已检查 Harness Self-Test 回答形态。
- [ ] 已检查交付/工作流回合需要回合卡片。
- [ ] `rules/extended.md` 中仍保留 Preflight 和 Interaction QA 语言。

## 6. Tag 审阅

- [ ] release 文件和生成文件提交后，工作区干净。
- [ ] annotated tag 已准备：`vX.Y.Z`。
- [ ] tag message 包含验证证据。
- [ ] owner 明确批准打 tag 和 push。

## 当前 v0.9.0 候选说明

- [ ] 确认当前 Feature Inventory 改动纳入本次发布：
  - `.gitignore`
  - `rules/extended.md`
  - `docs/FEATURES.template.md`
- [ ] 确认 `CHANGELOG.md`、`CHANGELOG.zh-CN.md`、`VERSION` 和 release docs 已加入。
- [ ] 确认中文镜像文件和语言切换链接已加入。
- [ ] 文件落到 Harness 仓库后，运行完整验证集。
