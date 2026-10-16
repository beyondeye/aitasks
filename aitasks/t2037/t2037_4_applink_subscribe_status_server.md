---
priority: medium
effort: medium
depends: [t2037_3]
issue_type: feature
status: Ready
labels: [applink, monitor]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

Switch applink to the client (parent: Python monitor status server task).

applink builds its own `TmuxMonitor` (`applink/server.py:190`), and
`PushScheduler` (`applink/pusher.py:69`) polls `capture_all_async`. It also uses
that instance as an action and content gateway. Calls found in
`applink/router.py` / `pusher.py`: `send_keys`, `forward_key`, `send_enter`,
`kill_window`, `kill_agent_pane_smart`, `spawn_tui`, `switch_to_pane`,
`capture_pane`, `capture_pane_content_async`, `capture_cursor_async`,
`cycle_compare_mode`, `get_pane`.

## Do

- Status (`pane_status` pushes and the router's `not_idle` restart gate) comes
  from the subscription.
- Decide per call which ones stay on a local gateway instance (actions, cursor
  capture, history scrollback) and which go through the server (`capture{}`).
- The mobile wire protocol (`aidocs/applink/protocol.md`) stays unchanged.

## Verification

Existing applink tests pass; a live check that a paired client still receives
`pane_status` updates and can send keys, with only the server capturing for
status.
