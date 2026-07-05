#!/bin/bash
set -euo pipefail

# ============================================================
# harness-evolve.sh — Rule self-evolution (proposal generator)
#
# Reads accumulated execution signal from Brain and proposes rule
# changes. NEVER modifies rules/*.md itself — it only writes a
# proposal file for the human to review, edit, and merge by hand.
#
# Signal sources (all in Brain, cross-project, git-synced):
#   global/evolution/audit-trail.md     ← harness-audit.sh --log
#   global/evolution/banned-patterns.md ← recurring 禁止项 (optional)
#   global/evolution/corrections.md     ← recurring Executor 指导 (optional)
#
# Output:
#   <project>/docs/evolution/proposal-YYYY-MM-DD.md
#
# Usage:
#   .harness/scripts/harness-evolve.sh [--since 30d] [--threshold 3]
#
# Design principles:
#   - Proposes, never auto-applies (human gate = no drift)
#   - Frequency threshold (don't evolve on noise / one-offs)
#   - Proposals include DELETION (evolution = subtraction too)
# ============================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info() { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# --- Parse arguments ---
SINCE_DAYS=30
THRESHOLD=3
while [[ $# -gt 0 ]]; do
    case "$1" in
        --since) shift; SINCE_DAYS="${1:-30}"; SINCE_DAYS="${SINCE_DAYS%d}"; shift ;;
        --threshold) shift; THRESHOLD="${1:-3}"; shift ;;
        -h|--help)
            echo "Usage: .harness/scripts/harness-evolve.sh [--since 30d] [--threshold 3]"
            echo ""
            echo "Aggregates execution signal from Brain and proposes rule changes."
            echo "Writes a proposal to docs/evolution/ — never edits rules/*.md."
            echo ""
            echo "Options:"
            echo "  --since <N>d     Look back N days (default: 30)"
            echo "  --threshold <N>  Min occurrences to propose a change (default: 3)"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Resolve paths ---
HARNESS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Use current working directory as project; fall back to HARNESS_ROOT parent
PROJECT_DIR="${1:-$(pwd)}"
if [ ! -d "$PROJECT_DIR" ]; then
    PROJECT_DIR="$(pwd)"
fi
shift 2>/dev/null || true

# --- Resolve signal source: first existing candidate wins ---
# Prefer Brain (cross-project), fall back to per-project audit-log.md.
CANDIDATES=()
if [ -f "$HARNESS_ROOT/scripts/brain-resolve.sh" ]; then
    # shellcheck disable=SC1091
    source "$HARNESS_ROOT/scripts/brain-resolve.sh"
    if resolve_brain_dir "$HARNESS_ROOT" 2>/dev/null && [ -n "${BRAIN_DIR:-}" ]; then
        CANDIDATES+=("$BRAIN_DIR/global/evolution/audit-trail.md")
    fi
fi
CANDIDATES+=("$HARNESS_ROOT/audit-log.md")

TRAIL_FILE=""
for c in "${CANDIDATES[@]}"; do
    if [ -f "$c" ]; then TRAIL_FILE="$c"; break; fi
done

HAS_OPTIONAL_SIGNAL=false
if [ -n "${BRAIN_DIR:-}" ]; then
    for sig in "harness-failures.md" "corrections.md" "banned-patterns.md"; do
        if [ -f "$BRAIN_DIR/global/evolution/$sig" ]; then
            HAS_OPTIONAL_SIGNAL=true
            break
        fi
    done
fi

if [ -z "$TRAIL_FILE" ] && [ "$HAS_OPTIONAL_SIGNAL" = false ]; then
    warn "No audit signal found. Run '.harness/scripts/harness-audit.sh --log' a few times first."
    exit 0
fi

# --- Compute date windows (macOS date -v, GNU fallback) ---
if date -v-1d '+%Y-%m-%d' >/dev/null 2>&1; then
    CUTOFF=$(date -v-"${SINCE_DAYS}"d '+%Y-%m-%d')
    PREV_CUTOFF=$(date -v-"$((SINCE_DAYS * 2))"d '+%Y-%m-%d')
else
    CUTOFF=$(date -d "${SINCE_DAYS} days ago" '+%Y-%m-%d')
    PREV_CUTOFF=$(date -d "$((SINCE_DAYS * 2)) days ago" '+%Y-%m-%d')
fi

# --- Aggregate signal by tag (awk) ---
# Output per tag: level|current_count|prev_count|projects
if [ -n "$TRAIL_FILE" ]; then
    AGG=$(awk -v cutoff="$CUTOFF" -v prev_cutoff="$PREV_CUTOFF" '
        /^## [0-9]{4}-[0-9]{2}-[0-9]{2}/ {
            # header: "## YYYY-MM-DD HH:MM · project · plan ref"
            cur_date = substr($2, 1, 10)
            split($0, parts, "·")
            cur_proj = parts[2]; gsub(/^ +| +$/, "", cur_proj)
            next
        }
        /^- (FAIL|WARN): / {
            level = $2; sub(/:$/, "", level)
            tag = $3
            in_window = (cur_date >= cutoff)
            in_prev   = (cur_date >= prev_cutoff && cur_date < cutoff)
            if (in_window) {
                cnt[tag]++
                lvl[tag] = level
                key = tag SUBSEP cur_proj
                if (!(key in seen)) { seen[key]=1; projs[tag] = projs[tag] (projs[tag]?",":"") cur_proj }
            }
            if (in_prev) prev[tag]++
        }
        END {
            for (t in cnt) printf "%s|%s|%d|%d|%s\n", t, lvl[t], cnt[t], prev[t]+0, projs[t]
        }
    ' "$TRAIL_FILE")
else
    AGG=""
fi

if [ -n "$TRAIL_FILE" ]; then
    SIGNAL_SOURCE_LABEL="${TRAIL_FILE/#$HOME/~}"
else
    SIGNAL_SOURCE_LABEL="${BRAIN_DIR:-$HARNESS_ROOT/brain}/global/evolution/{harness-failures,corrections,banned-patterns}.md"
fi

# --- Map a tag to its rule location + suggested action ---
# echoes: "<rule_location>|<current_rule>|<suggested_action>"
tag_to_rule() {
    case "$1" in
        tripwire-missed)  echo "core.md Tripwire|违反任一条必须停手|强化：把未读文件/未查 plan/未验证列入 Harness failure 自动提案" ;;
        self-test-fake)   echo "core.md Harness Self-Test|Self-Test 必须绑定当前任务|强化：泛泛复述规则视为未通过，并要求重答" ;;
        fake-verification) echo "core.md 铁律 3/7|没验证 ≠ 完成|强化：用户端失败时把验证声明写入 failure 信号" ;;
        plan-hijack)      echo "core.md 铁律 0|纯解释/讨论无需检查 plan|强化：区分讨论和交付，不机械进入 Executor" ;;
        repeated-failure) echo "core.md 铁律 5|同一错误 ≥2 次输出 Debug Card|强化：多轮无效尝试必须熔断" ;;
        under-asking)     echo "core.md 铁律 3|需求不清楚先问，不猜|强化：业务/数据/权限边界不清时必须提问" ;;
        over-asking)      echo "core.md 铁律 2/3|低风险技术细节默认自决|降噪：低风险实现不要反复打断用户" ;;
        executor-correction) echo "extended.md §10.3 Executor|Executor 不做架构决策/不越权|从 corrections.md 提炼高频纠正项" ;;
        banned-pattern)   echo "extended.md §10.7/§10.9|反复禁止项应进入 plan 禁止项|从 banned-patterns.md 提炼明确禁止清单" ;;
        plan-integrity)   echo "core.md 铁律 0|plan 必须含 ## 目标 / ## 步骤|强化措辞：plan 缺段落直接拒绝执行" ;;
        missing-selfcheck) echo "extended.md §10.3 自检日志|每完成一步追加 ### Step N 条目|强化：把'每步必写自检日志'升为铁律级措辞" ;;
        verify-missing)   echo "extended.md §10.3 自检日志格式|每条 verify: 必须有命令+结果|强化：缺 verify 行视为该步未完成" ;;
        verify-vague)     echo "extended.md §10.3 自检日志格式|禁止 verify: 只写'完成/done'|强化：给出反例清单" ;;
        step-order)       echo "extended.md §10.3 Executor 禁止|不跳步，按顺序执行|强化措辞或加时间戳自检提示" ;;
        scope-creep)      echo "core.md 铁律 0 特别警告 + §10.3|不在 plan 范围外改动|候选【升为铁律】：改 plan 外文件前先停下报阻塞" ;;
        files-missing)    echo "extended.md §10.3 自检日志格式|每条 files: 列出改动文件|强化：缺 files 行无法审计，视为不合规" ;;
        *)                echo "（未知 tag，需人工判断）|—|人工分析这个高频信号对应哪条规则" ;;
    esac
}

append_proposal() {
    local tag="$1" level="${2:-WARN}" cur="${3:-0}" prev="${4:-0}" projs="${5:-}"
    local rule_loc cur_rule action trend

    [ -z "$tag" ] && return 0
    [ "${cur:-0}" -lt "$THRESHOLD" ] && return 0

    ((PROPOSAL_COUNT++)) || true

    IFS='|' read -r rule_loc cur_rule action <<< "$(tag_to_rule "$tag")"

    if [ "${prev:-0}" -gt 0 ]; then
        if [ "$cur" -lt "$prev" ]; then trend="📉 上期 $prev → 本期 $cur（在改善）"
        elif [ "$cur" -gt "$prev" ]; then trend="📈 上期 $prev → 本期 $cur（在恶化，需更强约束）"
        else trend="➡️ 与上期持平（$cur）"; fi
    else
        trend="🆕 上期无记录，本期 $cur 次"
    fi

    {
        echo "## 提案 ${PROPOSAL_COUNT}：${tag}（${level}，本期 ${cur} 次）"
        echo ""
        echo "**证据**：近 ${SINCE_DAYS} 天 \`$tag\` 出现 $cur 次，涉及项目：${projs:-未知}"
        echo "**趋势**：$trend"
        echo "**对应规则**：$rule_loc — $cur_rule"
        echo "**建议**：$action"
        echo ""
        echo "- [ ] 接受  - [ ] 修改后接受  - [ ] 拒绝（一次性/噪声）"
        echo ""
        echo "---"
        echo ""
    } >> "$TMP_BODY"
}

aggregate_signal_file() {
    local sig="$1" file="$2"
    awk -F'·' -v sig="$sig" -v cutoff="$CUTOFF" '
        function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
        /^[0-9]{4}-[0-9]{2}-[0-9]{2}/ {
            date = substr(trim($1), 1, 10)
            if (date < cutoff) next
            proj = trim($2)
            if (sig == "harness-failures.md") tag = trim($3)
            else if (sig == "corrections.md") tag = "executor-correction"
            else tag = "banned-pattern"
            if (tag == "") tag = sig
            cnt[tag]++
            key = tag SUBSEP proj
            if (!(key in seen)) {
                seen[key] = 1
                projs[tag] = projs[tag] (projs[tag] ? "," : "") proj
            }
        }
        END {
            for (t in cnt) printf "%s|WARN|%d|0|%s\n", t, cnt[t], projs[t]
        }
    ' "$file"
}

# --- Build proposal ---
DATE_TODAY=$(date '+%Y-%m-%d')
EVO_DIR="$PROJECT_DIR/docs/evolution"
PROPOSAL="$EVO_DIR/proposal-$DATE_TODAY.md"
mkdir -p "$EVO_DIR"

PROPOSAL_COUNT=0
TMP_BODY="$(mktemp)"

while IFS='|' read -r tag level cur prev projs; do
    append_proposal "$tag" "$level" "$cur" "$prev" "$projs"
done <<< "$AGG"

# --- Optional signals: harness-failures, corrections, banned-patterns ---
for sig in "harness-failures.md" "corrections.md" "banned-patterns.md"; do
    sig_file="${BRAIN_DIR:-}/global/evolution/$sig"
    if [ -n "${BRAIN_DIR:-}" ] && [ -f "$sig_file" ]; then
        while IFS='|' read -r tag level cur prev projs; do
            append_proposal "$tag" "$level" "$cur" "$prev" "$projs"
        done < <(aggregate_signal_file "$sig" "$sig_file")
    fi
done

# --- Write the proposal file ---
if [ "$PROPOSAL_COUNT" -eq 0 ]; then
    rm -f "$TMP_BODY"
    ok "没有任何信号达到阈值（≥ $THRESHOLD 次/近 ${SINCE_DAYS} 天）。规则暂不需要进化。"
    echo ""
    info "信号源：${SIGNAL_SOURCE_LABEL}"
    exit 0
fi

{
    echo "# 规则进化提案 · $DATE_TODAY"
    echo ""
    echo "> 由 \`harness-evolve.sh\` 生成。窗口 ${SINCE_DAYS} 天，阈值 ${THRESHOLD} 次。"
    echo "> 信号源：\`${SIGNAL_SOURCE_LABEL}\`"
    echo "> **本文件不改任何规则。** 你 review 后，手动把接受的改动合进 \`rules/core.md\` / \`extended.md\`，再跑 \`generate.sh\`。"
    echo ""
    echo "共 $PROPOSAL_COUNT 条提案（按出现频次）："
    echo ""
    cat "$TMP_BODY"
    echo "## 合并后"
    echo ""
    echo "1. 把接受的改动写进 \`rules/core.md\` 或 \`rules/extended.md\`"
    echo "2. 跑 \`.harness/generate.sh\` 传播到 7 个工具"
    echo "3. 下次 \`harness-evolve.sh\` 看同一 tag 的频次是否下降——这是进化是否有效的唯一指标"
} > "$PROPOSAL"
rm -f "$TMP_BODY"

echo ""
ok "生成 $PROPOSAL_COUNT 条进化提案"
info "请 review：${PROPOSAL/#$PROJECT_DIR\//}"
echo ""
echo -e "  ${BOLD}下一步${NC}：打开提案，对每条勾选 接受/修改/拒绝，手动合并进 rules/*.md，再跑 generate.sh"
echo ""
