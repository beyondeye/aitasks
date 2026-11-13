---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [tests, test_infrastructure, tmp_cleanup]
created_at: 2026-11-13 12:31
updated_at: 2026-11-13 12:31
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
