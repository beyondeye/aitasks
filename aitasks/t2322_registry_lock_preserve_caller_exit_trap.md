---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, shell]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2290
followup_kind: upstream_defect
created_at: 2026-11-17 09:55
updated_at: 2026-11-17 11:41
---

## Origin

Spawned from t2302 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/registry_lock.sh:130,155` — `registry_lock_acquire`
  replaces the caller's EXIT trap with its own release
  (`trap "registry_lock_release '$dir'" EXIT`), and `registry_lock_release` runs
  `trap - EXIT`. Any caller that had its own EXIT trap silently loses it once a
  lock is taken: it is replaced during the hold and cleared after release.
  `ait_archive_rearm_exit_trap` re-arms only the archive sweep, nothing else.

## Diagnostic context

t2302 found this as a test leak. `tests/test_registry_lock.sh` created its
scratch root with `trap 'rm -rf "$TMPROOT"' EXIT`. The first
`registry_lock_acquire` in the suite's own shell replaced that trap, and
`registry_lock_release` cleared it, so the root leaked on every run, including
normal completion. t2302 worked around it test-side, by re-executing the suite
under a parent process that owns the root. The library itself is unchanged.

Production callers already carry workarounds or comments about it, for
example `aitask_fold_mark.sh:780` and `:835`, which note that
`registry_lock_acquire` "has just installed its own" trap. Other callers
(`aitask_shadow_rejected.sh:207`, `aitask_agent_marks.sh:88`,
`aitask_agent_sessions.sh`) should be audited for an EXIT trap set before the
acquire that would be lost.

## Suggested fix

Chain the release into the existing EXIT trap instead of replacing it, and on
release restore the caller's previous trap rather than `trap - EXIT`. Possible
mechanisms are `trap -p` capture/restore, or the existing
`txn_chain_exit_trap` / `_tg_prepend_exit_trap` patterns. Then remove the
caller-side workarounds and keep `tests/test_registry_lock.sh` case 5
("exiting releases the lock") green. Add a case where a caller's own EXIT
handler still runs after acquire+release, and after an exit while the lock is
held.
