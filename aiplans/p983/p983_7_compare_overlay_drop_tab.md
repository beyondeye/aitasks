---
Task: t983_7_compare_overlay_drop_tab.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_7_compare_overlay_drop_tab
Branch: aitask/t983_7_compare_overlay_drop_tab
Base branch: main
---

# p983_7 — Compare overlay; delete Compare tab

Child of t983. **Do not conflate the two compare surfaces:** the dimension-matrix
*tab* (`_build_compare_matrix`,
`.aitask-scripts/brainstorm/brainstorm_app.py:6049` → `#compare_content`, fed by
`CompareNodeSelectModal`, :1891) vs the compare design *op* (comparator agent;
its seeding is handled in t983_4/_6). This child re-homes the **matrix** surface.

## Goal
Make the dimension-matrix compare a contextual overlay reachable from a marked
multi-selection (t983_2/_3) and from the Node Hub (t983_5); delete the Compare tab.

## Steps
1. Wrap `_build_compare_matrix` (:6049, already near-pure: node dicts → DataTable)
   into an overlay/screen opened from a marked set (2-4 nodes) and the Node Hub.
2. Delete the Compare `TabPane` (`#compare_content`, :3560) and
   `CompareNodeSelectModal` (:1891); route node selection through the marked set
   (replaces the modal's checkboxes).
3. Re-home `D`/diff (`action_compare_diff`, :4259, reads `self._compare_nodes`)
   onto the Compare overlay or Node Hub; coordinate `tab_compare` key removal with
   the t983_9 deconflict.

## Verification
- Unit: matrix-build logic covered in
  `tests/test_brainstorm_compare_overlay.py` (rename/rewrite of
  `test_brainstorm_compare_modal.py`): node dicts → expected rows/similarity;
  selection from the marked set.
- Suite `tests/test_brainstorm*.py` green.
- Manual: mark 2-4 nodes → compare overlay → matrix renders; no Compare tab.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_7`.
