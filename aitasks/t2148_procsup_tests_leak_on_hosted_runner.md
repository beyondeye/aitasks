---
priority: high
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [go_engine, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: daelyasy@hotmail.com
anchor: 1852
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 11:38
updated_at: 2026-10-26 15:26
---

## Origin

Found by t2141 (observing the first hosted CI runs of t2138's two-mode goengines
wiring). The wiring itself is not at fault. The defect is in t1854_6's procsup tests
(commit 60ca89154), which landed in the same push as t2138 and have never passed on a
hosted runner.

## Symptom

`Go engines check` → `check` job → `go test ./...` fails in
`internal/procsup` on GitHub-hosted `ubuntu-latest` (Ubuntu 24.04, 4 vCPU). The
hangguard leak detector reports a marked process still alive after the test's
isolated subprocess exited:

- run 40187609686 (309e0b8c6):
  `supervise_linux_test.go:311: LEAK:TestHaltStartInterleavings|5080:sleep`
- run 40279191111 (6e315def2):
  `supervise_linux_test.go:250: LEAK:TestSupervisorDeathHalts|5383:sh` and
  `supervise_linux_test.go:311: LEAK:TestHaltStartInterleavings|5484:sleep`
- run 40301069108 (t2141's throwaway fail-closed probe, otherwise identical to 6e315def2):
  `supervise_linux_test.go:311: LEAK:TestHaltStartInterleavings|5467:sleep`

TestHaltStartInterleavings has failed on 3 of 3 hosted runs so far.

Message: "processes carrying the test's marker were alive after its subprocess
exited (killed)". The last green `check` (40161193156, v0.40.0) predates procsup.

**Impact:** `main`'s required `check` job is red. Because `go test` fails, every
later step is skipped: the release cross-build, the per-executable
`*_SHA256SUMS.txt` loop, the structure guard, build.sh/benchci.sh tests, the annot
corpus sync guard, and the export integrity script tests. So no step after go test
gets any CI coverage at all. The release workflow's `goengines` job runs the same
`go test` and should fail the same way at the next `v*` tag.

## Local repro attempts (all passed — not reproduced)

On omg16, with `internal/procsup` clean vs HEAD 6e315def2:
- `go test -count=5 -run 'TestHaltStartInterleavings|TestSupervisorDeathHalts' ./internal/procsup/`: ok
- `taskset -c 0,1 go test -count=8 ./internal/procsup/`: ok (53s)

## Hypothesis (unverified)

These tests kill processes in `t.Cleanup` (`killAfter`, `supervise_linux_test.go:45`,
a bare `SIGKILL` with no wait). In TestSupervisorDeathHalts, the dead supervisor's
orphaned `sh -c "setsid sleep 300 & …; wait"` exits only once its daemon dies. Either
of these may still be alive (not yet a zombie) when hangguard's `reapMarked` scans
right after the subprocess exits. Hosted-runner scheduling widens that window. Look
first at: whether the tests should wait for the death of every marked process they
own before returning, and whether `reapMarked` needs a bounded grace for processes
already sent SIGKILL. That grace would have to keep the detector able to fail a real
leak; see `internal/testsupport/hangguard/reap_linux.go`.

Do not "fix" this by skipping the tests on CI or loosening the detector without a
negative control proving that a real leak still fails.

## Acceptance

- Both tests pass on the hosted runner. Prove it with ≥3 green `check` runs; a
  `workflow_dispatch` on a branch is fine.
- The root cause is identified and stated, not only the symptom suppressed.
- A real leak is still reported (negative control).

Re-observing the full legacy `check` on `main` after this lands is owned by a
dependent follow-up created by t2141 (a task archives before its push, so this task
can't observe its own main-branch run).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-26T13:26:23Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-26T13:45:30Z status=pass attempt=1 type=human
