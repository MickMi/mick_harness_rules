# Ambiguous requirement: converge on product decisions

## Round 1 user input

“工作台项目太多了，做一个智能推荐，帮我写 PRD。”

## Round 1 response behavior

Start with the current understanding: the user wants the workbench to reduce the effort of deciding which project needs attention. Recommend ranking existing projects by actionable blockers and pending decisions before inventing personalized prediction. Ask no more than two questions that change the product:

1. Is the primary outcome “find the next project to handle” or “discover projects worth revisiting”?
2. May the recommendation use only visible project status, or also private Brain preferences?

Do not ask about model choice, API design, storage, or visual details. Do not draft a fake complete PRD yet.

## Round 2 user answer

“是找下一个要处理的项目，只能看当前项目状态，不要读 Brain。”

## Round 2 response behavior

Carry both answers forward. If the existing conversation already defines what counts as actionable, draft directly. Otherwise state the recommended priority—user decisions, blockers, failed operations, then stale work—and ask only whether this ordering is acceptable. Never ask the two Round 1 questions again.

## Fact boundary

The recommendation order remains a recommendation until confirmed. The user’s Brain restriction is a confirmed product boundary. Neither the active Profile nor old session logs may override it.
