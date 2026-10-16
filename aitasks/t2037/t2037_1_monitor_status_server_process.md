---
priority: medium
effort: high
depends: [2034_3]
issue_type: feature
status: Ready
labels: [monitor, tmux]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

The status server process and its lifecycle (parent: Python monitor status
server task). It owns one `TmuxMonitor` producer and serves the t2034_3
protocol.

## Do

- One server per (tmux socket, framework `VERSION`): the socket path is keyed on
  the tmux socket (`AITASKS_TMUX_SOCKET` or the default) and `VERSION`, under
  `$XDG_RUNTIME_DIR/aitasks/` (fallback `~/.aitask/run/`), directory mode 0700.
- An `ensure` entry point: an exclusive file lock (no double start), then start
  the server detached (`setsid`) if none is answering.
- Exit after a grace period with no subscribers, or when the control client
  sees `%exit`. Detect and replace a stale socket left by a crashed server.
- Apply each session's own project `tmux.monitor` config (`load_monitor_config`
  through the session→project map), not one project's config for every
  session.
- tmux calls only through the gateways (`lib/tmux_exec.py`;
  `tests/test_no_raw_tmux.sh` enforces).

## Verification

Tests: single start under concurrent `ensure`, idle exit, stale-socket
recovery, per-version isolation, per-session config, delta ordering by `gen`.
