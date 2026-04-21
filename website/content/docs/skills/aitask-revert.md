---
title: "/aitask-revert"
linkTitle: "/aitask-revert"
weight: 35
description: "Revert changes associated with completed tasks — fully or partially"
depth: [advanced]
---

Revert changes associated with completed tasks — fully or partially. This skill analyzes a task's commits, identifies affected areas, and creates a self-contained revert task with all the information needed to undo the changes. Use it when a feature adds unnecessary complexity, an experiment didn't pan out, or you want to selectively undo parts of a completed task.

**Usage:**
```
/aitask-revert                  # Interactive: discover task to revert
/aitask-revert 42               # Direct: revert task t42
/aitask-revert t42              # Also accepted with t prefix
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

1. **Profile selection** — Same profile system as `/aitask-pick`
2. **Task discovery** — Three methods to find the task to revert:
   - **Direct ID** — Pass the task number as an argument to skip discovery
   - **Browse recent tasks** — Lists recently implemented tasks from git history with commit counts and dates
   - **Search by files** — Select files in the codebase, then discover which tasks changed them (uses the same file selection as [`/aitask-explain`](../aitask-explain/))
3. **Task analysis** — Displays a detailed summary: commits with change stats, affected directory areas, and per-child breakdown for parent tasks with children
4. **Revert type selection** — Choose between complete revert (all changes) or partial revert (select what to keep and what to undo)
5. **Selection and confirmation** — For complete reverts, choose post-revert disposition. For partial reverts, select areas or child tasks to revert with a confirmation summary showing what will be reverted vs. kept
6. **Revert task creation** — Creates a standalone refactor-type task containing all commit hashes, file lists, area breakdowns, disposition instructions, and implementation transparency requirements
7. **Decision point** — Continue to implementation now or save the revert task for later

## Revert Types

### Complete Revert

Reverts all changes from the task. After reverting, choose what happens to the original task:

- **Delete task and plan** — Remove entirely from the archive
- **Keep archived** — Add revert notes to the archived task file
- **Move back to Ready** — Un-archive and reset status for potential re-implementation

### Partial Revert

Select which parts of the task to undo. For parent tasks with children, two selection modes are available:

- **By child task** — Select which child tasks to revert, keeping others intact. Recommended for reverting entire feature slices
- **By area** — Select directory areas to revert, then see which child tasks are affected (fully, partially, or not at all)

For standalone tasks (no children), partial revert uses area-based selection.

## Key Capabilities

- **Self-contained revert tasks** — The created revert task includes all commit hashes, file lists, area breakdowns, and disposition instructions. The implementing agent doesn't need to re-run analysis
- **Implementation transparency** — The revert task requires the implementing agent to present a detailed pre-revert summary (what will change, impact analysis, cross-area dependencies) for user approval before executing any changes
- **Child-aware partial reverts** — For parent tasks with children, select entire child tasks to revert or drill down to specific areas with automatic child-to-area mapping
- **Deep archive support** — Can discover and revert tasks stored in `old.tar.gz` deep archives
- **Three disposition options** — Control what happens to the original task after reverting: delete, keep archived with notes, or move back to Ready

**Profile key:** `explore_auto_continue` — Reuses the same key as `/aitask-explore`. Set to `true` to skip the "continue to implementation or save" prompt.

## Workflows

For a full workflow guide with examples and tips, see [Revert Changes with AI](../../workflows/revert-changes/).
