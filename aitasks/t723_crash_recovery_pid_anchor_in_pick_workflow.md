---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_pick, task_workflow]
folded_tasks: [694]
created_at: 2026-04-30 11:13
updated_at: 2026-04-30 11:13
---

## Context

When tmux (or the host shell) crashes mid-implementation, the agent process dies but the task's `status: Implementing` and lock file persist. The user re-runs `/aitask-pick <N>`. Today the workflow detects this case via `RECLAIM_STATUS:` (emitted whenever `prev_status == Implementing` and `prev_assigned == EMAIL`), but:

1. **Wording is wrong for the same-host case.** `task-workflow/SKILL.md:143` says *"no active lock holds it"* — but on same-host crash recovery the lock IS still held with this hostname. The `RECLAIM_STATUS:` branch was originally designed for a rare lock-missing anomaly and now also catches the common crash-recovery case under inaccurate language.
2. **No reliable "the prior agent is dead" signal.** Lock YAML records `task_id`, `locked_by`, `locked_at`, `hostname` but no PID. We can't distinguish "agent still running" from "agent crashed" except by hostname comparison (which collapses both same-host crash and same-host live-rerun into the same silent re-lock branch in `aitask_lock.sh:162-168`).
3. **No "where did the prior agent leave off?" orientation.** The user accepts/declines reclaim with no indication of what's already been changed in the worktree.
4. **All reclaim branches are inlined** in `task-workflow/SKILL.md` Step 4 — should be extracted to a dedicated procedure file per the project's "extract new procedures to their own file" convention.

## Scope

### 1. Add PID anchor to lock metadata

In `aitask_lock.sh` `acquire_lock`, extend the lock YAML written at line ~179-182 to include:
- `pid: <PID>` — the bash PID claiming the lock (or PPID — whichever maps to the agent's session; verify during implementation)
- `pid_starttime: <jiffies>` — read from `/proc/<pid>/stat` field 22 on Linux, anchors against PID recycling
- macOS portability: `ps -o lstart= -p <pid>` (BSD) or skip the starttime field on macOS — design must degrade gracefully if `pid_starttime` is absent

### 2. New `RECLAIM_CRASH:` signal

In `aitask_pick_own.sh`, when `prev_status == Implementing && prev_assigned == EMAIL`:
- Read the existing lock's `pid` + `pid_starttime` (if present) from `aitask_lock.sh --check`-style output.
- Same-hostname AND PID is dead (or PID alive but starttime mismatch — i.e., recycled) → emit `RECLAIM_CRASH:<locked_at>|<hostname>`.
- Keep emitting `RECLAIM_STATUS:` only for the genuine anomaly (lock missing or stale metadata).
- Cross-hostname continues to emit `LOCK_RECLAIM:` (unchanged).

### 3. Extract crash-recovery into its own procedure file

Create `.claude/skills/task-workflow/crash-recovery.md`. The procedure:
1. Receives the reclaim signal type and parsed fields.
2. **Surveys uncommitted in-progress work before prompting** — this is critical for orientation:
   - `git worktree list --porcelain` — look for `aitask/<task_name>` worktree
   - If worktree exists: `cd aiwork/<task_name> && git status --porcelain` and `git diff --stat HEAD` to show what was modified but not committed
   - If no worktree: same checks against current directory / branch
   - Read the plan file in `aiplans/p<N>` (if it exists) to see how far the prior agent got — partial step completion markers, "Final Implementation Notes" stub, etc.
3. Surfaces a concise summary to the user: "Prior agent left N modified files (M staged, K untracked). Plan shows steps 1-3 complete, step 4 in progress."
4. Then prompts via `AskUserQuestion`: "Reclaim and continue (review prior work before resuming)" / "Pick a different task (revert to Ready)" / "Abort with prior work intact (don't change task state)".
5. Wording is case-specific:
   - `LOCK_RECLAIM` (multi-PC) — current wording is fine
   - `RECLAIM_CRASH` (same-host crash) — "Previous agent on this machine appears to have crashed (PID gone since `<locked_at>`). Resume with prior work intact?"
   - `RECLAIM_STATUS` (anomaly) — "Task status `Implementing` but no lock anchor matches your environment. Reclaim?"

Then refactor `task-workflow/SKILL.md` Step 4 to a thin dispatcher: parse signals, call the procedure with the relevant context. Update Step 7's pre-implementation guard to reuse the same procedure for the multi-PC branch only (it doesn't need crash recovery — Step 7 only fires after Step 4 already succeeded).

### 4. Tests

Add tests covering:
- Lock acquire writes `pid`/`pid_starttime` correctly (Linux + macOS portability where possible)
- Same-host crash recovery: kill a background `sleep` whose PID we recorded as the lock holder, then `aitask_pick_own.sh` emits `RECLAIM_CRASH:`
- PID-recycling defense: PID is alive but `pid_starttime` differs → still treated as crashed
- Multi-PC reclaim still emits `LOCK_RECLAIM:` (no regression)
- Lock-missing anomaly still emits `RECLAIM_STATUS:`

### 5. Resolves t694

t694 asked whether same-host stale locks deserve a warning and what the threshold should be. The PID-liveness signal sidesteps the threshold question entirely — we don't need a time-based heuristic when we have a sharp aliveness signal. Document this resolution in the plan's Final Implementation Notes.

## Out of scope

- Cross-user lock takeover (already handled).
- Multi-PC reclaim UX (handled by t692; this task does not change `LOCK_RECLAIM:` wording).
- Auto-recovery of partially-implemented work (this task surfaces the state to the user; it does not auto-resume mid-step).
- Any change to `aitask_lock.sh --cleanup` semantics.

## Touchpoints

- `.aitask-scripts/aitask_lock.sh` (lock YAML write + new `--check`-style output for PID fields)
- `.aitask-scripts/aitask_pick_own.sh` (emit `RECLAIM_CRASH:`)
- `.claude/skills/task-workflow/SKILL.md` Step 4 (dispatcher + reference to new procedure)
- `.claude/skills/task-workflow/SKILL.md` Step 7 (ownership guard — reuse procedure for cross-host case only)
- `.claude/skills/task-workflow/crash-recovery.md` (new file)
- `tests/` — at least one new test script

## Notes

- macOS portability: `/proc` doesn't exist on macOS; use `ps -o lstart= -p <pid>` or accept that `pid_starttime` is Linux-only and gracefully fall back to PID-only check on macOS (with a comment that PID recycling is a known minor edge case there).
- Lock format change is backward-compatible: lock files written by older versions lack `pid`/`pid_starttime`, in which case we fall through to the existing `RECLAIM_STATUS:` path (preserves today's behavior).

## Merged from t694: investigate same host stale lock warning ux


## Context

Spun off from t692 (multi-PC self-reclaim warning). t692 added a `LOCK_RECLAIM:` signal in `aitask_lock.sh` that fires when the same email picks a task already locked on a *different* host. Same-host stale locks (locked by you on this same machine, but `locked_at` is hours old) were explicitly **out of scope** for t692 — user direction during planning was to "create followup investigation task, define actual need of the fix, scope, etc."

## Investigation goals

Determine whether same-host stale locks warrant a warning analogous to t692's multi-PC reclaim prompt, and if so, define:

1. **Need.** How often do users actually re-pick a task they started hours ago on the same host? Is the silent-refresh behavior they get today a problem, or just fine? Anecdotes / Slack mentions / past aitask review findings would help.
2. **Threshold.** What `locked_at`-age threshold is "stale"? 1 hour? 4 hours? Project-configurable in `project_config.yaml`? Per-user in `userconfig.yaml`?
3. **UX.** Same prompt as t692 (`LOCK_RECLAIM:` → "Reclaim and continue" / "Pick a different task")? Or quieter (just an info line, no confirmation)? Same prompt risks fatigue if it fires every morning when resuming yesterday's work.
4. **Edge cases.**
   - Hostname tracking under Docker / SSH / containers where `hostname` can be ephemeral or duplicated.
   - Interaction with `aitask_lock.sh --cleanup` (currently only removes locks for archived tasks — would need extending if we treat time-based stale locks as cleanup candidates).
   - What if the user has multiple local clones on the same machine with different working copies? Each runs same hostname but represents different work-in-progress.

## Deliverable

A short design doc / plan file (or a follow-up implementation task) that:
- Recommends fix-or-not based on the investigation.
- If fix: specifies threshold, prompt UX, where the threshold lives (config key + default).
- If not: documents the rationale so this question doesn't get re-litigated.

## Out of scope

- Cross-user lock takeover (already handled).
- Multi-PC reclaim (handled by t692).
- Auto-expiry of live locks across all dimensions — this task is specifically about *same-host stale* warnings.

## Notes

- See `aiplans/archived/p692_*.md` after t692 archives for the precedent design.
- The `LOCK_RECLAIM:` plumbing in `aitask_lock.sh` / `aitask_pick_own.sh` / task-workflow Step 4 is fully reusable — same-host stale handling would just add a second trigger condition (age threshold) alongside the existing hostname-mismatch one.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t694** (`t694_investigate_same_host_stale_lock_warning_ux.md`)
