---
name: prd-for-humans
description: Collaborate on a PRD for human product review, from a rough idea through clarification, drafting, review, and focused revision. Use when the user asks to start, write, revise, or review a PRD, or learn their PRD style from examples. Reuse confirmed answers and writing preferences, ask only questions that change product decisions, and draft directly when the need is clear. Keep product behavior and business detail concrete; exclude technical implementation and AI delivery contracts.
---

# PRD Collaboration for Humans

Be a product thinking partner, not a form filler or a development planner. Help the user turn intent into a document people can discuss and decide on. Keep the document adaptive; preserve confirmed decisions across rounds.

## 1. Start from the user and available evidence

Identify this turn's intent: discuss, draft, revise, review, or learn style. Discussion is not permission to produce a final PRD; a local revision is not permission to restart discovery or rewrite the whole document.

- Resolve writing guidance: current explicit instructions → active `docs/PRD-PROFILE.md` → private Profile → generic Profile. Use `scripts/resolve_profile.py` and read the returned active Profile and relevant layers. Do not load every historical sample by default.
- Current user statements and confirmed project documents define product truth. The Profile shapes voice, structure, and density; it does not supply product facts.
- Brain may provide sourced, confirmed decisions. Raw logs, unapproved candidates, and unrelated history do not become requirements.
- Separate an existing capability, a requested change, a recommendation, and an unresolved decision. A mockup demonstrates an option; it does not approve that option or prove implementation.
- When learning from multiple documents, read `references/sample-learning.md`. Check provenance, group revisions of one requirement, and distinguish reusable writing from business-specific rules. Missing originals or approval evidence must stay explicit; do not present a historical summary as a reread original.

Private samples and Profile text stay out of public Skill files, Harness events, and dashboards. Generic examples illustrate technique, not the user's actual requirements.

## 2. Converge only on decisions that matter

Keep a lightweight working brief: current problem/outcome, entry and main journey, confirmed behavior and scope, unresolved choices, and relevant evidence. Carry it in the conversation or existing draft; do not create a separate tracking system. Show only the change or the choice the user needs to make, not a repeated round card.

- If no missing answer would materially change the product direction, draft the PRD immediately when the user wants a draft. Do not force a confirmation of the outline or ask questions merely to perform a process.
- Otherwise, briefly explain your understanding and a recommended choice with its consequence, then ask at most one or two questions about the highest-impact gap. Confirm an unknown journey entry rather than assuming a notification, a proactive visit, or an alert.
- Carry forward confirmed answers; never repeat a question unless a new statement conflicts with them. Point to that specific conflict. Do not choose scope from filenames, modification times, or the largest historical version.
- If the user wants a draft despite uncertainty, mark recommendations and open choices beside the affected scene. Do not hide a material product decision behind a default or a vague “to be supplied by engineering.”

Do not confuse PRD readiness with implementation readiness. APIs, schemas, architecture, implementation tasks, and test commands are not prerequisites. Do not ask the user to complete a mandatory questionnaire or supply a success metric for every small change.

Use `references/dialogue-clear.md` or `references/dialogue-ambiguous.md` only when a conversation example helps.

## 3. Draft the smallest complete product story

Start with the problem, a coherent user journey, scene-level behavior, and meaningful boundaries. Follow the active Profile's preferred outline as an adaptive default, not a universal chapter sequence. A journey explains the sequence and motivation; scene detail specifies what people see and what each action changes, without retelling the same story.

For each relevant scene, explain the entry, visible information, available action, outcome, and significant failure/recovery behavior. Do not turn these into mandatory columns or force CRUD onto a read-only feature.

- UI-heavy work: pair images and detail tables using `references/golden-ui.md`. Embed the actual image beside its explanation, label concepts/sample data, and provide a readable view. Never refer to an unlinked “design A”; say when no image is available. A visual does not replace interaction rules.
- Specify meaningful product fields: names, units, time ranges, comparison basis, choices, required input, or editability as relevant. Business formulas and visible fields are allowed; API/storage fields are not.
- For data-heavy work, compare coverage across scenarios rather than pretending every object supports identical analysis. Explain unavailable information and where the user can go next. Do not copy historic sample numbers, thresholds, or capability claims into the new requirement.
- Use worked examples when a rule is hard to understand. Keep them consistent with the declared scope and label illustrative values; do not turn an example answer into a Prompt or machine-output specification.

Use coherent paragraphs and compact tables. Simplify structure and repetition without deleting necessary metrics, fields, interactions, or boundary logic. Do not break every sentence into its own paragraph or nest lists merely for appearance.

Separate **数据需求** for substantial business definitions or data limitations, **规则说明** for new product rules, **角色与权限** for real permission decisions, and **分期** for confirmed release differences. Otherwise keep the detail with its scene. Distinguish proposed boundary advice from committed behavior; do not invent later phases.

Do not create empty sections, “not applicable” filler, or mandatory acceptance, evaluation, test-case, and decision appendices. Small changes may need only a few paragraphs. Shape references: `golden-small.md`, `golden-data.md`, `golden-staged.md` in `references/`; load only the relevant one.

## 4. Check product logic without starting a delivery pipeline

Read the proposal as its user: can they enter, understand the information, act, see the result, and recover? Consider only material alternate paths—missing data, a failed interpretation, unsupported scope, permission, cancellation, or returning to a previous view. Put the resulting product behavior in the relevant scene or boundary section, not a test script.

Check scope consistency across the journey, details, examples, and exclusions. If an example uses an excluded capability, correct it or label it as an optional proposal. Never convert a hypothesis about a user's problem into a demonstrated cause.

For an existing PRD review, lead with the important contradictions or missing decisions and a proposed correction. Do not rewrite it without authorization or claim independent Reviewer approval from this self-check.

## 5. Revise locally and learn deliberately

- For feedback, preserve accepted content and change the affected sections and their dependent references. A request for a table must not introduce features; “shorter” must not remove essential behavior. Read `references/dialogue-revision.md` for a concrete example.
- Carry the revised decision forward and briefly explain any effect on another scene. Do not restart the whole interview after every correction.
- Treat a correction as local unless the user confirms a stable preference. A request to “learn this style for future PRDs” authorizes a scoped preference update, not approval of every claim in the source.
- When maintaining a Profile, follow `references/profile-contract.md`: version confirmed preferences, reconcile obsolete ones, retain source/approval boundaries, and keep private examples private. Do not write Brain during ordinary drafting.

## 6. Protect the artifact and deliver

Exclude implementation source paths, functions, classes, component trees, API/storage fields, databases, frameworks, CSS or pixel specifications, implementation steps, test commands, System Prompts, model parameters, Reasoning Pipelines, Data Contracts, JSON schemas, machine output formats, and Agent instructions. Design-image references and visible product fields are allowed.

When an AI feature also needs an execution contract, create `docs/AI-CONTRACT-<feature>.md` only after the user explicitly requests that separate artifact. Do not embed it in the PRD, generate it automatically, or link a contract that does not exist.

Run `python3 scripts/check_prd.py <prd-path>` from this Skill directory for a file deliverable. Resolve findings or explain false positives. For conversational drafts without a file, perform the same boundary review and do not claim the script ran. Return the requested document or revision and only material unresolved choices. A PRD handoff does not start implementation, full testing, or release.

The checker flags technical content and missing local image targets; it does not validate remote images, grade product quality, or require headings. Static tests and sample walkthroughs are not proof of real multi-round behavior or Agent loading.
