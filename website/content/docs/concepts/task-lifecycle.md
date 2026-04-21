---
title: "Task lifecycle"
linkTitle: "Task lifecycle"
weight: 100
description: "The status transitions a task moves through from creation to archival."
depth: [main-concept]
---

## What it is

Every task carries a `status` field that captures where it is in its life:

| Status | Meaning |
|--------|---------|
| `Ready` | Created and triaged. Available to be picked. |
| `Editing` | Being authored or revised in a TUI; not yet ready for implementation. |
| `Implementing` | A skill has claimed the task; an agent is actively working on it. |
| `Postponed` | Deferred — left visible but skipped during normal selection. |
| `Done` | Implementation finished and committed. Awaiting archival. |
| `Folded` | The task has been merged into another (the `folded_into` task). |

Transitions are driven by the workflow scripts: picking a task moves `Ready → Implementing` and acquires a lock; a successful run moves `Implementing → Done` (then `Done → Archived` as the file moves into `aitasks/archived/`); aborting reverts to `Ready` and releases the lock. Folded is a terminal status — folded files are deleted (not archived) when the primary they were merged into is archived.

## Why it exists

A small, fixed set of statuses lets the prioritization, board, and selection logic stay simple: every script that asks "what's next?" only has to reason about a handful of states. Recording transitions as commits — rather than as silent in-place edits — means `git log` for a task file is also its audit trail.

## How to use

You rarely set `status` by hand. The workflow scripts do it as side effects of picking, archiving, aborting, and folding. The full transition logic lives in the implementation scripts on GitHub: [`aitask_pick_own.sh`](https://github.com/beyondeye/aitasks/blob/main/.aitask-scripts/aitask_pick_own.sh), [`aitask_archive.sh`](https://github.com/beyondeye/aitasks/blob/main/.aitask-scripts/aitask_archive.sh), and the [task abort procedure](https://github.com/beyondeye/aitasks/blob/main/.claude/skills/task-workflow/task-abort.md).

## See also

- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — where the field lives
- [Locks]({{< relref "/docs/concepts/locks" >}}) — the lock state mirrors lifecycle transitions
- [Folded tasks]({{< relref "/docs/concepts/folded-tasks" >}}) — the `Folded` terminal state

---

**Next:** [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}})
