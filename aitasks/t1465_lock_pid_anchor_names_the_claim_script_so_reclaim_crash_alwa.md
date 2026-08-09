---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [crash_recovery, aitask_pick, bash_scripts]
created_at: 2026-08-09 13:01
updated_at: 2026-08-09 13:01
---

`get_lock_pid()` anchors a task lock to a process that is guaranteed to be dead
moments later, so `RECLAIM_CRASH` fires on essentially every same-host re-pick
and a genuine crash becomes indistinguishable from normal operation.

## Root cause

`.aitask-scripts/aitask_lock.sh:83-85`:

```bash
# PID to anchor the lock to. PPID is the agent's bash/claude process —
# when the agent dies (tmux crash), kill -0 returns ESRCH, and re-pick
# detects the crash via aitask_pick_own.sh.
get_lock_pid() {
    echo "$PPID"
}
```

The comment holds only if `aitask_lock.sh` is invoked directly by the agent's
own shell. On the path that actually matters it is not:
`aitask_pick_own.sh:227` invokes it via command substitution

```bash
lock_output=$("$SCRIPT_DIR/aitask_lock.sh" --lock "$task_id" --email "$email" 2>&1) || lock_exit=$?
```

so `$PPID` resolves to **`aitask_pick_own.sh` itself** — a short-lived script
that exits a few seconds after the claim. The anchor therefore names a dead
process from almost the moment it is written.

## Evidence

**1. A real lock from a live session.** Observed reclaim signal:
`PRIOR_LOCK:269696|1097644|omg16|2026-08-09 10:50`. Resolving the starttime
anchor (`btime` + `1097644`/`CLK_TCK`) gives a process start of
**2026-08-09 10:50:20** — the same moment the lock was recorded, while the
session holding it had been working since roughly 09:49. A long-lived agent
cannot have a starttime equal to its own lock timestamp; the anchored process
was created by the claim.

**2. Mechanism.** A probe reproducing line 227's invocation shape (parent
script; child invoked via `$(...)`; child echoes `$PPID`) records the parent's
own PID, which is dead as soon as the parent returns.

**3. End-to-end with the real writer, nothing hand-planted.** Using the
paired-repo fixture from `tests/test_crash_recovery_pid_anchor.sh`:

- claim #1 via the real `aitask_pick_own.sh` -> `OWNED:1`
- read the anchor back via `aitask_lock.sh --check` -> `pid=623122`,
  `kill -0` reports **DEAD** immediately after the claim
- innocent same-host re-claim -> `OWNED:1` **and**
  `RECLAIM_CRASH:2026-08-09 12:48|pc-A|623122`, with nothing having crashed

**4. Negative control — the liveness helper is correct.** Planting a genuinely
live PID (a running `sleep`) together with its matching
`/proc/<pid>/stat` field-22 starttime yields `RECLAIM_STATUS`, **not**
`RECLAIM_CRASH`. `is_lock_holder_alive()` and the starttime PID-recycling
defense in `.aitask-scripts/lib/pid_anchor.sh` both behave correctly, and
`get_pid_starttime()` indexes field 22 correctly. The defect is isolated to
`get_lock_pid()`.

## Impact

`RECLAIM_CRASH` carries no information: it is emitted whether or not the prior
agent crashed. Because task-workflow Step 4 routes it into the Crash Recovery
Procedure, the user is shown "Previous agent on this machine appears to have
crashed (PID N no longer running)" and asked whether to reclaim. The prompt is
the only thing standing between two agents and the same task, and it is fed a
false crash story that makes "reclaim" the obvious answer.

Observed live: a `/aitask-pick 1427` session was told a still-running sibling
session had crashed, reclaimed t1427_5, and duplicated roughly 15 minutes of
verification work while the original session was still committing. See the
companion task on the acquire-path liveness gate, which is the other half of
that outcome.

## Test gap

Every anchor in `tests/test_crash_recovery_pid_anchor.sh` is hand-planted
(`pid: 999999`, `pid: 1` with a wrong starttime, a pre-anchor lock with no
fields). No test claims a lock through the normal writer and then asks whether
the recorded anchor is alive, so the writer's choice of PID is never exercised
and the suite stays green. This is the "prove the writer, not just the readers"
gap.

## Acceptance criteria

- The lock anchors to a process whose lifetime actually tracks the agent
  session, not to the claim script. Decide and document what that process is
  (candidates: the tmux pane's process, the agent CLI process, an explicit
  `AIT_AGENT_PID` passed in by the launcher) and what happens when it cannot be
  resolved — a fallback that silently re-introduces a short-lived PID is not
  acceptable, and "unknown" must be its own state rather than collapsing to
  "dead".
- A test that exercises the **writer**: acquire through `aitask_pick_own.sh`
  with no planted state, read the anchor back, and assert it is alive while the
  owning session is alive.
- A test that a same-host re-pick of a lock whose holder is still alive does
  **not** emit `RECLAIM_CRASH`.
- The misleading comment on `get_lock_pid()` is corrected.
- Existing hand-planted tests keep passing (they pin the reader contract and
  remain valid).

## Sources

`.aitask-scripts/aitask_lock.sh` (`get_lock_pid`, `lock_task`),
`.aitask-scripts/aitask_pick_own.sh` (line 227 acquire, lines 391-427 reclaim
decision), `.aitask-scripts/lib/pid_anchor.sh`,
`.aitask-scripts/aitask_backfill_pid_anchor.sh`,
`tests/test_crash_recovery_pid_anchor.sh`,
`.claude/skills/task-workflow/crash-recovery.md`.
