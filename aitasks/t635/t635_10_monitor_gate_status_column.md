---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t635_8]
issue_type: feature
status: Implementing
labels: [gates, aitask_monitor, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 18:54
updated_at: 2026-06-16 16:37
---

## Context

Phase 3 of `aidocs/gates/integration-roadmap.md` — the framework doc's
integration table row for the monitor TUI: a per-task gate status column
(e.g. "3/4 pass, 1 pending").

## Scope

- `ait monitor` (and minimonitor where layout allows) shows a compact
  per-task gate summary derived via the shared t635_8 parser.
- Tasks without a ledger show nothing (no column noise for ungated tasks).
- Follow `aidocs/framework/tui_conventions.md`; keybindings only if an
  interaction is added (display-only is acceptable for v1).

## References

- `aidocs/gates/integration-roadmap.md` (Phase 3)
- `aidocs/gates/aitask-gate-framework.md` (integration table, Monitor TUI row)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T13:37:07Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T13:37:08Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-16T13:55:52Z status=pass attempt=1 type=human
