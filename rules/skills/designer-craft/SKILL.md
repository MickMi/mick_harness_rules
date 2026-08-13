---
name: designer-craft
description: Shape, redesign, implement, or critique distinctive and usable product interfaces without losing product truth. Use for dashboards, app shells, websites, components, onboarding, empty/error states, visual hierarchy, typography, layout, color, interaction, responsive behavior, accessibility, or when an interface feels generic, noisy, inconsistent, or unlike the user's taste. Do not use for backend-only work or routine style edits that already have an unambiguous design-system rule.
---

# Designer Craft

Start from the product task and the user's taste, not from a fashionable component recipe. The Harness Designer role owns scope and handoff; this Skill only improves design judgment and execution.

## Establish the truth

1. Read `rules/roles/designer.md` or the injected equivalent. Harness permissions, plan scope, privacy and verification override this Skill.
2. Read the brief, current page, real data shape, existing tokens/components/assets, and explicit aesthetic feedback. Treat missing `DESIGN.md` as missing documentation, not proof of a blank slate.
3. Name the surface mode:
   - **Operate**: finish a task; prioritize scanability, predictable interaction and status clarity.
   - **Persuade**: decide and act; prioritize narrative, credibility and a clear call to action.
   - **Read**: understand; prioritize structure, typography and navigation.
   - **Experience**: explore an artifact; let content lead and interface recede.
4. Decide whether the task is refinement or redesign. Refinement preserves identity and behavior; redesign preserves product truth and constraints but may replace the visual world. Ask before changing factual copy, claims or core behavior.

## Shape before editing

Write a compact direction before code:

- User task and first thing they must notice.
- One visual thesis: what should this surface feel like, and why it fits this product.
- Hierarchy: primary, supporting and background information.
- Interaction spine: entry → action → result → recovery.
- Existing truths to preserve and explicit anti-goals.

Explore two or three materially different directions when the brief is open. Select one with a product reason; do not blend them into a compromise. When the brief is explicit, implement it directly.

## Craft the interface

- Use the existing stack and components. Introduce a new pattern only when it creates a clear user benefit.
- Make hierarchy legible through composition, scale, spacing and contrast before adding decoration.
- Use typography, color, borders, radii and motion as one coherent system. Repeated values should become existing-style tokens.
- Prefer real icons and assets over text glyphs or decorative placeholders. Never invent product data or commercial claims.
- Cover default, hover, focus, active, disabled, loading, empty, error and success states only where the component can reach them.
- Preserve keyboard access, semantic structure, visible focus, readable contrast, reduced motion and narrow-screen use.
- Avoid mechanical “AI look” defaults: undifferentiated card grids, excessive pills, gratuitous purple gradients, gradient text, every section in a rounded container, and decoration with no task value. Treat these as warnings, not bans when the brief deliberately calls for them.

## Critique with evidence

Run two bounded passes:

1. Inspect desktop and narrow-screen states together. List issues by user impact: task clarity, hierarchy, interaction, state coverage, accessibility, consistency, then polish.
2. Fix the batch and confirm once. Stop unless the confirmation reveals a new blocking defect.

Do not call a page “good” because it looks polished in one screenshot. Check the actual user path, real state source, resize/refresh behavior and failure feedback. If browser or visual tooling is unavailable, mark visual verification as pending.

## Deliver

- For design direction: return the thesis, hierarchy, interaction spine, key states and implementation constraints.
- For implementation: return changed files and real-path verification.
- For critique: return prioritized, actionable findings with the affected surface and evidence.
- Keep decisions traceable to the related requirement/version so the Harness workspace can display the role's contribution.

## Safety boundary

- Do not install hooks, start background servers, call external image APIs, read transcripts, alter global Agent configuration or write Brain memory through this Skill.
- Do not run upstream Skill scripts. `rules/skills/SOURCES.md` records the audited inspirations and excluded capabilities.
- Use only tools and writes already authorized by the user's task and Harness plan.
