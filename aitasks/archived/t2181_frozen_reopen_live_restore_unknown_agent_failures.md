---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: []
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-03 10:39
updated_at: 2026-11-03 17:34
completed_at: 2026-11-03 17:34
---

## Origin

Spawned from t2175_2 during Step 8b review.

## Upstream defect

- `tests/test_frozen_reopen_live.sh` — 47 of 148 assertions fail with
  `RESTORE_FAILED:<id>|unknown_agent` (cases c2, c3, k, …: restores into a
  target session fail before reaching the session checks).

## Diagnostic context

While running regressions for t2175_2 (sitrep harvest, drop/purge receipt
gates), `bash tests/test_frozen_reopen_live.sh` reported
`Results: 101 passed, 47 failed, 148 total`. The same command run in a clean
detached worktree of HEAD `42b547c67` (before any t2175_2 change) gave the
identical 101/47 with the same `unknown_agent` failures, so the failure is
pre-existing and unrelated to t2175_2. It was not diagnosed further.

Sample lines:

    FAIL: c2: restore into the foreign session fails closed (expected output containing 'session_not_for_root:C', got 'RESTORE_FAILED:...|unknown_agent')
    FAIL: c3: the restore succeeds (expected output containing 'RESTORED:...|', got 'RESTORE_FAILED:...|unknown_agent')
    FAIL: k: restored (expected output containing 'RESTORED:...|', got 'RESTORE_FAILED:...|unknown_agent')

Observed on host omg16, run from inside a tmux session (the suite runs there;
three sibling live suites refuse to). Whether it depends on the environment
(agent detection for the fixture's fake agent, recent agent-kind changes such as
t2109's `--agent-kind`) is the first thing to establish.

## Suggested fix

Find why `lib/agent_restore.py` classifies the fixture agents as `unknown_agent`
(probably an agent-string / agent-kind resolution change the fixture never
followed), then fix the fixture or the resolver — whichever is wrong.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T11:18:36Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-03T15:32:25Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-03T15:34:40Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:0e8a3e302286c75f

> **✅ gate:risk_evaluated** run=2026-11-03T15:34:40Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2181/risk_evaluated_2026-11-03T15:34:40Z-risk_evaluated-a1.log`
