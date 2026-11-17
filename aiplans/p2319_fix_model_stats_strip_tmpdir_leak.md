---
Task: t2319_fix_model_stats_strip_tmpdir_leak.md
Base branch: main
Output branch: main
---

# t2319 — Stop `aitask_model_stats_strip.sh` leaking its work dir into TMPDIR

## Context

The full Python suite's TMPDIR guard reported `TMPDIR LEFTOVERS (1): ait_stats_strip.<rand>`.
The task said the leaking route was not yet identified. **It is now:** reproduced with
each strip-driving test under a private TMPDIR:

| test (tests/test_model_stats_migrate.py) | leftover |
|---|---|
| `test_killed_between_rewrite_and_commit_resumes` | `ait_stats_strip.3eVjXC` |
| `test_commit_failure_rolls_back` | none |
| `test_failed_commit_never_restores_over_a_competing_edit` | none |
| `test_dirty_worktree_defers` | none |

That test's `AIT_STATS_STRIP_AFTER_REWRITE_HOOK` sends **SIGKILL** to the strip process
between the rewrite and the commit (the script's documented termination seam). **SIGKILL
can't be trapped**, so the task's suggested `trap … EXIT` alone does **not** fix the
observed leak. That is the same case as a real OOM kill or `kill -9`.

Measured (probe script): bash runs an EXIT trap on fatal TERM, HUP and INT, so the
script itself *can* cover every exit except SIGKILL. That matches the note already in
`aitask_task_commit.sh:146-151`.

**Fix in two layers:**
1. **Caller-owned scratch** (this layer fixes the observed leak, SIGKILL included): the only
   caller, `lib/model_stats_migrate.py::_local_strip`, runs the helper with
   `TMPDIR` pointed at a `tempfile.TemporaryDirectory` it owns. Whatever the child leaves
   behind, even after SIGKILL, goes when the caller's `with` block exits.
2. **Script-owned cleanup** (in-script defense for direct runs and any future caller):
   one `EXIT` trap removes `WORK_DIR` on every catchable exit, replacing the two
   inline `rm -rf` calls.

## Implementation

### 1. `.aitask-scripts/aitask_model_stats_strip.sh`

- Add a cleanup function that never fails (errexit is still on inside an EXIT trap):
  ```bash
  _strip_cleanup() {
      if [[ -n "$WORK_DIR" ]]; then rm -rf -- "$WORK_DIR" 2>/dev/null || true; fi
      return 0
  }
  ```
- Arm it immediately **before** the `mktemp -d` (WORK_DIR is still "", so arming early
  leaves no window and the cleanup does nothing until the dir exists), then re-arm the
  archive sweep, following the pattern in `aitask_task_commit.sh:152-153`. `lib/archive_utils.sh`
  claims the single EXIT trap when it is sourced (reached via `task_utils.sh`), so
  `ait_archive_rearm_exit_trap` (`lib/archive_utils.sh:282`) chains our handler instead of
  silently dropping the archive cleanup:
  ```bash
  trap _strip_cleanup EXIT
  ait_archive_rearm_exit_trap
  WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_stats_strip.XXXXXX")" || strip_error "mktemp_failed"
  ```
  The order matters: our trap first, then the re-arm wraps it. Reversing them would clobber the
  archive chain.
- Remove the inline `rm -rf "$WORK_DIR"` from `strip_deferred()` (line 65) and from the
  success path (line 155). The trap is now the single cleanup route.
- Header comment: add a short "Scratch" paragraph. WORK_DIR is removed by the EXIT trap on
  every exit, fatal TERM/INT/HUP included. SIGKILL skips it, so the caller runs the
  helper under a private TMPDIR it owns and removes afterwards.

### 2. `.aitask-scripts/lib/model_stats_migrate.py::_local_strip` (~line 447)

Replace the `NamedTemporaryFile` + `finally: os.unlink` with one owned directory that holds
both the message file and the child's TMPDIR:
```python
with tempfile.TemporaryDirectory(prefix="ait-stats-strip-") as scratch:
    msg = os.path.join(scratch, "message")
    with open(msg, "w", encoding="utf-8") as fh:
        fh.write(strip_message(agent, kind, mid))
    proc = subprocess.run([... unchanged argv ...], cwd=ctx.top, capture_output=True,
                          text=True, check=False,
                          env={**os.environ, "TMPDIR": scratch})
```
The rest of the function (output parsing) stays as is, after the `with` block. Update the
docstring with one sentence: the helper's scratch lives in a caller-owned dir, so a killed
helper leaves nothing behind.

### 3. Tests — `tests/test_model_stats_migrate.py`, new class `TestStripScratchHygiene(NoRemoteBase)`

A helper `private_tmp()` creates `self.tmp / "scratch"` and patches both
`os.environ["TMPDIR"]` and `tempfile.tempdir` to it (both, so the Python side and the bash
child resolve to the same place). A helper `assert_empty(d)` asserts `os.listdir(d) == []`
and names what it found.

**Caller level** (through `msm.migrate`, i.e. the production route):
- `test_strip_route_leaves_no_scratch`: clean strip (`MIGRATED`).
- `test_deferred_dirty_route_leaves_no_scratch`: dirty worktree (`MIGRATE_DEFERRED:…|dirty`).
- `test_commit_failed_route_leaves_no_scratch`: failing pre-commit hook.
- `test_sigkilled_helper_leaves_no_scratch`: the kill-9 hook (`strip_interrupted`). This
  is the observed leak.

**Script level** (invoke `msm.STRIP_HELPER` directly with `env TMPDIR=<private>` and no
caller wrapping, to prove the script's own trap):
- STRIPPED, `STRIP_DEFERRED:dirty`, `STRIP_DEFERRED:commit_failed:…`, and a hook that sends
  **SIGTERM** to `$AIT_STATS_STRIP_PID` (the process dies with rc −15). Each asserts the
  private dir is empty. The expected blobs come from `git hash-object --stdin` over the
  current bytes and over `msm.strip_blob(bytes)`. The message file lives under `self.tmp`,
  not the private dir.

Keep each case's expected outcome assertion, so a route that silently changes outcome can't
pass as "clean".

## Verification

1. **Pre-fix control** (shows which assertions catch the bug). Stage the new tests against
   unmodified copies of the script and module in an isolated scratch copy, without
   stash/restore in the shared worktree. Expected: `sigkilled` (caller level) and SIGTERM
   (script level) **fail**. The other six pass both before and after: they are regression
   guards for routes that were already clean, and are labelled as such.
2. Post-fix: `~/.aitask/venv/bin/python -m pytest -q tests/test_model_stats_migrate.py`
   passes in full, with each case's outcome asserted.
3. Leak check: rerun the reproduction loop (the four existing tests, each under a private TMPDIR).
   Every one must print no leftovers.
4. `shellcheck .aitask-scripts/aitask_model_stats_strip.sh`.
5. `tests/test_metadata_writer_inventory.py`: the helper's writer route
   (`aitask_model_stats_strip.sh::<module>` → `aitask_task_commit.sh`) is unchanged, so it must
   still pass.
6. `bash tests/run_all_python_tests.sh` (check `${PIPESTATUS[0]}` / the last-line verdict).
   Expect no `ait_stats_strip.*` in the TMPDIR LEFTOVERS line.

## Step 9

Post-implementation: commit code (`bug: … (t2319)`), commit the plan through
`./ait git`, then archive per the task-workflow Step 9.

## Risk

### Code-health risk: low
- The new EXIT trap could clobber `archive_utils.sh`'s source-time trap. Handled by the
  documented `ait_archive_rearm_exit_trap` re-arm, following `aitask_task_commit.sh`'s pattern. · severity: low · → mitigation: None (handled in plan step 1)
- Changing the child's TMPDIR changes where `archive_utils`/`registry_cas` scratch lands.
  It all becomes caller-owned and removed afterwards, which is the intent. · severity: low · → mitigation: None

### Goal-achievement risk: low
- The task's suggested fix (trap only) would not fix the observed SIGKILL leak. The plan
  adds the caller-owned TMPDIR and proves both layers with a pre-fix control. · severity: low · → mitigation: None (handled in plan steps 2–3)

## Final Implementation Notes
- **Actual work done:** (1) `aitask_model_stats_strip.sh`: one EXIT trap (`_strip_cleanup`, then `ait_archive_rearm_exit_trap` so archive_utils' source-time sweep stays chained) armed before `mktemp -d`. It replaces both inline `rm -rf "$WORK_DIR"`. New optional `--scratch-dir <existing dir>` parents the work dir (default `$TMPDIR`). The help range now runs to `2,48p` to cover the grown header. (2) `lib/model_stats_migrate.py::_local_strip`: one `tempfile.TemporaryDirectory` holds the message file and is passed as `--scratch-dir`, so a SIGKILLed helper's work dir goes away with it. (3) `tests/test_model_stats_migrate.py::TestStripScratchHygiene`, 9 tests. Caller level through `msm.migrate`: STRIPPED / dirty / commit_failed / SIGKILL, plus `test_helper_inherits_callers_tmpdir`. Script level with the helper run directly: STRIPPED / dirty / commit_failed / SIGTERM (rc −15). Each asserts both the route's outcome and an empty private TMPDIR.
- **Deviations from plan:** The plan had the caller override the helper's `TMPDIR`. The shipped version passes `--scratch-dir` and leaves TMPDIR alone. Reason: `ait_lock_dir` (`lib/stale_lock.sh:154`) derives the framework's shared per-user/per-repo mutex base (`merge`, `emails`, ledger blocks, sync's `data_index`) from `$TMPDIR`. A private TMPDIR would hand the helper's whole process tree, git hooks included, a private lock namespace and silently drop mutual exclusion. Nothing in today's strip chain (registry_cas, atomic_write, aitask_task_commit → task_git_commit_scoped) takes such a lock, so this is a guard against future breakage, not a live bug. `test_helper_inherits_callers_tmpdir` pins it.
- **Issues encountered:**
  - **Shared-file collision.** At pick time all three files were *untracked* in-flight work of the live t1912_5 session. I added `TestStripScratchHygiene` to its test file without checking first. t1912_5's path-scoped commit `3d4a7472c` then absorbed the class, including its two then-red tests. The user confirmed t1912_5 had landed. The two sessions agreed over cross-session messages: t1912_5 stays off these paths, and this commit turns the tests green. Lesson (memory `feedback_shared_file_gate_before_edit_not_commit`): the gate check belongs before the first edit, and "untracked" counts as another task's work in progress.
  - **My first `private_tmp()` leaked the test environment.** It used an `addCleanup`'d `mock.patch.dict(os.environ)`. Cleanups run after `tearDown`, so it "restored" a mid-test snapshot (fake HOME, `GIT_CONFIG_GLOBAL=/dev/null`) over the environment MigrateBase had just restored. `TestParity` then failed deterministically in module order but passed alone. The fix assigns `os.environ["TMPDIR"]` directly, since MigrateBase's own patch.dict undoes it.
- **Key decisions:**
  - Both layers are needed. SIGKILL can't be trapped (it is the observed leak, from `test_killed_between_rewrite_and_commit_resumes`'s kill-9 hook), so only the caller can own it. The script trap covers direct runs and TERM/INT/HUP; I measured that bash runs EXIT on all three, matching `aitask_task_commit.sh`'s note.
  - The cleanup returns 0 unconditionally, because errexit is live inside an EXIT trap.
- **Verification record:**
  - **Reproduction, pre-fix**, each test under a private TMPDIR: the SIGKILL test left `ait_stats_strip.3eVjXC`; the other three strip tests left nothing.
  - **Pre-fix control** (a `git archive HEAD` copy plus the new test file): only `test_sigkilled_helper_leaves_no_scratch` and `test_helper_sigterm_leaves_no_scratch` fail. The other 7 are regression guards that pass both before and after.
  - **Mutant control** (TMPDIR override reinstated): only `test_helper_inherits_callers_tmpdir` fails.
  - **Post-fix:** module + `test_metadata_writer_inventory.py` 54 passed. `test_setup_model_stats_migration.sh` 25/25. Leak loop clean on all four routes. shellcheck clean at warning level.
  - **Full Python suite:** PASSED (runner=pytest, exit=0), run on the TMPDIR-override variant before the `--scratch-dir` narrowing, with no `ait_stats_strip.*` in TMPDIR LEFTOVERS. The narrowing itself was verified by the targeted runs above.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/stale_lock.sh:154 — ait_lock_dir creates a persistent per-repo lock base "${TMPDIR}/aitask-locks-<uid>-<cksum>" by design; the full Python suite run left 3 of them (aitask-locks-1000-2210770147, -2297860352, -3678257901) in its per-run TMPDIR, i.e. some tests reach ait_lock_dir without a pinned AITASKS_LOCK_DIR — leaking tests not identified; not caused by this change (the strip chain takes no ait_lock_dir lock)`
