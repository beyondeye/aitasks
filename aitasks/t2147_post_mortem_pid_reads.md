---
priority: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [test_infrastructure]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1689
followup_kind: risk_mitigation
created_at: 2026-10-26 11:38
updated_at: 2026-10-26 11:53
---

## Origin

Risk-mitigation ("after") follow-up for t2142, created at Step 8d after implementation landed.

## Risk addressed

The latent started-before-deadline race in the six other post-mortem _read_pid callers of tests/test_bounded_run.py.

> Six other `test_bounded_run.py` tests also read the pid after the group is killed, under short deadlines, and carry the same race in principle: the run at line 102 (1 s), and those at lines 117 (1 s), 146 (0.5 s KeyboardInterrupt), 175 (0.3 s), 198 (0.5 s) and 236 (CLI 0.5 s). They spawn `sh` directly, which takes milliseconds, and none has been seen to flake. Step 3's longer bound does not help them. · severity: low

## Goal

t2142 fixed `TestCrewGitTimeout.test_git_cmd_timeout_reports_124` with a retry loop. The loop runs each attempt under a deadline of 1, 2, 4, then 8 s and reads the pidfile right after the call. Any pid it finds goes into `self.leftovers` before any assertion runs. Each attempt must be a genuine timeout. The loop stops at the first attempt whose fixture demonstrably ran, and fails if even the 8 s attempt has no pid. See `tests/test_bounded_run.py` and `aiplans/archived/p2142_*.md`.

Factor that loop into a shared helper, e.g. `_run_until_started(self, call, deadlines)`. The helper must keep:

- the same per-attempt "genuine deadline" assertions (passed in as a callback, since the expected outcome differs per test: `TimeoutExpired`, `KeyboardInterrupt`, a `Hangup` exception, exit 124)
- registration of the pid before any assertion

Apply the helper to the six post-mortem `_read_pid` callers at lines ~102, 117, 146, 175, 198 and 236. They read the pid after the process group is dead, so the 30 s readiness bound cannot rescue them.

Several of these tests also assert a lower bound on elapsed time against the grace. Scale those bounds per attempt, so a retry under a longer deadline does not break them.

Verify each converted test with a slow-start pre-fix control (a fixture that sleeps before writing its pid): the old body fails, the new body passes.
