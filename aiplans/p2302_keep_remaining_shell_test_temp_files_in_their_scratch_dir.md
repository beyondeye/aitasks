---
Task: t2302_keep_remaining_shell_test_temp_files_in_their_scratch_dir.md
Base branch: main
Output branch: main
---

# t2302 — Keep the remaining shell tests' temp files in their scratch dir

## Context

t2290 added `tests/run_shell_test.sh` (per-run `TMPDIR` + `TMPDIR LEFTOVERS`
report) and listed the aitasks-owned producers that still leave files in
`TMPDIR` (i.e. `/tmp` on a plain run). This task fixes them test-side.

**Baseline, measured 2026-11-16** (all 56 listed files run via
`run_shell_test.sh`, all exit 0):

- 52 files leave leftovers, matching the task's table.
- `test_verified_update` is already clean: no change.
- `test_codex_model_detect` is a **live** calibration test (56 real Codex CLI
  calls). It was started by mistake during the baseline and stopped after about
  12 calls. It leaves `codex_model_test_*`. It will **not** be run live again;
  it is verified with a stub `codex`.
- **New finding:** `aitask-locks-1000-1150791982` appears in 20 tests. It is the
  cksum of the **real repo root**. Those tests run the real `.aitask-scripts/`
  and take locks in the live per-repo lock namespace
  (`/tmp/aitask-locks-<uid>-<cksum>`) that real `ait` commands use. On a plain
  run the fixed name means it does not pile up, but it is a test-isolation
  hole. The same redirect closes it.

**Root causes, by family:**

- **Lock bases.** `ait_lock_dir` (`.aitask-scripts/lib/stale_lock.sh:144`)
  defaults to `${TMPDIR:-/tmp}/aitask-locks-<uid>-<cksum(repo root)>`.
- **`*.log` and `ait_commit_scoped_err.*`.** The producers do a `mktemp` in
  `$TMPDIR` that the caller is meant to read or that a `die` path strands.
- **`tmp.*`.**
  - A per-case `mktemp -d` with no removal (`test_global_shim` `TMPDIR_2`).
  - `$(mktemp -d)/sub` where only `sub` is removed (`test_t167_integration`,
    `test_t644_branch_mode_upgrade`).
  - An EXIT trap overwritten later: `test_skill_template:187`.
    `test_registry_lock` also loses its trap, because
    `registry_lock_acquire` installs its own EXIT trap and
    `registry_lock_release` runs `trap - EXIT`
    (`.aitask-scripts/lib/registry_lock.sh:130,155`).
- **Python fixtures.** The chatlink, applink and codex wrappers create
  `tempfile.mkdtemp` dirs and never remove them.

## Approach

**One run-level `TMPDIR` per test file, removed by that file's own cleanup.**
Everything that honours `$TMPDIR` then lands in a directory that gets cleaned:
`mktemp`, Python `tempfile`, and the default lock base.

I redirect `TMPDIR` rather than export `AITASKS_LOCK_DIR` (which the task text
suggests), for two reasons:
- The lock base keeps its real per-repo-root namespacing. `AITASKS_LOCK_DIR`
  would make every fixture repo in a file share one base, a behaviour change
  the tests never had.
- The same redirect also covers the `*.log`, `ait_commit_scoped_err.*`,
  `tmp.*` and Python rows.

**An inherited `AITASKS_LOCK_DIR` would defeat the redirect.** `ait_lock_dir`
(`stale_lock.sh:146`) gives that variable precedence over `TMPDIR`. So if the
caller's environment exports it, a suite would lock in the caller's shared
directory, outside any guard. Suite setup therefore **unsets the inherited
value**. Two suites set it on purpose, `test_issue_update_ledger:62` and
`test_gate_codex_approvals:759`, and both settings come after setup, so they
still apply. So do per-command `AITASKS_LOCK_DIR=… cmd` prefixes
(`test_pick_own_scoped_commit`, `test_task_data_writer_guard`).

No production script changes.

### 1. New helper `tests/lib/run_tmpdir.sh` (every edited suite calls it)

It is sourced and bash-3.2-safe, with an idempotent load guard like
`fixture_root.sh`.

- `run_tmpdir_init <label> [<parent>]`:
  - Must run in the suite's **top-level shell**, after `enter_scratch_cwd` (so
    the shared `ait-test-cwd-<uid>` stays where it is). Never inside `$( )`.
  - Validates `<label>` against `^[A-Za-z0-9_]+$`.
  - `mktemp -d "${<parent>:-${TMPDIR:-/tmp}}/<label>_run_XXXXXX"`, then resolves
    the physical path (`cd … && pwd -P`, as `fixture_root_init` does). With
    `<parent>` (the suite's existing root, which its own cleanup already
    removes), the caller registers nothing more.
  - Sets `RUN_TMPDIR`, runs `export TMPDIR="$RUN_TMPDIR"`, and runs
    **`unset AITASKS_LOCK_DIR`** (see above). The header explains why, and
    says that a case wanting an override must set it after this call.
  - Exits 1 with `FAIL: …` on failure, the same contract as
    `fixture_root_init`.
  - It installs **no trap**. Most adopting files install their own
    `trap … EXIT` later and would silently replace it (the t2290 lesson).
- `run_tmpdir_cleanup`: idempotent. Runs `chmod -R u+w` (some fixtures
  `chmod a-w`), then `rm -rf -- "$RUN_TMPDIR"`. Never fails.
- The header documents how a caller registers the root with **an owner that
  survives early exits**, following the rule in §2.

### 2. Apply per file, choosing the pattern by the file's existing cleanup

Before editing each file, run the shared_file_gate check (see Pre-phase).
Every call site gets one short comment pointing at `tests/lib/run_tmpdir.sh`
(t2302). The call always comes **before** the suite's first producer: before
any real-repo script call (this closes the live-namespace hole above) and
before any deliberate `AITASKS_LOCK_DIR` assignment.

**Ownership rule:** the root must be removed on early exits too, not only at
the footer.
- If neither the file nor anything it sources installs an EXIT trap (check
  with grep), add `trap run_tmpdir_cleanup EXIT`.
- If an EXIT trap exists, register the root inside that trap's function or
  array.
- A footer loop alone is never the only owner.

- **A. One existing root plus a trap → `run_tmpdir_init <label> "$ROOT"`**,
  placed right after the root's trap. Nothing more to register.
  - Files: `test_change_surface` (FIXTURE_ROOT), `test_create_project_flag`,
    `test_gate_codex_approvals`, `test_gate_ledger`, `test_gate_record`,
    `test_issue_update_ledger`, `test_parallel_admission_preflight`,
    `test_resource_admission`, `test_setup_tmux_default_session`.
  - Exception: if a file creates lock dirs or logs **before** its root
    exists, use a standalone root created earlier instead.
- **B. `CLEANUP_DIRS` array → `run_tmpdir_init <label>` plus
  `CLEANUP_DIRS+=("$RUN_TMPDIR")`**, placed right after `CLEANUP_DIRS=()`.
  - If the array is drained only by a footer loop, with no trap, also add
    `trap run_tmpdir_cleanup EXIT` (ownership rule).
  - Files: `test_anchor_create`, `test_characterize_batch_label_frontmatter`,
    `test_create_silent_stdout`, `test_followup_kind_roundtrip`,
    `test_label_autoadd`, `test_task_push`, `test_premise_baseline_seeding`,
    `test_pick_own_expect_status`, `test_query_files_inflight`,
    `test_gate_recorded_pass`, `test_gate_reentry`,
    `test_gate_guarded_archival`, `test_gate_plan_approval_transitions`, and
    every fixture-root `test_gate_*` / `test_web_merge_materialize` /
    `test_run_project_command` file.
  - The helper call comes **before** any real-repo script call, which is what
    closes the live-namespace hole above.
- **C. No cleanup mechanism → helper plus `trap run_tmpdir_cleanup EXIT`.**
  - Files: `test_crash_recovery_pid_anchor`, `test_draft_finalize`,
    `test_lock_force`, `test_lock_live_holder_gate`, `test_lock_reclaim`,
    `test_pick_own_scoped_commit`, `test_pr_contributor_metadata`,
    `test_sync` (it has only `trap '' TERM`), `test_global_shim`,
    `test_t167_integration`, `test_t644_branch_mode_upgrade`, and the Python
    wrappers `test_chatlink_daemon`, `test_chatlink_flow`, `test_chatlink_tui`,
    `test_chatlink_wizard`, `test_applink_tunnel`.
  - Before adding the trap, confirm with grep that the file and its sourced
    libs install no other EXIT trap.
- **Special cases:**
  - `test_lock_anchor_tmux_live`: call the helper and add
    `run_tmpdir_cleanup` to `cleanup()` **after** `kill-server`, so the pane
    holding TMPDIR is gone first.
  - `test_chatlink_relay`: Parts 1 and 2 (lines 59 and 480, the Python steps
    that leave `chatlink_test_*`) run **before** the file's only EXIT trap,
    which is at line 524. So:
    - Call `run_tmpdir_init chatlink_relay` at the top, and **immediately
      after it** add `trap run_tmpdir_cleanup EXIT`.
    - Line 524 becomes
      `trap 'rm -rf "${E2E_TMP:-}"; run_tmpdir_cleanup' EXIT`. It extends the
      trap instead of replacing it. `E2E_TMP` also lives under the run root, so
      either removal is enough.
  - `test_task_commit_scoped`: call the helper **before** sourcing
    `sync_fixture.sh`, so `_SYNC_FIXTURE_BASE` lands under the run root. After
    sourcing, chain `trap '_sync_fixture_cleanup; run_tmpdir_cleanup' EXIT`.
  - `test_task_data_writer_guard`: same ordering, and add
    `run_tmpdir_cleanup` to the line-40 trap.
  - `test_skill_template`: line 187 `trap unit_cleanup EXIT` replaces the
    `TMP_DIR` trap. Make `unit_cleanup` also `rm -rf "$TMP_DIR"`, then use
    pattern A.
  - `test_registry_lock`: **re-exec under an owning parent.** Inside the
    suite's own shell, no EXIT trap can own the root:
    `registry_lock_acquire` replaces the trap (`registry_lock.sh:130`) and
    `registry_lock_release` clears it with `trap - EXIT` (`:155`). So the
    owner must live in a process the library never runs in. At the top of the
    file, before sourcing the library:
    ```bash
    if [[ -z "${_AIT_REGLOCK_TEST_ROOT:-}" ]]; then
        _root="$(mktemp -d "${TMPDIR:-/tmp}/test_registry_lock_XXXXXX")" || exit 1
        trap 'chmod -R u+w "$_root" 2>/dev/null; rm -rf -- "$_root"' EXIT
        trap 'exit 129' HUP; trap 'exit 130' INT; trap 'exit 143' TERM
        _AIT_REGLOCK_TEST_ROOT="$_root" bash "${BASH_SOURCE[0]}" "$@"
        exit $?
    fi
    TMPROOT="$_AIT_REGLOCK_TEST_ROOT"
    run_tmpdir_init registry_lock "$TMPROOT"
    ```
    - The child keeps every case unchanged. Case 5, "exiting releases the
      lock", still runs the library's own trap in its subshell.
    - The child's old `TMPROOT=$(mktemp -d)` and its EXIT trap are removed;
      the parent owns the root.
    - The parent removes the root whatever way the child ends: normal
      completion, `exit`, a library trap swap, or a signal. A signal is
      deferred while the parent waits on its foreground child, then handled.
    - The production trap-clobbering (any caller's own EXIT trap is lost) is
      offered as an upstream follow-up at Step 8b, not fixed here.
  - `test_codex_model_detect`:
    - Add `KEEP_RESULTS=0` and
      `trap '[[ $KEEP_RESULTS == 1 ]] || rm -rf "${RESULTS_DIR:-}"' EXIT`.
    - The FAIL branch sets `KEEP_RESULTS=1` and prints
      `Results kept for inspection: $RESULTS_DIR`.
    - The `Results dir:` line stays as it is.
    - Result: a passing or interrupted run cleans up, and a failing run keeps
      its evidence.

### 3. Leftover guard: add an opt-in strict mode, keep warn-only as the default

- `tests/lib/tmpdir_guard.sh`: `tmpdir_guard_end` sets `_TG_LEFTOVER_COUNT`
  to the reported count **only when the inspection actually ran**, meaning the
  guard dir existed and the `find` listing succeeded. It sets the count to 0
  when the dir no longer exists, since nothing is left. In every other case,
  including a guard that never started, it stays empty, which fails closed.
- `tests/run_shell_test.sh`, with `AIT_TMPDIR_GUARD_STRICT=1`:
  - **The guard cannot start** (`tmpdir_guard_begin` fails, e.g. an invalid or
    unwritable `TMPDIR`) → print
    `TMPDIR GUARD: strict mode needs the guard, which could not start — not running the test`
    and exit 2. The test is not run unguarded.
  - The test exits 0 but `_TG_LEFTOVER_COUNT` is empty or greater than 0 →
    print `TMPDIR GUARD: strict mode — leftovers (or no inspection) turn a pass into a failure`
    and exit 1.
  - A failing test keeps its own exit status.
  - Default mode is unchanged: on a guard-start failure it still warns and
    runs the test unguarded (`|| true`).
- **Decision recorded:** the default is not flipped. Only these 56 files were
  re-measured, not all ~500 shell tests. The Python runner shares the guard
  and its leftovers were never attributed. A blanket flip would also run live
  tests such as `test_codex_model_detect`. Strict mode makes the later flip a
  one-line change.
- Update the CLAUDE.md "Hunting `/tmp` leaks" paragraph with one sentence on
  `AIT_TMPDIR_GUARD_STRICT=1`.

### Pre-phase (risk mitigations)

1. [shared_file_gate] Immediately before editing each target file, and again
   just before committing, run `git status --short -- <file>` and
   `git diff --stat -- <file>`.
   - A file with foreign uncommitted hunks is **not edited**. Skip it and
     report it, because another session owns the file right now.
   - The commit names explicit paths only (`git commit -- <paths>`), never the
     index.

## Verification

**Ordering:** capture the pre-fix controls in 4b, 4c and 4d
(`test_gate_pass`, `test_registry_lock`, `test_chatlink_relay`) **before**
editing those three files, as the first implementation action.

1. Run `shellcheck` on `tests/lib/run_tmpdir.sh`, `tests/run_shell_test.sh`,
   `tests/lib/tmpdir_guard.sh` and every edited test file. Compare each
   against `git show HEAD:<f> | shellcheck -`: there must be no new warnings.
2. Re-run all 52 edited files (excluding `test_codex_model_detect`) with
   `AIT_TMPDIR_GUARD_STRICT=1 bash tests/run_shell_test.sh tests/<t>.sh`, 4 at
   a time. Expect every file to exit 0 with **no** `TMPDIR LEFTOVERS` line,
   which in strict mode means exit 0 proves the file is clean. Each file's
   pass/fail summary must match the baseline.
3. Re-run a sample of the edited files plainly (`bash tests/<t>.sh`). Before
   and after, run `ls /tmp | grep -cE 'aitask-locks-1000|_run_|tmp\.'` and
   check the count does not grow.
4. Strict mode and its negative controls:
   - A scratch test that runs `mktemp` and exits 0 → strict mode exits 1 and
     the default mode exits 0.
   - A clean scratch test → both modes exit 0.
   - A failing test with no leftovers keeps its own exit status.
   - **Guard-startup failure:**
     `TMPDIR=/nonexistent/x AIT_TMPDIR_GUARD_STRICT=1 bash tests/run_shell_test.sh <clean scratch test>`
     → exit 2, the message is printed, and the test did not run (a marker
     file the test would write is absent). The same command without strict
     mode → the warning is printed, the test runs, and the exit is 0 (today's
     behaviour, pinned).
4b. **Inherited lock override:**
    - Create a disposable external dir `X` (in the scratchpad) and run a
      sample with `AITASKS_LOCK_DIR="$X"` exported: one real-repo-lock suite
      (`test_gate_pass`), one fixture-lock suite (`test_lock_force`), and both
      deliberate-override suites (`test_issue_update_ledger`,
      `test_gate_codex_approvals`).
    - Expect: each passes under strict mode, and `X` is still empty afterwards
      (`find "$X" -mindepth 1 | wc -l` = 0).
    - Pre-fix control, captured **before** editing `test_gate_pass.sh`, while
      the file still matches HEAD (confirm with `git diff --quiet`): the same
      command leaves `X` populated. This proves the check can fail. No scratch
      copies or restores are needed.
4c. **`test_registry_lock` lifetime.** Run it with `TMPDIR` set to a fresh
    scratch dir `B`, so its root lands where it can be observed:
    - Normal completion → `B` empty, the suite passes, case 5 passes.
    - Early abort: start it with `setsid`, wait until `B` holds a
      `test_registry_lock_*` dir, then `kill -TERM` the **child** bash only
      (from `pgrep -P <parent>`) → the parent exits non-zero and `B` is empty.
    - Interrupt: `kill -INT -- -<pgid>` on a fresh run → `B` is empty.
    - Pre-fix control, captured **before** editing the file: a normal run
      already leaves its `tmp.*` root in `B` (baseline). The TERM injection
      also leaves it there.
4d. **`test_chatlink_relay` early stop before Part 3** (a normal completion
    cannot show this gap):
    - Run it under `setsid` with `TMPDIR` set to a fresh scratch dir `C`.
    - Wait until a `chatlink_test_*` dir appears under `C/chatlink_relay_run_*`,
      which means Part 1 is in flight and line 524 has not run yet.
    - Run `kill -TERM -- -<pgid>`, then check that `C` is empty.
    - Pre-fix control, captured before editing: the same injection leaves
      `chatlink_test_*` in `C`.
5. `test_codex_model_detect` with a stub `codex` on `PATH`:
   - A stub that always errors → the FAIL path, the results dir is kept, and
     the message is printed.
   - A stub that echoes the requested model in the expected JSON shape → the
     PASS path, the dir is removed.
   - No live calls.
6. `bash tests/test_asserts_counters.sh` and any existing test of
   `tmpdir_guard.sh` (find it with `grep -l tmpdir_guard tests/`) still pass.

## Step 9

Post-implementation: current-branch mode. Commit the code
(`bug: … (t2302)`), then archive through the standard Step 9 flow.

## Risk

### Code-health risk: low
- 52 test files are edited in a shared worktree, and another session could
  touch one of them mid-run (concurrent-session hazard). · severity: low ·
  → mitigation: inline pre-phase shared_file_gate
- Trap composition: a new trap could silently replace an existing one,
  bringing a leak back, or one file could pick the wrong cleanup pattern. The
  removal target is always a fresh `mktemp -d` root, so nothing outside it can
  be deleted. · severity: low · → mitigation: None (accepted; covered by
  Verification step 2: strict-mode rerun of every edited file)
- The `test_registry_lock` re-exec changes that file's process structure. A
  parent/child split could mask the child's exit status or swallow a signal.
  · severity: low · → mitigation: None (accepted; covered by Verification 4c,
  normal, child-TERM and group-INT runs with pre-fix controls)

### Goal-achievement risk: low
- Only the 56 listed files are fixed and re-measured. Shell tests added since
  t2290, or never attributed, may still leak, which is why the default flip is
  deferred. · severity: low · → mitigation: None (accepted by the user; the
  full strict sweep was dropped)
- The `test_codex_model_detect` change can only be verified with a stub,
  never live. · severity: low · → mitigation: None (accepted; covered by
  Verification step 5)

### Planned mitigations
- timing: pre-phase | name: shared_file_gate | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — concurrent edits to shared test files | desc: Before editing each target test, and again before commit, check git status/diff for foreign hunks; skip and report any owned file; commit named paths only
