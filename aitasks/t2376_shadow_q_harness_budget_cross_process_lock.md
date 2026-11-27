---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [shadow, skills, codex]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2179
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-27 08:23
updated_at: 2026-11-27 10:36
---

## Origin

Spawned from t2368 during Step 8b review.

## Upstream defect

- `aidocs/benchmarks/shadow_q/harness.py:660` — `Budget` serializes reservations with an in-process `threading.Lock` only, so two concurrent `harness.py pilot` / main-run processes can both recover the journal and exceed the invocation cap.

## Diagnostic context

t2368 ran a small paid live check through this harness with one shared, journaled `Budget`. Plan review showed that the journal makes the cap durable across restarts of ONE process, but not across two processes that run at the same time: each calls `Budget.recover()`, reads the same `used` value, and then both `acquire()` the same next slot. An offline check granted two reservations with a cap of one.

t2368 did not change `Budget`. Its runner (`aidocs/benchmarks/shadow_q/adhoc_live_check.py`) works around it: `BatchLock` takes an exclusive, non-blocking `flock` on `runs/<batch>/budget_journal.jsonl.lock` before `recover()` and holds it for the whole run, so a second runner refuses to start (`RUN_REFUSED`). The harness's own commands that launch paid sessions (`smoke`, `pilot`, `judge`, `rejudge`, all built through `_experiment()` at `harness.py`) take no such lock.

The same review also noted that the token and cost thresholds only compare usage already accrued, so the last call can pass them. t2368's runner adds headroom in a `Budget` subclass (`HeadroomBudget.acquire`); the harness commands have none. That is a documented stop-launch threshold in `Budget`'s docstring, not a defect, and is listed here only so the fix does not conflate the two.

## Suggested fix

Move the batch lock into the harness: take it in `_experiment()` (or in `Budget.recover()` when a journal is given) and hold it for the command's lifetime, then drop the runner's own `BatchLock` in favour of it. Reuse the lock-file name the runner already uses, which `aidocs/benchmarks/shadow_q/.gitignore` already ignores. Keep the existing tests `test_second_runner_is_refused_while_the_lock_is_held` and `test_cap_and_pending_reservations_survive_a_restart` in `tests/test_shadow_q_harness.py` green, and add one that runs two harness commands against one batch.

Relevant to t2179_2 (the main run) and t2187, which are the paid users of the harness commands.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-27T08:36:37Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-27T09:17:52Z status=pass attempt=1 type=human
