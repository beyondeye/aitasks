---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-10-16 01:05
updated_at: 2026-10-16 01:05
---

## Origin

Spawned from t2018 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_crew_addwork.sh:332` — `git pull --rebase --no-autostash --quiet 2>/dev/null || true` leaves a conflicting rebase in progress (detached HEAD, possibly markers) in the shared crew worktree; the runner now holds on it (`rebase_in_progress`), but the script strands it. Same at `.aitask-scripts/aitask_crew_setmode.sh:126`.
- `.aitask-scripts/agentcrew/agentcrew_utils.py:499` — `git_commit_push_if_changes` stages with `git add -A` without checking `crew_merge_state()`, so an unfinished merge/rebase another process creates mid-iteration can be committed by the runner's end-of-iteration commit or an agent's terminal transition.
- `aidocs/agentcrew/agentcrew_architecture.md:222` — "Mark stale agents as Error" is stale (the runner only logs stale heartbeats; status is unchanged), and line 300 ("Agents never touch git directly") is stale (`ait crew status set` commits and pushes terminal transitions).

Line numbers are as of commit ab2cf4b37. Re-derive them before editing.

## Diagnostic context

t2018 rewrote the runner's `git_pull` (`.aitask-scripts/agentcrew/agentcrew_utils.py`) so it never opens a merge in the live crew worktree. It fetches the tracked branch, then either fast-forwards or proves a diverged merge clean in memory (`merge-tree --write-tree`), builds it with `commit-tree`, and advances with a protected `merge --ff-only --no-overwrite-ignore`. It also added `crew_merge_state(worktree)`, which names an unfinished merge or rebase (`merge_in_progress`, `rebase_in_progress`, `unmerged_paths`, `probe_failed`), and `git_pull` returns `PULL_UNSAFE` in that case. The runner's `main()` and `--check` refuse, and `run_loop` holds (no reads, writes or stages) until the state is resolved.

That protects only the runner's own pull. Two other writers in the same worktree can still create or commit such a state:

- addwork/setmode commit, then `git pull --rebase … || true`. A conflict leaves the rebase stopped in the shared worktree. The runner now holds on it instead of committing onto the detached HEAD, but nothing finishes or reports the rebase, so the runner stays held until a human intervenes.
- `git_commit_push_if_changes` is used by the runner's end-of-iteration and shutdown commits and by `ait crew status set` terminal transitions. It runs `git add -A && git commit` unconditionally, so a merge or rebase state that appears between the runner's pull and its commit (or during an agent's terminal transition) is concluded with whatever content is on disk, including conflict markers.

Test harness to reuse: `tests/test_crew_pull_no_autostash.sh` (Python harness wrapping `agentcrew_utils.git_cmd`; `--inject-after-fetch` injects another process's merge at an exact point).

## Suggested fix

Have addwork/setmode refuse cleanly when their rebase stops: abort only the rebase they started, and only when nothing else has written the worktree, or report it and leave it for a human. Never strand it silently. Guard `git_commit_push_if_changes` with `crew_merge_state()`: skip staging and committing, with a warning, while a merge or rebase is unfinished. Also fix the two stale lines in the architecture doc.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2024** id=2026-10-16T05:02:51Z.793c22e73a93f02ec5c1b5f3 from=t2024 from_verified=yes at=2026-10-16T05:02:51Z base=989687394d156e04d8cd8a58ae71735104b56ab6 base_branch=main dirty=no host=omg16
>
> | t2024 (commit ae0074ab7) moved the addwork/setmode pull your task targets. Line refs as of that commit:
> | 
> | - The `git pull --rebase --no-autostash --quiet 2>/dev/null || true` lines you cite (`aitask_crew_addwork.sh:332`, `aitask_crew_setmode.sh:126`) are gone. Both scripts now call `crew_pull_rebase` (`lib/agentcrew_utils.sh:170`). It runs a time-limited `git fetch --quiet -- <remote> <merge_ref>` of the tracked branch through `lib/bounded_run.py`, then, only if the fetch succeeded, a LOCAL `git -C <wt> rebase --no-autostash --quiet >/dev/null 2>&1`. Your premise still holds for that local rebase: a conflict stops it in the shared worktree and it is not aborted or reported. The single place to fix is now `crew_pull_rebase`.
> | - In addwork, the fetch/rebase/push now run OUTSIDE the commit subshell (`aitask_crew_addwork.sh:342-350`), guarded by a TERM stop-request flag (`_AIT_CREW_STOP`, set by `trap '_AIT_CREW_STOP=1' TERM` at line 29). brainstorm's `_run_addwork` sends that SIGTERM at its deadline, and addwork then skips publishing. setmode still runs `crew_pull_rebase .` inside its subshell (line 127).
> | - `git_commit_push_if_changes` moved to `agentcrew/agentcrew_utils.py:552` (you cite :499). Its push is now `git_cmd(..., timeout=crew_git_timeout())`.
> | - Related: the brainstorm deadline path (`brainstorm_crew._addwork_outcome`) reads `crew_merge_state()` back after a last-resort kill and reports an unfinished rebase with a `rebase --abort` remedy. It never aborts on its own.
> | 
> | Advisory context only; the design choice of abort vs report stays yours.
