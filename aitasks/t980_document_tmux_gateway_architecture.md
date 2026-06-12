---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [tmux, documentation, ait_bridge]
created_at: 2026-06-12 07:49
updated_at: 2026-06-12 07:49
---

## Problem

The tmux interaction architecture was refactored in **t952** (a shared tmux
command gateway, one per language) and **t953** (a dedicated `-L ait` socket),
but no `aidocs/framework/` doc captures the resulting design. CLAUDE.md only
points to `aidocs/framework/tui_conventions.md` for "spawning tmux panes /
windows". New tmux-touching code therefore has no on-demand reference to keep
it from drifting back to ad-hoc raw `tmux` calls scattered across the tree (the
exact ~45–50-call-site sprawl t952 collapsed).

## Goal

Add a **brief** standalone conventions doc under `aidocs/framework/`
(e.g. `tmux_gateway.md`) describing the new architecture and the rules new
code must follow, and link it on demand from CLAUDE.md. Also reconcile the
existing `aidocs/framework/` docs that still describe the pre-gateway model.

## Deliverable 1 — new conventions doc

Keep it brief and rule-oriented (current-state only, no version history in the
body per `documentation_conventions.md`). Cover:

- **The gateway is the only sanctioned place a raw `tmux` process is spawned.**
  - Python: `.aitask-scripts/lib/tmux_exec.py` — `TmuxClient` (`run` /
    `run_async` / `spawn` / `run_via_control` / `resize_pane` /
    `new_session_argv`) plus module fns `tmux_socket_args`, `session_target`,
    `window_target`.
  - Shell: `.aitask-scripts/lib/tmux_exec.sh` — `ait_tmux`,
    `ait_tmux_socket_args` (emitter for `exec`/compound sites),
    `ait_tmux_session_target` / `ait_tmux_window_target`, `ait_tmux_legacy*`
    (migration-window probes of the user's default server).
- **The three centralized policies** (previously implicit/duplicated):
  1. **Socket selection** (t953): `AITASKS_TMUX_SOCKET` — unset → `-L ait`
     (dedicated socket, isolated from the user's default server); `default` →
     explicit opt-out to the user's server; set-but-empty → no flag (legacy
     escape hatch following `$TMUX`, used by the test isolation harness). Read
     once at client construction, never per-call.
  2. **Target formatting**: `=<session>` exact-match `-t` targets are
     **mandatory** (tmux's default prefix match makes `aitasks` match
     `aitasks_mob`).
  3. **Exec strategy**: per-tick subprocess vs. persistent control-mode client,
     with the `(rc, stdout)` / `(-1, "")` fallback contract.
- **The enforcement guard**: `tests/test_no_raw_tmux.sh` freezes raw `tmux`
  spawns to the two gateways plus a documented per-entry allowlist (gateways +
  Layer-A backends + ambient `$TMUX` self-probes). New code must route through
  the gateway, not the allowlist.
- A short "writing new tmux code" checklist (use the gateway; never hand-format
  `-t`; don't add to the allowlist).

## Deliverable 2 — reconcile stale / overlapping docs

- **`aidocs/framework/python_tui_performance.md`** — descriptively stale: it
  attributes the raw `asyncio.create_subprocess_exec("tmux", …)` spawn to
  `tmux_monitor.py::capture_all_async()`, but `tmux_monitor.py` now imports
  `TmuxClient` and routes through `run_async_via_control`; the raw spawn lives
  in the gateway. Update the code-location attribution. NOTE: the performance
  *conclusion* (fork+exec dominates, PyPy ~0%) is unchanged — keep it, fix only
  the attribution.
- **`aidocs/framework/tui_conventions.md`** — already has overlapping rules
  (exact-match targeting, dedicated `-L ait` socket, tmux-stress task
  guidance). Cross-link the new gateway doc rather than duplicating; move /
  consolidate only if it reads cleaner. Decide and record which doc owns the
  exact-match-target rule so the two don't drift.
- Re-scan the rest of `aidocs/framework/` for any other pre-gateway
  assumptions while in there (`cross_repo_references.md`,
  `monitor_idle_and_prompt_detection.md`, `sed_macos_issues.md` looked current
  in the scoping pass but verify against the final doc).

## CLAUDE.md wiring

Add an on-demand pointer (`> **Read aidocs/framework/tmux_gateway.md** when …`)
in the appropriate section — likely near the existing TUI Development /
tui_conventions pointers — with a trigger like "writing or editing any code
that spawns or commands tmux (panes, windows, sessions, sockets)".

## Notes / cross-references

- Source of truth read during scoping: `lib/tmux_exec.py` and `lib/tmux_exec.sh`
  headers + docstrings already articulate the design crisply — distill from
  them, don't re-derive.
- Per repo convention, keep the doc brief and current-state-only; genericize
  any real-repo names if examples are needed.
