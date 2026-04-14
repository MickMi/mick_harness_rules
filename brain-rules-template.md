# 🧠 Brain Auto-Write Rules (自动记忆写入规则)
#
# This section instructs the AI to automatically write valuable learnings
# to the Brain memory system during conversations.
# Injected by brain-init.sh — DO NOT edit manually in project files.

# Brain Memory Auto-Write Protocol
When working in this project, you have access to a personal knowledge base ("Brain").
The Brain CLI is available at: `.harness/brain-push.sh`

## Auto-Write Trigger Conditions
Automatically call `brain-push.sh` when ANY of the following occurs during our conversation:

### 🐛 Gotcha / Pitfall Discovered
- Found a non-obvious bug, environment issue, or API quirk
- Discovered a library/tool limitation that wasted time
- Hit a configuration trap that others might also encounter
- **Action**: `.harness/brain-push.sh --layer session --source <ide> "concise description of the gotcha"`

### 🏗️ Architecture Decision Made
- Chose a specific library, framework, or approach over alternatives
- Made a trade-off decision (performance vs readability, etc.)
- Established a new pattern or convention for this project
- **Action**: `.harness/brain-push.sh --layer session --source <ide> "decision: what was decided and why"`

### 💡 Preference / Convention Established
- User expressed a coding style preference
- Established a naming convention or project structure rule
- Agreed on a workflow or process improvement
- **Action**: `.harness/brain-push.sh --layer session --source <ide> "preference: description"`

### ⚠️ Environment / Tool Limitation Found
- Discovered OS-specific behavior differences
- Found CI/CD pipeline constraints
- Identified version compatibility issues
- **Action**: `.harness/brain-push.sh --layer session --source <ide> "env: description of limitation"`

## Do NOT Trigger For
- Routine code writing, formatting, or refactoring
- Project-specific configuration that has no cross-project value
- Temporary debugging steps or experiments
- Information already present in the Brain (search first with `.harness/brain-search.sh <keyword>`)

## Write Format Guidelines
- Keep entries to ONE concise sentence (max 2 sentences if context is critical)
- Include the technology/tool name for searchability (e.g., "Redis", "Next.js", "Docker")
- Use present tense ("X causes Y" not "X caused Y")
- Prefix with category hint: gotcha/decision/preference/env

## Before Writing: Dedup Check
Before pushing a new entry, quickly check if a similar entry already exists:
```bash
.harness/brain-search.sh "<main keyword>"
```
If a similar entry exists, skip the write. Only write genuinely new information.

## Source Identifier
Replace `<ide>` with the actual IDE/platform name:
- Cursor → `cursor`
- Trae → `trae`
- Windsurf → `windsurf`
- VS Code Copilot → `copilot`
- Other → `ide`
