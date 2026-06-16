---
priority: low
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: [t822_8]
issue_type: feature
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 10:43
updated_at: 2026-06-17 00:30
---

Add an applink-mode flag to `aitask_monitor.sh` — a `--headless-for-applink` mode that skips Textual startup and exposes `monitor_core` only via the applink listener, for running the bridge on a box nobody is watching.

## Context

Eighth (final) §"Deferred follow-up tasks" bullet of `aidocs/applink/monitor_port_design.md`. Depends on t822_8: a headless server is only useful once the listener (t822_7) can actually push pane content (t822_8).

## Key Files to Modify

- `.aitask-scripts/aitask_monitor.sh` — new flag; route to a headless entry point instead of the Textual app. Follow `aidocs/framework/shell_conventions.md` for the shell changes.
- The applink listener package — a headless runner: start `monitor_core` capture loop + WS listener without any Textual `App` (no terminal UI; log to stdout/file).
- Decide and document where pairing/QR happens in headless mode (e.g. print the `applink://...` URI + ASCII QR to stdout, or require a pre-provisioned session) — coordinate with the pairing flow in `aidocs/applink/protocol.md`.

## Reference Files

- `aidocs/applink/monitor_port_design.md` — §Deferred follow-up tasks (this bullet), §Headless-core extraction (no-Textual rule makes this possible)
- `.aitask-scripts/aitask_monitor.sh` — existing arg parsing / launch path
- `aidocs/framework/tui_conventions.md` — launcher conventions (this mode deliberately bypasses the TUI; don't register it as a switchable TUI)

## Implementation Plan

1. Add flag parsing + help text to `aitask_monitor.sh`; route to the headless runner.
2. Implement the headless runner reusing the t822_7/t822_8 listener + push loop with no Textual imports on the import path.
3. Handle shutdown signals cleanly (close control client, stop WS server).
4. Document the mode where the applink user docs live at that point (keep out of the TUI lists per project conventions if it isn't a TUI).

## Verification Steps

- `ait monitor --headless-for-applink` starts without a TTY (e.g. under `setsid`/redirected stdout) and serves a pairing endpoint.
- A scripted client pairs and receives keyframes — no Textual process/screen involved.
- Plain `ait monitor` behavior unchanged.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T21:30:45Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T21:30:47Z status=pass attempt=1 type=machine
