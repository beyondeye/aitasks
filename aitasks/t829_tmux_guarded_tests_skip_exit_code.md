---
priority: medium
effort: medium
depends: [790]
issue_type: test
status: Ready
labels: [testing, test_infrastructure, tmux]
created_at: 2026-05-25 18:04
updated_at: 2026-05-25 18:05
boardidx: 160
---

## Context

Surfaced by t790 triage of pre-existing test failures
(`aiplans/p790_triage_preexisting_test_failures_post_t777.md`, Bucket C).

Eight tmux / multi-session / TUI-switcher tests refuse to run from inside a
tmux session (intended safety guard, added after a real incident where a
failing tmux test killed the user's surrounding tmux server). Each emits:

```
ERROR: test_*.sh cannot run from inside a tmux session.
This test creates and tears down its own tmux server. Past failures have
cascaded into the surrounding user server, killing every pane inside it ...
```

and exits non-zero. The whole-suite regression driver in
`aiplans/archived/p734_test_scaffold_helper_for_fake_aitask_repo.md` §3
buckets any non-zero exit as FAIL, so the guard pollutes the failure count
whenever the suite is run from inside tmux (essentially always for the
maintainer).

Affected tests:

- `tests/test_tmux_control.sh`
- `tests/test_tmux_control_resilience.sh`
- `tests/test_tmux_exact_session_targeting.sh`
- `tests/test_tmux_run_parity.sh`
- `tests/test_kill_agent_pane_smart.sh`
- `tests/test_multi_session_monitor.sh`
- `tests/test_multi_session_primitives.sh`
- `tests/test_tui_switcher_multi_session.sh`

## Approach

Three options considered in p790's plan; preferred path is **1+2 combined**:

1. Have each guarded test exit with a distinct skip exit code — use **77**
   (GNU autotools convention). The 8 tests currently exit 2 from the guard
   branch.
2. Pull the guard into a shared helper (e.g. a function in
   `tests/lib/test_scaffold.sh`) so the SKIP-exit semantics live in one
   place and a future ninth tmux test reuses the same machinery.
3. Update the regression-loop snippet (CLAUDE.md "Testing" section, p734
   §3, and any successor docs) to bucket exit-77 as SKIP and report
   `PASS / FAIL / SKIP` counts.

Reject the documentation-only path (option 3 alone) — it leaves the
headline count wrong by default.

## Out of scope

- Making the tmux tests runnable from inside tmux (the guard exists for a
  reason — past data-loss incident).
- Other Bucket A / B failures from t790.
- Adding a CI path that runs the 8 tests outside tmux (could be a future
  follow-up).

## Verification

- Run the 8 listed tests from inside tmux; each exits 77 with the existing
  human-readable guard message.
- Run the whole-suite regression loop (updated to bucket 77 as SKIP) from
  inside tmux; output shows `PASS: X  FAIL: 0  SKIP: 8` with the 8 tests
  listed under SKIP, not FAIL.
- Run the 8 tests from a fresh non-tmux terminal; they execute their real
  bodies (pass or fail on real assertions, not on the guard).
- Skip helper (if extracted) has a docstring referencing this task.
