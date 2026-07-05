# Mick Agent Harness

[中文](README.md) | **English**

Keep your AI coding rules, personal preferences, and project discipline consistent across devices, projects, and code agents.

Mick Agent Harness is a personal Agent collaboration layer. It is not a new code agent, and it does not replace the coding ability of tools such as Claude Code, Codex, or Cursor. Its role is to **supplement Agent capability, not override it**. General AI coding ability will keep improving; the durable value of this Harness is injecting your working style, quality bar, verification habits, and long-term memory so different agents behave more like you.

The current implementation repo is `mick_harness_rules`; the product name is **Mick Agent Harness**.

## Why It Exists

When you use one agent, one project, and one machine, a few local rules may be enough. The problem becomes painful once you use Claude Code, Codex, Cursor, IDE plugins, or multiple machines and projects:

- preferences repeatedly explained in Claude are invisible to Codex;
- a gotcha found in project A returns in project B;
- a new machine does not have the same rules or memory;
- an agent edits before reading files, checking `plan.md`, or verifying work;
- Self-Test passes while the real user path is still broken;
- multi-round debugging produces plausible explanations without convergence.

Mick Agent Harness addresses this breakage: **rules, context, verification discipline, and long-term memory keep working across devices, projects, and agents.**

## Who It Is For

Mick Agent Harness is for users who:

- use Claude Code, Codex, Cursor, IDE plugins, or API calls together;
- switch between multiple machines or projects;
- want to introduce constraints into an existing AI-written project;
- need agents to follow their working style, not just write code;
- want gotchas, preferences, and verification results to become long-term memory;
- want a reusable, low-intrusion, verifiable Harness instead of reminding every agent every turn.

If you are only trying AI on a one-off script, you may not need it. It is built for heavy AI-coding users and people building a personal Agent workflow.

## Start in 5 Minutes

### 1. Install once per machine

```bash
git clone https://github.com/MickMi/mick_harness_rules.git ~/.mick-harness
mkdir -p ~/.local/bin
ln -sf ~/.mick-harness/bin/harness ~/.local/bin/harness
~/.local/bin/harness install
```

If already installed:

```bash
harness update
```

### 2. Initialize each project once

Run this in a new or existing project:

```bash
cd /path/to/your-project
harness init
```

This adds a small project entry that points agents to the global Harness.

For Brain config and full checks:

```bash
harness init --full
```

### 3. Make agents read the rules

Sync into supported local agents:

```bash
harness agents sync
```

For tools that cannot be managed automatically:

```bash
harness export codex
harness export agent
harness export ide
harness export api
```

### 4. Verify loading

Ask the Agent:

```text
请按 Harness Self-Test 用 5 句话证明你理解当前任务约束。
```

A valid answer must be specific to the current task:

1. current mode;
2. highest risk;
3. how completion will be proven;
4. how repeated failure will stop;
5. what it will not do in this turn.

Self-Test only proves loading and understanding. It is not delivery. Real delivery still needs test commands, dry-runs, screenshots, logs, or a clearly labeled "unverified" status.

## What Success Looks Like

Your project should contain:

```text
AGENTS.md
.harness/ -> ~/.mick-harness
```

The Agent should know to:

- read files before editing;
- check `plan.md` before file changes or deliverables;
- avoid forced planning for ordinary discussion;
- include verification evidence before delivery;
- stop repeated failed debugging with a Debug Card;
- output round cards for delivery, Self-Test, Harness loading checks, and similar workflow turns.

You can inspect status with:

```bash
harness check
harness report
harness metrics
```

## What It Writes

| Operation | Possible write location | Purpose | Rollback |
|---|---|---|---|
| `harness install` | `~/.mick-harness`, `~/.local/bin/harness` | Install global Harness and CLI | Delete the directory and symlink |
| `harness agents sync` | `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` | Inject managed loaders | Remove the `MICK-HARNESS-GLOBAL` block |
| `harness init` | project `AGENTS.md`, `.harness/`, `.gitignore` | Mount Harness into the project | Delete `.harness`; remove the `AGENTS.md` symlink or `HARNESS:BEGIN` block |
| `harness init --full` | project `.harness-config.yaml` | Enable full config and checks | Delete the config file |
| `harness brain install` | `~/.mick-brain`, optional Claude hook/LaunchAgent | Create Brain and enable sync | Delete Brain or disable the hook |

If a project already has a rule file with the same name, Harness injects a marked block and keeps existing content.

## What It Can Guarantee

Prompt constraints cannot make every model comply 100% of the time. Mick Agent Harness has explicit boundaries:

| Capability | Supported | Notes |
|---|---|---|
| Unified rule entry | Yes | Through global loaders and project `AGENTS.md`. |
| Project-level mounting | Yes | Projects keep a small entry point instead of a copied rule tree. |
| Force a model to obey every instruction | No | Models may still ignore prompt constraints. |
| Detect missing loading or verification | Yes | Through Self-Test, `harness check`, round cards, and verification evidence. |
| Prevent every bad code change from merging | No | Use tests, CI, review, or stronger engineering gates. |
| Long-term memory | Yes | Through Private Brain and optional hook adapters. |
| Automatic core-rule rewriting | No | Evolution creates proposals for human review. |

In short: Harness is not a magic enforcement layer. It is a system of **prior injection + posterior checks + long-term memory + human gatekeeping**.

## Supported Surfaces

| Surface | Recommended method | Current status |
|---|---|---|
| Claude / Claude Code | `harness agents sync` | Automatic managed loader; Brain hook support is strongest here. |
| Codex / Codex CLI | `harness agents sync` or `harness export codex` | Supports global loader; Brain writes through optional adapter / ingest. |
| `AGENTS.md` compatible tools | `harness init` | Stable project-level entry. |
| Cursor / IDE plugins | `harness export ide` | Paste manually or load from plugin side. |
| Any code agent | `harness export agent` | Generic prompt contract. |
| Pure API calls | `harness export api` | Use as system/developer message. |
| Custom hooks | `bash scripts/brain-ingest.sh` | Tool-neutral Brain write entry. |

For weaker models, pure API calls, surfaces without filesystem access, or high-risk tasks:

```bash
harness export api --full
harness export ide --full
```

## How It Works

Mick Agent Harness has four layers:

| Layer | Purpose | Typical file/command |
|---|---|---|
| Global Harness | Local shared rules and tooling | `~/.mick-harness`, `harness install` |
| Agent Loader | Global entry injected into a code-agent surface | `harness agents sync`, `harness export codex` |
| Project Manifest | Small project entry that points to the global Harness | `AGENTS.md`, `.harness/` |
| Private Brain | Private long-term memory and evolution signals | `~/.mick-brain`, `harness brain install` |

Recommended shape:

```text
Install Harness once per machine
  -> run harness init once per project
  -> let each Agent read the same rules through loader/export
  -> constrain delivery with check / audit / verification
  -> write important lessons to Private Brain
  -> periodically generate Harness evolution proposals
```

## Daily Commands

Daily use should stay small:

```bash
harness check
harness report
harness metrics
harness update
```

| Command | Purpose |
|---|---|
| `harness check [dir]` | Check project Harness / Brain / rule-generation health. |
| `harness report [dir]` | Show `plan.md` progress, blockers, and verification state. |
| `harness metrics [dir]` | Aggregate completion, verification coverage, and audit signals. |
| `harness update` | Update global Harness, regenerate rules, refresh registered projects, sync Agent loaders. |
| `harness agents scan` | Inspect local Agent entries that can be managed automatically. |
| `harness agents sync` | Sync managed loaders into supported Agent entries. |

## Advanced: Private Brain

Brain is private long-term memory. By default it lives in `~/.mick-brain`, and it can also be configured as a private Git repository.

Brain has three layers:

| Layer | Stores |
|---|---|
| Global | Cross-project preferences, communication style, common gotchas, long-term quality bar. |
| Project | Project-specific decisions, architecture context, historical issues, business context. |
| Session | Conversation summaries, execution results, verification evidence, failure signals. |

Install or inspect:

```bash
harness brain install
harness brain status
```

If the user has no Brain yet, `harness brain install` creates a local `~/.mick-brain` skeleton. If a private remote is configured but cannot be cloned, Harness falls back to a local Brain instead of blocking `harness init --full`, `harness check`, or the original Harness workflow.

Brain is private data. It should not be committed into the public Harness repo or a business project repo.

## Advanced: Hook Adapter

Hook adapters write session summaries, failure signals, and verification results from different tools into Brain. They are managed through the existing Brain command instead of adding many top-level commands:

```bash
harness brain install
harness brain status
```

Default config lives in `config/.brain-config.yaml`:

- `claude_code.enabled: true`: Claude Code SessionEnd and daily sync are enabled by default;
- `codex.enabled: false`: optional Codex inbox;
- `generic.enabled: false`: optional generic command/inbox adapter.

Tool-neutral ingestion:

```bash
printf '%s\n' "session summary" \
  | bash ~/.mick-harness/scripts/brain-ingest.sh --source codex --kind session
```

Failure signal ingestion:

```bash
printf '%s\n' "Harness missed a required round card" \
  | bash ~/.mick-harness/scripts/brain-ingest.sh --source codex --kind failure
```

This lets Claude Code, Codex, IDE plugins, and pure API calls join the same Brain feedback loop. Automatic triggering remains user-configured.

## Advanced: Harness Evolution

Mick Agent Harness does not silently rewrite its own rules. The evolution path is:

```text
Agent work
  -> round card / audit / failure signal
  -> Private Brain evolution log
  -> harness brain evolve
  -> rule-evolution proposal
  -> user review
  -> accepted change to rules/*.md
  -> generate / export / sync
  -> fewer similar failures later
```

Run:

```bash
harness brain evolve
```

The success metric is not whether rules become more complex. It is whether the same failure signal becomes less frequent afterward.

## Design Principles

- **Reusable**: one Harness can mount into many projects.
- **Low intrusion**: projects keep a small entry point instead of a copied rule tree.
- **Tool-neutral**: the core abstraction is an Agent collaboration protocol, not one vendor's config file.
- **Simple by default**: install, init, and update should each feel like one command.
- **Evidence-driven**: unverified work is not complete.
- **Private first**: public Harness and private Brain are separate.
- **Human-gated evolution**: signals can be collected automatically, but rule merges require human approval.
- **Context-cost aware**: Core loads by default; Extended loads when risk requires it.

## Current Limitations

- Prompt constraints cannot make every model comply 100% of the time; posterior checks and user review remain necessary.
- Automatic loader management mainly covers file-backed entries; some IDE plugins still require manual export.
- Brain hook automation is most complete for Claude Code; Codex, IDE, and API flows join through optional adapter / ingest.
- `harness brain evolve` creates proposals; it does not rewrite rules automatically.
- Private Brain remote sync depends on the user's private repo access and network state.

## Development and Verification

Common checks:

```bash
bash -n bin/harness scripts/*.sh generate.sh
./generate.sh --check
MICK_HARNESS_ROOT="$PWD" ./bin/harness version
MICK_HARNESS_ROOT="$PWD" ./bin/harness export codex
```

Project init check:

```bash
tmp_project="$(mktemp -d)"
MICK_HARNESS_ROOT="$PWD" ./bin/harness init "$tmp_project" --full
```

Brain fallback check:

```bash
tmp_home="$(mktemp -d)"
HOME="$tmp_home" MICK_HARNESS_ROOT="$PWD" ./bin/harness brain install
HOME="$tmp_home" MICK_HARNESS_ROOT="$PWD" ./bin/harness brain status
```

## Next Version Focus

- Add a unified `harness doctor` for install, project, Agent loader, Brain, hook, and audit health.
- Improve the Adapter Registry so each tool has an explicit support level, loading method, and hook capability.
- Add fixture tests for Brain ingest, hook adapters, `brain evolve`, and no-Brain fallback.
- Keep simplifying the product path into: install once, init once per project, sync/export once per Agent, enable Brain optionally.
