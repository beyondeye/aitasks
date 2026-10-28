---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [monitor, minimonitor, tmux, performance, applink]
children_to_implement: [t2034_1, t2034_2, t2034_3, t2034_6]
artifacts:
  - handle: art:trail-monitor-status-server
    kind: implementation_trail
    name: Shared monitor status server (aitasks)
created_at: 2026-10-16 08:01
updated_at: 2026-10-28 21:40
---

Replace per-instance tmux scanning in `ait monitor`, `ait minimonitor` and
applink with one shared monitor status server per tmux server and framework
version, which those TUIs subscribe to.

## Why

- Every agent window gets its own minimonitor (`maybe_spawn_minimonitor`,
  `lib/agent_launch_utils.py:2353`). Each builds a full `TmuxMonitor`
  (`monitor/minimonitor_app.py:1592`) with its own `tmux -C` client. Every 3 s
  (`refresh_seconds=3`, `minimonitor_app.py:1251`) it discovers panes in every
  session and runs `capture-pane -p -e -S -200` plus prompt classification on
  every agent and shadow pane. `monitor/monitor_app.py:856` and
  `applink/server.py:190` (through `PushScheduler`, `applink/pusher.py:69`)
  repeat the same scan. The work grows with the square of the number of agents.
- Snapshot from 2026-10-16 on the developer machine: 7 minimonitors + 4 monitors
  scanning the same 5 sessions / 24 panes. Minimonitors were 73–117 MB RSS each
  and about 12% of one core combined (ps lifetime averages). Most of that RSS is
  CPython + Textual, so this task targets CPU and tmux load, not memory; memory
  is the concern of the Go monitor port (aitasks_go#16).
- The idle clock is per instance (`_apply_bookkeeping`,
  `monitor/monitor_core.py:2918-2926`): a pane an instance has not seen before
  starts at 0 s, so two minimonitors can show different idle times for the same
  pane. One server means one clock.

## Shape

- The server owns the producer, which is already split from the commit side
  (`capture_all_classified_async`, `monitor_core.py:3293` → `commit_snapshots`,
  `:3419`): discovery + session→project map, capture, `strip_ansi`, prompt
  classification + `agent_key_from_pane`, the idle clock, shadow pairing
  (`@aitask_shadow_target`), and the completed set (`TaskInfoCache`).
- Stays client-side: the minimonitor review loop (`monitor/review_loop.py`),
  all actions (send-keys, kill, pick, shadow spawn), the TUI switcher.
- One server per (tmux server/socket, framework `VERSION`). On 2026-10-16 three
  framework versions (0.27.0, 0.37.0, 0.38.0) shared one tmux server, and prompt
  patterns change between releases. Clients without server support keep
  scanning in-process.
- Local only: a Unix socket under `$XDG_RUNTIME_DIR/aitasks/` (`~/.aitask/run/`
  where that is unset, e.g. macOS), directory mode 0700. No TCP, TLS or pairing —
  applink stays the remote path. The first client starts the server under a file
  lock; it exits after a grace period with no subscribers, or on control-mode
  `%exit`. If the server is unreachable, clients fall back to in-process
  `TmuxMonitor`.
- Per-session config: apply each session's own project `tmux.monitor` settings
  through the session→project map (today each client applies its own project's
  settings to every session).

## Children, in order

1. t2034_1 — measure the scanning vs Textual CPU split.
2. t2034_2 — make the producer client-agnostic (per-client settings semantics).
3. t2034_3 — protocol spec + codec + stream recorder/replayer.
4. t2034_6 — Python↔Go classifier cross-check, the gate for making the Go
   server the default (xdeps aitasks_go#t47, the re-homed Go server).

## Split-out parents (anchored to this task)

The server work is too large for single children, and the framework allows only
one level of children, so it lives in two top-level parents:

- t2037 — Python server + Python client; monitor, minimonitor and applink
  subscribe (depends on t2034_3).
- t2038 — Postponed; re-homed to aitasks_go#t47 (developed in private
  goengines, exported to public goengines; depends on t2037 and on the Go tmux
  package aitasks_go#17).

## Cross-repo

- The Go `ait monitor` port is aitasks_go#16 (second per-app task under the
  aitasks_go#8 umbrella). It is a client of this server and uses the recorded
  protocol stream as its parity fixture.
- How Go binaries ship, and so where shared Go code such as the tmux package
  lives, is decided in aitasks_go#15.
