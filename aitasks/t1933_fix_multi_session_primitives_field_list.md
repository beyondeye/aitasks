---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [monitor, minimonitor, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1922
followup_kind: upstream_defect
created_at: 2026-10-09 15:31
updated_at: 2026-10-09 15:43
---

## Origin

Spawned from t1922 during Step 8b review.

## Upstream defect

- tests/test_multi_session_primitives.sh:55 — "AitasksSession fields" assertion still expects the pre-t1811 field list and fails because `default_session_problem` (added by t1811) is missing from the expected string; pre-existing, untouched by this task.

## Diagnostic context

While verifying t1922 (session → project-root discovery), `bash tests/test_multi_session_primitives.sh` reported 19/20 with:

```
FAIL: AitasksSession fields (expected 'FIELDS:is_live,is_stale,project_group,project_name,project_root,session', got 'FIELDS:default_session_problem,is_live,is_stale,project_group,project_name,project_root,session')
```

t1922 did not change the `AitasksSession` fields; `default_session_problem` was added by t1811 (registry-synthesized entries whose `tmux.default_session` could not be read), and this pinned field list was never updated.

## Suggested fix

Add `default_session_problem` to the expected sorted field list at tests/test_multi_session_primitives.sh:55 (and check whether any other pinned field lists in tests still predate t1811).
