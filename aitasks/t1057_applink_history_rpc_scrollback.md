---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [applink, applink_dataplane]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-22 16:52
updated_at: 2026-06-28 10:42
boardidx: 210
---

Implement the AppLink `history` RPC (Stage 5) on the server: a scrollback query endpoint that returns past rows as a single binary keyframe with NEGATIVE row_ids (-1 = line immediately above before_line, etc.) per content_transport.md §Scrollback / §history.

Current state: there is NO `history` verb in applink/router.py — Stage 5 is unimplemented server-side (and on mobile, paired task aitasks_mobile t14_13). Request shape: {pane_id, before_line, count}; server replies on the control plane with a token, then sends one binary keyframe on the data plane with negative-id rows. Reuses the keyframe frame shape (no sixth frame type).

Note: ties into the keyframe-viewport-only fix (t1054) — once live keyframes are viewport-only, scrollback is reached exclusively through this RPC. The capture buffer already retains scrollback (capture-pane -S -200, monitor_core.py).

Surfaced by the aitasks_mobile t14_11 AppLink audit (aidocs/applink/implementation_status_2026-06-22.md, server #3).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-28T07:42:19Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-28T07:42:20Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-28T07:55:40Z status=pass attempt=1 type=human
