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
