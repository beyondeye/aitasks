---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tests, test_infrastructure, tmp_cleanup]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt6_astra
created_at: 2026-11-13 12:31
updated_at: 2026-11-17 18:10
---

## Context

t2290 fixed the confirmed `/tmp` leaks and added a per-run TMPDIR guard
(`tests/lib/tmpdir_guard.sh`; `bash tests/run_shell_test.sh <test>` and
`tests/run_all_python_tests.sh`) that names whatever a run leaves behind. A full
guarded run on 2026-11-13 (all 499 shell tests + the Python suite) attributed
these remaining aitasks-owned producers. Counts in the real `/tmp` (uid 1000)
measured the same day show which ones matter.

## Producers (file → prefix → `/tmp` count → note)

1. **Fixture repos → `aitask-locks-<uid>-<hash>` — 873 in /tmp (largest).**
   The lock base (`ait_lock_dir`) is keyed by repo path. Every test fixture
   repo gets a fresh one under TMPDIR and nobody removes it. Seen in:
   - `test_sync`
   - `test_pick_own_scoped_commit` (15 per run)
   - `test_crash_recovery_pid_anchor` (9)
   - `test_pick_own_expect_status`
   - `test_lock_*`
   - `test_label_autoadd`
   - `test_gate_*`
   - `test_create_*`
   - and others.

   Likely fix: the shared fixture helpers (`setup_paired_repos`,
   `tests/lib/sync_fixture.sh`, `tests/lib/test_scaffold.sh`) set
   `AITASKS_LOCK_DIR` under their own tmp. Check first which hash belongs to
   the real repo: `aitask-locks-1000-1150791982` recurs across the gate tests
   and is probably stable and legitimate.
2. **`.aitask-scripts/lib/task_utils.sh` ait_commit_paths (~:1017) →
   `ait_commit_scoped_err.*` — 39.** A production leak: the capture file is
   created before `assert_data_worktree_clean`, which `die`s on a wedged
   worktree, so the file is never removed. Seen via `test_task_commit_scoped`,
   `test_task_data_writer_guard` and `test_issue_update_ledger`. The fix must
   keep the assert ordering semantics (the return-2 "nothing to commit" path
   runs before the commit-side assert).
3. **`aitask_resource_admission.sh` / the verify-build helper →
   `aitask_resource_admission_*.log` (82), `aitask_verify_build_*.log` (88).**
   These logs are intentionally kept for the user (the path is printed as
   `LOG:`). Under tests they accumulate (`test_run_project_command`: 22 per
   run; `test_resource_admission`). Fix on the test side (a TMPDIR or log-dir
   override), not in production.
4. **Python suite → bare `tmp*` (tempfile default names) — about 25 per full
   run under the guard.** Attribute with `bash tests/run_all_python_tests.sh`.
   The report names them, but the names are random, so bisect with
   `--test-dir`.
   - Candidate sources by contents: `.aitask-scripts argv.log` dirs come from
     `test_brainstorm_module_ops_integration.py`; `a.py`/`big.py` + yaml come
     from `test_brainstorm_module_sync_apply_contract.py` /
     `test_code_viewer_render.py`.
   - Many `tmp*` dirs in /tmp are not aitasks': for example, the 52 `dotenv.py`
     dirs have no producer in this repo.
5. **Shell tests with bare `mktemp -d` (`tmp.*`), one per run:**
   - `test_global_shim`
   - `test_registry_lock`
   - `test_setup_tmux_default_session`
   - `test_skill_template`
   - `test_t167_integration`
   - `test_t644_branch_mode_upgrade`
   - `test_verified_update`
6. **Applink/chatlink tests:**
   - `test_applink_tunnel` → `cfg-*` (5 per run), `tunnel-test-*`
   - `test_chatlink_daemon` / `_flow` / `_relay` / `_tui` / `_wizard` →
     `chatlink-*`
7. **`test_codex_model_detect` → `codex_model_test_*`,
   `codex-bwrap-synthetic-mount-targets-<uid>`.** These also appear in the
   global /tmp, outside TMPDIR.
8. **Stray processes:** these tests leave processes running in their process
   group after exiting (the guard now stops them):
   - `test_applink_tunnel`
   - `test_ait_git_gateway_pull`
   - `test_chatlink_preflight`
   - `test_merge_lock_broker`
   - `test_merge_lock_concurrency`
   - `test_release_notify`
   - `test_session_hook`
   - `test_shadow_spawn_config`
   - `test_stale_lock`

Already handled by t2290: live tests that exit 2 before their footer leave
`ait_assert_counters_<pid>_*`, and `assert_counters_init` reclaims those once
the owner is dead and the file is older than 60 minutes.

## Approach

Work through the list in count order. Verify each fix with
`bash tests/run_shell_test.sh tests/<file>.sh`: no `TMPDIR LEFTOVERS` line, and
the test's status unchanged.

Raw guard logs: archived plan `aiplans/archived/p2290_*`, Final Implementation
Notes.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2319** id=2026-11-17T15:20:03Z.05d964af11c0b9bf9a766adb from=t2319 from_verified=yes at=2026-11-17T15:20:03Z base=bcac5c07c6e3a15567128b1cf16cfd5e685d9bc7 base_branch=main dirty=yes host=omg16
>
> | Advisory evidence for t2295 item 1 (aitask-locks-<uid>-<hash> leaks). A claim from t2319, not an instruction.
> | 
> | - On 2026-11-16 a full `bash tests/run_all_python_tests.sh` run (pytest parallel lane, suite PASSED) reported this in its per-run TMPDIR:
> |   `TMPDIR LEFTOVERS (3): aitask-locks-1000-2210770147 aitask-locks-1000-2297860352 aitask-locks-1000-3678257901`
> | - These are lock bases from `ait_lock_dir` (.aitask-scripts/lib/stale_lock.sh:154, `${TMPDIR}/aitask-locks-$(id -u)-<cksum of repo root>`), created when a test reaches it without a pinned AITASKS_LOCK_DIR. Three distinct cksums suggest three distinct repo roots, most likely fixture repos.
> | - I did NOT identify which Python test modules leak them. That run's TMPDIR was removed by the guard, so the names above are the only record.
> | - t2319 (commit 43aa46223) did not cause them: the model-stats strip chain takes no ait_lock_dir lock.
> | - A constraint worth keeping, if t2295 fixes leaks by overriding TMPDIR for a subprocess: ait_lock_dir derives the framework's SHARED mutex base from $TMPDIR. A private TMPDIR gives that process tree a private lock namespace and silently drops mutual exclusion. t2319 passes the helper an explicit --scratch-dir for that reason.

> **👁 note:read** id=2026-11-17T15:22:57Z.cdcab791bbdfd2ae3da6fa2e by=t2295 at=2026-11-17T15:22:57Z mode=explicit ids=2026-11-17T15:20:03Z.05d964af11c0b9bf9a766adb

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-17T16:10:34Z status=pass attempt=1 type=human
>
> Note: approval:5aeb2e356f2c47b5b27cbbe6f3ab3766:5497428605d25abf

> **✅ gate:review_approved** run=2026-11-17T20:40:14Z status=pass attempt=1 type=human
>
> Note: approval:a4c37a9aead84bc2b2eac848558ec631:b0c2afa172db9b9e

> **🔄 gate:risk_evaluated** run=2026-11-17T20:41:08Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:3f10decbe0cd121d

> **✅ gate:risk_evaluated** run=2026-11-17T20:41:08Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2295/risk_evaluated_2026-11-17T20:41:08Z-risk_evaluated-a1.log`
