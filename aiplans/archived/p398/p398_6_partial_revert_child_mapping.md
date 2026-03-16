---
Task: t398_6_partial_revert_child_mapping.md
Parent Task: aitasks/t398_aitask_revert.md
Sibling Tasks: aitasks/t398/t398_4_website_documentation.md, aitasks/t398/t398_5_revert_whitelist_registration.md
Archived Sibling Plans: aiplans/archived/p398/p398_1_revert_analyze_script.md, aiplans/archived/p398/p398_2_revert_skill.md, aiplans/archived/p398/p398_3_post_revert_integration.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t398_6 — Partial Revert Child Mapping

## Context

The aitask-revert skill's partial revert flow (Step 3b) presents areas grouped by directory from `--task-areas`. For parent tasks with children, this isn't the most natural granularity — users more likely want to "revert child task X's changes" rather than "revert directory Y". The `--task-commits` output already tags each commit with its originating child task ID, but this information isn't surfaced during partial revert area selection.

## Steps

### Step 1: Add `--task-children-areas <id>` subcommand to `aitask_revert_analyze.sh`

**File:** `.aitask-scripts/aitask_revert_analyze.sh`

Add a new subcommand that groups areas by child task ID. This reuses the existing `build_search_ids()`, `get_child_ids()`, and area aggregation logic from `cmd_task_areas()`.

**New function `cmd_task_children_areas()`:**
- Call `get_child_ids()` to get child IDs
- If no children → output `NO_CHILDREN` and return
- For each child ID:
  - Collect commit hashes for that child only (grep for `(t<child_id>)`)
  - Run area aggregation on those commits (same logic as `cmd_task_areas()`)
  - Resolve child task name from filename (via `aitask_query_files.sh child-file` or `all-children`)
  - Output header: `CHILD_HEADER|<child_id>|<child_name>|<commit_count>`
  - Output areas: `CHILD_AREA|<child_id>|<dir>|<file_count>|<ins>|<del>|<file_list>`
- For parent-level commits (tagged with parent ID, not any child):
  - Collect commit hashes for parent ID only
  - Run area aggregation
  - Output: `PARENT_HEADER|<parent_id>|<commit_count>`
  - Output: `PARENT_AREA|<parent_id>|<dir>|<file_count>|<ins>|<del>|<file_list>`

**Helper function `_collect_hashes_for_id()`:** Extract the commit-hash-collection logic from `collect_commit_hashes()` but for a single ID (no children expansion). Used by `cmd_task_children_areas()` to get commits per-child.

**Registration:** Add `--task-children-areas` to `parse_args()`, `show_help()`, and `main()` case statement.

### Step 2: Update SKILL.md Step 2 — Enhanced per-child display

**File:** `.claude/skills/aitask-revert/SKILL.md` (Step 2: Task Analysis & Confirmation, around line 95-128)

After the existing per-child commit count breakdown, add per-child area details. The SKILL should run the new subcommand:

```bash
./.aitask-scripts/aitask_revert_analyze.sh --task-children-areas <id>
```

Update the display template to show:
```
### Per-Child Breakdown (if parent with children)
- t<id>_1 (<name>): <N> commits
  Areas: <dir1>/, <dir2>/
- t<id>_2 (<name>): <N> commits
  Areas: <dir3>/
- Parent-level: <N> commits (if any)
  Areas: <dir4>/
```

### Step 3: Update SKILL.md Step 3b — Dual-mode selection for parent tasks

**File:** `.claude/skills/aitask-revert/SKILL.md` (Step 3b: Partial Revert Path, around line 166-208)

Add a new conditional flow at the start of Step 3b for parent tasks with children.

**For parent tasks with children** (check: `--task-children-areas` returned data, not `NO_CHILDREN`):

First, ask selection mode via `AskUserQuestion`:
- Question: "This is a parent task with children. How do you want to select what to revert?"
- Header: "Selection"
- Options:
  - "By child task" (description: "Select which child tasks to revert — recommended for reverting entire feature slices")
  - "By area" (description: "Select directory areas to revert, then see which child tasks are affected")

#### Mode A: By child task

1. Present child tasks as multiSelect options:
   - **If <= 4 children (+ parent-level if present):** Show all as multiSelect options
     - Each child: label = `t<id>_<N> (<name>)`, description = `<commit_count> commits, areas: <area_list>`
     - If parent-level commits exist: add option label = `Parent-level commits`, description = `<N> commits, areas: <area_list>`
   - **If > 4 items:** List all children in the question text, then provide options:
     - "All children" (description: "Revert all child tasks")
     - First 2-3 children as individual options
     - Free text via "Other" for comma-separated child IDs

2. After child selection, show confirmation summary:
   ```
   ## Revert Summary

   ### Will REVERT:
   - t<id>_1 (<name>) — <N> commits, areas: <dir1>/, <dir2>/
   - t<id>_3 (<name>) — <N> commits, areas: <dir3>/

   ### Will KEEP:
   - t<id>_2 (<name>) — <N> commits, areas: <dir4>/
   ```

3. Confirm/Adjust/Cancel (same AskUserQuestion pattern as current Step 3b)

4. After confirmation, collect per-area commit mapping for selected children (same `git diff-tree` logic as current Step 3b, but only for commits from selected children)

#### Mode B: By area (with child mapping)

1. Present areas as multiSelect (existing flow, unchanged)

2. **NEW — After area selection, map back to children:** Use the `--task-children-areas` data to cross-reference selected areas against per-child areas. For each child, determine:
   - **Fully affected:** ALL of the child's areas are in the revert selection
   - **Partially affected:** SOME of the child's areas are in the revert selection
   - **Not affected:** NONE of the child's areas are in the revert selection

3. Show enhanced confirmation summary with child mapping:
   ```
   ## Revert Summary

   ### Will REVERT:
   - <dir1>/ — <files>, touched by commits: <hash1>, <hash2>
   - <dir2>/ — <files>, touched by commits: <hash3>

   ### Will KEEP:
   - <dir3>/ — <files>

   ### Child Task Mapping
   - t<id>_1 (<name>): FULLY AFFECTED — all areas selected for revert
   - t<id>_2 (<name>): PARTIALLY AFFECTED — 1 of 2 areas selected
   - t<id>_3 (<name>): NOT AFFECTED — no areas selected
   ```

4. Confirm/Adjust/Cancel

**For standalone tasks (no children):** Fall back to the current area-based selection (no change to existing flow).

### Step 4: Update SKILL.md Step 4 — Revert task template for child-level reverts

**File:** `.claude/skills/aitask-revert/SKILL.md` (Step 4: Create Revert Task, around line 210-370)

Add two new partial revert template variants for parent tasks. Insert after the existing partial revert template:

**Template variant 1 — Child-level selection (Mode A):**

```markdown
**For partial reverts of parent tasks using child-level selection:**

## Revert: Partially revert t<id> (<original task name>) — by child task

### Original Task Summary
<1-2 sentence summary>

### Children to REVERT
- t<id>_1 (<name>): <N> commits
  Areas: <dir1>/, <dir2>/
  Commits:
  - `<hash>` (<date>): <message> — <file1> (+N/-M), ...

### Children to KEEP (do NOT modify)
- t<id>_2 (<name>): <N> commits
  Areas: <dir3>/

### Parent-level commits (if any)
- <reverted or kept, per user selection>

### Revert Instructions
1. Revert ALL changes from children listed in "Children to REVERT"
2. Preserve ALL changes from children listed in "Children to KEEP"
3. When a commit from a reverted child touches files also modified by kept children, manually revert only the reverted child's hunks
4. Run verification/tests after reverting

### Implementation Transparency Requirements
<same as existing partial revert template>

### Post-Revert Task Management
<same disposition handling as existing template>
```

**Template variant 2 — Area selection with child mapping (Mode B):**

Use the existing partial revert template but append a **Child Task Mapping** section after "Areas to KEEP":

```markdown
### Child Task Mapping
The selected areas map to the following child tasks:
- t<id>_1 (<name>): FULLY AFFECTED — all areas selected for revert
- t<id>_2 (<name>): PARTIALLY AFFECTED — <N> of <M> areas selected
  Areas being reverted: <dir1>/
  Areas being kept: <dir2>/
- t<id>_3 (<name>): NOT AFFECTED — no areas selected for revert
```

This section is informational — helps the implementing agent understand the child-task provenance of each area being reverted.

### Step 5: Update disposition templates — per-child annotations

**File:** `.claude/skills/aitask-revert/SKILL.md` (Step 4 disposition sections)

When a partial revert involves a parent task with children (either Mode A or Mode B), the disposition instructions must annotate **individual child task files** in addition to the parent:

**For "Keep archived" and "Move back to Ready" dispositions:**

Add instructions to the template to annotate each affected child task's archived file:

```markdown
### Per-Child Disposition
For each child task that was **fully** or **partially** reverted, update the archived child task file with Revert Notes:

**Fully reverted children** (e.g., t<id>_1, t<id>_3):
Add to `<archived_child_path>`:
   ## Revert Notes
   - **Reverted by:** t<revert_task_id>
   - **Date:** <YYYY-MM-DD>
   - **Type:** Complete (all changes from this child were reverted)
   - **Areas reverted:** <child's area list>

**Partially reverted children** (e.g., t<id>_2 — only some areas reverted):
Add to `<archived_child_path>`:
   ## Revert Notes
   - **Reverted by:** t<revert_task_id>
   - **Date:** <YYYY-MM-DD>
   - **Type:** Partial
   - **Areas reverted:** <list of this child's reverted areas>
   - **Areas kept:** <list of this child's kept areas>

Children that were NOT affected need no annotation.

Commit all child annotations: `./ait git add <paths> && ./ait git commit -m "ait: Add revert notes to t<id> children"`
```

**For "Delete task and plan" disposition:**

Add instructions to delete specific children's archived files (fully reverted only), keep partially-reverted children (with Revert Notes), and keep unaffected children as-is.

### Step 6: Add automated tests for `--task-children-areas`

**File:** `tests/test_revert_analyze.sh`

**6a. Enhance `setup_test_repo()` to create distinguishable per-child areas:**

The existing test repo has all child commits in `src/`. Add extra commits so children have distinct directories:

```bash
# After existing t50_1 commit (src/login.py):
mkdir -p templates
echo "login template" > templates/login.html
git add . && git commit -m "feature: Add login template (t50_1)" --quiet

# After existing t50_2 commit (src/signup.py):
mkdir -p tests
echo "signup tests" > tests/test_signup.py
git add . && git commit -m "test: Add signup tests (t50_2)" --quiet
```

Now per-child areas are:
- t50 (parent): `src/` (auth.py)
- t50_1: `src/` (login.py) + `templates/` (login.html)
- t50_2: `src/` (signup.py) + `tests/` (test_signup.py)

**6b. Add test cases:**

```
=== Test: --task-children-areas for parent with children ===
- Output contains CHILD_HEADER|50_1|
- Output contains CHILD_HEADER|50_2|
- Output contains CHILD_AREA|50_1|src/|
- Output contains CHILD_AREA|50_1|templates/|
- Output contains CHILD_AREA|50_2|src/|
- Output contains CHILD_AREA|50_2|tests/|
- Output contains PARENT_HEADER|50| (for parent-level commits)
- Output contains PARENT_AREA|50|src/| (auth.py)

=== Test: --task-children-areas for standalone task ===
- Output is exactly "NO_CHILDREN"

=== Test: --task-children-areas for nonexistent task ===
- Output is "NO_CHILDREN" (no children found)

=== Test: --help shows --task-children-areas ===
- Help output contains "--task-children-areas"

=== Test: --task-children-areas child names ===
- CHILD_HEADER for 50_1 contains the name extracted from filename (e.g., "login")
- CHILD_HEADER for 50_2 contains "signup"
```

## Verification

1. Run `bash tests/test_revert_analyze.sh` — all tests pass including new --task-children-areas tests
2. Run `shellcheck .aitask-scripts/aitask_revert_analyze.sh` — clean
3. Read through SKILL.md flow for: parent task with children (both modes), standalone task (area fallback)
4. Verify edge case handling: parent-level commits shown separately, standalone tasks use current area-based flow

## Final Implementation Notes
- **Actual work done:** Added `--task-children-areas` subcommand to `aitask_revert_analyze.sh` with `_collect_hashes_for_id()` and `_aggregate_areas()` helpers. Refactored `cmd_task_areas()` to use the shared `_aggregate_areas()` helper. Updated SKILL.md with dual-mode partial revert selection (by child task / by area with child mapping), child-level and area-with-mapping revert task templates, and per-child disposition annotations. Added 17 automated tests.
- **Deviations from plan:** Refactored `cmd_task_areas()` to use `_aggregate_areas()` — this wasn't explicitly in the plan but was a natural consequence of extracting the shared area aggregation logic. Used `sed 's/^AREA||/AREA|/'` to strip the empty ID column from the `_aggregate_areas()` output when used by `cmd_task_areas()`, maintaining backward compatibility.
- **Issues encountered:** shellcheck SC2295 warning for unquoted expansions inside `${..#pattern}` — fixed by quoting sub-expansions separately as shellcheck suggested.
- **Key decisions:** The `_aggregate_areas()` helper outputs lines with a configurable prefix and an ID column (e.g., `CHILD_AREA|50_1|src/|...`). For `cmd_task_areas()`, the ID column is stripped via sed to maintain the existing `AREA|src/|...` format. Child task names are extracted from `all-children` output by stripping the `t<parent>_<child>_` prefix from the filename stem.
- **Notes for sibling tasks:**
  - The `--task-children-areas` subcommand is called by the revert skill in Step 2 to collect per-child area data, which is then stored and reused in Step 3b for both child-level and area-level selection modes
  - Output format: `CHILD_HEADER|<child_id>|<child_name>|<commit_count>` + `CHILD_AREA|<child_id>|<dir>|<file_count>|<ins>|<del>|<file_list>` per child, plus optional `PARENT_HEADER` + `PARENT_AREA` for parent-level commits
  - `NO_CHILDREN` is output for standalone tasks (no children found)

## Step 9 Reference
After implementation, follow task-workflow Step 9 for archival.
