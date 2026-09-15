---
name: prd-for-humans
description: Start, draft, revise, or review a product requirements document for human product review. Use when the user explicitly asks to write a PRD, begin PRD discovery, or turn product requirements into a reviewable PRD. Decide whether the requirement is clear enough to draft now; otherwise converge through a few decision-changing questions. Keep product intent, user behavior, scope, rules, tradeoffs, and acceptance clear while excluding implementation guidance, Prompt design, model/data contracts, machine output formats, and Agent instructions.
---

# PRD for Humans

Write for the people deciding whether the product should be built and what it should do. Keep the product boundary strict and the document shape adaptive to the actual requirement.

## Resolve the writing profile

1. Apply the user's explicit instructions from the current turn first.
2. Read an active project profile at `docs/PRD-PROFILE.md` when present.
3. Resolve the private and generic profiles with `scripts/resolve_profile.py`; read only the returned active profile and any higher-priority layer.
4. Never copy private profile text into Harness events, public files, or the dashboard. Expose only version and source metadata.

See `references/profile-contract.md` when creating or changing a profile. Treat a correction as a one-off edit until the user confirms it is a stable preference; only then create a new profile version.

## Find the decision spine

Before drafting, identify:

- The present problem and the people affected.
- The outcome this requirement must change.
- The behavior or product rule people need to review.
- The boundary of this release and the evidence that will show it works.
- Any unresolved choice that materially changes the product.

Ask at most the smallest set of questions needed to resolve a material product decision. Do not turn PRD creation into a questionnaire, and do not invent missing decisions.

## Decide whether to draft or discuss

Treat PRD readiness as a product judgment, not a mandatory field checklist. Build a working brief from the current conversation and existing product facts: who has the problem, what outcome should change, the main experience or rule under review, the meaningful release boundary, and how people will judge the result. Some requirements will not need every element stated separately.

- If no missing answer would materially change the product direction, draft the PRD immediately. Do not ask confirmation questions merely to perform a process.
- If a missing answer would change the target user, core journey, business rule, scope, permission, failure behavior, or acceptance, stay in discussion. First state the current understanding and a recommended default, then ask at most one or two questions about the highest-impact unresolved decision.
- On later rounds, carry forward every confirmed answer. Ask only the next unresolved decision; never repeat a question unless the new answer conflicts with an earlier fact, and name that conflict when asking.
- If the user explicitly asks to proceed with uncertainty, draft with recommendations and unresolved decisions visibly separated from confirmed facts. Never silently promote a recommendation to a requirement.

Do not confuse PRD readiness with implementation readiness. A human PRD may be ready for product review without APIs, schemas, technical architecture, task breakdowns, or test commands.

See `references/dialogue-clear.md` and `references/dialogue-ambiguous.md` for conversation behavior. They are examples of judgment, not required wording.

## Keep facts and memory separate

- Current user statements and confirmed project documents define product truth for this PRD.
- The active PRD Profile shapes language, structure, density, and review style; it does not supply product facts.
- Brain may supply confirmed decisions and stable preferences with a clear source. Raw session logs, unapproved candidates, inferred intent, and unrelated project history are not requirements.
- A correction in this PRD changes only this document by default. Propose a Profile update only after the user confirms the correction is a stable preference across future PRDs.
- When sources disagree, surface the conflict and ask for the smallest necessary decision instead of choosing the most recent-looking text.

## Choose an adaptive outline

Use headings as navigation, not as a completeness score. Start with the shortest document that lets reviewers understand the problem, proposed experience, boundary, and acceptance. Add a module only when its content changes a product decision.

Examples of conditional modules:

- Add **数据需求** when the product reads, compares, derives, displays, or makes decisions from data. Cover source meaning, business definition, freshness, missing-data behavior, and user-visible confidence in product language.
- Add **规则说明** when the requirement introduces a new business definition, threshold, priority, eligibility rule, or calculation.
- Add **异常与边界** when failure, permission, empty, conflicting, or recovery states materially affect the experience.
- Add **分期** when different releases prove different outcomes or when deferral changes reviewer expectations.
- Add **角色与权限**, **内容规范**, or **关键状态** only when those are genuine product decisions.

For a small requirement, a short document with four natural sections may be enough. For a larger requirement, separate user journeys, rules, data, boundaries, phases, and acceptance when that improves review. Do not create empty sections, “not applicable” filler, or a fixed chapter sequence merely to satisfy a template.

Use `references/golden-small.md`, `references/golden-data.md`, and `references/golden-staged.md` as shape examples, not text templates.

## Write product truth

- Lead with current user friction and the concrete change, not a slogan.
- Describe journeys as what the user sees, decides, and can recover from.
- State scope with enough precision to prevent different human interpretations.
- Use business thresholds, formulas, examples, and user-visible states when they define the product. These are not technical pollution.
- Separate confirmed facts, recommendations, and unresolved decisions. Do not expand “later” into unconfirmed roadmap promises.
- Prefer prose before lists. Use tables only when comparison or mapping is easier to review in rows.
- Keep the language natural for the product and audience; do not force every requirement into identical wording or length.

## Protect the artifact boundary

Exclude file paths, functions, classes, component trees, interfaces or fields, databases, frameworks, CSS or pixel specifications, implementation steps, test commands, System Prompts, model parameters, Reasoning Pipelines, Data Contracts, JSON schemas, machine output formats, and Agent instructions.

When an AI feature also needs an execution contract, create `docs/AI-CONTRACT-<feature>.md` only after the user explicitly requests that separate artifact. Do not embed it in the PRD, generate it automatically, or link a contract that does not exist.

## Review and deliver

1. Read the draft once as a product reviewer: can a human decide why, for whom, what, how far, and how to judge success?
2. Remove sections that add ceremony but no decision value.
3. Run `python3 scripts/check_prd.py <prd-path>` from this Skill directory. Resolve every finding or explain a documented false positive before delivery.
4. Return the PRD and a short list of unresolved product decisions. Do not append a developer handoff unless requested.

The checker enforces the technical boundary; it does not grade product quality or require specific headings.
