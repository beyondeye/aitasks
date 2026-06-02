---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
created_at: 2026-06-02 11:55
updated_at: 2026-06-02 11:55
boardidx: 120
boardcol: manual_verifications
---

Carry-over of deferred manual-verification items from t905. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] --link-to-task creates a child aitask and writes module_tasks[M]. — DEFER 2026-06-02 11:42 auto: module_tasks[M] write half verified deterministically (_write_module_task merges/overwrites/initializes). Live half _create_linked_module_task shells out to 'aitask_create.sh --batch --commit' creating a REAL committed child aitask — not safely automatable (would pollute task tree + commit to shared aitask-data branch). Needs human live TUI run.
