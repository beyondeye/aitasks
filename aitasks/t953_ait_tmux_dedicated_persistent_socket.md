---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tmux, ait_bridge]
created_at: 2026-06-10 08:58
updated_at: 2026-06-10 08:58
---

## Problem

All `ait`-managed tmux sessions live on the user's **shared default tmux
server** (default socket). This couples `ait` to whatever else the user runs in
tmux: a stray `tmux kill-server` aimed at the default server takes `ait` down
too, the framework cannot present a stable backend handle to a remote/hosted
front-end, and there is no clean place to enforce per-verb permission gating
(the served TUI would otherwise be tempted to `tmux attach` the user's personal
server — exactly the anti-pattern `aidocs/applink/wish_ssh_evaluation.md` warns
against).

This is candidate approach #1 from t943 ("dedicated socket"), which t943 itself
**rejected** for being too wide a blast radius for a surgical crash-fix. It is
real future work once the tmux call sites are centralized.

## Goal

Run `ait`'s tmux sessions on a **dedicated, named socket** (`tmux -L ait` or
`-S <runtime-dir>/ait/tmux.sock`), isolated from the user's default server, and
combine it with the **persistent-slice lifecycle** already introduced by t943 so
the dedicated server also survives compositor / `app.slice` teardown and client
disconnects (the hosted always-on case).

Two axes, both needed for the hosted/remote topology (see t943 for the
distinction):
- **Socket** = namespace isolation (who can reach/command the server).
- **Slice/cgroup** = survival (what lifecycle unit owns the process) — from t943.

## Depends on

- **t952** (centralize tmux invocations behind a shared gateway). With the
  gateway owning the socket flag in ONE place, this becomes a localized config
  change instead of threading `-L`/`-S` through ~50 call sites. Do NOT attempt
  this before t952 lands.

## Key interactions / risks

- **t936** — tmux tests refuse to run with a live default-socket session; a
  dedicated socket changes that interaction and may simplify or complicate it.
  Re-check t936 / t829 (`tmux_guarded_tests_skip_exit_code`) when planning.
- **t943** — reuse `ait_tmux_new_session_persistent` (the single creation
  chokepoint + slice persistence) and add the socket dimension to it.
- Migration: existing sessions on the default socket are invisible to a
  dedicated-socket `ait` — plan a transition / discovery story so a user mid-flight
  is not stranded (registry, `_ensure_session_live`, `tui_switcher`).

## Why it matters for deployment

`aidocs/applink/wish_ssh_evaluation.md` (hosted topology, use case 3) needs a
stable, well-known backend the served front-end attaches Layer A to, kept
separate from the user's personal tmux. A dedicated persistent `ait` server is
the physical form of the doc's "local = window-manager + backend / remote =
backend-only" split, and a public hosted address it can survive on solves the
v1 LAN-only limitation without building the deferred relay broker.

## Notes / cross-references

- Anchors: `lib/tmux_bootstrap.sh`, `lib/agent_launch_utils.py`,
  `monitor/tmux_monitor.py`, `lib/tui_switcher.py` — all must route the socket
  flag via the t952 gateway, not inline.
- Per repo convention, evaluate cleanliness / blast-radius and rejected
  alternatives in the plan before implementing.
