# 项目流程状态 (State of Workflow)

> 这是 AI 调度的 **single source of truth**。任何 Agent 在动手前都必须先读这里，
> 任何 Agent 在完成产物后都必须更新这里。

---

## 📍 当前需求

- **Feature 名称**: <!-- 例如：share-card -->
- **创建日期**: <!-- YYYY-MM-DD -->
- **负责模式**: 自动调度（AI 根据本文件激活角色）

---

## 🔄 流程状态

> 勾选 `[x]` = 已完成；当前激活阶段在 `**当前阶段**` 标记的那一行。

- [ ] **PM 需求审查** → `docs/PRD-<feature>.md`  ← **当前阶段**
- [ ] **Designer 视觉稿** → `docs/design/<feature>-mockup.html` + `<feature>-design-notes.md`
- [ ] **QA 测试策略** → `docs/test_strategy-<feature>.md` + `docs/test_cases-<feature>.md`
- [ ] **Dev 实现** → 源代码 + 单元测试
- [ ] **Reviewer 审查** → 审查报告（写入 `docs/reviews/<feature>-<date>.md`）
- [ ] **Done** → 合并 / 发布

---

## 🚦 调度规则（给 AI 看）

### 当用户发来一条消息时，AI 必须按以下顺序判断：

1. **读取本文件**，找出当前 `**当前阶段**` 标记所在行 → 这是默认激活的角色
2. **比对用户意图**：
   - 如果意图与当前阶段一致 → 直接以该角色回应
   - 如果意图明显跨阶段（例如当前在 PM 阶段，用户却让你写代码）→ **必须反问**：
     > "当前流程在 [X 阶段]，[Y 产物] 还没就绪。你是要：
     > A) 先把 [X] 走完
     > B) 跳过 [X] 直接进入 [Y 阶段]（跳过的风险：...）
     > C) 推翻当前流程，重新审查需求"

3. **跳过规则**：
   - 用户明确说"跳过 X"或"直接 Y" → 在本文件中把跳过的阶段标为 `[~]`（已跳过）并注明原因
   - 单文件 Bug 修复 / 文档更新 / 格式化 → **不走流程**，直接修，本文件不变

### Agent 完成产物后必须做的两件事

1. 在回复末尾输出**交接块**（Handoff Block，格式见各 agent 模板）
2. 用户确认后，**更新本文件**：
   - 把当前阶段的 `[ ]` 改为 `[x]`
   - 把 `**当前阶段**` 标记移到下一行
   - 在下方"流程日志"追加一条记录

---

## 📝 流程日志

| 时间 | 阶段 | 产物 | 备注 |
|------|------|------|------|
| YYYY-MM-DD HH:mm | (例)PM 完成 | docs/PRD-share-card.md | 用户确认锁定 |

---

## 🔁 多需求并行

如果同时在做多个 feature，复制本文件为 `docs/STATE-<feature>.md`，
并在 `docs/STATE.md`（主文件）顶部维护一个索引：

```markdown
## 进行中的需求
- [ ] share-card → docs/STATE-share-card.md (Designer 阶段)
- [ ] payment-retry → docs/STATE-payment-retry.md (Dev 阶段)
```

AI 在每次对话开始时，根据上下文判断当前讨论的是哪个 feature，然后读对应的 STATE 文件。
