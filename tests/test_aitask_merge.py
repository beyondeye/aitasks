"""Unit tests for aitask_merge.py auto-merge functions (t228_5).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_aitask_merge.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "board"))
from aitask_merge import merge_body, merge_frontmatter, parse_conflict_file
# Importing aitask_merge above also inserts ../lib on sys.path, so gate_ledger
# (the canonical ledger parser/builder used to construct realistic fixtures) is
# now importable.
import gate_ledger


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

    def test_anchor_keeps_newer(self):
        # Scalar anchor (t1016): newer side wins, like updated_at, and the field
        # is NOT dropped into the unresolved/PARTIAL path on sync.
        local = {"anchor": "42", "updated_at": "2026-02-20 10:00"}
        remote = {"anchor": "99", "updated_at": "2026-02-24 15:00"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["anchor"], "99")
        self.assertNotIn("anchor", unresolved)

    def test_anchor_keeps_local_when_newer(self):
        local = {"anchor": "42", "updated_at": "2026-02-24 15:00"}
        remote = {"anchor": "99", "updated_at": "2026-02-20 10:00"}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["anchor"], "42")
        self.assertNotIn("anchor", unresolved)

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


# ---------------------------------------------------------------------------
# TestGateRunsUnion (t635_21) — concurrent '## Gate Runs' append auto-merge
# ---------------------------------------------------------------------------

_HEAD = "## Task Description\n\nSome content.\n"
_SEC_PREAMBLE = (
    f"\n\n{gate_ledger.SECTION_HEADER}\n{gate_ledger.SECTION_COMMENT}\n\n"
)


def _blk(gate, status, run, **fields):
    """Build a gate-run block via the REAL builder (proves we union real output)."""
    f = {"run": run}
    f.update(fields)
    return gate_ledger.build_block("", gate, status, f)


def _body(head, *blocks):
    """Assemble a task body: head + '## Gate Runs' section with given blocks.

    Pass no blocks to get a head-only body (no ledger section).
    """
    if not blocks:
        return head
    return head + _SEC_PREAMBLE + "\n\n".join(blocks) + "\n"


class TestGateRunsUnion(unittest.TestCase):

    def test_distinct_appends_both_survive(self):
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        b = _blk("lint", "pass", "2026-06-30T10:05:00Z")          # local-only
        c = _blk("docs_updated", "pass", "2026-06-30T10:06:00Z")  # remote-only
        merged, resolved = merge_body(_body(_HEAD, a, b), _body(_HEAD, a, c))
        self.assertTrue(resolved)
        self.assertNotIn("<<<<<<<", merged)
        for g in ("tests_pass", "lint", "docs_updated"):
            self.assertIn(f"gate:{g}", merged)

    def test_ordering_deterministic(self):
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        b = _blk("lint", "pass", "2026-06-30T10:05:00Z")
        c = _blk("docs_updated", "pass", "2026-06-30T10:06:00Z")
        left = _body(_HEAD, a, b)
        right = _body(_HEAD, a, c)
        self.assertEqual(merge_body(left, right)[0], merge_body(right, left)[0])

    def test_shared_block_deduped(self):
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        b = _blk("lint", "pass", "2026-06-30T10:05:00Z")
        merged, _ = merge_body(_body(_HEAD, a, b), _body(_HEAD, a))
        self.assertEqual(merged.count("run=2026-06-30T10:00:00Z"), 1)

    def test_derivation_last_run_wins(self):
        old = _blk("tests_pass", "fail", "2026-06-30T10:00:00Z", attempt="1")
        new = _blk("tests_pass", "pass", "2026-06-30T10:10:00Z", attempt="2")
        merged, resolved = merge_body(_body(_HEAD, old), _body(_HEAD, new))
        self.assertTrue(resolved)
        self.assertEqual(gate_ledger.derive_gate_runs(merged)["tests_pass"].status, "pass")

    def test_cross_side_same_gate_orders_by_timestamp(self):
        # Local newer than remote for the SAME gate → local must win (chronological,
        # not side-order). Catches an append-at-end ordering bug.
        local_new = _blk("g", "pass", "2026-06-30T11:00:00Z", attempt="1")
        remote_old = _blk("g", "fail", "2026-06-30T10:00:00Z", attempt="1")
        merged, resolved = merge_body(_body(_HEAD, local_new), _body(_HEAD, remote_old))
        self.assertTrue(resolved)
        self.assertEqual(gate_ledger.derive_gate_runs(merged)["g"].status, "pass")

    def test_same_run_different_attempt_both_kept(self):
        # Same gate + same run second, different attempt: legitimate, both kept.
        a1 = _blk("g", "fail", "2026-06-30T10:00:00Z", attempt="1")
        a2 = _blk("g", "pass", "2026-06-30T10:00:00Z", attempt="2")
        merged, resolved = merge_body(_body(_HEAD, a1), _body(_HEAD, a2))
        self.assertTrue(resolved)
        self.assertIn("attempt=1", merged)
        self.assertIn("attempt=2", merged)
        self.assertEqual(gate_ledger.derive_gate_runs(merged)["g"].status, "pass")

    def test_attempt_sorted_numerically(self):
        # attempt 2 vs 10 at the same run second: 10 must sort AFTER 2 → 10 current.
        a2 = _blk("g", "fail", "2026-06-30T10:00:00Z", attempt="2")
        a10 = _blk("g", "pass", "2026-06-30T10:00:00Z", attempt="10")
        merged, resolved = merge_body(_body(_HEAD, a2), _body(_HEAD, a10))
        self.assertTrue(resolved)
        self.assertEqual(gate_ledger.derive_gate_runs(merged)["g"].attempt, "10")

    def test_divergent_same_identity_falls_back(self):
        # Same (name, run, attempt) but different status → contract violation → conflict.
        x1 = _blk("g", "pass", "2026-06-30T10:00:00Z", attempt="1")
        x2 = _blk("g", "fail", "2026-06-30T10:00:00Z", attempt="1")
        merged, resolved = merge_body(_body(_HEAD, x1), _body(_HEAD, x2))
        self.assertFalse(resolved)
        self.assertIn("<<<<<<<", merged)
        self.assertIn("status=pass", merged)
        self.assertIn("status=fail", merged)

    def test_non_iso_run_falls_back_to_conflict(self):
        bad = _blk("weird", "pass", "garbage")
        good = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        merged, resolved = merge_body(_body(_HEAD, good), _body(_HEAD, bad))
        self.assertFalse(resolved)
        self.assertIn("<<<<<<<", merged)

    def test_missing_run_falls_back_to_conflict(self):
        good = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        # A marker block with no run= field at all.
        no_run = "> **✅ gate:weird** status=pass attempt=1"
        merged, resolved = merge_body(_body(_HEAD, good), _body(_HEAD, no_run))
        self.assertFalse(resolved)
        self.assertIn("<<<<<<<", merged)

    def test_trailing_prose_falls_back_and_preserves_text(self):
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        local = _body(_HEAD, a) + "\nA stray human note under the ledger.\n"
        remote = _body(_HEAD, a) + "\nA different stray note.\n"
        merged, resolved = merge_body(local, remote)
        self.assertFalse(resolved)
        self.assertIn("stray human note", merged)
        self.assertIn("different stray note", merged)

    def test_clean_section_normalized(self):
        # Odd inter-block spacing + a legacy comment normalize to canonical form.
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        b = _blk("lint", "pass", "2026-06-30T10:05:00Z")
        messy_head = _HEAD + "\n\n## Gate Runs\n<!-- legacy comment -->\n\n\n" + a + "\n"
        clean = _body(_HEAD, a, b)
        merged, resolved = merge_body(messy_head, clean)
        self.assertTrue(resolved)
        self.assertIn(gate_ledger.SECTION_COMMENT, merged)
        self.assertNotIn("legacy comment", merged)
        # canonical: one blank line between blocks, single canonical preamble.
        self.assertEqual(merged.count(gate_ledger.SECTION_HEADER), 1)

    def test_one_side_no_section(self):
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        merged, resolved = merge_body(_body(_HEAD, a), _body(_HEAD))  # remote has no ledger
        self.assertTrue(resolved)
        self.assertIn("gate:tests_pass", merged)

    def test_prose_conflict_with_clean_ledger(self):
        a = _blk("tests_pass", "pass", "2026-06-30T10:00:00Z")
        b = _blk("lint", "pass", "2026-06-30T10:05:00Z")
        local = _body("## A\n\nLocal prose.\n", a, b)
        remote = _body("## B\n\nRemote prose.\n", a)
        merged, resolved = merge_body(local, remote)
        self.assertFalse(resolved)            # prose head still conflicts
        self.assertIn("<<<<<<<", merged)
        self.assertIn("gate:lint", merged)    # ledger still unioned
        self.assertEqual(merged.count("run=2026-06-30T10:00:00Z"), 1)  # deduped


if __name__ == "__main__":
    unittest.main()
