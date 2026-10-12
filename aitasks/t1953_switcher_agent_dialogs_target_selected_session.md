---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui_switcher, tmux, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1946
implemented_with: claudecode/opus5_5
created_at: 2026-10-12 12:29
updated_at: 2026-10-12 15:26
---

## Context

The TUI switcher (`j`) lets you select another aitasks session with Left/Right.
Every *direct* launch already targets that selected session (`self._session`):

- `_switch_to` runs `select-window` on the selected session, or `new-window` via
  `_spawn_in_session` (`.aitask-scripts/lib/tui_switcher.py`), which uses
  `-t <selected>: -c <selected project root>`.
- Git (`_launch_git_with_companion`), explore (fire-and-forget) and create-task
  use `_spawn_in_session` too.
- Each then calls `_teleport_if_cross`, which runs `switch-client` to the
  selected session when it differs from the attached one.

## Problem

Two switcher actions launch through the shared `AgentCommandScreen` dialog
instead:

- `action_shortcut_explore_pick`
- `action_shortcut_agent`

The launch goes to whatever session the dialog's tmux tab holds, and the
switcher's selection never reaches it:

1. **Wrong preselected session.** The switcher passes `project_root=` (the
   selected project's root, so cwd is right) but no session. The tab preselects
   via `pick_initial_session` (`.aitask-scripts/lib/agent_command_screen.py`),
   in this order:
   - the last session chosen for that project (`_last_session_by_project`);
   - the project's configured `default_session` *name*, if a session by that
     name is live;
   - the first live session.

   Every project defaults to `aitasks`, and a live session's name can differ
   from its config (for example a bootstrap under a fallback name). So the
   dialog can preselect a session other than the one the user selected,
   including another project's. It is visible in the dialog, so not silent, but
   the default is wrong.
2. **No teleport.** Neither dialog path calls `_teleport_if_cross` after a
   successful tmux launch, so the user stays in the attached session while the
   agent starts elsewhere. Every other switcher launch moves the client.

Found while answering a question after t1951 (code reading; not reproduced
live).

## Wanted

- `AgentCommandScreen` takes an explicit `default_tmux_session: str | None`.
  This mirrors the existing `default_tmux_window` / `explicit_tmux_window`
  pattern: explicit caller intent beats both the per-project memory and the
  config-name default, and only when that session is live. Otherwise it falls
  back to `pick_initial_session`'s current order.
  - Thread it through `pick_initial_session`, or resolve it ahead of that call,
    and through `_compute_window_options` for the initial window list.
- Both switcher dialog paths pass `default_tmux_session=self._session`.
- On a successful tmux launch, if `result.session` differs from the attached
  session, teleport the client there:
  - use `result.session` (what the user actually confirmed in the dialog), not
    `self._session`, in case they changed it;
  - reuse `_teleport_if_cross` semantics, but targeted at the confirmed session.
- Other `AgentCommandScreen` callers (board, codebrowser, monitor, minimonitor,
  trails, syncer) keep their behaviour: the new parameter defaults to None.

## Verification

- Unit tests:
  - `pick_initial_session`, or the resolution seam: the explicit session wins
    when live; when it is not live, the order falls back unchanged.
- Switcher tests (`tests/test_tui_switcher_agent_launch.py` style):
  - both dialog paths construct the screen with `default_tmux_session` equal to
    the selected session;
  - a cross-session tmux launch issues `switch-client` to the confirmed session;
  - a same-session launch does not.
- Keep the existing `AgentCommandScreen` golden/construction tests green; for
  example `tests/test_pick_command_screen.py`'s `build_pick_screen` golden must
  not gain the new key.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T12:26:56Z status=pass attempt=1 type=human
