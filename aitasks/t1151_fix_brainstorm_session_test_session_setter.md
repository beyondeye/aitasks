---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, switcher]
gates: [risk_evaluated]
anchor: 1148
created_at: 2026-07-15 16:41
updated_at: 2026-07-15 16:41
boardidx: 260
---

## Origin

Spawned from t1148 during Step 8b review.

## Upstream defect

- tests/test_tui_switcher_brainstorm_session.sh:47 — the shell test's inline
  Python assigns `overlay._session = …`, but t1099 made `_session` a read-only
  derived property on `TuiSwitcherOverlay` (identity now lives in
  `_selected_key`), so the test crashes with `AttributeError: property
  '_session' of 'TuiSwitcherOverlay' object has no setter`.

## Diagnostic context

Discovered while running the switcher test suite for t1148 (which added the `X`
explore-with-picker shortcut). The failure is pre-existing and unrelated to
t1148: `git stash`-ing the t1148 changes and re-running the test reproduces the
identical `AttributeError` on the unmodified tree. The companion Python test
`tests/test_tui_switcher_agent_launch.py` already uses the post-t1099 pattern
(`ov._selected_key = "s1"` with a comment noting `_session` is now a derived
read-only property), so the brainstorm shell test simply wasn't migrated.

## Suggested fix

Update the inline Python in `tests/test_tui_switcher_brainstorm_session.sh`
(around line 47) to set `overlay._selected_key` instead of assigning
`overlay._session`, mirroring the pattern in
`tests/test_tui_switcher_agent_launch.py`. Verify by running
`bash tests/test_tui_switcher_brainstorm_session.sh`.
