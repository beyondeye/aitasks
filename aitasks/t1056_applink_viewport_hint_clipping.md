---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [applink, applink_dataplane]
created_at: 2026-06-22 16:52
updated_at: 2026-06-25 09:55
boardidx: 60
---

Implement AppLink `viewport_hint` (Stage 4) span/row clipping on the server. content_transport.md §subscribe: the server clips spans/rows to the client's requested column window before encoding, halving bandwidth for wide TUIs on narrow screens.

Current state: applink/content.py:465 stores the hint on the Subscription ('stored, ignored until Stage 4 clipping') but never applies it — keyframe/delta/append all encode the full width. The mobile client also doesn't emit the hint yet (paired task aitasks_mobile t14_12), so this delivers value once both land.

Fix: when subscription.viewport_hint is set, clip each row's spans to the [cols_lo, cols_hi] window (and optionally the rows window) in the keyframe/delta/append encode path, recomputing span widths/offsets at the clip boundary.

Surfaced by the aitasks_mobile t14_11 AppLink audit (aidocs/applink/implementation_status_2026-06-22.md, server #2).
