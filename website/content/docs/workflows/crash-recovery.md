---
title: "Crash Recovery"
linkTitle: "Crash Recovery"
weight: 42
description: "Resume a task whose prior agent died mid-implementation, with a survey of leftover work before deciding to reclaim or drop"
depth: [intermediate]
---

When tmux or the host shell crashes mid-implementation, the agent process dies but the task's `status: Implementing` and its [lock](../../concepts/locks/) persist on the `aitask-locks` branch. On the next `/aitask-pick <N>`, the workflow notices that the prior agent's process is gone, surveys uncommitted work in the worktree, and asks whether to **Reclaim and continue** here or **Pick a different task**.

There is no time threshold to tune: the decision is made from the process the lock was anchored to. That anchor has **three** states, not two, and the distinction is what makes the signal trustworthy:

| State | Meaning | Outcome |
|---|---|---|
| **dead** | The anchored process is provably gone, or the PID now belongs to a different process | `RECLAIM_CRASH:` — the headline case |
| **alive** | The anchored process is provably still the one that took the lock | **The claim is refused** — no crash is reported |
| **unknown** | Liveness cannot be established | **The claim is refused** — no crash is reported |
| **unknown, no anchor** | The lock never named a session process at all | Claimed, with the anomaly prompt |

Only a *provably* dead anchor is reported as a crash. "We cannot tell" is never rounded up to "it crashed" — a recovery prompt that says an agent crashed has to be right, because reclaiming while the other session is still working duplicates its work.

The same verdict also decides whether the task can be claimed at all. A lock held by *another live session of yours on this machine* is not a recovery situation, and it is refused rather than reclaimed — see [When the holder is still running](#when-the-holder-is-still-running) below.

## When the Recovery Path Fires

Three triggers route through the same Crash Recovery procedure. Their prompt wording differs by case, but the survey block and the Reclaim/Decline decision are identical.

### Same-host crash (headline case)

When a task is claimed, [`aitask_lock.sh`](../../commands/lock/) records `pid:`, `pid_starttime:` and `pid_starttime_kind:` in the lock metadata alongside the existing `locked_by` / `locked_at` / `hostname` fields.

**What the `pid:` points at.** It is the **agent session's own process** — specifically the process of the tmux pane the agent runs in. The framework launches every agent as its pane's own process, so the pane's pid *is* the agent CLI, and it dies exactly when the agent or the pane dies. Resolution order at claim time:

1. `AIT_AGENT_PID`, if set — an explicit override for launchers that start an agent outside tmux, and for tests. It must name a process that exists; a stale value is refused with a warning rather than trusted.
2. The tmux pane's process, resolved from `$TMUX_PANE`. The lookup is checked against the pane's own tmux server, so an inherited or stale `$TMUX_PANE` from a different server can never name a stranger's pane.
3. Otherwise **unknown**, written as `pid: -`. There is deliberately no further fallback: recording some other, short-lived PID is exactly how the anchor stops meaning anything.

**How liveness is decided on re-pick.** [`/aitask-pick`](../../skills/aitask-pick/) looks the PID up through `/proc`, then `ps`, then `kill`'s error code. It treats the PID as gone **only** on an explicit "No such process". A "not permitted" answer is positive proof the process exists, and a lookup that is blocked outright — for example under a `hidepid` procfs mount, which hides another user's live process from both `/proc` and `ps` — resolves to *unknown*, not *dead*. (A bare `kill -0` cannot distinguish those two: it returns the same failure for both.)

The PID alone is not an identity, because PIDs are recycled, so the lock also stores a start-time token and the source it came from (`pid_starttime_kind`). A *dead* verdict needs the process to be confirmed absent or the token to prove a different process now holds the number; an *alive* verdict needs a matching token from a high-resolution source. Anything less is unknown.

If — and only if — the verdict is **dead** and the recorded hostname is the current host, the picker emits a `RECLAIM_CRASH:` signal: the headline case this feature was built for.

### Multi-PC reclaim

You started a task on PC_A, walked over to PC_B, and ran `/aitask-pick` on the same task ID. The recorded hostname differs from the current one, so the picker emits a `LOCK_RECLAIM:` signal. This case predates the PID-anchor work and now lives in the same Crash Recovery procedure with case-specific wording.

### Lock anomaly fallback

The task is `Implementing` and `assigned_to` matches you, but the anchor does not establish a crash. The picker emits `RECLAIM_STATUS:`. This covers the cases where there is no holder left to check:

- the lock records **no session process** (`pid: -` or `pid: 0`) — a claim made outside tmux with no `AIT_AGENT_PID`, a legacy lock predating the PID anchor, or a lock that went missing entirely;
- the lock is **this session's own**, being refreshed;
- the task's `Implementing` status outlived its lock.

All of these land here rather than in the crash path, because the one thing this prompt must not do is tell you an agent crashed when it did not.

## When the Holder Is Still Running

A lock is not always something to recover from. If the anchored process is a *different* session of yours on *this* machine, reclaiming it does not rescue abandoned work — it puts two agents on one task, which is how the same verification work gets done twice. So the claim is **refused** instead:

| Signal | Meaning |
|---|---|
| `LOCK_LIVE_HOLDER:` | The holding session is provably still running |
| `LOCK_UNVERIFIABLE_HOLDER:` | The holding session could not be shown to be either running or gone |

Both refusals happen **before** the lock is written, before `status` becomes `Implementing`, and before anything is committed — so a refused pick leaves the task byte-for-byte as it was, and there is nothing to undo. The prompt offers "Pick a different task" first and a force option second; unattended runs ([`/aitask-pickrem`](../../skills/aitask-pickrem/)) always abort rather than force.

Three cases deliberately do **not** trigger a refusal:

- **Your own session re-claiming.** The lock records the process, not just the email, so a session recognises its own lock and refreshes it silently. Without that, the ownership guard, an in-pane re-pick, and every resume of an in-flight task would lock you out of your own work.
- **A lock from another host.** A PID from another machine means nothing here; that is the multi-PC reclaim case above.
- **A lock that never recorded a session process.** There is nothing to verify, so refusing would strand it forever. It stays reclaimable through the anomaly prompt.

To clear a refusal properly, release the lock from the session that holds it (`ait lock --unlock <task_id>`), or let that session finish.

## The In-Progress Work Survey

Before prompting, the procedure runs a read-only survey of any uncommitted work the prior agent left behind. The user sees this block before deciding, so they are not asked to reclaim blind.

```
Prior in-progress work:
- Worktree: aiwork/t42_add_login
- 5 modified, 2 staged, 1 untracked
- Recorded checkpoints: plan_approved: pass, review_approved: pass
- Resume target: post-implementation (Step 9)
- Plan: Steps 1-3 complete, "Final Implementation Notes" not yet written
```

Each line:

- **Worktree.** Resolved by parsing `git worktree list --porcelain` for a `branch refs/heads/aitask/<task_name>` entry. When no separate worktree exists (the prior pick worked on the current branch), this reads `(current branch)`.
- **File counts.** Derived from `git status --porcelain` and `git diff --stat HEAD` against the resolved worktree. The split surfaces "you have 2 staged commits ready, 5 modifications still unstaged, 1 untracked file" at a glance — much more useful than a single total.
- **Recorded checkpoints / Resume target.** The primary progress signal. When the task recorded gate checkpoints during its earlier session (see [Resuming From the First Unmet Checkpoint](#resuming-from-the-first-unmet-checkpoint) below), the survey shows the derived checkpoint state and the stage the workflow will resume at.
- **Plan.** A one-line progress hint extracted from the plan file at `aiplans/p<N>_<name>.md` (or `aiplans/p<parent>/p<parent>_<child>_<name>.md` for child tasks). When no checkpoints were recorded, this plan-file marker is the fallback progress hint; the procedure looks for the most-recent marker — a "Final Implementation Notes" stub, checked-step markers (`- [x]`), or a "Post-Review Changes" section — to convey how far the prior agent got.

When the prior agent crashed before making any changes (or the worktree was already cleaned up), the block reads:

```
Prior in-progress work: none detected
```

## The Reclaim / Decline Prompt

The prompt header is `Reclaim`. The question text is case-specific; the two options are identical across all three signals.

### Question wording

- **`RECLAIM_CRASH`** (same-host crash):

  > Previous agent on this machine appears to have crashed (PID `<pid>` no longer running since `<locked_at>`).
  >
  > _\<survey block\>_
  >
  > Resume with prior work intact?

- **`LOCK_RECLAIM`** (multi-PC reclaim):

  > Task t\<N\> is already in `Implementing`, claimed by you on `<prev_hostname>` since `<locked_at>` (current host: `<current_hostname>`).
  >
  > _\<survey block\>_
  >
  > Reclaim and continue here?

- **`RECLAIM_STATUS`** (lock anomaly — the anchor is alive, absent, or unverifiable):

  > Task t\<N\> shows status `Implementing` already assigned to you, but no PID anchor matches your environment.
  >
  > _\<survey block\>_
  >
  > Reclaim and continue here?

### Options

- **Reclaim and continue** — The lock is now held on this host with a fresh PID anchor. Prior in-progress changes remain intact in the worktree (or current branch). The picker resumes from the recorded resume target (see below) rather than always restarting at planning. This is the option to pick when the survey looks like work worth saving.

- **Pick a different task** — Releases the lock, reverts the task to `Ready`, clears `assigned_to`, commits and pushes. Control returns to the calling skill's task selection. **Important:** declining only resets the task's metadata. Uncommitted files in the worktree (and the worktree itself, if a separate one was created) are left in place — clean them up manually with `git stash`, `git restore`, or `git worktree remove` if you don't intend to come back.

## End-to-End Example

The headline `RECLAIM_CRASH` case as a single narrative:

1. The user runs `/aitask-pick 42`. The picker claims the lock — recording the **agent pane's** pid plus its start-time token — enters plan mode, and starts implementing in `aiwork/t42_add_login`.
2. tmux crashes (or `tmux kill-server`, or the laptop loses power). The agent's pane process dies with it. Task `t42` is still `status: Implementing`, lock still pinned to this host.
3. The user opens a fresh terminal and re-runs `/aitask-pick 42`. The picker reads the lock, sees the recorded hostname matches, and looks the anchored PID up: not in `/proc`, not in `ps`, and `kill` reports "No such process". That is a confirmed absence → `RECLAIM_CRASH:`.
4. The Crash Recovery procedure surveys the `aiwork/t42_add_login` worktree, prints a "Prior in-progress work" block (3 modified files, partial plan progress), and asks the case-specific prompt.
5. The user picks **Reclaim and continue**. The picker writes a new lock with the resumed agent's PID, the workflow proceeds to Step 5, and prior changes are intact and visible to the resumed agent.

Without this flow the same scenario would have surfaced as the older "no PID anchor matches your environment" wording with no survey of leftover files — leaving the user to discover by hand what the prior agent had touched.

## Resuming From the First Unmet Checkpoint

When a profile records gate checkpoints (the `record_gates` execution-profile key — on by default for the `fast` profile), task-workflow appends a checkpoint to the task's ledger as each one is reached: the plan is approved, the change is reviewed, and so on. On re-pick, the recovery flow reads that ledger and resumes from the **first unmet checkpoint** instead of replaying planning and implementation from the top:

- **No checkpoints recorded** (the task crashed before its plan was approved, or the profile does not record gates) — the workflow plans from scratch, exactly as before. This is the default for profiles without `record_gates`.
- **Plan approved, not yet reviewed** — the workflow reclaims the lock and resumes directly at implementation, following the already-approved plan.
- **Review approved** — the code was already committed and reviewed in the earlier session; the workflow resumes at post-implementation (merge, if a branch was used, and archival). The merge approval is still required — re-entry never auto-merges.

The reclaim prompt's survey shows the recorded checkpoints and the resume target, so reclaiming is an informed choice. Resume is conservative by design: if a checkpoint was recorded but the plan file is missing, the workflow falls back to planning from scratch.

### A resumed task is checked against the remote first

A resumed task has been sitting still while everyone else pushed, so its local branches are the most likely in the repository to be out of date. Before any work restarts, the workflow re-reads the base and merge-target branch names **from the saved plan file** — not from whichever execution profile you happen to be running now — and checks them against the remote. A branch name that is not a valid, safe git ref stops the resume rather than being guessed at.

What happens next depends on how far the task had got:

- **Resuming at implementation** — you get the same remote-drift warning you would have seen at planning time, with extra emphasis on remote changes to files your plan targets. Choosing to stop reverts the task to `Ready` so you can pull and re-pick; that re-pick goes through normal planning, so the check cannot bounce you in a loop.
- **Resuming at post-implementation** — the merge target is checked instead. This matters because the merge itself is purely local: if the remote has moved ahead, the merge succeeds quietly and the problem only appears later as a rejected push. You are offered a fast-forward sync of the merge target, continuing anyway, or stopping. Stopping here leaves the task in flight (it is *not* reverted — the code is already committed and reviewed) so re-picking resumes at the same place.

The sync only ever fast-forwards. If your local merge target has commits the remote does not, that is a real divergence, and the workflow stops and asks rather than rebasing or resetting anything.

## Tips

- **Claims made outside tmux record no anchor.** If you start an agent in a plain terminal rather than a tmux pane, the lock records `pid: -` and re-picks report the anomaly fallback instead of a crash. Set `AIT_AGENT_PID` to the agent's own PID when launching it if you want crash detection there — and note that such a lock also cannot be protected from a concurrent claim, since there is no process to check.
- **A lock taken from the board TUI is anchored to the board.** The Lock button in `ait board` records the board's own pane process, and the board typically stays open for hours — so that lock reads as a *live holder* to any agent you then start for the same task, and the pick is refused. That is the honest answer, but if you meant the lock as a reservation rather than a claim, unlock it from the board before launching the agent.
- **The backfill script is no longer needed.** `./.aitask-scripts/aitask_backfill_pid_anchor.sh` tags pre-anchor locks with a `pid: 0` sentinel. That sentinel now means *unknown*, so a backfilled lock re-picks as `RECLAIM_STATUS:` — the same, honest outcome it would get with no fields at all. Running the script is optional and changes no signal.
- **Decline does not touch your worktree.** "Pick a different task" reverts task metadata and releases the lock. Uncommitted files in the worktree, and the worktree directory itself, are left alone. Decide explicitly whether to keep them.
- **macOS portability.** The identity token comes from `/proc/<pid>/stat` on Linux and from `ps -o lstart=` elsewhere, so macOS/BSD gets PID-recycling defense too — but only at one-second resolution. Because that cannot rule out a PID recycled within the same second, a *matching* token there yields "unknown" rather than "alive"; it is recorded as such in `pid_starttime_kind`. Crash detection itself is unaffected on macOS: a crashed agent's PID is absent, which is decided before any token is compared.
- **Cross-host reclaim is the same procedure.** Multi-PC reclaim (`LOCK_RECLAIM:`) shares the survey block, the option list, and the decline cleanup with same-host crash recovery. Only the question wording differs.

## See also

- [Concepts: Locks](../../concepts/locks/) — the `aitask-locks` branch and the lock metadata the recovery reads
- [Parallel Development](../parallel-development/) — the broader concurrency picture this fits into
- [`/aitask-pick`](../../skills/aitask-pick/) — the skill that runs the recovery
- [`ait lock`](../../commands/lock/) — manual lock inspection and force-release
