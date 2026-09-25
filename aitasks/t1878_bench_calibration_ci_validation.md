---
priority: medium
effort: low
depends: [1852_3]
issue_type: test
status: Ready
labels: [testmap, go_engine, testing, test_infrastructure]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-09-24 15:44
updated_at: 2026-09-24 15:44
---

## Origin

Risk-mitigation ("after") follow-up for t1872, created at Step 8d after implementation landed.

## Risk addressed

calibration proxy may not track CI hardware (goal-achievement)

- Calibration is a single CPU-bound proxy; fork/IO-dominated benchmarks (`LsTree`) and noisy shared CI runners may not track it, so the scaled 2× rule could still flake or mask on real CI hardware. Partly de-risked here by the serial producer and the step-7 slowed-host run; the CI side stays unverifiable until t1852_3's workflow exists, which the advisory-until-validated rollout rule covers · severity: medium · → mitigation: bench_calibration_ci_validation

## Goal

Validate the goengines benchgate's host normalization on real GitHub-hosted runners and decide whether the CI bench step may become a required check.

State after t1872 (see `goengines/README.md`, *Host normalization*): per-line calibration classes (`cpu` default, `cal=spawn` for LsTree, `cal=sha1` for BlobDigest); default producer `go test -p 1 -cpu 1 -run ^$ -bench . -count 3 ./...`; scaled ratios fail above `benchgate.Threshold = 1.6` (the 2× rule, judged with margin). On the recording host (Core Ultra 9 275HX, 6 core/quota conditions) healthy scaled ratios reached 1.17 and seeded 2.1× regressions scaled as low as 1.72 — a single-host measurement with only a 0.12 margin under the lowest regression. The gate is documented as **not yet portable**.

Once `goengines-check.yml` (t1852_3) exists with the bench step **advisory** (`continue-on-error`, not required):

1. Collect ≥5 healthy samples and ≥2 seeded-regression samples (a temp baseline with every non-calibration line divided by 2.1, applied inside the job only). Each sample is a **separate fresh workflow run** (fresh runner VM; `workflow_dispatch` re-runs spread over ≥2 days) — never repeats inside one job.
2. Each run records to its job summary: CPU model (`/proc/cpuinfo` model name), `nproc`, every `BENCH_SCALE:` line, and every benchmark's scaled ratio.
3. **Promote the step to required** only if, for every benchmark: every healthy run passes with scaled ratio ≤ 1.3 and plausible scales (0.25–4), and every seeded run fails it (scaled > 1.6).
4. Otherwise keep it advisory and file the cause as a task (mis-classed benchmark, missing calibration class, a threshold that does not separate on runners, a scale outside 0.25–4 because the runner is >4× slower than the recording host).
5. If all samples ran on one CPU model, record that in the README and keep the rule that a first unexplained bench failure on a new CPU model demotes the step to advisory.

Record the per-run table and the decision in `goengines/README.md` (replace the single-host basis paragraph's "not yet portable" statement only if promotion criteria are met).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852_3** id=2026-09-25T08:48:03Z.c4f255f964febebdb49c0905 from=t1852_3 from_verified=yes at=2026-09-25T08:48:03Z base=c1095fff666203f8a5300204b6982373bad04d25 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t1852_3, tree-relative to code commit c1095fff6 (.github/workflows/goengines-check.yml, goengines/ci/benchci.sh; docs in aidocs/framework/go_engine.md "CI").
> | 
> | - The `bench` job is advisory (job-level `continue-on-error: true`); `check` is the required job. Promoting = removing that line (the structure guard tests/test_release_workflow_goengines.py asserts bench is advisory, so update it in the same change).
> | - Samples need no workflow edit: `workflow_dispatch` with input `seed_regression` (boolean). Seeded = every non-calibration baseline line / 2.1 via `benchci.sh seed`, applied in-job only.
> | - Each run's job summary: mode, CPU model (/proc/cpuinfo), nproc, a table `benchmark | class | current ns/op | baseline ns/op | scale | scaled ratio | verdict`, the BENCH_SCALE* lines, and the raw gate output.
> | - Ratio = cur / (base x scale) with scale recomputed from BENCH_SCALE fields 3/4 (unrounded; field 2 is %.3f and would flip values near 1.3), printed at 6 dp, never judged. `n/a` when the class scale is IMPLAUSIBLE / CALIBRATION_MISSING / UNSCALED (gate fell back to 1), or for BENCH_MISSING / BENCH_NEW rows.
> | - One local observation (moment-relative: an unpinned, loaded host on 2026-09-25, not a runner): a healthy full run scaled sha1 at 1.786 and BlobDigest's scaled ratio came out 0.52 (DispatchVersion 0.88, LsTree 0.86); the seeded run failed all three (2.49 / 2.02 / 1.86). Only a data point; runner samples are what count.
