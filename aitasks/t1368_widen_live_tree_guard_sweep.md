---
priority: low
effort: low
depends: []
issue_type: test
status: Postponed
labels: [test, tui, board]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1111
followup_kind: risk_mitigation
created_at: 2026-08-02 12:15
updated_at: 2026-08-13 23:06
boardidx: 11264
---

## Origin

Risk-mitigation ("after") follow-up for t1354_2, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement, from t1354_2's `## Risk`:

> Scope grew 9 -> 15 files during verification; further unlisted coupling would
> weaken the guard's completeness claim · severity: low

t1354_2's tier-1 sweep is exhaustive over `tests/test_board_*.py` — but only
over that glob. The same live-tree coupling can appear in any other TUI test
module, and would not be caught.

## Goal

Widen the tier-1 live-tree sweep in `tests/test_board_fixture_harness.py` from
`tests/test_board_*.py` (25 files) to all `tests/test_*.py` (~175 files).

## Why this is worth doing

Verified during t1354_2 that no non-board test currently chdirs to `REPO_ROOT`
at import/test time — every other `os.chdir` in `tests/` targets a tmpdir. So
the widening is expected to be near-free today. Its value is prospective: it
closes the glob as an escape hatch before a new `test_settings_*` /
`test_brainstorm_*` / `test_monitor_*` module reintroduces the coupling.

It also gives the allowlist its first entry that is provable on the *real*
tree rather than only on synthetic fixtures:
`tests/test_shortcut_scopes.py:322` has `os.chdir(REPO_ROOT)` inside an
`if __name__ == "__main__":` block (benign — not executed under discovery),
which is exactly the "justified exception, pinned with a reason" case the
mechanism exists for.

## Key Files to Modify

- `tests/test_board_fixture_harness.py` — `LiveTreeSweepTests._board_test_sources`
  (change the glob), `CHDIR_ALLOWED` (add the `test_shortcut_scopes.py` entry
  with its reason).

## Cautions

- **Re-run the whole sweep before assuming it is free.** The prediction above
  was measured on 2026-08-02; new modules land weekly.
- The canonical-import half of the rule will also widen. Any non-board module
  that imports `aitask_board` canonically needs the same judgement call as
  `test_board_movement` / `test_board_persistence_seam` did: exempt with a
  written reason, or migrate it.
- Keep the exemption **per-expression**, never per-module — that property is
  pinned by `test_exemption_cannot_hide_a_repo_root_chdir` and is the reason
  the guard cannot rot into a rubber stamp.

## Verification Steps

- Sweep green over all `tests/test_*.py`.
- Every new allowlist entry proven load-bearing by the existing removal control
  (`test_allowlist_entries_are_load_bearing`) — which iterates the dict, so new
  entries are covered automatically.
- `test_sweep_covers_more_than_the_migrated_set` still holds.
- Full suite green; no measurable wall-clock change (the sweep is a source scan).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:15Z.6ebe94b4365676caea19e30e from=t1794_9 from_verified=yes at=2026-09-22T06:09:15Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
