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


class _GateCacheFixture(unittest.TestCase):
    """setUp + ``_info`` shared by the cache test classes; holds no tests."""

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


class GateCacheMtimeTest(_GateCacheFixture):
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



class LedgerIdentityTest(_GateCacheFixture):
    """``ledger_identity_for`` — gate-run CONTENT identity (t2283).

    The minimonitor's stale-banner gate asks "has a new gate run been recorded
    since this feedback was bound?". File identity cannot answer that: a note,
    a status flip or any frontmatter rewrite changes ``(st_mtime_ns, st_size)``
    without recording anything. So the identity must move with the gate-run
    blocks and with nothing else.
    """

    APPENDED = GATED_BODY + (
        "\n> **✅ gate:plan_approved** run=2026-01-02T00:00:00Z "
        "status=pass attempt=2 type=human\n"
    )

    def _rewrite(self, body, *, status="Implementing"):
        text = _task_text(body).replace("status: Implementing",
                                        f"status: {status}")
        self.path.write_text(text, encoding="utf-8")
        st = os.stat(self.path)
        # Force a distinct ns mtime even on coarse-timestamp filesystems.
        os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
        return self._info(body=body)

    def test_identity_is_a_stable_string_served_from_cache(self):
        info = self._info()
        first = self.gc.ledger_identity_for(info)
        self.assertIsInstance(first, str)
        self.assertTrue(first)
        self.assertEqual(self.gc.ledger_identity_for(info), first)
        self.assertEqual(self.reads["n"], 1, "identity must share the cache entry")

    def test_appending_a_gate_run_changes_it(self):
        before = self.gc.ledger_identity_for(self._info())
        after = self.gc.ledger_identity_for(self._rewrite(self.APPENDED))
        self.assertNotEqual(before, after)

    def test_non_ledger_edits_leave_it_unchanged(self):
        before = self.gc.ledger_identity_for(self._info())
        cases = (
            ("frontmatter status edit", GATED_BODY, "Ready"),
            ("prose edit", "Some new prose.\n\n" + GATED_BODY, "Implementing"),
            ("inbox note", GATED_BODY + "\n## Inbox\n\n> | a note\n",
             "Implementing"),
        )
        for label, body, status in cases:
            with self.subTest(label):
                reads = self.reads["n"]
                info = self._rewrite(body, status=status)
                self.assertEqual(self.gc.ledger_identity_for(info), before)
                self.assertEqual(self.reads["n"], reads + 1,
                                 "fixture must really invalidate the cache")

    def test_empty_ledger_has_a_real_identity(self):
        gated = self.gc.ledger_identity_for(self._info())
        empty = self.gc.ledger_identity_for(self._rewrite("No ledger here.\n"))
        self.assertIsNotNone(empty)
        self.assertNotEqual(empty, gated)

    def test_underivable_identity_is_none(self):
        self.assertIsNone(self.gc.ledger_identity_for(None))
        self.assertIsNone(self.gc.ledger_identity_for(
            self._info(abs_path="/nonexistent/dir/t10_demo.md")))
        self.assertIsNone(self.gc.ledger_identity_for(self._info(abs_path="")))

    def test_a_parse_failure_is_none_not_a_crash(self):
        orig = monitor_core._ledger_content_identity

        def boom(*a, **k):
            raise RuntimeError("identity failed")

        monitor_core._ledger_content_identity = boom
        self.addCleanup(setattr, monitor_core, "_ledger_content_identity", orig)
        info = self._info()
        self.assertIsNone(self.gc.ledger_identity_for(info))
        # The other halves of the entry are unaffected.
        self.assertEqual(self.gc.summary_for(info), "3/4 pass, 1 pending")


if __name__ == "__main__":
    unittest.main()
