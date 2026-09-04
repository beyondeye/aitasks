---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, robustness]
anchor: 1661
followup_kind: upstream_defect
created_at: 2026-09-04 13:05
updated_at: 2026-09-04 13:05
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
