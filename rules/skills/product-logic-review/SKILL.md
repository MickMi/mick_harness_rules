---
name: product-logic-review
description: Review a product requirement before implementation by simulating user journeys, state changes, permissions, timing, failures, and boundary cases. Use when a Harness Reviewer receives a PM-approved requirement for product_review, or when scope changes may invalidate an earlier product approval. Do not use for code review, QA execution, implementation planning, or writing the human PRD.
---

# Product Logic Review

Use this Skill as the Reviewer’s pre-development method. Harness role, plan, privacy, permission and verification rules remain authoritative.

## Establish the review object

1. Identify one `requirement_id`, the user outcome, confirmed behavior, explicit exclusions and unresolved decisions.
2. Separate facts, PM decisions and assumptions. An assumption that changes user-visible behavior is a finding, not a silent default.
3. Choose proportional depth:
   - **Quick**: one actor, one reversible path, no permissions/data/external side effects.
   - **Standard**: multiple states, error recovery, saved data, permissions or cross-surface behavior.
   - **Deep**: money, security, destructive actions, concurrency, multi-party workflows or irreversible state.

Do not force a fixed chapter list or persona count. Expand only where the requirement has real risk.

## Simulate behavior

Trace the smallest set of journeys that can falsify the requirement:

- Entry conditions: who can start, from which state, with what required information.
- Happy path: action → visible feedback → state change → durable result.
- Boundary path: empty, maximum, duplicate, stale, partial and ambiguous input when relevant.
- Permission path: unauthorized, role change, ownership and information visibility.
- Timing path: repeated clicks, concurrent actors, refresh/restart, timeout and late responses.
- Failure path: what remains unchanged, what can retry, what must roll back, and how the user recovers.
- Lifecycle path: edit, cancel, delete, restore, migrate or expire only when the feature supports them.

Prefer state tables or short scenario chains when they expose contradictions. 不要输出私有思维过程（private chain-of-thought）；只报告输入、可观察的状态变化和结论。

## Record findings

Each actionable finding contains:

- Severity: blocking or non-blocking.
- Scenario: precondition → user action → observed ambiguity or contradiction.
- User impact: what becomes wrong, unsafe or impossible to understand.
- Violated invariant: the rule that cannot simultaneously remain true.
- Decision needed: the smallest PM/user choice required; do not invent the answer.

Merge duplicates. Do not create speculative edge cases without a plausible user path or project risk.

## Decide the gate

- `changes_requested`: any blocking product ambiguity, contradiction, missing recovery rule or unresolved permission/data boundary exists. Hand back to PM.
- `approved`: all blocking findings are resolved and the remaining behavior is observable and testable. Hand key scenarios to Executor and QA.
- A scope change that alters actors, visible behavior, persisted state, permissions, failure recovery or exclusions invalidates the old approval and requires a new `product_review`.

The review artifact stays separate from the human PRD. PM may apply confirmed decisions to product documents; technical implementation detail belongs in plan or an AI delivery contract.

## Deliver

Return a compact product review with: review object, depth/risk basis, tested journeys, findings, accepted invariants, gate result (`approved` or `changes_requested`), and the next owner.

Do not implement fixes, design QA’s full test suite, approve code, install hooks, write Brain memory, or modify global Agent configuration through this Skill. Do not output private reasoning; only provide review evidence and decisions.
