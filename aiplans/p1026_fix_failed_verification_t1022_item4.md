---
Task: t1026_fix_failed_verification_t1022_item4.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Fix archived-parent shadowing in board relation resolution (t1026)

## Context

t1021 added "parity swaps" so the board's **Folded Tasks / Folded Into / Parent**
relation dialogs resolve an *archived* target read-only (mirroring the t992
Depends/Verifies fix). The manual-verification task t1022 found item #4 **failed**.

The recorded failure (`aiplans/archived/p1022_manual_verification_auto.md`, Item 4):

> `ParentField("t40")` did not resolve archived parent `t40_parent.md` when an
> active child `aitasks/t40/t40_1_child_active.md` existed. It returned the active
> child because `find_task_by_id("t40")` prefix-matched `t40_1_*` before the
> archived fallback.

Confirmed locally: with an active child `t40/t40_1_*.md` and the parent only
present under `archived/t40_parent.md`, `find_task_by_id('t40')` returns the
**child**, so `find_task_including_archived('t40')` returns the active child
(`archived=False`) and `ParentField._open_parent` opens it **editable** instead
of opening the archived parent read-only.

### Root cause

`TaskManager.find_task_by_id` (`.aitask-scripts/board/aitask_board.py:399`) matches
by the prefix `f"{task_id}_"`. For a **parent** id `t40` that prefix is `t40_`,
which incorrectly matches child filenames `t40_1_*.md` in the `child_task_datas`
loop. So a parent id resolves to one of its own children whenever the parent
itself is not an *active* parent file — which is exactly the archived-parent case.
This shadows the archived fallback in `find_task_including_archived` (line 410).

This is the true bug behind item #4. Folded Tasks / Folded Into resolve correctly
already (verified); only the Parent relation is affected, because only Parent ids
are bare parent ids that can collide with active child filenames.

## Approach (structural fix in `find_task_by_id`)

Fix at the resolver, not at the call site — it is strictly more correct for all
6 callers (none benefit from a parent id matching a child; the three
`find_task_by_id(parent_num)` callers explicitly want the parent and handle
`None`). A parent id must never prefix-match a child file; only a **child** id
(one containing `_`, e.g. `t40_1`) may match the `child_task_datas` table.

### Edit — `.aitask-scripts/board/aitask_board.py` (`find_task_by_id`, ~line 399)

Guard the `child_task_datas` loop so it runs only for child ids:

```python
def find_task_by_id(self, task_id: str):
    """Find a task (parent or child) by its ID like 't47' or 't47_1'."""
    prefix = f"{task_id}_"
    for filename, task in self.task_datas.items():
        if filename.startswith(prefix):
            return task
    # Only a child ID (e.g. 't47_1') may match a child file. A parent ID
    # ('t47') must NOT prefix-match its own children ('t47_1_*'), or an active
    # child shadows the archived-parent fallback in
    # find_task_including_archived (t1026).
    if "_" in str(task_id).lstrip("t"):
        for filename, task in self.child_task_datas.items():
            if filename.startswith(prefix):
                return task
    return None
```

Why this is safe / complete:
- Active parent present → matched by the first loop (unchanged behavior).
- Child id `t40_1` → `"_" in "40_1"` is true → child loop runs, resolves
  `t40_1_*.md` (unchanged behavior).
- Parent id `t40`, no active parent file, active child exists → child loop is
  skipped → returns `None` → `find_task_including_archived` proceeds to the
  archived fallback and resolves `t40_parent.md` with `archived=True` →
  `ParentField` opens it **read-only**. (Fix.)
- The `_` prefix in `f"{task_id}_"` already bounds matches (e.g. `t40_` does not
  match `t405_*`), so no new false positives.

## Tests — `tests/test_board_archived_relation_lookup.py`

Extend the existing `ArchivedRelationLookupTests` class (same `_write_task` /
`_load_board_module` harness):

1. `test_find_task_by_id_parent_ignores_active_child` — write active child
   `t40/t40_1_child_active.md` (no active parent file); assert
   `find_task_by_id("t40")` returns `None` (regression for the prefix collision).
2. `test_parent_field_resolves_archived_parent_with_active_child` — the item-4
   scenario: active child `t40/t40_1_child_active.md` + archived
   `archived/t40_parent.md`; assert `find_task_including_archived("t40")` returns
   `t40_parent.md` with `.archived` True (the read-only detail path).
3. `test_find_task_by_id_child_still_resolves` — guard the child path: assert
   `find_task_by_id("t40_1")` still returns `t40_1_child_active.md`.

Run: `python3 -m unittest tests.test_board_archived_relation_lookup -v`

## Verification

1. `python3 -m unittest tests.test_board_archived_relation_lookup -v` — all pass,
   including the 3 new cases.
2. `python3 -m unittest tests.test_archive_iter_consolidated -v` — the reused
   `find_archived_markdown_by_id` is unaffected.
3. `python3 -c "import ast; ast.parse(open('.aitask-scripts/board/aitask_board.py').read())"`
   — board syntax sanity.

## Risk

### Code-health risk: low
- Single-function guard in one file; strictly more correct for all 6 callers of
  `find_task_by_id` (a parent id resolving to a child was always a latent bug).
  The `_`-bounded prefix and the type-separated task tables keep the change
  contained. · severity: low · → mitigation: None

### Goal-achievement risk: low
- Root cause is confirmed against the recorded p1022 failure and a local
  reproduction; the fix is unit-tested against an independent on-disk archived
  ground truth, exercising the active-child → archived-parent fallback directly. · severity: low · → mitigation: None

## Post-Implementation

Per task-workflow Step 9: review/approve (Step 8), commit code (`bug:` prefix,
`(t1026)`) + plan separately, merge to main, archive t1026.

## Final Implementation Notes

- **Actual work done:** Guarded the `child_task_datas` loop in
  `TaskManager.find_task_by_id` (`.aitask-scripts/board/aitask_board.py`) so it
  runs only when the task id is a child id (`"_" in task_id.lstrip("t")`). Added
  3 regression tests to `tests/test_board_archived_relation_lookup.py`
  (`ArchivedRelationLookupTests`): parent id ignores active child, the t1022
  item-4 archived-parent-with-active-child resolves read-only, and the child id
  still resolves.
- **Deviations from plan:** None. Implemented exactly as planned.
- **Issues encountered:** The board file's line numbers shifted mid-task (a
  background pull updated the working tree), so the first Edit failed the
  stale-state check; re-read confirmed `find_task_by_id` was unchanged and the
  edit applied cleanly. No content conflict.
- **Key decisions:** Fixed at the resolver (`find_task_by_id`) rather than at the
  `ParentField` call site — a parent id resolving to one of its own children was
  a latent bug for all 6 callers, not just the Parent relation dialog. The
  `"_" in id` guard is the minimal correct discriminator since parents live in
  `task_datas` and children in `child_task_datas`, and the trailing `_` in the
  prefix already bounds matches (`t40_` does not match `t405_*`).
- **Upstream defects identified:** None.
