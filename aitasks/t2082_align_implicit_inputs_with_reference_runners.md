---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-10-20 15:21
updated_at: 2026-10-20 15:21
---

## Origin

Risk-mitigation ("after") follow-up for t2081, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — implicit-input rules keyed on language because M3.2 reference runners are not implemented

- **The reference runners (M3.2) are not implemented.** Rules key on the test language, not on the runner's real command line, cwd or unit kind. An implemented runner may read inputs these rules miss. · severity: medium · → mitigation: align_implicit_inputs_with_reference_runners

## Goal

Once M3.2 (`t1854_2`) lands the pytest / go-test / gradle-class / bash-file reference runners, cross-check `goengines/internal/testmap/cost/implicit.go` against what each implemented runner actually reads:
- its command line and working directory: pytest `-c`, `--rootdir`, `-p` plugins and an ini resolved from the cwd rather than the test's ancestors; go-test per-package vs per-file units and its `-run` filter;
- the unit kind and `filter_scope` it declares. A gradle-class runner with `filter_scope: whole_run` is already `opaque:whole-run`.

Add a red-proved row with an exact `anchor_reason` to `TestEligibilityImplicitInputs` for every input the rules miss. Today the rules key on `Facts(test).Lang`; if a runner's real behaviour differs (e.g. its cwd is not an ancestor of the test), key the affected rule on the runner as well. The isolated-mutant harness and the 33 mutants from t2081 are described in that task's archived plan.
