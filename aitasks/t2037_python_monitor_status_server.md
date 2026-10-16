---
priority: medium
effort: high
depends: [t2034_3]
issue_type: feature
status: Ready
labels: [monitor, minimonitor, tmux, applink]
children_to_implement: [t2037_1]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

Build the shared monitor status server in Python, reusing `monitor_core`
unchanged as the producer, plus a Python client. Then switch monitor,
minimonitor and applink to subscribe. Background and overall shape: aitasks#2034;
protocol: t2034_3; producer settings semantics: t2034_2. Split out of t2034
because the server, the client and the two consumer migrations are separate
pieces of work.

## Children

1. Server process and lifecycle.
2. `MonitorClient` (fallback, replay mode).
3. Monitor + minimonitor subscribe.
4. applink subscribes.

## Cross-repo

The replay mode (child 2) feeds the Textual twin of the Go monitor parity demo
(aitasks_go#16_5). The Go server (a later top-level task anchored to t2034)
reimplements this server behind the same protocol.
