---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [artifacts, trails, tui, aitask_board]
gates: [risk_evaluated]
anchor: 1210
followup_kind: upstream_defect
created_at: 2026-08-16 11:01
updated_at: 2026-08-16 11:01
---

## Origin

Spawned from t1505_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:4092-4094` — the trail detail modal's
  `line()` helper treats a whitespace-only string as present, so a
  schema-valid whitespace-only `problem_statement` / `recommendation_summary` /
  `method_note` renders as a labelled line with blank content.

The guard is `if value in (None, "", [], {}): return`, which catches the empty
string but not `"   "` or `"\n"`.

## Diagnostic context

t1505_3 added `narrative.overview` and had to decide how strictly to constrain
it. That surfaced a disagreement between the two shipped renderers of trail
narrative prose:

- `trail_summary_text()` (`aitask_board.py:800-822`) strips, and treats a
  whitespace-only value as **absent** — it falls through to the next field.
- `TrailDetailScreen._sections()`'s `line()` (`:4092-4098`) does **not** strip,
  so the same value renders as a labelled line with blank content.

t1505_3 closed this for `overview` alone, at the schema boundary
(`"pattern": "\\S"`), because the field was brand new and tightening it
invalidated no stored document. **The legacy prose fields were deliberately
left alone**: `problem_statement`, `recommendation_summary`, `method_note` and
the per-entry `rationale` carry only `minLength: 1`, and adding a pattern to
them would invalidate every stored trail. So the defect is still reachable
through them.

Verified during t1505_3 (2026-08-16), against the current schema:

```
$ python3 .aitask-scripts/lib/trail_schema.py validate <gate_framework.json with problem_statement="   ">
VALID:trail-gate-framework-landing     # rc=0 — schema-valid
```

and `line("problem", "   ")` passes its `value in (None, "", [], {})` guard, so
the modal prints `problem: ` followed by blank content.

## Suggested fix

Make `line()` treat a blank-after-strip string as absent, matching
`trail_summary_text()`'s already-shipped semantics — the renderers should agree:

```python
def line(label, value):
    if value in (None, "", [], {}):
        return
    if isinstance(value, str) and not value.strip():
        return
    ...
```

Fixing it in the renderer (rather than by tightening the legacy schema fields)
is what keeps every stored trail valid. Pin it with a modal-level test asserting
no labelled line is emitted for a whitespace-only narrative field; the
`test_absent_narrative_overview_prints_no_empty_label` test in
`tests/test_board_bytrail_view.py` is the closest existing precedent.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:08Z.ac98f1d17b265799d8e3356d from=t1794_9 from_verified=yes at=2026-09-22T06:08:08Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1526_trail_modal_blank_labelled_line_on_whitespace_narrative.md) cites stale line anchors: aitask_board.py:4092-4094, aitask_board.py:800-822; symbols you name -> current module: TrailDetailScreen -> board_trail_view.py, trail_summary_text -> board_trail_view.py.
