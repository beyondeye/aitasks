---
priority: medium
effort: low
depends: [2037_4]
issue_type: manual_verification
status: Ready
labels: [applink, monitor]
verifies: [2037_4]
premise_baseline: fff7e0564ad3161d17fd2540b1fce78d30d60b8e @ 2026-11-09 15:18
anchor: 2034
followup_kind: risk_mitigation
created_at: 2026-11-09 15:18
updated_at: 2026-11-09 15:18
---

## Origin

Risk-mitigation ("after") follow-up for t2037_4, created at Step 8d after implementation landed.

## Risk addressed

no real paired phone exercised the server-mode push and verb paths

- No real phone in the loop: the live check drives the real `_handle` and router over a scripted socket, not a paired phone over TLS, so a device-specific difference (cadence feel, parked panes on screen) would not be caught · severity: medium · → mitigation: applink_device_manual_check

## Goal

With a real paired phone, confirm the server-mode behaviour t2037_4 shipped (applink reads pane status from the shared monitor status server while a device streams): badges, cadences, actions, compare mode, parked panes, and the idle lifecycle. Design: `aidocs/framework/monitor_status_protocol.md` "Consumers: applink".

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t2037_4
