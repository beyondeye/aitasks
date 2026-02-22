---
name: aitask-wrap
description: Wrap uncommitted changes into an aitask with retroactive documentation and traceability.
---

Retroactively wraps uncommitted changes into the aitasks framework. Analyzes the diff, creates a task file and plan file documenting the changes and probable intent, commits the code changes with proper format, and archives the task — all in one flow.

## Workflow

### Step 0: Detect Uncommitted Changes

Check for uncommitted changes (both staged and unstaged):

```bash
git status --porcelain
```

**If no output** (no changes at all):
- Display: "No uncommitted changes found. Nothing to wrap."
- Abort the workflow.

**If changes exist:**

Display a summary of changes:

```bash
git diff --stat
git diff --cached --stat
```

Show the user a brief overview: number of files changed, insertions, deletions.

### Step 0b: Select Files to Include

List all changed files (staged + unstaged + untracked):

```bash
git status --porcelain
```

Use `AskUserQuestion`:
- Question: "Which changes should be included in this wrap?"
- Header: "Files"
- Options:
  - "All changes" (description: "Include all modified, staged, and untracked files")
  - "Let me select" (description: "Choose specific files to include")

**If "Let me select":**

Present the file list using `AskUserQuestion` with `multiSelect: true`:
- Question: "Select files to include:"
- Header: "Select"
- Options: Each changed file as an option (group by status: staged, modified, untracked)

Note: If more than 4 files, use pagination (3 files per page + "Show more" option). Accumulate selections across pages.

Store the selected file list for use in subsequent steps.

**If "All changes":**
- Include everything shown by `git status --porcelain`

### Step 1: Analyze Changes

Read the full diff for included files:

```bash
git diff -- <file1> <file2> ...
git diff --cached -- <file1> <file2> ...
```

For untracked files, read their content directly.

**Analyze the changes to determine:**

1. **Factual summary**: What was changed (files, functions, behavior)
2. **Probable user intent**: Why these changes were likely made
3. **Suggested issue_type**: One of `feature`, `bug`, `refactor`, `chore`, `documentation`, `performance`, `style`, `test` — based on the nature of changes
4. **Suggested task name**: A short, descriptive name suitable for a filename (lowercase, underscores, max 50 chars)
5. **Suggested labels**: Based on file paths and content (e.g., `ui`, `backend`, `tests`)
6. **Suggested priority**: `medium` by default, `high` if it looks like a critical fix
7. **Suggested effort**: Assess from diff size (`low` for <50 lines, `medium` for 50-200, `high` for 200+)

### Step 2: Present Analysis and Confirm

Display the analysis in a structured format:

```
## Wrap Analysis

**Task name:** <suggested_name>
**Issue type:** <suggested_type>
**Priority:** <suggested_priority> | **Effort:** <suggested_effort>
**Labels:** <suggested_labels>

**Task summary:**
<1-3 sentence summary for the task file>

**Plan summary:**
<detailed description of changes and probable intent for the plan file>

**Files to commit:**
<list of files>

**Commit message:** <type>: <description> (tN)
```

Use `AskUserQuestion`:
- Question: "Does this analysis look correct?"
- Header: "Confirm"
- Options:
  - "Looks good" (description: "Proceed with these values")
  - "Adjust task name or metadata" (description: "Change name, type, priority, effort, or labels")
  - "Adjust descriptions" (description: "Edit the task summary or plan content")

**If "Adjust task name or metadata":**

Use `AskUserQuestion` to ask which field to change:
- Question: "What would you like to adjust?"
- Header: "Adjust"
- Options:
  - "Task name" (description: "Change the suggested task name")
  - "Issue type" (description: "Change the issue type classification")
  - "Priority/Effort" (description: "Change priority or effort level")
  - "Labels" (description: "Change the suggested labels")

For each selection, use `AskUserQuestion` with appropriate options or free text input. After adjustment, return to the beginning of Step 2 to re-display.

**If "Adjust descriptions":**

Use `AskUserQuestion`:
- Question: "What would you like to adjust?"
- Header: "Adjust"
- Options:
  - "Task summary" (description: "Edit the brief task description")
  - "Plan content" (description: "Edit the detailed plan/intent description")
  - "Both" (description: "Edit both task summary and plan content")

For each, ask the user for the replacement text via free text input (use "Other" option). After adjustment, return to the beginning of Step 2 to re-display.

### Step 3: Final Confirmation

Display a complete summary of everything that will happen:

```
## Ready to Execute

1. Create task: t<N>_<name>.md (priority: <p>, effort: <e>, type: <type>)
2. Create plan: aiplans/p<N>_<name>.md
3. Commit code: "<type>: <description> (tN)"
4. Archive task and plan

Files to be committed:
<file list>
```

Use `AskUserQuestion`:
- Question: "Ready to commit and wrap these changes?"
- Header: "Execute"
- Options:
  - "Yes, proceed" (description: "Create task, commit changes, and archive")
  - "Go back" (description: "Return to adjust analysis")
  - "Abort" (description: "Cancel — no changes will be made")

**If "Go back":** Return to Step 2.
**If "Abort":** Display "Wrap cancelled. No changes were made." and end.
**If "Yes, proceed":** Continue to Step 4.

### Step 4: Execute

All steps execute sequentially without further user prompts.

#### 4a: Create Task File

```bash
./aiscripts/aitask_create.sh --batch --commit \
  --name "<task_name>" \
  --desc-file - \
  --priority <priority> \
  --effort <effort> \
  --type <issue_type> \
  --labels "<labels>" <<'TASK_DESC'
<task summary content>
TASK_DESC
```

**Parse output** to extract the created task filename and ID:
```bash
git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

Extract `<N>` from the filename `t<N>_<name>.md`.

#### 4b: Create Plan File

Write the plan file to `aiplans/p<N>_<name>.md`:

```markdown
---
Task: t<N>_<name>.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

<factual summary of what was changed>

## Files Modified

<per-file descriptions of changes>

## Probable User Intent

<analysis of why these changes were likely made>

## Final Implementation Notes

- **Actual work done:** <summary of the implemented changes>
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed)
- **Issues encountered:** N/A (changes were already made before wrapping)
- **Key decisions:** <any notable technical decisions visible in the diff>
```

#### 4c: Stage and Commit Code Changes

Stage the selected files and the plan file, then commit:

```bash
git add <selected_files> aiplans/p<N>_<name>.md
git commit -m "<issue_type>: <description> (t<N>)"
```

Where `<description>` is a concise commit message derived from the task summary.

**Important:** The commit message MUST use the `<issue_type>: <description> (t<N>)` format. This is required for `aitask_issue_update.sh` to find commits associated with a task.

#### 4d: Archive Task

```bash
./aiscripts/aitask_archive.sh <N>
```

Parse the script output and handle structured lines:
- `ISSUE:<task_num>:<issue_url>` — unlikely for wrap (no linked issue), but handle per task-workflow Issue Update Procedure if present
- `COMMITTED:<hash>` — archival commit was created
- Other lines — display as informational

#### 4e: Push

```bash
git push
```

### Step 5: Summary

Display the final summary:

```
## Wrap Complete

- Task: t<N>_<name>.md (archived)
- Plan: aiplans/archived/p<N>_<name>.md
- Code commit: <hash> — <issue_type>: <description> (t<N>)
- Archive commit: <hash>
- Pushed to remote
```

## Edge Cases

### No Uncommitted Changes
If `git status --porcelain` returns empty, abort immediately with a clear message.

### Very Large Diffs
If the diff exceeds ~2000 lines, truncate for analysis but still include all files in the commit. Display a warning: "Large diff detected — analysis may not capture all details. Please review the generated descriptions carefully."

### Untracked Files
Untracked files shown by `git status --porcelain` (lines starting with `??`) should be included in the file selection. Read their content directly (not via `git diff`) for analysis.

### Mixed Staged and Unstaged Changes
Both are included. `git diff` shows unstaged, `git diff --cached` shows staged. Both are analyzed and committed together.

### Task Creation Fails
If `aitask_create.sh --batch --commit` fails (e.g., no network for atomic counter), display the error and abort. No code changes will have been committed at this point.

### Archive Fails
If `aitask_archive.sh` fails, display the error. The task and code commit will still exist — the user can archive manually later with `ait archive <N>`.

## Notes

- This skill is self-contained — no handoff to task-workflow since the work is already complete
- The plan file uses "Final Implementation Notes" format because implementation already happened before wrapping
- Only source code commits use the `<issue_type>: <description> (tN)` format. The task creation commit (from aitask_create.sh) and archive commit (from aitask_archive.sh) use the `ait:` prefix automatically
- Labels are read from `aitasks/metadata/labels.txt` for suggestions; new labels can be used freely
