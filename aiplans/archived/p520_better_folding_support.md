---
Task: t520_better_folding_support.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

Two problems with folding:

1. **No ad-hoc folding during planning** — When a user requests folding in a task description or during the planning conversation, Claude Code doesn't know what to do because the planning workflow has no instructions for it.

2. **Child tasks can't be folded** — The framework prohibits folding child tasks, but in practice child tasks sometimes need to be folded into other tasks when their requirements fit better elsewhere.

The folding infrastructure (procedures, scripts) is already well-built. The fix is about (a) adding instructions to reference existing procedures from the planning workflow, (b) removing the child task restriction, and (c) adding parent cleanup when a child task is folded.

## Changes

### 1. `task-fold-marking.md` — Add parent cleanup for child tasks

**File:** `.claude/skills/task-workflow/task-fold-marking.md`

Add a new **Step 4b** (after Step 4, before Step 5) that handles child task parent cleanup:

- After setting a folded task to `Folded` status in Step 4, check if the folded task ID contains an underscore (e.g., `16_2`) indicating it's a child task
- If it is a child task, extract the parent number and remove the child from the parent's `children_to_implement`:
  ```bash
  ./.aitask-scripts/aitask_update.sh --batch <parent_num> --remove-child t<parent>_<child>
  ```
- This ensures the parent immediately reflects the correct list of pending children

### 2. `aitask_archive.sh` — Safety-net `--remove-child` in `handle_folded_tasks()`

**File:** `.aitask-scripts/aitask_archive.sh`
**Function:** `handle_folded_tasks()` (line ~302)

After the child ID pattern match (line 302-305), and before the `task_git rm` on line 350, add a safety-net call to remove the child from the parent's `children_to_implement` if this is a child task:

```bash
# If folded task is a child, remove from parent's children_to_implement
if [[ "$folded_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
    local fold_parent="${BASH_REMATCH[1]}"
    "$SCRIPT_DIR/aitask_update.sh" --batch "$fold_parent" --remove-child "t${folded_id}" --silent 2>/dev/null || true
fi
```

This is a no-op if the child was already removed at fold time, but catches edge cases.

### 3. `aitask-fold/SKILL.md` — Allow child tasks to be folded

**File:** `.claude/skills/aitask-fold/SKILL.md`

**Step 0b changes:**
- Line 30: Change parsing to accept child task IDs (e.g., `16_2`) alongside parent IDs
- Line 47: Remove the "must not be a child task" exclusion check
- For child task IDs, resolve with `aitask_query_files.sh child-file <parent> <child>` instead of `task-file <id>`
- Keep other checks: status must be `Ready` or `Editing`, must not have children

**Notes section changes:**
- Line 157: Update to: "Only tasks with status `Ready` or `Editing` and without children are eligible for folding (both standalone and child tasks)"
- Line 158: Remove or replace the "Child tasks cannot be folded" note. Replace with: "When a child task is folded, it is automatically removed from its parent's `children_to_implement` list via the Task Fold Marking Procedure"

### 4. `planning.md` — Add ad-hoc fold instructions

**File:** `.claude/skills/task-workflow/planning.md`
**Location:** After the "Folded Tasks Note" bullet (line 66), add a new sibling bullet.

New "Ad-Hoc Fold Request" bullet that instructs Claude Code to:

1. **Recognize** fold requests in task description text or user conversation
2. **Parse task IDs** — extract referenced numbers, supporting both parent (e.g., `42`) and child (e.g., `16_2`) formats
3. **Resolve each task file:**
   - Parent IDs: `./.aitask-scripts/aitask_query_files.sh task-file <id>`
   - Child IDs (contains underscore): `./.aitask-scripts/aitask_query_files.sh child-file <parent> <child>`
4. **Validate** (same checks as aitask-fold, minus the child exclusion):
   - Status must be `Ready` or `Editing`
   - Must not have children (`./.aitask-scripts/aitask_query_files.sh has-children <id>`)
   - Skip invalid tasks with warnings
5. **Confirm** with user via `AskUserQuestion`
6. **Execute fold:**
   - **Task Fold Content Procedure** (`task-fold-content.md`) → update task description via `aitask_update.sh --batch`
   - **Task Fold Marking Procedure** (`task-fold-marking.md`) with `commit_mode: "fresh"` — this now includes parent cleanup for child tasks (from change #1)
7. **Resume** planning by re-reading the updated task file

### 5. `aitask-pickrem/SKILL.md` — Brief ad-hoc fold reference

**File:** `.claude/skills/aitask-pickrem/SKILL.md`
**Location:** After "Folded Tasks Note" on line 216.

Add compact version referencing `planning.md`'s "Ad-Hoc Fold Request" procedure, but skip the user confirmation step (non-interactive mode).

### 6. `aitask-pickweb/SKILL.md` — Brief ad-hoc fold reference

**File:** `.claude/skills/aitask-pickweb/SKILL.md`
**Location:** After "Folded Tasks Note" on line 177.

Same compact version as pickrem.

## Verification

1. Read all modified files to verify structural consistency
2. Verify `aitask_query_files.sh child-file` command syntax against the script
3. Verify `aitask_update.sh --batch --remove-child` flag exists and works
4. Run `shellcheck .aitask-scripts/aitask_archive.sh` after the shell script change
5. Verify task-fold-marking.md references are consistent with the actual procedure
6. Step 9 (Post-Implementation) in SKILL.md — verify `handle_folded_tasks()` output parsing still works (no new output lines needed)

## Reference: Step 9 (Post-Implementation)

See `.claude/skills/task-workflow/SKILL.md` Step 9 for archival, merge, and cleanup steps. All changes in this plan are markdown/instruction files except for the shell script change in `aitask_archive.sh`. Run `shellcheck` on that file before committing.

## Final Implementation Notes

- **Actual work done:** All 6 planned changes were implemented as designed:
  1. `task-fold-marking.md` — Added Step 4b for child task parent cleanup
  2. `aitask_archive.sh` — Added safety-net `--remove-child` block in `handle_folded_tasks()` (lines ~344-350 of the modified file)
  3. `aitask-fold/SKILL.md` — Step 0b parsing now accepts child IDs, child-task exclusion check removed, child IDs resolved via `child-file` subcommand, Notes section updated
  4. `planning.md` — Added "Ad-Hoc Fold Request" bullet with full inline procedure (parse → resolve → validate → confirm → execute via Task Fold Content + Task Fold Marking → resume)
  5. `aitask-pickrem/SKILL.md` — Added compact reference (non-interactive: skip confirmation)
  6. `aitask-pickweb/SKILL.md` — Same compact reference

- **Deviations from plan:** None. The plan was followed exactly.

- **Issues encountered:** None during implementation. Initial plan only addressed problem #1 (no ad-hoc folding); user pointed out problem #2 (child tasks can't be folded) during plan review, which expanded the scope to include changes 1, 2, and parts of 3.

- **Key decisions:**
  - **Parent cleanup at fold time AND archive time** — Step 4b in task-fold-marking.md handles it eagerly so the parent immediately reflects correct state. The archive script adds a safety-net so edge cases (e.g., manual folding via aitask_update.sh that bypasses the marking procedure) still get cleaned up.
  - **Child task primary task can be folded into a different parent** — A child of t16 can be folded into t42 (a completely different task). The Step 4b note explicitly clarifies this.
  - **Inline procedure in planning.md** — Rather than creating a new shared procedure file, the ad-hoc fold instructions are inlined in planning.md because they reference the existing Task Fold Content + Task Fold Marking procedures. The pickrem/pickweb files just point back to planning.md.
  - **No EnterPlanMode requirement for ad-hoc fold** — The fold operation happens during the planning conversation but doesn't need plan mode itself; it modifies task metadata files via shell commands (which work in plan mode since they're not source code edits).

- **Verification performed:**
  - `shellcheck -e SC1091,SC2012 .aitask-scripts/aitask_archive.sh` — clean (only pre-existing warnings excluded)
  - `bash tests/test_archive_scan.sh` — 23/23 passed
  - `bash tests/test_archive_utils.sh` — 46/46 passed

- **Follow-up work:** Created task t522 (encapsulate_fold_logic_in_scripts) to investigate moving folding procedure logic into helper bash scripts to reduce instruction complexity and improve consistency across callers.

- **Note for related skills:** Per CLAUDE.md, skill changes here are in the Claude Code source of truth (`.claude/skills/`). Equivalent updates for Gemini CLI (`.gemini/skills/`), Codex CLI (`.agents/skills/`), and OpenCode (`.opencode/skills/`) should be tracked as separate aitasks if those tools also use folding.
