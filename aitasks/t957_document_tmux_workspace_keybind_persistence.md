---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [tmux]
created_at: 2026-06-10 09:31
updated_at: 2026-06-10 09:31
---

## Origin

Risk-mitigation ("after") follow-up for t943, created at Step 8d after
implementation landed.

## Risk addressed

addresses: user-launched workspace server not covered by framework hardening

From t943's plan `## Risk` (goal-achievement):
- **Partial coverage:** the fix only protects *framework-created* servers. The
  actual 2026-06-07 server was created by the user's own Hyprland `tmux-spawn`
  keybind (outside the repo), so the complete fix also needs that launcher
  hardened — a personal Omarchy-config change, separate from this task ·
  severity: medium

## Goal

Add a troubleshooting / docs note (and cross-reference the omarchy guidance)
explaining that a workspace launcher / keybind which starts the `ait` tmux
server should place it in a persistent slice — e.g.
`systemd-run --user --slice=session.slice -- tmux new-session …` — so a
user-created server also survives compositor / `app.slice` teardown, the same
way t943 hardened the framework-created server.

Context: t943 hardened only the framework's own server-creation chokepoint
(`spawn_session_detached`). A server started by the user's own Hyprland
keybind/uwsm launch still lands in a transient `app.slice` scope and dies with
the compositor — this doc closes that gap for users who launch their ait
session outside `ait ide`.
