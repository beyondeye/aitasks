---
Task: t1872_bench_host_normalization.md
Base branch: main
Output branch: main
---

# t1872 — Host-normalized benchmark gate (calibration scaling)

## Context

`goengines/bench/baseline.txt` holds ns/op recorded on one dev host. t1852_3
will run the full benchgate (`go run ./internal/tools/benchgate -baseline
bench/baseline.txt`) in CI (`goengines-check.yml`), where a slower runner
falsely fails the 2× rule and a faster one masks real regressions. Fix: record
a fixed-work calibration benchmark alongside the baselines and scale every
baseline by `current_calibration / baseline_calibration` before the 2× test.

**CI-own-baseline alternative rejected** (documented in README): GitHub-hosted
runners vary per job, so a CI-recorded baseline has the same portability
problem, and it would need committing from CI. Calibration scaling works for
both dev hosts and CI with one committed file.

## Design

- **Serial producer (review finding 1).** `go test ./...` runs package test
  binaries in parallel (`-p` defaults to GOMAXPROCS), benchmarks included, so
  the calibration package and the measured packages can overlap and distort
  each other differently. The default producer becomes
  `go test -p 1 -run ^$ -bench . -count 1 ./...`, and the baseline is
  re-recorded with it (`-update` uses the same default producer). The README
  documents that a custom producer for the gate or `-update` must keep `-p 1`.
- **No baseline format change.** The calibration is an ordinary baseline line
  under a reserved name: `internal/benchgate.BenchmarkCalibrate <ns/op>`.
  Constant `benchgate.Calibration = "internal/benchgate.BenchmarkCalibrate"`.
- `BenchmarkCalibrate` lives in `internal/benchgate/calibrate_test.go`
  (test-only, never shipped): CPU-bound, allocation-free, no I/O — a fixed
  xorshift/mix loop (~1M iterations per op, result into a package-level sink so
  it is not optimized away).
- **Compare** (`internal/benchgate/benchgate.go`), signature unchanged:
  1. existing BENCH_INVALID checks; BENCH_EMPTY now means "no measurement
     other than the calibration".
  2. Calibration resolution, emitted as the **first** result line:
     - both sides present → `s = cur/base`;
       - `MinScale(0.25) ≤ s ≤ MaxScale(4)` → `BENCH_SCALE:<s %.3f>|<cur>|<base>`, apply;
       - outside → `BENCH_SCALE_IMPLAUSIBLE:<s>|<cur>|<base>`, **Fail** (both
         modes), per-bench lines computed unscaled (informational).
     - either side absent → Full: `BENCH_CALIBRATION_MISSING:baseline|current`,
       **Fail**; Partial: `BENCH_UNSCALED:baseline|current`, no fail. Unscaled.
  3. Calibration entry excluded from per-benchmark lines (never OK/NEW/MISSING).
  4. `ratio = ns / (e.NsOp * s)`; the `BENCH_REGRESSION:<n>|<cur>|<base>|<ratio>`
     / `BENCH_OK:<n>|<cur>|<base>` shapes are unchanged — `<base>` stays the
     recorded value, `<ratio>` is the scaled ratio. `budget=` is **never** scaled.
- **Runner `-update` guard (review finding 3).** Before writing, `-update`
  refuses (exit 1, file byte-identical) when the run has no calibration
  measurement (`BENCH_CALIBRATION_MISSING:current`) **or** no non-calibration
  measurement (`BENCH_EMPTY:`) — a calibration-only run would otherwise make
  `Rewrite` drop every real baseline.
- **CI rollout guard (review finding 2).** This task cannot edit the (not yet
  existing) CI workflow, so the guard is split:
  - *Now, on real hardware:* a slowed-host experiment on this machine (see
    Verification) checks that the scale tracks every current benchmark —
    including the fork-bound `BenchmarkLsTree` — before anything ships.
  - *For CI:* an `ait note` to t1852_3 (sent at Step 8e) stating that the bench
    step in `goengines-check.yml` must start **advisory**
    (`continue-on-error: true`, not a required check) and only become blocking
    once the validation follow-up (below) meets its promotion criteria. The
    README's host-normalization paragraph states the same rollout rule and
    criteria, so it does not depend on the note alone.
  - *Promotion criteria (review finding 4)* — samples must be **separate
    runner instances**, not repeats inside one job:
    - ≥5 healthy samples, each a **fresh workflow run** (separate job ⇒ fresh
      hosted-runner VM; `workflow_dispatch` re-runs, spread over ≥2 days),
      plus ≥2 fresh runs with a seeded regression (a temp baseline with one
      benchmark divided by 3, applied inside the job only).
    - Each run records to its job summary: runner CPU model
      (`/proc/cpuinfo` model name), `nproc`, the `BENCH_SCALE:` line, and
      every per-benchmark line with its scaled ratio.
    - **Promote to required** only if: every healthy run exits 0 with every
      scaled ratio ≤ 1.5 (headroom under 2.0) and every scale inside
      [MinScale, MaxScale]; every seeded run reports `BENCH_REGRESSION` for the
      seeded benchmark.
    - **Stays advisory** if any healthy run fails, any scaled ratio exceeds
      1.5, any scale is implausible, or any seeded regression is missed; the
      follow-up records which benchmark/CPU model caused it and the fix
      (recalibration, per-benchmark exemption, or a different proxy) becomes
      a new task.
    - If every sample landed on one CPU model, promotion is allowed but the
      README records the single-model sample, and the rollout rule says a
      first unexplained bench failure on a new CPU model demotes the step to
      advisory again.

## Implementation steps

1. `internal/benchgate/benchgate.go`: add `Calibration`, `MinScale`,
   `MaxScale`; rework `Compare` as above (helper returning scale, protocol
   line, fail); update the package doc (baseline format + calibration rule).
2. `internal/benchgate/calibrate_test.go`: `BenchmarkCalibrate`.
3. `internal/benchgate/benchgate_test.go`: add calibration lines to the existing
   fixtures (`TestCompareFactor`, `TestCompareBudget`,
   `TestCompareMissingNewEmpty`, `TestSlowedFixtureFailsTwoX`) and adjust the
   `Lines[0]` expectations; new tests:
   - `TestCalibrationScalesSlowHost`: cal 2×, every bench 2× → pass, `BENCH_SCALE:2.000|…`.
   - `TestCalibrationCatchesRegression`: cal 1×, bench 2.5× → `BENCH_REGRESSION`;
     also a 2× slower host with a bench 5× slower (2.5× scaled) → fail.
   - `TestCalibrationFastHostUnmasks`: cal 0.5×, bench 1.2× (2.4× scaled) → fail.
   - `TestCalibrationMissing`: absent in baseline / in current → Full fails with
     `BENCH_CALIBRATION_MISSING:<side>`; Partial passes with `BENCH_UNSCALED:<side>`.
   - `TestCalibrationImplausible`: s=5 and s=0.2 → `BENCH_SCALE_IMPLAUSIBLE`, fail in both modes.
   - `TestBudgetNotScaled`: a fast host (cal 0.5×) with a bench within 2× scaled
     but over budget → `BENCH_OVER_BUDGET`; a slow host (cal 2×) with a bench over
     budget but fine scaled → still `BENCH_OVER_BUDGET`.
   - `TestEmptyExceptCalibration`: cur = {calibration} only → `BENCH_EMPTY:`.
   - `TestCalibrateIsCPUBound` (skipped in -short): `testing.Benchmark(BenchmarkCalibrate)`
     reports 0 allocs/op and a finite positive ns/op.
4. `internal/tools/benchgate/main.go`: `-p 1` in `defaultProducer` (and the doc
   comment); the `-update` guards above.
   `internal/tools/benchgate/main_test.go`: add the calibration to `benchOut`
   / `fullBaseline` (fixture pkg `internal/benchgate`), adjust counts;
   `TestGatePasses` asserts that `BENCH_SCALE:` follows `BENCH_MODE:`; new
   `TestUpdateRefusesWithoutCalibration` and `TestUpdateRefusesCalibrationOnly`
   (each: exit 1, right line, file byte-identical); `TestDefaultProducerSerial`
   pins `-p 1` in `defaultProducer`.
5. `goengines/bench/baseline.txt`: re-record with
   `go run ./internal/tools/benchgate -baseline bench/baseline.txt -update`
   (serial producer; adds the calibration line; header comment mentions scaling
   and `-p 1`).
6. `goengines/README.md`: extend the `baseline file` and `benchgate` rows of
   `## Interfaces` (reserved calibration name; `BENCH_SCALE:`
   `BENCH_SCALE_IMPLAUSIBLE:` `BENCH_CALIBRATION_MISSING:` `BENCH_UNSCALED:`;
   budgets unscaled; the serial default producer; `-update` refusals; pinned by
   the new tests); add a "Host normalization" paragraph under *Build, test,
   bench*: why calibration beats a CI-recorded baseline, the `-p 1`
   requirement, the CPU-proxy limitation, the slowed-host result from step 7,
   and the CI rollout rule (advisory until validated on the runner).
7. Slowed-host validation (real hardware, results recorded in the plan's Final
   Implementation Notes and summarized in the README): build the benchgate
   binary, then
   - 3× plain `benchgate -baseline bench/baseline.txt` → all pass, scale ≈ 1;
   - 3× `taskset -c 3 benchgate …` while `taskset -c 3 sh -c 'while :; do :; done'`
     hogs the same core (≈2× slower host; git children inherit the affinity) →
     expect scale ≈ 1.5–2.5 and pass. If `BenchmarkLsTree` fails here, the
     proxy does not track fork-bound work: stop and report it before
     committing rather than loosening the rule;
   - a seeded regression on the slowed host (temp baseline copy with
     `BenchmarkBlobDigest` divided by 3) → `BENCH_REGRESSION`, exit 1.
   The hog is killed in a trap; nothing in the repository changes.

## Verification

```bash
cd goengines
test -z "$(gofmt -l .)" && go vet ./... && go test ./...
go run ./internal/tools/benchgate -baseline bench/baseline.txt   # exit 0, BENCH_SCALE ≈ 1
```
Plus the step-7 slowed-host runs and a temp-copy negative control (calibration
baseline ×4.5 → `BENCH_SCALE_IMPLAUSIBLE`, exit 1).

## Step 9 reference
Current-branch (fast profile): commit code + plan, archive via
`aitask_archive.sh 1872`.

## Risk

### Code-health risk: low
- `Compare`'s semantics change (the full gate now requires the calibration line) and existing fixtures are rewritten; bounded to `internal/benchgate` + its runner, pinned by tests · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Calibration is a single CPU-bound proxy; fork/IO-dominated benchmarks (`LsTree`) and noisy shared CI runners may not track it, so the scaled 2× rule could still flake or mask on real CI hardware. Partly de-risked here by the serial producer and the step-7 slowed-host run; the CI side stays unverifiable until t1852_3's workflow exists, which the advisory-until-validated rollout rule covers · severity: medium · → mitigation: bench_calibration_ci_validation

### Planned mitigations
- timing: after | name: bench_calibration_ci_validation | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: high | addresses: calibration proxy may not track CI hardware (goal-achievement) | desc: Once goengines-check.yml (t1852_3) lands with the bench step advisory, collect ≥5 healthy + ≥2 seeded-regression samples as separate fresh workflow runs (fresh runner VMs over ≥2 days), recording CPU model, nproc, BENCH_SCALE and every per-bench scaled ratio per run; promote the step to required only under the plan's promotion criteria (all healthy pass with ratios ≤1.5, scales plausible, every seeded regression caught), otherwise keep it advisory and file the fix; depends on t1852_3
