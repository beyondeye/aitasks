"""`followup_kind` through the REAL TaskInfoCache sibling lookups (t1468_5).

`find_next_sibling` / `find_ready_siblings` gained a `followup_kind` slot so the
monitor / minimonitor sibling picker and the applink `pick_next_sibling` payload
can show that a candidate is an auto-spawned follow-up rather than genuine new
work.

**Why this file has to exist.** Every other test touching that surface reads a
*replica* rather than the real class:

- ``tests/test_applink_router.sh`` supplies its own ``find_ready_siblings``
  stub returning hardcoded tuples — it never parses frontmatter;
- ``tests/test_monitor_sibling_row_render.py`` constructs ``_SiblingRow``
  directly — it never calls the cache;
- ``tests/test_multi_session_monitor.sh`` *does* drive the real cache, but
  indexes only ``[0]``.

So a wrong frontmatter key or a wrong tuple slot in ``monitor_core.py`` would
leave the picker and the payload silently unmarked while all of those stay
green. This drives the real cache over a real on-disk task tree and asserts the
value through **both** return shapes, for a recognised kind, an absent kind, and
an unrecognised one.

Run: python3 tests/test_task_info_cache_followup_kind.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from monitor.monitor_core import TaskInfoCache  # noqa: E402

PARENT = "700"


def _write_child(root: Path, child: str, title: str, *,
                 status: str = "Ready", followup_kind: str | None = None,
                 depends: str | None = None) -> None:
    path = root / "aitasks" / f"t{PARENT}" / f"t{PARENT}_{child}_{title}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "priority: medium",
        "effort: medium",
        f"status: {status}",
        "issue_type: feature",
    ]
    if followup_kind is not None:
        lines.append(f"followup_kind: {followup_kind}")
    if depends is not None:
        lines.append(f"depends: [{depends}]")
    lines += ["---", "", f"# Child {child}", "", "body"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class SiblingFollowupKindTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "aitasks").mkdir()
        (self.root / "aiplans").mkdir()
        self.cache = TaskInfoCache(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _ready_kinds(self, task_id: str) -> dict:
        """{sib_id: followup_kind} from the real find_ready_siblings rows."""
        rows = self.cache.find_ready_siblings(task_id)
        for row in rows:
            self.assertEqual(len(row), 4, "row shape is part of the contract")
        return {sib_id: kind for sib_id, _title, _blocked, kind in rows}

    # --- find_ready_siblings -------------------------------------------------

    def test_ready_siblings_carry_every_kind_class(self) -> None:
        _write_child(self.root, "1", "current")
        _write_child(self.root, "2", "recognised",
                     followup_kind="risk_mitigation")
        _write_child(self.root, "3", "ordinary")
        _write_child(self.root, "4", "unrecognised",
                     followup_kind="not_a_real_kind")

        kinds = self._ready_kinds(f"{PARENT}_1")

        self.assertEqual(kinds[f"{PARENT}_2"], "risk_mitigation",
                         "a recognised kind must reach the caller verbatim")
        self.assertEqual(kinds[f"{PARENT}_3"], "",
                         "a task with no followup_kind reads as no follow-up")
        self.assertEqual(kinds[f"{PARENT}_4"], "not_a_real_kind",
                         "an unrecognised kind rides through, so the render "
                         "boundary can show it as unrecognised rather than as "
                         "'not a follow-up'")

    def test_ready_siblings_keep_blocked_by_alongside_the_kind(self) -> None:
        """The kind is an addition, not a replacement, of the blocking hint."""
        _write_child(self.root, "1", "current")
        _write_child(self.root, "2", "prereq")
        _write_child(self.root, "3", "dependent",
                     followup_kind="upstream_defect",
                     depends=f"{PARENT}_2")

        rows = {row[0]: row for row in self.cache.find_ready_siblings(f"{PARENT}_1")}

        self.assertEqual(rows[f"{PARENT}_3"][2], [f"{PARENT}_2"])
        self.assertEqual(rows[f"{PARENT}_3"][3], "upstream_defect")

    def test_ready_siblings_coerce_a_non_string_kind(self) -> None:
        """A hand-edited list / int must not escape as a non-string.

        The applink payload JSON-serializes this value, so the tuple slot has
        to be a string or the wire shape becomes type-unstable.
        """
        _write_child(self.root, "1", "current")
        _write_child(self.root, "2", "listy", followup_kind="[a, b]")
        _write_child(self.root, "3", "inty", followup_kind="42")

        kinds = self._ready_kinds(f"{PARENT}_1")

        for sib in (f"{PARENT}_2", f"{PARENT}_3"):
            self.assertIsInstance(kinds[sib], str)
        self.assertEqual(kinds[f"{PARENT}_2"], "",
                         "a list is not a kind — it reads as no follow-up")

    # --- find_next_sibling ---------------------------------------------------

    def test_next_sibling_carries_a_recognised_kind(self) -> None:
        _write_child(self.root, "1", "current")
        _write_child(self.root, "2", "suggested", followup_kind="qa_test_gap")

        result = self.cache.find_next_sibling(f"{PARENT}_1")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3, "return shape is part of the contract")
        self.assertEqual(result[0], f"{PARENT}_2")
        self.assertEqual(result[2], "qa_test_gap")

    def test_next_sibling_kind_is_empty_when_absent(self) -> None:
        _write_child(self.root, "1", "current")
        _write_child(self.root, "2", "suggested")

        result = self.cache.find_next_sibling(f"{PARENT}_1")

        self.assertEqual(result[2], "")

    def test_next_sibling_carries_an_unrecognised_kind(self) -> None:
        _write_child(self.root, "1", "current")
        _write_child(self.root, "2", "suggested", followup_kind="typo_kind")

        result = self.cache.find_next_sibling(f"{PARENT}_1")

        self.assertEqual(result[2], "typo_kind")

    def test_next_sibling_reads_the_suggested_task_not_the_current_one(self) -> None:
        """Negative control for the tuple slot: the kind must come from the
        sibling that is actually suggested, not from the caller's own task."""
        _write_child(self.root, "1", "current", followup_kind="docs_gap")
        _write_child(self.root, "2", "suggested", followup_kind="review_finding")

        result = self.cache.find_next_sibling(f"{PARENT}_1")

        self.assertEqual(result[2], "review_finding")


if __name__ == "__main__":
    unittest.main()
