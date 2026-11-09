---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [task_relations]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1981
followup_kind: upstream_defect
created_at: 2026-11-09 11:00
updated_at: 2026-11-09 11:37
---

## Origin
Spawned from t1981_6 during Step 8b review.

## Upstream defect
- `.aitask-scripts/aitask_archive.sh:595` — in the child flow, `archive_metadata_update "$parent_task_file"` applies the run's global `--superseded` (and, since t1981_6, `--obsolete`) reason to the auto-archived PARENT too. A parent whose last pending child is archived as superseded or obsolete gets `archived_reason: superseded|obsolete`, although its other children landed as completed work.

## Diagnostic context
`archive_metadata_update` reads the script-global `SUPERSEDED` / `OBSOLETE` flags. In `archive_child`, when the archived child was the parent's last pending child, the parent is archived in the same run through the same helper, so it inherits the child's reason.

Consequences:
- **The task-relations consumers misclassify the parent.** `relations_consume.end_state` reads `archived_reason` and reports the parent as `dropped`, not `landed` (task_relations.md D8).
- **The landed trigger skips it.** t1981_6's `fire_landed_triggers` skips `--superseded` / `--obsolete` runs entirely, so a parent whose other children completed real work never fires `obsolescence landed`.

## Suggested fix
Apply `archived_reason` only to the task the flag names (the child). Archive the auto-archived parent as completed work, unless a deliberate rule says otherwise. Then let `fire_landed_triggers` fire for that parent even on a `--superseded` / `--obsolete` child run, by deciding per id from the archived file rather than from the global flags. Add a test with a parent whose last child is archived `--superseded` / `--obsolete`.
