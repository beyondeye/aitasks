---
priority: low
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [shadow, concurrency]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-09-24 15:42
updated_at: 2026-09-25 16:53
---

## Origin

Risk-mitigation ("after") follow-up for t1873, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — the same language gap in drift check / parallel admission / trail gather.

(From t1873's risk evaluation.) `lib/plan_paths.py` `extract()` recognizes only `sh|py|md|yaml|yml|json|toml`. A plan referencing `internal/pkg/server.go`, `src/main.rs`, `app/index.ts`, or an extensionless `Makefile` therefore yields zero tokens, so the remote drift check, parallel admission and trail gather have **no** path evidence for Go/Rust/TS/extensionless projects (findings doc `aidocs/framework/plan_path_reference_extraction_findings.md` §1–§2).

## Goal

t1873 added `plan_paths.find_references()`, the inverted, language-agnostic search: given the paths git reported as changed, which does a text reference, and under which heading. It also added `find_suffix_references()` for module-relative mentions and `find_dir_references()`. Only the shadow's evidence helper (`lib/shadow_scope.py`) uses them today.

Evaluate moving the other plan_paths consumers from extension-grammar extraction to `find_references()` against their changed-path sets:

- `aitask_remote_drift_check.sh` (via `lib/plan_paths_sh.sh`): it already has the remote-changed set (`git diff --name-only <base>...origin/<base>`), so it can test that set against the plan text instead of intersecting extracted tokens.
- `lib/parallel_admission.py` / `lib/parallel_admission_collect.py` and `lib/trail_gather.py`: these need candidates FROM the plan (in-flight surfaces with no changed set), so assess whether a hybrid is appropriate. Use `extract()` for candidates, plus `find_references()` against each in-flight task's dirty/committed set where one exists.

For each consumer, measure the prompt-rate and verdict impact on the live corpus before switching (the parallel-admission comments in `aitasks/metadata/profiles/fast.yaml` record why prompt rate matters). Keep `tests/test_plan_paths_seam.sh`'s single-grammar guard intact.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-25T13:53:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-25T14:40:25Z status=pass attempt=1 type=human
