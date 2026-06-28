---
priority: medium
effort: low
depends: []
issue_type: test
status: Implementing
labels: [applink, applink_dataplane]
assigned_to: dario-e@beyond-eye.com
anchor: 1057
created_at: 2026-06-28 10:57
updated_at: 2026-06-28 13:00
boardidx: 60
---

## Origin

Risk-mitigation ("after") follow-up for t1057 (AppLink `history` RPC, server-side), created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement risk (severity: medium) from t1057's plan `## Risk`: `before_line`'s coordinate space + the best-effort anchoring contract must match `aitasks_mobile` t14_13, or end-to-end scrollback renders at the wrong offset on the phone even though the server is internally correct. t1057's server-side unit + e2e tests cannot cover the cross-repo rendering agreement alone.

## Goal

Once the paired mobile client (`aitasks_mobile` t14_13) lands, verify end-to-end that the server's negative-row-id `history` keyframe renders scrollback at the correct offset on the phone:

- Confirm the mobile client treats `before_line` as **viewport-relative** (`0` = viewport top) and translates each response `row_id -j` back to its own absolute `before_line - j`, matching the server contract documented in `aidocs/applink/content_transport.md` §Scrollback ("Server semantics (v1)").
- Scroll up over an idle/finished agent pane and confirm the pulled scrollback lines are correct and in order (contiguous `-1..-m`, no gaps, no overlap with the live viewport).
- Over an **actively-scrolling** pane, confirm behavior reflects the documented best-effort anchoring (anchored to the drain-time capture; may overlap by the scroll delta) without crashing or corrupting the live view.
- Confirm a stale/nonexistent subscribed pane yields a token but no rendered scrollback (best-effort delivery), and that an unsubscribed pane is rejected (`not_subscribed`).

This closes the cross-repo coordinate-space + anchoring agreement between the t1057 server and the t14_13 mobile client.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-28T10:03:53Z status=pass attempt=1 type=human
