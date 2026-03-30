#!/bin/bash

echo "🚀 开始初始化 Vibe Coding 脚手架 (Harness Engineering)..."

# 1. 创建基础目录
mkdir -p docs
echo "✅ 创建目录结构: docs/"

# 2. 注入全局认知护栏 (.cursorrules)
cat << 'EOF' > .cursorrules
# Role & Vibe (角色与基调)
- 定位：你是一位拥有 10 年以上经验的资深全栈架构师。交付企业级代码。
- 态度：极其务实，极简主义，拒绝过度工程。
- 沟通约束：绝对禁止废话。禁止说“好的”、“我明白了”等。直接输出思考过程或代码。

# 核心认知框架
1. 强制反思与目标对齐：操作前确认最终业务目标，防偏离。
2. 主动反驳机制：若我的需求偏离目标或有更好方案，必须提出质疑，不要盲从。

# 执行路径
1. 谋定而后动：写代码前必须在 <thinking> 标签内简述实现逻辑、设计模式和边界风险。
2. 上下文隔离：修改已有文件前必须完整阅读。绝不凭猜测覆盖代码。
3. 测试即契约 (TDD)：接收意图 -> 编写测试和契约 -> 运行失败 -> 编写实现直到通过。
4. 分步交付：复杂任务先输出核心骨架，我确认后再填细节。

# 代码哲学
- 防御性编程：不信任外部输入，完善边界检查和 Try/Catch。
- 单一职责：函数超一屏强制拆分。
- 尽早返回 (Early Return)：杜绝深层 if-else 嵌套。
- 自解释优先：变量/函数名具业务含义，少写What注释，只写Why注释。

# 调试与排错
- 拒绝盲目试错：报错必须先分析 Error Traceback。
- 日志先行：复杂 Bug 先加结构化日志缩小排查范围。

# 状态管理与上下文护栏
- 架构决策记录：引入新库或遇环境坑，主动提示我更新到 docs/architecture.md 或 MEMORY.md。
- 活文档同步：重构后强制更新相关文档。
- 待办收尾：完成后主动清理 TODO.md，并输出 Conventional Commits 规范的提交信息。
EOF
echo "✅ 注入全局认知护栏: .cursorrules"

# 3. 注入记忆中枢骨架
cat << 'EOF' > MEMORY.md
# 项目记忆与经验库 (Memory & Learnings)

## 🏗️ 架构决策记录 (ADR)
- [$(date +'%Y-%m-%d')] 初始状态：确立 Vibe Coding 护栏机制。

## ⚠️ 已知天坑与环境限制 (Gotchas)
- (暂无)
EOF
echo "✅ 初始化记忆中枢: MEMORY.md"

cat << 'EOF' > TODO.md
# 项目待办与状态流转

## 🚧 当前进行中 (In Progress)
- [ ] 

## 📋 待办清单 (Backlog)
- [ ] 编写核心业务逻辑
- [ ] 跑通基础自动化测试

## ✅ 已完成 (Done)
- [x] 初始化 Vibe Coding 脚手架
EOF
echo "✅ 初始化待办清单: TODO.md"

cat << 'EOF' > docs/architecture.md
# 系统架构与业务上下文

## 🎯 业务最终目标
(在此描述本项目的核心业务目标)

## 🧩 核心模块划分
- (待补充)
EOF
echo "✅ 初始化架构文档: docs/architecture.md"

# 4. 注入物理防线 (pre-commit)
cat << 'EOF' > .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  # Python 护栏 (如果项目中不用Python可删除此块)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.3
    hooks:
      - id: ruff
        args: [ --fix ]
      - id: ruff-format

  # 前端 护栏 (如果项目中不用前端可删除此块)
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.1.0
    hooks:
      - id: prettier
        types_or: [javascript, typescript, css, html]
EOF
echo "✅ 注入物理防线配置: .pre-commit-config.yaml"

# 5. 自动安装防线
if command -v pre-commit &> /dev/null; then
    echo "⚙️ 检测到已安装 pre-commit，正在挂载 Git Hooks..."
    git init -q # 确保是git仓库
    pre-commit install
    echo "✅ 物理防线挂载成功！"
else
    echo "⚠️ 未检测到 pre-commit 命令。"
    echo "请运行 'brew install pre-commit' 然后手动执行 'pre-commit install'。"
fi

echo "🎉 Vibe Coding 脚手架搭建完成！开启你的心流吧。"