# Crash Recovery Procedure

Called from task-workflow Step 4 (and the Step 7 ownership guard) when one
or more reclaim signals are emitted by `aitask_pick_own.sh`. Surveys
in-progress work, displays a case-appropriate prompt, and returns the
user's decision (`reclaim` | `decline`).

## Inputs (from caller context)

- `task_id`, `task_name`, `task_file`, `EMAIL`
- Parsed signal fields. When multiple signals are emitted, prefer in this
  order: `LOCK_RECLAIM` > `RECLAIM_CRASH` > `RECLAIM_STATUS`.
  - `LOCK_RECLAIM:<prev_hostname>|<prev_locked_at>|<current_hostname>`
  - `RECLAIM_CRASH:<prev_locked_at>|<prev_hostname>|<prev_pid>`
  - `RECLAIM_STATUS:<prev_status>|<prev_assigned_to>`

Set `signal_type` to one of `LOCK_RECLAIM` / `RECLAIM_CRASH` /
`RECLAIM_STATUS` based on the prefer-order above.

## Step 1 — Survey in-progress work

The previous agent may have left uncommitted changes the user should know
about before deciding. Run these read-only checks:

1. Worktree check:
   ```bash
   git worktree list --porcelain
   ```
   If a `branch refs/heads/aitask/<task_name>` line is present, capture
   the `worktree <path>` two lines above as `survey_dir`. Otherwise set
   `survey_dir` to the current directory (`.`).

2. Status + diff (run from `survey_dir`):
   ```bash
   git -C "<survey_dir>" status --porcelain | head -20
   git -C "<survey_dir>" diff --stat HEAD | tail -10
   ```
   Count modified files (M+A+D), staged files (entries starting with
   non-space in column 1), and untracked (`??`).

3. Plan progress:
   ```bash
   ./.aitask-scripts/aitask_query_files.sh plan-file <task_id>
   ```
   If `PLAN_FILE:<path>` is returned, read the file and look for the
   most-recent marker — "Final Implementation Notes", checked-step
   markers (`- [x]`), or a "Post-Review Changes" section. Summarize as a
   single line.

Build a short summary block (3-6 lines):

```
Prior in-progress work:
- Worktree: <path or "(current branch)">
- N modified, M staged, K untracked
- Plan: <progress hint or "no plan file">
```

If there are no uncommitted changes and no plan progress, the summary is
"Prior in-progress work: none detected".

## Step 2 — Case-specific prompt

Use `AskUserQuestion`. Pick the question text by `signal_type`:

- `LOCK_RECLAIM` (multi-PC):
  > "Task t\<N\> is already in `Implementing`, claimed by you on
  > `<prev_hostname>` since `<prev_locked_at>` (current host:
  > `<current_hostname>`).
  >
  > \<survey\>
  >
  > Reclaim and continue here?"

- `RECLAIM_CRASH` (same-host crash):
  > "Previous agent on this machine appears to have crashed (PID
  > `<prev_pid>` no longer running since `<prev_locked_at>`).
  >
  > \<survey\>
  >
  > Resume with prior work intact?"

- `RECLAIM_STATUS` (anomaly — lock missing or pre-PID-anchor lock):
  > "Task t\<N\> shows status `Implementing` already assigned to you,
  > but no PID anchor matches your environment.
  >
  > \<survey\>
  >
  > Reclaim and continue here?"

Header: "Reclaim"

Options:
- "Reclaim and continue" (description: "Resume work — the lock is held here, prior in-progress changes remain intact")
- "Pick a different task" (description: "Release the lock, revert to Ready, choose another task")

## Step 3 — Handle decision

If "Reclaim and continue": return `reclaim` to the caller.

If "Pick a different task": run lock release, revert status, commit, push,
then return `decline`:

```bash
./.aitask-scripts/aitask_lock.sh --unlock <task_id> 2>/dev/null || true
./.aitask-scripts/aitask_update.sh --batch <task_id> --status Ready --assigned-to ""
./ait git add aitasks/
./ait git commit -m "ait: Revert t<task_id> to Ready (reclaim declined)" 2>/dev/null || true
./ait git push
```
