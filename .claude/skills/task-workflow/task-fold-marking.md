# Task Fold Marking Procedure

This shared procedure handles the frontmatter updates that mark tasks as folded:
setting `folded_tasks` on the primary, updating each folded task's status to
`Folded`, and handling transitive folds. It is referenced by aitask-fold (Step 3),
aitask-explore (Step 3), aitask-pr-import (Step 5), and aitask-contribution-review
(Step 6).

## Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `primary_task_num` | Task ID of the primary task receiving the folded tasks | `42` |
| `folded_task_ids` | List of task IDs being folded into the primary | `[12, 15]` |
| `handle_transitive` | Whether to check folded tasks for their own `folded_tasks` and re-point them to the primary (default: `true`) | `true` |
| `commit_mode` | How to commit the changes: `"fresh"` (new commit), `"amend"` (amend previous commit), or `"none"` (caller handles commit) | `"fresh"` |

## Procedure

### Step 1: Check Existing folded_tasks

Read the primary task file's frontmatter. If it already has a `folded_tasks` field, note the existing IDs — new IDs will be appended (merged), not replaced.

### Step 2: Handle Transitive Folded Tasks

**Skip this step if `handle_transitive` is `false`.**

For each task ID in `folded_task_ids`:
1. Read its frontmatter
2. Check if it has a `folded_tasks` field (e.g., `folded_tasks: [B, C]`)
3. If yes, collect those transitive task IDs

Include all transitive IDs in the primary's full `folded_tasks` list.

**Example:** Folding task A (which has `folded_tasks: [B, C]`) into primary D → D gets `folded_tasks: [A, B, C]`, and B/C's `folded_into` must be updated to point to D.

### Step 3: Set folded_tasks Frontmatter

Build the complete list: existing `folded_tasks` (from Step 1) + new `folded_task_ids` + transitive IDs (from Step 2).

```bash
./.aitask-scripts/aitask_update.sh --batch <primary_task_num> --folded-tasks "<comma-separated list of all IDs>"
```

### Step 4: Update Each Folded Task

For each task ID in `folded_task_ids`, set its status to `Folded` and add the `folded_into` reference:

```bash
./.aitask-scripts/aitask_update.sh --batch <folded_task_num> --status Folded --folded-into <primary_task_num>
```

### Step 5: Update Transitive Tasks

**Skip this step if `handle_transitive` is `false` or no transitive tasks were found.**

For each transitive task ID (B, C from the example), update `folded_into` to point to the primary:

```bash
./.aitask-scripts/aitask_update.sh --batch <transitive_task_num> --folded-into <primary_task_num>
```

### Step 6: Commit

Based on `commit_mode`:

**If `"fresh"`:**
```bash
./ait git add aitasks/
./ait git commit -m "ait: Fold tasks into t<primary_task_num>: merge t<id1>, t<id2>, ..."
```

**If `"amend"`:**
```bash
./ait git add aitasks/
./ait git commit --amend --no-edit
```

**If `"none"`:** Skip commit — the caller will handle it.
