---
Task: t2149_observe_full_goengines_check_on_main.md
Base branch: main
Output branch: main
---

# Plan: t2149 — observe the full `Go engines check` on `main`

## Context

t2141 could only partly verify t2138's two-mode goengines CI wiring on `main`:
`check` stopped at `go test` on the procsup hosted-runner leak (t2148), so every
later step was skipped and never observed. t2148 has landed (`a06e4f5d8`, on
`origin/main`). This task observes the first `main` **push** run that contains
the fix and records step-level conclusions. If the run diverges from the static
guard's model (`tests/test_release_workflow_goengines.py`), that becomes a bug
task against the workflow wiring.

This is an observation task. It needs **no code change**. The only deliverable
is the evidence record in this plan's Final Implementation Notes, plus a bug
task if there is a divergence.

## Evidence already gathered (read-only, during planning)

**Qualifying run.** `gh run list --workflow goengines-check.yml --branch main`:
the first push run whose head contains `a06e4f5d8` is **40338582752**
(event `push`, branch `main`, head `8d8f9008f8ff`, "ait: Merge origin/main into
main", 2026-10-26T14:19Z, run conclusion `success`). The run before it,
40279191111 (`6e315def23`), lacks the fix (`git merge-base --is-ancestor`).

Step conclusions (`gh run view 40338582752 --json jobs`) and log markers (`--log`):

| Item | Observed | Verdict |
|---|---|---|
| `mode` prints `MODE:legacy` | `MODE:legacy` in the mode job; job success | ✅ |
| `check` / `go test` | success; every package `ok`, incl. `internal/procsup 7.462s` | ✅ |
| Release cross-build + sums loop | success; builds 4 targets; `sums=(*_SHA256SUMS.txt)` finds `ait-testmap_0.40.0_SHA256SUMS.txt` (≥1 exists); `sha256sum -c` → 4× `: OK` | ✅ |
| Release workflow structure guard | success | ✅ |
| build.sh tests | success | ✅ |
| benchci.sh tests | success | ✅ |
| annot conformance corpus sync guard | success | ✅ |
| export integrity script tests | success | ✅ |
| `export-integrity`: `INTEGRITY_SKIPPED:legacy mode …` | `INTEGRITY_SKIPPED:legacy mode — goengines/ is developed here; …`; step success | ✅ |
| `export-integrity`: `DRIFT_SKIPPED:legacy` | present; Drift report step success | ✅ |
| export-only steps skipped | Setup Python, Release workflow structure guard, build.sh tests, export integrity script tests → all `skipped` | ✅ |
| `bench` runs, advisory | runs; "Benchmark gate" `failure` (BENCH_REGRESSION `cmd/ait-testmap.BenchmarkDispatchVersion` 1.70×; BENCH_OVER_BUDGET `testmap/deps.BenchmarkScanCold`/`ScanWarm`); job red, **run conclusion `success`** → job-level `continue-on-error` holds | ✅ (verdict is t1878's) |

**Static-guard comparison.** Each property the guard pins matches the observed
run: the mode job and its mode step are not skippable. `check`/`bench` run
unless the mode is positively `export`. `export-integrity` always runs, its
integrity check is blocking and its drift report advisory, and its three guard
steps (plus Setup Python) are export-only. Only `bench` is advisory. The sums
loop verifies every sums file. The guard itself ran green inside this run at
`8d8f9008f`, so the workflow and the model agreed at that commit.
**No divergence → no bug task.**

**Supplementary (not the acceptance run).** The workflow gained a
`dashcheck.sh tests` step after this run (`3c4e20069`, t2154), so 40338582752
predates it. The latest `main` push run, **40502092574** (`444391966b`), also
succeeds. There `dashcheck.sh tests` runs and passes, the full step list matches
the above, and `bench` fails advisorily again. This step is outside the task's
checklist; it is recorded only as context.

## Implementation steps

1. Re-confirm that run 40338582752's data has not changed (one `gh run view
   40338582752 --json jobs,conclusion` call; the conclusions must match the table).
2. Write the **Final Implementation Notes** into the plan file. They must hold
   the run IDs, head SHA, the step-level table above, the static-guard
   comparison, the "no divergence → no bug task" disposition, the
   supplementary-run note, and the reproduction commands (below), verbatim.
   The notes are the durable closure evidence.
3. No source files change, so Step 8 has no code commit. Commit only the plan
   file (scoped, `./.aitask-scripts/aitask_task_commit.sh`). Then go to Step 9
   (archival) per the shared workflow.

Reproduction commands (go verbatim into the notes):
```bash
gh run list --workflow goengines-check.yml --branch main --limit 15 \
  --json databaseId,event,headSha,conclusion,createdAt
git merge-base --is-ancestor a06e4f5d8 8d8f9008f8   # fix included
git merge-base --is-ancestor a06e4f5d8 6e315def23   # earlier run: not included (exit 1)
gh run view 40338582752 --json jobs,conclusion
gh run view 40338582752 --log | grep -E 'MODE:|INTEGRITY_|DRIFT_|SHA256SUMS|: OK$|BENCH_'
```

## Verification

- The table matches `gh run view 40338582752 --json jobs` conclusions exactly.
- The log grep shows `MODE:legacy`, `INTEGRITY_SKIPPED:legacy mode`,
  `DRIFT_SKIPPED:legacy`, one `SUMS:` file and four `: OK` lines.
- Run conclusion `success` despite `bench` failure = advisory confirmed.

## Step 9

Post-implementation per the shared workflow: no merge (current-branch mode on
`main`). Run the gate (`risk_evaluated`), then archive t2149 and its plan.

## Risk

### Code-health risk: low
None identified. (No source, workflow or test file changes.)

### Goal-achievement risk: low
None identified. Every checklist item is directly observed on a qualifying
`main` push run, and the static-guard comparison is per-property against the
guard's assertions.

## Final Implementation Notes

- **Actual work done:** Observation only; no source, workflow or test file changed.
  The acceptance run is **Go engines check run 40338582752**: event `push`, branch
  `main`, head `8d8f9008f8ffd35a6d1f9a55c9dfafebbe0519f3` ("ait: Merge origin/main
  into main"), started 2026-10-26T14:19:29Z, run conclusion `success`. It is the
  first `main` push run whose head contains t2148's fix `a06e4f5d8`. The previous
  push run, 40279191111 (`6e315def23`), does not contain it. On 2026-10-29 its
  step conclusions were re-read and matched the planning-time table exactly:
  - `mode` (success): Detect goengines mode=success; log `MODE:legacy`.
  - `check` (success): gofmt, go vet, Hang-guard preflight, Setup Python,
    Install pinned pytest, **go test** (every package `ok`, incl.
    `internal/procsup 7.462s`), **Release cross-build** (4 targets built;
    `sums=(*_SHA256SUMS.txt)` matched `ait-testmap_0.40.0_SHA256SUMS.txt`, so at
    least one sums file exists; `sha256sum -c` printed 4× `: OK` for
    darwin_amd64/darwin_arm64/linux_amd64/linux_arm64), **Release workflow
    structure guard**, **build.sh tests**, **benchci.sh tests**, **annot
    conformance corpus sync guard**, **export integrity script tests**: all
    `success`.
  - `export-integrity` (success): Export integrity=success, printing
    `INTEGRITY_SKIPPED:legacy mode — goengines/ is developed here; gofmt, vet,
    the preflight, go test and the bench are its validation`; Drift report=success,
    printing `DRIFT_SKIPPED:legacy`. The export-only steps Setup Python, Release
    workflow structure guard, build.sh tests and export integrity script tests
    were all `skipped`.
  - `bench` (job `failure`, advisory): it ran, and Benchmark gate=failure with
    `BENCH_MODE:full`, `BENCH_REGRESSION:cmd/ait-testmap.BenchmarkDispatchVersion|7661|2793|1.70`,
    `BENCH_OVER_BUDGET:internal/testmap/deps.BenchmarkScanCold|2052975439|1.5s` and
    `BENCH_OVER_BUDGET:internal/testmap/deps.BenchmarkScanWarm|218511183|150ms`.
    The other benchmarks were `BENCH_OK`. The run conclusion stayed `success`, so
    the job-level `continue-on-error` holds. The bench verdict belongs to t1878.
- **Static-guard comparison (`tests/test_release_workflow_goengines.py`):** No
  divergence. The mode job and its mode step are not skippable. `check` and
  `bench` both ran (legacy, so `needs.mode.outputs.mode != 'export'`).
  `export-integrity` always runs: its integrity check is blocking and passed, and
  its drift report is advisory and passed. Its guard steps carrying
  `EXPORT_STEP_IF` (and Setup Python) were skipped. Only `bench` is advisory: it
  went red and the run stayed green. The sums loop verified every sums file.
  The structure guard itself ran green inside this run at `8d8f9008f`, so the
  workflow and the model agreed at the observed commit. **No bug task created.**
- **Deviations from plan:** None.
- **Issues encountered:** None. The bench failure is expected and owned by t1878
  (the t2148 note predicted it). On this run `testmap/annot` and
  `testmap/modules` were `BENCH_OK`, while the t2148 note's branch runs had them
  failing. The set of failing benchmarks varies from run to run; that is
  t1878's concern.
- **Key decisions:**
  - Only the first qualifying push run on `main` counts, per the task. Branch
    and workflow_dispatch runs (the t2148 note's 40334103309 / 40334114895 /
    40334119129) were not used as evidence.
  - Supplementary context, not acceptance: `dashcheck.sh tests` was added to
    `check` later (`3c4e20069`, t2154), so it is absent from 40338582752. The
    latest `main` push run, **40502092574** (`444391966b`, success), runs it
    green, with the same step list otherwise and the same advisory bench failure.
- **Upstream defects identified:** None
- **Reproduction commands:**
  ```bash
  gh run list --workflow goengines-check.yml --branch main --limit 15 \
    --json databaseId,event,headSha,conclusion,createdAt
  git merge-base --is-ancestor a06e4f5d8 8d8f9008f8   # fix included (exit 0)
  git merge-base --is-ancestor a06e4f5d8 6e315def23   # earlier run: not included (exit 1)
  gh run view 40338582752 --json jobs,conclusion
  gh run view 40338582752 --log | grep -E 'MODE:|INTEGRITY_|DRIFT_|SHA256SUMS|: OK$|BENCH_'
  ```
