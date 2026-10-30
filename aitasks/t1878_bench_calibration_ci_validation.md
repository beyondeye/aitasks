---
priority: medium
effort: low
depends: [t1852_3]
issue_type: test
status: Postponed
labels: [testmap, go_engine, testing, test_infrastructure]
gates: [risk_evaluated]
anchor: 1852
followup_kind: risk_mitigation
created_at: 2026-09-24 15:44
updated_at: 2026-10-30 12:10
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

> **✉ note:t15** id=2026-10-25T08:55:31Z.5aac6cd350fa751fdd5da156 from=aitasks_go#t15 at=2026-10-25T08:55:31Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).
> | 
> | PREMISE CHANGE SPECIFIC TO THIS TASK
> | After the cutover, the bench gate (bench/baseline.txt, internal/tools/benchgate,
> | the calibration classes) runs privately in aitasks_go at each exported commit.
> | Public CI in export mode (aitasks t2138) skips go test, preflight and bench.
> | Validating the gate on hosted runners in public goengines-check.yml is
> | therefore only meaningful before the cutover. Reconsider this task's scope
> | before investing in it: it may belong in aitasks_go (re-homed by t22),
> | validated against whatever CI the private repo uses.

> **✉ note:t2141** id=2026-10-26T09:41:40Z.f4c5bd35da11207611727195 from=t2141 from_verified=yes at=2026-10-26T09:41:40Z base=7f49dbd62e8c9ab5ae05de2935184d3bf72256d7 base_branch=main dirty=no host=omg16
>
> | Advisory context from t2141 (observing goengines-check after t2138). It doesn't change this task's scope.
> | 
> | Hosted `bench` samples now exist that this task's sampling plan can count. Each is a separate fresh run, all healthy mode (no seed), all advisory (`continue-on-error` kept each run's result unaffected):
> | 
> | - 40187609686 (309e0b8c6), main push: REGRESSION DispatchVersion 2.92, annot.BenchmarkScan 1.81; OVER_BUDGET deps.ScanCold, deps.ScanWarm; SCALE cpu 1.434 / sha1 1.257 / spawn 1.847
> | - 40279191111 (6e315def2), main push: REGRESSION DispatchVersion 2.89, annot.BenchmarkScan 1.94; OVER_BUDGET deps.ScanCold, deps.ScanWarm, modules.CheckModulesDrift; SCALE cpu 1.636 / sha1 1.434 / spawn 2.278
> | - 40301069108 (2b8b9133a, a throwaway branch whose goengines tree is identical to 6e315def2): bench failed the same way (raw lines not extracted)
> | 
> | Earlier hosted runs (40161193156, 39774143760, 39578979896) also show `bench: failure`. On this evidence, no healthy hosted sample has passed the gate yet. The CPU model and nproc are only in each run's job summary; I didn't read them.
> | 
> | Unrelated but relevant to sampling: until t2148 (procsup hosted-runner leak) lands, the required `check` job in the same workflow is red too.

> **✉ note:t2149** id=2026-10-29T19:29:12Z.5c73bfbd013d93c9d800181e from=t2149 from_verified=yes at=2026-10-29T19:29:12Z base=b5e76cf6b592fcef21415535dc8f43848addb87e base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2149 (observing the first full Go engines check on main after t2148). This is a pair of samples, not an instruction, and it does not change t1878's scope.
> | 
> | Two healthy (unseeded) `main` push runs of goengines-check.yml on GitHub-hosted runners, with bench in `BENCH_MODE:full`. In both, the advisory bench job failed and the run concluded `success`:
> | 
> | - Run 40338582752 (head 8d8f9008f, 2026-10-26T14:19Z):
> |   scales cpu 1.616, sha1 1.446, spawn 1.733.
> |   BENCH_REGRESSION cmd/ait-testmap.BenchmarkDispatchVersion 1.70;
> |   BENCH_OVER_BUDGET testmap/deps.BenchmarkScanCold 2.05s/1.5s and ScanWarm 219ms/150ms;
> |   BENCH_OK for BlobDigest, LsTree, annot.BenchmarkScan, modules.BenchmarkCheckModulesDrift, registry Check/Scan.
> | - Run 40502092574 (head 444391966, 2026-10-27T12:13Z):
> |   scales cpu 1.633, sha1 1.411, spawn 2.358.
> |   BENCH_REGRESSION DispatchVersion 2.78 and annot.BenchmarkScan 1.90;
> |   BENCH_OVER_BUDGET deps ScanCold 2.14s/1.5s, ScanWarm 238ms/150ms, modules.BenchmarkCheckModulesDrift 329ms/300ms;
> |   BENCH_OK for BlobDigest, LsTree, registry Check/Scan.
> | 
> | The ratios above are the gate's own printed field 4, not recomputed. The failing set differs between the two runs: annot and modules pass in one and fail in the other. DispatchVersion and the deps budgets fail in both. CPU model and nproc for each run are in its job summary; t2149 did not read them.
> | 
> | Source: `gh run view <id> --log | grep BENCH_`. Recorded in t2149's archived plan.

> **✉ note:t22_3** id=2026-10-29T22:23:18Z.38bad52333ca079b3fe8c556 from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:18Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.

> **✉ note:t22_4** id=2026-10-30T10:11:49Z.edb6d197c5317ae73b890274 from=aitasks_go#t22_4 from_verified=yes at=2026-10-30T10:11:49Z base=cfd671f97ef9fd0159d4d67ea4261a612790a2b1 base_branch=main dirty=no host=omg16
>
> | Re-homed: the engine work of this task moved to aitasks_go#t66
> | (beyondeye/aitasks_go). This task is Postponed as a pointer and must not be
> | picked. History of its completed siblings: aitasks_go
> | aidocs/aitasks_go/testmap_history/.
