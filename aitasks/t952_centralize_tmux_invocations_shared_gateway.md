---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [tmux, ait_bridge]
children_to_implement: [t952_4, t952_5, t952_6]
created_at: 2026-06-10 08:58
updated_at: 2026-06-10 18:16
boardidx: 20
---

## Problem

tmux interaction is scattered across **~45–50 raw call sites** with no single
chokepoint. A survey (2026-06-10) found ~60–70% of calls route through *some*
helper, but across **four parallel "hubs" with no common substrate**:

- `.aitask-scripts/lib/tmux_bootstrap.sh` (shell) — server/session creation.
- `.aitask-scripts/lib/agent_launch_utils.py` — session/window discovery,
  `launch_in_tmux()`, `tmux_session_target()` / `tmux_window_target()`.
- `.aitask-scripts/monitor/tmux_monitor.py` + `monitor/tmux_control.py` —
  pane capture / keys / kill, plus the persistent `tmux -C attach` async client.
- `.aitask-scripts/lib/tui_switcher.py` — navigation (`switch-client`,
  `select-window`), some inline `subprocess.Popen`.
- Stragglers with fully inline calls: `aitask_companion_cleanup.sh`,
  `agentcrew/agentcrew_runner.py`.

Because there is no single place that issues `tmux`, three cross-cutting
policies are implicit and duplicated: **socket selection** (everyone assumes the
default socket — no `-L`/`-S` is threaded anywhere), **target formatting**
(`=session` exact-match is sometimes via the helper, sometimes hardcoded), and
**exec strategy** (per-tick `subprocess` vs. the control-mode client, which is
reusable in principle but currently tied to monitor).

## Why now

This is the foundational substrate under the deployment directions in
`aidocs/applink/wish_ssh_evaluation.md` (serving `ait` TUIs over SSH/wish and on
a hosted box) and under the `monitor_core` extraction seam designed in t822_3.
Both assume a **single, well-known tmux backend handle** that a served front-end
can attach Layer A (agent/process multiplexing) to, without fighting the user's
personal default tmux server. Centralizing tmux access is the precondition that
makes the dedicated-socket move (follow-up task) a one-config-knob change
instead of ~50 edits, and that makes per-verb permission gating tractable.

## Goal

Introduce a single tmux command gateway (one per language) that becomes the
**only** place a raw `tmux` process is spawned, and migrate the existing call
sites through it — without behavior change.

## Scope

1. **Python `TmuxClient` / `tmux_exec` module** — the sole owner of
   `Popen(["tmux", ...])`. Typed methods (`capture_pane`, `list_panes`,
   `new_window`, `switch_client`, `send_keys`, `kill_pane`, ...). It owns:
   - the **socket flag** in one place (default today; a config knob later);
   - the **exec strategy** — per-tick subprocess vs. the persistent control-mode
     client (`tmux_control.py`), so control-mode becomes reusable beyond monitor;
   - **target formatting** (promote `tmux_session_target()` /
     `tmux_window_target()` from "available" to "mandatory").
2. **Shell mirror `tmux_exec.sh`** so the shell call sites (`tmux_bootstrap.sh`,
   `aitask_companion_cleanup.sh`) also route the socket flag and targeting.
3. **Migrate call sites** through the gateway; fold the inline stragglers
   (`agentcrew_runner.py`, `aitask_companion_cleanup.sh`) in.
4. **Single source for session discovery / registry** — collapse the duplicate
   registry reading in `agent_launch_utils.discover_aitasks_sessions()` (Python)
   and `aitask_project_resolve.sh` (bash) to one authority the gateway exposes.

## Out of scope (future direction — separate tasks)

- **Dedicated/persistent socket move** — the follow-up task that depends on this
  one (references t943's persistence axis and t936's test interaction).
- **Navigation Layer A/B split** (abstract `Navigator`: local-tmux vs. in-app)
  — entangled with the t822_3 `monitor_core` extraction; capture there.

## Notes / cross-references

- Survey anchors: `tmux_bootstrap.sh` (`spawn_session_detached`),
  `agent_launch_utils.py` (`launch_in_tmux`, `tmux_*_target`),
  `tmux_monitor.py` (`TmuxMonitor`), `tmux_control.py` (`TmuxControlBackend`),
  `tui_switcher.py` (`_ensure_session_live`, inline Popen at ~618-629/1009+).
- `aidocs/applink/wish_ssh_evaluation.md` — Layer A (backend, stays) vs Layer B
  (window-manager, demoted when remote); the `monitor_core` unifying conclusion.
- t822_3 (`monitor_port_design`) — the `monitor_core` seam this sits beneath.
- t943 — surgical slice-persistence at the single creation chokepoint (does NOT
  touch the socket/gateway; this task is the broader groundwork).
- Per repo convention, assess cleanliness / blast-radius and rejected
  alternatives in the plan before implementing — this is a wide, cross-cutting
  refactor and should be staged (gateway first, migrate incrementally).
