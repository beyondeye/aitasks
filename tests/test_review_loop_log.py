"""Unit tests for the durable review-loop event store (t1606).

Pure filesystem + stdlib — no tmux, no Textual, no event loop, like the store
itself. The load-bearing contracts, each with a control so a green run cannot
be vacuous:

- an append round-trips, and never raises whatever the filesystem does;
- **retention cannot interleave with a live append**, because it only ever
  touches files no live process owns. This is the property the whole
  per-session no-rewrite design exists to provide, and the interleaving test
  below is the one that would have caught the rejected shared-ring/trim shape;
- both retention guards refuse independently — a live pid, and an age floor
  that covers the pid reuse liveness cannot;
- the reader is tolerant **by line**: a diagnostic tool that dies on a damaged
  file fails exactly when it is needed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
sys.path.insert(0, str(SCRIPTS_DIR / "monitor"))

import review_loop as rl  # noqa: E402
import review_loop_log as rll  # noqa: E402


def _write_session(directory: Path, stamp: str, pid: int, lines) -> Path:
    path = directory / f"{stamp}-{pid}.jsonl"
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


def _event_line(reason: str, ts: str = "2026-08-25T10:00:00+00:00") -> str:
    return json.dumps({"schema": 1, "ts": ts, "kind": "disarm",
                       "reason": reason}, sort_keys=True)


class StoreTempDirMixin:
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "events"
        os.environ[rll.LOG_DIR_ENV] = str(self.dir)
        rll.reset_session_for_tests()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(rll.reset_session_for_tests)
        self.addCleanup(lambda: os.environ.pop(rll.LOG_DIR_ENV, None))


class RecordEventTests(StoreTempDirMixin, unittest.TestCase):
    def test_append_round_trips(self):
        self.assertTrue(rll.record_event(
            rll.KIND_DISARM, rl.DISARM_SHADOW_GONE, shadow_pane="%201"))
        events, notes = rll.read_events(self.dir)
        self.assertEqual(notes, [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["reason"], rl.DISARM_SHADOW_GONE)
        self.assertEqual(events[0]["kind"], rll.KIND_DISARM)
        self.assertEqual(events[0]["shadow_pane"], "%201")
        self.assertEqual(events[0]["schema"], rll.SCHEMA_VERSION)

    def test_modes_are_owner_only(self):
        rll.record_event(rll.KIND_HOLD, rl.HOLD_PRE_ENTER_DIALOG)
        self.assertEqual(self.dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual(rll.session_path().stat().st_mode & 0o777, 0o600)

    def test_all_events_land_in_one_session_file(self):
        """One writer per file for its whole life — the invariant that makes
        the append lock-free."""
        for _ in range(5):
            rll.record_event(rll.KIND_HOLD, rl.HOLD_PRE_ENTER_DIALOG)
        self.assertEqual(len(list(self.dir.glob("*.jsonl"))), 1)

    def test_an_unwritable_store_returns_false_and_never_raises(self):
        """The applink NullHandler doctrine: a logging failure must not take
        the TUI down. The caller surfaces the False — see
        `_loop_auto_disarm`'s "(not recorded)" suffix."""
        blocker = Path(self._tmp.name) / "blocked"
        blocker.write_text("not a directory", encoding="utf-8")
        os.environ[rll.LOG_DIR_ENV] = str(blocker / "events")
        rll.reset_session_for_tests()
        self.assertFalse(
            rll.record_event(rll.KIND_DISARM, rl.DISARM_AGENT_GONE))

    def test_a_record_is_bounded_and_stays_valid_json(self):
        """Bounded BY CONSTRUCTION, so a long field can never produce a torn
        line — the reader tolerates damage, but the writer must not cause it."""
        self.assertTrue(rll.record_event(
            rll.KIND_DISARM, rl.DISARM_AGENT_GONE, note="x" * 50_000))
        raw = rll.session_path().read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(raw), 1)
        self.assertLessEqual(len(raw[0].encode("utf-8")), rll.MAX_LINE_BYTES)
        json.loads(raw[0])  # must parse

    def test_none_valued_fields_are_omitted_not_serialized(self):
        rll.record_event(rll.KIND_HOLD, rl.HOLD_PRE_ENTER_DIALOG,
                         subject=None, shadow_pane="%9")
        events, _ = rll.read_events(self.dir)
        self.assertNotIn("subject", events[0])
        self.assertEqual(events[0]["shadow_pane"], "%9")


class RetentionTests(StoreTempDirMixin, unittest.TestCase):
    """Retention is the ONLY thing that ever removes data, so both of its
    guards get a direct test — and each must refuse on its own."""

    def setUp(self):
        super().setUp()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.dead_pid = self._find_dead_pid()

    @staticmethod
    def _find_dead_pid() -> int:
        """A pid that provably does not exist (so monitor_marker says STALE)."""
        proc = subprocess.run([sys.executable, "-c", "pass"])
        del proc
        for candidate in range(4_000_000, 4_000_400):
            try:
                os.kill(candidate, 0)
            except ProcessLookupError:
                return candidate
            except OSError:
                continue
        raise unittest.SkipTest("no provably-dead pid available")

    def _old(self, path: Path) -> Path:
        past = time.time() - (rll.RETENTION_AGE_FLOOR_SECONDS + 60)
        os.utime(path, (past, past))
        return path

    def test_prunes_oldest_first_down_to_the_cap(self):
        for index in range(8):
            self._old(_write_session(
                self.dir, f"2026010{index}T000000Z", self.dead_pid,
                [_event_line(rl.DISARM_AGENT_GONE)]))
        removed = rll.prune(self.dir, keep=3)
        self.assertEqual(len(removed), 5)
        survivors = sorted(p.name for p in self.dir.glob("*.jsonl"))
        self.assertEqual(len(survivors), 3)
        # Oldest went first: the survivors are the three newest stamps.
        self.assertTrue(all(name.startswith(("20260105", "20260106",
                                             "20260107"))
                            for name in survivors), survivors)

    def test_under_the_cap_removes_nothing(self):
        for index in range(3):
            self._old(_write_session(
                self.dir, f"2026010{index}T000000Z", self.dead_pid,
                [_event_line(rl.DISARM_AGENT_GONE)]))
        self.assertEqual(rll.prune(self.dir, keep=5), [])
        self.assertEqual(len(list(self.dir.glob("*.jsonl"))), 3)

    def test_guard_one_refuses_a_file_whose_pid_is_live(self):
        """Only a PROVABLE absence licenses a delete. Our own pid is live, and
        `monitor_marker` classifies an unverifiable read as present too."""
        live = self._old(_write_session(
            self.dir, "20260101T000000Z", os.getpid(),
            [_event_line(rl.DISARM_AGENT_GONE)]))
        for index in range(1, 6):
            self._old(_write_session(
                self.dir, f"2026020{index}T000000Z", self.dead_pid,
                [_event_line(rl.DISARM_AGENT_GONE)]))
        removed = rll.prune(self.dir, keep=1)
        self.assertNotIn(live, removed)
        self.assertTrue(live.exists(), "a live session's file was deleted")

    def test_guard_two_refuses_a_recent_file_even_when_liveness_says_dead(self):
        """The age floor covers pid reuse, which liveness cannot. Deliberately
        an INDEPENDENT refusal: this file's pid is provably gone."""
        recent = _write_session(
            self.dir, "20260101T000000Z", self.dead_pid,
            [_event_line(rl.DISARM_AGENT_GONE)])       # mtime = now
        for index in range(1, 6):
            self._old(_write_session(
                self.dir, f"2026020{index}T000000Z", self.dead_pid,
                [_event_line(rl.DISARM_AGENT_GONE)]))
        removed = rll.prune(self.dir, keep=1)
        self.assertNotIn(recent, removed)
        self.assertTrue(recent.exists())

    def test_the_age_floor_is_what_saved_it(self):
        """Control for the test above: the SAME file, aged past the floor, is
        removed. Without this, an over-strict liveness check would make the
        age-floor test pass while proving nothing about the floor."""
        subject = _write_session(
            self.dir, "20260101T000000Z", self.dead_pid,
            [_event_line(rl.DISARM_AGENT_GONE)])
        for index in range(1, 6):
            self._old(_write_session(
                self.dir, f"2026020{index}T000000Z", self.dead_pid,
                [_event_line(rl.DISARM_AGENT_GONE)]))
        self.assertNotIn(subject, rll.prune(self.dir, keep=1))
        self.assertTrue(subject.exists())
        # `keep=0` because the call above already removed the five filler
        # files, so at `keep=1` there would be no excess left and the second
        # prune would be a no-op — the control would then "pass" without ever
        # re-testing the guard.
        self._old(subject)
        self.assertIn(subject, rll.prune(self.dir, keep=0))
        self.assertFalse(subject.exists())

    def test_foreign_files_are_never_touched(self):
        stranger = self.dir / "notes.txt"
        stranger.write_text("someone else's file", encoding="utf-8")
        for index in range(8):
            self._old(_write_session(
                self.dir, f"2026010{index}T000000Z", self.dead_pid,
                [_event_line(rl.DISARM_AGENT_GONE)]))
        rll.prune(self.dir, keep=1)
        self.assertTrue(stranger.exists())

    def test_a_missing_directory_is_not_an_error(self):
        self.assertEqual(rll.prune(self.dir / "nope", keep=1), [])

    def test_the_cap_holds_once_the_new_session_writes(self):
        """`MAX_SESSION_FILES` is a cap on the STEADY STATE, not on
        everything-but-the-current-session.

        Retention runs at startup, before this process has written anything,
        so its own file is not on disk to be counted. Pruning to `keep` and
        then creating one more settles the store at `keep + 1`. `reserve=1` —
        what `on_mount` passes — holds the slot.
        """
        for index in range(rll.MAX_SESSION_FILES + 4):
            self._old(_write_session(
                self.dir, f"20260101T0000{index:02d}Z", self.dead_pid,
                [_event_line(rl.DISARM_AGENT_GONE)]))
        rll.prune(self.dir, reserve=1)
        self.assertEqual(len(list(self.dir.glob("*.jsonl"))),
                         rll.MAX_SESSION_FILES - 1)
        # Now the incoming session writes its first event.
        rll.record_event(rll.KIND_DISARM, rl.DISARM_AGENT_GONE)
        self.assertEqual(len(list(self.dir.glob("*.jsonl"))),
                         rll.MAX_SESSION_FILES)

    def test_without_the_reserve_the_store_overshoots_by_one(self):
        """The control: shows the reserve is what fixes it, not the cap."""
        for index in range(rll.MAX_SESSION_FILES + 4):
            self._old(_write_session(
                self.dir, f"20260101T0000{index:02d}Z", self.dead_pid,
                [_event_line(rl.DISARM_AGENT_GONE)]))
        rll.prune(self.dir)                      # reserve defaults to 0
        rll.record_event(rll.KIND_DISARM, rl.DISARM_AGENT_GONE)
        self.assertEqual(len(list(self.dir.glob("*.jsonl"))),
                         rll.MAX_SESSION_FILES + 1)


class RetentionNeverRacesAnAppendTests(StoreTempDirMixin, unittest.TestCase):
    """`review_loop_log_concurrency_proof` — the risk-mitigation post-phase.

    This is the exact interleaving the REJECTED design lost data on: a shared
    ring trimmed via read-modify-write drops any append that lands on the old
    inode between the trim's read and its `os.replace`.

    Here two writers append to their own session files, in separate processes,
    while a third process runs retention over the same directory. The
    assertion is total: **zero lines lost**, both live files intact, and only
    writerless files removed.

    Note what makes this pass — not luck, and not a lock. Retention's two
    guards mean it can only ever select files with no writer, so there is no
    interleaving to lose.

    **Measured, not asserted (2026-08-25).** The claim that this test
    discriminates was verified by building the rejected shape — one shared
    `events.jsonl` trimmed by read → `os.replace` — and driving this exact
    workload through it:

        two writers x 60 records, 20ms apart, one concurrent pruner
          shared ring (rejected):  120 written,   1 surviving  -> 119 LOST
          per-session (shipped):   120 written, 120 surviving  ->   0 lost

    The test fails against the shared ring on its non-vacuity control (that
    layout has no per-session files to prune), and its data-loss assertions
    fail there too. If a future refactor ever makes this pass against a
    rewrite-the-active-file design, it has stopped proving anything and must
    be strengthened before it counts.
    """

    #: Records per writer, and the gap between them. The gap is the whole
    #: point: an earlier version of this test wrote its records as fast as it
    #: could, finished in ~20ms, and the pruner never overlapped it at all --
    #: so it passed without a race ever occurring. SPREAD is what holds the
    #: window open long enough for retention to run repeatedly *during* the
    #: appends.
    RECORDS = 60
    SPREAD_SECONDS = 0.02

    WRITER = """
import os, sys, time
sys.path[:0] = [%(lib)r, %(mon)r]
os.environ[%(env)r] = %(dir)r
import review_loop_log as rll
for i in range(%(count)d):
    assert rll.record_event("hold", "pre_enter_dialog", seq=i)
    time.sleep(%(spread)r)
print(rll.session_path())
"""

    PRUNER = """
import os, sys, time
sys.path[:0] = [%(lib)r, %(mon)r]
os.environ[%(env)r] = %(dir)r
import review_loop_log as rll
from pathlib import Path
passes = 0
deadline = time.time() + %(seconds)r
# Progress is APPENDED after every pass, one byte-line each, and is read by
# counting lines. Two reasons, both learned the hard way:
#   * not stderr-at-exit -- the test terminates this process as soon as the
#     writers finish, so an exit-time report would never be produced and the
#     "did retention actually run?" control would be unfalsifiable;
#   * not write_text() -- that truncates before writing, so the test's own
#     read could catch it empty and blow up on int(''). An append under
#     PIPE_BUF is atomic, which is the same property the module under test
#     relies on. Do not "simplify" this back to a rewrite.
# One character per pass, no newline -- the count is the file's length. A
# newline escape here would be consumed by THIS template literal before the
# subprocess ever saw it, producing a syntax error in the child.
counter = Path(%(counter)r)
while time.time() < deadline:
    rll.prune(Path(%(dir)r), keep=1)
    passes += 1
    with open(counter, "a") as fh:
        fh.write("x")
"""

    def _spawn(self, source: str, **kwargs):
        params = dict(lib=str(SCRIPTS_DIR / "lib"),
                      mon=str(SCRIPTS_DIR / "monitor"),
                      env=rll.LOG_DIR_ENV, dir=str(self.dir),
                      spread=self.SPREAD_SECONDS)
        params.update(kwargs)
        return subprocess.Popen(
            [sys.executable, "-c", source % params],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def _seed_prunable(self, count: int) -> list:
        """Old files owned by a provably-dead pid -- legitimate prune targets.

        They are the NON-VACUITY control: without them "zero lines lost" could
        simply mean retention found nothing to do and never ran at all.
        """
        dead = RetentionTests._find_dead_pid()
        past = time.time() - (rll.RETENTION_AGE_FLOOR_SECONDS + 60)
        seeded = []
        for index in range(count):
            path = _write_session(self.dir, f"2020010{index}T000000Z", dead,
                                  [_event_line(rl.DISARM_AGENT_GONE)])
            os.utime(path, (past, past))
            seeded.append(path)
        return seeded

    def test_two_writers_and_a_pruner_lose_nothing(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        seeded = self._seed_prunable(6)
        writer_seconds = self.RECORDS * self.SPREAD_SECONDS

        # The pruner outlives the writers, so retention is already running
        # before the first append and still running after the last.
        counter = self.dir.parent / "prune_passes"
        pruner = self._spawn(self.PRUNER, seconds=writer_seconds + 1.5,
                             counter=str(counter))
        try:
            writers = [self._spawn(self.WRITER, count=self.RECORDS)
                       for _ in range(2)]
            paths = []
            for writer in writers:
                out, err = writer.communicate(timeout=120)
                self.assertEqual(writer.returncode, 0, err)
                paths.append(Path(out.strip()))
        finally:
            pruner.terminate()
            pruner.communicate(timeout=60)

        # --- the race actually happened -----------------------------------
        self.assertTrue(counter.exists(), "the pruner never ran a single pass")
        passes = len(counter.read_text().strip())
        self.assertGreater(passes, 10,
                           "retention barely ran -- the window was not open")
        self.assertFalse([p for p in seeded if p.exists()],
                         "retention never removed its legitimate targets, so "
                         "this test proves nothing about interleaving")

        # --- and nothing was lost -----------------------------------------
        self.assertEqual(len(set(paths)), 2, "writers shared a file")
        for path in paths:
            self.assertTrue(path.exists(),
                            f"retention deleted a LIVE writer's file: {path}")
            lines = [ln for ln in
                     path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertEqual(len(lines), self.RECORDS,
                             f"lost {self.RECORDS - len(lines)} record(s) "
                             f"in {path}")
            seqs = sorted(json.loads(line)["seq"] for line in lines)
            self.assertEqual(seqs, list(range(self.RECORDS)),
                             "records were lost or torn")


class ReaderTests(StoreTempDirMixin, unittest.TestCase):
    def test_newest_first_including_within_one_second(self):
        """`ts` is second-resolution, so same-second ordering is decided by
        arrival. A stable sort on `ts` alone returns them OLDEST-first — the
        opposite of what the reader promises."""
        for reason in (rl.DISARM_AGENT_GONE, rl.HOLD_PRE_ENTER_DIALOG,
                       rl.HOLD_PRE_ENTER_UNREADABLE):
            rll.record_event(rll.KIND_HOLD, reason)
        events, _ = rll.read_events(self.dir)
        self.assertEqual([e["reason"] for e in events],
                         [rl.HOLD_PRE_ENTER_UNREADABLE,
                          rl.HOLD_PRE_ENTER_DIALOG,
                          rl.DISARM_AGENT_GONE])

    def test_limit_returns_the_newest(self):
        for index in range(5):
            rll.record_event(rll.KIND_HOLD, rl.HOLD_PRE_ENTER_DIALOG,
                             seq=index)
        events, _ = rll.read_events(self.dir, limit=2)
        self.assertEqual([e["seq"] for e in events], [4, 3])

    def test_an_absent_directory_yields_nothing_and_no_notes(self):
        events, notes = rll.read_events(self.dir / "nope")
        self.assertEqual((events, notes), ([], []))

    def test_damaged_lines_are_skipped_not_fatal(self):
        """A file holding valid records AND damage: one torn/non-JSON line,
        one JSON line that is not an event object."""
        self.dir.mkdir(parents=True, exist_ok=True)
        _write_session(self.dir, "20260101T000000Z", 111, [
            _event_line(rl.DISARM_AGENT_GONE, "2026-08-25T10:00:00+00:00"),
            '{"schema": 1, "ts": "2026-08-25T10:00:01+00:00", "kind": "hold"',
            "this is not json at all",
            '{"not": "an event"}',
            "[1, 2, 3]",
            _event_line(rl.DISARM_SHADOW_GONE, "2026-08-25T10:00:02+00:00"),
        ])
        events, notes = rll.read_events(self.dir)
        self.assertEqual([e["reason"] for e in events],
                         [rl.DISARM_SHADOW_GONE, rl.DISARM_AGENT_GONE])
        self.assertTrue(any("skipped 4 unreadable line(s)" in n
                            for n in notes), notes)

    def test_one_unreadable_file_never_suppresses_another(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        good = _write_session(self.dir, "20260101T000000Z", 111,
                              [_event_line(rl.DISARM_AGENT_GONE)])
        bad = _write_session(self.dir, "20260102T000000Z", 222,
                             [_event_line(rl.DISARM_SHADOW_GONE)])
        bad.chmod(0o000)
        self.addCleanup(bad.chmod, 0o600)
        if os.access(bad, os.R_OK):  # running as root
            self.skipTest("cannot make a file unreadable as this user")
        events, notes = rll.read_events(self.dir)
        self.assertEqual([e["reason"] for e in events],
                         [rl.DISARM_AGENT_GONE])
        self.assertTrue(any(bad.name in n for n in notes), notes)
        self.assertTrue(good.exists())

    def test_format_event_decodes_the_reason_to_prose(self):
        """The reader and the toast must never describe one code differently:
        both go through `review_loop.loop_reason_message`."""
        line = rll.format_event({"ts": "T", "kind": "disarm",
                                 "reason": rl.DISARM_SHADOW_GONE,
                                 "shadow_pane": "%201"})
        self.assertIn(rl.loop_reason_message(rl.DISARM_SHADOW_GONE), line)
        self.assertIn("shadow_pane=%201", line)

    def test_format_event_survives_an_unknown_reason(self):
        self.assertIn("nonsense", rll.format_event({"reason": "nonsense"}))


class ReaderCliTests(StoreTempDirMixin, unittest.TestCase):
    """The CLI contract: stdout is a clean event stream, damage notes go to
    stderr, and skipped lines are NOT a failure — a non-zero exit would make
    the reader unusable in exactly the degraded case it exists to serve."""

    def _run(self, *args):
        env = dict(os.environ)
        env[rll.LOG_DIR_ENV] = str(self.dir)
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "monitor" / "review_loop_log.py"),
             *args],
            capture_output=True, text=True, env=env)

    def test_empty_store_degrades_gracefully(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("(no review-loop events recorded)", result.stdout)

    def test_damaged_input_keeps_stdout_clean_and_exits_zero(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        _write_session(self.dir, "20260101T000000Z", 111, [
            _event_line(rl.DISARM_SHADOW_GONE),
            "torn line, not json",
            '{"not": "an event"}',
        ])
        result = self._run("10")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(rl.loop_reason_message(rl.DISARM_SHADOW_GONE),
                      result.stdout)
        self.assertNotIn("skipped", result.stdout)
        self.assertIn("skipped 2 unreadable line(s)", result.stderr)


class MinimonitorDispatchTests(unittest.TestCase):
    """`ait minimonitor --loop-log` must reach the reader.

    The dispatch sits ABOVE the textual/tmux checks and the single-instance
    guard on purpose: reading a log needs neither, and after the guard the
    command would answer "A monitor is already running. Exiting." for anyone
    asking why their loop disarmed from the window that hosts the minimonitor
    — i.e. it would fail in exactly the case it exists to serve.
    """

    def test_the_dispatch_precedes_every_guard(self):
        script = (SCRIPTS_DIR / "aitask_minimonitor.sh").read_text(
            encoding="utf-8")
        dispatch = script.index('"${1:-}" == "--loop-log"')
        for guard in ("import textual", "command -v tmux",
                      "@aitask_monitor_kind"):
            self.assertLess(dispatch, script.index(guard),
                            f"--loop-log dispatch must precede: {guard}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
