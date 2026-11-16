"""The non-procfs `ps -o args=` fallbacks read argv at full width (t2311).

procps `ps` honours an inherited `COLUMNS` and cuts `-o args=` at that width
even when stdout is a pipe. A process that imported `readline` (pytest does)
has `COLUMNS=80` exported into its C-level environment, so every child `ps`
inherits it. `-ww` (unlimited width, accepted by procps and BSD ps) is the
fix. Whether BSD ps honours `COLUMNS` on a pipe is not measured; the tests
pin `-ww` on the platform where the truncation is real.

Each test forces the fallback by making the module's `/proc` read fail (the
module-global `open` shadows the builtin for that module only) and pins
`COLUMNS=80` in `os.environ`, which `subprocess.run` hands to `ps`. A positive
control proves the fixture really truncates without `-ww`, so the two
production assertions are not vacuous.

Run: python3 tests/test_ps_args_full_width.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from aitask_questions import owner  # noqa: E402
from monitor import monitor_core  # noqa: E402

PAD = "x" * 150  # pushes the marker well past column 80


def _no_procfs(*_args, **_kwargs):
    raise OSError("procfs disabled by the test")


@unittest.skipUnless(shutil.which("ps"), "ps is not on PATH")
class FullWidthFallbackTest(unittest.TestCase):

    def _spawn(self, marker: str) -> int:
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)", PAD + marker],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def _reap():
            proc.kill()
            proc.wait(timeout=5)
        self.addCleanup(_reap)
        # Wait until ps sees the exec'd argv, not the pre-exec fork image.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            out = subprocess.run(["ps", "-ww", "-o", "args=", "-p", str(proc.pid)],
                                 capture_output=True, text=True).stdout
            if marker in out:
                break
            time.sleep(0.05)
        return proc.pid

    def _narrow_env(self):
        return patch.dict(os.environ, {"COLUMNS": "80"})

    def test_control_plain_ps_truncates(self):
        """Without -ww the fixture's marker is cut off; otherwise the
        assertions below would pass whatever the production code does."""
        pid = self._spawn("CONTROLMARK")
        with self._narrow_env():
            out = subprocess.run(["ps", "-o", "args=", "-p", str(pid)],
                                 capture_output=True, text=True).stdout
        if "CONTROLMARK" in out:
            self.skipTest("this platform's ps does not truncate under COLUMNS=80")
        self.assertLessEqual(len(out.strip()), 80)

    def test_owner_argv_fallback_full_width(self):
        pid = self._spawn("OWNERMARK")
        with self._narrow_env(), \
                patch("aitask_questions.owner.open", _no_procfs, create=True):
            argv = owner._argv(pid)
        self.assertTrue(argv, "fallback returned no argv")
        self.assertEqual(argv[-1], PAD + "OWNERMARK")

    def test_companion_fallback_sees_keyword_past_col_80(self):
        pid = self._spawn("minimonitor")
        with self._narrow_env(), \
                patch("monitor.monitor_core.open", _no_procfs, create=True):
            self.assertTrue(monitor_core._is_companion_process(pid))


if __name__ == "__main__":
    unittest.main()
