---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: [t1243_1]
issue_type: bug
status: Done
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
updated_at: 2026-07-29 14:03
completed_at: 2026-07-29 14:03
---

## Context

**Child 2 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md`).

`Task.reload_and_save_board_fields()` is the board's only disk-write path for
layout fields. It snapshots **`boardcol` and `boardidx` by name, hardcoded**,
reloads the file (to preserve concurrent external edits to other fields),
re-applies those two, and calls the **timestamp-neutral** `save()`.

Three consequences:

1. **Any board key it does not name is silently dropped.** `Task._BOARD_KEYS =
   BOARD_KEYS` exists on the class but is **never read anywhere in the repo** — a
   dead assignment. So t1243_8's `boardgroup` would be set in memory and then
   reloaded away by the very save call meant to persist it. This is a latent bug
   **today**, independent of grouping.
2. **It cannot express a semantic change.** `save_with_timestamp()` exists and is
   documented "Use for semantic metadata changes", but the board-field path never
   calls it. t1243_8 makes `boardgroup` merge on *who changed the field*, which
   is meaningless if the write records no modification.
3. **Every call writes both layout keys, whatever it mutated — a live bug.**
   Five of the seven call sites change exactly one of `boardcol` / `boardidx`
   yet write back both, so a stale in-memory value silently reverts another
   writer's change to the key the operation never touched. Concretely:
   `normalize_indices` renumbers a column and, in doing so, yanks a card back
   out of the column another writer just moved it to.

This child fixes all three, ahead of any group work. It writes no group code
itself.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/lib/task_yaml.py` — the `BOARD_LAYOUT_KEYS` / `BOARD_KEYS`
  split (equal today; t1243_8 appends `boardgroup` to the latter).
- `.aitask-scripts/board/aitask_board.py` — `Task.reload_and_save_board_fields`,
  the dead `Task._BOARD_KEYS` assignment, and **all seven call sites**.
- `tests/test_board_persistence_seam.py` — **new**.

## Reference files for patterns

- `.aitask-scripts/lib/task_yaml.py` — `BOARD_KEYS`, `serialize_frontmatter`.
- `.aitask-scripts/board/aitask_board.py` — `Task.save`,
  `Task.save_with_timestamp`, `Task._update_timestamp`, `Task.load`.
- t1243_1's temp-tree + byte/path-differ harness — reuse it rather than building
  a second fixture.

## Implementation plan

Replace the hardcoded pair with a **required, validated field set**. A call
persists exactly the keys it names, and naming a non-layout key is what makes
the write semantic:

```python
def reload_and_save_board_fields(self, fields):          # REQUIRED — no default
    keys = tuple(fields)
    <raise ValueError if empty, or if any key is outside _BOARD_KEYS>
    semantic = any(k not in self._BOARD_LAYOUT_KEYS for k in keys)
    snapshot = {k: self.metadata.get(k) for k in keys}
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

- **Iterating the whole `BOARD_KEYS` set would be a data-loss path**, which is
  why the set is named per call. Re-applying a key this call did not mutate
  silently reverts another writer's change to it, timestamp-neutrally — in three
  directions: a layout move overwriting a shared `boardgroup`, a membership
  write discarding a newer `boardidx`, and a single-key layout op clobbering the
  other layout key (defect 3 above).
- **`fields` has no default.** A default is always plausible and never stated —
  which is exactly how five call sites came to write a key they never mutated.
- The `is not None` guard preserves an empty-string value (t1243_8's `""`
  tombstone) while never inventing a key that was genuinely absent. Note
  `delete_column` writes `board_idx = 0` — falsy but not `None`.
- **All seven call sites are audited to their actual mutation** and all stay
  timestamp-neutral: `("boardcol","boardidx")` for `move_task_col` /
  `delete_column`; `("boardcol",)` for `update_column`; `("boardidx",)` for
  `swap_tasks` (×2), `normalize_indices` and `_move_task_to_extreme`.
- The timestamp contract is **"sets `updated_at` to the current minute"**, not
  "advances it" — `_update_timestamp` is `%Y-%m-%d %H:%M`, so same-minute writes
  tie. t1243_8 already assumes this (it resolves `boardgroup` by base-aware
  change detection, not newer-wins).
- The reload→save window is **not** atomic: an edit landing after the reload is
  still overwritten. The docstring is narrowed to that honest claim.
- Retire the dead `Task._BOARD_KEYS = BOARD_KEYS` line by making the validation
  read it; `_BOARD_LAYOUT_KEYS` joins it as the semantic discriminator. No
  unread duplicate remains.

## Verification

New tests, over **real files** in a temp tree (reuse the t1243_1 harness):

1. **External-concurrent-edit survival:** set a board field in memory, rewrite
   `status` on disk between the mutation and the save, then save → **both** the
   board field and the external `status` edit are present afterwards. Plus the
   mirror, pinning the documented limit: an edit landing *after* the reload is
   lost.
2. **Timestamp discipline, under a frozen clock** (both assertions would
   otherwise race a minute boundary): a layout `fields` leaves a seeded
   `updated_at` untouched and an unchanged task byte-identical; a non-layout
   `fields` sets `updated_at` to the current minute; two such writes in the same
   frozen minute leave it **equal** (non-advancement, pinned), and a later minute
   changes it.
3. **Named-key round-trip:** with a synthetic shared key added to
   `Task._BOARD_KEYS`, set it in memory and confirm `fields=(key,)` persists it —
   the regression that would have caught the original drop bug.
4. **No write-back of an unnamed key,** in all three directions: a layout call
   keeps a remote shared-field change; a semantic-only call keeps a remote
   `boardidx`; an index-only call keeps a remote `boardcol` (and its mirror).
5. **Validation:** unknown or empty `fields` raise `ValueError` **before** any
   write; `fields` has no default. Plus `""` tombstone survival and "an absent
   key is never invented".
6. **Missing file:** a deleted/archived file is still **not** recreated.
7. **Call-site mapping,** which neither the seam tests nor `FLIP_TABLE` can pin
   (an *extra* field is byte-identical uncontended): a runtime spy asserting the
   exact `(file, fields)` records through the five real `TaskManager` callers,
   two end-to-end "does not revert a remote move" assertions through production
   code, and a fail-closed AST guard covering all seven sites.
8. **Negative controls (four, automated):** each rejected design — the legacy
   hardcoded pair, a broad default, iterating all of `BOARD_KEYS`, and
   layout ∪ named — must make its corresponding test above fail, with the
   failure message asserted so a control cannot go green on an unrelated error.
9. **`tests/test_board_movement.py` passes with `FLIP_TABLE` unedited** —
   narrowing the call sites is byte-identical under a single writer, so a change
   there would mean a real behavioural delta to diagnose, not a table to edit.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-29T09:12:59Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-29T10:59:15Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-29T11:03:47Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:3477244c6e5d6f1e

> **✅ gate:risk_evaluated** run=2026-07-29T11:03:47Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1243_2/risk_evaluated_2026-07-29T11:03:47Z-risk_evaluated-a1.log`
