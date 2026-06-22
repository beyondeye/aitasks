---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [applink]
created_at: 2026-06-22 16:51
updated_at: 2026-06-22 16:51
---

AppLink server does not handle the `pause` flow-control verb. content_transport.md §Back-pressure specifies: 'Mobile MAY send a pause push (verb: pause) when backgrounded but not yet Suspended ... server stops all pushes until resume push, no state lost.'

Current state: applink/router.py registers `resume` and `bye` as session verbs (SESSION_VERBS at router.py:69) but has NO `pause` handler in any verb set — a `pause` frame returns UNKNOWN_VERB. Meanwhile the mobile client (aitasks_mobile MonitorSessionMediator.kt:205-210) sends `pause` and optimistically transitions to Suspended, so the two sides disagree: the phone believes pushes are paused while the server keeps streaming.

Fix: add a `pause` verb that halts the PushScheduler for the connection until `resume`, mirroring the resume path. Gate at the read_only tier (it is a self-throttle, like subscribe/request_keyframe).

Surfaced by the aitasks_mobile t14_11 AppLink audit (aidocs/applink/implementation_status_2026-06-22.md, server #5).
