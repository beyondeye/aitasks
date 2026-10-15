---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2013
followup_kind: upstream_defect
created_at: 2026-10-16 00:33
updated_at: 2026-10-16 00:36
---

## Origin

Spawned from t2020 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_command_screen.py:727-735` — choosing "+ Create
  new session" hides the window-name input. `_show_new_session_input()` calls
  `_show_new_window_input()`, but the `win_select.clear()` just before it posts
  a `Select.Changed(NULL)`. That reaches `_on_window_changed` (:758), whose
  else-branch calls `_hide_new_window_input()` (:771). `tmux_new_window_row`
  ends up 0×0 in both the wide and the narrow dialog, so the user cannot see or
  edit the window name; the launch uses the hidden default (`agent-pick-5_5` in
  `tests/test_agent_command_dialog_narrow.py::test_keys_work_in_scrolled_dialog`).

(Line numbers as of commit 555e28536.)

## Diagnostic context

Found while measuring t2020's "tallest" wide state: after
`_enter_tallest_state` (session Select → `_NEW_SESSION_SENTINEL`), an in-memory
probe (Textual 8.2.7, the narrow test file's `_isolate` fixture) showed
`tmux_new_session_row` at (3,23,89,3), `tmux_window_select` at (15,27,77,3) and
`tmux_new_window_row` at (0,0,0,0). Selecting the sentinel through the Select
posts the same `Changed` event a user's choice does, so production follows the
same path: show the session-name row → `set_options([])` + `clear()` → show the
window-name row → the queued `Changed(NULL)` hides it again. The comment in
`_show_new_session_input` ("When creating new session, always create new
window") shows that the row is meant to be visible.

The launch result is still well-formed (`TmuxLaunchConfig(new_session=True,
new_window=True, window=<default name>)`), so this is a missing-control bug,
not a broken launch.

## Suggested fix

Make the NULL value that the new-session path produces keep the new-window row
visible. For example, have `_on_window_changed` treat `Select.NULL` as "new
window" while `_selected_session is None` (new session pending), or skip that
one `Changed` event. Add a test that chooses "+ Create new session" and asserts
`#tmux_new_window_row` is displayed and its input is editable, and that the
edited name reaches the `TmuxLaunchConfig`. Re-check t2020's tallest-state
assertions in `tests/test_agent_command_dialog_narrow.py`: the row's
reappearance makes the new-session state one row-group taller in both modes,
which the scroll fallback should absorb.
