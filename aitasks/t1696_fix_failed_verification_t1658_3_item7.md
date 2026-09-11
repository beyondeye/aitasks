---
priority: medium
effort: medium
depends: [t1658_1]
issue_type: bug
status: Implementing
labels: [verification, bug]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1658
followup_kind: verification_failure
created_at: 2026-09-02 18:55
updated_at: 2026-09-04 16:45
boardcol: now
boardidx: 29766
---

## Failed verification item from t1658_1

> [t1658_1] From that partial state, run `./ait sync` and confirm the branch converges (both `./ait git rev-list --count @{u}..HEAD` and `HEAD..@{u}` reach 0) with no work lost.

### Source

- **Manual-verification task:** `aitasks/t1658/t1658_3_manual_verification_data_branch_metadata_push.md` (item #7)
- **Origin feature task:** t1658_1
- **Origin archived plan:** `aiplans/archived/p1658/p1658_1_converge_local_data_branch_after_offbranch_push.md`

### Commits that introduced the failing behavior

- cb271b5a9 bug: Converge the local data branch after an off-branch metadata push (t1658_1)

### Files touched by those commits

- .agents/skills/task-workflow-remote-codex-/satisfaction-feedback.md
- .aitask-scripts/aitask_usage_update.sh
- .aitask-scripts/aitask_verified_update.sh
- .aitask-scripts/lib/task_utils.sh
- .aitask-scripts/lib/verified_update_lib.sh
- .claude/skills/task-workflow-remote-/satisfaction-feedback.md
- .claude/skills/task-workflow/satisfaction-feedback.md
- .opencode/skills/task-workflow-remote-/satisfaction-feedback.md
- tests/golden/procs/task-workflow/satisfaction-feedback-default.md
- tests/golden/procs/task-workflow/satisfaction-feedback-fast.md
- tests/golden/procs/task-workflow/satisfaction-feedback-remote.md
- tests/lib/metadata_update_fixture.sh
- tests/test_task_push.sh
- tests/test_usage_update.sh
- tests/test_verified_update.sh

### Observed behavior (recorded during t1658_3 auto-verification, 2026-09-02)

Reproduced on this checkout with three other agent sessions live.

**Setup — the partial state was forced exactly as item #6 specifies:**
`aitasks/metadata/models_claudecode.json` left locally modified, then
`aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick`.
Item #6 passed: stdout `UPDATED_REMOTE_ONLY:claudecode/opus4_6:pick:5`, exit 3,
explanation on stderr, local edit untouched. Branch left `behind 1 / ahead 0`,
with metadata commit `759616e58` on `origin/aitask-data` only.

**Then the probe edit was reverted, leaving the genuine partial state**
(behind 1 / ahead 0, models_claudecode.json clean, four unrelated task/plan
files dirty because their tasks are locked by live sessions).

**`./ait sync` did not converge:**

```
RC=0
sync: not everything was auto-committed —
  - t1675 is locked by a LIVE session on omg16 - its files left dirty for that session to commit
  - t1677 is locked by a LIVE session on omg16 - its files left dirty for that session to commit
  - t1658_3 is locked by a LIVE session on omg16 - its files left dirty for that session to commit
  - t1686 is locked by a LIVE session on omg16 - its files left dirty for that session to commit
Warning: Sync deferred: 4 protected file(s) block the rebase; the fetch still ran.

after:  ahead @{u}..HEAD = 0   behind HEAD..@{u} = 1
merge-base --is-ancestor 759616e58 HEAD -> NO (commit still missing locally)
```

`ait sync` exits **0** while leaving the branch behind, so a caller cannot tell
recovery failed.

**`task_data_converge()` — the seam t1658_1 itself added — recovered it immediately:**

```
STATUS=fast-forwarded REASON= AHEAD=0 BEHIND=0
merge-base --is-ancestor 759616e58 HEAD -> YES
```

All four dirty foreign files were still present and byte-identical (md5 unchanged)
afterwards.

### The defect

The partial-outcome messages direct the user to a command that cannot perform the
recovery in the very situation that produces the partial outcome:

- `lib/verified_update_lib.sh:191` - "... not on the local data branch (converge: ...) - recover with './ait sync'"
- `lib/task_utils.sh:732` - "local edits to the same file(s) block the fast-forward; commit them or reconcile with './ait sync'"
- `lib/task_utils.sh:734` - "local data branch has both unpushed and unpulled commits; reconcile with './ait sync'"

`ait sync` reconciles via `pull --rebase`, which requires a clean worktree. Its
own t1599 lock protection deliberately leaves live-locked task files dirty and
then takes the `protected_dirty` deferral (`aitask_sync.sh` step 5 early exit),
so on a multi-agent box the recommended recovery is unreachable — while
`task_data_converge()`'s `fetch` + `merge --ff-only` succeeds against exactly
that state.

**Not a data-loss bug:** nothing was lost, and the next metadata update
self-heals because it calls `task_data_converge()` before committing. The defect
is the misdirecting recovery instruction (and `ait sync`'s silent exit 0), not
the convergence seam, which behaved correctly throughout.

### Suggested direction (not prescriptive)

Point the recovery hint at a path that works with a dirty shared worktree - e.g.
name the converge seam directly, or have `ait sync` run `task_data_converge()`
on its `protected_dirty` deferral path before giving up. Whatever is chosen, the
hint and the reachable recovery must agree.

### Additional surface carrying the same hint

The rendered satisfaction-feedback procedures repeat the unreachable advice on the
partial-result branch and must be updated together with the shell messages:

- `.claude/skills/task-workflow/satisfaction-feedback.md:42` and `:93`
- `.claude/skills/task-workflow-remote-/satisfaction-feedback.md:38-area` and `:87-area`
- `.agents/skills/task-workflow-remote-codex-/satisfaction-feedback.md`
- `.opencode/skills/task-workflow-remote-/satisfaction-feedback.md`
- goldens under `tests/golden/procs/task-workflow/satisfaction-feedback-*.md`

(The continue-not-abort contract in those files is correct and was verified working
in t1658_3 item 8 - only the `./ait sync` recovery wording is at issue.)

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1658_3 item #7.

## Scope correction: the DIVERGED state has no recovery at all (observed 2026-09-04)

The analysis above was recorded from the **fast-forwardable** partial state
(`behind 1 / ahead 0`), where `task_data_converge()` recovers immediately. That
is not the state this repo actually drifts into. Observed live on `omg16` today,
on `aitask-data`:

```
ahead/behind vs origin/aitask-data:  46  12     (was 30 / 8 ~20 min earlier, still growing)
merge-base:                          8e32d4070
origin-only commits touch ONLY:      aitasks/metadata/models_claudecode.json
worktree:                            4-5 task files permanently dirty
                                     (live /aitask-pick agents t1647_2, t1704, t1705)
```

**Both recovery paths refuse, so the two findings above compose into a deadlock:**

- `task_data_converge()` does **not** self-heal here. Its fast-forward arm is
  reached only when `ahead == 0`; with both counts non-zero it takes the earlier
  early return at `lib/task_utils.sh:985-990` -> `STATUS=diverged`,
  `REASON=local_diverged`, and hands off to `./ait sync`.
- `./ait sync` takes the `protected_dirty` deferral at `aitask_sync.sh:1278`
  (`(( ${#PROTECTED_DIRTY[@]} )) && remote_ahead > 0`) and exits 0 before the
  rebase, because the shared worktree is dirty by design on a multi-agent box.

So each guard forwards recovery to the other and neither executes. The state is
**absorbing, not self-healing**: every subsequent pick fires
`commit_and_push_from_remote_clone()`, whose pre-converge is itself the
`diverged` no-op, then pushes one more commit to origin only. The gap grew by
16 local + 4 remote commits during a single session of observation.

### Corrections to the assessment above

- "the next metadata update self-heals because it calls `task_data_converge()`
  before committing" holds **only while `ahead == 0`**. Once any local commit
  lands while origin is ahead, the pre-converge becomes a no-op and the
  divergence is permanent.
- "the defect is the misdirecting recovery instruction ..., not the convergence
  seam" is too narrow. In the diverged state there is **no reachable recovery to
  point the hint at** — rewording alone cannot fix this case. The suggested
  direction ("have `ait sync` run `task_data_converge()` on its `protected_dirty`
  deferral path") is also insufficient on its own, since that call returns
  `diverged` without acting.

### What actually recovered it

A merge (not a rebase) resolves it with the worktree dirty, because the two
sides are path-disjoint — origin's commits touch only `models_claudecode.json`,
which was clean locally and untouched by all 46 local commits. Performed by hand:

1. `git worktree add --detach <tmp> <local-tip>`; `git merge origin/aitask-data`
   there (clean, one file changed).
2. `git -C .aitask-data merge --ff-only <merge-commit>` — the merge commit
   descends from the local tip, so this is a fast-forward that **fails closed**
   if an agent commits in the window (it did, on the first attempt; retried).
3. `git push origin aitask-data`.

Result `cd994a6ef`, `0 / 0`, with every dirty agent file left untouched. Note
step 2 is exactly the `merge --ff-only` seam t1658_1 chose — it works here too;
what is missing is a step that first *creates* a descendant of the local tip
when `ahead != 0`, which is the gap in the `diverged` arm.

A fix should therefore give the `diverged` arm a real action (a path-disjointness
check plus an off-worktree merge is one option that preserves the
"never stash, never commit other sessions' files" contract), not only a better
hint. Any such change must keep failing closed when the dirty paths *do* overlap.

### Related: stale locks widen the blocked set

`PROTECTED_DIRTY` is computed from the lock branch, which is not self-cleaning.
At the time of this observation 9 of the 12 locks on `aitask-locks` named dead
pids, the oldest (`t259`) held since 2026-02-26. `t1699_lock.yaml` (pid 3874251,
dead) was protecting a dirty file and was released manually; the other 8 stale
locks remain. Each one can pin a file into `PROTECTED_DIRTY` indefinitely and
make the deferral above fire more often than the live sessions alone warrant.
Tracked separately as **t1715** (stale-lock reaping); not in this task's scope.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1725** id=2026-09-07T13:40:39Z.1adc9e86b6ca2e7432aa7b9d from=t1725 at=2026-09-07T13:40:39Z base=529baf5aef304196e683ac492d0d374affbd54fc base_branch=main dirty=yes host=omg16
>
> | t1725 (sync deferrals actionable) overlaps your suggested direction. Its child t1725_3 implements the sync-side half: when local_ahead == 0, aitask_sync.sh fast-forwards (merge --ff-only) instead of deferring on dirty files that no incoming commit touches; and only tracked-dirty files with local commits (or files an incoming commit touches) block the rebase. Please keep t1696 scoped to the hint-wording half (task_utils.sh:732/734, verified_update_lib.sh:191, satisfaction-feedback procedures + goldens) and, once t1725_3 lands, point the hints at './ait sync' again where it now succeeds. Consider depends: [1725_3].

> **✉ note:t1789** id=2026-09-11T08:27:58Z.7711fe537a2c1e3674acffc1 from=t1789 from_verified=yes at=2026-09-11T08:27:58Z base=c78deab369254f559285e8ab2bdf73878049e808 base_branch=main dirty=no host=omg16
>
> | t1789 (commit 12bfaac90 on main) appended Tests 61-63 to
> | tests/test_task_push.sh, just before the summary block, plus a file-level
> | MAINT_SPAWN constant directly above them. As of 12bfaac90 the file ends at
> | Test 63, so number any test you append from 64.
> | 
> | It also changed Test 41's _ait_data_git override to skip leading `-c <k=v>`
> | pairs: every pull and abort in the task-data reconciliation now carries
> | AIT_RECONCILE_GIT_OPTS (lib/task_utils.sh) before the subcommand, so a stub
> | keyed on $1 no longer sees the subcommand.
