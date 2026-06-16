"""Unit tests for GateSummaryCache + TaskInfo.task_file_abs (t635_10).

The monitor TUIs show a compact per-task gate summary derived via the shared
``lib/gate_ledger.py`` parser. These tests verify:

- the compact summary is rendered for tasks that have a gate ledger and empty
  for ungated tasks (no column noise);
- the cache fails closed (returns "") on missing/unreadable paths and never
  raises;
- the cache parses the ABSOLUTE ``task_file_abs`` path, so it is correct even
  when the process working directory is not the task's project root (the
  cross-session / multi-project monitor case);
- caching avoids a re-read, and ``clear()`` drops the cache.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from monitor.monitor_shared import GateSummaryCache, TaskInfoCache  # noqa: E402
from monitor import monitor_core  # noqa: E402


GATED_BODY = (
    "## Gate Runs\n\n"
    "> **✅ gate:plan_approved** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human\n\n"
    "> **✅ gate:risk_evaluated** run=2026-01-01T00:01:00Z status=pass attempt=1 type=machine\n\n"
    "> **✅ gate:build_verified** run=2026-01-01T00:02:00Z status=pass attempt=1 type=machine\n\n"
    "> **⏳ gate:review_approved** run=2026-01-01T00:03:00Z status=pending type=human\n"
)


def _write_task(path: Path, *, gated: bool, status: str = "Implementing") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = GATED_BODY if gated else "Just a plain body, no gate markers.\n"
    path.write_text(
        "---\n"
        "priority: medium\n"
        "effort: low\n"
        f"status: {status}\n"
        "issue_type: feature\n"
        "---\n\n"
        "# Demo task\n\n"
        f"{body}",
        encoding="utf-8",
    )


class GateSummaryCacheTest(unittest.TestCase):
    def _resolve(self, tmp: Path, *, gated: bool):
        """Resolve a TaskInfo for t10 via TaskInfoCache rooted at ``tmp``."""
        _write_task(tmp / "aitasks" / "t10_demo.md", gated=gated)
        cache = TaskInfoCache(tmp)
        info = cache.get_task_info("10")
        self.assertIsNotNone(info)
        return info

    def test_gated_task_renders_summary(self):
        with tempfile.TemporaryDirectory() as d:
            info = self._resolve(Path(d), gated=True)
            gc = GateSummaryCache()
            self.assertEqual(gc.summary_for(info), "3/4 pass, 1 pending")

    def test_ungated_task_empty(self):
        with tempfile.TemporaryDirectory() as d:
            info = self._resolve(Path(d), gated=False)
            gc = GateSummaryCache()
            self.assertEqual(gc.summary_for(info), "")

    def test_none_and_empty_abs_path(self):
        gc = GateSummaryCache()
        self.assertEqual(gc.summary_for(None), "")
        stub = monitor_core.TaskInfo(
            task_id="10", task_file="aitasks/t10_demo.md", title="x",
            priority="", effort="", issue_type="", status="", body=GATED_BODY,
            plan_content=None,  # task_file_abs defaults to ""
        )
        self.assertEqual(gc.summary_for(stub), "")

    def test_fail_closed_on_missing_file(self):
        # has_gate_markers is true (body has markers) but the absolute path does
        # not exist → read_task_gate_state raises → fail closed to "".
        gc = GateSummaryCache()
        info = monitor_core.TaskInfo(
            task_id="10", task_file="aitasks/t10_demo.md", title="x",
            priority="", effort="", issue_type="", status="", body=GATED_BODY,
            plan_content=None, task_file_abs="/nonexistent/dir/t10_demo.md",
        )
        self.assertEqual(gc.summary_for(info), "")  # no exception

    def test_caches_and_clears(self):
        with tempfile.TemporaryDirectory() as d:
            info = self._resolve(Path(d), gated=True)
            gc = GateSummaryCache()

            calls = {"n": 0}
            orig = monitor_core.gate_ledger.read_task_gate_state

            def counting(*a, **k):
                calls["n"] += 1
                return orig(*a, **k)

            monitor_core.gate_ledger.read_task_gate_state = counting
            try:
                self.assertEqual(gc.summary_for(info), "3/4 pass, 1 pending")
                self.assertEqual(gc.summary_for(info), "3/4 pass, 1 pending")
                self.assertEqual(calls["n"], 1)  # second call served from cache
                gc.clear()
                self.assertEqual(gc.summary_for(info), "3/4 pass, 1 pending")
                self.assertEqual(calls["n"], 2)  # re-derived after clear
            finally:
                monitor_core.gate_ledger.read_task_gate_state = orig

    def test_cwd_independent(self):
        # The must-fix: summary_for must parse the ABSOLUTE task_file_abs, not
        # the relative task_file, so it is correct when cwd != project root.
        with tempfile.TemporaryDirectory() as proj, \
                tempfile.TemporaryDirectory() as elsewhere:
            info = self._resolve(Path(proj), gated=True)

            # task_file stays relative (display value); task_file_abs is absolute
            # and inside the project root.
            self.assertFalse(os.path.isabs(info.task_file))
            self.assertTrue(os.path.isabs(info.task_file_abs))
            self.assertTrue(
                Path(info.task_file_abs).resolve().is_relative_to(Path(proj).resolve())
            )

            gc = GateSummaryCache()
            cwd = os.getcwd()
            os.chdir(elsewhere)  # unrelated dir: relative task_file would miss
            try:
                self.assertEqual(gc.summary_for(info), "3/4 pass, 1 pending")
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
