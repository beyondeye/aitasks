---
priority: medium
effort: high
depends: [t2034_3]
issue_type: feature
status: Ready
labels: [monitor, minimonitor, tmux, applink]
anchor: 2034
created_at: 2026-10-16 08:01
updated_at: 2026-10-16 08:01
---

Build the shared monitor status server in Python, reusing `monitor_core`
unchanged as the producer, plus a Python client. Then switch monitor,
minimonitor and applink to subscribe (see the parent task; protocol from
child 3).

## Server

- One per (tmux socket, framework `VERSION`): the socket path is keyed on the
  tmux socket (`AITASKS_TMUX_SOCKET` or the default) and `VERSION`, under
  `$XDG_RUNTIME_DIR/aitasks/` (fallback `~/.aitask/run/`), directory mode 0700.
- Started by the first client through an `ensure` entry point under an exclusive
  file lock (no double start), detached with `setsid`. Exits after a grace period
  with no subscribers, or when its control client sees `%exit`. A stale socket
  left by a crashed server is detected and replaced.
- Applies each session's own project `tmux.monitor` config (`load_monitor_config`
  through the session→project map), not one project's config for every session.
- tmux calls go through the gateways (`lib/tmux_exec.py`,
  `aidocs/framework/tmux_gateway.md`; `tests/test_no_raw_tmux.sh` enforces).

## Client

- `MonitorClient` exposing the `TmuxMonitor` surface the apps read
  (`capture_all_async`, `get_shadow_snapshot`,
  `get_session_to_project_mapping_async`, `get_pane`, …), so the app-side changes
  stay small.
- A replay mode that reads a recorded fixture (child 3), for the parity demo in
  aitasks_go#16.
- Fallback: when the server cannot be reached or started, use in-process
  `TmuxMonitor` (today's code), the same posture as the existing
  control-mode → subprocess fallback.
- Monitor, minimonitor and applink (`PushScheduler`) become subscribers. The
  review loop's own raw-tail captures of the followed pane and its shadow stay
  client-side.

## Verification

- Tests: single start under concurrent `ensure`, idle exit, stale-socket
  recovery, fallback path, per-version isolation, delta ordering by `gen`.
- Live: with N minimonitors, one capture pass per tick (count `capture-pane`
  calls before and after); idle seconds agree across clients.
- Re-run child 1's measurement and record the difference.
