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
