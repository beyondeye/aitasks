#!/usr/bin/env python3
"""`ait scratchpad` — a basic notes editor for a pane bound to a code agent (t2073_2).

``--task <id>`` keeps the notes per task, through the store helper
``aitask_scratchpad_store.sh`` (t2073_1). ``--unsaved`` is a throwaway pad that
never touches the store. ``--target <pane>`` only labels the header.

**One writer per store.** The app holds an ``fcntl.flock`` on
``<store>/.holder.lock``, opened ``O_RDWR`` WITHOUT ``O_CREAT`` (only the helper's
``open`` creates it, so an app racing archival can never re-create a pruned
store). Ownership comes before content: the flock is taken first and only then is
``notes.md`` read, so a previous writer's final save is always visible to its
successor. A busy lock opens a read-only snapshot that never saves and never
promotes itself. Every ``save`` child inherits the flock fd (``pass_fds``), so an
orphaned in-flight save keeps the lock until its write lands.

**Autosave.** A save is due at ``min(last_change + DEBOUNCE,
first_unsaved_change + MAX_DIRTY_AGE)``; continuous typing postpones the debounce
but not the maximum dirty age. Saves are serialized. ctrl+s saves now, ctrl+q
attempts a final save then exits, SIGHUP spawns a detached best-effort flush.
On a hard kill, changes not included in the latest successfully saved buffer may
be lost, including edits queued during a pending save. Autosave targets starting
within roughly three seconds when no save is pending; this is not a maximum loss
window. The helper's 5 s figure bounds only its lock wait; no save duration is
bounded.

**Why there is one save-driver task and no Textual timers.** A ``set_timer``
callback (and an async action handler) is awaited by the message pump, so a slow
save there would freeze typing; and ``set_timer(0)`` — the natural "overdue, fire
now" — raises ``ZeroDivisionError`` inside ``Timer._run`` (Textual 8.2.7). So key
handlers only update state and wake ``_sp_save_loop``, which recomputes the due
time with plain arithmetic and is the only place a save ever runs.

**Why saves use ``subprocess.Popen`` and temp files.** An asyncio subprocess
transport kills a still-running child when it closes, which would kill an
in-flight save on a graceful exit. Stdin is a fully written anonymous temp file,
never a pipe: a parent killed mid-write would hand the helper a truncated buffer
it would commit as a success. Children run in their own session, so the pane's
SIGHUP does not reach them.

**Timeouts and unresolved writes.** The helper's final step is a separate ``mv``.
A timed-out save is therefore ended by killing its whole process group and
confirming the group is empty before any retry; if that cannot be confirmed the
attempt stays pending (``STUCK``) and no save starts — ``_sp_write_unresolved``
guards every save entry point. A save whose outcome is unknown (timeout, error)
may already have replaced the file, so it invalidates the known-disk baseline and
the next save is forced even when the buffer equals the old acknowledged text.

Every app-owned private name carries the ``_sp_`` prefix: Textual's App owns
``_driver`` and ``_closing`` (and more), and shadowing either breaks shutdown.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HERE.parent
for _p in (str(_SCRIPTS_DIR), str(_SCRIPTS_DIR / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rich.text import Text  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.widgets import Static, TextArea  # noqa: E402

from multirow_footer import MultiRowFooter  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402
from tui_clipboard import copy_to_system_clipboard  # noqa: E402

#: The store helper. Read through the module at call time so tests can swap it.
_STORE_SH = _SCRIPTS_DIR / "aitask_scratchpad_store.sh"

DEBOUNCE = 1.0
MAX_DIRTY_AGE = 3.0
#: Fixed delay before retrying a failed save, measured from its completion.
RETRY_DELAY = 2.0
STORE_CMD_TIMEOUT = 30.0
#: Budget for killing a timed-out save's process group and seeing it empty.
GROUP_DRAIN_TIMEOUT = 5.0
POLL = 0.05
#: How often a STUCK attempt is re-probed.
STUCK_POLL = 1.0

ST_OPENING = "opening…"
ST_SAVED = "saved"
ST_SAVING = "saving…"
ST_DIRTY = "unsaved changes"
ST_UNSAVED_MODE = "NOT SAVED (no task)"
ST_READONLY = "read-only: open elsewhere"
ST_ARCHIVED = "not saved — task archived"
ST_NO_TASK = "not saved — no active task"
ST_STORE_ERROR = "not saved — store unavailable"
ST_SAVE_FAILED = "save failed — retrying in {n}s"
ST_STUCK = "save stuck — waiting for the previous write to finish"
ST_QUITTING = "saving before quit…"
ST_DRIVER_ERROR = "autosave stopped — error"

_MODE_STATUS = {
    "opening": ST_OPENING,
    "unsaved": ST_UNSAVED_MODE,
    "readonly": ST_READONLY,
    "archived": ST_ARCHIVED,
    "no_task": ST_NO_TASK,
    "store_error": ST_STORE_ERROR,
}

_TASK_ID_RE = re.compile(r"^t?([0-9]+(?:_[0-9]+)?)$")
_SAVED_RE = re.compile(r"SAVED:(?:[0-9]+|empty)")


# --- store helper plumbing (module-level seams) ------------------------------

def _sp_acquire_holder(fd: int) -> bool:
    """Take the writer flock without blocking. ``False`` means another holder."""
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _sp_spawn_store(args, stdin_bytes: bytes = b"", holder_fd: int | None = None):
    """Start the store helper. Total: returns ``(proc, out_file, err)``.

    Stdin is a fully written anonymous temp file (never a pipe — see the module
    docstring); stdout+stderr go to another one, read after exit. The child gets
    its own session, so its pid is its process-group id. On any preparation or
    spawn failure every temp file created so far is closed and
    ``(None, None, "ERROR:spawn: …")`` is returned.
    """
    in_file = out_file = None
    try:
        in_file = tempfile.TemporaryFile()
        if stdin_bytes:
            in_file.write(stdin_bytes)
            in_file.flush()
            in_file.seek(0)
        out_file = tempfile.TemporaryFile()
        proc = subprocess.Popen(
            [str(_STORE_SH), *args],
            stdin=in_file,
            stdout=out_file,
            stderr=subprocess.STDOUT,
            pass_fds=(holder_fd,) if holder_fd is not None else (),
            start_new_session=True,
        )
        return proc, out_file, None
    except Exception as exc:  # noqa: BLE001 - total by contract
        if out_file is not None:
            out_file.close()
        return None, None, f"ERROR:spawn: {exc}"
    finally:
        if in_file is not None:
            in_file.close()


def _sp_killpg(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass


def _sp_group_alive(pgid: int) -> bool:
    """Whether any process (zombies included) is left in ``pgid``."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def _sp_terminate_group(proc) -> bool:
    """Kill a timed-out save's whole group; ``True`` once it is provably empty.

    Never a blocking ``wait``: the direct child is reaped with ``poll()`` inside
    one deadline, so a helper stuck in uninterruptible I/O cannot freeze the
    event loop. ``False`` means the group could not be confirmed empty.
    """
    pgid = proc.pid
    _sp_killpg(pgid, signal.SIGKILL)
    deadline = time.monotonic() + GROUP_DRAIN_TIMEOUT
    while True:
        if proc.poll() is not None and not _sp_group_alive(pgid):
            return True
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(POLL)


async def _sp_await_store(proc, out_file, timeout: float):
    """Wait for a helper child without blocking the loop. ``(rc, output)``.

    Never raises except ``CancelledError``, and a cancel does NOT kill the child:
    an in-flight save must survive the app's shutdown. A timeout returns
    ``(1, "ERROR:timed out")`` once the group is gone, or ``(1, "STUCK:<pgid>")``.
    """
    try:
        deadline = time.monotonic() + timeout
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                if await _sp_terminate_group(proc):
                    return 1, "ERROR:timed out"
                return 1, f"STUCK:{proc.pid}"
            await asyncio.sleep(POLL)
        try:
            out_file.seek(0)
            out = out_file.read().decode("utf-8", "replace").strip()
        except (OSError, ValueError) as exc:
            out = f"ERROR:cannot read helper output: {exc}"
        return proc.returncode, out
    finally:
        out_file.close()


async def _sp_run_store(args, stdin_bytes: bytes = b"", holder_fd: int | None = None):
    proc, out_file, err = _sp_spawn_store(args, stdin_bytes, holder_fd)
    if err is not None:
        return 1, err
    return await _sp_await_store(proc, out_file, STORE_CMD_TIMEOUT)


def _sp_min_time(*values: float | None) -> float:
    """Minimum of the non-``None`` values; the last argument is the fallback."""
    present = [v for v in values if v is not None]
    return min(present)


def _sp_last_line(out: str) -> str:
    lines = out.splitlines()
    return lines[-1].strip() if lines else ""


def _sp_read_notes(store_dir: Path) -> str:
    try:
        data = (store_dir / "notes.md").read_bytes()
    except FileNotFoundError:
        return ""
    return data.decode("utf-8", "replace")


# --- widgets ------------------------------------------------------------------

class ScratchEditor(TextArea):
    """TextArea whose copy and cut reach the system clipboard (tui_clipboard)."""

    def action_copy(self) -> None:
        # The whole buffer when nothing is selected: the common "grab my notes"
        # case needs no selection gesture.
        copy_to_system_clipboard(self.app, self.selected_text or self.text)

    def action_cut(self) -> None:
        # Stock TextArea.action_cut, with its copy routed through the seam.
        if self.read_only:
            return
        start, end = self.selection
        if start == end:
            edit_result = self._delete_cursor_line()
        else:
            edit_result = self._delete_via_keyboard(start, end)
        if edit_result is not None:
            copy_to_system_clipboard(self.app, edit_result.replaced_text)


class ScratchpadApp(ShortcutsMixin, App):
    """Notes editor for one task (``task_id``) or an unsaved pad (``None``)."""

    _shortcuts_scope = "scratchpad"
    TITLE = "ait scratchpad"
    AUTO_FOCUS = "#sp-editor"

    CSS = """
    #sp-header { background: $boost; padding: 0 1; height: 1; }
    #sp-editor { height: 1fr; }
    """

    # Modifier keys only: every letter belongs to the editor. All three are
    # priority bindings so they win over the focused TextArea (which owns
    # ctrl+c itself) and replace App's own ctrl+q quit / ctrl+c help_quit. Their
    # actions are sync and never await a save (see the module docstring).
    BINDINGS = [
        Binding("ctrl+s", "save_now", "Save", priority=True),
        Binding("ctrl+q", "flush_quit", "Quit", priority=True),
        Binding("ctrl+c", "copy", "Copy", priority=True),
    ]

    def __init__(self, task_id: str | None, target: str | None = None) -> None:
        super().__init__()
        self._sp_task_id = task_id
        self._sp_target = target
        self._sp_mode = "unsaved" if task_id is None else "opening"
        self._sp_editor = ScratchEditor(
            id="sp-editor", soft_wrap=True, read_only=task_id is not None
        )
        self._sp_status = _MODE_STATUS[self._sp_mode]
        self._sp_holder_fd: int | None = None
        self._sp_store_dir: Path | None = None
        # Text confirmed on disk; None while the disk state is unknown.
        self._sp_persisted_text: str | None = None
        self._sp_first_unsaved: float | None = None
        self._sp_last_change: float | None = None
        self._sp_edits_during_save_first: float | None = None
        self._sp_save_in_flight = False
        self._sp_save_now_requested = False
        self._sp_retry_at: float | None = None
        self._sp_stuck_pgid: int | None = None
        self._sp_stuck_proc = None
        self._sp_quit_requested = False
        self._sp_final_attempted = False
        self._sp_driver_error = False
        self._sp_shutdown = False
        self._sp_wake = asyncio.Event()
        self._sp_startup_task: asyncio.Task | None = None
        self._sp_save_task: asyncio.Task | None = None
        self._sp_sighup_installed = False

    # --- layout / status --------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(self._sp_header_text(), id="sp-header")
        yield self._sp_editor
        yield MultiRowFooter()

    def _sp_header_text(self) -> Text:
        name = f"t{self._sp_task_id}" if self._sp_task_id else "scratch"
        text = f"{name} · {self._sp_status}"
        if self._sp_target:
            text += f" · → {self._sp_target}"
        return Text(text)

    def _sp_refresh_status(self) -> None:
        if self._sp_mode != "owner":
            status = _MODE_STATUS[self._sp_mode]
        elif self._sp_driver_error:
            status = ST_DRIVER_ERROR
        elif self._sp_stuck_pgid is not None:
            status = ST_STUCK
        elif self._sp_save_in_flight:
            status = ST_SAVING
        elif self._sp_quit_requested:
            status = ST_QUITTING
        elif self._sp_is_dirty():
            if self._sp_retry_at is not None:
                wait = max(0, round(self._sp_retry_at - time.monotonic()))
                status = ST_SAVE_FAILED.format(n=wait)
            else:
                status = ST_DIRTY
        else:
            status = ST_SAVED
        self._sp_status = status
        if self._sp_shutdown:
            return
        try:
            self.query_one("#sp-header", Static).update(self._sp_header_text())
        except Exception:  # noqa: BLE001 - not mounted (yet / any more)
            pass

    # --- state predicates ----------------------------------------------------

    def _sp_is_dirty(self) -> bool:
        """THE dirty predicate: buffer differs from the text confirmed on disk."""
        if self._sp_persisted_text is None:
            return True
        return self._sp_editor.text != self._sp_persisted_text

    def _sp_write_unresolved(self) -> bool:
        """A write may still complete: in flight, or a STUCK aborted attempt."""
        return self._sp_save_in_flight or self._sp_stuck_pgid is not None

    # --- startup: ownership before content -----------------------------------

    def on_mount(self) -> None:
        try:
            asyncio.get_running_loop().add_signal_handler(
                signal.SIGHUP, self._sp_on_sighup)
            self._sp_sighup_installed = True
        except (NotImplementedError, RuntimeError, ValueError):
            pass
        if self._sp_mode == "opening":
            self._sp_startup_task = asyncio.create_task(self._sp_startup())
        self._sp_refresh_status()

    async def _sp_startup(self) -> None:
        try:
            rc, out = await _sp_run_store(["open", self._sp_task_id])
            if self._sp_shutdown:
                return
            last = _sp_last_line(out)
            if rc == 0 and last == "NO_TASK":
                self._sp_mode = "no_task"
            elif rc != 0 or not (last.startswith("OPENED:")
                                 and last.endswith("/notes.md")):
                self._sp_mode = "store_error"
                self.notify(f"scratchpad store: {out or f'exit {rc}'}",
                            severity="error")
            else:
                await self._sp_claim_and_load(
                    Path(last[len("OPENED:"):]).parent)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - never crash on startup
            if not self._sp_shutdown:
                self._sp_mode = "store_error"
                self.notify(f"scratchpad store: {exc}", severity="error")
        finally:
            if not self._sp_shutdown:
                if self._sp_mode not in ("owner", "readonly"):
                    self._sp_editor.read_only = False
                self._sp_refresh_status()

    async def _sp_claim_and_load(self, store_dir: Path) -> None:
        """Open the holder (no O_CREAT), take the flock, THEN read the notes."""
        fd = None
        try:
            try:
                fd = os.open(store_dir / ".holder.lock", os.O_RDWR)
            except FileNotFoundError:
                self._sp_mode = "archived"
                return
            if self._sp_shutdown:
                return
            if not _sp_acquire_holder(fd):
                os.close(fd)
                fd = None
                text = _sp_read_notes(store_dir)
                if self._sp_shutdown:
                    return
                self._sp_editor.load_text(text)
                self._sp_editor.read_only = True
                self._sp_mode = "readonly"
                return
            if self._sp_shutdown:
                return
            text = _sp_read_notes(store_dir)
            self._sp_store_dir = store_dir
            self._sp_persisted_text = text
            self._sp_editor.load_text(text)
            self._sp_editor.read_only = False
            self._sp_holder_fd, fd = fd, None
            self._sp_mode = "owner"
            self._sp_save_task = asyncio.create_task(self._sp_save_loop())
            self._sp_save_task.add_done_callback(self._sp_on_save_task_done)
        finally:
            if fd is not None:
                os.close(fd)

    # --- editing and keys (never await) --------------------------------------

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self._sp_mode != "owner" or self._sp_shutdown:
            return
        now = time.monotonic()
        if not self._sp_save_in_flight and not self._sp_is_dirty():
            self._sp_first_unsaved = None
        else:
            self._sp_last_change = now
            if self._sp_save_in_flight:
                if self._sp_edits_during_save_first is None:
                    self._sp_edits_during_save_first = now
            elif self._sp_first_unsaved is None:
                self._sp_first_unsaved = now
        self._sp_refresh_status()
        self._sp_wake.set()

    def action_save_now(self) -> None:
        if self._sp_mode != "owner":
            self.notify(self._sp_status)
            return
        self._sp_save_now_requested = True
        self._sp_wake.set()

    def action_flush_quit(self) -> None:
        """Attempt the final save, report a failure, then exit."""
        if (self._sp_mode != "owner" or self._sp_save_task is None
                or self._sp_save_task.done()):
            self._sp_exit_now()
            return
        if self._sp_quit_requested:
            return
        self._sp_quit_requested = True
        self._sp_save_now_requested = True
        self._sp_refresh_status()
        self._sp_wake.set()

    async def action_quit(self) -> None:
        # The command palette's "Quit" system command (and any other caller of
        # the inherited quit action) must flush like ctrl+q — the stock
        # implementation exits at once, over dirty notes.
        self.action_flush_quit()

    def action_copy(self) -> None:
        self._sp_editor.action_copy()

    # --- the save driver -----------------------------------------------------

    def _sp_next_due(self, now: float) -> float | None:
        """When the next save may start — the one scheduling formula."""
        if self._sp_mode != "owner":
            return None
        if self._sp_stuck_pgid is not None:
            return now + STUCK_POLL  # a poll, never a save
        if self._sp_write_unresolved() or not self._sp_is_dirty():
            return None
        if self._sp_first_unsaved is None:
            self._sp_first_unsaved = now
        if self._sp_save_now_requested:
            return now
        last = (self._sp_last_change if self._sp_last_change is not None
                else self._sp_first_unsaved)
        edit_due = min(last + DEBOUNCE, self._sp_first_unsaved + MAX_DIRTY_AGE)
        if self._sp_retry_at is not None:
            return max(edit_due, self._sp_retry_at)
        return edit_due

    async def _sp_save_loop(self) -> None:
        while not self._sp_shutdown:
            if self._sp_stuck_pgid is not None:
                self._sp_poll_stuck()
            if self._sp_mode != "owner":
                if self._sp_quit_requested:
                    self._sp_exit_now()
                return
            if self._sp_quit_requested:
                if self._sp_stuck_pgid is not None:
                    self._sp_exit_now(
                        "scratchpad: previous write unresolved — exited "
                        "without the final save; unsaved edits may be lost")
                    return
                if not self._sp_save_in_flight and (
                        not self._sp_is_dirty() or self._sp_final_attempted):
                    self._sp_exit_now(
                        None if not self._sp_is_dirty() else
                        "scratchpad: final save failed — unsaved edits may "
                        "be lost")
                    return
            now = time.monotonic()
            due = self._sp_next_due(now)
            if due is None or due > now:
                self._sp_wake.clear()
                try:
                    await asyncio.wait_for(
                        self._sp_wake.wait(),
                        None if due is None else due - now)
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                await self._sp_save_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - the sole save task must live
                self._sp_save_in_flight = False
                self._sp_record_failure(f"ERROR:{exc!r}", uncertain=True)
                self._sp_refresh_status()

    async def _sp_save_once(self) -> None:
        if self._sp_write_unresolved():
            return
        if not self._sp_is_dirty():
            self._sp_save_now_requested = False
            return
        text = self._sp_editor.text
        quit_at_start = self._sp_quit_requested
        self._sp_save_in_flight = True
        self._sp_edits_during_save_first = None
        self._sp_save_now_requested = False
        self._sp_refresh_status()
        proc = None
        try:
            proc, out_file, err = _sp_spawn_store(
                ["save", self._sp_task_id],
                text.encode("utf-8", "replace"),
                self._sp_holder_fd)
            if err is not None:
                rc, out = 1, err
            else:
                rc, out = await _sp_await_store(
                    proc, out_file, STORE_CMD_TIMEOUT)
        finally:
            self._sp_save_in_flight = False
        if quit_at_start:
            self._sp_final_attempted = True
        last = _sp_last_line(out)
        if rc == 0 and _SAVED_RE.fullmatch(last):
            self._sp_persisted_text = text
            self._sp_retry_at = None
            if self._sp_is_dirty():
                self._sp_first_unsaved = (
                    self._sp_edits_during_save_first
                    if self._sp_edits_during_save_first is not None
                    else time.monotonic())
            else:
                self._sp_first_unsaved = None
        elif rc == 0 and last in ("ARCHIVED", "ABSENT"):
            self._sp_mode = "archived"
        elif err is not None or (rc == 3 and last == "LOCK_BUSY"):
            # Certain no-write: no child ran, or the helper refused before
            # touching the store.
            self._sp_record_failure(out, uncertain=False)
        else:
            if out.startswith("STUCK:") and proc is not None:
                self._sp_stuck_pgid = proc.pid
                self._sp_stuck_proc = proc
            self._sp_record_failure(out, uncertain=True)
        self._sp_refresh_status()

    def _sp_record_failure(self, out: str, uncertain: bool) -> None:
        """Schedule the retry; an uncertain outcome forgets the disk baseline."""
        now = time.monotonic()
        if uncertain:
            # The replacement may have committed before the failure: the disk
            # holds an unknown text, so the next save must not be skipped.
            self._sp_persisted_text = None
        self._sp_retry_at = now + RETRY_DELAY
        self._sp_first_unsaved = _sp_min_time(
            self._sp_first_unsaved, self._sp_edits_during_save_first, now)

    def _sp_poll_stuck(self) -> None:
        proc = self._sp_stuck_proc
        if ((proc is None or proc.poll() is not None)
                and not _sp_group_alive(self._sp_stuck_pgid)):
            self._sp_stuck_pgid = None
            self._sp_stuck_proc = None
            self._sp_refresh_status()

    def _sp_on_save_task_done(self, task: asyncio.Task) -> None:
        if task.cancelled() or self._sp_shutdown:
            return
        if task.exception() is not None:
            self._sp_driver_error = True
            self._sp_refresh_status()
            self.notify(ST_DRIVER_ERROR, severity="error")

    # --- shutdown --------------------------------------------------------------

    def _sp_exit_now(self, message: str | None = None) -> None:
        """Exit without awaiting any save; an in-flight child keeps running."""
        if self._sp_shutdown:
            return
        self._sp_shutdown = True
        self._sp_wake.set()
        self.exit(message=message)

    def _sp_spawn_detached_flush(self) -> None:
        """Best-effort SIGHUP flush; never waits, never raises."""
        try:
            if (self._sp_mode != "owner" or self._sp_write_unresolved()
                    or self._sp_shutdown or not self._sp_is_dirty()):
                return
            _proc, out_file, _err = _sp_spawn_store(
                ["save", self._sp_task_id],
                self._sp_editor.text.encode("utf-8", "replace"),
                self._sp_holder_fd)
            if out_file is not None:
                out_file.close()
        except Exception:  # noqa: BLE001 - a flush may fail, never raise
            pass

    def _sp_on_sighup(self) -> None:
        try:
            self._sp_spawn_detached_flush()
        finally:
            self._sp_exit_now()

    async def on_unmount(self) -> None:
        self._sp_shutdown = True
        self._sp_wake.set()
        if self._sp_sighup_installed:
            try:
                asyncio.get_running_loop().remove_signal_handler(signal.SIGHUP)
            except Exception:  # noqa: BLE001
                pass
            self._sp_sighup_installed = False
        for task in (self._sp_startup_task, self._sp_save_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except BaseException:  # noqa: BLE001 - cancelled or failed
                    pass
        if self._sp_holder_fd is not None:
            try:
                os.close(self._sp_holder_fd)
            except OSError:
                pass
            self._sp_holder_fd = None


def _sp_parse_args(argv: list[str]):
    """``(rc, task_id, target)``; ``rc`` is ``None`` when the app should run."""
    parser = argparse.ArgumentParser(
        prog="ait scratchpad",
        description="Notes editor for a code-agent pane.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--task", metavar="ID",
                      help="persist the notes for this task (e.g. 42 or 42_3)")
    mode.add_argument("--unsaved", action="store_true",
                      help="a throwaway pad that is never saved")
    parser.add_argument("--target", metavar="PANE",
                        help="the bound agent pane (shown in the header)")
    try:
        ns = parser.parse_args(argv)
    except SystemExit as exc:
        return (exc.code if isinstance(exc.code, int) else 2), None, None
    if ns.task is None:
        return None, None, ns.target
    match = _TASK_ID_RE.match(ns.task)
    if not match:
        print(f"ait scratchpad: invalid task id: {ns.task}", file=sys.stderr)
        return 2, None, None
    return None, match.group(1), ns.target


def main(argv: list[str] | None = None) -> int:
    rc, task_id, target = _sp_parse_args(
        list(sys.argv[1:] if argv is None else argv))
    if rc is not None:
        return rc
    app = ScratchpadApp(task_id, target)
    app.run()
    return app.return_code or 0


if __name__ == "__main__":
    sys.exit(main())
