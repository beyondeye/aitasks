"""Unit tests for GateSummaryCache mtime/size invalidation (t1111_1).

The monitor's per-task gate summary cache used to be cleared wholesale on every
3s refresh tick, re-reading every visible gated task's ledger from disk. It now
invalidates by file identity ``(st_mtime_ns, st_size)``: an unchanged ledger is
served from cache; a changed one re-reads. These tests pin that contract with a
call-counting spy over the shared ``gate_ledger.read_task_gate_state`` disk read.

The ``st_mtime_ns`` (not float ``st_mtime``) + ``st_size`` identity is the point
of the change: float-second granularity would miss two ledger edits within the
same wall-clock second, and mtime alone would miss a same-mtime rewrite of a
different length — ``test_same_mtime_different_size_rereads`` is the guard.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from monitor.monitor_shared import GateSummaryCache  # noqa: E402
from monitor import monitor_core  # noqa: E402


GATED_BODY = (
    "## Gate Runs\n\n"
    "> **✅ gate:plan_approved** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human\n\n"
    "> **✅ gate:risk_evaluated** run=2026-01-01T00:01:00Z status=pass attempt=1 type=machine\n\n"
    "> **✅ gate:build_verified** run=2026-01-01T00:02:00Z status=pass attempt=1 type=machine\n\n"
    "> **⏳ gate:review_approved** run=2026-01-01T00:03:00Z status=pending type=human\n"
)


def _task_text(body: str) -> str:
    return (
        "---\n"
        "priority: medium\n"
        "effort: low\n"
        "status: Implementing\n"
        "issue_type: feature\n"
        "---\n\n"
        "# Demo task\n\n"
        f"{body}"
    )


class GateCacheMtimeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "t10_demo.md"
        self.path.write_text(_task_text(GATED_BODY), encoding="utf-8")

        self.gc = GateSummaryCache()

        # Count real disk reads of the ledger; os.stat identity checks are not
        # counted (they are the cheap gate the cache adds in front of the read).
        self.reads = {"n": 0}
        orig = monitor_core.gate_ledger.read_task_gate_state

        def counting(*a, **k):
            self.reads["n"] += 1
            return orig(*a, **k)

        monitor_core.gate_ledger.read_task_gate_state = counting
        self.addCleanup(
            setattr, monitor_core.gate_ledger, "read_task_gate_state", orig
        )

    def _info(self, *, abs_path=None, body=GATED_BODY):
        return monitor_core.TaskInfo(
            task_id="10", task_file="aitasks/t10_demo.md", title="Demo",
            priority="", effort="", issue_type="", status="", body=body,
            plan_content=None,
            task_file_abs=str(self.path) if abs_path is None else abs_path,
        )

    def test_two_calls_one_read(self):
        # Unchanged file across two calls → served from cache the second time.
        info = self._info()
        self.assertEqual(self.gc.summary_for(info), "3/4 pass, 1 pending")
        self.assertEqual(self.gc.summary_for(info), "3/4 pass, 1 pending")
        self.assertEqual(self.reads["n"], 1)

    def test_mtime_bump_rereads(self):
        info = self._info()
        self.gc.summary_for(info)
        self.assertEqual(self.reads["n"], 1)
        # Bump mtime (ns) without touching content/size → identity changed.
        st = os.stat(self.path)
        os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        self.gc.summary_for(info)
        self.assertEqual(self.reads["n"], 2)

    def test_same_mtime_different_size_rereads(self):
        info = self._info()
        self.gc.summary_for(info)
        self.assertEqual(self.reads["n"], 1)
        orig = os.stat(self.path)
        # Rewrite with a DIFFERENT length, then force mtime_ns back to the
        # original value. mtime-only (or float-second) identity would treat this
        # as unchanged; the size component catches it.
        longer = GATED_BODY + (
            "> **✅ gate:merge_approved** run=2026-01-01T00:04:00Z "
            "status=pass attempt=1 type=human\n"
        )
        self.path.write_text(_task_text(longer), encoding="utf-8")
        self.assertNotEqual(os.stat(self.path).st_size, orig.st_size)
        os.utime(self.path, ns=(orig.st_atime_ns, orig.st_mtime_ns))
        self.assertEqual(os.stat(self.path).st_mtime_ns, orig.st_mtime_ns)
        self.gc.summary_for(info)
        self.assertEqual(self.reads["n"], 2)

    def test_missing_file_fails_closed(self):
        # os.stat miss short-circuits before the ledger read: "" and no raise.
        info = self._info(abs_path="/nonexistent/dir/t10_demo.md")
        self.assertEqual(self.gc.summary_for(info), "")
        self.assertEqual(self.reads["n"], 0)


if __name__ == "__main__":
    unittest.main()
