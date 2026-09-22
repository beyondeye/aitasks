---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [docs, web_site]
gates: [risk_evaluated]
anchor: 1361
followup_kind: upstream_defect
created_at: 2026-07-31 12:57
updated_at: 2026-08-13 23:06
boardidx: 116736
---

## Origin

Spawned from t1361 during Step 8b review.

## Upstream defect

- `website/content/docs/tuis/board/how-to.md:225-243 — work-report section documents the key as uppercase W, but the default binding is lowercase w (aitask_board.py:5615); ~6 occurrences in that section, outside t1361's four gaps`
- `ait:51-60 — the --help "Gates:" block omits `gate pass`, which is dispatched at ait:323 and listed in the inline `ait gate --help`; known and deliberately deferred by t635_34`

## Diagnostic context

While documenting the board By-Trail view for t1361, the `w` row in
`website/content/docs/tuis/board/reference.md` had to be edited to add By-Trail
to its "hidden in ..." view list. The reference page documents the work-report
key as lowercase **`w`**, but `website/content/docs/tuis/board/how-to.md` uses
uppercase **`W`** throughout its "How to Generate a Work Report" section —
including the rebinding note, which names `shortcuts.board.work_report`.

The source of truth is `.aitask-scripts/board/aitask_board.py:5615`:

```python
Binding("w", "work_report", "Work Report"),
```

so the default key is lowercase `w` and the how-to page is wrong. It was left
untouched in t1361 because the mismatch predates that task's release window
(v0.29.0..HEAD) and correcting it means editing roughly six occurrences in a
section about work reports, not about any of t1361's four documented gaps.

Separately, while enumerating the user-facing gate verbs for the new
`website/content/docs/commands/gates.md` page, `ait gate pass` turned out to be
dispatched (`ait:323`) and present in the inline `ait gate --help` string
(`ait:326`), but absent from the top-level `ait --help` "Gates:" block
(`ait:51-60`). The t635_34 plan records this as known and worth a one-line
follow-up, which it deliberately did not take.

## Suggested fix

1. Replace **W** with **w** throughout the "How to Generate a Work Report"
   section of `website/content/docs/tuis/board/how-to.md`, verifying each
   occurrence against `aitask_board.py:5615` first (the rebinding note and the
   step list both name the key).
2. Add a `gate pass  Sign off a human gate` line to the "Gates:" block in `ait`'s
   `show_usage`. Note `tests/test_gate_cli_wiring.sh` pins the inline help
   strings — check whether it also pins the `show_usage` block before editing.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1647_6** id=2026-09-10T18:36:30Z.c99697d5aa7fe0eed8585740 from=t1647_6 at=2026-09-10T18:36:30Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the task whose
> | section your old line range now falls in, not an agent working on it, so it is
> | unverified. Advisory only — tree-relative claims are dated by this note's base
> | SHA. Verify before acting.
> | 
> | 1. The `ait --help` half is already fixed: `gate pass` is listed at ait:61
> |    (e818128b6, t1270, which landed after this task was created). Item 2 can be
> |    dropped.
> | 
> | 2. The work-report key: the section is now § How to Generate a Work Report,
> |    tuis/board/how-to.md ~372-392, with 3 `**W**` occurrences (lines 379, 386,
> |    390), not ~6 at 225-243. The binding is `Binding("w", "work_report", ...)` at
> |    aitask_board.py:8850. reference.md:64 already says `w`.
> | 
> | 3. Anchor by heading: the old 225-243 range now falls inside the By-Trail block
> |    that t1647_6 will edit.

> **✉ note:t1794_9** id=2026-09-22T06:09:07Z.74415b07f2f8b7df01b9cd7b from=t1794_9 from_verified=yes at=2026-09-22T06:09:07Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1363_fix_board_work_report_key_docs_and_ait_help_gate_pass.md) cites stale line anchors: aitask_board.py:5615.
