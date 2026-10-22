---
Task: t2125_settings_fetch_exclusion_worker.md
Base branch: main
Output branch: main
---

# t2125 — Run the Settings fetch-exclusion apply in a thread worker

## Context

t2099 made `SettingsApp.save_artifacts_settings` re-apply the routine-fetch
exclusion by calling `_apply_fetch_exclusion` → `_run_fetch_exclusion`
(`.aitask-scripts/settings/settings_app.py:3952-3976`), which runs
`aitask_artifact.sh fetch-exclusion apply` with `subprocess.run(timeout=30)` **on
the Textual event loop**. The CLI takes a repo-wide lock (`AFX_LOCK_TIMEOUT`=10s),
so a busy lock freezes the TUI (no input, no repaint) for up to 10s, and a slow
child for up to 30s.

Goal: the config save stays synchronous; the CLI runs in a tracked thread worker;
toasts are marshalled back with `call_from_thread`; newest save wins; app exit
never waits on the CLI.

## Design findings (verified in Textual 8.2.7 source)

- Thread workers run via `loop.run_in_executor(None, …)` (`textual/worker.py:326`).
  `Worker.cancel()` only sets a flag for a thread — the thread keeps running.
- App shutdown calls `self.workers.cancel_all()` (`textual/app.py:3465`), but
  `asyncio.run` then joins the default executor, so a thread blocked in
  `subprocess.run` would hold exit open until the child finishes (≤30s).
  → The seam must **poll a `cancelled` predicate** to make cancellation real.
- Killing the child on cancel is unsafe: `lib/artifact_fetch_exclusion.sh` rewrites
  `remote.<r>.*` in several `git config` steps (saved/active/restoring state
  machine). So a cancelled run is **abandoned, not killed** — the child finishes
  its apply on its own. Its stdout/stderr go to unlinked `tempfile.TemporaryFile`s
  (not pipes), so an abandoned child never blocks on a full pipe nor takes SIGPIPE
  after we stop reading. `stdin=DEVNULL`.
- The 30s timeout keeps today's semantics (`subprocess.run(timeout=…)` kills the
  child): on deadline, `proc.kill(); proc.wait()` and report failure.
- House idiom (`board/board_trail_screen.py:1147`, `codebrowser/history_screen.py:192`):
  `@work(thread=True, group=…)` + a generation number checked in the UI-thread
  callback. Own group, so `exclusive=True` cancels only the previous apply.

## Implementation steps

1. **Imports** (`settings_app.py`): add `import time`; extend
   `from textual import on` → `from textual import on, work`; add
   `from textual.worker import get_current_worker  # noqa: E402`.

2. **Seam** — rewrite `_run_fetch_exclusion` to take
   `cancelled: Callable[[], bool] = lambda: False` and a class constant
   `FETCH_EXCLUSION_TIMEOUT = 30`:
   ```python
   def _run_fetch_exclusion(self, cancelled=lambda: False) -> tuple[int, str, str]:
       try:
           with tempfile.TemporaryFile("w+") as out_f, tempfile.TemporaryFile("w+") as err_f:
               proc = subprocess.Popen(
                   [str(ARTIFACT_CLI), "fetch-exclusion", "apply"],
                   stdin=subprocess.DEVNULL, stdout=out_f, stderr=err_f)
               deadline = time.monotonic() + self.FETCH_EXCLUSION_TIMEOUT
               while True:
                   try:
                       rc = proc.wait(timeout=0.1)
                       break
                   except subprocess.TimeoutExpired:
                       if cancelled():
                           return 1, "", "fetch-exclusion update abandoned"
                       if time.monotonic() >= deadline:
                           proc.kill()
                           proc.wait()
                           return 1, "", ("cannot run the fetch-exclusion update: timed out "
                                          f"after {self.FETCH_EXCLUSION_TIMEOUT}s")
               out_f.seek(0); err_f.seek(0)
               return rc, out_f.read(), err_f.read()
       except (OSError, ValueError) as exc:   # ValueError covers UnicodeDecodeError
           return 1, "", f"cannot run the fetch-exclusion update: {exc}"
   ```
   Docstring: runs in the worker thread; cancel abandons (never kills) the child
   and why; temp files instead of pipes and why. Text mode matches the old
   `text=True` (locale encoding).

3. **Worker + callback** — replace `_apply_fetch_exclusion` body:
   ```python
   def _retire_fetch_exclusion(self) -> None:
       """Invalidate any in-flight apply: its result describes an older save."""
       self._fetch_exclusion_gen += 1
       self.workers.cancel_group(self, "fetch_exclusion")

   def _apply_fetch_exclusion(self) -> None:
       """Re-apply the exclusion off the event loop (t2125)."""
       self._fetch_exclusion_worker(self._fetch_exclusion_gen)

   @work(thread=True, exclusive=True, group="fetch_exclusion")
   def _fetch_exclusion_worker(self, gen: int) -> None:
       worker = get_current_worker()
       rc, out, err = self._run_fetch_exclusion(lambda: worker.is_cancelled)
       if not worker.is_cancelled:   # superseded, or the app is exiting
           self.call_from_thread(self._on_fetch_exclusion, gen, rc, out, err)

   def _on_fetch_exclusion(self, gen, rc, out, err) -> None:
       if gen != self._fetch_exclusion_gen:   # a newer save superseded this run
           return
       <the existing warning / info toasts, unchanged, stderr escape()d>
   ```
   `_fetch_exclusion_gen = 0` initialised in `__init__` (checked: no Textual
   attribute of that name). The gen check closes the window where an older run
   finished just before the newer save cancelled it.

   **Invalidation happens on every successful save, not only on a launch.**
   In `save_artifacts_settings`, call `self._retire_fetch_exclusion()` right after
   `self.config_mgr.save_project_settings(data)` and before the `if branch:`
   branch, which keeps its guard: with no branch nothing new is launched, but a
   pending apply from an earlier branch save is still retired. Otherwise a sequence
   like save `new-branch` → select `local`, clear the branch → save would leave the
   first worker's gen current, and its outdated success/warning toast would appear
   after the newer save. Refused saves (validation errors return before the write)
   retire nothing, because the config did not change.

4. **Tests** (`tests/test_settings_artifacts_tab.py`):
   - `run_app`'s `fx_seam` accepts `cancelled=None`; add an optional
     `fx_seam` override parameter so a test can supply a blocking seam.
   - Add `async def drain(app, pilot)`: `await app.workers.wait_for_complete()`
     then `await pilot.pause()` (deliberate real-worker drain, per
     `testing_conventions.md`). Existing `FetchExclusionTests` call it after
     `save_artifacts_settings()`; `test_save_without_gitbranch_skips_exclusion`
     also asserts no worker in group `fetch_exclusion` was started.
   - New `test_blocked_seam_does_not_block_save`: seam sets `entered`, then
     waits on `release` (polling `cancelled`). Save returns, config is saved,
     `entered` is set, no "Routine fetches" toast yet; `pilot.press("k")` switches
     `TabbedContent.active` to `tab_artifacts` (UI responsive while the seam is
     blocked); set `release`; drain; the CHANGED toast arrives.
   - New `test_newest_save_wins`: first save's seam blocks then returns
     `FETCH_EXCLUSION:CHANGED` regardless of cancel; second save's seam returns
     UNCHANGED immediately; release, drain → no "Routine fetches" toast, two seam calls.
   - New `test_clearing_save_retires_pending_result`: config starts with
     `old-branch`; first save sets `new-branch`, and its seam blocks on `release`
     and returns a failure `(1, "", "[x] lock busy\n")` while ignoring cancel. Then
     select backend `local`, clear the branch (`set_branch(app, "")`), save again;
     assert the second save persisted and made no new seam call (still 1). Then
     set `release` and drain: no "not updated" warning and no "Routine fetches"
     toast. Repeat the same shape with a CHANGED result in a second sub-case.
     Mutant control (scratch, reverted): move the retire call back inside
     `_apply_fetch_exclusion` → this test fails.
   - New `test_exit_does_not_wait_for_seam`: blocking seam that returns when
     `cancelled()` turns true; exit the app inside `run_test` with the seam still
     blocked; assert the runner returns well under the seam's 10s safety cap,
     the seam observed `cancelled()`, and no fetch-exclusion toast.
   - New real-seam tests (no app boot) with `settings_app.ARTIFACT_CLI` patched to
     a scratch script:
     - success: script prints `FETCH_EXCLUSION:CHANGED` → `(0, "...CHANGED\n", "")`;
     - abandon: script `sleep 1; touch marker` with `cancelled=lambda: True` →
       returns in <1s with rc 1, and `marker` appears afterwards (child not killed);
     - timeout: `FETCH_EXCLUSION_TIMEOUT = 0.3`, script `sleep 5` → rc 1,
       "timed out", returns in <2s.

### Post-phase (risk mitigations)

1. [real_exit_teardown_probe] Add `RealTeardownTests.test_headless_run_exits_with_seam_blocked`
   to `tests/test_settings_artifacts_tab.py`: write a scratch driver script
   (in the test's tempdir, run with `sys.executable` and `cwd` = the fixture root)
   that imports `SettingsApp`, installs a seam that blocks on a `threading.Event`
   for at most 20s (polling `cancelled`) and records to a marker file whether it
   saw `cancelled()`, sets a gitbranch branch from an `on_mount`-scheduled
   callback, calls `save_artifacts_settings()`, then `app.exit()` once the seam
   reports it entered, and runs `app.run(headless=True)`. That goes through a real
   `asyncio.run` teardown, including the default-executor join. Assert the
   subprocess exits 0 in <8s (a `subprocess.run(timeout=15)` guard) and the marker
   says `cancelled`. Mutant control (scratch, reverted): drop the poll in
   the stub → the run hits the timeout guard.

## Threading checklist (testing_conventions.md)

Lifecycle: exit with pending work (exit test). Concurrency: two saves (newest-wins).
Failure recovery: failed seam warning (existing test). Resource cleanup: drain
leaves no live workers; abandoned child completes (abandon test). Parity: the same
toast texts (existing tests unchanged in their assertions). N=50 concurrency is not
meaningful for a single-UI-thread trigger — dropped, noted in Final Notes.

## Verification

- `python3 tests/test_settings_artifacts_tab.py`
- `bash tests/run_all_python_tests.sh --test-dir tests` restricted run not needed;
  run the settings test files: `python3 tests/test_settings_*.py` that import the app.
- Mutant controls (scratch, reverted): run the seam synchronously in
  `_apply_fetch_exclusion` → `test_blocked_seam_does_not_block_save` fails; drop the
  `cancelled()` poll → abandon test fails.

## Step 9

Post-implementation: commit code (`performance: … (t2125)`), plan via
`aitask_task_commit.sh`, archive per Step 9.

## Risk

### Code-health risk: low
- Abandoned children on exit/supersede keep running after the TUI stops tracking them (by design, to avoid a half-written git config); a stray `ResourceWarning` from the dropped `Popen` is possible · severity: low · → mitigation: none (accepted by design)

### Goal-achievement risk: low
- The exit test runs under `run_test`, not a real `asyncio.run` teardown, so the executor-join behaviour at real interpreter exit is inferred from Textual source rather than measured · severity: low (residual — addressed by inline post-phase real_exit_teardown_probe) · → mitigation: inline post-phase real_exit_teardown_probe

### Planned mitigations
- timing: post-phase | name: real_exit_teardown_probe | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — exit latency unmeasured under real teardown | desc: headless app.run() subprocess test proving exit does not wait on a blocked fetch-exclusion seam
