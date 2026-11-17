---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-16 18:06
updated_at: 2026-11-17 17:20
completed_at: 2026-11-17 17:20
---

## Origin

Spawned from t2316 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_model_stats_strip.sh:96 — mktemp -d "${TMPDIR:-/tmp}/ait_stats_strip.XXXXXX" work dir leaked into the Python suite's per-run TMPDIR (guard reported "TMPDIR LEFTOVERS (1): ait_stats_strip.r9J2h3" on the final full-suite run); cleanup at :64/:146 apparently misses some exit path — leaking path not yet identified`

## Diagnostic context

- Seen on a full `bash tests/run_all_python_tests.sh` run on 2026-11-16, after
  t2316 had removed every Chromium leftover from the same report. The guard
  (`tests/lib/tmpdir_guard.sh`) printed `TMPDIR LEFTOVERS (1):
  ait_stats_strip.r9J2h3` (warn-only; suite PASSED).
- Earlier runs that day did not report it, so it is path- or timing-dependent
  (not every run). t2316 did not touch this script.
- The script creates `WORK_DIR` at line 96 and removes it at line 64 (an error
  helper) and line 146; an exit route that bypasses both (e.g. a
  `strip_deferred` / early-return path, a signal, or a subshell `exit`) would
  leave it. Which Python test drives it was not identified — start with
  `grep -rln aitask_model_stats_strip tests/`.

## Suggested fix

Install `trap 'rm -rf "$WORK_DIR"' EXIT` right after the `mktemp -d` (or route
every exit through one cleanup), then add a test that runs each exit route
under a private TMPDIR and asserts it is empty
(`bash tests/run_shell_test.sh` shows leftovers for shell tests).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1912_5** id=2026-11-16T20:48:03Z.133b35eee289065ac1dc5e62 from=t1912_5 at=2026-11-16T20:48:03Z base=7d9572c13ee2cafe6110a585c593c21f9990d7a4 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1912_5 (which wrote aitask_model_stats_strip.sh and its tests; code commit 3d4a7472c). This is a likely source, not a proven one: I did not reproduce your leaked ait_stats_strip.r9J2h3 dir.
> | 
> | - tests/test_model_stats_migrate.py::TestNoRemote::test_killed_between_rewrite_and_commit_resumes SIGKILLs the helper on purpose. It sets AIT_STATS_STRIP_AFTER_REWRITE_HOOK to `kill -9 "$AIT_STATS_STRIP_PID"`, which runs after `WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_stats_strip.XXXXXX")"`. A killed process runs no cleanup and no trap, so this test leaves exactly one ait_stats_strip.* dir under the suite's TMPDIR on every run, by construction.
> | - The kill is the point of that test: it proves that a fresh process resumes a strip interrupted between rewrite and commit. So the fix probably belongs in the test, which could remove `$TMPDIR/ait_stats_strip.*` afterwards or give the helper a private TMPDIR. An EXIT trap in the helper would not help against SIGKILL.
> | - Your report says the leak was not seen on every run. That fits only if the module is not always collected, or the guard missed it on those runs, so check that before relying on this explanation.
> | - The other exits: strip_error is only reached before WORK_DIR exists, and strip_deferred and the STRIPPED path both `rm -rf "$WORK_DIR"`. As of the tree at 3d4a7472c, I see no other leaking route.

> **👁 note:read** id=2026-11-17T09:38:17Z.e8feda7e49f6a5e584f55300 by=t2319 at=2026-11-17T09:38:17Z mode=explicit ids=2026-11-16T20:48:03Z.133b35eee289065ac1dc5e62

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T16:41:03Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-17T09:38:58Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-17T15:20:16Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:4fb4ffd190649ed0

> **✅ gate:risk_evaluated** run=2026-11-17T15:20:16Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2319/risk_evaluated_2026-11-17T15:20:16Z-risk_evaluated-a1.log`
