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

- [x] **cleanup_lifetime_controls:** Before changing producers, capture the
  current fatal-guard capture-file leak in a disposable repo and the process
  leftovers in the named shell suites. Keep baseline logs outside the inspected
  scratch roots. Inspect files before the enclosing run_tmpdir cleanup can mask
  leaks. Include no-change return 2, an already-wedged repo, and a wedge injected
  between the preflight and the guarded git call. Compare against the same
  controls after implementation. Approved as inline by the user.

## Implementation

1. [x] **Production capture lifetime.** In
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

2. [x] **Attribute and clean remaining Python fixtures.** Run the guarded
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

3. [x] **Own spawned processes in the nine named shell suites.** Baseline and
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

4. [x] **Close the original inventory.** Run representative already-fixed
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

## Post-Review Changes

### Change Request 1 (2026-11-17 22:18)
- **Requested by user:** Preserve the caller's descriptors during fatal scoped-commit cleanup; own and reap the broker suite's b20, w22 and w22c background workers on early exits.
- **Changes made:** Confirmed both findings. The commit helper now selects two unused descriptors and invokes its capture body with scoped redirections, leaving caller-owned descriptors untouched even while EXIT runs. The capture is still unlinked before guarded calls and no caller trap is changed. The regression EXIT handler itself writes to descriptors 8–11; all cases also use TMPDIR paths containing spaces and a quote. Broker workers are registered immediately in their owning shell, have private process groups for descendant cleanup, and are deregistered after normal completion. Suite cleanup drains workers before anchors and fixture directories.
- **Verification:** The reviewed helper fails 9 of the extended 105 checks; the corrected helper passes 105/105. Extended early-exit controls cover b20 while polling, w22 after its first rendezvous returns P, and w22c after its first rendezvous returns x. All three workers survive baseline EXIT cleanup; none survives corrected EXIT cleanup, checked before the control's own cleanup. Every injected exit retains status 7. Strict guarded suites: commit_capture_cleanup 105/105, task_commit_scoped 80/80, task_data_writer_guard 148/148, issue_update_ledger 141/141, merge_lock_broker 138/138, merge_lock_concurrency 42/42; no file/process guard warnings. Earlier full Python results remain applicable to the unchanged Python fixture change.
- **Control evidence:** `/tmp/t2295-evidence/broker_worker_controls.py`, `broker-workers-before.log`, `broker-workers-after.log`, `descriptor-before.log`, and `descriptor-final.log`. The control waits for the suite process with output redirected to files, so inherited output pipes cannot delay observation until a leaked child eventually exits.
- **Files affected:** `.aitask-scripts/lib/task_utils.sh`, `tests/test_commit_capture_cleanup.sh`, `tests/test_merge_lock_broker.sh`.

### Change Request 2 (2026-11-17 22:31)
- **Requested by user:** Remove the descriptor allocator's fixed 10–63 ceiling, which changed an unchanged-file --no-stage call from return 2 to return 1 despite free higher descriptors; add an occupied-range control.
- **Changes made:** Confirmed the regression in a real disposable Git repository. The allocator now searches up to the process's soft descriptor limit from `ulimit -n`, with no artificial ceiling when the limit is unlimited. It continues to skip caller-owned descriptors. Added cases with every descriptor 10–63 occupied for an unchanged tracked file (return 2), a changed tracked file (successful commit), and a fatal MERGE_HEAD guard, retaining the existing EXIT-handler descriptor and capture-cleanup assertions.
- **Verification:** The previous allocator fails seven assertions in the extended suite. The revised helper passes 140/140. Strict guarded task_commit_scoped 80/80, task_data_writer_guard 148/148, and issue_update_ledger 141/141 also pass without file/process guard warnings. Bash syntax and diff checks pass; no new non-source ShellCheck diagnostics. Evidence: `/tmp/t2295-evidence/fd-range-before.log`, `commit_capture_cleanup-fd-range.log`, and `fd-range.status`.
- **Files affected:** `.aitask-scripts/lib/task_utils.sh`, `tests/test_commit_capture_cleanup.sh`.

## Final Implementation Notes
- **Actual work done:** Fixed scoped-commit stderr capture lifetime; removed nested subshell ownership from both merge test anchor helpers and all three red-proof calls; explicitly reaped and deregistered proof/N=51 workers; fixed shell/sleep process fixtures; scoped screenshot recipe lock bases to each disposable session.
- **Deviations from plan:** Used two unused, scoped file descriptors selected up to the process soft limit over an immediately unlinked capture file instead of composing EXIT traps. Fatal guards retain current-shell semantics, caller traps are unchanged, caller-owned descriptors remain untouched even during fatal EXIT handlers, and no capture pathname remains during guarded calls. `exec sleep` preserves the gateway/release holder PID and start identity. Session-hook argv fixtures retain the Bash process and park on a builtin FIFO read. No shared Python fixture change was needed: all three remaining lock bases came from one screenshot replay test. Shadow-spawn was already clean; stale-lock gained explicit wait/early cleanup despite a clean baseline.
- **Issues encountered:** The baseline complete Python run had two unrelated concern-picker color assertions (expected #ff0000, actual #363636); 12,517 parallel and 56 serial tests passed, with seven skips. Python attribution identified `AgentsDatasetTests::test_the_shipped_multi_pane_recipes_replay` as the sole producer of three lock directories. The initial direct capture test needed to chdir into its fixture so the fatal guard examined the fixture gitdir; a new assertion now verifies that fatal guards exit the calling shell.
- **Key decisions:** Keep production lock namespace and intentional LOG retention unchanged. Fixture setup and panes for a screenshot session share a lock base; distinct sessions have distinct bases. Background merge workers own separate process groups for early-failure cleanup; ordinary completion waits and removes their registrations. All three proof calls record exactly three PIDs and assert their absence before suite EXIT and the outer guard.
- **Verification:** Direct helper checks 140/140 after descriptor and occupied-range review; old-library negative control fails exactly the three capture-lifetime assertions. Merge broker 138/138 after worker review; merge concurrency 42/42 including preserved red/negative concurrency assertions and twelve ownership/liveness checks. An external mutation restoring all three enclosing substitutions fails exactly the three owner-registration checks. Injected early exits preserve status 7 and leave zero of the recorded proof children, broker anchor, and b20/w22/w22c workers before any outer guard. All nine named process suites pass under strict guard with no file/process leftovers. Syntax checks pass; ShellCheck introduces no non-source diagnostics.
- **Final full-suite result:** 12,517 parallel tests and all 56 serial live tests passed; seven skipped; the same two baseline concern-picker color assertions failed. The changed screenshot recipe passed. The guard reported no leftover files or processes, versus three lock directories in the baseline. All fourteen representative shell suites passed without guard leftovers.
- **Original producer inventory:** (1) historical shell fixture lock bases already addressed by t2302; remaining Python recipe bases fixed here; (2) production capture leak fixed here; (3) intentional production LOG files retained, test containment from t2302 verified; (4) historical Python bare-temp candidates already fixed, full baseline reports only the three attributed lock bases; (5) historical shell bare-temp roots already fixed by t2302, representative checks; (6) wrapper temp roots already fixed, remaining process leaks fixed here; (7) model-detection cleanup already implemented by t2302 with recorded PASS/FAIL stub controls, no live model calls run here; (8) six process leaks reproduced and fixed, stale-lock cleanup hardened, shadow-spawn already clean.
- **Upstream defects identified:**
  - `tests/test_concern_picker_modal.py` — two pre-existing resolved-color assertions fail in the baseline full Python suite (expected #ff0000, actual #363636); not modified in this task.
