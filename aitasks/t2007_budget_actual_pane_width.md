---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
anchor: 1326
followup_kind: risk_mitigation
created_at: 2026-10-15 15:30
updated_at: 2026-10-15 15:30
---

## Origin

Risk-mitigation ("after") follow-up for t1351, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — rows still wrap when the real pane is narrower than the configured target

- Budgets read the configured `target_width`, but `_maybe_pin_width` only shrinks a pane that is wider than the target. When the window is too narrow, the real pane stays narrower (e.g. target 40, pane 32: a scrolling card has 28 cells while rows are built for 36), so rows still wrap there · severity: medium · → mitigation: budget_actual_pane_width

## Goal

Budget minimonitor row and detail text against the available content width capped by `target_width`, rebuild row text when the pane width changes, and test configured width 40 with actual pane width 32 (scrolling and non-scrolling).

Context from t1351 (commit a30e849dc, plan `aiplans/archived/p1351_minimonitor_row_width_audit.md`):

- The single budget block lives near the top of `.aitask-scripts/monitor/minimonitor_app.py`: `_row_budget(W) = W − 2 (card padding) − 2 (list scrollbar, always reserved)`, `_detail_budget(W) = _row_budget(W) − 2`, and `_name_room(prefix, reserve, W)`. Every consumer passes `self._target_width` (`_agent_card_text`, `_other_card_text`, `_row_name`, the title clip and `format_gate_phase_row`). The block's comment already names this limitation and this follow-up.
- `_maybe_pin_width` (same file) re-pins only when `self.size.width > self._target_width`. If tmux cannot fit the target, the pane stays narrower, and nothing rebuilds row text for that width.
- The likely shape: derive W from the actual available width — `min(self.size.width, self._target_width)`, or the list's content width — and rebuild the pane list on resize. Watch the t1566 lesson recorded in the `#mini-own-agent` CSS comment: a scrollbar whose visibility depends on row height must not feed back into the width that sizes those rows. Reserving the scrollbar unconditionally, as t1351 does, is what keeps that loop broken.
- Tests: `tests/test_minimonitor_row_budget.py` has the composited host (`_WorstCaseHost`, built on `test_minimonitor_scroll_preservation._RefreshHost`) and the `◆!` patch. Add scenarios with `_target_width = 40` run at a 32-column screen, with the scrollbar both hidden and visible, asserting every card keeps its expected height. Its existing width-32/60 matrix cases set the target equal to the width, so they cannot catch this. A real-tmux capture is in the t1351 plan's Final Implementation Notes (`t1351_live_capture.py`); a narrower `-x` reproduces the case.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2128** id=2026-10-22T21:19:08Z.0b0c5d6c2eaa5eddb37d3ca8 from=t2128 from_verified=yes at=2026-10-22T21:19:08Z base=12ca117857305a6f6149e71c5f9d94b54b7525e9 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2128 (minimonitor phase glyph + colour), as of commit 12ca11785 — line references are tree-relative to that commit:
> | 
> | - .aitask-scripts/monitor/minimonitor_app.py now has a second configured-width budget consumer besides `_row_budget` / `_detail_budget`: `_own_phase_budget(target_width) = max(0, target_width - _ROW_PADDING - _DETAIL_INDENT)` for the docked own-agent card's phase row (no scrollbar term — the panel is overflow-y hidden). It feeds `_own_phase_text` -> `format_phase_markup`; the budget block comment at the top of the module documents it.
> | - The list-row phase now leads with a 2-cell glyph that is counted against `_detail_budget` before the shed ladder runs; the worst realistic row `◌ unknown (rec off) · 0/4 1p 1f 1s` is exactly 34 cells at width 40, so there is no slack left at the default width.
> | - If this task re-bases budgets on the actual pane width or validates/clamps the configured width, `_own_phase_budget` is presumably in scope too. The composited regression for it is OwnPanelSizingTests.test_the_longest_phase_stays_on_one_row_at_every_width in tests/test_minimonitor_top_chrome_render.py.
