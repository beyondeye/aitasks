---
priority: high
effort: medium
depends: [t1243_14]
issue_type: performance
status: Ready
labels: [aitask_board, tui, python, script-performance]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-04 07:58
updated_at: 2026-08-04 09:45
boardidx: 7168
---


## Context

Follow-up of **t1395**, which attributed the ~1.16 s residual left on a lateral
board move after t1243_5's DOM transplant. Findings are recorded in
`aiplans/p1243_board_task_groups_and_fast_reordering.md`, section
**`### RECORDED RESULT — t1395 residual move/layout cost attribution`** — read it
first; this task is the fix it recommends, and its numbers set this task's target.

**The residual is not layout.** On a 200-card board, one lateral keypress
(median-of-5-run-medians **1129.3 ms**, harness floor 73.4 ms) spends:

| span (self time) | median | share | calls |
|---|---|---|---|
| `dom_query` — cold `DOMQuery.nodes`, i.e. full-tree walks | **587.3 ms** | **53.6 %** | **123** |
| `render` + `reflow` + `layout` (Textual, not ablatable) | 300.9 ms | 23.6 % | 4–6 |

The queries come from one chain. `card.focus()` inside `_refocus_card` reaches
`Screen.set_focus`, whose last statement is
`call_after_refresh(self.refresh_bindings)` →`bindings_updated_signal` →
`Footer.bindings_changed` → `call_after_refresh(self.recompose)` →
`Footer.compose` → `Screen.active_bindings` → `app._check_action_state(...)`,
which calls **`KanbanApp.check_action` once per binding**. The board declares 99
bindings and `check_action` holds **8** `self._focused_card()` call sites, each of
which is `self.query("TaskCard:focus")` — a full-screen `walk_children` + CSS
match over ~1250 widgets (~7 ms measured in t1243_4).

Measured per lateral keypress: **4** bindings sweeps → **201** `check_action`
invocations → **107** `_focused_card()` calls → **123** cold full-tree queries.

## Problem

`_focused_card()` re-derives, 107 times per keypress, an answer that changes at
most once — which widget has focus. It is the single largest cost in the board's
hottest interaction, and it is paid on **every focus change**, not only on moves.

## Goal

Remove the query storm without changing which bindings the footer shows or which
actions `check_action` enables.

## Target (set from t1395's measurement, not asserted a priori)

Judged on the **lateral** axis, median keypress latency, using t1243_1's
pre-registered harness and **within-run ablation** — never cross-run absolutes.

- **≥ 45 % reduction** in median lateral keypress latency.

That is deliberately below the two measured ablation figures, which are
*ideal-removal upper bounds*:

| ablation (t1395, within-run, median of 5) | removable |
|---|---|
| `-focus_query` — memoize `_focused_card` on focus identity | **55.5 %** (per-run 55.5 / 47.0 / 59.0 / 29.8 / 60.3) |
| `-bindings` — no-op `Screen.refresh_bindings` entirely | **76.2 %** (per-run 76.2 / 72.6 / 77.4 / 62.0 / 77.5) |

Run 4 is the low outlier on both; its ambient load rose to 4.85 mid-run. A real
implementation must still do the work correctly, so clearing the ablation figure
is necessary-not-sufficient — hence the target sits under it.

## Candidate approaches (not pre-decided)

1. **Memoize `_focused_card()` on focus identity.** This is exactly what t1395's
   `-focus_query` ablation did, and it held every validity invariant (`writes > 0`,
   ping-pong stationarity) across 5 runs. The memo key must hold a **strong
   reference** to the focused widget alongside its `id`, or a collected widget's
   id can be reused and produce a stale hit. Needs a correct invalidation point —
   focus change and DOM mutation.
2. **Stop re-deriving focus by query at all.** `self.query("TaskCard:focus")` is
   rooted at `App.default_screen`, whereas `app.focused` / `screen.focused` is a
   direct pointer. They are **not** interchangeable: pushing a modal does not blur
   the board's focused card, so the two disagree while a modal is up. Any swap
   must be shown to preserve `check_action`'s verdicts in that state, not assumed.
3. **Reduce the number of sweeps.** 4 `active_bindings` sweeps per keypress is
   itself suspect; one would do. This is the `-bindings` lever and is the larger
   win, but it reaches into Textual's signal wiring rather than board code.

Approach 3 subsumes 1; measure before choosing.

## Coordination — timing relative to t1243_14

**This task must land AFTER `t1243_14`** (declared via `depends: [t1243_14]`).

t1243_14 is the *retrospective* of the t1243 workstream: it re-runs the
pre-registered benchmark and builds the baseline-vs-landed comparison table that
decides whether t1243_4 and t1243_5 met their targets. Landing a 45-76 % win from
outside that workstream first would make its table incomparable with the recorded
baselines (lateral 2173.2 ms → 1162.4 ms) and would retroactively flatter
t1243_5. Order is therefore load-bearing, not a preference.

t1243_14's task file carries the reverse pointer.

## Verification

- Use t1243_1's harness (`tests/test_board_movement.py`, `AITASK_BOARD_BENCH=1`)
  and its per-sample validity invariants. Do not invent a second method.
- **Repeat ≥ 5 runs** of the judged configuration; one run cannot adjudicate
  anything on this box. Report the harness floor and ambient load per run.
- Re-run **`test_bench_attribution`** (t1395) and show `dom_query`'s self-time
  share falling — attribution is the proof the intended cost was removed, as
  distinct from an absolute that moved for ambient reasons.
- The ping-pong stationarity check and `writes > 0` are the negative control: if
  the optimisation changed behaviour rather than cost, they must fail.
- No footer relabelling regression: `check_action`'s verdicts must be unchanged,
  including while a modal screen is pushed.

## Out of scope

- `_column_widgets()`'s four full-DOM class queries (~25 ms/keypress). t1395
  proved it is **unreachable from the move path** (0 calls, both axes) — it is a
  *plain-arrow navigation* cost, first reported by t1243_4. **Now owned by
  t1403** (`board_nav_column_widgets_query_cost`). Fixing it here would not move
  this target. Note t1403 touches the **same harness file**, so do not run the
  two concurrently.
- Textual's own `layout` / `reflow` / `render` (23.6 % combined). Not ablatable.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:28Z.83ebb5bfbafb27627d12035c from=t1794_9 from_verified=yes at=2026-09-22T06:09:28Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1402_board_focus_query_storm_on_move.md) cites symbols you name -> current module: KanbanApp -> aitask_board.py, TaskCard -> board_widgets.py.
