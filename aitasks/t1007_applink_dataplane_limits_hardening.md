---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [applink, applink_dataplane]
created_at: 2026-06-16 10:54
updated_at: 2026-06-25 09:55
boardidx: 110
---

## Origin

Risk-mitigation ("after") follow-up for t822_8 (applink snapshot push loop / data plane Stage 1), created at Step 8d after implementation landed.

## Risk addressed

addresses: code-health "asyncio push scheduler" + goal-achievement "no real mobile client / schema-drift & DoS"

- New per-connection **asyncio push scheduler** (cadence timers, wake-event, back-pressure, lifecycle tied to connection close) is fresh concurrency on the server's event loop. · severity: medium
- **No real mobile client here** — payload-schema drift / malformed-input handling can only be exercised against a synthetic client. · severity: medium

## Goal

Enforce and verify resource limits on the applink binary data plane so a malicious or buggy client cannot exhaust server resources or crash the push loop. Coordinate with **t985** (applink security review + hardening) so the work is not duplicated — this task is the data-plane-specific slice.

Scope:
- **Max subscribed panes per connection** — reject / cap `subscribe` payloads with an unreasonable pane count (the scheduler currently iterates every requested pane each tick).
- **Cadence-floor enforcement audit** — confirm `content.clamp_cadences` floors cannot be bypassed and add an upper bound on `keyframe_interval_ms`.
- **MessagePack frame-size cap + decode-bomb guard** — bound the size of any client→server payload the router parses; ensure outbound frame sizes are bounded under pathological pane content.
- **Scheduler resilience** — verify a single pane's encode/capture error cannot take down the whole connection's push loop; add a regression test.

## Reference

- `aiplans/archived/p822/p822_8_applink_snapshot_push_loop.md` (Final Implementation Notes) — what currently exists and what is explicitly NOT yet bounded.
- `.aitask-scripts/applink/pusher.py`, `.aitask-scripts/applink/content.py`, `.aitask-scripts/applink/router.py`.
- `aidocs/applink/content_transport.md` §Back-pressure; `aidocs/applink/permissions.md`.
