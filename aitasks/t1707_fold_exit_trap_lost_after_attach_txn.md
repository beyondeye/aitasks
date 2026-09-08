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

- `aitask_fold_mark.sh:~800 — fold has NO EXIT trap after its Step 5b attach
  transaction returns.` `registry_lock_release` runs `trap - EXIT`, clearing the
  `_fold_abort_cleanup` handler that `_fold_attach_txn` chained on. The shipped
  Step 6 arms all call `_fold_rollback` explicitly, so no current path is broken,
  but a `die` anywhere between Step 5b and those arms would abort with no
  rollback. Pre-existing (t1668).
- `website/content/docs/skills/aitask-trail.md:85 — cross-reference points at
  /docs/commands/task-management for `ait artifact`, which contains no
  attach/artifact content.` A dead-end pointer rather than a dead link, so
  `check_links.py` passes it. Pre-existing.

## Diagnostic context

Surfaced while t1698 promoted `aitask_fold_mark.sh`'s private snapshot facility
to `lib/txn_snapshot.sh` and had to reason carefully about EXIT-trap ownership.

The relevant mechanics, established there and worth not re-deriving:

- `registry_lock_acquire` (`lib/registry_lock.sh:130`) installs
  `trap "registry_lock_release '<dir>'" EXIT`, **overwriting** whatever the
  caller had; `registry_lock_release` then clears EXIT outright with `trap -
  EXIT`.
- So a trap installed *before* `with_attach_lock` is destroyed by the acquire,
  and one chained *inside* the callback is destroyed by the release. Fold does
  both: it arms `_fold_abort_cleanup` at top level (line ~533), `_fold_attach_txn`
  re-chains it over the lock handler, and the release then clears the whole
  chain when Step 5b returns successfully.
- From that point to Step 6, fold is running an armed transaction
  (`_fold_txn_active=true`) with no handler to fire it.

Not reachable by any shipped path today — every Step 6 failure arm calls
`_fold_rollback` by hand — which is why t1698 deliberately left it alone rather
than fixing it opportunistically inside an unrelated change.

The second defect is a documentation cross-reference noticed while updating the
same page for t1698's user-visible behaviour change.

## Suggested fix

Re-arm the trap after `with_attach_lock` returns in Step 5b — the same
`txn_chain_exit_trap '_fold_abort_cleanup'` call the transaction already uses,
issued once more after the lock is released. Verify with a fault injected
between Step 5b and Step 6 (no shipped path reaches there, so the test needs an
injected `die`, and should say so in its comment rather than reading as a
production scenario).

For the doc pointer: either give `ait attach` / `ait artifact` a section in
`website/content/docs/commands/task-management.md` (there is currently none) or
retarget the link.

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
