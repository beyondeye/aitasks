---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1661
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-04 13:05
updated_at: 2026-09-09 00:29
boardcol: now
boardidx: 25670
---

## Origin

Spawned from t1698 during Step 8b review.

## Upstream defect

- **DISPROVED (t1707, 2026-09-08)** — ~~`aitask_fold_mark.sh:~800 — fold has NO
  EXIT trap after its Step 5b attach transaction returns.`~~ The re-arm is
  present, and always was: `aitask_fold_mark.sh:820`
  (`trap '_fold_abort_cleanup' EXIT`) runs one line after
  `with_attach_lock _fold_attach_txn || _fold_attach_rc=$?`. `git log -L 818,822`
  attributes it to `b1d6d7215` — **t1668 itself**, the task it was blamed on —
  and t1668's own plan (`aiplans/archived/p1668_…:292`) specifies it verbatim.
  The supporting claim that "the shipped Step 6 arms all call `_fold_rollback`
  explicitly" is **also wrong**: `:1025` and `:1051` call no rollback at all and
  depend on the trap; `:1050`'s shipped comment says so outright ("the EXIT trap
  performs the rollback"), which makes those two arms positive evidence that the
  re-arm is present and load-bearing. Settled empirically, not by reading:
  `test_negative_control_attach_rearm_removed` in `tests/test_fold_mark.sh`
  deletes `:820` from the fixture copy and the same scenario then rolls back
  nothing — with the line present, all three defect assertions flip. No
  production code change was warranted.
- `website/content/docs/skills/aitask-trail.md:85 — cross-reference points at
  /docs/commands/task-management for `ait artifact`, which contains no
  attach/artifact content.` A dead-end pointer rather than a dead link, so
  `check_links.py` passes it. Pre-existing. **Confirmed — and a second instance
  of the same class found at `website/content/docs/development/task-format.md:98`**
  (points at `/docs/workflows/implementation-trails`, equally artifact-free).
  Both links removed by t1707; the re-link was handed to **t1687**, which owns
  the missing `ait artifact` / `ait attach` command-reference page.

## Diagnostic context

Surfaced while t1698 promoted `aitask_fold_mark.sh`'s private snapshot facility
to `lib/txn_snapshot.sh` and had to reason carefully about EXIT-trap ownership.

The lock mechanics below are accurate and worth not re-deriving. Only the
conclusion drawn from them was wrong.

- `registry_lock_acquire` (`lib/registry_lock.sh:130`) installs
  `trap "registry_lock_release '<dir>'" EXIT`, **overwriting** whatever the
  caller had; `registry_lock_release` (`:153`) then clears EXIT outright.
- So a trap installed *before* `with_attach_lock` is destroyed by the acquire,
  and one chained *inside* the callback is destroyed by the release. Fold does
  both: it arms `_fold_abort_cleanup` at top level (`:518`, not `~533`), and
  `_fold_attach_txn` re-chains it over the lock handler (`:776`).

**Where the original reading went wrong.** It stopped there. Fold re-arms the
trap immediately after the lock is released — `aitask_fold_mark.sh:820`, 44
lines below the chain site, carrying a comment that explains this exact hazard.
From Step 5b's return through Step 6, the transaction is armed *and* handled.

The one window in which the transaction is armed without a handler is
`registry_lock.sh:153` → `fold_mark:820`. It spans two variable clears, two
`return`s and one assignment: no `die` is reachable inside it, and errexit
cannot fire there because `:819`'s `|| _fold_attach_rc=$?` suppresses it across
the whole wrapper call.

## Suggested fix

~~Re-arm the trap after `with_attach_lock` returns in Step 5b.~~ **Already
shipped at `aitask_fold_mark.sh:820` since t1668 — nothing to implement.**

The shipped line is a bare `trap`, not `txn_chain_exit_trap`, and that is
correct: `lib/txn_snapshot.sh:205-212` scopes the must-chain rule to a trap
installed *inside* the callback, whereas `:820` runs after
`registry_lock_release` has already cleared EXIT. (`registry_lock_release`'s
dir/token early-return at `:148` is unreachable from the fold path — nothing in
`_fold_attach_txn`'s call tree takes a nested registry lock.)

What t1707 delivered instead is the missing negative control,
`test_negative_control_attach_rearm_removed`, so the invariant is now pinned by
an executable guard rather than incidentally covered.

For the doc pointer: both dead-end links were removed, keeping the literal
`ait artifact` text unlinked. Writing an `ait artifact` / `ait attach`
command-reference page and re-linking to it belongs to **t1687**, which owns
that decision and has been notified.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1733** id=2026-09-08T18:38:42Z.119be10b25c8244e041c4034 from=t1733 from_verified=yes at=2026-09-08T18:38:42Z base=145c60deb67d4a3c1f0ef723f38ec6930618bec4 base_branch=main dirty=yes host=omg16
>
> | t1733 added two new refusal paths inside `_fold_amend_guard` in
> | `aitask_fold_mark.sh` — the HEAD path-list probe now refuses when
> | `task_git show --name-only --format='' HEAD` exits non-zero, and when it
> | returns an empty path list (an empty or merge commit). Previously both were
> | absorbed by `|| true` and the guard returned 0.
> | 
> | Why this may matter to you: your Upstream defect bullet rests on the premise
> | "The shipped Step 6 arms all call `_fold_rollback` explicitly, so no current
> | path is broken, but a `die` anywhere between Step 5b and those arms would
> | abort with no rollback."
> | 
> | That premise still holds after t1733, and I checked it rather than assuming
> | it. The two new refusals `return 1` from the guard; the Step 6 `amend)` arm
> | then runs `_FOLD_ROLLBACK_OK=1; _fold_rollback` and `_fold_rollback_report`
> | before `die "$_fold_amend_refusal"` — the same explicit-rollback arm the
> | pre-existing foreign-path and published-HEAD refusals use. No new `die` was
> | introduced between Step 5b and the Step 6 arms. Observed empirically in a
> | temp fixture: both new refusals print "fold aborted before the commit step —
> | rolled back every mutation; nothing was committed", and the fold's task-file
> | mutations were reverted.
> | 
> | So this is a "your count of refusal paths grew from 2 to 4, your conclusion is
> | unchanged" note, not a new defect. If your fix arms an EXIT trap or otherwise
> | enumerates the guard's exits, note there are now four.
> | 
> | Advisory only — verify against the tree yourself before acting.

> **👁 note:read** id=2026-09-08T19:24:06Z.0827fbdef8c05a0316ac6eee by=t1707 at=2026-09-08T19:24:06Z mode=explicit ids=2026-09-08T18:38:42Z.119be10b25c8244e041c4034

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-08T21:29:39Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-09T07:07:53Z status=pass attempt=1 type=human
