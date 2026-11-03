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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2034_1** id=2026-11-03T15:02:06Z.4ba80cc9914a7fe3fc7a97d4 from=t2034_1 from_verified=yes at=2026-11-03T15:02:06Z base=6930f54e25e74a1e92e01e7fab1a8c1cbbcf2914 base_branch=main dirty=yes host=omg16
>
> | t2034_1 measurement results (2026-11-03, omg16; full tables, method and scripts in
> | aiplans/p2034/p2034_1_measure_monitor_scan_cost.md, task-data commit db064ad60 —
> | archived with t2034_1). Advisory; numbers are from one host at one moment.
> | 
> | - Monitoring cost at the time of measurement: ~2.2–2.4 cores (38 minimonitors
> |   140–158 % of a core combined, 4 monitors ~8 %, tmux server 65–73 %). ps lifetime
> |   averages (tmux server 21 %) understated it.
> | - The tmux server is the largest single scan cost and is almost entirely scanning:
> |   with 12 agents and K=0 scanners it used 0.02 %, K=1 0.77 %, K=4 2.68 % — grows as
> |   N agents × K scanners (~0.64 % of a core per extra scanner at N=12,
> |   ≈1.6 ms server CPU per capture-pane incl. discovery/control traffic). Supports the
> |   "Why" section's quadratic-growth claim.
> | - In-process, scanning is a minority of a minimonitor's CPU (≈14 % steady, live);
> |   Textual render/dispatch ≈80 %. Monitor: producer ≈43 %.
> | - Estimated shared-server saving ≈0.9–1.0 core (≈0.63–0.71 from tmux-server dedup
> |   + ≈0.28 in-process). The gain is from dedup (t2037), not language: one Python
> |   producer ≈0.7–0.9 % of a core, so t2038 / aitasks_go#t47's CPU payoff is small —
> |   its case would rest on memory. Single-idle-clock gain unaffected.
> | - Untouched by the server: minimonitor rendering ≈1.2 cores across 38 instances,
> |   growing with N (every card re-rendered per tick) — spun out as a separate
> |   follow-up task.
