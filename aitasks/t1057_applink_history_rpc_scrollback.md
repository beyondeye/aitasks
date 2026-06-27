---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [applink, applink_dataplane]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-22 16:52
updated_at: 2026-06-27 22:35
---

Implement the AppLink `history` RPC (Stage 5) on the server: a scrollback query endpoint that returns past rows as a single binary keyframe with NEGATIVE row_ids (-1 = line immediately above before_line, etc.) per content_transport.md §Scrollback / §history.

Current state: there is NO `history` verb in applink/router.py — Stage 5 is unimplemented server-side (and on mobile, paired task aitasks_mobile t14_13). Request shape: {pane_id, before_line, count}; server replies on the control plane with a token, then sends one binary keyframe on the data plane with negative-id rows. Reuses the keyframe frame shape (no sixth frame type).

Note: ties into the keyframe-viewport-only fix (t1054) — once live keyframes are viewport-only, scrollback is reached exclusively through this RPC. The capture buffer already retains scrollback (capture-pane -S -200, monitor_core.py).

Surfaced by the aitasks_mobile t14_11 AppLink audit (aidocs/applink/implementation_status_2026-06-22.md, server #3).
