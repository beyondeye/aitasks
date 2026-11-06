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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2218** id=2026-11-06T08:46:11Z.528d3b95db1412bb6fe1437b from=t2218 from_verified=yes at=2026-11-06T08:46:11Z base=5195517375567c1525e8c1b0e8e22fe8fb639a7a base_branch=main dirty=yes host=omg16
>
> | Context for the multi-row footer's mounted tests (advisory, from t2218):
> | 
> | A single `await pilot.pause()` after mount, focus or a view switch can read the footer in a state that is unbuilt, mid-recompose or stale. Under load this happened in tests/test_board_footer_multirow.py, which once failed in the full xdist suite. The reason: Textual's Footer composes nothing until `bindings_updated` fires, its handler then queues `recompose` on the footer's own pump, and `recompose` itself is async (remove, then mount). On top of that, `MultiRowFooter.on_resize` queues one more recompose after a height change.
> | 
> | Commit 519551737 adds a pattern you can copy for the other TUIs: `_footer_ready` / `_board_ready` / `_focus_and_settle` in tests/test_board_footer_multirow.py. It combines:
> | - a sentinel on the footer's pump;
> | - recompose counters (a class-level patch of MultiRowFooter.recompose);
> | - a trigger witness (since=);
> | - a check that the footer is non-empty after it settles.
> | 
> | Each TUI also has its own startup-focus claim, and that needs a precondition wait as well. For the board this is `app.focused is not None`, because `AUTO_FOCUS` is "".
