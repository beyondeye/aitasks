#!/usr/bin/env python3
"""Behavioural pins for the `ait scratchpad` notes editor (t2073_2).

Every case drives the real Textual app under ``App.run_test`` against a
temporary store, with the REAL store helper (``aitask_scratchpad_store.sh``)
unless a case swaps ``_STORE_SH`` for a small fake that delegates ``open`` to the
real helper and scripts ``save`` (failures, delays, fd/session probes). Timing
cases use the real wall clock — the point is how the installed Textual and the
save driver behave, not a mocked timer.

The groups worth naming, each pinning a defect found in plan review:

* responsiveness (case 4) — a save must never run inside the message pump;
* overdue deadlines (case 5) — no zero-delay ``set_timer`` (it raises in 8.2.7);
* retry delay and recovery (6, 14b, 14c) — the sole save task must survive any
  failure, and new edits must not shorten the fixed retry delay;
* ownership (8, 9, 10, 12, 13, 14d) — flock before read, inherited by every save
  child, released on every exit path;
* unresolved writes (14e–14h) — a timed-out save's whole process group is
  stopped before a retry, a STUCK attempt blocks every save entry point, and an
  unconfirmed outcome forces the next save even when the buffer equals the old
  acknowledged text. 14e and 14h each carry a negative control that reproduces
  the original defect.

Run: bash tests/run_all_python_tests.sh (or this file directly)
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import errno
import fcntl
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

from scratchpad import scratchpad_app as sp  # noqa: E402
from textual.app import App  # noqa: E402
from textual.driver import Driver  # noqa: E402
from textual.widgets import TextArea  # noqa: E402
from textual.widgets.text_area import Selection  # noqa: E402

REAL_STORE = str(sp._STORE_SH)
MODULE_PATH = Path(sp.__file__)
REAL_MV = shutil.which("mv")
REAL_POPEN = subprocess.Popen
REAL_TEMPFILE = tempfile.TemporaryFile

FAKE_STORE = textwrap.dedent("""\
    #!{python}
    import json, os, subprocess, sys, time
    ctl = json.load(open(os.environ["SP_FAKE_CTL"]))
    real = os.environ["SP_REAL_STORE"]
    if sys.argv[1] != "save":
        os.execv(real, [real] + sys.argv[1:])
    data = sys.stdin.buffer.read()
    state = os.environ["SP_FAKE_STATE"]
    n = int(open(state).read()) if os.path.exists(state) else 0
    n += 1
    open(state, "w").write(str(n))
    rec = {{"n": n, "start": time.time()}}
    holder = ctl.get("check_fd")
    if holder:
        want = os.stat(holder)
        seen = False
        for name in os.listdir("/dev/fd"):
            try:
                st = os.fstat(int(name))
            except (OSError, ValueError):
                continue
            if (st.st_dev, st.st_ino) == (want.st_dev, want.st_ino):
                seen = True
        rec["inherited"] = seen
        rec["new_session"] = os.getsid(0) != os.getsid(os.getppid())
    if n == 1 and ctl.get("sleep_first"):
        time.sleep(ctl["sleep_first"])
    if ctl.get("delay"):
        time.sleep(ctl["delay"])
    if n <= ctl.get("fail_n", 0):
        rec.update(end=time.time(), ok=False)
        with open(os.environ["SP_FAKE_LOG"], "a") as log:
            log.write(json.dumps(rec) + "\\n")
        if ctl.get("fail_rc", 4) == 3:
            print("LOCK_BUSY")
        else:
            print("Error: injected failure", file=sys.stderr)
        sys.exit(ctl.get("fail_rc", 4))
    p = subprocess.run([real, "save", sys.argv[2]], input=data,
                       capture_output=True)
    rec.update(end=time.time(), ok=p.returncode == 0)
    with open(os.environ["SP_FAKE_LOG"], "a") as log:
        log.write(json.dumps(rec) + "\\n")
    sys.stdout.buffer.write(p.stdout)
    sys.exit(p.returncode)
    """)

SHIM_MV = textwrap.dedent("""\
    #!/usr/bin/env bash
    last="${{@: -1}}"
    if [[ "$last" == */notes.md && -e "$SHIM/block_once" ]]; then
        rm -f "$SHIM/block_once"
        echo $$ > "$SHIM/blocked.pid"
        read -r _ < "$SHIM/fifo"
    elif [[ "$last" == */notes.md && -e "$SHIM/block_after" ]]; then
        rm -f "$SHIM/block_after"
        {mv} "$@"
        rc=$?
        echo $$ > "$SHIM/blocked.pid"
        read -r _ < "$SHIM/fifo"
        exit $rc
    fi
    exec {mv} "$@"
    """)


def _write_line(path: Path) -> None:
    with open(path, "w") as fh:  # blocks until a reader is present
        fh.write("go\n")


class _Base(unittest.IsolatedAsyncioTestCase):
    """Temp task tree + store, the real helper, and a spawn recorder."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ait_sp_"))
        self.tasks = self.tmp / "aitasks"
        self.tasks.mkdir()
        self.task_file = self.tasks / "t42_x.md"
        self.task_file.write_text("---\nstatus: Implementing\n---\n")
        self.pad = self.tmp / "pad"
        self.store = self.pad / "42"
        self.notes_path = self.store / "notes.md"
        self.holder = self.store / ".holder.lock"
        self.env = mock.patch.dict(os.environ, {
            "TASK_DIR": str(self.tasks),
            "AITASK_SCRATCHPAD_DIR": str(self.pad),
        })
        self.env.start()
        os.environ.pop("AITASK_SCRATCHPAD_PAUSE_FIFO", None)
        self.spawns: list[dict] = []
        self.pgids: list[int] = []
        real_spawn = sp._sp_spawn_store

        def spawn(args, stdin_bytes=b"", holder_fd=None):
            rec = {"args": list(args), "t": time.monotonic(),
                   "text": stdin_bytes.decode("utf-8", "replace")}
            self.spawns.append(rec)
            res = real_spawn(args, stdin_bytes, holder_fd)
            if res[0] is not None:
                self.pgids.append(res[0].pid)
            return res

        self._patches = [mock.patch.object(sp, "_sp_spawn_store", spawn)]
        for p in self._patches:
            p.start()
        self.loop_errors: list[dict] = []

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()
        self.env.stop()
        for pgid in self.pgids:
            with contextlib.suppress(OSError):
                os.killpg(pgid, signal.SIGKILL)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- fixture helpers ----------------------------------------------------

    def patch(self, target, name, value) -> None:
        p = mock.patch.object(target, name, value)
        p.start()
        self._patches.append(p)

    def run_store(self, *args, text: str | None = None) -> str:
        p = subprocess.run([REAL_STORE, *args], input=(text or "").encode(),
                           capture_output=True, check=True)
        return p.stdout.decode().strip()

    def seed(self, text: str | None = None) -> None:
        self.run_store("open", "42")
        if text is not None:
            self.run_store("save", "42", text=text)

    def notes(self) -> str | None:
        try:
            return self.notes_path.read_text()
        except FileNotFoundError:
            return None

    def saves(self) -> list[dict]:
        return [s for s in self.spawns if s["args"][:1] == ["save"]]

    def holder_free(self) -> bool:
        fd = os.open(self.holder, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False
        finally:
            os.close(fd)

    def use_fake(self, **ctl) -> None:
        fake = self.tmp / "fake_store.py"
        fake.write_text(FAKE_STORE.format(python=sys.executable))
        fake.chmod(0o755)
        (self.tmp / "ctl.json").write_text(json.dumps(ctl))
        os.environ.update({
            "SP_FAKE_CTL": str(self.tmp / "ctl.json"),
            "SP_FAKE_STATE": str(self.tmp / "fake.state"),
            "SP_FAKE_LOG": str(self.tmp / "fake.log"),
            "SP_REAL_STORE": REAL_STORE,
        })
        self.patch(sp, "_STORE_SH", fake)

    def fake_log(self) -> list[dict]:
        path = self.tmp / "fake.log"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def use_shim(self) -> Path:
        shim = self.tmp / "shim"
        shim.mkdir()
        (shim / "mv").write_text(SHIM_MV.format(mv=REAL_MV))
        (shim / "mv").chmod(0o755)
        os.mkfifo(shim / "fifo")
        os.environ["SHIM"] = str(shim)
        os.environ["PATH"] = f"{shim}:{os.environ['PATH']}"
        return shim

    def record_loop_errors(self) -> None:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda _l, ctx: self.loop_errors.append(ctx))

    async def wait_for(self, pred, timeout: float = 10.0, msg: str = "") -> None:
        deadline = time.monotonic() + timeout
        while not pred():
            if time.monotonic() > deadline:
                self.fail(f"timed out waiting: {msg}")
            await asyncio.sleep(0.05)

    async def owner(self, app, pilot) -> None:
        await self.wait_for(lambda: app._sp_mode != "opening", msg="startup")
        self.assertEqual(app._sp_mode, "owner")

    async def idle(self, app) -> None:
        """Settle: no save in flight and nothing due, so nothing outlives the test."""
        def quiet():
            return (not app._sp_save_in_flight
                    and (app._sp_mode != "owner"
                         or app._sp_next_due(time.monotonic()) is None))
        await self.wait_for(quiet, msg="driver idle")

    def record_exit(self, app) -> list:
        """Capture ``exit(message=…)``: Textual prints and clears the renderables."""
        messages: list = []
        real_exit = app.exit

        def exit_(*a, **kw):
            messages.append(kw.get("message"))
            return real_exit(*a, **kw)

        app.exit = exit_
        return messages

    async def press_timed(self, pilot, key: str) -> float:
        t0 = time.monotonic()
        await pilot.press(key)
        return time.monotonic() - t0


class LoadAndAutosaveTests(_Base):
    async def test_01_loads_existing_notes(self):
        self.seed("hello\nworld\n")
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            self.assertEqual(app._sp_editor.text, "hello\nworld\n")
            self.assertEqual(app._sp_status, sp.ST_SAVED)
            self.assertIn("t42 · saved", str(app._sp_header_text()))
            self.assertFalse(app._sp_editor.read_only)

    async def test_02_debounced_save(self):
        self.seed()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("a", "b", "c")
            await asyncio.sleep(1.6)
            await self.idle(app)
            self.assertEqual(self.notes(), "abc")
            self.assertEqual(app._sp_status, sp.ST_SAVED)

    async def _type_continuously(self, app, pilot) -> tuple[float, float]:
        first = time.monotonic()
        end = first + 5.0
        while time.monotonic() < end:
            await pilot.press("x")
            await asyncio.sleep(0.2)
        return first, time.monotonic()

    async def test_03_deadline_under_continuous_typing(self):
        self.seed()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            first, _end = await self._type_continuously(app, pilot)
            saves = self.saves()
            self.assertTrue(saves, "no save started during 5 s of typing")
            self.assertLessEqual(saves[0]["t"] - first, 3.5)
            await self.idle(app)

    async def test_03_control_without_deadline_no_save_while_typing(self):
        self.patch(sp, "MAX_DIRTY_AGE", 1e9)
        self.seed()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            _first, end = await self._type_continuously(app, pilot)
            self.assertEqual([s for s in self.saves() if s["t"] < end], [])
            await asyncio.sleep(1.3)
            await self.idle(app)
            self.assertEqual(len(self.saves()), 1)

    async def test_04_input_responsive_and_saves_serialized_while_held(self):
        self.seed()
        fifo = self.tmp / "pause"
        os.mkfifo(fifo)
        reached = Path(f"{fifo}.reached")
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            os.environ["AITASK_SCRATCHPAD_PAUSE_FIFO"] = str(fifo)
            await pilot.press("a")
            await pilot.press("ctrl+s")
            await self.wait_for(reached.exists, msg="save parked")
            for key in ("b", "c", "d", "e", "f", "ctrl+s"):
                self.assertLess(await self.press_timed(pilot, key), 0.3, key)
            self.assertEqual(app._sp_editor.text, "abcdef")
            self.assertEqual(len(self.saves()), 1)
            self.assertEqual(self.saves()[0]["text"], "a")
            del os.environ["AITASK_SCRATCHPAD_PAUSE_FIFO"]
            await asyncio.to_thread(_write_line, fifo)
            await self.wait_for(lambda: len(self.saves()) == 2, msg="follow-up")
            await self.idle(app)
            self.assertEqual(len(self.saves()), 2)
            self.assertEqual(self.saves()[1]["text"], "abcdef")
            self.assertEqual(self.notes(), "abcdef")

    async def test_05_past_due_deadline_fires_immediately(self):
        self.seed()
        fifo = self.tmp / "pause"
        os.mkfifo(fifo)
        reached = Path(f"{fifo}.reached")
        ends: list[float] = []
        real_await = sp._sp_await_store

        async def timed_await(proc, out_file, timeout):
            try:
                return await real_await(proc, out_file, timeout)
            finally:
                ends.append(time.monotonic())

        self.patch(sp, "_sp_await_store", timed_await)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            os.environ["AITASK_SCRATCHPAD_PAUSE_FIFO"] = str(fifo)
            await pilot.press("a")
            await pilot.press("ctrl+s")
            await self.wait_for(reached.exists, msg="save parked")
            await asyncio.sleep(0.5)
            await pilot.press("b")
            await asyncio.sleep(3.5)  # the deadline is now well past
            del os.environ["AITASK_SCRATCHPAD_PAUSE_FIFO"]
            await asyncio.to_thread(_write_line, fifo)
            await self.wait_for(lambda: len(self.saves()) == 2, msg="follow-up")
            first_end = min(e for e in ends if e > self.saves()[0]["t"])
            self.assertLessEqual(self.saves()[1]["t"] - first_end, 0.5)
            await self.idle(app)
            self.assertIsNone(app._exception)
            self.assertEqual(self.notes(), "ab")

    async def test_07_unsaved_mode_writes_nothing(self):
        app = sp.ScratchpadApp(None)
        async with app.run_test() as pilot:
            await pilot.press("a", "b")
            await pilot.press("ctrl+s")
            await asyncio.sleep(3.5)
            self.assertEqual(app._sp_editor.text, "ab")
            self.assertEqual(self.spawns, [])
            self.assertFalse(self.pad.exists())
            self.assertEqual(app._sp_status, sp.ST_UNSAVED_MODE)
            self.assertIn("NOT SAVED (no task)", str(app._sp_header_text()))

    async def test_11_archived_shows_in_header_and_stops(self):
        self.seed("base")
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            (self.tasks / "archived").mkdir()
            self.task_file.rename(self.tasks / "archived" / self.task_file.name)
            await pilot.press("z")
            await self.wait_for(lambda: app._sp_mode == "archived", msg="archived")
            self.assertEqual(app._sp_status, sp.ST_ARCHIVED)
            count = len(self.saves())
            await pilot.press("y")
            await asyncio.sleep(3.5)
            self.assertEqual(len(self.saves()), count)
            self.assertEqual(self.notes(), "base")


class RetryTests(_Base):
    async def test_06_fixed_retry_delay_then_recovery(self):
        self.seed()
        self.use_fake(fail_n=3, fail_rc=4)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("a", "ctrl+s")
            await self.wait_for(lambda: len(self.fake_log()) >= 1, msg="1st")
            self.assertTrue(app._sp_status.startswith("save failed"))
            await pilot.press("b")  # typing during the retry delay
            await self.wait_for(lambda: len(self.fake_log()) >= 4, timeout=15,
                                msg="4 attempts")
            log = self.fake_log()
            for prev, nxt in zip(log, log[1:]):
                gap = nxt["start"] - prev["end"]
                self.assertGreaterEqual(gap, sp.RETRY_DELAY - 0.1)
                self.assertLessEqual(gap, sp.RETRY_DELAY + 1.0)
            self.assertEqual([r["ok"] for r in log], [False, False, False, True])
            await self.idle(app)
            self.assertEqual(self.notes(), "ab")
            self.assertEqual(app._sp_status, sp.ST_SAVED)
            t_key = time.monotonic()
            await pilot.press("c")
            await self.wait_for(lambda: len(self.fake_log()) >= 5, msg="5th")
            self.assertLess(self.saves()[-1]["t"] - t_key, 1.6)
            await self.idle(app)

    async def test_06_slow_lock_busy_waits_full_delay_after_completion(self):
        self.seed()
        self.use_fake(fail_n=1, fail_rc=3, delay=1.5)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("a", "ctrl+s")
            await self.wait_for(lambda: len(self.fake_log()) >= 2, msg="retry")
            first, second = self.fake_log()[:2]
            self.assertGreaterEqual(second["start"] - first["end"],
                                    sp.RETRY_DELAY - 0.1)
            await self.idle(app)
            self.assertEqual(self.notes(), "a")

    async def test_14b_failure_without_concurrent_edits_task_survives(self):
        self.record_loop_errors()
        self.seed()
        self.use_fake(fail_n=1, fail_rc=4)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("a", "ctrl+s")
            await self.wait_for(lambda: len(self.fake_log()) >= 1, msg="fail")
            await self.wait_for(lambda: app._sp_status.startswith("save failed"),
                                msg="failed status")
            self.assertFalse(app._sp_save_task.done())
            await self.wait_for(lambda: len(self.fake_log()) >= 2, msg="retry")
            await self.idle(app)
            self.assertFalse(app._sp_save_task.done())
            self.assertFalse(app._sp_driver_error)
            self.assertEqual(self.notes(), "a")
        self.assertEqual(self.loop_errors, [])

    async def test_14c_spawn_error_popen_then_recovery(self):
        self.seed()
        calls = {"n": 0}

        def popen(argv, *a, **kw):
            if argv[:2] == [REAL_STORE, "save"]:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise OSError(errno.EMFILE, "Too many open files")
            return REAL_POPEN(argv, *a, **kw)

        self.patch(subprocess, "Popen", popen)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("a", "ctrl+s")
            await self.wait_for(lambda: calls["n"] >= 1, msg="spawn error")
            self.assertTrue(app._sp_status.startswith("save failed"))
            self.assertFalse(app._sp_save_task.done())
            # A spawn error is a certain no-write: the baseline survives.
            self.assertEqual(app._sp_persisted_text, "")
            await self.wait_for(lambda: self.notes() == "a", msg="recovered")
            await self.idle(app)

    async def test_14c_tempfile_error_closes_partials_then_recovery(self):
        self.seed()
        made: list = []
        state = {"n": 0}

        def temp(*a, **kw):
            state["n"] += 1
            if state["n"] == 2:
                raise OSError(errno.ENOSPC, "No space left on device")
            fh = REAL_TEMPFILE(*a, **kw)
            made.append(fh)
            return fh

        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            self.patch(tempfile, "TemporaryFile", temp)
            await pilot.press("a", "ctrl+s")
            await self.wait_for(lambda: state["n"] >= 2, msg="tempfile error")
            await self.wait_for(lambda: self.notes() == "a", msg="recovered")
            await self.idle(app)
            self.assertTrue(made)
            self.assertTrue(all(fh.closed for fh in made))

    async def test_14c_sighup_with_popen_failing_still_exits(self):
        self.seed()

        def popen(argv, *a, **kw):
            if argv[:2] == [REAL_STORE, "save"]:
                raise OSError(errno.EMFILE, "Too many open files")
            return REAL_POPEN(argv, *a, **kw)

        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("a")
            self.patch(subprocess, "Popen", popen)
            os.kill(os.getpid(), signal.SIGHUP)
            await self.wait_for(lambda: app._sp_shutdown, msg="exit")
        self.assertEqual(app.return_code, 0)


class OwnershipTests(_Base):
    async def test_08_busy_lock_read_only_never_saves(self):
        self.seed("theirs")
        fd = os.open(self.holder, os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            app = sp.ScratchpadApp("42")
            async with app.run_test() as pilot:
                await self.wait_for(lambda: app._sp_mode != "opening")
                self.assertEqual(app._sp_mode, "readonly")
                self.assertTrue(app._sp_editor.read_only)
                self.assertEqual(app._sp_status, sp.ST_READONLY)
                self.assertEqual(app._sp_editor.text, "theirs")
                await pilot.press("a", "b", "ctrl+s")
                self.assertEqual(app._sp_editor.text, "theirs")
                await asyncio.sleep(3.5)
                self.assertEqual(self.saves(), [])
                fcntl.flock(fd, fcntl.LOCK_UN)
                await asyncio.sleep(1.5)
                self.assertEqual(app._sp_mode, "readonly")
                self.assertEqual(self.saves(), [])
        finally:
            os.close(fd)

    async def test_09_ownership_before_read(self):
        self.seed("stale")
        real_acquire = sp._sp_acquire_holder

        def acquire(fd):
            self.notes_path.write_text("NEWER")
            return real_acquire(fd)

        self.patch(sp, "_sp_acquire_holder", acquire)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            self.assertEqual(app._sp_editor.text, "NEWER")

    async def test_09_negative_control_read_before_lock_is_stale(self):
        self.seed("stale")
        real_acquire = sp._sp_acquire_holder

        def acquire(fd):
            self.notes_path.write_text("NEWER")
            return real_acquire(fd)

        self.patch(sp, "_sp_acquire_holder", acquire)

        class ReadFirst(sp.ScratchpadApp):
            async def _sp_claim_and_load(self, store_dir):
                text = sp._sp_read_notes(store_dir)  # the defect: read first
                fd = os.open(store_dir / ".holder.lock", os.O_RDWR)
                sp._sp_acquire_holder(fd)
                os.close(fd)
                self._sp_editor.load_text(text)
                self._sp_mode = "readonly"

        app = ReadFirst("42")
        async with app.run_test():
            await self.wait_for(lambda: app._sp_mode != "opening")
            self.assertEqual(app._sp_editor.text, "stale")

    async def test_10_save_child_inherits_holder_fd_in_new_session(self):
        self.seed()
        self.use_fake(check_fd=str(self.holder))
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("a", "ctrl+s")
            await self.wait_for(lambda: self.fake_log(), msg="save")
            await self.idle(app)
        rec = self.fake_log()[0]
        self.assertTrue(rec["inherited"])
        self.assertTrue(rec["new_session"])

    async def test_12_ctrl_q_saves_exits_and_releases(self):
        self.seed()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("h", "i", "ctrl+q")
            await self.wait_for(lambda: app._sp_shutdown, timeout=5, msg="exit")
        self.assertEqual(app.return_code, 0)
        self.assertEqual(self.notes(), "hi")
        self.assertTrue(self.holder_free())

    async def test_12_ctrl_q_failed_final_save_reports_and_exits(self):
        self.seed()
        self.use_fake(fail_n=99, fail_rc=4)
        app = sp.ScratchpadApp("42")
        exits = self.record_exit(app)
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("h", "ctrl+q")
            await self.wait_for(lambda: app._sp_shutdown, timeout=5, msg="exit")
        self.assertEqual(len(self.fake_log()), 1)
        self.assertEqual(app.return_code, 0)
        self.assertIn("may be lost", " ".join(map(str, exits)))
        self.assertTrue(self.holder_free())

    async def _palette_quit(self, app_cls) -> None:
        self.seed("BASE")
        app = app_cls("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("n", "e", "w")  # well inside the 1 s debounce
            quit_cmd = next(c for c in app.get_system_commands(app.screen)
                            if c.title == "Quit")
            result = quit_cmd.callback()
            if asyncio.iscoroutine(result):
                await result
            await self.wait_for(lambda: not app.is_running, timeout=5,
                                msg="exit")
        self.assertEqual(app.return_code, 0)

    async def test_12_palette_quit_flushes_like_ctrl_q(self):
        await self._palette_quit(sp.ScratchpadApp)
        self.assertEqual(self.notes(), "newBASE")
        self.assertEqual(len(self.saves()), 1)
        self.assertTrue(self.holder_free())

    async def test_12_negative_control_stock_quit_loses_dirty_notes(self):
        class StockQuit(sp.ScratchpadApp):
            action_quit = App.action_quit  # the inherited exit-at-once

        await self._palette_quit(StockQuit)
        self.assertEqual(self.notes(), "BASE")
        self.assertEqual(self.saves(), [])

    async def test_13_sighup_flushes_detached_and_exits(self):
        self.seed()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("h", "u", "p")
            os.kill(os.getpid(), signal.SIGHUP)
            await self.wait_for(lambda: app._sp_shutdown, timeout=5, msg="exit")
        await self.wait_for(lambda: self.notes() == "hup", timeout=5,
                            msg="flush landed")
        await self.wait_for(self.holder_free, timeout=5, msg="lock released")
        loop = asyncio.get_running_loop()
        self.assertFalse(loop.remove_signal_handler(signal.SIGHUP))

    async def test_14d_quit_during_delayed_open(self):
        self.record_loop_errors()
        fifo = self.tmp / "pause"
        os.mkfifo(fifo)
        reached = Path(f"{fifo}.reached")
        os.environ["AITASK_SCRATCHPAD_PAUSE_FIFO"] = str(fifo)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.wait_for(reached.exists, msg="open parked")
            self.assertEqual(app._sp_mode, "opening")
            await pilot.press("ctrl+q")
            await self.wait_for(lambda: app._sp_shutdown, msg="exit")
        await asyncio.to_thread(_write_line, fifo)
        await asyncio.sleep(1.5)
        self.assertTrue(app._sp_startup_task.done())
        self.assertIsNone(app._sp_save_task)
        self.assertEqual(self.loop_errors, [])
        self.assertTrue(self.holder.exists())
        self.assertTrue(self.holder_free())
        self.assertIsNone(self.notes())


class FrameworkStateTests(_Base):
    def _private_names(self):
        tree = ast.parse(MODULE_PATH.read_text())
        names = set()
        for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)
                    and n.name in ("ScratchpadApp", "ScratchEditor")):
            for node in ast.walk(cls):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("_") and not node.name.startswith("__"):
                        names.add(node.name)
                if (isinstance(node, ast.Attribute)
                        and isinstance(node.ctx, ast.Store)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == "self"
                        and node.attr.startswith("_")):
                    names.add(node.attr)
        return names

    def test_14_private_names_prefixed_and_collision_free(self):
        names = self._private_names()
        self.assertTrue(names)
        self.assertEqual(sorted(n for n in names if not n.startswith("_sp_")), [])
        framework = set(dir(App())) | set(dir(TextArea()))
        self.assertEqual(sorted(names & framework), [])
        source = MODULE_PATH.read_text()
        self.assertNotIn("._closing", source)
        self.assertNotIn("._driver", source)

    async def _behaviour(self, task_id):
        if task_id:
            self.seed()
        app = sp.ScratchpadApp(task_id)
        async with app.run_test() as pilot:
            if task_id:
                await self.owner(app, pilot)
            self.assertIsInstance(app._driver, Driver)
            self.assertTrue(app.is_headless)
            await pilot.press("o", "k")
            self.assertEqual(app._sp_editor.text, "ok")
            await pilot.press("ctrl+q")
            await self.wait_for(lambda: app._sp_shutdown, timeout=5, msg="exit")
        self.assertEqual(app.return_code, 0)
        self.assertIsNone(app._exception)

    async def test_14_driver_intact_owner_mode(self):
        await self._behaviour("42")
        self.assertEqual(self.notes(), "ok")

    async def test_14_driver_intact_unsaved_mode(self):
        await self._behaviour(None)

    def test_14f_every_save_entry_checks_the_guard_first(self):
        tree = ast.parse(MODULE_PATH.read_text())
        funcs = {n.name: n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in ("_sp_spawn_detached_flush", "_sp_save_once", "_sp_next_due"):
            calls = [(c.lineno, c.func.attr if isinstance(c.func, ast.Attribute)
                      else getattr(c.func, "id", ""))
                     for c in ast.walk(funcs[name]) if isinstance(c, ast.Call)]
            guard = [ln for ln, f in calls if f == "_sp_write_unresolved"]
            spawn = [ln for ln, f in calls
                     if f in ("_sp_spawn_store", "_sp_run_store")]
            self.assertTrue(guard, name)
            if spawn:
                self.assertLess(min(guard), min(spawn), name)


class UnresolvedWriteTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        # Short enough that a shim-parked save times out quickly, long enough
        # that an ordinary real-helper save never does on a loaded box.
        self.patch(sp, "STORE_CMD_TIMEOUT", 2.0)
        self.patch(sp, "RETRY_DELAY", 0.5)

    def blocked_pid(self, shim: Path) -> int | None:
        try:
            return int((shim / "blocked.pid").read_text())
        except (FileNotFoundError, ValueError):
            return None

    async def test_14e_timeout_in_rename_cannot_overwrite_retry(self):
        self.seed("BASE")
        shim = self.use_shim()
        (shim / "block_once").touch()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("o", "ctrl+s")
            await self.wait_for(lambda: self.blocked_pid(shim), msg="mv parked")
            old_text = app._sp_editor.text
            await pilot.press("n")
            final = app._sp_editor.text
            await self.wait_for(lambda: self.notes() == final, msg="retry saved")
            await self.idle(app)
            self.assertEqual(app._sp_status, sp.ST_SAVED)
            pid = self.blocked_pid(shim)
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
            with self.assertRaises(OSError) as cm:
                os.open(shim / "fifo", os.O_WRONLY | os.O_NONBLOCK)
            self.assertEqual(cm.exception.errno, errno.ENXIO)
            await asyncio.sleep(1.5)
            self.assertEqual(self.notes(), final)
            self.assertNotEqual(old_text, final)

    async def test_14e_negative_control_bash_only_kill_reverts(self):
        async def kill_bash_only(proc):
            proc.kill()
            proc.wait()
            return True

        self.patch(sp, "_sp_terminate_group", kill_bash_only)
        self.seed("BASE")
        shim = self.use_shim()
        (shim / "block_once").touch()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("o", "ctrl+s")
            await self.wait_for(lambda: self.blocked_pid(shim), msg="mv parked")
            old_text = app._sp_editor.text
            await pilot.press("n")
            final = app._sp_editor.text
            await self.wait_for(lambda: self.notes() == final, msg="retry saved")
            await self.idle(app)
            await asyncio.to_thread(_write_line, shim / "fifo")
            await self.wait_for(lambda: self.notes() == old_text, timeout=2,
                                msg="the surviving old mv reverted the notes")

    async def _enter_stuck(self, app, pilot, shim: Path) -> None:
        state = {"until": None}
        real_alive = sp._sp_group_alive

        def alive(pgid):
            if state["until"] is None:
                state["until"] = time.monotonic() + 3.0
            if time.monotonic() < state["until"]:
                return True
            return real_alive(pgid)

        self.patch(sp, "_sp_group_alive", alive)
        self.patch(sp, "GROUP_DRAIN_TIMEOUT", 0.3)
        self.patch(sp, "STUCK_POLL", 0.2)
        await self.owner(app, pilot)
        await pilot.press("s", "ctrl+s")
        await self.wait_for(lambda: app._sp_status == sp.ST_STUCK, msg="stuck")

    async def test_14f_stuck_group_holds_back_every_retry(self):
        self.seed("BASE")
        shim = self.use_shim()
        (shim / "block_once").touch()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self._enter_stuck(app, pilot, shim)
            count = len(self.saves())
            await pilot.press("t", "ctrl+s")
            await asyncio.sleep(1.0)
            if app._sp_stuck_pgid is not None:
                self.assertEqual(len(self.saves()), count)
            final = app._sp_editor.text
            await self.wait_for(lambda: self.notes() == final, timeout=8,
                                msg="saved after the group drained")
            await self.idle(app)
            self.assertEqual(len(self.saves()), count + 1)
            self.assertFalse(app._sp_save_task.done())

    async def test_14f_sighup_while_stuck_spawns_no_flush(self):
        self.seed("BASE")
        shim = self.use_shim()
        (shim / "block_once").touch()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self._enter_stuck(app, pilot, shim)
            count = len(self.saves())
            os.kill(os.getpid(), signal.SIGHUP)
            await self.wait_for(lambda: app._sp_shutdown, msg="exit")
        await asyncio.sleep(1.5)
        self.assertEqual(len(self.saves()), count)
        self.assertEqual(self.notes(), "BASE")

    async def _stuck_by_unkillable_child(self, app, pilot) -> None:
        self.patch(sp, "_sp_killpg", lambda pgid, sig: None)
        self.patch(sp, "STORE_CMD_TIMEOUT", 0.5)
        self.patch(sp, "GROUP_DRAIN_TIMEOUT", 0.5)
        self.patch(sp, "STUCK_POLL", 0.2)
        await self.owner(app, pilot)
        await pilot.press("a", "ctrl+s")
        await self.wait_for(lambda: app._sp_status == sp.ST_STUCK, timeout=2,
                            msg="stuck")

    async def test_14g_unkillable_child_keeps_loop_responsive(self):
        self.seed()
        self.use_fake(sleep_first=60)
        app = sp.ScratchpadApp("42")
        exits = self.record_exit(app)
        async with app.run_test() as pilot:
            await self._stuck_by_unkillable_child(app, pilot)
            for key in ("b", "c", "d", "e", "f"):
                self.assertLess(await self.press_timed(pilot, key), 0.3, key)
            self.assertEqual(app._sp_editor.text, "abcdef")
            count = len(self.saves())
            await pilot.press("ctrl+s")
            await asyncio.sleep(0.5)
            self.assertEqual(len(self.saves()), count)
            t0 = time.monotonic()
            await pilot.press("ctrl+q")
            await self.wait_for(lambda: app._sp_shutdown, timeout=1, msg="exit")
            self.assertLess(time.monotonic() - t0, 1.0)
        self.assertEqual(len(self.saves()), count)
        self.assertIn("unresolved", " ".join(map(str, exits)))

    async def test_14g_recovers_once_the_group_is_really_gone(self):
        self.seed()
        self.use_fake(sleep_first=60)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self._stuck_by_unkillable_child(app, pilot)
            await pilot.press("b")
            os.killpg(app._sp_stuck_pgid, signal.SIGKILL)
            await self.wait_for(lambda: self.notes() == "ab", timeout=5,
                                msg="saved after recovery")
            await self.idle(app)
            self.assertIsNone(app._sp_stuck_pgid)

    async def _ack_lost(self, app, pilot, shim: Path) -> None:
        await self.owner(app, pilot)
        await pilot.press("x", "ctrl+s")
        await self.wait_for(lambda: self.blocked_pid(shim), msg="mv done, parked")
        self.assertEqual(self.notes(), "xBASE")
        await pilot.press("ctrl+z")
        self.assertEqual(app._sp_editor.text, "BASE")

    async def test_14h_unconfirmed_write_forces_save_after_undo(self):
        self.seed("BASE")
        shim = self.use_shim()
        (shim / "block_after").touch()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self._ack_lost(app, pilot, shim)
            await self.wait_for(lambda: app._sp_persisted_text is None,
                                msg="baseline invalidated")
            self.assertNotEqual(app._sp_status, sp.ST_SAVED)
            await self.wait_for(lambda: self.notes() == "BASE", msg="forced save")
            await self.idle(app)
            self.assertEqual(len(self.saves()), 2)
            self.assertEqual(app._sp_status, sp.ST_SAVED)

    async def test_14h_quit_waits_for_the_confirmed_save(self):
        self.seed("BASE")
        shim = self.use_shim()
        (shim / "block_after").touch()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self._ack_lost(app, pilot, shim)
            await self.wait_for(lambda: app._sp_persisted_text is None,
                                msg="baseline invalidated")
            await pilot.press("ctrl+q")
            await self.wait_for(lambda: app._sp_shutdown, timeout=5, msg="exit")
        self.assertEqual(self.notes(), "BASE")
        self.assertEqual(len(self.saves()), 2)

    async def test_14h_explicit_save_forces_the_save(self):
        self.patch(sp, "RETRY_DELAY", 30.0)  # only ctrl+s can trigger it
        self.seed("BASE")
        shim = self.use_shim()
        (shim / "block_after").touch()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self._ack_lost(app, pilot, shim)
            await self.wait_for(lambda: app._sp_persisted_text is None,
                                msg="baseline invalidated")
            await pilot.press("ctrl+s")
            await self.wait_for(lambda: self.notes() == "BASE", msg="forced save")
            await self.wait_for(lambda: app._sp_status == sp.ST_SAVED)

    async def test_14h_negative_control_keeping_the_baseline(self):
        real_record = sp.ScratchpadApp._sp_record_failure

        def keep_baseline(self_, out, uncertain):
            real_record(self_, out, uncertain=False)

        self.patch(sp.ScratchpadApp, "_sp_record_failure", keep_baseline)
        self.seed("BASE")
        shim = self.use_shim()
        (shim / "block_after").touch()
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self._ack_lost(app, pilot, shim)
            await self.wait_for(lambda: not app._sp_save_in_flight
                                and app._sp_retry_at is not None,
                                msg="timed out")
            await asyncio.sleep(1.5)
            self.assertEqual(len(self.saves()), 1)
            self.assertEqual(app._sp_status, sp.ST_SAVED)
            self.assertEqual(self.notes(), "xBASE")

    async def test_14h_certain_failure_keeps_the_baseline(self):
        # The fake sleeps 1 s before answering LOCK_BUSY; it must not time out.
        self.patch(sp, "STORE_CMD_TIMEOUT", 30.0)
        self.seed("BASE")
        self.use_fake(fail_n=1, fail_rc=3, delay=1.0)
        app = sp.ScratchpadApp("42")
        async with app.run_test() as pilot:
            await self.owner(app, pilot)
            await pilot.press("x", "ctrl+s")
            await self.wait_for(lambda: app._sp_save_in_flight, msg="in flight")
            await pilot.press("ctrl+z")
            await self.wait_for(lambda: self.fake_log(), msg="LOCK_BUSY")
            await self.wait_for(lambda: not app._sp_save_in_flight)
            await asyncio.sleep(1.5)
            self.assertEqual(app._sp_persisted_text, "BASE")
            self.assertEqual(len(self.saves()), 1)
            self.assertEqual(app._sp_status, sp.ST_SAVED)
            self.assertEqual(self.notes(), "BASE")


class ClipboardAndCliTests(_Base):
    async def test_15_copy_and_cut_use_the_seam(self):
        copied: list[str] = []
        self.patch(sp, "copy_to_system_clipboard",
                   lambda app, text: copied.append(text))
        app = sp.ScratchpadApp(None)
        async with app.run_test() as pilot:
            app._sp_editor.load_text("hello world")
            await pilot.press("ctrl+c")
            self.assertEqual(copied[-1], "hello world")
            app._sp_editor.selection = Selection((0, 0), (0, 5))
            await pilot.press("ctrl+c")
            self.assertEqual(copied[-1], "hello")
            await pilot.press("ctrl+x")
            self.assertEqual(copied[-1], "hello")
            self.assertEqual(app._sp_editor.text, " world")

    def test_16_cli(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sp._sp_parse_args(["--task", "x1"])[0], 2)
            self.assertEqual(sp.main(["--task", "x1"]), 2)
            self.assertEqual(sp._sp_parse_args([])[0], 2)
            self.assertEqual(
                sp._sp_parse_args(["--task", "42", "--unsaved"])[0], 2)
        self.assertEqual(sp._sp_parse_args(["--task", "t42"]), (None, "42", None))
        self.assertEqual(sp._sp_parse_args(["--task", "7_3"]), (None, "7_3", None))
        self.assertEqual(sp._sp_parse_args(["--unsaved", "--target", "%5"]),
                         (None, None, "%5"))


if __name__ == "__main__":
    unittest.main()
