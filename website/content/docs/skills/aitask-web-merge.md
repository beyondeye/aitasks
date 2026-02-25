---
title: "/aitask-web-merge"
linkTitle: "/aitask-web-merge"
weight: 13
description: "Merge completed Claude Web branches to main and archive task data"
---

Runs **locally** after [`/aitask-pickweb`](../aitask-pickweb/) completes on Claude Code Web. It detects remote branches with completed task executions, merges code to main (excluding `.aitask-data-updated/`), copies the plan to aitask-data, archives the task, and cleans up.

**Usage:**
```
/aitask-web-merge
```

No arguments needed — the skill scans all remote branches automatically.

> **Note:** Must be run from the project root directory on your local machine (not on Claude Code Web). See [Skills overview](..) for details.

## Step-by-Step

The skill follows a **scan → select → merge → archive → push → cleanup** flow:

1. **Scan** — Runs `aitask_web_merge.sh --fetch` to detect remote branches containing `.aitask-data-updated/completed_t*.json` completion markers
2. **Select** — If multiple branches found, presents them for selection (or offers "Process all sequentially")
3. **Pull and merge** — Pulls latest main (`--ff-only`), merges the web branch (`--no-ff --no-commit`), removes `.aitask-data-updated/` from the merge, commits
4. **Copy plan** — Reads the plan from the web branch via `git show`, writes it to `aiplans/` on aitask-data
5. **Archive** — Runs `aitask_archive.sh` to archive the task (and parent if all children are complete)
6. **Push and cleanup** — Pushes main and aitask-data, deletes the remote implementation branch

## Merge Strategy

The merge uses `--no-ff --no-commit` to stage changes without committing, then explicitly removes `.aitask-data-updated/` before the final commit. This ensures:

- The merge commit on main is clean — no temporary metadata files
- The `.aitask-data-updated/` directory only existed on the web branch
- The commit message follows the standard `<issue_type>: <description> (t<task_id>)` format

## Plan File Handling

The plan file is stored on the web branch at `.aitask-data-updated/plan_t<task_id>.md`. During merge, this file is:

1. Read from the remote branch via `git show origin/<branch>:.aitask-data-updated/plan_t<task_id>.md`
2. Written to the correct aitask-data path:
   - Parent tasks: `aiplans/p<N>_<name>.md`
   - Child tasks: `aiplans/p<parent>/p<parent>_<child>_<name>.md`
3. Committed to aitask-data via `./ait git`

The plan filename is derived by replacing the leading `t` with `p` in the task filename.

## Issue Handling

If the archived task (or its parent) has a linked `issue` field, the skill prompts to update or close it using `aitask_issue_update.sh`. Options: close with notes, comment only, close silently, or skip.

## Multiple Branches

When multiple completed branches are detected:

- **Single branch:** Auto-selected, no prompt
- **Multiple branches:** Presented via `AskUserQuestion` with a "Process all sequentially" option
- After processing one branch, the skill offers to continue with remaining branches

## Suggested Workflow

```
Local machine          Claude Code Web           Local machine
─────────────          ───────────────           ─────────────
1. ait lock 42         2. /aitask-pickweb 42     3. /aitask-web-merge
   (lock task)            (implement + commit)      (merge + archive)
```

See [Claude Code Web workflow](../../workflows/claude-web/) for the full end-to-end guide.

## See Also

- [`/aitask-pickweb`](../aitask-pickweb/) — Web-side implementation skill
