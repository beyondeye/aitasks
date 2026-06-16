---
priority: medium
effort: low
depends: [t635_8]
issue_type: feature
status: Implementing
labels: [gates, aitask_monitor, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 18:54
updated_at: 2026-06-16 15:26
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
