---
title: "Code Agent Skills"
linkTitle: "Skills"
weight: 50
description: "Reference for aitasks skills across supported code agents"
---

aitasks provides code agent skills that automate the full task lifecycle. Claude Code is the source of truth (`/aitask-*`); Gemini CLI and OpenCode use the same slash-command style, while Codex CLI wrappers use `$aitask-*`.

_Claude Code / Codex CLI / Gemini CLI / OpenCode (agent availability depends on installed wrappers)_.

> **Multi-agent support:** Codex CLI and Gemini CLI wrappers are installed in `.agents/skills/`; OpenCode wrappers are installed in `.opencode/skills/`. Invoke skills with `/aitask-pick`, `/aitask-create`, etc. in Claude Code, Gemini CLI, and OpenCode, or with `$aitask-pick`, `$aitask-create`, etc. in Codex CLI. Run `ait setup` to install the wrappers detected for your agent. Interactive Codex skills require **plan mode** because `request_user_input` is only available there; OpenCode uses native `skill` and native `ask`, so this caveat does not apply there. However, if OpenCode is launched in plan mode, its read-only tool restriction may cause task locking to be skipped — see [Known Issues]({{< relref "/docs/installation/known-issues" >}}).

> **Run from the project root.** aitasks expects to be invoked from the directory containing `.git/` — the root of your project's git repository. All skills use relative paths (e.g., `./.aitask-scripts/aitask_ls.sh`) and expect to start there. Launching an agent from a subdirectory can break path-based permissions and wrapper assumptions, and in Claude Code it will also trigger repeated permission prompts. Always `cd` there before launching your agent.

## Skill Overview

### Task Implementation

Core workflow skills for picking and implementing tasks.

| Skill | Description |
|-------|-------------|
| [`/aitask-pick`](aitask-pick/) | The central skill — select and implement the next task (planning, branching, implementation, archival) |
| [`/aitask-pickrem`](aitask-pickrem/) | Autonomous remote variant of /aitask-pick — zero interactive prompts, profile-driven |
| [`/aitask-pickweb`](aitask-pickweb/) | Sandboxed variant for Claude Code Web — local metadata storage, requires follow-up with /aitask-web-merge |
| [`/aitask-web-merge`](aitask-web-merge/) | Merge completed Claude Web branches to main and archive task data |

### Task Management

Create, organize, import, and wrap tasks.

| Skill | Description |
|-------|-------------|
| [`/aitask-create`](aitask-create/) | Create tasks interactively via code agent prompts |
| [`/aitask-explore`](aitask-explore/) | Explore the codebase interactively, then create a task from findings |
| [`/aitask-fold`](aitask-fold/) | Identify and merge related tasks into a single task |
| [`/aitask-revert`](aitask-revert/) | Revert changes associated with completed tasks — fully or partially |
| [`/aitask-wrap`](aitask-wrap/) | Wrap uncommitted changes into an aitask with retroactive documentation |

### Contributions

Import external work and contribute changes back.

| Skill | Description |
|-------|-------------|
| [`/aitask-pr-import`](aitask-pr-import/) | Import a pull request as an aitask with AI-powered analysis and implementation plan |
| [`/aitask-contribute`](aitask-contribute/) | Turn local changes into structured contribution issues for upstream repos |
| [`/aitask-contribution-review`](aitask-contribution-review/) | Analyze contribution issues for duplicates and overlaps, then import as tasks |

### Code Review

Review code and manage review guides.

| Skill | Description |
|-------|-------------|
| [`/aitask-explain`](aitask-explain/) | Explain files: functionality, usage examples, and code evolution traced through aitasks |
| [`/aitask-qa`](aitask-qa/) | Run QA analysis on any task — discover tests, run them, identify gaps, and create follow-up test tasks |
| [`/aitask-review`](aitask-review/) | Review code using configurable review guides, then create tasks from findings |
| [`/aitask-reviewguide-classify`](aitask-reviewguide-classify/) | Classify a review guide by assigning metadata and finding similar guides |
| [`/aitask-reviewguide-merge`](aitask-reviewguide-merge/) | Compare two similar review guides and merge, split, or keep separate |
| [`/aitask-reviewguide-import`](aitask-reviewguide-import/) | Import external content as a review guide with proper metadata |

### Configuration & Reporting

Settings, statistics, and model management.

| Skill | Description |
|-------|-------------|
| [`/aitask-refresh-code-models`](aitask-refresh-code-models/) | Research latest AI code agent models and update model configuration files |
| [`/aitask-stats`](aitask-stats/) | View completion statistics |
| [`/aitask-changelog`](aitask-changelog/) | Generate changelog entries from commits and plans |
| [Verified Scores](verified-scores/) | How skill satisfaction ratings accumulate into verified model scores |

---

**Next:** [Command Reference]({{< relref "commands" >}})
