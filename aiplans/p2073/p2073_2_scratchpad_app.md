---
Task: t2073_2_scratchpad_app.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_1_scratchpad_store_and_archival.md, aitasks/t2073/t2073_3_bound_helper_pane_rule.md, aitasks/t2073/t2073_4_minimonitor_scratchpad_key.md, aitasks/t2073/t2073_5_scratchpad_docs.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-20 14:25
---

# t2073_2 — scratchpad_app

## Context

This is a child of t2073 (minimonitor scratchpad pane). It builds `ait scratchpad`, a small
Textual notes editor that runs in a pane bound to a code agent. t2073_4 adds the minimonitor
key that spawns it. Notes persist through the t2073_1 store helper
`.aitask-scripts/aitask_scratchpad_store.sh`, landed in d70250f70. The pane's companion-cleanup
hook kills it when its agent dies, so the app cannot rely on a clean exit. That is why
autosave has a maximum dirty age and why the hard-kill behaviour is tested.

Full parent design: `aiplans/p2073_minimonitor_scratchpad_pane.md`.

## Verification notes (2026-10-20, verify pass)

- **Every file this child touches is clean**, and no in-flight task (t1854_4, t2062, t2067,
  t2078) edits them. The files: `ait`, `lib/tui_registry.py`, `lib/shortcut_scopes.py`,
  `tests/test_no_lib_to_tui_import.sh` and `tests/test_shortcuts_registry_coverage.sh`.
  `scratchpad/` does not exist yet, so no pre-edit gate is needed.
- **Line references confirmed.**
  - `./ait`: help line :34, update-check skip list :198 (contains `frozenagent`), case entry
    :218.
  - `tui_registry.TUI_REGISTRY` :17-31.
  - `shortcut_scopes.KNOWN_BINDING_SOURCES` :46-66.
  - `test_no_lib_to_tui_import.sh` `TUI_PACKAGES` :46-49.
  - `test_shortcuts_registry_coverage.sh` `TUIS` :59.
  - `monitor_shared._run_rejected_cmd` :1593 and `ConcernPayloadEditModal` :4684.
- **Helper interface as built** (from the t2073_1 note, acknowledged):
  - `open` → `OPENED:<abs>/notes.md` or `NO_TASK`.
  - `save` (whole buffer on stdin) → `SAVED:<n>`, `SAVED:empty`, `ARCHIVED` or `ABSENT`.
  - Exit 2 = usage, exit 3 = `LOCK_BUSY` (after a 5 s lock wait), exit 4 = error.
  - `.holder.lock` is created only by `open`.
  - The store root is `${AITASK_SCRATCHPAD_DIR:-.aitask-scratchpad}`. The task dir is
    `${TASK_DIR:-aitasks}`, cwd-relative.
  - Test seam: `AITASK_SCRATCHPAD_PAUSE_FIFO` parks `open` at `open:after_task_check` and
    `save` at `save:after_exists_check`, both inside the lifecycle lock. The verb writes the
    point to `<fifo>.reached`.
- **Loss contract** is the corrected, content-based one, quoted under "Shared design".

### Textual 8.2.7 / CPython facts, each probed against the installed venv

- **Keys.**
  - App binds `ctrl+q → quit` (priority) and `ctrl+c → help_quit`.
  - Screen binds `ctrl+c,super+c → screen.copy_text`.
  - TextArea binds `ctrl+c,super+c → copy`, `ctrl+x,super+x → cut` and `ctrl+v → paste`.
    `ctrl+v` uses Textual's internal clipboard; terminal paste is a `Paste` event.
  - Stock `TextArea.action_copy` and **`action_cut`** both call `app.copy_to_clipboard`
    directly.
  - `TextArea.load_text()` posts `TextArea.Changed`.
- **`_closing` belongs to `MessagePump`.** `post_message` drops messages while it is true,
  so setting it before `App.exit()` queued **0** `ExitApp` messages (probe). The app must
  never touch it. Its own flags are `_sp_*`-prefixed.
- **`set_timer(0.0, …)` is broken.** The callback never fired, and `Timer._run`'s skip
  branch raised `ZeroDivisionError` at shutdown (probe).
- **An awaiting timer callback blocks input.** With a `set_timer` callback awaiting 1 s,
  `pilot.press("x")` took 0.85 s, and the editor was still empty when the callback ended.
  A plain `asyncio.create_task` body kept `press` at 0.06 s (probe). Async **action
  handlers** are awaited by the pump the same way, so no key action may await a save.
- **asyncio subprocess transports kill live children.**
  `BaseSubprocessTransport.close()` (also called from `__del__`) runs `self._proc.kill()`
  when the child is still running. A save spawned through
  `asyncio.create_subprocess_exec` would therefore be killed when the app exits gracefully
  (ctrl+q forced quit, SIGHUP) mid-save. That breaks "an orphaned in-flight save keeps the
  lock until it lands". **Saves use `subprocess.Popen`, awaited by a cancellable poll
  loop.** No transport means nothing kills the child behind our back.

### Refinements found in verification (folded into the steps below)

1. `action_cut` routes through the clipboard seam too.
2. Save stdin and stdout go through fully written anonymous temp files, never pipes. A
   truncated stdin from a killed parent would be committed by the helper as a success.
3. Save children use `start_new_session=True`, so the pane's SIGHUP does not kill them.
4. Never two saves at once, including the exit flush. The lifecycle lock is not FIFO, so
   older text could otherwise land last.
5. Dirty state is content-based: the buffer differs from the last-persisted text.
6. Live "hard kill" means `kill -KILL`; `kill-pane` (SIGHUP) is tested as its own path.
7. Footer + `priority=True` App bindings for `ctrl+s`/`ctrl+q`/`ctrl+c`. `?`/`j` are not
   spliced (printable keys the editor consumes).
8. **(review)** A scratchpad-specific shutdown flag; `MessagePump._closing` is never
   written.
9. **(review)** No Textual timers. One long-lived **save-driver task** owns all scheduling,
   so an overdue deadline is handled by plain arithmetic, never by a zero-delay timer.
10. **(review)** Saving runs in that driver task. Key handlers only update state and wake
    it, and never await a subprocess.
11. **(review)** One scheduling formula covers both edits and the failure retry delay
    (a fixed `RETRY_DELAY`, measured from failure completion), which new edits cannot
    shorten.
12. **(found while verifying 10)** `Popen` + poll loop instead of the asyncio subprocess
    transport, which kills live children on close.
13. **(review 2)** **Every app-owned private attribute and method is `_sp_`-prefixed.**
    `App._driver` is Textual's terminal driver: assigning a task to it breaks
    `is_headless` and shutdown. A probe of the planned names against a mounted App found
    `_driver` as the only collision today. The prefix rule plus a test (case 14) keeps
    future Textual names from colliding too.
14. **(review 2)** Failure-path timestamps never compare with `None`. The save driver is
    crash-proof (`try/except Exception` → failure path), and a done-callback makes any
    unexpected task death visible.
15. **(review 2)** The startup task is tracked (`_sp_startup_task`). It checks shutdown after
    every await, is cancelled and awaited on unmount, and releases a partially acquired
    holder fd. Nothing is created after shutdown.
16. **(review 2)** `_sp_spawn_store` is total. Temp-file and `Popen` errors (`OSError`,
    `ValueError`) close any partial resources and return an error, which enters the same
    failure/retry path. The SIGHUP handler runs `_sp_exit_now()` in a `finally`, so a
    flush that fails to spawn cannot skip the exit.
17. **(review 3)** A save timeout terminates the save's whole process group and confirms
    it drained before any retry. Otherwise the attempt stays pending (`STUCK`) and no new
    save runs. The shutdown/cancel paths still never kill an in-flight save.
18. **(review 4)** One `_sp_write_unresolved()` guard on **every** save entry point,
    including the SIGHUP detached flush. The termination-and-drain cleanup is one fully
    async, deadline-bounded loop: non-blocking `poll()` reaping, no `proc.wait()`, and the
    retained `Popen` handle when it ends `STUCK`.
19. **(review 5)** An uncertain save outcome invalidates the known-disk baseline
    (`_sp_persisted_text = None`). All clean, dirty, status, Save and Quit decisions go
    through the single `_sp_is_dirty()` predicate. The next save is therefore forced and
    confirmed even when the buffer equals the older acknowledged text. Only spawn errors
    and `LOCK_BUSY` count as certain no-writes.
20. **(review 6, simplification)** The original quit contract and a fixed retry delay
    replace the second-ctrl+q interaction and exponential backoff. Quit attempts the final
    save, reports a failure, then exits (or exits without it when an older write is
    `STUCK`). The retry delay is a fixed `RETRY_DELAY` measured from failure completion.
    Serialization, the unresolved-write guard, bounded cleanup and the unknown-disk
    predicate are unchanged.

## Shared design decisions (from the parent plan; abridged, unchanged)

- **One writer per store:** an app-held `fcntl.flock` on `<store>/.holder.lock`, opened
  `O_RDWR` **without `O_CREAT`**; only `open` creates the file.
  - **Ownership before content:** take the flock first, and only then read `notes.md`.
  - On contention, take a separate read-only path that never saves and never promotes
    itself.
  - Every `save` subprocess inherits the flock fd (`pass_fds`).
- **Autosave with a deadline:** a save is due at `min(last_change + 1.0 s,
  first_unsaved_change + 3.0 s)`.
  - Saves are serialized. Save on `ctrl+s`, on exit and on SIGHUP (best-effort).
  - **On a hard kill, changes not included in the latest successfully saved buffer may be
    lost, including edits queued during a pending save.** Autosave targets starting within
    roughly three seconds when no save is pending; this is not a maximum loss window.
  - The helper's 5 s figure bounds only its lock wait; no save duration is bounded
    (t2073_1).

## Implementation

### 1. `.aitask-scripts/scratchpad/__init__.py` (docstring only) + `scratchpad_app.py`

**Module scaffolding**
- The module docstring covers: purpose; ownership order; the autosave contract (the
  verbatim sentences above); the single save-driver task and why there are no Textual
  timers; why saves use `Popen` rather than asyncio subprocesses; and the hard-kill vs
  SIGHUP split.
- `sys.path` setup copied from `frozenagent_app.py:46-50`.
- Imports: `ShortcutsMixin`, `MultiRowFooter`, `copy_to_system_clipboard`.
- Module constants (read via the module at call time so tests can patch them):
  - `_STORE_SH = _SCRIPTS_DIR / "aitask_scratchpad_store.sh"`
  - `DEBOUNCE = 1.0`, `MAX_DIRTY_AGE = 3.0`
  - `RETRY_DELAY = 2.0` (fixed; measured from failure completion)
  - `STORE_CMD_TIMEOUT = 30.0`, `POLL = 0.05`
- Header strings:
  - `ST_SAVED = "saved"`
  - `ST_SAVING = "saving…"`
  - `ST_DIRTY = "unsaved changes"`
  - `ST_UNSAVED_MODE = "NOT SAVED (no task)"`
  - `ST_READONLY = "read-only: open elsewhere"`
  - `ST_ARCHIVED = "not saved — task archived"`
  - `ST_NO_TASK = "not saved — no active task"`
  - `ST_STORE_ERROR = "not saved — store unavailable"`
  - `ST_SAVE_FAILED = "save failed — retrying in {n}s"`
  - `ST_QUITTING = "saving before quit…"`

  The ctrl+q text is rendered from the resolved binding key, not a literal.

**`_sp_acquire_holder(fd) -> bool`** (module-level seam)
- `fcntl.flock(fd, LOCK_EX | LOCK_NB)`; returns `False` on EWOULDBLOCK/EAGAIN.

**`_sp_spawn_store(args, stdin_bytes, holder_fd) -> (Popen | None, out_file | None, err | None)`**
(module-level, sync, **total**)
- Writes `stdin_bytes` to a `tempfile.TemporaryFile()`, then `flush` and `seek(0)`.
- `out_file = tempfile.TemporaryFile()`.
- Calls `subprocess.Popen([str(_STORE_SH), *args], stdin=in_file, stdout=out_file,
  stderr=subprocess.STDOUT, pass_fds=(holder_fd,) if holder_fd is not None else (),
  start_new_session=True)`.
- The whole body sits in `try/except (OSError, ValueError)`, covering ENOSPC, EMFILE, a
  missing or non-executable helper, and a bad fd. On error it closes whichever temp files
  exist and returns `(None, None, f"ERROR:spawn: {exc}")`.
- `in_file` is always closed in `finally`.
- **The single spawn path** for `open`, the driver's saves and the detached exit flush.

**`async _sp_await_store(proc, out_file, timeout) -> (rc, out)`** (module-level)
- Polls `proc.poll()` every `POLL` with `asyncio.sleep` until the child exits or `timeout`
  elapses.
- **On timeout it never kills just the bash pid.** The helper's final step is
  `mv -f tmp notes.md` (`lib/atomic_write.sh:149`), a separate process. A surviving `mv`
  would commit the old buffer after a successful retry, because the retry reclaims the
  dead pid's lifecycle lock (`stale_lock.sh`: dead pid ⇒ reclaimable). It calls
  `await _sp_terminate_group(proc)` instead:
  1. `os.killpg(proc.pid, SIGKILL)`. The child is a session leader (`start_new_session`),
     so `pgid == pid`, and the helper's call tree never leaves the group: no `setsid`,
     `nohup` or `&` on the store path (grepped).
  2. **No blocking `proc.wait()`** (a `waitpid` with no timeout would freeze the event-loop
     thread if the helper sat in uninterruptible I/O). Instead, one async loop bounded by
     a single deadline `GROUP_DRAIN_TIMEOUT = 5.0` covers the whole cleanup. Each
     iteration:
     - reaps the direct child with non-blocking `proc.poll()` (WNOHANG);
     - probes `_sp_group_alive(pgid)`: `os.killpg(pgid, 0)`, with `ProcessLookupError` ⇒
       gone and EPERM ⇒ alive;
     - then `await asyncio.sleep(POLL)`.

     Orphaned descendants are zombies until init reaps them, normally within milliseconds,
     and a zombie cannot write. The unreaped direct child keeps the group non-empty, so
     reaping it is part of draining.
  3. Done when `proc.poll() is not None` **and** the group is gone →
     `(1, "ERROR:timed out")`, an ordinary failure, and the retry is safe.
  4. Deadline reached → `(1, "STUCK:<pgid>")`. The caller retains the **`Popen` handle**
     (`_sp_stuck_proc`) together with the pgid, so later polls can still reap it.
- Seams: `_sp_killpg(pgid, sig)` and `_sp_group_alive(pgid) -> bool`.
- Then reads `out_file` from offset 0.
- Total: never raises except `CancelledError`. On cancel it **does not** kill the child
  (the detached save must land); it just propagates. `out_file` is closed in `finally`.
- `async _sp_run_store(args, stdin_bytes, holder_fd) -> (rc, out)` composes the two. A spawn
  error returns `(1, err)` without awaiting.

**`class ScratchEditor(TextArea)`**
- `action_copy`: the selection, or the whole `text` when nothing is selected, sent through
  `copy_to_system_clipboard`. Never raises `SkipAction`.
- `action_cut`: the stock body with its copy routed through the seam.
- `soft_wrap=True`.

**`class ScratchpadApp(ShortcutsMixin, App)`**
- `_shortcuts_scope = "scratchpad"`, `AUTO_FOCUS = "#sp-editor"`.
- `BINDINGS`, all `priority=True`, all **sync** action methods:
  - `ctrl+s → save_now "Save"`
  - `ctrl+q → flush_quit "Quit"`
  - `ctrl+c → copy "Copy"` (delegates to the editor's `action_copy`)
- `compose`: `Static#sp-header` (a `rich.text.Text`, no markup), `ScratchEditor#sp-editor`,
  `MultiRowFooter()`.
- State. **All app-owned private names carry the `_sp_` prefix** (methods too), so none
  can shadow Textual's (`_driver`, `_closing`, …). Unprefixed names below are shorthand
  for the `_sp_` field:
  - `_sp_holder_fd`, `_sp_store_dir`, `_sp_persisted_text`, `_sp_mode`
    (`opening|owner|readonly|unsaved|no_task|store_error|archived`)
  - `_sp_first_unsaved`, `_sp_last_change`, `_sp_edits_during_save_first`
  - `_sp_save_in_flight`, `_sp_save_now_requested`
  - `_sp_retry_at`
  - `_sp_quit_requested`, `_sp_shutdown`
  - `_sp_wake: asyncio.Event`
  - `_sp_startup_task`, `_sp_save_task: asyncio.Task | None`
- Textual's `_driver` and `_closing` are **never** read or written by this module.

### 2. Ownership, the save driver, and shutdown

**Startup** (`on_mount` sets `_sp_startup_task = asyncio.create_task(self._sp_startup())`;
the task is retained, and cancelled and awaited at unmount)

`_sp_startup` runs off the pump, so a slow `open` never blocks typing.
- **After every await, before any acquisition**, it checks `if self._sp_shutdown:
  return`. The checkpoints are: after `open` returns, before `os.open`, before the flock,
  before the read and `load_text`, and before creating the save task.
- A `try/finally` closes `_sp_holder_fd` if it was opened but startup did not reach the
  `owner` hand-off (shutdown, an exception, or the read-only path).
- An unexpected exception switches the mode to `store_error` (notify), never a crash.
- Nothing touches widgets after `_sp_shutdown`.

Steps:
1. `--unsaved` → mode `unsaved`. No helper call, no lock, no save task.
2. Spawn `open <id>` via `_sp_run_store`.
   - `NO_TASK` → `no_task`.
   - rc≠0 or unparsable output → `store_error` (notify the output).
   - `OPENED:<p>` → `_store_dir = Path(p).parent`.
3. `os.open(_store_dir/".holder.lock", os.O_RDWR)`, **no `O_CREAT`**. `FileNotFoundError` →
   `archived`.
4. `_sp_acquire_holder(fd)`. `False` → **read-only**: close the fd, snapshot-read `notes.md`
   (`""` if missing), `editor.read_only = True`, mode `readonly`. It never saves and never
   retries.
5. **Only now** read `notes.md` (missing → `""`; decoded as UTF-8 with
   `errors="replace"`, so a foreign byte can never make every later `text.encode()` raise). Set `_persisted_text = text`, then
   `editor.load_text(text)`. The resulting `Changed` compares equal, so the editor stays
   clean. Mode `owner`; start `_sp_save_task = asyncio.create_task(self._sp_save_loop())`
   with a done-callback. If the task ends with an exception while `not _sp_shutdown`, the
   callback sets the status to "autosave stopped — error" and notifies. A dead driver is
   never silent.

   Until step 5, the editor is `read_only=True` with the status "opening…", so nothing typed
   before ownership is known can be lost or overwritten.

**Known-disk baseline and the one dirty predicate.** `_sp_persisted_text: str | None` is the
text **confirmed** on disk by the startup read or by a `SAVED:` response, and **`None`
when the disk state is unknown**.
- Every clean/dirty decision goes through `_sp_is_dirty()`:
  `_sp_persisted_text is None or editor.text != _sp_persisted_text`.
- No code compares against `_sp_persisted_text` directly. This covers the Changed handler,
  `_sp_next_due`, `_sp_save_once`'s early return, the quit-exit condition, the status
  text and the detached flush.
- The header shows `saved` only when `not _sp_is_dirty()` and no write is unresolved.
- An unknown baseline therefore forces one confirmed save of the current buffer, **even
  when it equals the last acknowledged text** (an undo back to `BASE`). Explicit Save and
  Quit honour it the same way, because both wait on the predicate.

**Key handlers and `on_text_area_changed` never await.** They update state and call
`self._wake.set()`.
- **Changed** (mode `owner` only; `now = monotonic()`):
  - If `not _sp_is_dirty()` and no save is in flight → clean: clear
    `_first_unsaved`, status `saved`.
  - Otherwise set `_last_change = now`. While a save is in flight, set
    `_edits_during_save_first` if unset; otherwise set `_first_unsaved` if unset.
  - Then wake.
- **`action_save_now`**: if `owner`, set `_save_now_requested = True` and wake. Otherwise
  `notify` the status.
- **`action_flush_quit`** — the original contract: attempt the final save, report a
  failure, then exit.
  - Mode not `owner` → `_sp_exit_now()`.
  - Otherwise set `_sp_quit_requested = True` and `_save_now_requested = True`, status
    `ST_QUITTING`, then wake. A repeated ctrl+q while quitting is a no-op.
  - The driver then exits after **exactly one** final outcome. That is a confirmed clean
    buffer, or the final attempt's result, success or failure. A failure is reported with
    `notify` ("final save failed — unsaved edits may be lost"), and the app exits anyway.
  - If a write is unresolved, the driver waits for it to resolve (bounded by
    `STORE_CMD_TIMEOUT` + `GROUP_DRAIN_TIMEOUT`).
    - If that ends `STUCK`, no final save may start. The app reports "previous write
      unresolved — exiting without the final save" and exits, under the "may be lost"
      contract.

**`_sp_next_due(now) -> float | None`** — the one scheduling formula:
- `None` if the mode is not `owner`, or `not _sp_is_dirty()` and quit is not requested.
- If the buffer is dirty but `_first_unsaved` is unset (the baseline was just invalidated
  with no new edit), `_first_unsaved` is the invalidation time, so the deadline applies.
- `edit_due`:
  - `now` if `_save_now_requested`.
  - Else `min(_last_change + DEBOUNCE, _first_unsaved + MAX_DIRTY_AGE)`.
- If `_retry_at` is set and `_save_now_requested` is **not** set → `max(edit_due,
  _retry_at)`. New edits can never pull a retry earlier than its retry delay; an explicit
  `ctrl+s`/`ctrl+q` may.
- Else `edit_due`.

**`async _sp_save_loop()`** — the only place a save runs, so saves are serialized by
construction:
```
while not self._sp_shutdown:
    now = monotonic()
    if quit requested and not _sp_is_dirty() and not _sp_write_unresolved():
        _sp_exit_now(); return
    due = self._sp_next_due(now)
    if due is None or due > now:
        self._wake.clear()
        try: await asyncio.wait_for(self._wake.wait(),
                                    None if due is None else due - now)
        except asyncio.TimeoutError: pass
        continue                       # always recompute; no timers anywhere
    try:
        await self._sp_save_once()
    except asyncio.CancelledError:
        raise
    except Exception as exc:          # never let the sole save task die
        self._sp_record_failure(f"ERROR:{exc!r}")
```
An overdue deadline (`due ≤ now`) saves on the next iteration. That is the
"fire immediately" behaviour, with no zero-delay timer.

**`async _sp_save_once()`**
1. Capture `text`. If `not _sp_is_dirty()`, clear `_save_now_requested` and return. With
   an unknown baseline, this never returns early.
2. Set `_save_in_flight`, `_edits_during_save_first = None`, clear `_save_now_requested`,
   status `saving…`.
3. `rc, o = await _sp_run_store(["save", id], text.encode(), _sp_holder_fd)`. A spawn or
   preparation error arrives here as `(1, "ERROR:spawn: …")`. `finally: _save_in_flight =
   False`.
4. Outcome:
   - **`SAVED:*`** → `_persisted_text = text`, `_retry_at = None`. If
     `_sp_is_dirty()` is still true: `_first_unsaved = _edits_during_save_first or now`. Else clear
     it.
   - **`ARCHIVED` / `ABSENT`** → mode `archived`, status `ST_ARCHIVED`. The loop ends
     because `_sp_next_due` returns `None`. If quit was requested → `_sp_exit_now()`.
   - **Anything else** (rc 3 `LOCK_BUSY`, rc 4, timeout, spawn error, unparsable output)
     → `_sp_record_failure(o, uncertain=…)`, shared with the loop's exception guard.
     - **Certain no-write vs uncertain.** Only two outcomes prove that this attempt wrote
       nothing:
       - a spawn or preparation error (no child ever ran);
       - rc 3 `LOCK_BUSY`: the helper prints it before touching the store ("NOTHING was
         changed").

       **Every other failure is uncertain:**
       - a timeout or `STUCK` (the replacement may have committed before the kill —
         reproduced: disk held `CHANGED` with no `SAVED:`);
       - rc 4;
       - unparsable output;
       - an exception in the loop guard.

       An uncertain failure sets `_sp_persisted_text = None` (baseline unknown). Status
       never shows `saved` while the baseline is unknown.
     - `_retry_at = monotonic() + RETRY_DELAY`, measured from **completion**, so a 5 s
       `LOCK_BUSY` is followed by the full delay.
     - **`STUCK:<pgid>`** additionally sets `_sp_stuck_pgid` and `_sp_stuck_proc`. While
       they are set, the aborted attempt is **still pending**:
       - `_sp_next_due` returns a poll time (`now + 1.0`), never a save.
       - Each wake-up runs non-blocking `_sp_stuck_proc.poll()` plus
         `_sp_group_alive(pgid)`.
       - Status: "save stuck — waiting for the previous write to finish".
       - Once both report gone, it clears the pair and normal scheduling resumes (overdue ⇒
         immediate).

**One guard for every save entry point.** `_sp_write_unresolved()` is `_save_in_flight or
_sp_stuck_pgid is not None`, and **every** path that could start a save checks it first:
- `_sp_next_due` (returns only a poll time while unresolved);
- `_sp_save_once` (returns immediately);
- `action_save_now` (only sets the request, which `_sp_next_due` defers);
- `action_flush_quit`: while a save is in flight, quit waits for it to resolve. If it
  ends `STUCK`, quit exits **without** starting the final save (reported).
- `_sp_spawn_detached_flush`: the SIGHUP flush is **skipped** while unresolved.

So no save can ever start while an older write may still complete. Shutdown while
unresolved exits under the existing contract: the newer edits "may be lost". A unit test
asserts the guard call sits first in each entry point; see case 14f.
     - `_first_unsaved = _sp_min_time(_first_unsaved, _edits_during_save_first, now)`.
       `_sp_min_time` takes the minimum of its **non-`None`** arguments, with `now` as the
       final fallback. The original edit time is kept, and a failure with no concurrent
       edit never compares a float with `None`.
     - Status `ST_SAVE_FAILED`. When quit was requested, report the failure and
       `_sp_exit_now()`, per the quit contract above.

**`_sp_exit_now()`** (sync)
- Sets `_sp_shutdown = True`, wakes the driver, and calls `self.exit()`.
- It never awaits a save. A save in flight continues as a detached child holding the
  inherited flock.

**`_sp_spawn_detached_flush()`** (sync; used by SIGHUP)
- Runs only when the mode is `owner`, `not _sp_write_unresolved()` (neither in flight nor
  stuck), `not _sp_shutdown` and `_sp_is_dirty()`.
- It calls `_sp_spawn_store(["save", id], …)` and never waits. The returned `out_file` is
  closed at once, because the child keeps its own fd.
- The body is wrapped in `try/except Exception` (logged): a flush can fail, but it can
  never raise.

**SIGHUP**
- `on_mount` registers `asyncio.get_running_loop().add_signal_handler(SIGHUP,
  self._sp_on_sighup)`. That is a loop callback, not a raw `signal.signal` handler, so
  calling `exit()` from it is safe.
- `_sp_on_sighup`: `try: _sp_spawn_detached_flush() finally: _sp_exit_now()`.
- `on_unmount` removes the handler, so the test process is unaffected after the app.

**`on_unmount`** (async)
1. Set `_sp_shutdown`, then wake.
2. Cancel and await `_sp_startup_task`, then `_sp_save_task` (each only if not `None`),
   suppressing `CancelledError`. A child in flight is **not** killed: `_sp_await_store`
   does not kill on cancel, and there is no transport.
3. `os.close(_sp_holder_fd)` if it is still open (startup's `finally` already closed a
   partial one). Ownership is released as soon as no detached child holds the inherited
   copy.

**`_sp_exit_now()` before startup finishes** (mode `opening`) simply exits. Unmount cancels
the startup task at its current await. The open child may still finish and create the store
and `.holder.lock`, which is harmless: nothing locks it, and the next instance owns it.

**CLI** — `main(argv) -> int`:
- `argparse` with a mutually exclusive required group `--task <id>` | `--unsaved`, and an
  optional `--target <pane>` shown in the header (`→ <pane>`).
- `--task` matches `^t?([0-9]+(_[0-9]+)?)$` and is stored bare. A bad id or missing mode →
  exit 2.

### 3. Launcher, dispatcher, registries, test lists

- NEW `.aitask-scripts/aitask_scratchpad.sh`: a verbatim clone of `aitask_frozenagent.sh`,
  with a header naming the scratchpad and why the update check is skipped (spawned beside
  an agent, must start fast). Mode 755. It `exec`s `scratchpad/scratchpad_app.py`.
- `./ait`:
  - help line `  scratchpad     Launch the scratchpad notes editor` before `settings`;
  - `scratchpad` added to the update-check skip list next to `frozenagent`;
  - case entry after `frozenagent`.
- `lib/tui_registry.py`: `("scratchpad", None, None, False)` after `minimonitor`.
- `lib/shortcut_scopes.py`: `("scratchpad_app", "scratchpad/scratchpad_app.py",
  ("scratchpad",))` after `frozenagent_app`.
- `tests/test_no_lib_to_tui_import.sh`: `scratchpad` added to `TUI_PACKAGES`.
- `tests/test_shortcuts_registry_coverage.sh`: a `TUIS` entry for `ScratchpadApp` built with
  `lambda C: C(None, None)`, scope `"scratchpad"`.

### 4. Tests

**NEW `tests/test_scratchpad_app.py`** (`unittest`, `App.run_test`; real Textual and real
wall clock)

- **Setup.**
  - The module is imported by path (the `test_frozenagent_app.py` pattern).
  - Each test gets a tmp dir with `TASK_DIR=<tmp>/aitasks/t42_x.md` and
    `AITASK_SCRATCHPAD_DIR=<tmp>/pad`, set in `os.environ`. The store is seeded through the
    **real helper**.
  - Pause-fifo tests set `AITASK_SCRATCHPAD_PAUSE_FIFO` in `os.environ` **after** mount, so
    only saves park, and release by writing a line from `asyncio.to_thread`.
  - A **fake store** is an executable Python script assigned to `_STORE_SH`. It delegates
    `open` to the real helper. Its `save` behaviour is read from a control JSON (`fail_n`,
    `fail_rc`, `delay`), and it appends `time.time()` plus outcome to an attempt log.
- **Env hygiene.** `PATH`, `TASK_DIR`, `AITASK_SCRATCHPAD_DIR` and
  `AITASK_SCRATCHPAD_PAUSE_FIFO` are set with `unittest.mock.patch.dict(os.environ)`.
  Patched module constants use `mock.patch.object`. Both are restored per test.
  `tearDown` kills any recorded fake or shim pgid.
- **Settle rule.** Every test ends by awaiting a `_settle()` helper. It waits until the
  driver is idle (no save in flight, nothing due), with a bounded poll of 10 s. Then it
  requests exit, so no task or child is left running when the `run_test` block closes
  (testing_conventions).
- Cases:
  1. **Loads existing notes.** The editor shows the seeded text, and the header says
     `saved`.
  2. **Debounced save.** Type `abc`, pause 1.5 s → `notes.md == "abc"`.
  3. **Deadline under continuous typing.** A key every 0.2 s for 5 s; attempts are recorded
     by wrapping `_sp_spawn_store`. The first save starts ≤ 3.5 s after the first key, with no
     save pending (a start target, not a maximum loss window).
     **Control:** `MAX_DIRTY_AGE = 1e9` → no save starts while typing continues.
  4. **Input stays responsive while a save is held; saves are serialized.** The real
     helper's pause fifo parks a save.
     - While it is parked, `pilot.press` of 5 keys plus ctrl+s each return in < 0.3 s, and
       the editor shows the new text immediately.
     - `.reached` shows no second save point, and the `_sp_spawn_store` wrapper counts exactly
       one `save`.
     - Release → exactly one follow-up save, carrying the newest text. `notes.md` == the
       final text.
  5. **Past-due deadline with the installed framework.** Park a save for 4 s (past
     `MAX_DIRTY_AGE`) while typing a key at t=0.5 s. Release:
     - the follow-up save starts ≤ 0.5 s after the first save completes (overdue → immediate);
     - no exception is raised, and the app's `_exception` is `None`;
     - `notes.md` holds the final text.
  6. **Failed-save retry delay, then recovery.** Fake store with `fail_n=3`, `fail_rc=4`,
     `delay=0`. Type once. Attempt timestamps:
     - each gap between consecutive attempt *starts* is ≥ 2.0 s after the previous attempt
       *completed* (−0.1 s tolerance), and ≤ 2.0 s + 1.0 s (fixed delay, not growing),
       with no attempt in between;
     - keys typed during each retry delay add no attempts;
     - the 4th attempt succeeds: `notes.md` == the newest text and the header says `saved`;
     - a later edit saves after the plain debounce (~1 s): the retry delay is cleared.

     **Slow-failure variant:** `fail_rc=3` (the `LOCK_BUSY` shape), `delay=1.5`, `fail_n=1`
     → the second attempt starts ≥ 2.0 s after the first **completes**, not immediately.
  7. **Unsaved mode writes nothing.** Type, wait 4 s. No spawn happened, the `pad/` tree is
     unchanged, and the header says `NOT SAVED (no task)`.
  8. **Busy lock → read-only.** The test holds the flock before mount.
     - The editor is read-only, the header says `read-only: open elsewhere`, and typing
       changes nothing.
     - No `save` spawns within 4 s.
     - Releasing the test's lock does not promote the app.
  9. **Ownership before read.** Patch `_sp_acquire_holder` to write `NEWER` before returning
     `True` → the editor shows `NEWER`.
     **Negative control:** a subclass that reads before locking shows the stale text.
  10. **The save child inherits the holder fd and a new session.** A fake store's `save`
      matches `(st_dev, st_ino)` of some `/dev/fd` entry against `.holder.lock`, compares
      `os.getsid(0)` with the app pid's sid, and logs both. Assert inherited and new
      session.
  11. **ARCHIVED → header.** Move the task file into `archived/`, type, wait 1.5 s → header
      `not saved — task archived`. No further attempt within 4 s.
  12. **ctrl+q terminates and releases ownership.**
      - Type, press ctrl+q → `run_test`'s app stops running within 5 s with
        `return_code == 0`.
      - `notes.md` holds the text.
      - A test-side `flock(LOCK_EX|LOCK_NB)` on `.holder.lock` then **succeeds**.
      - Also: with the fake store failing (rc 4), ctrl+q makes exactly one final attempt,
        a failure notification is recorded (patched `notify`), and the app exits with
        `return_code == 0`.
  13. **The SIGHUP path.** Type (dirty, no save in flight), then `os.kill(os.getpid(),
      SIGHUP)`:
      - the app exits;
      - within 5 s `notes.md` holds the text (the detached flush);
      - the flock probe succeeds afterwards;
      - after unmount, the SIGHUP handler is no longer installed:
        `loop.remove_signal_handler(SIGHUP)` returns `False`.
  14. **No framework-attribute collisions.**
      - An AST scan of `scratchpad_app.py` finds every `self.<name>` assignment and every
        method defined on `ScratchpadApp`/`ScratchEditor` whose name starts with `_`. Each
        must start with `_sp_`, except Textual hooks the class deliberately overrides (none
        are expected). None may be an attribute of a mounted plain `App()`/`TextArea()`;
        that cross-check runs on the installed Textual.
      - Behavioural half, in **owner** and **unsaved** modes: after mount,
        `isinstance(app._driver, textual.driver.Driver)` holds, `app.is_headless` is
        `True`, typing reaches the editor, and ctrl+q exits with `return_code == 0` and no
        `app._exception`.
  14b. **Failure without concurrent edits, then recovery; the save task stays alive.** Fake
       store with `fail_n=1`. Type once and do not type again.
       - The first attempt fails, the header says `save failed`, and
         `app._sp_save_task.done()` is `False`.
       - The retry at ≥ 2 s succeeds, and `_sp_save_task.done()` is still `False`.
       - Neither `TypeError` nor any other exception reaches the done-callback (asserted
         through a recorded-exceptions list the test installs as the loop's exception
         handler).
  14c. **Injected spawn/preparation errors.**
       - (i) Patch the module's `subprocess.Popen` to raise `OSError(EMFILE)` on the first
         save call only → header `save failed`, retry delay applied, the task is alive, the
         retry succeeds, and `notes.md` holds the text.
       - (ii) Patch `tempfile.TemporaryFile` to raise `OSError(ENOSPC)` once → same
         recovery. No temp file object is left open; a wrapper counts opens and closes.
       - (iii) SIGHUP with `Popen` raising → the app still exits (the `finally` runs
         `_sp_exit_now`).
  14e. **A timeout during the final rename cannot overwrite a successful retry.**
       Deterministic, with the real helper and real Textual.
       - **Setup.** A shim dir prepended to `os.environ["PATH"]` holds an `mv` script
         with the real `mv` path baked in at creation (resolved via `shutil.which` first).
         When its last argument ends in `/notes.md` and `$SHIM/block_once` exists, it
         removes `block_once`, writes `$$` to `$SHIM/blocked.pid`, blocks on `read <
         $SHIM/fifo`, then `exec`s the real `mv "$@"`. Otherwise it execs the real `mv`
         directly. `STORE_CMD_TIMEOUT` is patched to `1.0` and `RETRY_DELAY` to `0.5`.
       - **Scenario.** Seed `BASE`.
         1. Type `OLD`. The save parks in the shim's `mv`.
         2. Once `blocked.pid` appears, type ` NEW`.
         3. The timeout fires and the group is terminated. The retry saves `OLD NEW`.
       - **Assert:**
         - `notes.md == "OLD NEW"` and the header says `saved`;
         - the blocked shim pid is gone (`os.kill(pid, 0)` → `ProcessLookupError`);
         - `os.open(fifo, O_WRONLY|O_NONBLOCK)` → `ENXIO`: no reader is left to release;
         - after 1.5 s more, `notes.md` is still `"OLD NEW"`.
       - **Negative control** (reproduces the reported defect): patch
         `_sp_terminate_group` to the old `proc.kill(); proc.wait()` and repeat. The retry
         still saves `OLD NEW`. Then write one line to the fifo (the old `mv` is still alive
         and reading) → within 2 s `notes.md` reverts to `OLD`. This proves the case can
         fail.
       - **Shutdown preservation** is checked separately by live (f): the cancel/exit paths
         never call `_sp_terminate_group`.
  14f. **A group that will not drain holds back every retry.**
       - Patch `_sp_group_alive` to report alive for 3 s, then dead, and patch
         `GROUP_DRAIN_TIMEOUT` to `0.3`. Use the shim from 14e with a 1.0 s timeout.
       - After the timeout: the status shows `save stuck`, and **no** `save` spawns while
         the group is reported alive (spawn counter unchanged). ctrl+s during this time
         also spawns nothing.
       - Once the patch reports dead → exactly one save, `notes.md` == the final text, and
         the save task is alive.
       - **SIGHUP variant:** in a fresh run, enter the same STUCK state with a dirty buffer,
         then `os.kill(os.getpid(), SIGHUP)`. The app exits, **no** `save` spawns (the
         counter is unchanged; the detached flush was skipped), and `notes.md` is
         unchanged after 1.5 s.
       - **Static guard check:** an AST walk asserts that `_sp_spawn_detached_flush`,
         `_sp_save_once` and `_sp_next_due` each call `_sp_write_unresolved` before any
         `_sp_spawn_store`/`_sp_run_store` call.
  14g. **A direct child that will not die keeps the loop responsive.**
       - Fake store whose `save` sleeps 60 s. `_sp_killpg` is patched to a no-op for that
         save's pgid, so the direct child really stays alive past the budget.
         `STORE_CMD_TIMEOUT = 0.5`, `GROUP_DRAIN_TIMEOUT = 0.5`.
       - Assert:
         - the status reaches `save stuck` within 2 s;
         - while stuck, each of 5 `pilot.press` calls returns in < 0.3 s and its text
           appears in the editor (the loop is not blocked);
         - ctrl+s spawns nothing;
         - ctrl+q during STUCK exits within 1 s **without** spawning a final save, and
           the "previous write unresolved" report is recorded.
       - **Recovery variant:** in a fresh run, after STUCK the test really kills the pgid
         (`os.killpg(pgid, SIGKILL)` from the test). The app's stuck poll reaps the
         retained `Popen`, sees the group gone, resumes, and the next save (the fake now
         succeeds) lands the final text.
       - **Cleanup:** the test kills any surviving fake pgid in `tearDown`.
  14h. **Timeout after replacement but before acknowledgement, then an undo to BASE.**
       - **Setup.** A shim `mv` (as in 14e), but in `block_after` mode: it runs the real
         `mv` first, then writes `$$` to `blocked.pid` and blocks on the fifo. The helper
         therefore never prints `SAVED:`, although `notes.md` already holds the new text.
         `STORE_CMD_TIMEOUT = 1.0`, `RETRY_DELAY = 0.5`.
       - **Scenario.**
         1. Seed `BASE` (the confirmed baseline). Type `X`; the first save parks after
            replacement, so the disk holds `BASEX`.
         2. While it is parked, press ctrl+z: the buffer is `BASE` again, equal to the old
            acknowledged text.
         3. The timeout terminates the group.
       - **Assert:**
         - between the failure and the retry, the header is **not** `saved`;
         - a **second save spawns** even though the buffer equals the last acknowledged
           text (the spawn counter is 2);
         - after it, `notes.md == "BASE"` and only then does the header say `saved`.
       - **Quit variant:** same setup, but after the timeout press ctrl+q once. The app
         does not exit until the confirmed `BASE` save lands, then exits. `notes.md ==
         "BASE"`.
       - **Explicit-save variant:** after the timeout, ctrl+s leads to
         the same forced save.
       - **Negative control:** patch `_sp_record_failure` so it keeps the baseline (no
         `None`). There is no second spawn, the header says `saved`, and `notes.md` stays
         `BASEX`. This proves the case catches the defect.
       - **Certain-failure control:** a fake store returning rc 3 `LOCK_BUSY` with the
         buffer undone to `BASE` keeps the baseline. No forced save; the header says
         `saved`.
  14d. **Quit during a delayed open, with the loop kept alive.**
       - Set `AITASK_SCRATCHPAD_PAUSE_FIFO` **before** mount, so `open` parks at
         `open:after_task_check`, and install a recording loop exception handler.
       - Press ctrl+q while the open is parked → the app exits.
       - After the `run_test` block, keep the loop alive: release the fifo from a thread,
         then `await asyncio.sleep(1.5)`.
       - Assert:
         - `_sp_startup_task.cancelled()` or `done()`;
         - `_sp_save_task is None`;
         - no exceptions recorded (no `NoMatches`, no widget access after shutdown);
         - a test-side flock on the (now created) `.holder.lock` **succeeds**: no leaked
           holder fd;
         - no `notes.md` written.
  15. **Copy and cut use the seam.** Patch `copy_to_system_clipboard`.
      - ctrl+c with no selection → called with the whole buffer.
      - With a selection → called with the selection.
      - ctrl+x → called with the cut text, which is removed.
  16. **CLI.** `--task x1` → 2; no mode → 2; `t42` → `42`.

**NEW `tests/test_scratchpad_autosave_live.sh`**
- Setup:
  - `require_isolated_tmux`, a private `tmux -L ait_scratch_$$`, and a fixture repo with
    `aitasks/t42_x.md`.
  - The app is launched via `exec env … "$PY" <repo>/.aitask-scripts/scratchpad/scratchpad_app.py
    --task 42`, so `#{pane_pid}` is the app.
  - Readiness: poll `capture-pane` for `saved`. Typing via `send-keys -l`.
  - Cleanup trap: `kill-server` on this socket only.
  - No assertions run in subshells.
- Cases:
  - **(a)** Type `alpha`, wait 2.5 s, `kill -KILL` → on disk.
  - **(b)** Token `k<i> ` every 0.2 s for 6 s, then immediately `kill -KILL` → every token
    older than 3 s + 1.5 s is on disk.
  - **(c) Control.** Seed `old`, type `new`, `kill -KILL` at 0.3 s → still `old`.
  - **(d)** Type `hup`, `kill-pane` at 0.3 s → `hup` on disk within 5 s (the SIGHUP flush).

### Post-phase (risk mitigations)

1. [orphan_save_handoff] Add live cases **(e)** and **(f)** to
   `tests/test_scratchpad_autosave_live.sh`.
   1. **(e) Setup.**
      1. Make a fifo `$T/pause` and launch the app with `AITASK_SCRATCHPAD_PAUSE_FIFO=$T/pause`.
      2. When `$T/pause.reached` reads `open:after_task_check`, write one line to the fifo
         (bounded poll ≤ 5 s).
      3. Once `saved` shows, type a ≥ 8 KiB buffer (known prefix + a generated line repeated
         + known suffix).
      4. Wait for `.reached` = `save:after_exists_check`, then `kill -KILL <pane_pid>`.
   2. **(e) Assertions.**
      1. A `python3 -c` probe of `flock(LOCK_EX|LOCK_NB)` on `.holder.lock` **fails**: the
         orphaned child holds the inherited fd.
      2. `notes.md` lacks the suffix.
      3. Release the fifo. Within 5 s, `notes.md` `cksum` equals that of the expected
         buffer rebuilt from the same generator (no truncation), and the flock probe
         **succeeds**.
      4. A fresh instance (no fifo env) shows `saved` and the prefix.
   3. **(f)** Same as (e), but end the app with `tmux kill-pane` instead of `kill -KILL`.
      This is the graceful SIGHUP exit with a save in flight. The flush is skipped (a save
      is in flight); the parked save must survive the app's shutdown and land complete after
      release. This proves no subprocess transport or exit path kills it.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`. Read the last line.
- `bash tests/test_scratchpad_autosave_live.sh`.
- `bash tests/test_tui_clipboard_seam.sh`, `bash tests/test_no_lib_to_tui_import.sh`,
  `bash tests/test_shortcuts_registry_coverage.sh`, `bash tests/test_no_raw_tmux.sh`, and
  `~/.aitask/venv/bin/python -m pytest tests/test_shortcut_scopes.py -q`.
- `shellcheck .aitask-scripts/aitask_scratchpad.sh`.
- Manual: `./ait scratchpad --unsaved` (typing + a terminal paste); `./ait scratchpad --task
  2073_2` saves to `.aitask-scratchpad/2073_2/notes.md`; ctrl+q exits.

## Step 9 (Post-Implementation)

Standard child archival via task-workflow Step 9.

## Risk

### Code-health risk: low
- New isolated TUI package; registry, dispatcher and test-list edits are additive one-liners
  · severity: low · → mitigation: none
- A new launcher verb on the update-check skip list · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Autosave must survive a hard pane kill within the stated contract. A hard kill may lose
  changes not included in the latest successfully saved buffer, including edits queued
  during a pending save. The ~3 s autosave start target (no save pending) is not a maximum
  loss window. The failure mode is scheduling under continuous typing, overdue deadlines
  and the failure retry delay · severity: medium · → mitigation: none (single save-driver task
  with one scheduling formula; continuous-typing, past-due and retry-delay unit tests against
  real Textual; live SIGKILL cases a–c)
- Writer ownership must come before the first read, or a successor can overwrite newer
  notes · severity: medium · → mitigation: none (flock-before-read order, a handoff test
  with a negative control, fd-inheritance proof)
- An in-flight save orphaned by a hard kill must neither truncate the notes (partial stdin)
  nor release ownership before it lands · severity: low (residual — temp-file stdin,
  `start_new_session`, `pass_fds`, `Popen` without a killing transport; proven by inline
  post-phase orphan_save_handoff) · → mitigation: inline post-phase orphan_save_handoff
- Shutdown paths (ctrl+q, SIGHUP, unmount, quit during a pending open) must terminate the
  app and release ownership without killing an in-flight save or touching Textual-owned
  state (`_closing`, `_driver`) · severity: low (residual — `_sp_` prefix rule with an AST
  and collision test, tracked and cancelled startup task with shutdown checkpoints,
  loop-registered SIGHUP handler with `finally` exit; unit cases 12–14d, live d/f) · →
  mitigation: none
- A timed-out save whose descendant (`mv`) outlives the killed helper could commit older
  text after a successful retry. The retry reclaims the dead pid's lifecycle lock, and the
  inherited flock does not stop retries from the owning app · severity: low (residual —
  process-group kill + bounded async drain confirmation before any retry, a `STUCK`
  pending state honoured by every save entry point including the SIGHUP flush; case 14e
  with a negative control reproducing the defect, cases 14f/14g) · → mitigation: none
- A timed-out save may have replaced `notes.md` before acknowledging. An undo back to the
  last acknowledged text would then read as clean while the disk holds newer text ·
  severity: low (residual — the uncertain outcome invalidates the baseline, and the single
  `_sp_is_dirty` predicate forces a confirmed save; case 14h with negative and
  certain-failure controls) · → mitigation: none
- Timeout cleanup blocking the event loop (an uninterruptible helper under a blocking
  `waitpid`) · severity: low (residual — non-blocking `poll()` inside one deadline,
  retained handle; case 14g asserts key latency and quit while stuck) · → mitigation: none
- The sole save task must not die on an unexpected error (a None comparison, a spawn
  `OSError`), or later edits stay unsaved silently · severity: low (residual — total
  spawn, exception guard in the loop, a done-callback that surfaces task death; cases
  14b/14c) · → mitigation: none
- Key handlers must stay responsive while a save is slow · severity: low (residual — saving
  only in the driver task; unit case 4 asserts press latency while a save is parked) · →
  mitigation: none

### Planned mitigations
- timing: post-phase | name: orphan_save_handoff | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — orphaned in-flight save truncating notes or releasing ownership early | desc: Live cases (e)/(f): SIGKILL or kill-pane the app while its save is parked by the helper's pause fifo; the inherited flock stays busy, the released save lands byte-identical, and a fresh instance becomes owner
