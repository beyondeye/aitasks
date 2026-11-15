---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [sitrep]
gates: [risk_evaluated]
anchor: 2299
followup_kind: upstream_defect
created_at: 2026-11-15 19:37
updated_at: 2026-11-15 19:37
---

## Origin
Spawned from t2299_2 during Step 8b review.

## Upstream defect
- `.aitask-scripts/lib/sitrep_refresh.py:271-275 — TaskIndex._facts accepts a missing or invalid status: an archived record with status '' or 'Banana' comes back as found=archived with no error, so refresh classifies unvalidated records`

## Diagnostic context
t2299_2 (the sitrep crash detector) first planned to delegate archived-task lookups to `sitrep_refresh.TaskIndex.lookup`. Plan review showed that `_facts` builds `TaskFacts(found=..., status=str(meta.get("status") or "").strip())` without validating it. A scratch probe confirmed it: an archived loose or bundled record with no `status:`, or with `status: Banana`, returns `found=archived` and no error. `_meta_of` also returns any dict, so only a missing or unparseable frontmatter is an `error`.

t2299_2 therefore validates archived records itself (`sitrep_crash.strict_meta`) and uses `TaskIndex` only for its fold-scan answer. Refresh (`check_task` and its reminder / "landed" verdicts) still reads the lax facts: an unreadable status can be classified as an ordinary not-Done task instead of `unknown`.

`tests/test_sitrep_crash.py::TaskReader::test_archived_records_are_validated` pins the current lax behaviour as a contrast: `idx.lookup("12").found == "archived"` for a `Banana` status.

## Suggested fix
In `TaskIndex._lookup`, validate the status for both active and archived records against the task-status vocabulary (Ready, Editing, Implementing, Postponed, Done, Folded). Return `TaskFacts("error", detail=...)` for a missing or invalid one, and keep archive read errors as they are. Then flip the contrast assertion in `tests/test_sitrep_crash.py`, and add refresh tests showing such a record gives `unknown`, never a done or open verdict.
