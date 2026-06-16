---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t983_6]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 11:40
updated_at: 2026-06-16 18:03
---

## Context
Child of t983. The Compare *tab* is a heavyweight home for what is a contextual
analysis over a marked node set. This child re-hosts the dimension-matrix compare
result as an overlay reachable from a marked multi-selection (t983_2/_3) and from
the Node Hub (t983_5), then deletes the Compare tab. NOTE the two distinct
surfaces — do not conflate: the dimension-matrix *tab* (`_build_compare_matrix`,
`.aitask-scripts/brainstorm/brainstorm_app.py:6049` → `#compare_content`, fed by
`CompareNodeSelectModal`, :1891) vs the compare design *op* (comparator agent;
seeding handled in t983_4/_6). This child handles the matrix surface.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — re-host `_build_compare_matrix`
  as an overlay/screen; delete the Compare `TabPane` (`#compare_content`, :3560)
  and `CompareNodeSelectModal` (:1891); route node selection through the marked
  set; decide where `D`/diff (`action_compare_diff`, :4259, reads
  `self._compare_nodes`) lands (Compare overlay or Node Hub).
- `tests/test_brainstorm_compare_modal.py` → rename/rewrite as
  `tests/test_brainstorm_compare_overlay.py`.

## Reference Files for Patterns
- `_build_compare_matrix` (:6049) — already near-pure (node dicts → DataTable);
  keep its matrix-build logic unit-testable when re-hosting.
- `CompareNodeSelectModal` (:1891) + `_on_compare_selected` — being deleted; the
  marked set replaces its checkbox selection.

## Implementation Plan
1. Wrap the matrix build into an overlay opened from a marked multi-selection
   (2-4 nodes) and from the Node Hub's Operations entry.
2. Delete the Compare tab and `CompareNodeSelectModal`; remove `tab_compare`
   keybinding/`check_action` scoping (coordinate with t983_9 deconflict).
3. Re-home `D`/diff; ensure `self._compare_nodes` plumbing still works from the
   marked set.

## Verification
- Unit: matrix-build logic covered in
  `tests/test_brainstorm_compare_overlay.py` (node dicts → expected rows /
  similarity); selection routed from the marked set.
- Suite: `tests/test_brainstorm*.py` green (compare_modal removed/rewritten).
- Manual: mark 2-4 nodes in Browse → open compare overlay → matrix renders; no
  Compare tab remains.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T15:03:15Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T15:03:17Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-16T21:32:03Z status=pass attempt=1 type=human
