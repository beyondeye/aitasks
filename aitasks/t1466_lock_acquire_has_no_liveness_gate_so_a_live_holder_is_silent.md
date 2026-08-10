---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [crash_recovery, aitask_pick, bash_scripts, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-08-09 13:01
updated_at: 2026-08-10 16:29
---

A task lock held by a **live** agent session is handed to a second session
without any liveness check, so two agents on the same machine can concurrently
own one task. Observed live: two `/aitask-pick` sessions both owned t1427_5 and
duplicated its verification work.

## What the acquire path does today

`.aitask-scripts/aitask_lock.sh` `lock_task()`, around line 181:

```bash
# Idempotent: if same email owns the lock, refresh it
if [[ "$locked_by" == "$email" ]]; then
    debug "Lock already held by same user, refreshing"
    ...
```

The branch is entered on an email match alone. It emits `LOCK_RECLAIM:` when the
prior host differs and always emits `PRIOR_LOCK:`, then falls through and takes
the lock. The PID-anchor fields it just read are used **only** to decorate the
signal that `aitask_pick_own.sh` emits afterwards — they never gate the
acquisition. The `LOCK_HOLDER:` refusal in the `else` branch applies only when
the lock is held by a *different* email.

Consequence: for the ordinary single-user, multi-session setup this project
encourages (several agent panes in one checkout), the mutex does not exclude
anything. Whoever claims last wins, silently.

## Evidence

Using the paired-repo fixture from `tests/test_crash_recovery_pid_anchor.sh`,
with a lock planted for the same email carrying a **genuinely live** holder — a
running `sleep 300`, with its true `/proc/<pid>/stat` field-22 starttime, and
`kill -0` confirming ALIVE at plant time:

```
signals: OWNED:1 RECLAIM_STATUS:Implementing|alice@test.com
RESULT: lock ACQUIRED from a provably-live holder (no liveness gate on acquire)
```

The correct `RECLAIM_STATUS` (rather than `RECLAIM_CRASH`) confirms the liveness
helper evaluated the holder as alive — and the acquisition proceeded regardless.

## Relationship to t1465

This is one half of an observed double-claim; **t1465** is the other. There the
anchor is written as the claim script's own PID, so `RECLAIM_CRASH` fires on
every same-host re-pick and the user is told a live session "appears to have
crashed".

The two compound: acquisition is ungated (this task), so the human confirmation
prompt in `crash-recovery.md` is the only real gate — and t1465 poisons that
prompt with a false crash story that makes "reclaim and continue" the obvious
answer. Fixing t1465 alone makes the prompt truthful but still leaves the lock
takeable from a live session; fixing this alone removes the double-claim but
leaves the misleading verdict. Whichever lands second should re-check the
other's assumptions about where the liveness decision is made.

## Design question to settle in the plan

The idempotent same-email refresh is **intentional** — it is what makes a normal
resume, a crash recovery, and a legitimate multi-PC handoff work, and it must
keep working. The question is not "remove it" but "what distinguishes a resume
from a collision":

- Should a live, same-host, same-email holder be refused outright, or surfaced
  through a distinct signal (e.g. `LOCK_LIVE_HOLDER:`) that routes to a
  different prompt than crash recovery — one whose default is *not* to take the
  lock?
- What is the right identity for "a different session by the same user"? Email
  is too coarse and hostname does not separate concurrent panes. The anchor from
  t1465, once it names a process that actually tracks the session, is the
  natural discriminator.
- How does this interact with `--force`, with `aitask_lock.sh --cleanup` stale
  reclamation, and with the `RECLAIM_STATUS` anomaly path?
- Fail-safe direction: an *unverifiable* holder ("cannot tell whether that PID
  is alive") must be its own state, distinct from both "alive" and "dead", and
  must not default to silently taking the lock.

## Acceptance criteria

- A same-host, same-email lock whose holder is verifiably **alive** no longer
  results in a silent takeover; the outcome is either a refusal or a distinct
  confirmation path that does not present the situation as a crash.
- Normal resume (holder genuinely gone), documented multi-PC reclaim, and
  `--force` all still work.
- A test that acquires a lock, keeps the holder alive, and asserts a second
  same-email acquire does not silently succeed.
- A test pinning the unverifiable-holder case to its own outcome.
- `aidocs/` / the lock documentation states the exclusion guarantee the lock
  actually provides, since "same user, one agent" is not the project's normal
  mode.

## Sources

`.aitask-scripts/aitask_lock.sh` (`lock_task`, the same-email refresh branch and
the `LOCK_HOLDER:` refusal), `.aitask-scripts/aitask_pick_own.sh` (lines
227-281 acquire and force paths, 391-427 reclaim signal decision),
`.aitask-scripts/lib/pid_anchor.sh`,
`.claude/skills/task-workflow/crash-recovery.md`,
`tests/test_task_lock.sh`, `tests/test_lock_force.sh`,
`tests/test_lock_reclaim.sh`, `tests/test_crash_recovery_pid_anchor.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-10T13:30:06Z status=pass attempt=1 type=human
