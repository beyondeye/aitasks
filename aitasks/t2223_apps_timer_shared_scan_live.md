---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [monitor, minimonitor, performance]
gates: [risk_evaluated]
anchor: 2034
followup_kind: risk_mitigation
created_at: 2026-11-07 19:15
updated_at: 2026-11-07 19:15
---

## Origin

Risk-mitigation ("after") follow-up for t2037_3, created at Step 8d after implementation landed.

## Risk addressed

An app timer that requests a full server scan per client would pass every in-plan check below the app.

From t2037_3's plan (`## Risk` / Goal-achievement): "Checks below the app could pass even if the real app interval asked for a full server scan per client, which would quietly defeat the resource savings. The unit-level 'App timer' test covers one mounted app (or two) against a producer's full-scan count. A live check of several mounted apps over real intervals against the real server's scan count is deferred as a follow-up."

## Goal

Add a live test that mounts several REAL `ait monitor` / `ait minimonitor` apps (their real `main()` / `_start_monitoring` / `set_interval` wiring, not hand-built `MonitorClient`s) on an isolated tmux server, sharing one real status server, and counts that server's full scans over several intervals.

- The status server is another process, so it needs a scan counter it exposes (for example a `stats` request or a field in `welcome.server`), added to `.aitask-scripts/monitor/status_server.py` and the protocol spec `aidocs/framework/monitor_status_protocol.md`.
- Exclude startup and intentional refresh actions; assert that the count of full scans over N intervals equals the server's own tick count (one scan per tick, independent of the number of mounted apps), with a control that mounts the apps in-process (`AITASKS_MONITOR_SERVER=0`) and shows the per-app scans.
- Reuse the isolation of `tests/test_monitor_status_server_live.py` `LiveCase` (scratch `-L` socket, `TMUX_TMPDIR`, `XDG_RUNTIME_DIR`, `HOME`, marks file) and the cleanup rules of `tests/test_monitor_apps_subscribe_live.py`.
- Existing coverage it extends: `tests/test_monitor_apps_subscribe.py::AppTimerTests` (unit level, fake producer) and `tests/test_monitor_apps_subscribe_live.py` (live, clients only, counts client-side `capture-pane`).
- If it is timing-sensitive under the xdist lane, add it to the runner's serial carve-out and to the CLAUDE.md list in the same commit.
