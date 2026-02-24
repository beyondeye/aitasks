"""Unit tests for aitask_merge.py auto-merge functions (t228_5).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_aitask_merge.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "aiscripts", "board"))
from aitask_merge import merge_body, merge_frontmatter, parse_conflict_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conflict(local: str, remote: str) -> str:
    """Build a 2-way conflict marker block."""
    return f"<<<<<<< HEAD\n{local}=======\n{remote}>>>>>>> remote\n"


def _conflict_diff3(local: str, base: str, remote: str) -> str:
    """Build a diff3 (3-way) conflict marker block."""
    return (
        f"<<<<<<< HEAD\n{local}"
        f"||||||| base\n{base}"
        f"=======\n{remote}"
        f">>>>>>> remote\n"
    )


# ---------------------------------------------------------------------------
# TestConflictParser
# ---------------------------------------------------------------------------

class TestConflictParser(unittest.TestCase):

    def test_full_file_conflict(self):
        content = _conflict("line A\n", "line B\n")
        result = parse_conflict_file(content)
        self.assertIsNotNone(result)
        local, remote = result
        self.assertIn("line A", local)
        self.assertIn("line B", remote)
        self.assertNotIn("line B", local)
        self.assertNotIn("line A", remote)

    def test_multi_hunk_conflict(self):
        content = (
            "shared header\n"
            + _conflict("local1\n", "remote1\n")
            + "shared middle\n"
            + _conflict("local2\n", "remote2\n")
            + "shared footer\n"
        )
        result = parse_conflict_file(content)
        self.assertIsNotNone(result)
        local, remote = result
        self.assertIn("shared header", local)
        self.assertIn("shared header", remote)
        self.assertIn("shared middle", local)
        self.assertIn("shared middle", remote)
        self.assertIn("shared footer", local)
        self.assertIn("shared footer", remote)
        self.assertIn("local1", local)
        self.assertIn("local2", local)
        self.assertIn("remote1", remote)
        self.assertIn("remote2", remote)
        self.assertNotIn("remote1", local)
        self.assertNotIn("local1", remote)

    def test_diff3_style(self):
        content = _conflict_diff3("local\n", "base\n", "remote\n")
        result = parse_conflict_file(content)
        self.assertIsNotNone(result)
        local, remote = result
        self.assertIn("local", local)
        self.assertIn("remote", remote)
        # Base content should be discarded
        self.assertNotIn("base", local)
        self.assertNotIn("base", remote)

    def test_no_conflict_markers(self):
        content = "---\npriority: high\n---\nBody text\n"
        result = parse_conflict_file(content)
        self.assertIsNone(result)

    def test_shared_lines_preserved(self):
        content = (
            "before\n"
            + _conflict("A\n", "B\n")
            + "after\n"
        )
        result = parse_conflict_file(content)
        self.assertIsNotNone(result)
        local, remote = result
        self.assertTrue(local.startswith("before\n"))
        self.assertTrue(remote.startswith("before\n"))
        self.assertTrue(local.endswith("after\n"))
        self.assertTrue(remote.endswith("after\n"))


# ---------------------------------------------------------------------------
# TestMergeRules
# ---------------------------------------------------------------------------

class TestMergeRules(unittest.TestCase):

    def test_boardcol_keeps_local(self):
        local = {"boardcol": "now", "updated_at": "2026-01-01"}
        remote = {"boardcol": "next", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["boardcol"], "now")
        self.assertNotIn("boardcol", unresolved)

    def test_boardidx_keeps_local(self):
        local = {"boardidx": 10, "updated_at": "2026-01-01"}
        remote = {"boardidx": 50, "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["boardidx"], 10)
        self.assertNotIn("boardidx", unresolved)

    def test_updated_at_keeps_newer(self):
        local = {"updated_at": "2026-02-20 10:00"}
        remote = {"updated_at": "2026-02-24 15:00"}
        merged, _ = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["updated_at"], "2026-02-24 15:00")

    def test_updated_at_keeps_local_when_newer(self):
        local = {"updated_at": "2026-02-24 15:00"}
        remote = {"updated_at": "2026-02-20 10:00"}
        merged, _ = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["updated_at"], "2026-02-24 15:00")

    def test_labels_union(self):
        local = {"labels": ["ui", "backend"], "updated_at": "2026-01-01"}
        remote = {"labels": ["backend", "api"], "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(sorted(merged["labels"]), ["api", "backend", "ui"])
        self.assertNotIn("labels", unresolved)

    def test_depends_union(self):
        local = {"depends": [1, 3], "updated_at": "2026-01-01"}
        remote = {"depends": [2, 3], "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(sorted(merged["depends"]), ["1", "2", "3"])
        self.assertNotIn("depends", unresolved)

    def test_priority_keeps_remote_batch(self):
        local = {"priority": "high", "updated_at": "2026-01-01"}
        remote = {"priority": "low", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["priority"], "low")
        self.assertNotIn("priority", unresolved)

    def test_effort_keeps_remote_batch(self):
        local = {"effort": "low", "updated_at": "2026-01-01"}
        remote = {"effort": "high", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["effort"], "high")
        self.assertNotIn("effort", unresolved)

    def test_status_implementing_wins(self):
        local = {"status": "Ready", "updated_at": "2026-01-01"}
        remote = {"status": "Implementing", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["status"], "Implementing")
        self.assertNotIn("status", unresolved)

    def test_status_implementing_wins_local(self):
        local = {"status": "Implementing", "updated_at": "2026-01-01"}
        remote = {"status": "Ready", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["status"], "Implementing")
        self.assertNotIn("status", unresolved)

    def test_status_both_implementing(self):
        local = {"status": "Implementing", "updated_at": "2026-01-01"}
        remote = {"status": "Implementing", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["status"], "Implementing")
        self.assertNotIn("status", unresolved)

    def test_status_both_non_implementing_unresolved(self):
        local = {"status": "Done", "updated_at": "2026-01-01"}
        remote = {"status": "Postponed", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertIn("status", unresolved)

    def test_field_only_in_local(self):
        local = {"priority": "high", "issue": "https://example.com", "updated_at": "2026-01-01"}
        remote = {"priority": "high", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["issue"], "https://example.com")
        self.assertNotIn("issue", unresolved)

    def test_field_only_in_remote(self):
        local = {"priority": "high", "updated_at": "2026-01-01"}
        remote = {"priority": "high", "assigned_to": "user@example.com", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["assigned_to"], "user@example.com")
        self.assertNotIn("assigned_to", unresolved)

    def test_field_same_both_sides(self):
        local = {"priority": "high", "status": "Ready", "updated_at": "2026-01-01"}
        remote = {"priority": "high", "status": "Ready", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["priority"], "high")
        self.assertEqual(merged["status"], "Ready")
        self.assertEqual(len(unresolved), 0)

    def test_empty_labels_merge(self):
        local = {"labels": [], "updated_at": "2026-01-01"}
        remote = {"labels": ["api", "backend"], "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(sorted(merged["labels"]), ["api", "backend"])
        self.assertNotIn("labels", unresolved)

    def test_all_resolvable_returns_empty_unresolved(self):
        local = {
            "boardcol": "now", "labels": ["ui"], "priority": "high",
            "updated_at": "2026-02-20",
        }
        remote = {
            "boardcol": "next", "labels": ["api"], "priority": "low",
            "updated_at": "2026-02-24",
        }
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(len(unresolved), 0)

    def test_unresolved_uses_local_as_placeholder(self):
        local = {"status": "Done", "updated_at": "2026-01-01"}
        remote = {"status": "Postponed", "updated_at": "2026-01-01"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertIn("status", unresolved)
        # Unresolved fields use local value as placeholder
        self.assertEqual(merged["status"], "Done")


# ---------------------------------------------------------------------------
# TestBodyMerge
# ---------------------------------------------------------------------------

class TestBodyMerge(unittest.TestCase):

    def test_identical_bodies(self):
        body = "## Task Description\n\nSome content here.\n"
        merged, resolved = merge_body(body, body)
        self.assertTrue(resolved)
        self.assertEqual(merged, body)

    def test_different_bodies(self):
        local_body = "## Version A\n\nLocal content.\n"
        remote_body = "## Version B\n\nRemote content.\n"
        merged, resolved = merge_body(local_body, remote_body)
        self.assertFalse(resolved)
        self.assertIn("<<<<<<< LOCAL", merged)
        self.assertIn("=======", merged)
        self.assertIn(">>>>>>> REMOTE", merged)
        self.assertIn("Local content", merged)
        self.assertIn("Remote content", merged)


if __name__ == "__main__":
    unittest.main()
