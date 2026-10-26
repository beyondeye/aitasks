---
Task: t2141_observe_first_ci_runs.md
Base branch: main
Output branch: main
---

# t2141 — Observe the first CI runs of t2138's two-mode goengines wiring

## Context

t2138 made `goengines-check.yml` and the release `goengines` job two-mode, keyed on
`goengines/EXPORT.txt` (via `.github/scripts/goengines_integrity.sh mode`). Hosted-runner
semantics (`!cancelled()` with a failed `needs`, skipped-as-success, `GITHUB_OUTPUT`
plumbing) can't be run locally. This task checks them against real runs and files any
divergence as a bug task.

This task is observation only. It changes no tracked framework/code file. Its outputs are
the evidence in this plan, two throwaway-branch probe runs (the branches are deleted
afterwards), one bug task, one advisory note, and one follow-up task.

## Evidence already gathered (item 1: legacy mode on `main`)

Runs `40187609686` (t2138 commit 309e0b8c6) and `40279191111` (merge 6e315def2), both `push` on `main`:

| claim | observed | verdict |
|---|---|---|
| `mode` job prints `MODE:legacy` | yes, both runs | OK |
| `check` and `bench` run in legacy mode | both jobs ran (gated `!cancelled() && mode != 'export'`) | OK. The gate doesn't tell `legacy` from empty, so item 3 provides the positive output proof |
| `check` ran in full | gofmt, vet and preflight passed. **`go test` failed** in `internal/procsup`, so every later step was skipped: the release cross-build, the per-executable `*_SHA256SUMS.txt` loop, the structure guard, build.sh tests, benchci.sh tests, the annot corpus sync guard, and the export integrity script tests | **PARTIALLY VERIFIED, rest BLOCKED.** The job was admitted and its early steps ran. The full run can't be confirmed until the procsup defect is fixed. A dependent follow-up owns re-observing it (step 6) |
| `bench` ran, advisory | ran and failed (`BENCH_REGRESSION` / `BENCH_OVER_BUDGET`). It has failed on every hosted run since before t2138 (40161193156, 39774143760, …), and `continue-on-error` kept it from failing the run | OK as wiring. The bench itself belongs to t1878 |
| `export-integrity` reports legacy | `MODE:legacy`, `INTEGRITY_SKIPPED:legacy mode — …`, `DRIFT_SKIPPED:legacy`. Setup Python / structure guard / build.sh tests / integrity script tests: `skipped` | OK |

**Defect found (not wiring):** on the hosted runner, `go test ./internal/procsup` fails through
the hangguard leak detector: `LEAK:TestHaltStartInterleavings|<pid>:sleep` in both runs, plus
`LEAK:TestSupervisorDeathHalts|<pid>:sh` in run 2. The tests came from t1854_6 (60ca89154), which
was pushed together with t2138, so they have never passed on CI. The last green `check`
(40161193156) predates procsup. Locally (clean `internal/procsup` vs HEAD) the tests pass:
`-count=5` of both tests passed, and `-count=8` of the whole package pinned to 2 CPUs passed.
Hypothesis, unverified: a process the test kills in `t.Cleanup` (`killAfter`, a SIGKILL with no
wait), or the dead supervisor's orphaned `sh` that exits only after its daemon dies, is still
alive when `reapMarked` scans just after the test subprocess exits. Hosted-runner scheduling
widens that window.

## Steps

### 1. Isolated probe worktree (never the shared main checkout)
The main checkout has a concurrent session's uncommitted goengines/workflow edits, so all
probe work happens in a detached scratch worktree cut from `origin/main`:
```bash
S=/tmp/claude-1000/-home-ddt-Work-aitasks/91026242-0898-4a93-bf92-99f129694a08/scratchpad
git fetch origin main
git worktree add --detach "$S/probe" origin/main
```

### 2. Probe A: export mode (item 3)
- In `$S/probe`: `git switch -c probe/t2141-export-mode`.
- Generate `goengines/EXPORT.txt` (format 1) from the tree's real hashes. Use the t2138
  dry-run recipe: `format: 1`, `source: beyondeye/aitasks_go@<40 hex = current HEAD sha>`,
  `manifest: sha256:<64 hex>`, `gate: probe pass`, and one sorted `file: <sha256> <path>` line
  per tracked file under `goengines/` except `README.md`, `.gitignore` and `EXPORT.txt` (the
  record rule).
- **Seed two harmless drift fixtures** (non-Go `.txt` files at the `goengines/` root, so build,
  vet, gofmt and closure are unaffected). This exercises the "drift is a warning only" claim,
  which a clean record never reaches:
  - `goengines/t2141_probe_unlisted.txt`: tracked, **omitted** from the record → `DRIFT:unlisted`;
  - `goengines/t2141_probe_modified.txt`: listed with its hash, **then edited** after hashing →
    `DRIFT:modified`.
- Check locally in the worktree, with `GITHUB_ACTIONS=true` to mirror the runner:
  `check` prints `INTEGRITY_OK` and exits 0; `drift` prints exactly those two `DRIFT:` lines,
  two `::warning file=goengines/t2141_probe_…,title=goengines drift::…` lines, then
  `DRIFT_FOUND:2`, and **exits 0 on its own**.
- Commit (`test: t2141 export-mode probe — do not merge`) and `git push -u origin probe/t2141-export-mode`.
  The `goengines/**` path filter triggers the run, so no dispatch is needed.
- Expect, all required:
  - `mode` → `MODE:export`, and **`check` and `bench` skipped**. This is the positive proof that
    `mode=export` reached `needs.mode.outputs`.
  - `export-integrity`: `Export integrity` → `INTEGRITY_OK`.
  - **`Drift report`** prints `DRIFT:unlisted:t2141_probe_unlisted.txt`,
    `DRIFT:modified:t2141_probe_modified.txt` and `DRIFT_FOUND:2`, and the run carries the two
    `goengines drift` **warning annotations**. The step's own conclusion is `success`, and its log
    has no `##[error]Process completed` line. That shows the step itself exited 0, so it isn't
    `continue-on-error` masking a failure.
  - The export-only steps after it (Setup Python, structure guard, build.sh tests, integrity
    script tests) **run and pass**, and the `export-integrity` job concludes `success`.
  Only the two seeded files may drift: the record lists every other tracked file, so any third
  `DRIFT:` entry is a finding.

### 3. Probe B: fail-closed (item 2)
- From `origin/main` in the same worktree: `git switch -c probe/t2141-fail-closed origin/main`,
  then make `goengines/EXPORT.txt` a symlink (`ln -s README.md goengines/EXPORT.txt`). Locally,
  `mode` must exit 1 with `MODE_ERROR:EXPORT.txt is a symlink`. Commit and push.
- Expect: the `mode` job fails, and **`check` and `bench` still run** (`!cancelled()` with an
  empty output). `export-integrity` fails at its own mode step. The run is red overall,
  which is the intended outcome.

### 4. Watch and record
`gh run list --branch <b> --workflow goengines-check.yml` → `gh run view <id> --json jobs`
plus `--log` for the marker lines. Wait with Monitor or a background poll, never with
foreground sleeps.

### 5. Cleanup
`git push origin --delete probe/t2141-export-mode probe/t2141-fail-closed`,
`git worktree remove --force "$S/probe"`, and delete the local probe branches. Then
`git ls-remote origin 'refs/heads/probe/*'` must return nothing.

### 6. Hand off findings
- **Bug task** for the procsup hosted-runner leak (via `aitask_create.sh --batch`). Type bug,
  priority high because it keeps `main`'s required `check` red and hides every guard step after
  `go test`. Labels `go_engine, testing`, anchor 1852. Body: run IDs, the leak lines, the local
  repro attempts that passed, the hedged hypothesis, and the files
  (`internal/procsup/supervise_linux_test.go` `killAfter` / the two tests,
  `internal/testsupport/hangguard`).
- Any **wiring divergence** seen in probes A/B gets its own bug task against the workflow
  wiring (the task's closing instruction).
- **Note to t1878** (`./ait note 1878 --from 2141`): the hosted bench samples now available
  (run IDs, the regression/over-budget lines), tree-relative to 6e315def2. Advisory only.
- **Follow-up task A: re-observe the full legacy `check` on `main`** (the blocked part of
  item 1). Type test, `depends: [<bug task>]`, anchor 2138. A dependent task rather than a
  criterion on the bug task, because a task archives before its push, so the bug task can't
  observe its own hosted run. Checklist: on the first `Go engines check` push run on `main`
  after the fix, `go test` passes, and then each of these runs and passes:
  - the release cross-build;
  - the per-executable sums loop (`sha256sum -c` once per `*_SHA256SUMS.txt`, and at least one file);
  - the release workflow structure guard;
  - build.sh tests;
  - benchci.sh tests;
  - the annot conformance corpus sync guard;
  - the export integrity script tests.

  `mode` still prints `MODE:legacy`, and `export-integrity` still reports legacy. Any divergence
  becomes a bug task.
- **Follow-up task B: the Release `goengines` job at the next `v*` tag** (item 4). Type test,
  `depends: [<bug task>]` (until the fix, the release job's `go test` fails the same way), anchor
  2138. It copies item 4's checklist verbatim: legacy detected, preflight and go test ran,
  Export integrity reported legacy, and every `*_SHA256SUMS.txt` was uploaded.
- A and B are the recorded dispositions for the parts of items 1 and 4 that can't be observed
  this session. t2141's Final Implementation Notes mark item 1 **partially verified** and item 4
  **deferred**, naming those two tasks.

### 7. Step 9 (Post-Implementation)
No code commit. Record the evidence and probe results in the plan's Final Implementation
Notes, then archive through the normal Step 9 flow.

## Verification
- Every claim in the table above, and every probe expectation, is backed by a run ID and the
  job/step conclusions from `gh run view --json jobs`.
- Probe A's drift claim rests on its own step's exit status and log, not the job's color:
  `gh run view --json jobs` gives the `Drift report` step conclusion, and `--log` gives that
  step's lines (no `##[error]`) and the warning annotations.
- The bug task, follow-ups A and B, and the t1878 note each exist, with A and B depending on the bug task.
- After cleanup, `git ls-remote origin 'refs/heads/probe/*'` is empty and `git worktree list`
  has no probe entry.
- `git status` of the main checkout is unchanged by this task (the concurrent session's edits
  are untouched).

## Risk

### Code-health risk: low
- No tracked file changes. The probe branches live only in a scratch worktree and are
  deleted afterwards. A push of the wrong ref is the only path to `main`, and every push names
  its `probe/t2141-*` branch explicitly · severity: low · → mitigation: none (explicit
  refspecs plus the cleanup `ls-remote` check)

### Goal-achievement risk: low
- Part of item 1 (every `check` step after `go test`) and all of item 4 can't be observed
  this session. They are recorded as partially verified / deferred and not claimed here ·
  severity: low · → mitigation: none (follow-up tasks A and B are the dispositions)
- Probe A's fixture record isn't a real exporter's output. It proves the wiring, not
  aitasks_go#t21's exporter · severity: low · → mitigation: none (out of scope by design)
