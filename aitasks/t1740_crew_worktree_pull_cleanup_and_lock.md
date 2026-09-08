---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-08 12:46
updated_at: 2026-09-08 12:46
---

## Origin

Risk-mitigation ("after") follow-up for t1725_1, created at Step 8d after implementation landed.

## Risk addressed

Code-health / goal — crew worktrees abort unconditionally with no serialization.

From t1725_1's `## Risk`:
> The deferred gateway/crew/sync paths still leave wedges after this lands, so the
> parent's "any framework-driven pull" wording is not yet fully met · severity: low

## Goal

Two crew pull sites run `git pull --rebase --quiet 2>/dev/null || true`, which
leaves a conflicted rebase behind in the crew worktree:

- `.aitask-scripts/aitask_crew_setmode.sh:125`
- `.aitask-scripts/aitask_crew_addwork.sh:328`

Apply the ownership-checked cleanup t1725_1 built, and add serialization.

### The "private worktree" assumption is false — check it before relying on it

An earlier draft of t1725_1 justified skipping the lock with "a crew worktree has
exactly one writer by construction". That was asserted, not verified, and it does
not hold:

- there is **no lock anywhere in the crew family** — `aitask_crew_setmode.sh`,
  `aitask_crew_addwork.sh` and `lib/agentcrew_utils.sh` contain no
  `stale_lock_acquire` / `registry_lock_acquire` / `ait_lock_dir` call and no `trap`;
- `.aitask-scripts/brainstorm/brainstorm_session.py` invokes both scripts
  programmatically, so two runs against one crew worktree are plausible rather than
  theoretical, and they would start from the same HEAD and produce matching
  `orig-head` evidence — the one case the ownership helper cannot decide.

Also note a crew worktree is private to one *crew*, not to one *invocation*: an
interrupted earlier run or a manual recovery can leave a rebase behind, so an
unconditional `rebase --abort` can discard work it did not start.

### Shape

`ait_rebase_abort_if_ours` is already repo-agnostic — it takes a runner, so it works
with plain `git` inside the crew worktree. The pull mutex is currently hard-wired to
the data git-dir (`ait_pull_mutex_acquire` derives it from `_data_wedge_gitdir`);
generalize it to take a git-dir so the crew window can hold its own lock.

Consequences to design for, found while planning t1725_1:

- the depth/token bookkeeping must become **per lock dir**, since one process can
  legitimately hold the data lock and a crew lock at once — a single global counter
  would break;
- both crew commit blocks run inside a `( cd "$WT_PATH" … )` **subshell**, which a
  parent-level `EXIT` trap does not cover, so the release must be explicit with a
  subshell-scoped trap as the backstop;
- the crew scripts do **not** currently source `lib/task_utils.sh` (only
  `terminal_compat.sh`, `launch_modes_sh.sh`, `agentcrew_utils.sh`), so the helpers
  have to be made reachable — sourcing it is load-inert (data-worktree detection is
  lazy) but is a decision worth recording.

## Key files

- `.aitask-scripts/aitask_crew_setmode.sh` (~119-127, the commit block)
- `.aitask-scripts/aitask_crew_addwork.sh` (~320-330, the commit block)
- `.aitask-scripts/lib/task_utils.sh` — `ait_pull_mutex_acquire` /
  `ait_pull_mutex_release`, `ait_rebase_abort_if_ours`, `_ait_inprogress_state_at`
- `.aitask-scripts/brainstorm/brainstorm_session.py` — the programmatic caller

## Verification

- Two concurrent `aitask_crew_addwork.sh` runs against one crew worktree: the second
  reports the skipped-pull outcome, starts no rebase, and does not touch the first's
  state. Release, re-run → it proceeds (the control proving it was the lock, not a
  broken fixture).
- A crew worktree left mid-rebase by a killed earlier run → the next invocation
  leaves it in place and says so, rather than aborting it.
- A conflicted crew pull that IS this invocation's own → aborted, no `rebase-merge`
  left, and the following crew commit succeeds.
- Per-dir independence: holding a crew-git-dir lock and a data-git-dir lock in one
  process both succeed, and releasing one leaves the other held (this is what a
  single global depth counter fails).
- After every path, the crew lock dir is gone (subshell-exit release).
- Mutation-test both directions, as t1725_1 did: neuter the abort and confirm the
  cleanup assertions fail; neuter the ownership check and confirm the
  "left in place" assertions fail. Cheap, and it caught a vacuous lock assertion
  in t1725_1.
