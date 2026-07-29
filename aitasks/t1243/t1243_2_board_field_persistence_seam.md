---
priority: high
effort: low
depends: [t1243_1]
issue_type: bug
status: Implementing
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
implemented_with: claudecode/opus5
created_at: 2026-07-28 01:12
updated_at: 2026-07-29 12:12
---

## Context

**Child 2 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md`).

`Task.reload_and_save_board_fields()` is the board's only disk-write path for
layout fields. It snapshots **`boardcol` and `boardidx` by name, hardcoded**,
reloads the file (to preserve concurrent external edits to other fields),
re-applies those two, and calls the **timestamp-neutral** `save()`.

Two consequences:

1. **Any board key it does not name is silently dropped.** `Task._BOARD_KEYS =
   BOARD_KEYS` exists on the class but is **never read anywhere in the repo** — a
   dead assignment. So t1243_8's `boardgroup` would be set in memory and then
   reloaded away by the very save call meant to persist it. This is a latent bug
   **today**, independent of grouping.
2. **It cannot express a semantic change.** `save_with_timestamp()` exists and is
   documented "Use for semantic metadata changes", but the board-field path never
   calls it. t1243_8 makes `boardgroup` merge on *who changed the field*, which
   is meaningless if the write never advances `updated_at`.

This child fixes both, ahead of any group work. It writes no group code itself.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `Task.reload_and_save_board_fields`,
  and the dead `Task._BOARD_KEYS` assignment.
- `tests/test_board_persistence_seam.py` — **new**.

## Reference files for patterns

- `.aitask-scripts/lib/task_yaml.py` — `BOARD_KEYS`, `serialize_frontmatter`.
- `.aitask-scripts/board/aitask_board.py` — `Task.save`,
  `Task.save_with_timestamp`, `Task._update_timestamp`, `Task.load`.
- t1243_1's temp-tree + byte/path-differ harness — reuse it rather than building
  a second fixture.

## Implementation plan

Replace the hardcoded pair with a loop over `BOARD_KEYS`, and add an opt-in
semantic flag:

```python
def reload_and_save_board_fields(self, semantic: bool = False):
    """Reload from disk, re-apply board-owned fields, and save.

    Preserves concurrent external edits to non-board fields. `semantic=True`
    additionally advances `updated_at` — used for board-owned fields that carry
    shared meaning (membership), not per-checkout layout.
    """
    snapshot = {k: self.metadata.get(k) for k in BOARD_KEYS}
    if not self.load():
        return                       # file gone (archived/deleted) — do NOT recreate
    for k, v in snapshot.items():
        if v is not None:
            self.metadata[k] = v
    if semantic:
        self._update_timestamp()
    self.save()
```

Notes that are load-bearing:

- The `is not None` guard preserves an empty-string value (t1243_8's `""`
  tombstone) while never inventing a key that was genuinely absent.
- **All existing call sites keep the default `semantic=False`** and stay
  timestamp-neutral — layout is per-checkout and merges local-wins, so a
  timestamp on a column move would be noise. Do not flip them.
- Retire the dead `Task._BOARD_KEYS = BOARD_KEYS` line by making this loop the
  real consumer (either delete the attribute or have the loop read it — pick one
  and leave no unread duplicate).

## Verification

New tests, over **real files** in a temp tree (reuse the t1243_1 harness):

1. **External-concurrent-edit survival:** set a board field in memory, rewrite
   `status` on disk between the mutation and the save, then save → **both** the
   board field and the external `status` edit are present afterwards.
2. **Timestamp discipline:** `semantic=True` advances `updated_at`;
   `semantic=False` leaves the file byte-identical apart from the board field.
3. **Third-key round-trip:** with a synthetic extra key appended to `BOARD_KEYS`,
   set it in memory and confirm it survives the reload-and-save — this is the
   regression that would have caught the original bug.
4. **Missing file:** a deleted/archived file is still **not** recreated.
5. **Negative control:** revert to the hardcoded two-name snapshot and confirm
   test 3 fails — proving the test discriminates.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-29T09:12:59Z status=pass attempt=1 type=human
