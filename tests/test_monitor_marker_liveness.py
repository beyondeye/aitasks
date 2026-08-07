"""The `@aitask_monitor_kind` marker rule, and shell/Python parity (t1451).

`lib/monitor_marker.py` is the ONE implementation of "is this marker a running
monitor?". It is imported by `agent_launch_utils.maybe_spawn_minimonitor` and
exec'd as a CLI by `aitask_minimonitor.sh`. Two implementations that agree by
inspection would drift silently in at least two ways:

* `${marker##*:}` in shell reads `garbage:123` as a dead numeric pid, so the
  shell would CLEAR a marker Python calls unverifiable and blocks on;
* `kill -0` reports *failure* for a live process owned by another user, where
  `os.kill(pid, 0)`'s `PermissionError` means the process exists.

So :data:`MARKER_TABLE` is run through **both** entry points and asserted to
agree with the table *and with each other*. The subprocess lane is literally
what the shell guard executes, so it is an end-to-end pin on the shell path's
verdict rather than a replica of it.

The second half pins the *transport*: verdict codes must be disjoint from the
statuses a failing interpreter produces, or an interpreter failure becomes
indistinguishable from a decision. Mapping one to "stale" would make the guard
clear a LIVE marker on a crash — the worst outcome in the whole design.

Run: python3 tests/test_monitor_marker_liveness.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import monitor_marker  # noqa: E402
from monitor_marker import (  # noqa: E402
    EXIT_ABSENT,
    EXIT_PRESENT,
    EXIT_STALE,
    STATE_ABSENT,
    STATE_PRESENT,
    STATE_STALE,
    monitor_marker_alive,
    monitor_marker_state,
    parse_monitor_marker,
)

MARKER_TOOL = REPO_ROOT / ".aitask-scripts" / "lib" / "monitor_marker.py"

_EXIT_TO_STATE = {
    EXIT_PRESENT: STATE_PRESENT,
    EXIT_STALE: STATE_STALE,
    EXIT_ABSENT: STATE_ABSENT,
}


def _reaped_pid() -> int:
    """A pid that is definitely gone — spawned and reaped, never guessed."""
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


_DEAD_PID = _reaped_pid()
_LIVE_PID = os.getpid()

# The shared contract. Every row runs through both entry points.
MARKER_TABLE: list[tuple[str, str]] = [
    # absent — the only value that means "no monitor here"
    ("", STATE_ABSENT),
    # present — parseable, process exists
    (f"minimonitor:{_LIVE_PID}", STATE_PRESENT),
    (f"monitor:{_LIVE_PID}", STATE_PRESENT),
    # stale — parseable, process gone (the ONLY clearable state)
    (f"minimonitor:{_DEAD_PID}", STATE_STALE),
    (f"monitor:{_DEAD_PID}", STATE_STALE),
    # ---- unverifiable => present, never cleared -------------------------
    # Malformed BUT NUMERIC: the family a hand-rolled `${marker##*:}` +
    # `kill -0` shell parse gets wrong, reading each as a dead pid.
    ("garbage:123", STATE_PRESENT),
    (f"garbage:{_DEAD_PID}", STATE_PRESENT),
    ("minimonitor:1:2", STATE_PRESENT),
    ("mini monitor:123", STATE_PRESENT),
    ("MINIMONITOR:123", STATE_PRESENT),
    (":123", STATE_PRESENT),
    (" minimonitor:123", STATE_PRESENT),
    ("minimonitor:123 ", STATE_PRESENT),
    # Malformed and non-numeric
    ("minimonitor", STATE_PRESENT),
    ("minimonitor:", STATE_PRESENT),
    ("minimonitor:abc", STATE_PRESENT),
    ("minimonitor:-1", STATE_PRESENT),
    ("garbage", STATE_PRESENT),
    # A value that must be classified, not parsed as a CLI option.
    ("--help", STATE_PRESENT),
    ("-minimonitor:1", STATE_PRESENT),
]


def _cli_state(value: str) -> str:
    """Run the CLI the way the shell guard does; map its exit to a state."""
    proc = subprocess.run(
        [sys.executable, str(MARKER_TOOL), "state", value],
        capture_output=True, text=True,
    )
    if proc.returncode not in _EXIT_TO_STATE:
        raise AssertionError(
            f"CLI returned unmapped status {proc.returncode} for {value!r} "
            f"(stdout={proc.stdout!r} stderr={proc.stderr!r})"
        )
    return _EXIT_TO_STATE[proc.returncode]


class MarkerStateTableTests(unittest.TestCase):
    """Lane 1: the in-process predicate."""

    def test_table(self):
        for value, expected in MARKER_TABLE:
            with self.subTest(value=value):
                self.assertEqual(monitor_marker_state(value), expected)

    def test_alive_predicate_agrees_with_state(self):
        for value, expected in MARKER_TABLE:
            with self.subTest(value=value):
                self.assertIs(
                    monitor_marker_alive(value), expected == STATE_PRESENT
                )

    def test_only_stale_is_clearable(self):
        """The guards clear on `stale` alone. Nothing unverifiable may reach it
        — clearing a marker we do not understand deletes another tool's state.
        """
        clearable = {v for v, s in MARKER_TABLE if s == STATE_STALE}
        for value in clearable:
            self.assertIsNotNone(parse_monitor_marker(value))

    def test_permission_error_counts_as_alive(self):
        """A live process owned by another user exists. This is the second
        place a `kill -0` shell rewrite diverges, and it cannot be provoked
        portably, so it is driven at the `os.kill` seam."""
        def _deny(pid, sig):
            raise PermissionError(1, "Operation not permitted")

        original = monitor_marker.os.kill
        monitor_marker.os.kill = _deny
        try:
            self.assertEqual(
                monitor_marker_state(f"minimonitor:{_LIVE_PID}"), STATE_PRESENT
            )
        finally:
            monitor_marker.os.kill = original


class MarkerCliParityTests(unittest.TestCase):
    """Lane 2: the CLI the shell guard actually executes."""

    def test_table_via_cli(self):
        for value, expected in MARKER_TABLE:
            with self.subTest(value=value):
                self.assertEqual(_cli_state(value), expected)

    def test_lanes_agree(self):
        for value, _expected in MARKER_TABLE:
            with self.subTest(value=value):
                self.assertEqual(_cli_state(value), monitor_marker_state(value))

    def test_cli_prints_nothing(self):
        """Exit status IS the verdict; output would invite a caller to parse it
        (and `--help` must not produce usage text)."""
        for value in ("", f"minimonitor:{_LIVE_PID}", "--help"):
            with self.subTest(value=value):
                proc = subprocess.run(
                    [sys.executable, str(MARKER_TOOL), "state", value],
                    capture_output=True, text=True,
                )
                self.assertEqual(proc.stdout, "")
                self.assertEqual(proc.stderr, "")


class MarkerCliTransportTests(unittest.TestCase):
    """The verdict/error-code collision this design exists to avoid."""

    def test_verdict_codes_are_disjoint_from_interpreter_failures(self):
        """An uncaught exception exits 1, a missing file / usage error exits 2,
        a failed exec 126/127, a signal 128+n. A verdict sharing any of those
        makes an interpreter failure look like a decision — and `1` mapped to
        `stale` would clear a live marker on a crash."""
        self.assertEqual(EXIT_PRESENT, 0)
        for code in (EXIT_STALE, EXIT_ABSENT):
            self.assertGreater(code, 2)
            self.assertLess(code, 126)
        self.assertEqual(
            len({EXIT_PRESENT, EXIT_STALE, EXIT_ABSENT}), 3, "codes must differ"
        )

    def test_usage_errors_fail_safe_to_present(self):
        for argv in (
            ["monitor_marker.py"],
            ["monitor_marker.py", "state"],
            ["monitor_marker.py", "bogus", "x"],
            ["monitor_marker.py", "state", "a", "b"],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(monitor_marker.main(argv), EXIT_PRESENT)

    def test_usage_errors_fail_safe_via_subprocess(self):
        for args in ([], ["state"], ["bogus", "x"], ["state", "a", "b"]):
            with self.subTest(args=args):
                proc = subprocess.run(
                    [sys.executable, str(MARKER_TOOL), *args],
                    capture_output=True, text=True,
                )
                self.assertEqual(proc.returncode, EXIT_PRESENT)

    def test_internal_failure_fails_safe_to_present(self):
        """The contract must not rest on the caller's exit-code mapping alone."""
        def _boom(value):
            raise RuntimeError("classification exploded")

        original = monitor_marker.monitor_marker_state
        monitor_marker.monitor_marker_state = _boom
        try:
            self.assertEqual(
                monitor_marker.main(["monitor_marker.py", "state", "whatever"]),
                EXIT_PRESENT,
            )
        finally:
            monitor_marker.monitor_marker_state = original


if __name__ == "__main__":
    unittest.main()
