---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ait_archive]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-03 14:14
updated_at: 2026-03-03 14:23
---

## Context

Folded tasks were originally designed for the `/aitask-explore` skill only, where folding always produced standalone parent tasks. Since then, folding has been adopted by `/aitask-fold`, `/aitask-pr-review`, and manual usage (e.g., folding t289 into child task t268_8). Several assumptions baked into the archive script and skill docs no longer hold, leading to bugs and edge cases.

The core issue discovered: when t268_8 (a child task with `folded_tasks: [289]`) was archived, t289 was never deleted because `archive_child()` never calls `handle_folded_tasks()`. Furthermore, when the parent t268 was auto-archived (all children complete), it also skipped `handle_folded_tasks()`.

## Issues to Fix

### Issue 1 (Bug): Child archival skips folded task cleanup

**File:** `aiscripts/aitask_archive.sh`
**Function:** `archive_child()` (line 335)

`handle_folded_tasks()` is only called from `archive_parent()` (line 224). The `archive_child()` function never calls it. If a child task has `folded_tasks`, those folded tasks are never cleaned up.

**Fix:** Add `handle_folded_tasks "$task_id" "$child_task_file"` in `archive_child()` before archiving the child, similar to how `archive_parent()` calls it at line 224.

### Issue 2 (Bug): Parent auto-archival (from last child) skips folded task cleanup

**File:** `aiscripts/aitask_archive.sh`
**Function:** `archive_child()`, lines 403-446

When the last child is archived, the parent gets auto-archived. But this auto-archival path calls `archive_metadata_update()` and `archive_move()` directly — it never calls `handle_folded_tasks()` for the parent. If the parent has `folded_tasks`, they become orphans.

**Fix:** Add `handle_folded_tasks "$parent_num" "$parent_task_file"` before the parent auto-archival section (before line 429).

### Issue 3 (Bug): Outdated SKILL.md note

**File:** `.claude/skills/task-workflow/SKILL.md`, line 503

The note says: "Since aitask-explore creates standalone parent tasks only, the child task archival path does not need to handle `folded_tasks`."

This is no longer true. `/aitask-fold` and manual folding can add `folded_tasks` to any task type.

**Fix:** Remove or update this note to reflect that `handle_folded_tasks()` is now called from both parent and child archival paths.

### Issue 4 (Edge case): Transitive folding creates orphans

**File:** `.claude/skills/aitask-fold/SKILL.md`, Step 0b and Step 3d

If task A has `folded_tasks: [B, C]` and then A is folded into D, the result is: D has `folded_tasks: [A]`, but B and C still have `folded_into: A` pointing to a task that will be deleted. When D is archived, only A is deleted. B and C become orphans.

The fold skill's Step 0b validates status but does NOT check whether a candidate task already has its own `folded_tasks`.

**Fix options (pick one):**
- **Option A (recommended):** When folding task A into D, if A has `folded_tasks`, merge them into D's list. So D gets `folded_tasks: [A, B, C]` and B/C get their `folded_into` updated to D.
- **Option B:** Prevent folding tasks that already have `folded_tasks` (add validation in Step 0b).

### Issue 5 (Edge case): `handle_folded_tasks()` resolves files by top-level glob only

**File:** `aiscripts/aitask_archive.sh`, line 288

```bash
folded_file=$(ls "$TASK_DIR"/t"${folded_id}"_*.md 2>/dev/null | head -1 || true)
```

This only looks in `$TASK_DIR/` (top-level). If a child task were ever folded (currently blocked by skill validation, but could change), its file would be in `$TASK_DIR/t<parent>/` and wouldn't be found.

Similarly, line 326 for plan deletion only looks in `$PLAN_DIR/` top-level:
```bash
task_git rm "$PLAN_DIR"/p${folded_id}_*.md --quiet 2>/dev/null || true
```

**Fix:** Use the existing `resolve_task_file` function (which handles both parent and child paths) instead of a manual glob. Similarly use `resolve_plan_file` for plan deletion.

### Issue 6 (Minor): Documentation inconsistency in explore skill

**File:** `.claude/skills/aitask-explore/SKILL.md`

The `folded_tasks` example shows `[106, 129_5]` including a child task ID `129_5`, but the rules say "Only standalone parent-level tasks without children may be folded in." The example contradicts the rule.

**Fix:** Change the example to use only parent task IDs, e.g., `[106, 129]`.

## Key Files

- **Fix:** `aiscripts/aitask_archive.sh` (Issues 1, 2, 5)
- **Fix:** `.claude/skills/task-workflow/SKILL.md` (Issue 3)
- **Fix:** `.claude/skills/aitask-fold/SKILL.md` (Issue 4)
- **Fix:** `.claude/skills/aitask-explore/SKILL.md` (Issue 6)
- **Test:** `tests/test_archive_folded.sh` (new — test child archival with folded tasks, parent auto-archival with folded tasks, transitive folding)

## Verification Steps

1. Create a mock child task with `folded_tasks: [N]` and archive it — verify folded task is deleted
2. Create a parent with `folded_tasks: [N]` and children — archive last child — verify parent's folded tasks are cleaned up
3. If implementing Option A for Issue 4: fold a task that has its own folded_tasks — verify transitive merge
4. Run existing tests: `bash tests/test_*.sh`
5. Shellcheck: `shellcheck aiscripts/aitask_archive.sh`
