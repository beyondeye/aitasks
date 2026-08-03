---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
anchor: 1326
created_at: 2026-07-30 10:34
updated_at: 2026-08-03 16:08
boardidx: 850
---

## Context

Risk-mitigation "after" task for **t1326**, paying down width debt that predates
it.

The minimonitor agent row renders at ~38 usable columns (`#mini-pane-list`,
40-wide pane minus `padding: 0 1`) and the worst case already overflows. Verified
by a real 40-column tmux capture during t1326:

```
 ★ ● ◆ ≈ agent-pick-1326-lon…  PROMPT
 123s
```

t1326 was **column-neutral** — it added 2 columns for the always-on ★/☆ pair and
took 2 back by cutting the window-name cap from 22 to 20 — so it did not create
the overflow, but it did consume the remaining headroom. A third always-on glyph
(t1343's conflict advisory is a candidate) has nowhere to come from.

## Goal

Audit the row across every glyph combination at 40 columns and decide, explicitly,
what gives way — rather than cutting the name cap again by reflex.

Combinations to cover: mark (★/☆) × shadow (absent / `◆` / `◆!`) × compare-mode
(`≈` / `=`) × status (`Active` / `IDLE 123s` / `PROMPT 123s` / `DONE 123s`) ×
name length.

## Acceptance criteria

- [ ] A test asserts the **composited screen** at width 40 (not `widget.render()`,
      which cannot reveal Rich ellipsising) for the worst-case combination
- [ ] The row's column budget is documented in one place with the arithmetic, so
      the next glyph has a stated budget to fit rather than a guess
- [ ] A decision is recorded on what sheds first when a glyph is added — name tail,
      status verbosity, or a second line
- [ ] Any change is confirmed by a real tmux capture at 40 columns, not only by
      Textual's headless renderer

## Incoming scope: cell-width-aware truncation (from t1382)

t1382 added an `other` section to the minimonitor pane list and, in review,
confirmed a defect that applies to **every** row in this file: the name/command
caps use `len()`, which counts code points rather than terminal cells. A window
name of 20 double-width (CJK / emoji) characters occupies 40 cells, so the row
overflows and Rich clips it — measured on the new `other` row at 36 code points
/ **64 cells** against the 38-cell budget.

It was dispositioned as a follow-up and routed here rather than fixed in t1382,
because `_agent_card_text` has the identical flaw and is the far more common
row: fixing one without the other would leave the audit's budget claim untrue.

- [ ] Replace the `len()`-based caps in `_agent_card_text` and
      `_other_card_text` with cell-width-aware truncation
      (`rich.cells.cell_len` / `set_cell_size`)
- [ ] Add a double-width case to the budget assertions — see the note in
      `test_row_fits_the_column_budget` (`tests/test_minimonitor_other_section.py`),
      which currently pins single-cell input only and says so
- [ ] State the budget in **cells**, not code points, wherever it is documented

## Reference

- `_agent_card_text` in `.aitask-scripts/monitor/minimonitor_app.py` (`max_name`)
- `format_pane_status` / `format_state_dot` / `format_shadow_glyph` /
  `format_mark_glyph` in `.aitask-scripts/monitor/monitor_shared.py`
- `_HINT_WIDTH_BUDGET = 38` in `tests/test_minimonitor_own_task_info.py`
- `_screen_text` / `_flat` in `tests/test_minimonitor_pick_by_number.py` — the
  composited-screen assertion helpers
