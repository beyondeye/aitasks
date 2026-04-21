---
title: "Revert Changes with AI"
linkTitle: "Revert Changes"
weight: 90
description: "Reverting features or changes that are no longer needed"
depth: [advanced]
---

AI-assisted development makes it easy to add features quickly — but not every feature survives contact with real usage. Some experiments don't pan out, some features add more complexity than value, and sometimes you want to undo part of a large change while keeping the rest. The [`/aitask-revert`](../../skills/aitask-revert/) skill handles all of this at a higher level than raw `git revert`, creating structured revert tasks with full traceability.

## When to Use

- **Feature bloat** — A completed feature adds unnecessary complexity and you want to remove it cleanly
- **Failed experiments** — A prototype or experimental feature didn't work out and should be rolled back
- **Partial cleanup** — A large task introduced changes across multiple areas, but only some need to be undone
- **Post-prototyping** — After rapid prototyping, you want to remove scaffolding or temporary code while keeping the core implementation
- **Dependency simplification** — A feature introduced dependencies or patterns that turned out to be overkill

## How It Works

The revert workflow follows five stages:

1. **Discover** — Find the task to revert by browsing recent tasks, searching by file, or entering a task ID directly
2. **Analyze** — Review commits, affected areas, and per-child breakdown (for parent tasks)
3. **Select** — Choose complete or partial revert, then specify exactly what to undo
4. **Create** — Generate a self-contained revert task with all commit hashes, file lists, and instructions
5. **Implement** — Execute the revert now or save for later

## Complete Revert

A complete revert undoes all changes from a task. This is the simplest path — useful when the entire feature should be removed.

**Example walkthrough:**

You implemented task t195 — "Add real-time notification badges" — three weeks ago. After user feedback, the team decides the badges are distracting and should be removed.

1. Run `/aitask-revert 195`
2. The skill analyzes t195's commits and shows a summary:
   - 4 commits, touching `src/components/`, `src/api/`, and `src/styles/`
   - +342 insertions, -28 deletions across 8 files
3. Select "Complete revert"
4. Choose disposition — "Keep archived" to preserve the task history with revert notes
5. The skill creates a new task: `t230_revert_t195.md` containing all commit details, affected files, and instructions
6. Continue to implementation or save for later

The implementing agent will analyze each commit, determine the safest revert approach (git revert, manual edits, or a combination), and present a pre-revert summary for your approval before making any changes.

## Partial Revert

A partial revert lets you keep some changes while undoing others. This is particularly powerful for parent tasks with children, where you can revert entire feature slices.

**Example walkthrough:**

Task t180 — "Add user settings panel" — was a parent task with three children:
- t180_1: Settings UI components
- t180_2: Settings API endpoints
- t180_3: Settings data migration

You want to keep the API and migration but remove the UI components (they'll be rebuilt with a different framework).

1. Run `/aitask-revert 180`
2. Review the per-child breakdown showing which areas each child touched
3. Select "Partial revert"
4. Choose "By child task" selection mode
5. Select t180_1 (Settings UI components) for revert — t180_2 and t180_3 remain
6. Review the confirmation summary:
   ```
   Will REVERT:
   - t180_1 (settings_ui_components) — 5 commits, areas: src/components/, src/styles/

   Will KEEP:
   - t180_2 (settings_api_endpoints) — 3 commits, areas: src/api/
   - t180_3 (settings_data_migration) — 2 commits, areas: migrations/
   ```
7. Confirm and choose disposition

For standalone tasks (without children), partial revert uses area-based selection — you choose which directories to revert and which to keep.

## Post-Revert Task Management

After the revert is executed, three options control what happens to the original task:

### Delete Task and Plan

Removes the original task and plan files entirely. Use when the feature was a dead end and there's no value in keeping the history beyond git commits. For parent tasks with children, also removes all archived child task and plan files.

### Keep Archived

Adds a "Revert Notes" section to the archived task file documenting what was reverted, when, and by which revert task. The original task stays in the archive as a historical record. This is the most common choice — it preserves the full paper trail.

### Move Back to Ready

Un-archives the task and resets its status to Ready, with revert notes explaining which parts were previously implemented and then reverted. Use when you plan to re-implement the feature differently — the task file retains its context and can be picked up again.

## Relationship to Git Revert

`/aitask-revert` operates at a higher level than `git revert`:

| | `git revert` | `/aitask-revert` |
|---|---|---|
| **Scope** | Individual commits | Entire tasks (potentially spanning many commits) |
| **Granularity** | All-or-nothing per commit | Partial reverts by area or child task |
| **Metadata** | No task awareness | Updates task status, adds revert notes, manages archived state |
| **Planning** | Immediate execution | Creates a structured revert task with implementation plan |
| **Safety** | May conflict silently | Implementation transparency — agent presents impact analysis before changes |
| **Traceability** | Commit message only | Full task chain: original task → revert task → implementation |

For simple single-commit reverts, `git revert` is fine. For multi-commit, multi-area task reverts — especially partial ones — `/aitask-revert` provides the structure and safety net to do it correctly.

## Tips

- **Start with complete reverts** when unsure — they're simpler and you can always re-add specific pieces later
- **Use child-level selection** for parent tasks when you want to revert entire feature slices. Use area-level selection when the revert cuts across child task boundaries
- **Choose "Keep archived"** as the default disposition unless you have a specific reason to delete or re-implement. It costs nothing and preserves the paper trail
- **Review the implementation transparency summary** carefully — the pre-revert impact analysis catches cross-area dependencies that aren't obvious from the commit list alone
- **For large reverts**, consider saving the task for later (`/aitask-pick <N>`) so you can review the revert plan in a fresh context with full attention
