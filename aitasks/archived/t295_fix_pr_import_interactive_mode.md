---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [cli]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-03 09:24
updated_at: 2026-03-03 09:56
completed_at: 2026-03-03 09:56
---

Fix bugs and improve UX in the interactive mode of `aiscripts/aitask_pr_import.sh`.

## Bugs to Fix

### 1. Draft not finalized on commit (critical)
**File:** `aiscripts/aitask_pr_import.sh`, `interactive_import_pr()` function (lines ~1216-1244)

The interactive import calls `aitask_create.sh --batch` **without** the `--commit` flag (line 1227), which creates a **draft** in `aitasks/new/` instead of a finalized task with a real ID. The subsequent "Commit to git?" prompt (line 1233) then does `git add` + `git commit` on the draft file — but the task is still in `aitasks/new/` without a real task ID.

**Fix:** Change the end flow to either:
- (a) Add `--commit` to the `aitask_create.sh` call and remove the manual git commit block, OR
- (b) Call `finalize_draft` before committing if the user says yes to commit

Option (a) is cleaner — add `--commit` when the user confirms they want to commit.

### 2. Uses `git` instead of `./ait git`
**File:** `aiscripts/aitask_pr_import.sh`, lines 1239-1240

Uses `git add` and `git commit` directly instead of `./ait git` (or the `task_git` helper from `aitask_create.sh`). This violates the convention for task file commits documented in CLAUDE.md.

**Fix:** Use `task_git` (from `task_utils.sh`) or `./ait git` instead of plain `git`.

### 3. Task ID extraction fails on draft filenames
**File:** `aiscripts/aitask_pr_import.sh`, line 1236

`task_id=$(basename "$created_file" .md | grep -oE '^t[0-9]+')` expects a filename like `t42_name.md` but draft files are named `draft_20260213_1423_name.md`, so `task_id` will be empty.

**Fix:** This is resolved by fix #1 — if we use `--commit`, the file will have a real task ID.

## UX Improvements

### 4. Add info note at start of interactive mode
At the beginning of `run_interactive_mode()`, show a note informing the user that the full PR import flow (with AI analysis, implementation planning, and codebase alignment) is available via the Claude skill:

```
NOTE: For a richer PR import experience with AI analysis, implementation planning,
and codebase alignment, use the Claude Code skill instead:
  /aitask-pr-review
The interactive bash script provides basic metadata import only.
```

### 5. Improve the import confirmation prompt
At the `interactive_import_pr()` confirmation step (line 1049), improve the fzf options with clearer descriptions:

- "Import" → "Import as task (basic — title, body, metadata only)"
- "Data-only (intermediate file)" → "Extract PR data only (for use with /aitask-pr-review skill)"
- "Skip" → "Skip this PR"

Add a note below the fzf selection explaining:
- **Data-only** extracts to `.aitask-pr-data/<N>.md` and can be processed by `/aitask-pr-review` for AI-enriched task creation
- **Import** creates a task directly but without AI analysis, implementation plan, or codebase alignment that the skill provides

### 6. Improve the commit prompt at the end
Replace the bare `read -rp "Commit to git? [Y/n]"` (line 1233) with an fzf-based prompt consistent with the rest of the interactive flow. Options:

- "Finalize and commit" (description: assigns real task ID, moves to aitasks/, commits)
- "Save as draft" (description: keeps in aitasks/new/ for later finalization)
- "Finalize without commit" (description: assigns real task ID but doesn't commit)

### 7. Add note about skill advantages
When the user chooses "Import" (full task creation from bash), print a brief note about what the skill provides that the bash import does not:

```
Tip: The /aitask-pr-review skill provides additional features over this import:
  - AI analysis of PR purpose, quality, and concerns
  - Implementation approach recommendations
  - Testing requirements
  - Codebase alignment checks
  - Related task discovery and folding
```

## References

- `aiscripts/aitask_pr_import.sh` — the script being fixed
- `aiscripts/aitask_create.sh` — task creation with draft/finalize flow
- `.claude/skills/aitask-pr-review/SKILL.md` — the Claude skill for comparison
- See `aitask_create.sh` lines 1231-1300 for the `--commit` vs draft logic
- See `aitask_create.sh` `finalize_draft()` function for the finalization flow
