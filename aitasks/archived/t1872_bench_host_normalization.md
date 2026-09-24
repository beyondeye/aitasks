---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [testmap, go_engine, testing, test_infrastructure]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1878]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-09-24 09:17
updated_at: 2026-09-24 15:44
completed_at: 2026-09-24 15:44
---

## Origin

Risk-mitigation ("after") follow-up for t1852_2, created at Step 8d after implementation landed.

## Risk addressed

bench baselines recorded on the dev host vs CI — "Bench baselines are recorded on this dev host; M1.3 wires the 2× rule into CI, where a different machine can fail (or mask) the ratio · severity: medium · → mitigation: bench_host_normalization"

## Goal

Make the goengines 2× benchmark gate portable across machines, so that t1852_3's `goengines-check.yml` can run it on CI hardware without false failures (a slower runner) or masked regressions (a faster runner).

Context (landed in t1852_2, commit 33012bff7):
- `goengines/internal/benchgate` (ParseBench / ParseBaseline / Compare / Rewrite) and the runner `goengines/internal/tools/benchgate` (`go run ./internal/tools/benchgate -baseline bench/baseline.txt [-partial] [-update]`; it runs the producer itself, full mode is the gate, BENCH_* protocol lines, exit 0/1/64).
- `goengines/bench/baseline.txt`: `<pkg>.<Benchmark> <ns/op> [budget=<duration>]`, recorded on one developer host.
- The README `## Interfaces` table pins the current shapes; extend it, don't break it.

Suggested design (validate at planning):
- Add a fixed-work calibration benchmark (CPU-bound, allocation-free, no I/O) whose baseline is recorded next to the others (e.g. a `# calibration <ns/op>` header, or a reserved `calibrate.BenchmarkCalibrate` line).
- Compare scales each baseline by `current_calibration / baseline_calibration` before applying the 2× rule; absolute `budget=` values stay unscaled (they are the proposal's latency targets, not relative numbers). Print the scale factor (e.g. `BENCH_SCALE:<factor>`).
- Fail closed: a missing or non-finite calibration measurement fails the full gate; an implausible scale (e.g. outside 0.25–4) is reported, not silently applied.
- Tests: calibration scaling on synthetic inputs (a 2× slower host with 2× slower benches passes; a genuine 2.5× regression on the same host fails), calibration missing → fail, budgets unaffected by scaling.
- Coordinate with t1852_3 (the CI workflow) on whether CI records its own baseline instead; if so, document the choice in the README.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-24T07:31:04Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-24T12:42:54Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-24T12:44:56Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:ff6a35a8d6a2bb61

> **✅ gate:risk_evaluated** run=2026-09-24T12:44:56Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1872/risk_evaluated_2026-09-24T12:44:56Z-risk_evaluated-a1.log`
