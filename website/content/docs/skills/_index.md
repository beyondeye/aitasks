---
title: "Claude Code Skills"
linkTitle: "Skills"
weight: 50
description: "Reference for all Claude Code slash-command skills"
---

aitasks provides Claude Code skills that automate the full task workflow. These skills are invoked as slash commands within Claude Code.

## Skill Overview

| Skill | Description |
|-------|-------------|
| [`/aitask-pick`](aitask-pick/) | The central skill — select and implement the next task (planning, branching, implementation, archival) |
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
