---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [tests, test_infrastructure, tmp_cleanup]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2290
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 13:09
updated_at: 2026-11-17 11:35
completed_at: 2026-11-17 11:35
---

## Problem

t2290 ran all 499 `tests/test_*.sh` through `tests/run_shell_test.sh`
(per-run TMPDIR + leftover report, 2026-11-15). After its fixes these
aitasks-owned producers still leave files in `TMPDIR` (i.e. in `/tmp` on a
plain `bash tests/test_x.sh` run). They are test-side: each production
helper below behaves as designed.

| prefix | tests | producer / cause |
|---|---|---|
| `aitask-locks-<uid>-<cksum>/` | 38 (list below) | `.aitask-scripts/lib/stale_lock.sh` `ait_lock_dir`: a persistent per-user, **per-repo-root** lock base. Each fixture repo has a random path, so each test run adds one dir per fixture repo. Fix: these tests set `AITASKS_LOCK_DIR` (the documented seam) under their own scratch dir |
| `aitask_verify_build_*.log` | test_run_project_command (19/run) | `aitask_run_project_command.sh`: with no `--task-id` it writes a mktemp log for the caller to read (printed on `LOG:`). Fix: export `TMPDIR` under the test's `$TMP` (or remove each reported `LOG:` path) |
| `aitask_resource_admission_*.log` | test_resource_admission | same pattern, `aitask_resource_admission.sh` |
| `ait_commit_scoped_err.*` | test_task_commit_scoped, test_issue_update_ledger, test_task_data_writer_guard | `lib/task_utils.sh` `task_git_commit_scoped`: the mktemp happens before `assert_data_worktree_clean`, which `die`s on a wedged worktree, so the wedge-path tests leak it. Test-side fix: TMPDIR under `$TMP`. (Production residual: one empty file per wedge-die; restructuring the helper around its two dying asserts was judged not worth the risk in t2290.) |
| `tmp.*` (bare `mktemp`) | test_global_shim, test_registry_lock, test_setup_tmux_default_session, test_skill_template, test_t167_integration, test_t644_branch_mode_upgrade, test_verified_update | per-case `mktemp -d` / `mktemp` with no trap, or a later `trap … EXIT` overwriting an earlier one |
| `chatlink*-test-*`, `chatlink_test*` | test_chatlink_daemon, _flow, _relay, _tui, _wizard | fixture dirs not removed (chatlink files were in another session's uncommitted work during t2290, so they were not touched) |
| `tunnel-test-*`, `cfg-*` | test_applink_tunnel | fixture dirs not removed |
| `codex_model_test*` | test_codex_model_detect | fixture dir not removed (the `codex-bwrap-synthetic-mount-targets-<uid>` dir next to it is created by the Codex CLI itself, not ours) |

Tests leaking `aitask-locks-*`: test_anchor_create test_change_surface test_characterize_batch_label_frontmatter test_crash_recovery_pid_anchor test_create_project_flag test_create_silent_stdout test_draft_finalize test_followup_kind_roundtrip test_gate_active_gates test_gate_cli_wiring test_gate_codex_approvals test_gate_guarded_archival test_gate_ledger test_gate_no_double_record test_gate_orchestrator test_gate_pass test_gate_plan_approval_transitions test_gate_procedure_docs test_gate_record test_gate_recorded_pass test_gate_reentry test_gate_risk_verifier test_gate_verifiers test_label_autoadd test_lock_anchor_tmux_live test_lock_force test_lock_live_holder_gate test_lock_reclaim test_parallel_admission_preflight test_pick_own_expect_status test_pick_own_scoped_commit test_pr_contributor_metadata test_premise_baseline_seeding test_query_files_inflight test_run_project_command test_sync test_task_push test_web_merge_materialize 

Not leaks (verified in t2290): `/tmp/ait_isolated_tmux_<uid>` (tests/lib/tmux_isolation.sh, intentionally persistent, reused);
fixed-name `/tmp/work2do*.md`, `/tmp/*_err` in the crew / apply_initializer tests (removed inline, fixed names cannot accumulate).

## Scope

- Fix each row test-side; prefer one run-level scratch dir per test with
  `export TMPDIR="$TMP/tmp"` (pattern used in t2290 for
  test_txn_snapshot.sh / test_release_notify.sh) and, for the lock rows,
  `export AITASKS_LOCK_DIR="$TMP/locks"`.
- Watch for later `trap … EXIT` lines that overwrite the cleanup trap.
- Verify with `bash tests/run_shell_test.sh tests/<t>.sh`: no
  `TMPDIR LEFTOVERS` line, test status unchanged.
- Then consider flipping the guard from warn-only to failing on leftovers
  (decision deferred by t2290 until attribution was complete).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T21:02:34Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-17T07:52:09Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-17T09:35:06Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:9e11a95040171b6c

> **✅ gate:risk_evaluated** run=2026-11-17T09:35:06Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2302/risk_evaluated_2026-11-17T09:35:06Z-risk_evaluated-a1.log`
