---
Task: t2295_fix_remaining_test_tmp_leak_producers.md
Base branch: main
Output branch: main
---

# t2295 — Fix remaining test temporary-file and process leaks

## Current evidence and scope

The task's November 13 inventory predates fixes already on main. Archived plan
`aiplans/archived/p2302_keep_remaining_shell_test_temp_files_in_their_scratch_dir.md`
records 54 passing shell suites with zero guarded leftovers, using
`tests/lib/run_tmpdir.sh`. Its work covers the listed fixture lock bases,
intentional production logs, bare shell temporary directories and chatlink
wrappers. Preserve that implementation and verify representative cases.

The named Python brainstorm fixtures now remove their temporary repositories,
and `test_code_viewer_render.py` uses TemporaryDirectory contexts. The advisory
inbox note from t2319 reports three remaining Python-suite lock bases but does
not attribute their modules. A fresh run must establish what still leaks.

Confirmed remaining defects in the current tree:
- `task_git_commit_scoped` in `.aitask-scripts/lib/task_utils.sh` allocates
  `ait_commit_scoped_err.*` before fatal add/commit worktree guards.
- `tests/test_merge_lock_broker.sh` and `tests/test_merge_lock_concurrency.sh`
  update ANCHORS inside `$(spawn_anchor)`, losing the cleanup list.
- `test_merge_lock_concurrency.sh` also invokes run_red_proof through two
  command substitutions and one command-substitution pipeline (cases 1, 1n,
  and 5). Fixing only spawn_anchor still loses ANCHORS and BGPIDS in those
  enclosing subshells; the ownership fix must cover the full invocation chain.
- Several process fixtures terminate a shell whose child sleep survives.

Work on main under the fast profile. Check target-file diffs immediately before
editing and preserve concurrent work. No live model calibration calls and no
cleanup of pre-existing global /tmp entries. Do not change production TMPDIR or
the production lock namespace to fix fixture leaks.

### Pre-phase (risk mitigations)

- [ ] **cleanup_lifetime_controls:** Before changing producers, capture the
  current fatal-guard capture-file leak in a disposable repo and the process
  leftovers in the named shell suites. Keep baseline logs outside the inspected
  scratch roots. Inspect files before the enclosing run_tmpdir cleanup can mask
  leaks. Include no-change return 2, an already-wedged repo, and a wedge injected
  between the preflight and the guarded git call. Compare against the same
  controls after implementation. Approved as inline by the user.

## Implementation

1. [ ] **Production capture lifetime.** In
   `.aitask-scripts/lib/task_utils.sh::task_git_commit_scoped`, give the stderr
   capture an explicit owner on fatal exits as well as normal returns. Preserve
   the existing caller's EXIT handler and its incoming exit status; use the
   shell-quoted trap composition pattern documented by
   `lib/txn_snapshot.sh::txn_chain_exit_trap`, without introducing a circular
   library dependency. Remove only this invocation's capture, restore the
   previous trap on normal returns, and keep mktemp failure nonfatal. Delay
   allocation until needed where possible. Keep guards fatal in the calling
   shell, retain add-error precedence, clear stale AIT_COMMIT_SCOPED_ERR on
   entry, and keep no-change return 2 before the commit-side assertion.
   Extend `tests/test_task_commit_scoped.sh` or add a focused
   `tests/test_commit_capture_cleanup.sh` for direct helper calls, covering
   both staging modes, failure diagnostics, existing traps and the race seam.

2. [ ] **Attribute and clean remaining Python fixtures.** Run the guarded
   Python suite without concurrent shell tests. If lock-base leftovers recur,
   narrow the producing modules with guarded subsets (preserve real __file__
   paths and imports). Inspect fixture subprocess calls, starting with
   `tests/test_gate_ledger_python_parser.py`,
   `tests/test_board_scoped_task_commit.py`,
   `tests/test_premise_baseline_board_roundtrip.py`,
   `tests/test_board_detail_followup_kind.py` and shared fixture helpers.
   Bind a fixture-specific AITASKS_LOCK_DIR under its TemporaryDirectory when
   the process operates exclusively on that fixture, restoring the environment
   afterwards. Related processes for the same fixture must share the override;
   separate repos must remain independent. For any confirmed bare-temp leak,
   use TemporaryDirectory/context cleanup or immediate addCleanup registration.
   Modify only attributed producers; record already-fixed candidates as such.

3. [ ] **Own spawned processes in the nine named shell suites.** Baseline and
   fix `test_applink_tunnel`, `test_ait_git_gateway_pull`,
   `test_chatlink_preflight`, `test_merge_lock_broker`,
   `test_merge_lock_concurrency`, `test_release_notify`, `test_session_hook`,
   `test_shadow_spawn_config` and `test_stale_lock` as evidence requires.
   - Change merge-test spawn_anchor to a direct function call with an output
     variable (e.g. `spawn_anchor A0`), so children and PID bookkeeping belong
     to the suite's owning shell; terminate and wait for owned children before
     deleting fixture directories.
   - Change run_red_proof to `run_red_proof <mode> <result_variable>` and call
     it directly in the owning shell in all three places (cases 1, 1n, 5).
     Return the verdict with `printf -v` using a name that does not collide
     with a function-local variable. Replace case 5's pipeline with the direct
     call followed by `${res##*|}`. Keep the existing rendezvous, contamination,
     BUSY:tA and negative-control assertions unchanged.
   - Each proof invocation must terminate and wait for its two anchors and
     broker worker before returning, then deregister their PIDs from the
     suite cleanup lists. Keep the owning-shell EXIT fallback armed throughout
     for early failures. Audit every spawn_anchor/run_red_proof call for
     enclosing substitutions, pipelines, background functions and subshells;
     checking only the immediate call is insufficient. Apply the same ownership
     rule to the N=51 worker launch and cleanup lists.
   - Use `exec sleep` for fake executables where a standalone long-lived
     process is the intended contract (applink/chatlink timeout stubs).
   - Where shell ancestry or lock-holder identity is itself under test,
     preserve it and explicitly track/reap the sleep child instead. Register
     cleanup immediately after spawning, including early-failure exits.
   - Investigate the current shadow dry-run test before editing; if its
     historical leak no longer reproduces, document that outcome.
   - Do not broaden cleanup to unrelated PIDs or rely on the outer guard to
     kill processes that the test should own.

4. [ ] **Close the original inventory.** Run representative already-fixed
   suites from t2302: sync, pick_own_scoped_commit, task_data_writer_guard,
   issue_update_ledger, run_project_command, resource_admission, registry_lock,
   global_shim, skill_template and the chatlink wrappers. Verify Codex model
   detection only with a stub if additional changes prove needed; retain its
   intentional failed-run evidence. Document each original producer category
   as fixed here, already fixed, intentionally retained, or unable to verify
   with a concrete reason. Investigate new attributable leaks found by these
   runs within this task.

## Verification

- Run changed shell suites using `AIT_TMPDIR_GUARD_STRICT=1 bash
  tests/run_shell_test.sh tests/<name>.sh`. Require unchanged passing status,
  no TMPDIR LEFTOVERS and no stray-process guard message. A nonzero baseline
  must be diagnosed rather than hidden by cleanup.
- Direct production-helper regression checks must inspect the scratch root
  before any suite-level cleanup; assert caller EXIT handlers still run and
  receive the original failure status. Verify no-change return 2 on a wedged
  repo with --no-stage, normal success, add failure, commit failure, mktemp
  failure, and the pre-git wedge seam. Use the old library in an isolated
  fixture as a negative control for newly added leak assertions.
- For each of the three run_red_proof invocations, record exactly its owned
  anchor and worker PIDs and assert they are gone immediately after it returns,
  before suite EXIT or the outer guard runs. Run disabled, enabled and repeated
  disabled proofs and retain their existing concurrency assertions. Include a
  negative control that restores an enclosing command substitution: ownership
  registration or immediate liveness checks must fail. Exercise an early exit
  after spawning to verify the suite fallback reaps the same owned children.
- Run the complete guarded Python suite after fixture changes, separately
  from shell tests. Record test counts, suite verdict, and leftover report.
  Use bounded workers; no blanket run of live shell/model tests.
- Run bash syntax checks and targeted shellcheck on changed shell code;
  distinguish pre-existing warnings from new ones.
- Recheck all final diffs and ensure only task-owned paths enter the review
  and commit. Preserve production LOG paths and lock mutual exclusion.

## Step 9

After implementation, consolidate results, request implementation review,
commit through the Codex approval broker, run declared gates, and archive the
task and plan with the standard Step 9 workflow. Task data commits remain
separate from the code commit `bug: Fix remaining temporary resource leaks (t2295)`.

## Risk

### Code-health risk: medium
- Fatal-guard handling is shared by production writers; trap composition could
  alter exit status or suppress an existing cleanup handler. · severity: medium
  · → mitigation: inline pre-phase cleanup_lifetime_controls; focused direct
  helper tests in Verification.
- Process fixtures deliberately exercise ancestry and liveness, so replacing
  all sleeps with exec would weaken their assertions. · severity: low
  · → mitigation: inline pre-phase cleanup_lifetime_controls; preserve ancestry
  where it is the tested behavior.

### Goal-achievement risk: medium
- The historical inventory includes already-landed fixes and unidentified
  Python producers; an outer scratch cleanup can conceal a live production
  leak. · severity: medium · → mitigation: inline pre-phase
  cleanup_lifetime_controls and module attribution before edits.
- Nested proof subshells can discard PID registration even after fixing the
  immediate spawn helper. · severity: low · → mitigation: inline pre-phase
  cleanup_lifetime_controls; direct proof calls and per-invocation liveness
  checks before any outer cleanup.
- The guard sees TMPDIR and its process group only; it cannot prove absence of
  every hard-coded global path or detached process. · severity: low
  · → mitigation: inspect named producer paths and owned process lifetimes;
  state verification limits explicitly.

### Planned mitigations
- timing: pre-phase | name: cleanup_lifetime_controls | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: production exit semantics and cleanup hidden by outer guards | desc: Capture fatal-guard and process-lifetime failures before edits, then repeat identical controls after fixes
