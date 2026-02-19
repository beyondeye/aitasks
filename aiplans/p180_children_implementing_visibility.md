---
Task: t180_children_implementing_visibility.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

In the aitask_board Python script, parent task cards with children only show a generic status line (e.g., "📋 Ready") and "👶 N children". To see which children are currently being implemented and by whom, users must expand the children with `x`. This is poor UX — implementing status should be visible at a glance on the parent card.

## Plan

**File:** `aiscripts/board/aitask_board.py`

### Modify `TaskCard.compose()` (lines 464-484)

In the status/children section of `compose()`, when a parent task has children with `status: Implementing`:

1. **After the existing status_parts block (line 471)**, add logic to detect implementing children
2. **Replace the generic children count line** with per-child implementing status lines when any child is implementing

**New flow:**
- Get child tasks via `self.manager.get_child_tasks_for_parent(task_num)`
- Filter for children with `status == 'Implementing'`
- If any implementing children exist:
  - Skip the parent's own status text, show each implementing child with its assignee
  - Show remaining count as "👶 N more children"
- If no implementing children: keep current behavior

### Concrete code changes

Replace lines 464-484 in `compose()` with new logic that:
1. Detects implementing children early
2. Suppresses parent status when children are implementing
3. Shows per-child implementing lines with assignee email
4. Shows remaining children count

## Verification

1. Run the board: `./aiscripts/board/aitask_board.sh`
2. Look at parent task t176 (which has child t176_3 in Implementing status)
3. Verify: parent card shows `⚡ t176_3 👤 dario-e@beyond-eye.com` instead of `📋 Ready`
4. Verify: remaining children count shows correctly
5. Verify: parent tasks with no implementing children still show normally

Post-implementation: proceed to Step 9 for archival.

## Final Implementation Notes
- **Actual work done:** Modified `TaskCard.compose()` in `aiscripts/board/aitask_board.py` to detect implementing children and display them directly on the parent card, replacing the generic status line
- **Deviations from plan:** None significant
- **Issues encountered:** Double "t" prefix bug — `_parse_filename` already returns task numbers with "t" prefix (e.g., `t176_3`), so the label format `f"t{child_num}"` produced `tt176_3`. Fixed by removing the extra "t" prefix.
- **Key decisions:** Used ⚡ emoji for implementing children to visually distinguish them from the parent status line

## Post-Review Changes

### Change Request 1 (2026-02-19 14:30)
- **Requested by user:** Fix double "t" prefix in child task IDs (showing "tt176_4" instead of "t176_4")
- **Changes made:** Removed extra "t" prefix from child label format string
- **Files affected:** `aiscripts/board/aitask_board.py`
