---
priority: medium
effort: medium
depends: [t2037_1]
issue_type: feature
status: Ready
labels: [monitor, minimonitor]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

The Python `MonitorClient` (parent: Python monitor status server task).

## Do

- Expose the `TmuxMonitor` read surface the apps use (`capture_all_async`,
  `get_shadow_snapshot`, `get_session_to_project_mapping_async`, `get_pane`, …),
  backed by a subscription, so the app-side changes stay small.
- Fallback: when the server cannot be reached or started, use in-process
  `TmuxMonitor` (today's code) — the same posture as the existing
  control-mode → subprocess fallback. Reconnect when the server restarts.
- Replay mode: serve a recorded stream file (t2034_3 recorder) instead of a live
  server. The Textual twin of the Go monitor parity demo (aitasks_go#16_5) uses
  it.

## Verification

Tests against a stub server: subscribe/snapshot/delta, stale `gen` dropped,
server restart → reconnect, unreachable → fallback, replay of a recorded
fixture.
