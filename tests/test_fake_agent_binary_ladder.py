"""The source ladder in `tests/lib/fake_agent_binary.py` is lazy (t1744).

t1737 item #4 measured the pre-fix module and found rung 2 — which `mkdtemp`s a
build dir and invokes `cc`/`clang`/`gcc` — evaluated **unconditionally**, on
every platform, because the loop was written over an eagerly built tuple
`(_sleep_binary(), _compiled_sleeper_path())`. The right binary came back, but
Linux paid for a C compile whose product was discarded, once per test process.

The benefit of the fix lives at the **call site**, not in either helper, so every
case here spies on the module attribute `_compiled_sleeper_path` and drives the
real `fake_agent_binary()` entry point.

`fake_agent_binary()` can fall out of a rung two different ways, and they fail
independently, so they are covered separately:

    A. `shutil.copy` raises — the source could not be copied at all;
    B. the copy lands but `_runs()` rejects it — the macOS case the module exists
       for (docstring §2: a copy of the system `sleep` is SIGKILLed on exec).

Covers:
  1. Rung 2 is NOT consulted when rung 1 succeeds — the t1737 finding — with the
     returned file asserted to be rung 1's own copy, so a ladder that simply
     dropped rung 1 could not pass instead.
  2. Rung 2 IS consulted, exactly once, when rung 1 falls out via path B.
  3. Rung 2 IS consulted, exactly once, when rung 1 falls out via path A.
  4. No rung runs and `allow_symlink=False` → `FakeAgentBinaryUnavailable`, with
     the file rung 1 left at `dest` cleaned up. Driven through path B so that
     cleanup assertion is not vacuous.
  5. `allow_symlink=True` reaches rung 3, and the link it leaves resolves to a
     runnable target and actually executes.

No case invokes a real compiler: rung 2 is spied in every one.

Run:
  python3 tests/test_fake_agent_binary_ladder.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import fake_agent_binary as fab  # noqa: E402

#: `sh` scripts, not copies of the system `sleep`: they copy and run on Linux
#: and macOS alike, so a rung can be made to succeed or fail deterministically
#: on either platform. `_runs()` invokes `[path, "0"]`; both ignore the argument.
_OK_STUB = "#!/bin/sh\nexit 0\n"
_FAIL_STUB = "#!/bin/sh\nexit 1\n"


class LadderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="ait-ladder-test-")
        # Registered immediately, and via addCleanup rather than tearDown, so
        # the directory goes away after a failing assertion too.
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ok_stub = self._stub("ok_stub", _OK_STUB)
        self.fail_stub = self._stub("fail_stub", _FAIL_STUB)
        self.missing = os.path.join(self.tmp, "no_such_source")
        self.rung2_calls = 0

        self._saved = {name: getattr(fab, name)
                       for name in ("_sleep_binary", "_compiled_sleeper_path", "_runs")}
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        for name, value in self._saved.items():
            setattr(fab, name, value)

    def _stub(self, name: str, body: str) -> str:
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.chmod(path, 0o755)
        return path

    def _spy_rung_two(self, result: str | None):
        """Replace rung 2 with a counting stub — no compiler is ever invoked."""
        def spy() -> str | None:
            self.rung2_calls += 1
            return result
        fab._compiled_sleeper_path = spy

    def _read(self, path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    # 1 — the t1737 finding.
    def test_rung_two_not_consulted_when_rung_one_succeeds(self) -> None:
        fab._sleep_binary = lambda: self.ok_stub
        self._spy_rung_two(self.fail_stub)

        dest = fab.fake_agent_binary(self.tmp, "claude")

        self.assertEqual(self.rung2_calls, 0,
                         "rung 2 was consulted even though rung 1 succeeded")
        # Negative control: without this, a ladder that dropped rung 1 entirely
        # would satisfy the zero-call assertion just as well.
        self.assertFalse(os.path.islink(dest))
        self.assertEqual(self._read(dest), _OK_STUB)

    # 2 — path B: the copy lands, the result will not run (the macOS shape).
    def test_rung_two_consulted_once_when_rung_one_copies_but_does_not_run(self) -> None:
        fab._sleep_binary = lambda: self.fail_stub
        self._spy_rung_two(self.ok_stub)

        dest = fab.fake_agent_binary(self.tmp, "claude")

        self.assertEqual(self.rung2_calls, 1)
        self.assertEqual(self._read(dest), _OK_STUB,
                         "returned the unrunnable rung-1 copy instead of rung 2's")

    # 3 — path A: the source could not be copied at all.
    def test_rung_two_consulted_once_when_rung_one_cannot_be_copied(self) -> None:
        fab._sleep_binary = lambda: self.missing
        self._spy_rung_two(self.ok_stub)

        dest = fab.fake_agent_binary(self.tmp, "claude")

        self.assertEqual(self.rung2_calls, 1)
        self.assertEqual(self._read(dest), _OK_STUB)

    # 4 — every rung exhausted, symlink not opted into.
    def test_unavailable_and_dest_cleaned_when_no_rung_runs(self) -> None:
        # Via path B on purpose: rung 1's copy really does land at `dest`, so
        # the cleanup below has something to remove. Reached via path A nothing
        # is ever created and the assertion would pass without testing anything.
        fab._sleep_binary = lambda: self.fail_stub
        self._spy_rung_two(None)

        with self.assertRaises(fab.FakeAgentBinaryUnavailable):
            fab.fake_agent_binary(self.tmp, "claude")

        self.assertEqual(self.rung2_calls, 1)
        self.assertFalse(os.path.lexists(os.path.join(self.tmp, "claude")),
                         "the unrunnable rung-1 copy was left behind at dest")

    # 5 — rung 3, which looks up the system sleep a second time (line 153).
    def test_symlink_rung_resolves_and_executes_when_opted_in(self) -> None:
        # The macOS-shaped condition rung 3 exists for: the source is fine, but
        # nothing copied out of place will run. That keeps rung 3's target
        # runnable while rungs 1-2 both fall through.
        fab._sleep_binary = lambda: self.ok_stub
        fab._runs = lambda path: False
        self._spy_rung_two(None)

        dest = fab.fake_agent_binary(self.tmp, "claude", allow_symlink=True)

        self.assertTrue(os.path.islink(dest))
        self.assertEqual(os.path.realpath(dest), os.path.realpath(self.ok_stub))
        # Independent ground truth: `_runs` is stubbed to False above, so the
        # module's own verdict proves nothing about whether the link is usable.
        self.assertEqual(
            subprocess.run([dest, "0"], capture_output=True, timeout=30).returncode, 0,
            "the symlink rung 3 left behind does not execute")


if __name__ == "__main__":
    unittest.main()
