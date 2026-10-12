---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, aitask_board, minimonitor, shortcuts]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1946
followup_kind: upstream_defect
created_at: 2026-10-11 22:32
updated_at: 2026-10-12 08:59
---

## Origin

Spawned from t1946 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:4962` — `_launch_brainstorm` looks for
  `brainstorm-<num>` in an unverified session: the raw ambient `#S` probe
  `_current_tmux_session()`, or the configured `default_session` name. It then
  selects the window with a raw `tmux select-window`. Window names carry only the
  task number, and one gateway server hosts every project's sessions. So it can
  switch to ANOTHER project's same-numbered brainstorm window and suppress this
  project's launch.
- `.aitask-scripts/lib/tui_switcher.py:142` — `_detect_current_session` sends a
  bare `display-message -p '#S'` through the gateway (`-L ait`). From a pane whose
  `$TMUX` names a different server, tmux has no client to resolve and answers its
  "best" session, so `action_tui_switcher` can open the overlay against an
  unrelated session.

## Diagnostic context

t1946 moved the board's pick/resume "focus an existing agent window" check into
`agent_launch_utils.focus_existing_agent_window`. Three review rounds found three
layers of the same bug, all now fixed there:
1. a bare gateway `#S` probe answers an unrelated session for a caller on another
   server, so `current_tmux_session()` targets `$TMUX_PANE` and compares
   `#{socket_path}` with `$TMUX`;
2. a verified caller can still sit in another project's session on the same
   server;
3. the configured `default_session` is only a name (every project defaults to
   `aitasks`).

The fix for 2 and 3 is `_sessions_owned_by(project_root)`, which runs canonical
discovery (stamp, then pane vote, then legacy registry). A candidate session is
searched only when it is owned; when none is, nothing is searched and the caller
launches. `_launch_brainstorm` and `tui_switcher._detect_current_session` still
use the old, unverified patterns.

## Suggested fix

- `_launch_brainstorm`: reuse the t1946 helpers. Generalise
  `focus_existing_agent_window` to take window names, or add a sibling for
  `brainstorm-<num>`, so the lookup is socket-verified and ownership-checked and
  the raw `select-window` goes through the gateway.
- `tui_switcher._detect_current_session`: replace it with
  `agent_launch_utils.current_tmux_session()`. Decide explicitly whether the
  switcher wants "the caller's verified session" (probably) or also needs
  project ownership.
- Live regression tests in the style of `tests/test_pick_command_screen.py`
  `LiveTwoServerTests`.
- Coordinate with t1950: a targeted per-session ownership resolver that would
  serve both.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T07:28:59Z status=pass attempt=1 type=human
