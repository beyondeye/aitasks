---
priority: medium
effort: medium
depends: [t2038_3]
issue_type: feature
status: Ready
labels: [monitor]
anchor: 2034
created_at: 2026-10-16 08:11
updated_at: 2026-10-16 08:11
---

State in the Go server, and the end-to-end comparison (parent: Go monitor status
server task).

## Source (`monitor/monitor_core.py` unless noted)

- Idle clock: `_apply_bookkeeping` (`:2918`–`:2926`), capture-generation
  ordering.
- Shadow pairing: `@aitask_shadow_target`, `match_shadow_pane_info` (`:533`).
- Task completion: `TaskInfoCache` (`:4309`), identity-keyed on
  `(st_mtime_ns, st_size)`, with the identity sampled before the read and a
  re-resolve under `archived/` on `OSError`; `is_task_completed`
  (`monitor/monitor_shared.py`).
- Snapshot/delta emission per the protocol.

## Verification

End-to-end: the Go and Python servers run against the same private tmux server
and project fixtures, and their snapshot streams match (allowing for timing
fields).
