---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, frozen_agents, tui]
anchor: 2337
followup_kind: upstream_defect
created_at: 2026-11-25 15:32
updated_at: 2026-11-25 15:32
---

## Origin

Spawned from t2359 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py` `_own_agent_identity_text`: `wrap_width = target_width - 4` budgets a 2-cell `★ ` glyph. A frozen card's prefix `<mark>F ` is 3 cells, so a 36-cell first name fold renders 39 cells against 38 usable. The panel cap then hides the frozen detail line. This was measured with `OWN_WINDOW_PATHOLOGICAL` (`"agent-" + "x"*120`) at width 40.

## Diagnostic context

t2359 budgeted the docked own-agent card's frozen detail line (`_own_frozen_line`) to its one row in `_OWN_PANEL_MAX_ROWS`. Review found that the composited render test could not use `OWN_WINDOW_PATHOLOGICAL` (`tests/test_minimonitor_top_chrome_render.py`):

- `_own_agent_identity_text` folds the window name to at most two lines at `wrap_width = max(8, target_width - 4)` (36 at 40). That wrap width is the budget for the 2-cell `★ ` / `☆ ` mark glyph: `padding: 0 1` leaves 38, and the glyph takes 2.
- When the followed agent is frozen, `_own_card_text` prefixes `format_frozen_prefix(mark_kind) + " "`, which is `☆F ` / `★F `, 3 cells. Without a mark it prefixes `F `, 2 cells.
- With a 36-cell first fold, line 1 is 39 cells against 38 usable, so Rich wraps it. The identity block then takes 3 rows instead of the 2 that `_OWN_PANEL_MAX_ROWS` counts, and the height cap hides the last row. With a title present, that is the frozen detail line, including the sitrep drop verdict.
- The identity text is built once, in `_maybe_build_own_agent_panel`, before freezing is known, and it is not rebuilt when the agent becomes frozen. The fix therefore cannot simply choose the wrap width at build time.
- t2359's render test uses `"agent-pick-" + "very-long-window-name-" * 2 + "end"`, whose first fold is 33 cells, to avoid this case.

## Suggested fix

Budget the name fold for the widest prefix the card can carry (`<mark>F `, 3 cells, so `target_width - 5`). The alternative is to rebuild the identity when the frozen state flips, but that makes the identity a refreshing element, which the one-shot contract forbids. Pin the fix with the `OWN_WINDOW_PATHOLOGICAL` frozen + title case in `DockedFrozenLineRenderTests`: the frozen line must stay visible, and the panel height must stay within `_OWN_PANEL_MAX_ROWS`.
