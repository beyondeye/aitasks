---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1563
followup_kind: risk_mitigation
created_at: 2026-08-18 14:25
updated_at: 2026-08-18 14:25
---

## Origin

Risk-mitigation ("after") follow-up for t1563, created at Step 8d after implementation landed.

## Risk addressed

addresses: code-health — the same-edge dock bug class recurs (t1278, t1499, t1563) and is silent

From t1563's plan `## Risk` section:

> This is the **third** instance of one bug class — t1278 (board
> `#filter_area`), t1499 (minimonitor top chrome), t1563 — each found only after
> shipping, because the fault is silent. Fixing this dialog leaves any other
> same-edge docked pair in the repo undiscovered. · severity: medium ·
> → mitigation: sweep_same_edge_dock_siblings

## Goal

Audit every Textual screen under `.aitask-scripts/` for two or more sibling
widgets sharing a `dock:` edge, fix any found, and add a guard so the class
stops recurring.

### Why this keeps happening

In Textual 8.2.7 sibling widgets with the same `dock:` edge are **not** stacked.
Equal heights give them the identical region; unequal heights give overlapping
ones — and the later-in-DOM widget wins. The loser keeps working: `update()`
succeeds, `display`/`visible` stay `True`, `.region` looks sane, and it still
appears in the compositor's `visible_widgets`. Only the composited frame shows
that it never reached the screen. That is why all three instances shipped and
were found by accident.

### Scope

1. **Enumerate.** Find every `dock:` declaration in `DEFAULT_CSS` / `.tcss`
   under `.aitask-scripts/` (board, monitor, minimonitor, codebrowser,
   brainstorm, settings, syncer, stats-tui, diffviewer, applink, the TUI
   switcher) and group by (container, edge). Any group with ≥2 siblings is a
   candidate. Note that a rule inherited from a base class counts — t1563's
   footer got its `dock: bottom` from `TaskDetailDialog`, not from the subclass,
   so a per-class grep would have missed it. Textual's own `Footer` also sets
   `dock: bottom`, so a widget docked bottom alongside a `Footer` /
   `MultiRowFooter` is a hit even though nothing in this repo's CSS says so.
2. **Confirm each candidate on a composited frame** before calling it a defect —
   `app.run_test(size=…)`, then compare `.region`s pairwise and read
   `screen._compositor.render_strips()`. The tell is `earlier.bottom > later.y`,
   not `earlier.region == later.region`.
3. **Fix** by wrapping each same-edge group in ONE docked container, as t1563
   did with `#pick-bottom-dock`. Undocking into flow is the alternative t1499
   used; pick per site.
4. **Guard.** Decide between (a) a per-surface render-level test in the t1499 /
   t1563 idiom, and (b) one cross-cutting source check that walks every
   `DEFAULT_CSS` in the repo and fails on a same-edge sibling pair. (b) scales
   and is what actually stops recurrence, but it must resolve inherited rules to
   be worth anything — a naive per-class scan would have passed t1563 clean.

### Reference material

- `.aitask-scripts/monitor/monitor_shared.py` — the t1563 fix
  (`#pick-bottom-dock`) and its CSS comment.
- `tests/test_minimonitor_pick_by_number.py::BottomDockGeometryTests` — the
  render-level guard, including the negative control that had to re-dock
  **both** children (re-docking only one does not reproduce the fault, because
  the invariant is "one docked widget per edge").
- `tests/test_minimonitor_top_chrome_render.py` — the t1499 guard.
- `.aitask-scripts/board/aitask_board.py` `#filter_area` — the t1278 comment.

### Verification

- Every candidate group is either shown to be a single docked widget per edge,
  or fixed and covered by a test.
- Each fix has a negative control that reproduces the overlap and names the
  failing assertion.
- Full suite: `bash tests/run_all_python_tests.sh` reports
  `PYTHON SUITE: PASSED`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:02Z.93d10ae823c5aa42a9107562 from=t1794_9 from_verified=yes at=2026-09-22T06:10:02Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
