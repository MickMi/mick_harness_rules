#!/usr/bin/env bash
# ============================================================
# session-start.sh — SessionStart hook for Mick Agent Harness
#
# Fires on Claude Code SessionStart (startup|clear|compact) events.
# Injects Harness Tripwire + Self-Test triggers as additionalContext
# so any tool session gets a hard reminder that Harness is loaded,
# even before it opens AGENTS.md.
#
# Design rules:
# - Only inject if current project has .harness/ mounted. Silent no-op otherwise.
# - Never emit stderr on the happy path (Claude Code shows it as a failure).
# - Keep the injected payload short (Tripwire + trigger list, not full core.md).
# - Exit 0 always. A broken hook must not block a session.
# ============================================================

set -euo pipefail

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Detect whether the CWD is inside a Harness-managed project.
# CWD when Claude Code fires the hook is the project root (or a subdir).
# Markers checked (any hit wins): .harness directory, AGENTS.md, CLAUDE.md.
find_harness_marker() {
    local dir="${PWD:-$HOME}"
    for _ in 1 2 3 4 5 6 7 8; do
        if [ -e "$dir/.harness" ] || [ -f "$dir/AGENTS.md" ] || [ -f "$dir/CLAUDE.md" ]; then
            echo "$dir"
            return 0
        fi
        [ "$dir" = "/" ] && break
        dir="$(dirname "$dir")"
    done
    return 1
}

# Silent no-op if we're not in a Harness project. Do NOT emit JSON — an empty
# additionalContext still costs tokens on every session.
if ! find_harness_marker >/dev/null 2>&1; then
    exit 0
fi

# The injected payload. Keep it tight; the full playbook lives in
# .harness/rules/core.md and .harness/rules/extended.md.
read -r -d '' PAYLOAD <<'EOF' || true
<HARNESS-LOADED>
Mick Agent Harness 已挂载。以下是最高优先级约束的摘要，完整规则见 `.harness/rules/core.md`：

⛔ Tripwire（违反任一 = 立即停手）：
1. 改动前必须先读（用 Read 读要改的文件）
2. 改动文件前先查 plan.md（存在 → 按 plan 执行；不存在 → 正常响应）
3. 没验证 ≠ 完成（禁止"应该好了/配置好了"话术）

🧪 Self-Test 触发条件（触发就必须先用 5 句话回答再动手）：
- 新项目首次启用 / 用户说"自检 / self-test"
- 高风险外部系统 / 复杂交互 / 重复 Bug / 刚违反过铁律

📋 铁律 0（最高优先）：本轮要改文件/生成交付物 → 先 `ls plan.md`。
   有 → 首句输出 `[📋 Executor · plan N/M · Step X] plan.md 已读取：<步骤>`
   没有 → 正常响应；>3 文件改动建议先出 plan
   纯讨论/解释无需检查

🚧 撞墙熔断：同一错误 ≥2 次 / 连续 3 次未解决 → 停手，输出 Debug Card

📤 交付/工作流强制输出回合卡片（6 槽位固定顺序：✅ 本回合 / 📍 整体 / ➡️ 下一步 / 🧠 推理深度｜上下文 / 📐 边界 / 🚧 阻塞）

🎯 完成话术必须带证据（跑命令 → 读输出 → 才能说"通过"）；Subagent/工具报告 success ≠ 完成，独立看 diff/verify

要点：完整规则在 `.harness/rules/core.md`（10 条铁律 + 反驳表 + Gate Function）和 `.harness/rules/extended.md`（Anti-Wall / Preflight / Interaction QA / Plan-Execute / 角色协作 / Brain 记忆）。
</HARNESS-LOADED>
EOF

# Escape for JSON embedding (bash parameter substitution, fastest for hooks).
escape_for_json() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

escaped="$(escape_for_json "$PAYLOAD")"

# Claude Code SessionStart expects hookSpecificOutput.additionalContext.
# Use printf, not heredoc, to avoid bash 5.3+ heredoc-stdin race.
printf '{\n  "hookSpecificOutput": {\n    "hookEventName": "SessionStart",\n    "additionalContext": "%s"\n  }\n}\n' "$escaped"

exit 0
