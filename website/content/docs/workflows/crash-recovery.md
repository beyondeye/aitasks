---
title: "Crash Recovery"
linkTitle: "Crash Recovery"
weight: 42
description: "Resume a task whose prior agent died mid-implementation, with a survey of leftover work before deciding to reclaim or drop"
depth: [intermediate]
---

When tmux or the host shell crashes mid-implementation, the agent process dies but the task's `status: Implementing` and its [lock](../../concepts/locks/) persist on the `aitask-locks` branch. On the next `/aitask-pick <N>`, the workflow notices that the prior agent's PID is gone, surveys uncommitted work in the worktree, and asks whether to **Reclaim and continue** here or **Pick a different task**. The PID liveness signal is binary — alive or dead — so there is no time threshold to tune and no false positives from a still-running agent.

## When the Recovery Path Fires

Three triggers route through the same Crash Recovery procedure. Their prompt wording differs by case, but the survey block and the Reclaim/Decline decision are identical.

### Same-host crash (headline case)

When a task is claimed, [`aitask_lock.sh`](../../commands/lock/) records `pid:` and `pid_starttime:` in the lock metadata alongside the existing `locked_by` / `locked_at` / `hostname` fields. On re-pick, [`/aitask-pick`](../../skills/aitask-pick/) checks the prior PID with `kill -0` and (Linux only) compares `pid_starttime` against `/proc/<pid>/stat` to defend against PID recycling. If the prior PID is gone, or if it is alive but the starttime no longer matches, AND the recorded hostname is the current host, the picker emits a `RECLAIM_CRASH:` signal — the headline case this feature was built for.

### Multi-PC reclaim

You started a task on PC_A, walked over to PC_B, and ran `/aitask-pick` on the same task ID. The recorded hostname differs from the current one, so the picker emits a `LOCK_RECLAIM:` signal. This case predates the PID-anchor work and now lives in the same Crash Recovery procedure with case-specific wording.

### Lock anomaly fallback

The task is `Implementing` and `assigned_to` matches you, but no PID anchor matches your environment — typically a legacy lock written before the PID-anchor change shipped, or a lock that went missing entirely. The picker emits `RECLAIM_STATUS:`. After upgrading, running `./.aitask-scripts/aitask_backfill_pid_anchor.sh` once retroactively tags pre-anchor locks with a `pid: 0` sentinel, so subsequent re-picks route through the headline `RECLAIM_CRASH:` path instead of this fallback.

## The In-Progress Work Survey

Before prompting, the procedure runs a read-only survey of any uncommitted work the prior agent left behind. The user sees this block before deciding, so they are not asked to reclaim blind.

```
Prior in-progress work:
- Worktree: aiwork/t42_add_login
- 5 modified, 2 staged, 1 untracked
- Plan: Steps 1-3 complete, "Final Implementation Notes" not yet written
```

Each line:

- **Worktree.** Resolved by parsing `git worktree list --porcelain` for a `branch refs/heads/aitask/<task_name>` entry. When no separate worktree exists (the prior pick worked on the current branch), this reads `(current branch)`.
- **File counts.** Derived from `git status --porcelain` and `git diff --stat HEAD` against the resolved worktree. The split surfaces "you have 2 staged commits ready, 5 modifications still unstaged, 1 untracked file" at a glance — much more useful than a single total.
- **Plan.** A one-line progress hint extracted from the plan file at `aiplans/p<N>_<name>.md` (or `aiplans/p<parent>/p<parent>_<child>_<name>.md` for child tasks). The procedure looks for the most-recent marker — a "Final Implementation Notes" stub, checked-step markers (`- [x]`), or a "Post-Review Changes" section — to convey how far the prior agent got.

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

- **`RECLAIM_STATUS`** (lock anomaly):

  > Task t\<N\> shows status `Implementing` already assigned to you, but no PID anchor matches your environment.
  >
  > _\<survey block\>_
  >
  > Reclaim and continue here?

### Options

- **Reclaim and continue** — The lock is now held on this host with a fresh PID anchor. Prior in-progress changes remain intact in the worktree (or current branch). The picker continues into Step 5/6 as if the original pick never crashed. This is the option to pick when the survey looks like work worth saving.

- **Pick a different task** — Releases the lock, reverts the task to `Ready`, clears `assigned_to`, commits and pushes. Control returns to the calling skill's task selection. **Important:** declining only resets the task's metadata. Uncommitted files in the worktree (and the worktree itself, if a separate one was created) are left in place — clean them up manually with `git stash`, `git restore`, or `git worktree remove` if you don't intend to come back.

## End-to-End Example

The headline `RECLAIM_CRASH` case as a single narrative:

1. The user runs `/aitask-pick 42`. The picker claims the lock (recording `pid: <agent-pid>` + `pid_starttime: <jiffies>`), enters plan mode, and starts implementing in `aiwork/t42_add_login`.
2. tmux crashes (or `tmux kill-server`, or the laptop loses power). The bash/Claude PID dies. Task `t42` is still `status: Implementing`, lock still pinned to this host.
3. The user opens a fresh terminal and re-runs `/aitask-pick 42`. The picker reads the lock, sees the recorded hostname matches, runs `kill -0 <dead-pid>` → ESRCH. The PID liveness check fails → emits `RECLAIM_CRASH:`.
4. The Crash Recovery procedure surveys the `aiwork/t42_add_login` worktree, prints a "Prior in-progress work" block (3 modified files, partial plan progress), and asks the case-specific prompt.
5. The user picks **Reclaim and continue**. The picker writes a new lock with the resumed agent's PID, the workflow proceeds to Step 5, and prior changes are intact and visible to the resumed agent.

Without this flow the same scenario would have surfaced as the older "no PID anchor matches your environment" wording with no survey of leftover files — leaving the user to discover by hand what the prior agent had touched.

## Tips

- **Backfill once after upgrading past t723.** Pre-existing `Implementing` locks written before the PID-anchor change lack `pid:` / `pid_starttime:`. Running `./.aitask-scripts/aitask_backfill_pid_anchor.sh` once tags them with the `pid: 0` sentinel so future re-picks of those tasks route through `RECLAIM_CRASH:` rather than the legacy `RECLAIM_STATUS:` fallback.
- **Decline does not touch your worktree.** "Pick a different task" reverts task metadata and releases the lock. Uncommitted files in the worktree, and the worktree directory itself, are left alone. Decide explicitly whether to keep them.
- **macOS portability.** PID-recycling defense via `pid_starttime` is Linux-only (it reads `/proc/<pid>/stat` field 22). On macOS the recovery falls back to PID liveness alone (`kill -0`) — the rare PID-recycling case is a documented minor edge there.
- **Cross-host reclaim is the same procedure.** Multi-PC reclaim (`LOCK_RECLAIM:`) shares the survey block, the option list, and the decline cleanup with same-host crash recovery. Only the question wording differs.

## See also

- [Concepts: Locks](../../concepts/locks/) — the `aitask-locks` branch and the lock metadata the recovery reads
- [Parallel Development](../parallel-development/) — the broader concurrency picture this fits into
- [`/aitask-pick`](../../skills/aitask-pick/) — the skill that runs the recovery
- [`ait lock`](../../commands/lock/) — manual lock inspection and force-release
