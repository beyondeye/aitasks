---
title: "Task Consolidation (Folding)"
linkTitle: "Task Consolidation"
weight: 25
description: "Merging overlapping or duplicate tasks into a single actionable task"
depth: [intermediate]
---

When multiple people capture ideas independently, or separate exploration sessions uncover the same issue, you end up with overlapping tasks. To **fold** them is to merge related tasks into a single primary task that incorporates all their content, so the work is implemented once and the context of every folded task is kept.

To go the other way and split one complex task into child tasks, see [Task Decomposition]({{< relref "/docs/workflows/task-decomposition" >}}).

## When to Use

- **Duplicate discoveries.** Two exploration sessions found the same bug or improvement opportunity
- **Overlapping scope.** Tasks that touch the same files and would be quicker to implement together
- **Related ideas captured separately.** Multiple task ideas that address the same area of the codebase
- **Triage reveals redundancy.** During review on the [board]({{< relref "/docs/tuis/board" >}}), you realize two "different" tasks are really the same work

## How It Works

- Select two or more tasks to fold together (interactively by discovering related tasks, or explicitly by providing task IDs)
- Choose which task becomes the **primary**: it stays, and the content of the others is merged into it
- Non-primary task descriptions are appended under `## Merged from t<N>` headers, preserving all original context
- Folded tasks are set to `Folded` status and cleaned up automatically after the primary task is implemented and archived
- The primary task can be implemented immediately or saved for later

## Two Entry Points

- [`/aitask-fold`]({{< relref "/docs/skills/aitask-fold" >}}): a standalone skill for folding at any time. Interactive mode finds related tasks by shared labels and similar descriptions; explicit mode (`/aitask-fold 106,108`) merges tasks whose IDs you already know
- [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}): during task creation, it scans pending tasks for overlap and offers to fold them into the new task. See [Exploration-Driven Development]({{< relref "/docs/workflows/exploration-driven" >}})

## Typical Consolidation Flow

1. Notice overlapping tasks during triage (on the [board]({{< relref "/docs/tuis/board" >}}) or via `ait ls`)
2. Run `/aitask-fold` (interactive) or `/aitask-fold 106,108,112` (explicit)
3. Select the primary task, usually the one with the best description or broadest scope
4. Review the merged result, then continue to implementation or save for later
5. After implementation and archival, folded task files are automatically deleted

---

**Next:** [Workflows index]({{< relref "/docs/workflows" >}}): browse other workflows by category, or continue to the [Code Agent Skills]({{< relref "/docs/skills" >}}) reference.
