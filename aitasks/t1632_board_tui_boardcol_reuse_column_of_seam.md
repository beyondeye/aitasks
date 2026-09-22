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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:08Z.afd48cd17aa24958d5287e31 from=t1794_9 from_verified=yes at=2026-09-22T06:10:08Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1632_board_tui_boardcol_reuse_column_of_seam.md) cites stale line anchors: aitask_board.py:2090, aitask_board.py:388, aitask_board.py:487-492.
> | 
> | Specific to t1632: `board_columns` is no longer imported only by aitask_board.py. board_task_manager.py, board_task_model.py and board_column_dialogs.py import it directly. aitask_board.py keeps `from board_columns import (...)` as a PURE RE-EXPORT (see its comment near that import): it is pinned by tests/test_board_columns_seam.py (a literal-text check on that file) and tests/test_board_column_manage.py (reads B.UNORDERED_ID). The seam you are extending now spans those four modules.
