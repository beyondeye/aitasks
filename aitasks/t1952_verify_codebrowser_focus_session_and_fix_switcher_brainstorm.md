---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tmux]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1946
followup_kind: upstream_defect
created_at: 2026-10-12 12:15
updated_at: 2026-10-12 12:29
---

## Origin

Spawned from t1951 during Step 8b review.

## Upstream defect

- `.aitask-scripts/board/aitask_board.py:1174` — `_current_tmux_session` (raw
  ambient `#S`, not socket-verified) still feeds `TaskDetailScreen`'s codebrowser
  `launch_or_focus_codebrowser(session, …)`. So the codebrowser focus can target
  another server's or project's session.
- `tests/test_tui_switcher_brainstorm_session.sh:87` — the test assigns
  `ov._session = "s2"`, but `_session` has been a read-only property since t1099
  (`045f5212d`). The test crashes with `AttributeError: property '_session' of
  'TuiSwitcherOverlay' object has no setter`. This predates t1951.

## Diagnostic context

t1951 moved the board's brainstorm focus onto
`agent_launch_utils.focus_existing_window`:
- It uses `owned_lookup_session`: the caller's session, socket-verified through
  `current_tmux_session()`, else the configured `default_session`. A session is
  searched only when discovery attributes it to the project.
- It moved the TUI switcher onto `current_tmux_session()`.

After that, the board's raw `_current_tmux_session` has exactly one consumer
left: the detail screen's `tmux_session_provider`, which is the codebrowser
launch. t1951 left it out of scope because changing it alters codebrowser launch
semantics for off-gateway callers.

`test_tui_switcher_brainstorm_session.sh` failed during t1951 verification. The
cause is the property assignment above, not t1951's change.

## Suggested fix

- Codebrowser: decide whether the focus wants `owned_lookup_session(Path.cwd())`
  (a codebrowser window exists in every project's session, so ownership matters)
  or `current_tmux_session()`.
  - If the result is None, warn the user rather than guess.
  - Then drop the raw `tmux` call and, if nothing raw remains, the board's
    allowlist entry in `tests/test_no_raw_tmux.sh`.
- Test: set the selection through `_selected_key` (the overlay's source of
  truth) instead of assigning `_session`.
