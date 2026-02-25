---
title: "Claude Code Skills"
linkTitle: "Skills"
weight: 50
description: "Reference for all Claude Code slash-command skills"
---

aitasks provides Claude Code skills that automate the full task lifecycle. These skills are invoked as slash commands within Claude Code.

> **Important: Run from the project root directory.** All skills use relative paths (e.g., `./aiscripts/aitask_ls.sh`) that must match the permission entries in `.claude/settings.local.json`. If you start Claude Code from a subdirectory instead of the project root (the directory containing `ait` and `aiscripts/`), these paths won't match and Claude Code will prompt for permission on **every command**. Always `cd` to the project root before launching Claude Code.

## Skill Overview

| Skill | Description |
|-------|-------------|
| [`/aitask-pick`](aitask-pick/) | The central skill — select and implement the next task (planning, branching, implementation, archival) |
| [`/aitask-pickrem`](aitask-pickrem/) | Autonomous remote variant of /aitask-pick — zero interactive prompts, profile-driven |
| [`/aitask-pickweb`](aitask-pickweb/) | Sandboxed variant for Claude Code Web — local metadata storage, requires follow-up with /aitask-web-merge |
| [`/aitask-explore`](aitask-explore/) | Explore the codebase interactively, then create a task from findings |
| [`/aitask-explain`](aitask-explain/) | Explain files: functionality, usage examples, and code evolution traced through aitasks |
| [`/aitask-fold`](aitask-fold/) | Identify and merge related tasks into a single task |
| [`/aitask-create`](aitask-create/) | Create tasks interactively via Claude Code |
| [`/aitask-wrap`](aitask-wrap/) | Wrap uncommitted changes into an aitask with retroactive documentation |
| [`/aitask-stats`](aitask-stats/) | View completion statistics |
| [`/aitask-changelog`](aitask-changelog/) | Generate changelog entries from commits and plans |
| [`/aitask-review`](aitask-review/) | Review code using configurable review guides, then create tasks from findings |
| [`/aitask-reviewguide-classify`](aitask-reviewguide-classify/) | Classify a review guide by assigning metadata and finding similar guides |
| [`/aitask-reviewguide-merge`](aitask-reviewguide-merge/) | Compare two similar review guides and merge, split, or keep separate |
| [`/aitask-reviewguide-import`](aitask-reviewguide-import/) | Import external content as a review guide with proper metadata |

---

**Next:** [Command Reference]({{< relref "commands" >}})
