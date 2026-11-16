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
