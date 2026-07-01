---
priority: low
effort: medium
depends: []
issue_type: test
status: Ready
labels: [applink, applink_dataplane]
anchor: 1007
created_at: 2026-06-28 12:31
updated_at: 2026-06-28 12:31
boardidx: 110
---

## Origin

Risk-mitigation ("after") follow-up for t1007, created at Step 8d after implementation landed.

## Risk addressed

addresses: goal-achievement "no real mobile client / synthetic-only verification"

- The data-plane resource limits hardened in t1007 (max subscribed panes, cadence floor/ceiling + type coercion, outbound `MAX_PUSH_FRAME_BYTES` cap incl. history, scheduler fault isolation) are exercised only against the in-process synthetic FakeWS/FakeMonitor unit path, not a live `wss://` socket or the real aitasks_mobile app. · severity: low

## Goal

Add a live/e2e test that drives the limits end-to-end through a real `AppLinkServer` `wss://` socket with a scripted synthetic client (pair → subscribe → drive frames), rather than calling `PushScheduler._run_once` / `_drain_history` directly. Cover:

- An over-long `subscribe` pane list is rejected, and an empty/roster subscribe is bounded to `MAX_SUBSCRIBED_PANES`.
- A non-numeric / out-of-range cadence is clamped (no connection drop); `keyframe_interval_ms` is capped at `MAX_KEYFRAME_INTERVAL_MS`.
- A pane whose encoded frame exceeds `MAX_PUSH_FRAME_BYTES` is dropped + audited over the real socket, the connection stays live, and the pane re-anchors (next live frame is a fresh keyframe); an oversize history keyframe is silently not delivered.
- A single pane's encode/capture fault does not tear down the connection's push loop.

Skippable when `msgpack` / TLS deps are unavailable (mirror the existing `tests/test_applink_*.sh` SKIP guards). Reference the in-process coverage in `tests/test_applink_pusher.sh` / `test_applink_server_limits.sh` and the headless-live harness in `tests/test_applink_headless_live.sh`.
