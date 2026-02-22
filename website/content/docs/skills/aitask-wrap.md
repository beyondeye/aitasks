---
title: "/aitask-wrap"
linkTitle: "/aitask-wrap"
weight: 45
description: "Wrap uncommitted changes into an aitask with retroactive documentation and traceability"
---

Retroactively wraps uncommitted changes into the aitasks framework. When you've made changes outside the normal task workflow — quick fixes, debugging improvements, config tweaks — this skill analyzes the diff, creates a task and plan file documenting the changes, commits everything with proper format, and archives it in one flow.

**Usage:**
```
/aitask-wrap
```

## Workflow Overview

1. **Detect changes** — Scans for uncommitted changes (staged, unstaged, and untracked). Aborts if nothing to wrap
2. **Select files** — Choose to include all changes or select specific files
3. **Analyze diff** — Reads the full diff and determines: factual summary, probable intent, suggested issue type, task name, labels, priority, and effort
4. **Confirm analysis** — Presents the analysis for review. Adjust task name, metadata, or descriptions before proceeding
5. **Execute** — After a final confirmation gate, runs everything without further prompts: creates task file → creates plan file → commits code changes → archives task and plan → pushes to remote
6. **Summary** — Displays the created task, plan, commit hashes, and archive status

## Key Capabilities

- **Auto-analysis** — Reads the diff to infer intent, suggest an issue type (`feature`, `bug`, `refactor`, etc.), and generate task/plan descriptions
- **Metadata suggestions** — Suggests priority, effort, and labels based on diff size and file paths. All suggestions are adjustable before execution
- **Single confirmation gate** — All user interaction happens before Step 5. Once confirmed, everything executes sequentially without interruption
- **All-in-one execution** — Task creation, plan creation, code commit, archival, and push happen in a single automated sequence
- **Edge case handling** — Handles large diffs (>2000 lines) with truncation warnings, mixed staged/unstaged changes, and untracked files

## When to Use

| Scenario | Skill |
|----------|-------|
| Changes already made, need to document retroactively | [`/aitask-wrap`](../aitask-wrap/) |
| Planning work before starting implementation | [`/aitask-create`](../aitask-create/) |
| Want to explore the codebase first, then create a task | [`/aitask-explore`](../aitask-explore/) |

Use `/aitask-wrap` when you've accumulated uncommitted changes that weren't tracked through the normal workflow — quick fixes applied directly, debugging sessions that turned into real improvements, config or dependency changes made outside the framework, or pair programming sessions where changes accumulated without task tracking.
