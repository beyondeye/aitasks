---
priority: high
risk_code_health: high
risk_goal_achievement: medium
effort: medium
depends: [t1725_3]
issue_type: enhancement
status: Implementing
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
implemented_with: claudecode/opus5
created_at: 2026-09-07 18:35
updated_at: 2026-09-10 16:10
---

## Problem

`ait sync` cannot converge the task-data branch when it is **diverged**
(`local_ahead > 0` **and** `remote_ahead > 0`) and any live session holds a
modified tracked task file. It defers, forever, and reports success.

The gate is `aitask_sync.sh:1279`:

```bash
if (( ${#PROTECTED_DIRTY[@]} )) && [[ "$remote_ahead" -gt 0 ]]; then
    batch_out "DEFERRED:protected_dirty:${#PROTECTED_DIRTY[@]} file(s) held by other sessions"
```

Two correct behaviours combine into a deadlock:

- the sweep **protects** a file whose owning task is held by a live session
  (`_protect "live_lock"`, ~709) rather than sweeping it into someone else's
  commit — the t1599_3 rule, and right;
- the reconcile step is `pull --rebase`, and **git rebase refuses on *any*
  unstaged change**, not merely a conflicting one.

So the protection that makes sync safe is also what blocks it, and
`DEFERRED:` is documented as "deliberately did less than a full cycle and this
is NOT an error" — so nothing escalates. A session parked on an
`AskUserQuestion` (t1725 finding 3 records one parked 16 hours) blocks
convergence for **every** session on the machine.

## Why this is not already covered

Checked against every in-flight sync task before filing:

- **t1725_3** implements the fast-forward half of this gate — its own words:
  "*3c: fast-forward when `local_ahead == 0` and the dirty files are untouched
  by incoming commits*". That is the **behind-only** case. It does not help a
  diverged branch, where no fast-forward exists.
- **t1725** (parent) makes the deferral *visible and actionable* (per-file
  record, holder pane, prompt state, TUI screen, commit-on-behalf). Its
  **explicit non-goal** is that "deferring on another live session's modified
  file is the correct outcome (t1599_3) and stays", and its AC pins that a
  modified tracked file "still defers". This task does not challenge that:
  **nothing here commits, stages or touches another session's file.** It only
  asks whether the *branch* can converge without doing so.
- **t1725_5** offers commit-on-behalf — a manual, per-file user choice. Useful,
  but it resolves the deadlock by taking over another agent's uncommitted work,
  which is exactly what the user should not have to do to run a sync.
- **t1727** makes `task_sync` / `task_push` auto-merge frontmatter conflicts
  like `ait sync` already does. Different failure: a *conflict during* rebase,
  not a tree state that prevents rebase from starting.
- **t1696** covers the hint wording for a *dead* holder / stale lock. Here the
  holders are provably **live**.

The gap is narrow and specific: **the reconcile strategy is hard-coded to
rebase, and rebase's precondition (a clean tree) is strictly stronger than what
convergence actually requires.**

## Evidence — measured on omg16, 2026-09-07

The branch was **6 ahead / 8 behind**, with three modified tracked files held by
two provably live `claude` sessions (pids 363362 → t1599_4, 1551652 → t1721;
both `kill -0` alive, both `ps comm=claude`). `./ait sync --batch` returned:

```
DEFERRED:protected_dirty:2 file(s) held by other sessions
```

exit 0, branch still diverged. t1725_3's fast-forward would not have fired
(`local_ahead` was 6). The branch was then converged by hand with
`git merge origin/aitask-data`, which succeeded cleanly and left all three dirty
files untouched — because `git merge` refuses only when it would **overwrite** a
dirty file, a strictly weaker precondition than rebase's.

Note that t1725's own grounding records the same shape: "a real 21-behind /
39-ahead divergence". Both observed incidents were **diverged**, not behind-only,
which is what makes the fast-forward-only fix insufficient in practice. With two
PCs on the lock branch and many concurrent sessions, diverged is the normal
state, not the exception.

## Goal

When the rebase is blocked by protected dirty files and the branch is diverged,
converge with a **merge** instead of deferring — but only when it is provably
safe, and never by touching a protected file.

## Suggested shape (not prescriptive)

Extend the same gate t1725_3 rewrites (hence the dependency — the two must not
edit it in conflicting ways). Where t1725_3 adds the `local_ahead == 0`
fast-forward, add a diverged branch guarded by three preconditions, **all
computed before anything mutates**:

1. no protected dirty path is touched by any incoming commit
   (`diff --name-only HEAD...origin/<branch>`) — otherwise merge refuses anyway;
2. the local-only and remote-only changed-file sets are **disjoint**
   (`diff --name-only <merge-base> HEAD` vs `<merge-base> origin/<branch>`), so
   the merge has no conflict candidates at all and never needs the union driver
   — which `.gitattributes` does not register, so a conflicting merge could not
   be auto-resolved the way a rebase's can via `try_auto_merge`;
3. the worktree is not mid-rebase/merge (the existing sentinel scan, ~334).

If any precondition fails, defer exactly as today — the fallback narrows the
deadlock, it does not remove the deferral. Report the outcome distinguishably
(e.g. a `MERGED` token, or `SYNCED` with a detail), and add it to
`DEFERRED_REASONS`/`_emitted_tokens`' sibling vocabulary in
`lib/sync_action_runner.py` plus its pinning test, in the same commit.

Decide explicitly whether a merge commit on `aitask-data` is acceptable: it
already carries 4 in the last 300 commits, so it is established practice rather
than a novelty — but the branch is otherwise rebase-linear and that should be a
stated decision, not a side effect.

## Acceptance criteria

- Diverged branch (`local_ahead > 0` and `remote_ahead > 0`) + a modified
  tracked file held by a **live** lock + disjoint changed-file sets →
  `ait sync` converges and pushes; afterwards both
  `./ait git rev-list --count @{u}..HEAD` and `HEAD..@{u}` are 0, and the
  protected file is **still dirty and byte-identical** to before the run.
- Same position but an incoming commit **touches** the protected path → still
  `DEFERRED:protected_dirty`, nothing merged. Negative control.
- Same position but the local-only and remote-only sets **overlap** → still
  defers, rather than producing a conflicted merge the sweep cannot resolve.
- Behind-only (`local_ahead == 0`) still takes t1725_3's fast-forward, not this
  path — the two branches stay distinguishable in the emitted token.
- A mid-rebase worktree still reports `DEFERRED:worktree_wedged` and never
  merges on top of it.
- No test asserts that a protected file was committed, staged, or modified by
  this path.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1725** id=2026-09-09T19:17:29Z.f826ee4f2a778a8790b11aff from=t1725 at=2026-09-09T19:17:29Z base=9cb61927c8910812c2c6a3fa852663cf7ad9bd8e base_branch=main dirty=no host=omg16
>
> | Context from an /aitask-explore session (2026-09-09, omg16) that hit this exact deadlock. Sent via --from 1725 because the explore session held no task; treat the sender as the family, not a verified agent.
> | 
> | **1. A third live measurement, and it satisfies every precondition in your "Suggested shape".**
> | As of this moment (a `git status` reading — not dated by the SHA below): `aitask-data` was 24 ahead / 26 behind; exactly one dirty tracked file, `aiplans/p1725/p1725_3_…md`, held by the live t1725_3 session (status Implementing, plan at Step 9); local-only vs remote-only changed-file sets from the merge-base were disjoint (16 vs 13, `comm -12` empty); no incoming commit touched the dirty path. `_rebase_blocked` clause 3 (`tracked AND local_ahead > 0`, aitask_sync.sh:1375 at this base) is the sole blocker. The guarded merge would have converged it without touching the protected file.
> | 
> | **2. Reframing: on a multi-agent box this is the steady state, not an incident.**
> | The user runs several code agents in parallel continuously, so the data worktree is dirty almost all the time and diverged is the normal branch shape (two PCs + many sessions). Combined with the t1599_3 protection, `DEFERRED:protected_dirty` is therefore effectively permanent, not transient. That argues for treating the guarded merge as the normal reconcile path for diverged branches rather than a narrow fallback — the "stated decision" about merge commits on `aitask-data` that the task asks for should be made with that frequency in mind.
> | 
> | **3. A second, circular surface outside this task's stated scope.**
> | The warning the user actually sees on every `./ait git` metadata write is from `task_data_converge` (lib/task_utils.sh:1594-1601 at this base): when ahead != 0 AND behind != 0 it sets `diverged` and returns WITHOUT attempting anything, and `_task_converge_warn` hints "reconcile with './ait sync'" — which then defers via clause 3. The hint points at a command that cannot act, from every agent, on every write. The seam is deliberately ff-only (t1658_1). Decide explicitly whether the same disjoint-sets/no-incoming-touch guard belongs there too, or at minimum whether the hint should stop naming `./ait sync` when sync is known to defer. Not a request to widen scope — a decision the plan should record, possibly as a follow-up.
> | 
> | **4. Syncer's main-branch pull has the same over-strong precondition.**
> | `_main_pull_worker` (syncer/syncer_app.py:2326-2334 at this base) refuses on ANY non-empty `git status --porcelain` with "Working tree dirty — stash or commit before pulling", before it runs `pull --ff-only` — which itself refuses only when it would overwrite a dirty file. That is the code-branch pull, not the data branch, so it is a separate fix; noted because the user reported "syncer fails because of dirty worktree" and this is the message that string matches. Unconfirmed which message they saw.

> **👁 note:read** id=2026-09-10T12:11:22Z.1bffa899b3705fec97141307 by=t1731 at=2026-09-10T12:11:22Z mode=explicit ids=2026-09-09T19:17:29Z.f826ee4f2a778a8790b11aff

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T13:10:48Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-10T18:07:03Z status=pass attempt=1 type=human
