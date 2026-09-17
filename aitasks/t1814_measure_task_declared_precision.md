---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [scheduling, planning]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1569
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-09-16 09:59
updated_at: 2026-09-17 08:16
---

## Origin

Risk-mitigation ("after") follow-up for t1688_1, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — description surfaces may be too coarse to justify `warn`.

From t1688_1's `## Risk`: "Descriptions name files as context as well as edit
targets (measured: ~16% of resolved description tokens sit under a key-files
heading), so `task_declared` overlaps are coarse · severity: medium (residual —
they can no longer produce a false CONFLICT, PINNED 6; the cost is caveat noise,
and a real description-only collision is reported as a caveat rather than
stopped) · → mitigation: measure_task_declared_precision".

## Goal

Extend `./.aitask-scripts/aitask_parallel_admission.sh sweep` with a
task-description source and score `task_declared` surfaces against the files
that actually landed, over the archived corpus — precision/recall and the
CONFLICT vs CLEAR_CAVEATED split — exactly as t1643 did for plan surfaces
(`.aitask-scripts/lib/parallel_admission_sweep.py`).

Two questions the measurement must answer:

1. **May a `task_declared` overlap ever grade CONFLICT?** t1688_1 ships them
   non-blocking (PINNED 6: class `declared`, caveat `task_declared_overlap`,
   never a conflict) precisely because this number did not exist. Promoting them
   is a contract change that t1688_2 and t1343 both depend on — do not promote
   without the numbers.
2. **Would a narrower extraction buy enough precision to justify it?** Compare
   whole-body extraction against a "key-files-section-preferred" variant (use
   the section only when the body has a key-files-style heading). Measured over
   the 527 active Ready/Implementing tasks on 2026-09-14: 2669 resolved token
   occurrences, of which only ~424 sit under such a heading (267 "key files to
   modify" + 157 "key files"); verification sections ~440, context/goal/problem
   ~375, reference sections ~178; by kind 493 are `aidocs/` / `CLAUDE.md`
   citations and 179 are task-data documents. Only 119/527 tasks carry such a
   heading at all, which is why narrowing was rejected as the mechanism in
   t1688_1 — it would return ~75% of tasks to `no_plan`.

Baseline to compare against (t1688_1, 129 candidates, `replay --candidates auto
--from plan --lock-freshness require-fresh`): CLEAR_CAVEATED 103, CONFLICT 12,
UNCHECKABLE 14, with 6 candidates carrying a `task_declared_overlap` caveat —
the would-have-been CONFLICTs whose precision this task measures.

## Key files

- `.aitask-scripts/lib/parallel_admission_sweep.py` (the t1643 oracle/confusion
  machinery), `.aitask-scripts/lib/parallel_admission_collect.py`
  (`sweep_population`, `task_surface`, `plan_extraction`).
- `.aitask-scripts/lib/plan_paths.py` (`task_body_text`,
  `cut_task_framework_sections`) for the narrowing variant.
- `tests/test_parallel_admission_sweep.py`, `tests/test_parallel_admission_collect.py`.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (read the LAST line only).
- Record the precision/recall table and the recommendation in the plan's Final
  Implementation Notes, and note it to t1688_2 if that task is still open.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T05:16:22Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-17T05:34:09Z status=pass attempt=1 type=human
