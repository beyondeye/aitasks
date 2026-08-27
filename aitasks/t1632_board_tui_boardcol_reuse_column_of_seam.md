---
priority: low
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [aitask_board, board_columns, python]
anchor: 1630
created_at: 2026-08-26 22:30
updated_at: 2026-08-26 22:30
boardcol: now
boardidx: 15430
---

## Problem

`board_columns.column_of()` is the canonical rule for "which column does this
task render in". t1630 promoted it to public and folded
`work_report_gather.py`'s inline copy onto it, so the **headless** side now has
one implementation.

The board TUI still has its own:

```python
# .aitask-scripts/board/aitask_board.py:388
@property
def board_col(self):
    return self.metadata.get("boardcol", UNORDERED_ID)
```

versus the seam:

```python
# .aitask-scripts/lib/board_columns.py — column_of()
raw = metadata.get("boardcol", UNORDERED_ID)
return raw if isinstance(raw, str) else ""
```

The board **already imports** from `board_columns` (`aitask_board.py:487-492`),
so this is a duplication by omission, not a layering constraint.

## The divergence is real but currently latent

Measured directly for `boardcol: 42`:

| | result |
|---|---|
| `column_of(md)` | `''` |
| `board_col` | `42` |

No behavioural difference **today**: `42` and `''` both fail to equal any
configured column id, so such a card renders in no lane either way — which is
the documented board behaviour. This is a copy that agrees *by accident*, which
is exactly the class t1630 existed to remove. `column_of`'s own docstring even
cites `aitask_board.py` as the behaviour it mirrors, so the seam currently
documents a duplicate as its source of truth.

## Why this is not a one-line drive-by

Replacing the property body with `return column_of(self.metadata)` changes the
**return type** for a non-string `boardcol` (`42` → `''`). Every consumer of
`board_col` must be checked before the swap:

- uses as a dict key or in a set (`42` and `''` hash differently),
- `str()` / f-string interpolation into rich markup or a rendered label,
- identity/equality comparisons against `UNORDERED_ID`,
- the `board_col` **setter** and `reload_and_save_board_fields(("boardcol", …))`
  round-trip (`aitask_board.py:2090`, `:2229`, `:2358`) — a value that is
  read as `''` but written back verbatim must not tombstone a field that held
  a typed value.

## Suggested implementation

1. Enumerate every read of `.board_col` (and any direct
   `metadata.get("boardcol"…)` elsewhere in the TUI) and classify each per the
   list above.
2. Import `column_of` in `aitask_board.py` and delegate the property to it.
3. Update `column_of`'s docstring: it should no longer cite `aitask_board.py`
   as the mirrored behaviour once the board is the importer.
4. Decide deliberately whether the **setter** should reject a non-string value
   at the write site rather than letting one exist to be read — record the
   decision either way.

## Verification

- A fixture task with `boardcol: 42` renders in **no** lane in a live board,
  exactly as before the change (this is the behaviour being preserved, not
  changed).
- A task with no `boardcol` and one with an explicit `boardcol: unordered` both
  render in Unsorted / Inbox — the t1630 two-state rule, now shared.
- Column move / reorder round-trips still write a correct `boardcol`
  (`reload_and_save_board_fields` paths).
- `tests/test_board_columns_seam.py`, `tests/test_board_column_cli.sh`,
  `tests/test_ls_boardcol_filter.sh` and the board's own suites stay green.
- A drift guard: assert `Task.board_col` and `column_of` agree for the same
  metadata across the absent / explicit-unordered / configured / non-string
  cases, so a future re-divergence fails a test.

## Context

Surfaced by a post-implementation sweep of t1630 (`ait ls --boardcol`), which
consolidated the same rule on the headless side. See
`aiplans/archived/p1630_ls_filter_by_board_column.md`.
