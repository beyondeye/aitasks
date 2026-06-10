---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [tmux, resilience]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-07 17:17
updated_at: 2026-06-10 09:05
---

## Problem

All `ait`-managed project tmux sessions share **one tmux server on the default
socket**. `spawn_session_detached` in `.aitask-scripts/lib/tmux_bootstrap.sh`
uses `tmux new-session -d -s "$session"` with **no `-L`/`-S` socket override**,
so every project (e.g. `aitasks`, `aitasks_go`, `aitasks_mobile`) lives on the
same server. A single `tmux kill-server`, a stray SIGHUP from a closing
terminal/compositor, or any whole-server teardown therefore takes down **every
project's session at once** — not just one.

When that happens, only the projects you subsequently switch back to get
respawned: `tui_switcher._ensure_session_live` re-bootstraps a project's session
on demand, but sessions you don't revisit stay gone with no notice.

### Observed incident (2026-06-07)

The shared tmux server (PID 3122) terminated at 15:42:44, tearing down all 9
pane scopes in the same second (visible as simultaneous
`tmux-spawn-*.scope: Consumed ...` lines in the user journal). A new server was
started at 15:56:33 by `ait monitor`, and the `aitasks` session was re-created
at 16:22:49 — but `aitasks_mobile` was never revisited, so it appeared to have
"crashed" while the others came back.

Investigation ruled out, via fully-readable kernel + user journals:
- **No OOM** (no kernel OOM entries this boot; `systemd-oomd` inactive; swap unused)
- **No segfault/crash** (`coredumpctl` has no tmux dump)
- **No reboot/suspend** (system up since 11:48; user `systemd[1449]` survived)
- **Not the framework** (no `kill-server`/`kill-session` anywhere in
  `.aitask-scripts/`; only `kill-pane` in `aitask_companion_cleanup.sh`)

The exact trigger left no journal trace (a clean signal — SIGTERM/SIGHUP or a
manual/global `tmux kill-server`). The framework cannot prevent an external
kill-server, but it can stop one such event from silently wiping all project
sessions.

## Goal

Make `ait`'s tmux session management resilient so a single whole-server
teardown does not silently lose every project's session.

## Candidate approaches (to evaluate during planning)

1. **Dedicated socket** — run `ait` sessions on a named socket (`tmux -L aitasks`
   / `-S <path>`) so they are isolated from the user's main/default tmux server
   and from each other's stray `kill-server`. Assess blast radius: this touches
   every `tmux` invocation in the framework (bootstrap, monitor, companion,
   tui_switcher, tests) — they would all need the socket flag threaded through.
   See the historical "leaks killed users' main servers" note in t936.
2. **Auto-respawn of known-live sessions** — record which project sessions were
   live (registry already exists via `_tmux_bootstrap_set_project_registry`) and
   re-bootstrap them after a server restart, instead of only respawning the
   project you switch back to.
3. **Detection/notification** — surface "your session vanished" rather than
   silently leaving a project down.

## Notes / cross-references

- Anchor: `.aitask-scripts/lib/tmux_bootstrap.sh` (`spawn_session_detached`,
  `_tmux_bootstrap_set_project_registry`), `lib/tui_switcher.py`
  (`_ensure_session_live`).
- Related but distinct: t633 (per-project exact session targeting verification),
  t936 (tmux tests refuse to run with a live default-socket session — a
  dedicated-socket change here may interact), t942 (monitor window renaming).
- Per repo convention, evaluate cleanliness / blast-radius and rejected
  alternatives in the plan before implementing; a socket change in particular is
  a wide, cross-cutting edit.
