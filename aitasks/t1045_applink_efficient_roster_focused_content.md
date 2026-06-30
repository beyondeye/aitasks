---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [applink, applink_dataplane]
assigned_to: dario-e@beyond-eye.com
anchor: 1044
created_at: 2026-06-21 18:17
updated_at: 2026-06-30 18:07
boardidx: 100
---

Follow-up to t1044. After t1044, an empty/absent `subscribe` expands to **all**
discovered panes and streams full content (keyframe + deltas) for every pane.
This works but is more bandwidth than necessary on cellular: the only pane whose
live content the user is actually viewing is the focused/explicitly-subscribed
one.

## Goal (server side — paired with aitasks_mobile)

Design and implement a more efficient subscription contract:
- Push `pane_status` (the roster: badges, idle/awaiting-input, window/task ids)
  for **all** discovered panes, so the mobile pane list stays populated.
- Stream **binary content** (keyframe/delta/append) only for the **focused** (or
  explicitly-subscribed) pane(s) — not for every pane in the roster.

This needs the `Subscription` model to track a "status pane set" distinct from a
"content pane set", and `pusher._push_pane` / `_run_once` to honor that split
(send `_send_pane_status` for the roster but skip the binary frames for
status-only panes). Update `aidocs/applink/protocol.md` §Subscription and
`content_transport.md` §subscribe to document the refined contract.

## Cross-repo coordination

This is a paired change: the mobile app (aitasks_mobile) must send/honor the
roster-vs-focused distinction (e.g. via `focus` selecting the content pane, or a
new field). The mobile-side work is tracked in the coordinated task
**aitasks_mobile#19** (which carries the reverse cross-repo dependency on this
task — the server contract lands first, then the client adopts it). Keep the wire
format additive/versioned per protocol.md §Versioning so older clients still work.

## Reference

- t1044 plan: aiplans/archived/p1044_applink_empty_subscribe_pane_roster.md
  (the "all panes, full content" baseline this optimizes).
- Server: .aitask-scripts/applink/content.py (`Subscription`),
  pusher.py (`_run_once`/`_push_pane`/`_send_pane_status`), router.py
  (`subscribe` handler / `_discover_pane_ids`).
