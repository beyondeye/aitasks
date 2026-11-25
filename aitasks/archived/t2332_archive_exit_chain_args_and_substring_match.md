---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [bash_scripts, shell]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2290
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-17 23:01
updated_at: 2026-11-25 18:36
completed_at: 2026-11-25 18:36
---

## Origin

Spawned from t2322 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/archive_utils.sh:228 — _ait_archive_exit_chain evals the stored caller trap inside a function installed as a bare `trap _ait_archive_exit_chain EXIT` (:263), so a caller handler reading $1 / "$@" sees an empty argument list (fatal under set -u) whenever the archive sweep wraps it`
- `.aitask-scripts/lib/archive_utils.sh:256 — _ait_archive_wrap_exit_trap's idempotence check (and the chain rewrite at :222) match _ait_archive_cleanup / _ait_archive_exit_chain as SUBSTRINGS, so a caller trap whose quoted data merely names them (e.g. rmdir "$d/_ait_archive_cleanup") is treated as already wrapped and the sweep is silently dropped`

## Diagnostic context

t2322 made `lib/registry_lock.sh` chain the caller's EXIT trap instead of
replacing it, mirroring `_ait_archive_exit_chain`. Plan review then found both
defects in t2322's OWN first version of that chain, and t2322 fixed them there:

- positional parameters: the chain is installed as
  `trap '_registry_lock_exit_chain "$@"' EXIT` (`_REGISTRY_LOCK_CHAIN_CMD`), so
  `"$@"` expands in the exit context and the caller's text, eval'd inside the
  function, keeps `$1`/`$#`/`"$@"`;
- recognition by whole command: `_registry_lock_owned_tail` accepts a wrapper
  only as the whole trap text or as the last command after an unescaped `"; "`
  (escaping decided by backslash-run parity) — never a substring.

The archive sweep has the same two shapes and was left alone (out of t2322's
scope). Consequences today:

- With archive_utils loaded, a caller handler that reads `$1` dies with
  "unbound variable" under `set -u` (and sees no args otherwise), because
  `_ait_archive_exit_chain` is called with none. Through registry_lock the
  chain also reaches the caller via the archive (archive wraps registry_lock's
  chain outermost), so registry_lock's "$@" fix is defeated whenever the sweep
  is armed.
- A caller trap such as `rmdir "$d/_ait_archive_cleanup"` makes
  `ait_archive_rearm_exit_trap` a no-op (substring "already ours"), so the
  sweep is dropped and bundled extractions leak. t2322's
  `tests/test_archive_rearm_exit_trap.sh` M-lit block documents this and
  deliberately does not assert LEFT there.

## Suggested fix

Install the sweep chain as `trap '_ait_archive_exit_chain "$@"' EXIT` (one
constant for install and recognition) and replace the substring `case`
patterns in `_ait_archive_wrap_exit_trap` / `_ait_archive_exit_chain` with
whole-command recognition. Consider moving `_registry_lock_owned_tail` /
`_registry_lock_join` into a shared helper both libs use. Note the shipped
trap text `_ait_archive_exit_chain` is pinned by several tests (archive suite
cases 7, 9, the M matrix's expected restore text) — update them together. Add
the M-lit LEFT assertion once the sweep survives quoted data.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-25T15:49:39Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-25T16:16:14Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-25T16:36:10Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:da7594c801a5148a

> **✅ gate:risk_evaluated** run=2026-11-25T16:36:10Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2332/risk_evaluated_2026-11-25T16:36:10Z-risk_evaluated-a1.log`
