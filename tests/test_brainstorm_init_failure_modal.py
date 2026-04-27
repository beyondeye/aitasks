"""Tests for InitFailureModal + _format_init_error in brainstorm_app.

Covers t660: brainstorm TUI used to silently exit when `ait brainstorm init`
failed (e.g. stale `crew-brainstorm-<N>` branch from a prior aborted attempt).
The fix surfaces the captured stderr/stdout in a persistent modal.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_app import (  # noqa: E402
    BrainstormApp,
    InitFailureModal,
    detect_stale_crew_branch,
)


class _StubApp:
    """Minimal stand-in carrying just the attributes _format_init_error reads."""

    def __init__(self, task_num: str):
        self.task_num = task_num


class FormatInitErrorTests(unittest.TestCase):
    def _format(self, app, *args, **kwargs):
        return BrainstormApp._format_init_error(app, *args, **kwargs)

    def test_includes_summary_stderr_and_stdout(self):
        text = self._format(
            _StubApp("42"),
            "Subprocess exit 1.",
            "stdout body",
            "stderr body",
            include_runner_log=False,
        )
        self.assertIn("Subprocess exit 1.", text)
        self.assertIn("STDERR:", text)
        self.assertIn("stderr body", text)
        self.assertIn("STDOUT:", text)
        self.assertIn("stdout body", text)

    def test_empty_streams_render_placeholder(self):
        text = self._format(
            _StubApp("42"), "Failure.", "", "", include_runner_log=False
        )
        self.assertIn("(empty)", text)

    def test_runner_log_appended_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            wt = tmp / ".aitask-crews" / "crew-brainstorm-7777"
            wt.mkdir(parents=True)
            log = wt / "_runner_launch.log"
            log.write_text("Traceback (most recent call last):\n  RuntimeError: boom\n")

            with patch(
                "brainstorm.brainstorm_app.crew_worktree", return_value=wt
            ):
                text = self._format(
                    _StubApp("7777"),
                    "Runner crashed.",
                    "out",
                    "err",
                    include_runner_log=True,
                )

            self.assertIn("_runner_launch.log", text)
            self.assertIn("RuntimeError: boom", text)

    def test_runner_log_skipped_when_absent(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td) / "missing-crew"
            with patch(
                "brainstorm.brainstorm_app.crew_worktree", return_value=wt
            ):
                text = self._format(
                    _StubApp("7777"),
                    "Runner crashed.",
                    "out",
                    "err",
                    include_runner_log=True,
                )
            self.assertNotIn("_runner_launch.log", text)


class StaleCrewBranchDetectionTests(unittest.TestCase):
    def test_detects_branch_from_aitask_crew_init_error(self):
        err = (
            "Error: Failed to create crew: Error: "
            "Branch 'crew-brainstorm-635' already exists. "
            "Crew 'brainstorm-635' may already be initialized."
        )
        self.assertEqual(detect_stale_crew_branch(err), "crew-brainstorm-635")

    def test_detects_branch_with_alphanumeric_task_num(self):
        err = "Branch 'crew-brainstorm-42_3' already exists."
        self.assertEqual(detect_stale_crew_branch(err), "crew-brainstorm-42_3")

    def test_returns_none_when_no_branch_mentioned(self):
        self.assertIsNone(detect_stale_crew_branch("Some other error"))
        self.assertIsNone(detect_stale_crew_branch(""))

    def test_returns_none_for_unrelated_branch(self):
        # Only crew-brainstorm-* branches qualify; other branch errors aren't recoverable here.
        self.assertIsNone(
            detect_stale_crew_branch("Branch 'main' already exists")
        )


class InitFailureModalSmokeTests(unittest.TestCase):
    def test_can_instantiate_with_error_text(self):
        modal = InitFailureModal("multi\nline\nerror")
        self.assertEqual(modal.error_text, "multi\nline\nerror")
        self.assertIsNone(modal.stale_branch)

    def test_stale_branch_attr_populated_when_pattern_matches(self):
        modal = InitFailureModal(
            "Error: Branch 'crew-brainstorm-635' already exists."
        )
        self.assertEqual(modal.stale_branch, "crew-brainstorm-635")


if __name__ == "__main__":
    unittest.main()
