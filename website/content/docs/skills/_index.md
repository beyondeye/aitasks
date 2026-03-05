---
title: "Code Agent Skills"
linkTitle: "Skills"
weight: 50
description: "Reference for aitasks skills across supported code agents"
---

aitasks provides code agent skills that automate the full task lifecycle. Claude Code is the source of truth (`/aitask-*`), with Codex CLI wrappers available for `$aitask-*`.

_Claude Code / Codex CLI / Gemini CLI / OpenCode (agent availability depends on installed wrappers)_.

> **Multi-agent support:** Codex CLI wrappers are installed in `.agents/skills/`. Invoke skills with `$aitask-pick`, `$aitask-create`, etc. Run `ait setup` to install Codex wrappers when Codex is detected. Interactive Codex skills require **plan mode** because `request_user_input` is only available there.

> **Important: Run from the project root directory.** All skills use relative paths (e.g., `./aiscripts/aitask_ls.sh`) that must match the permission entries in `.claude/settings.local.json`. If you start Claude Code from a subdirectory instead of the project root (the directory containing `ait` and `aiscripts/`), these paths won't match and Claude Code will prompt for permission on **every command**. Always `cd` to the project root before launching Claude Code.

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
| [`/aitask-create`](aitask-create/) | Create tasks interactively via Claude Code |
| [`/aitask-explore`](aitask-explore/) | Explore the codebase interactively, then create a task from findings |
| [`/aitask-fold`](aitask-fold/) | Identify and merge related tasks into a single task |
| [`/aitask-pr-import`](aitask-pr-import/) | Import a pull request as an aitask with AI-powered analysis and implementation plan |
| [`/aitask-wrap`](aitask-wrap/) | Wrap uncommitted changes into an aitask with retroactive documentation |

### Code Review

Review code and manage review guides.

| Skill | Description |
|-------|-------------|
| [`/aitask-explain`](aitask-explain/) | Explain files: functionality, usage examples, and code evolution traced through aitasks |
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

---

**Next:** [Command Reference]({{< relref "commands" >}})
