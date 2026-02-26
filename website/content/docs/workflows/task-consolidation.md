---
title: "Task Consolidation (Folding)"
linkTitle: "Task Consolidation"
weight: 25
description: "Merging overlapping or duplicate tasks into a single actionable task"
---

When multiple people capture ideas independently, or separate exploration sessions uncover the same issue, you end up with overlapping tasks. Rather than implementing them separately (duplicating effort) or manually deleting the extras (losing context), the aitasks framework lets you **fold** related tasks into a single primary task that incorporates all their content.

This is conceptually the opposite of [task decomposition](../task-decomposition/) but serves a different purpose: decomposition splits a complex task for controlled execution, while consolidation merges redundant tasks for efficient execution.

## When to Use

- **Duplicate discoveries** — Two exploration sessions found the same bug or improvement opportunity
- **Overlapping scope** — Tasks that touch the same files and would be more efficient to implement together
- **Related ideas captured separately** — Multiple task ideas that address the same area of the codebase
- **Triage reveals redundancy** — During review on the [board](../../tuis/board/), you realize two "different" tasks are really the same work

## How It Works

- Select two or more tasks to fold together (interactively by discovering related tasks, or explicitly by providing task IDs)
- Choose which task becomes the **primary** — it survives and absorbs content from the others
- Non-primary task descriptions are appended under `## Merged from t<N>` headers, preserving all original context
- Folded tasks are set to `Folded` status and cleaned up automatically after the primary task is implemented and archived
- The primary task can be implemented immediately or saved for later

## Two Entry Points

- [`/aitask-fold`](../../skills/aitask-fold/) — Standalone skill for folding at any time. Interactive mode discovers related tasks by labels and similarity; explicit mode (`/aitask-fold 106,108`) for quick merging when you already know the IDs
- [`/aitask-explore`](../../skills/aitask-explore/) — During task creation, automatically scans pending tasks for overlap and offers to fold them into the new task. See [Exploration-Driven Development](../exploration-driven/)

## Typical Consolidation Flow

1. Notice overlapping tasks during triage (on the [board](../../tuis/board/) or via `ait ls`)
2. Run `/aitask-fold` (interactive) or `/aitask-fold 106,108,112` (explicit)
3. Select the primary task — the one with the best description or broadest scope
4. Review the merged result, then continue to implementation or save for later
5. After implementation and archival, folded task files are automatically deleted
