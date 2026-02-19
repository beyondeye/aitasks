---
title: "/aitask-fold"
linkTitle: "/aitask-fold"
weight: 30
description: "Identify and merge related tasks into a single task"
---

Identify and merge related tasks into a single task, then optionally execute it. This skill provides the same folding capability as `/aitask-explore` but as a standalone workflow — no codebase exploration required.

**Usage:**
```
/aitask-fold                    # Interactive: discover and fold related tasks
/aitask-fold 106,108,112        # Explicit: fold specific tasks by ID
```

## Workflow Overview

1. **Profile selection** — Same profile system as `/aitask-pick`
2. **Task discovery** — In interactive mode, lists all eligible tasks (`Ready`/`Editing` status, not a child task, no children of their own), identifies related groups by shared labels and semantic similarity, and presents them for multi-select. In explicit mode, validates the provided task IDs and skips discovery
3. **Primary task selection** — Choose which task survives as the primary. All other tasks' content is merged into it. The originals are set to `Folded` status (with a `folded_into` reference to the primary) and deleted after the primary task is archived
4. **Content merging** — Non-primary task descriptions are appended under `## Merged from t<N>` headers. The `folded_tasks` frontmatter field tracks which tasks were folded in (appends to existing if present)
5. **Optional handoff** — Continue directly to implementation (via the standard `/aitask-pick` workflow) or save the merged task for later

## Key Capabilities

- **Two invocation modes** — Interactive discovery for finding related tasks, or explicit task IDs for quick folding when you already know what to merge
- **Graceful validation** — Invalid or ineligible tasks are warned and skipped rather than aborting. The workflow only aborts if fewer than 2 valid tasks remain
- **Append-safe** — If the primary task already has `folded_tasks` from a previous fold, new IDs are appended rather than replacing
- **Same cleanup mechanism** — Uses the same `folded_tasks` frontmatter field as `/aitask-explore`. Post-implementation cleanup (deletion of folded task files) is handled by the shared task-workflow Step 9

**Profile key:** `explore_auto_continue` — Reuses the same key as `/aitask-explore`. Set to `true` to skip the "continue to implementation or save" prompt.

For a full workflow guide, see [Task Consolidation](../../workflows/task-consolidation/).
