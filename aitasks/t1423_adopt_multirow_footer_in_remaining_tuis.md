---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tui, textual, shortcuts]
gates: [risk_evaluated]
anchor: 1418
followup_kind: risk_mitigation
created_at: 2026-08-05 10:51
updated_at: 2026-08-13 23:07
---

## Origin

Risk-mitigation ("after") follow-up for t1418, created at Step 8d after implementation landed.

## Risk addressed

> **Transitional duplication:** two `Footer` subclasses now coexist with different strategies — `codebrowser.ContextualFooter` *replicates* `Footer.compose()`, `MultiRowFooter` *reflows* it. Intentional and bounded (t1418 ships the widget and adopts it on the board only), but it is added duplication until the other five TUIs adopt it · severity: medium

## Goal

Adopt `.aitask-scripts/lib/multirow_footer.py`'s `MultiRowFooter` in the remaining
TUIs whose shown bindings already overflow a 120-column terminal, so the two footer
strategies converge on one widget and the duplication t1418 introduced is retired.

Measured shown-label width vs a 120-column terminal (from t1418's survey):

| TUI | shown bindings | ~label width |
|---|---|---|
| `agentcrew/agentcrew_dashboard.py` | 27 | 342 |
| `codebrowser/codebrowser_app.py` | 16 | 245 |
| `monitor/monitor_app.py` | 20 | 226 |
| `stats_app.py` | 13 | 177 |
| `codebrowser/history_screen.py` | 10 | 166 |

Notes for whoever picks this up:

- `codebrowser_app.py:173` `ContextualFooter(Footer)` is the interesting one: it
  **replicates** `Footer.compose()` (importing the private `FooterKey` / `FooterLabel`
  / `KeyGroup` names directly) to reorder bindings by focused pane. `MultiRowFooter`
  instead *reflows* whatever `super().compose()` yields, so the two compose in the
  natural direction — `ContextualFooter` should keep owning the ordering and delegate
  the row-packing by subclassing `MultiRowFooter` and calling `super().compose()`
  rather than re-implementing either half.
- Its comment at `codebrowser_app.py:51-53` claims the private API is "pinned to
  8.1.1" while `aitask_setup.sh:29` pins `textual>=8.2.7,<9` — correct that while
  you are in there.
- `MultiRowFooter` takes `hint_action` (an action, not a key). Each adopting TUI
  should pass its shortcuts-editor action so the `+N more (<key>)` affordance names
  the right key; omit it and the hint degrades to a bare `+N more`.
- `tests/test_multirow_footer.py` already covers the widget itself (planner, width
  model incl. groups/compact/wide characters, resize settling, config, negative
  control). Per-TUI adoption tests only need to assert the TUI mounts it and that its
  own bindings reach the rendered footer — see `tests/test_board_footer_multirow.py`
  as the template.
- Check each TUI for a viewport-height assumption before adopting: t1418 had to raise
  `tests/test_board_fixture_harness.py`'s control from a 12-row to a 14-row terminal
  because a 2-row footer shrank the column viewport.
