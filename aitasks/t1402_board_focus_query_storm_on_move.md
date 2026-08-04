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
updated_at: 2026-08-04 07:58
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
  *plain-arrow navigation* cost. It remains an unaddressed defect first reported
  by t1243_4 and deserves its own task; fixing it here would not move this
  target.
- Textual's own `layout` / `reflow` / `render` (23.6 % combined). Not ablatable.
