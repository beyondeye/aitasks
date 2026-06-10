---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [tmux]
created_at: 2026-06-10 09:30
updated_at: 2026-06-10 09:30
---

## Origin

Risk-mitigation ("after") follow-up for t943, created at Step 8d after
implementation landed.

## Risk addressed

addresses: secondary server-creation site in agent_launch_utils.py

From t943's plan `## Risk` (goal-achievement):
- Secondary framework server-creation site `launch_in_tmux()` (new_session
  branch) in `agent_launch_utils.py` is left unhardened (deferred to keep this
  change surgical and shell-only) · severity: low

## Goal

Mirror the persistent systemd-user-service (session.slice) server spawn that
t943 added to `spawn_session_detached` in the Python `launch_in_tmux()`
new_session branch (`.aitask-scripts/lib/agent_launch_utils.py`). Gate it on
systemd-run availability plus a `tmux has-session` precheck (so it only wraps a
genuine SERVER creation, not an attach), with the same setsid → plain-tmux
fallback ladder. Socket unchanged (default), matching t943.

Reference implementation: `ait_systemd_user_available` /
`ait_tmux_new_session_persistent` in `.aitask-scripts/lib/terminal_compat.sh`
and the call site in `.aitask-scripts/lib/tmux_bootstrap.sh` (t943). A Python
equivalent may either shell out to the bash helper or replicate the
`systemd-run --user --slice=session.slice --property=Type=forking
--property=KillMode=none --collect` invocation directly.

Note: t952 (centralize tmux invocations behind a shared gateway) may absorb or
simplify this — if t952 lands first, route the persistent spawn through the
gateway rather than duplicating the systemd-run logic in a second place.
