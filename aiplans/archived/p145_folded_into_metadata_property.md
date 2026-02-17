---
Task: t145_folded_into_metadata_property.md
---

## Context

When tasks are folded into another task (via `/aitask-fold` or `/aitask-explore`), the primary task gets a `folded_tasks` frontmatter field listing the folded IDs. However, the folded tasks themselves receive no indication they've been folded — they keep their original `Ready`/`Editing` status and have no reference back to the target task. This makes it hard to identify folded tasks in listings and the board UI.

This change adds:
1. A new `Folded` task status
2. A new `folded_into` frontmatter property on folded tasks (pointing to the target task number)
3. Board UI support for displaying/navigating `folded_into`
4. Skill updates to set these properties when folding

## Implementation Plan

### 1. `aiscripts/aitask_update.sh` — Foundation

**1a. Add batch variables** (after line 46):
```bash
BATCH_FOLDED_INTO=""
BATCH_FOLDED_INTO_SET=false
```

**1b. Add `CURRENT_FOLDED_INTO`** (after line 63):
```bash
CURRENT_FOLDED_INTO=""
```

**1c. Update help text** (line 84): Add `Folded` to status list

**1d. Add `--folded-into` to help text** (after `--folded-tasks` help at ~line 101):
```
  --folded-into NUM      Task number this task was folded into (use "" to clear)
```

**1e. Add `--folded-into` to arg parsing** (after line 179):
```bash
--folded-into) BATCH_FOLDED_INTO="$2"; BATCH_FOLDED_INTO_SET=true; shift 2 ;;
```

**1f. Add to parse reset block** (line 255 area): `CURRENT_FOLDED_INTO=""`

**1g. Add parsing case** (after `folded_tasks` case ~line 319):
```bash
folded_into) CURRENT_FOLDED_INTO="$value" ;;
```

**1h. Add `Folded` to status validation** (line 1197):
`Ready|Editing|Implementing|Postponed|Done|Folded`

**1i. Add `Folded` to interactive status selection** (line 760):
Add `\nFolded` to the echo string

**1j. Add `folded_into` to has_update check** (after line 1174):
```bash
[[ "$BATCH_FOLDED_INTO_SET" == true ]] && has_update=true
```

**1k. Add `folded_into` processing in batch apply** (after line 1265):
```bash
local new_folded_into="$CURRENT_FOLDED_INTO"
if [[ "$BATCH_FOLDED_INTO_SET" == true ]]; then
    new_folded_into="$BATCH_FOLDED_INTO"
fi
```

**1l. Update `write_task_file()` function** (line 378):
- Add parameter 16: `local folded_into="${16:-}"`
- After `folded_tasks` block (line 424), add:
  ```bash
  if [[ -n "$folded_into" ]]; then
      echo "folded_into: $folded_into"
  fi
  ```

**1m. Update all 3 `write_task_file` call sites** to pass `folded_into` as 16th arg:
- Line 653-656 (handle_child_task_completion): add `"$CURRENT_FOLDED_INTO"`
- Line 1101-1104 (interactive mode): add `"$CURRENT_FOLDED_INTO"`
- Line 1286-1289 (batch mode): add `"$new_folded_into"`

**1n. Update save/restore in handle_child_task_completion** (lines 631-678):
- Add `local saved_folded_into="$CURRENT_FOLDED_INTO"` with saves
- Add `CURRENT_FOLDED_INTO="$saved_folded_into"` with restores

### 2. `aiscripts/board/aitask_board.py` — Board UI

**2a. Create `FoldedIntoField` widget** (after `FoldedTasksField` at line 746):
- Model on `ParentField` (lines 749-777) — same pattern: display a task number, Enter navigates to it
- `render()`: `"  [b]Folded Into:[/b] t{self.target_num}"`
- `on_key(enter)`: find task by ID via `self.manager.find_task_by_id()`, push `TaskDetailScreen`

**2b. Add `Folded` to read-only check** in `TaskDetailScreen.compose()` (line 1094-1095):
```python
is_done = meta.get("status", "") == "Done"
is_folded = meta.get("status", "") == "Folded"
is_done_or_ro = is_done or is_folded or self.read_only
```

**2c. Display `folded_into` in compose()** (after `folded_tasks` block, ~line 1160):
```python
if meta.get("folded_into"):
    folded_into_num = str(meta["folded_into"])
    if self.manager:
        yield FoldedIntoField(folded_into_num, self.manager, classes="meta-ro")
    else:
        yield ReadOnlyField(
            f"[b]Folded Into:[/b] t{folded_into_num}", classes="meta-ro")
```

**2d. Update `can_delete` logic** (line 1174): Add `and not is_folded`:
```python
can_delete = (not is_done and not is_folded and not self.read_only
              and self.task_data.metadata.get("status", "") != "Implementing"
              and not is_child)
```

Note: `Folded` is NOT added to CycleField status options — it's set programmatically only.

**2e. Show `folded_into` in TaskCard** (in `TaskCard.compose()`, after status_parts block ~line 420):
Add a line to display `folded_into` on the card itself (not just detail view):
```python
folded_into = meta.get('folded_into')
if folded_into:
    yield Label(f"📎 folded into t{folded_into}", classes="task-info")
```

**2f. Unfold tasks when deleting a task with `folded_tasks`**:

In `_execute_delete()` (line 1866), before deleting files, check if the task has `folded_tasks`. If so, revert each folded task to `Ready` and clear its `folded_into` property using `aitask_update.sh`:

```python
def _execute_delete(self, task_num: str, paths: list, task: Task = None):
    # Unfold folded tasks before deleting
    if task:
        folded = task.metadata.get("folded_tasks", [])
        for fid in folded:
            fid_str = str(fid).lstrip("t")
            subprocess.run(
                ["./aiscripts/aitask_update.sh", "--batch", fid_str,
                 "--status", "Ready", "--folded-into", ""],
                capture_output=True, text=True, timeout=10
            )
    # ... rest of existing delete logic
```

Update callers to pass the `task` object:
- Line 1616 in `action_view_details`: `self._execute_delete(task_num, paths, focused.task_data)`

### 3. `aiscripts/aitask_ls.sh` — Task Listing

**3a. Update help text** (line 22): Add `Folded` to status values list

**3b. Update metadata format** (line 41): Add `|Folded` to status examples

**3c. Update `display_status` logic** (lines 405-413): Show actual status for non-Ready tasks:
```bash
if [ "$blocked" -eq 1 ]; then
    display_status="Blocked (by $d_text)"
elif [ "$has_children" -eq 1 ]; then
    display_status="Has children"
elif [[ "$status_text" != "Ready" ]]; then
    display_status="$status_text"
else
    display_status="Ready"
fi
```

Note: Default filter is `Ready`, so `Folded` tasks are automatically hidden. They appear with `--status Folded` or `--status all`.

### 4. `.claude/skills/aitask-fold/SKILL.md` — Fold Skill

**4a. Add new Step 3e** (between current 3d and 3e, renumber current 3e→3f):

```markdown
#### 3e: Update Folded Tasks Status

For each non-primary task ID that was folded:

\```bash
./aiscripts/aitask_update.sh --batch <folded_task_num> --status Folded --folded-into <primary_num>
\```
```

**4b. Update Notes section** (line 240): Change "remain in their original status (`Ready`/`Editing`)" to "are set to status `Folded` with a `folded_into` property pointing to the primary task"

**4c. Update eligibility exclusion** (lines 92-95): Add `Folded` to the explicit exclusion list

### 5. `.claude/skills/aitask-explore/SKILL.md` — Explore Skill

**5a. Add folded task status update** after `folded_tasks` is set (~line 217-221):

```markdown
# Update each folded task's status and folded_into reference
for folded_id in <folded_task_ids>; do
    ./aiscripts/aitask_update.sh --batch $folded_id --status Folded --folded-into <task_num>
done

# Amend the commit to include folded task status changes
git add aitasks/
git commit --amend --no-edit
```

**5b. Update eligibility filter** (line 143-146): Add `Folded` to exclusion list

**5c. Update Notes** (line 269): Mention `Folded` status is set on folded tasks

### 6. `.claude/skills/task-workflow/SKILL.md` — Task Workflow

**6a. Update Notes** (line 663): Change wording to reflect tasks now have `Folded` status instead of "remaining in original status"

## Files Modified

| File | Changes |
|------|---------|
| `aiscripts/aitask_update.sh` | Add `Folded` status, `--folded-into` param, parse/write/save-restore logic |
| `aiscripts/board/aitask_board.py` | Add `FoldedIntoField` widget, read-only for Folded status, display+navigation, card display, unfold on delete |
| `aiscripts/aitask_ls.sh` | Help text, display_status shows actual status for non-Ready tasks |
| `.claude/skills/aitask-fold/SKILL.md` | New step 3e to set Folded status + folded_into on non-primary tasks |
| `.claude/skills/aitask-explore/SKILL.md` | Set Folded status + folded_into on folded tasks after creation |
| `.claude/skills/task-workflow/SKILL.md` | Update notes about Folded status |

## Verification

1. **aitask_update.sh**: Test batch mode:
   ```bash
   ./aiscripts/aitask_update.sh --batch 145 --status Folded --folded-into 100
   # Verify frontmatter contains status: Folded and folded_into: 100
   # Then revert
   ./aiscripts/aitask_update.sh --batch 145 --status Implementing --folded-into ""
   ```

2. **Board UI**: Run `python aiscripts/board/aitask_board.py` and:
   - Create a test task with `status: Folded` and `folded_into: 145`
   - Verify the task card shows `📎 folded into t145` on the board
   - Verify it opens as read-only in detail view
   - Verify `Folded Into: t145` field is displayed and Enter navigates to t145
   - Verify Pick/Edit/Delete buttons are disabled
   - Test deleting a task that has `folded_tasks`: verify folded tasks revert to `Ready` and lose their `folded_into` property

3. **aitask_ls.sh**: Verify `./aiscripts/aitask_ls.sh -v --status Folded 99` shows folded tasks, and default listing hides them

## Final Implementation Notes

- **Actual work done:** Implemented all planned changes across 6 files. Added `Folded` status and `folded_into` property to aitask_update.sh, board UI (card + detail view with navigation), aitask_ls.sh, and 3 skill files. Also added unfold-on-delete logic in the board.
- **Deviations from plan:** Used unicode `\U0001f4ce` (paperclip) for the card display instead of emoji literal `📎` for consistency with other unicode references in the code.
- **Issues encountered:** None — all syntax checks passed on first try.
- **Key decisions:** `Folded` status is NOT available in the CycleField UI — it can only be set programmatically via skills. `FoldedIntoField` modeled on the existing `ParentField` pattern for consistency.

## Step 9 (Post-Implementation)

Archive t145 task and plan files after implementation is committed.
