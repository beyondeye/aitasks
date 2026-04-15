"""Tests for lib/launch_modes.py and its shell bridge."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"
HELPER_SH = LIB_DIR / "launch_modes_sh.sh"

sys.path.insert(0, str(LIB_DIR))
import launch_modes  # noqa: E402


class TestModule(unittest.TestCase):
    def test_default_in_valid_set(self):
        self.assertIn(launch_modes.DEFAULT_LAUNCH_MODE,
                      launch_modes.VALID_LAUNCH_MODES)

    def test_seed_vocabulary(self):
        self.assertIn("headless", launch_modes.VALID_LAUNCH_MODES)
        self.assertIn("interactive", launch_modes.VALID_LAUNCH_MODES)
        self.assertIn("openshell", launch_modes.VALID_LAUNCH_MODES)

    def test_validate(self):
        self.assertTrue(launch_modes.validate_launch_mode("headless"))
        self.assertTrue(launch_modes.validate_launch_mode("interactive"))
        self.assertTrue(launch_modes.validate_launch_mode("openshell"))
        self.assertFalse(launch_modes.validate_launch_mode("bogus"))
        self.assertFalse(launch_modes.validate_launch_mode(""))

    def test_normalize(self):
        self.assertEqual(launch_modes.normalize_launch_mode("headless"),
                         "headless")
        self.assertEqual(launch_modes.normalize_launch_mode(None),
                         launch_modes.DEFAULT_LAUNCH_MODE)
        self.assertEqual(launch_modes.normalize_launch_mode("bogus"),
                         launch_modes.DEFAULT_LAUNCH_MODE)
        self.assertEqual(
            launch_modes.normalize_launch_mode(None, "interactive"),
            "interactive",
        )

    def test_pipe_sorted(self):
        self.assertEqual(
            launch_modes.launch_modes_pipe(),
            "|".join(sorted(launch_modes.VALID_LAUNCH_MODES)),
        )


class TestShellBridgeParity(unittest.TestCase):
    """Shell bridge must stay in sync with the Python module."""

    def _source_and_echo(self, var: str, env: dict | None = None) -> str:
        result = subprocess.run(
            ["bash", "-c",
             f'source "{HELPER_SH}"; printf %s "${{{var}}}"'],
            capture_output=True, text=True,
            env={**os.environ, **(env or {})},
        )
        self.assertEqual(result.returncode, 0,
                         f"shell bridge failed: {result.stderr}")
        return result.stdout

    def test_pipe_matches_python(self):
        self.assertEqual(
            self._source_and_echo("LAUNCH_MODES_PIPE"),
            launch_modes.launch_modes_pipe(),
        )

    def test_regex_matches_python(self):
        self.assertEqual(
            self._source_and_echo("LAUNCH_MODES_REGEX"),
            f"^({launch_modes.launch_modes_pipe()})$",
        )


class TestExtensibility(unittest.TestCase):
    """Adding a new mode to VALID_LAUNCH_MODES flows to every consumer
    with no other file edits. Uses AIT_LAUNCH_MODES_DIR override to
    avoid mutating the real module on disk."""

    def test_new_mode_propagates_to_shell_bridge(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            sandbox = Path(td)
            (sandbox / "launch_modes.py").write_text(textwrap.dedent("""
                VALID_LAUNCH_MODES = frozenset(
                    {"headless", "interactive", "openshell", "futuremode"}
                )
                DEFAULT_LAUNCH_MODE = "headless"
                def launch_modes_pipe():
                    return "|".join(sorted(VALID_LAUNCH_MODES))
                def validate_launch_mode(v): return v in VALID_LAUNCH_MODES
                def normalize_launch_mode(v, fb="headless"):
                    return fb if v is None or v not in VALID_LAUNCH_MODES else v
            """))
            env = {"AIT_LAUNCH_MODES_DIR": str(sandbox)}
            result = subprocess.run(
                ["bash", "-c",
                 f'source "{HELPER_SH}"; printf %s "$LAUNCH_MODES_PIPE"'],
                capture_output=True, text=True,
                env={**os.environ, **env},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("futuremode", result.stdout)
            self.assertIn("headless", result.stdout)
            self.assertIn("interactive", result.stdout)
            self.assertIn("openshell", result.stdout)
            parts = result.stdout.split("|")
            self.assertEqual(parts, sorted(parts))


if __name__ == "__main__":
    unittest.main()
