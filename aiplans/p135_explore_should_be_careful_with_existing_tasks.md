---
Task: t135_explore_should_be_careful_with_existing_tasks.md
Branch: main
Base branch: main
---

# Implementation Plan: t135 — Explore Should Be Careful with Existing Tasks

## Context

During `/aitask-explore`, Claude sometimes reads existing pending tasks and silently integrates their content into newly created tasks. This happened with t133 (restructure README into docs), which informally referenced t106 and t129_5 in its description but left those tasks as `Ready` — never archived after t133 was implemented. The fix adds a structured step for detecting related tasks, getting user approval for folding them in, and automatically deleting folded tasks post-implementation (their content is fully incorporated into the new task and its plan).

## Changes

### File 1: `aiscripts/aitask_update.sh` — Add `folded_tasks` frontmatter support

Add support for reading, writing, and updating a `folded_tasks` YAML list field (format matches `depends` and `children_to_implement`).

**1. New batch variables** (around line 43, after `BATCH_ISSUE_SET`):
```bash
BATCH_FOLDED_TASKS=""
BATCH_FOLDED_TASKS_SET=false
```

**2. New current value** (around line 60, after `CURRENT_ISSUE`):
```bash
CURRENT_FOLDED_TASKS=""
```

**3. parse_args** — add case (around line 172, after `--issue`):
```bash
--folded-tasks) BATCH_FOLDED_TASKS="$2"; BATCH_FOLDED_TASKS_SET=true; shift 2 ;;
```

**4. show_help** — add under "Other options" section (around line 109):
```
Folded task options (batch mode):
  --folded-tasks TASKS   Folded task IDs (comma-separated, e.g., "106,129_5"; use "" to clear)
```

**5. parse_yaml_frontmatter** — reset `CURRENT_FOLDED_TASKS=""` (around line 247), and add case in the key parser (around line 308, after `issue`):
```bash
folded_tasks)
    CURRENT_FOLDED_TASKS=$(echo "$value" | tr -d '[]' | tr -d ' ')
    ;;
```

**6. write_task_file** — add 15th parameter and output (after `children_to_implement` block, around line 406):
```bash
local folded_tasks="${15:-}"
# Only write folded_tasks if present
if [[ -n "$folded_tasks" ]]; then
    local folded_yaml
    folded_yaml=$(format_yaml_list "$folded_tasks")
    echo "folded_tasks: $folded_yaml"
fi
```

**7. run_batch_mode** — add to `has_update` check (around line 1153):
```bash
[[ "$BATCH_FOLDED_TASKS_SET" == true ]] && has_update=true
```
Add processing (around line 1237, after issue processing):
```bash
local new_folded_tasks="$CURRENT_FOLDED_TASKS"
if [[ "$BATCH_FOLDED_TASKS_SET" == true ]]; then
    new_folded_tasks="$BATCH_FOLDED_TASKS"
fi
```
Add `"$new_folded_tasks"` as 15th argument to both `write_task_file` calls.

**8. run_interactive_mode** — pass `$CURRENT_FOLDED_TASKS` through as 15th argument to `write_task_file` (preserve existing value).

**9. handle_child_task_completion** — save/restore `CURRENT_FOLDED_TASKS` alongside other fields, pass through as 15th argument to `write_task_file`.

### File 2: `.claude/skills/aitask-explore/SKILL.md`

#### 2a. Insert new Step 2b (Related Task Discovery) — after line 131 (end of Step 2)

When the user selects "Create a task" in Step 2, before proceeding to Step 3:

1. List all pending tasks: `./aiscripts/aitask_ls.sh -v --status all --all-levels 99`
2. Filter to only Ready/Editing status, exclude tasks with children and child tasks
3. Read each candidate's title + first few lines of body text
4. Use judgment to identify tasks whose scope overlaps with exploration findings
5. If related tasks found: present via `AskUserQuestion` with `multiSelect: true`
   - User selects which tasks will be fully folded into the new one
   - Include a "None — no tasks to fold in" option
6. If no related tasks found: inform user and proceed
7. Store selected task IDs as `folded_tasks` list for Step 3

**Scope rule:** Only standalone parent tasks without children can be folded into the new task.

#### 2b. Modify Step 3 (Task Creation) — around lines 133-171

When `folded_tasks` is non-empty:

1. **Incorporate folded task content into the new task description.** Read the full description of each folded task and merge their requirements, details, and context into the new task's description. The new task description must be self-contained — it should contain all relevant information from the folded tasks so that at implementation time, the original folded task files never need to be read. The folded task files exist only as references for cleanup (deletion) after implementation.

2. Append a "Folded Tasks" reference section at the end of the task description:
```markdown
## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t106** (`t106_missing_install_doc_for_windows_and_gh.md`)
- ...
```

2. After `aitask_create.sh --batch --commit` creates the task, set the `folded_tasks` frontmatter field:
```bash
# Get the created task file and number
task_file=$(git log -1 --name-only --pretty=format:'' | grep '^aitasks/t')
task_num=$(echo "$task_file" | grep -oE 't[0-9]+' | head -1 | sed 's/t//')

# Set folded_tasks via aitask_update.sh (no --commit, we'll amend)
./aiscripts/aitask_update.sh --batch "$task_num" --folded-tasks "<comma-separated IDs>"

# Amend the create commit to include the frontmatter update
git add "$task_file"
git commit --amend --no-edit
```

#### 2c. Update Step 5 (Hand Off) context variables — around line 199

Add `folded_tasks` to the context variables list passed to task-workflow.

#### 2d. Update Notes section — after line 216

Add notes about the folded tasks feature and scope restrictions.

### File 3: `.claude/skills/task-workflow/SKILL.md`

#### 3a. Update Context Requirements table — around line 9

Add `folded_tasks` row: `array/null`, list of task IDs folded into this task.

#### 3b. Add folded-task note to Step 6.1 (Planning) — around line 219

Insert a brief note before the "Complexity Assessment" subsection:

- If the task has a `folded_tasks` frontmatter field, note that the task description already contains all relevant content from the folded tasks (folded task content was incorporated at creation time in aitask-explore Step 3). There is no need to read the original folded task files during planning — they exist only as references for post-implementation cleanup.

#### 3c. Add folded-task cleanup to Step 9 (Post-Implementation) — in the "For parent tasks" section, after plan archival but before the commit

Read the `folded_tasks` frontmatter field from the archived task file. For each task ID:
1. Resolve the task file: `ls aitasks/t<N>_*.md`
2. If file exists and status is NOT `Implementing`/`Done`:
   - Delete the task file:
     ```bash
     git rm aitasks/<folded_task_file>
     ```
   - Delete any associated plan file:
     ```bash
     git rm aiplans/p<folded_id>_*.md 2>/dev/null || true
     ```
   - Release lock (best-effort):
     ```bash
     ./aiscripts/aitask_lock.sh --unlock <folded_task_num> 2>/dev/null || true
     ```
   - Execute Issue Update Procedure if issue is linked (note in the comment that the task was folded into t<task_id>)
3. If file doesn't exist: skip silently (already deleted or archived)
4. If status is `Implementing`/`Done`: warn user, skip automatic deletion
5. All deletions are staged via `git rm` and included in the same commit

Add note: since aitask-explore creates standalone parent tasks only, child task archival path does not need folded_tasks handling.

#### 3d. Update Notes section — around line 624

Add notes about:
- Folded tasks remaining in original status until deleted in Step 9 (never set to Implementing)
- Folded tasks are deleted (not archived) because their content is fully incorporated into the new task and its plan

## Key Design Decisions

1. **`folded_tasks` as a frontmatter field** — stored as a YAML list (same format as `depends` and `children_to_implement`), managed by `aitask_update.sh`. Machine-readable and reliable for Step 9 cleanup. The folded task content is fully incorporated into the new task's description at creation time, so the original files are never read at implementation time — they exist only as references for deletion after the new task is completed.
2. **Folded tasks NOT set to Implementing** — avoids complicating the Task Abort Procedure. They stay at Ready/Editing until deleted.
3. **Delete, don't archive** — folded tasks are deleted rather than archived because all their information is incorporated into the new task and its plan.
4. **Only parent tasks without children can be folded in** — folding in children or parents-with-children is too complex.
5. **No new profile key** — related task discovery is lightweight (one prompt) and should always involve user judgment.

## Verification

1. Read the modified files and verify all new sections are correctly placed and internally consistent
2. Test `aitask_update.sh --batch <num> --folded-tasks "106,129_5"` sets the field correctly
3. Test that `write_task_file` correctly preserves `folded_tasks` when other fields are updated
4. Verify the new Step 2b correctly references `aitask_ls.sh` flags and filtering logic
5. Verify Step 9 deletion procedure handles edge cases: missing files, already-deleted tasks, Implementing/Done status
6. Verify Step 6.1 planning check is positioned before the Complexity Assessment
7. Run a dry mental walkthrough of the full explore -> create -> plan -> implement -> archive flow with folded tasks

## Final Implementation Notes

- **Actual work done:** All three files modified as planned. `aitask_update.sh` got full `folded_tasks` support (parse, write, batch update, preservation through interactive and child completion flows). `aitask-explore/SKILL.md` got Step 2b (Related Task Discovery) with user-controlled folding and Step 3 modifications for content incorporation + frontmatter update. `task-workflow/SKILL.md` got context table update, planning note, and Step 9 cleanup procedure.
- **Deviations from plan:** None. Implementation followed the plan exactly.
- **Issues encountered:** None. The `aitask_update.sh --folded-tasks` feature was tested end-to-end (set, preserve across updates, clear) and all tests passed.
- **Key decisions:** `folded_tasks` field positioned after `labels` and before `assigned_to` in the YAML frontmatter output order, consistent with other list fields.
