"""Unit tests for aitask_merge.py auto-merge functions (t228_5).

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_aitask_merge.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "board"))
from aitask_merge import merge_body, merge_frontmatter, parse_conflict_file
from board_groups import normalize_group_slug
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


# ---------------------------------------------------------------------------
# TestActiveGatesTupleMerge (t635_33)
# ---------------------------------------------------------------------------

class TestActiveGatesTupleMerge(unittest.TestCase):
    """The four active_gates* fields move as ONE group: the newer-updated_at
    side's tuple STATE wins wholesale — including absence. Never mixes sides."""

    def _tuple(self, active, filtered, profile, digest):
        return {
            "active_gates": active,
            "active_gates_filtered": filtered,
            "active_gates_profile": profile,
            "active_gates_digest": digest,
        }

    def test_both_present_newer_wins_wholesale(self):
        local = {"updated_at": "2026-07-01 10:00",
                 **self._tuple(["risk_evaluated"], [], "fast", "a.b.c")}
        remote = {"updated_at": "2026-07-02 10:00",
                  **self._tuple([], ["risk_evaluated"], "default", "d.e.f")}
        merged, unresolved = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["active_gates"], [])
        self.assertEqual(merged["active_gates_filtered"], ["risk_evaluated"])
        self.assertEqual(merged["active_gates_profile"], "default")
        self.assertEqual(merged["active_gates_digest"], "d.e.f")
        for f in ("active_gates", "active_gates_filtered",
                  "active_gates_profile", "active_gates_digest"):
            self.assertNotIn(f, unresolved)

    def test_newer_absent_deletes_tuple_local_newer(self):
        # Newer LOCAL legitimately has no tuple; the older remote's snapshot
        # must NOT be resurrected by one-sided preservation.
        local = {"updated_at": "2026-07-02 10:00"}
        remote = {"updated_at": "2026-07-01 10:00",
                  **self._tuple(["risk_evaluated"], [], "fast", "a.b.c")}
        merged, _ = merge_frontmatter(local, remote, batch=True)
        for f in ("active_gates", "active_gates_filtered",
                  "active_gates_profile", "active_gates_digest"):
            self.assertNotIn(f, merged)

    def test_newer_absent_deletes_tuple_remote_newer(self):
        local = {"updated_at": "2026-07-01 10:00",
                 **self._tuple(["risk_evaluated"], [], "fast", "a.b.c")}
        remote = {"updated_at": "2026-07-02 10:00"}
        merged, _ = merge_frontmatter(local, remote, batch=True)
        for f in ("active_gates", "active_gates_filtered",
                  "active_gates_profile", "active_gates_digest"):
            self.assertNotIn(f, merged)

    def test_never_mixes_sides(self):
        # Newer side carries only a PARTIAL tuple (should not happen — CLI
        # enforces atomicity — but merge must still not blend the older side's
        # remaining fields into it).
        local = {"updated_at": "2026-07-02 10:00",
                 "active_gates": ["risk_evaluated"]}
        remote = {"updated_at": "2026-07-01 10:00",
                  **self._tuple([], ["risk_evaluated"], "default", "d.e.f")}
        merged, _ = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged.get("active_gates"), ["risk_evaluated"])
        self.assertNotIn("active_gates_filtered", merged)
        self.assertNotIn("active_gates_profile", merged)
        self.assertNotIn("active_gates_digest", merged)

    def test_empty_tuple_preserved_when_newer(self):
        # An explicit empty active set (fully filtered task) is load-bearing.
        local = {"updated_at": "2026-07-02 10:00",
                 **self._tuple([], ["risk_evaluated"], "default", "d.e.f")}
        remote = {"updated_at": "2026-07-01 10:00"}
        merged, _ = merge_frontmatter(local, remote, batch=True)
        self.assertEqual(merged["active_gates"], [])
        self.assertEqual(merged["active_gates_filtered"], ["risk_evaluated"])


class TestBoardgroupBaseAwareMerge(unittest.TestCase):
    """`boardgroup` is resolved against the MERGE BASE, not presence or time.

    Two generic rules are both wrong for group membership:
      * one-sided presence resolves FIRST and unconditionally, so a side that
        clears the field loses to a side that still carries it — membership
        RESURRECTS on sync;
      * `updated_at` is task-wide and minute-resolution, so an unrelated edit on
        a stale checkout wins a field it never touched.
    """

    def _merge(self, local, remote, base=None):
        return merge_frontmatter(local, remote, batch=True, base_meta=base)

    # --- the resolution table -------------------------------------------
    def test_only_local_changed_local_wins(self):
        merged, unresolved = self._merge(
            {"boardgroup": "perf_work"}, {"boardgroup": "old"},
            base={"boardgroup": "old"})
        self.assertEqual(merged["boardgroup"], "perf_work")
        self.assertNotIn("boardgroup", unresolved)

    def test_only_remote_changed_remote_wins(self):
        merged, unresolved = self._merge(
            {"boardgroup": "old"}, {"boardgroup": "perf_work"},
            base={"boardgroup": "old"})
        self.assertEqual(merged["boardgroup"], "perf_work")
        self.assertNotIn("boardgroup", unresolved)

    def test_both_changed_to_same_value(self):
        merged, unresolved = self._merge(
            {"boardgroup": "same"}, {"boardgroup": "same"},
            base={"boardgroup": "old"})
        self.assertEqual(merged["boardgroup"], "same")
        self.assertNotIn("boardgroup", unresolved)

    def test_both_changed_differently_is_partial(self):
        merged, unresolved = self._merge(
            {"boardgroup": "mine"}, {"boardgroup": "theirs"},
            base={"boardgroup": "old"})
        self.assertIn("boardgroup", unresolved)

    def test_no_base_and_divergent_fails_closed(self):
        merged, unresolved = self._merge(
            {"boardgroup": "mine"}, {"boardgroup": "theirs"}, base=None)
        self.assertIn("boardgroup", unresolved)

    def test_identical_values_need_no_base(self):
        merged, unresolved = self._merge(
            {"boardgroup": "same"}, {"boardgroup": "same"}, base=None)
        self.assertEqual(merged["boardgroup"], "same")
        self.assertNotIn("boardgroup", unresolved)

    def test_absent_on_both_sides_is_not_invented(self):
        merged, unresolved = self._merge({"status": "Ready"},
                                         {"status": "Ready"})
        self.assertNotIn("boardgroup", merged)
        self.assertNotIn("boardgroup", unresolved)

    # --- deletion, the defect one-sided presence caused ------------------
    def test_local_cleared_beats_remote_still_carrying(self):
        """The headline case: a clear must NOT be resurrected."""
        merged, unresolved = self._merge(
            {"boardgroup": ""}, {"boardgroup": "perf_work"},
            base={"boardgroup": "perf_work"})
        self.assertEqual(merged["boardgroup"], "")
        self.assertNotIn("boardgroup", unresolved)

    def test_remote_cleared_beats_local_still_carrying(self):
        merged, unresolved = self._merge(
            {"boardgroup": "perf_work"}, {"boardgroup": ""},
            base={"boardgroup": "perf_work"})
        self.assertEqual(merged["boardgroup"], "")
        self.assertNotIn("boardgroup", unresolved)

    def test_unrelated_edit_does_not_win_the_field(self):
        """A `status`-only edit must not decide membership.

        Machine A cleared the group; machine B edited only `status` while still
        carrying the old value and has the NEWER timestamp. Newer-wins would
        hand B a field it never touched.
        """
        merged, unresolved = self._merge(
            {"boardgroup": "", "status": "Ready",
             "updated_at": "2026-01-01 10:00"},
            {"boardgroup": "perf_work", "status": "Editing",
             "updated_at": "2026-01-01 12:00"},
            base={"boardgroup": "perf_work", "status": "Ready",
                  "updated_at": "2026-01-01 09:00"})
        self.assertEqual(merged["boardgroup"], "")
        self.assertNotIn("boardgroup", unresolved)

    # --- canonicalisation: absent / None / "" all mean ungrouped ---------
    def test_absent_and_tombstone_are_not_a_change(self):
        """Deleting the key and writing "" are the same intent.

        Comparing raw would call this two different changes and fail closed for
        no reason.
        """
        merged, unresolved = self._merge(
            {},                                  # local deleted the key
            {"boardgroup": ""},                  # remote wrote the tombstone
            base={"boardgroup": ""})
        self.assertNotIn("boardgroup", unresolved)

    def test_yaml_null_reads_as_ungrouped(self):
        merged, unresolved = self._merge(
            {"boardgroup": None}, {"boardgroup": ""},
            base={"boardgroup": ""})
        self.assertNotIn("boardgroup", unresolved)

    def test_whitespace_bearing_value_is_a_real_change(self):
        """A quoted `"perf_work "` edit must NOT read as unchanged from base.

        If the boundary stripped, local would compare equal to the base and the
        user's edit would be silently discarded in favour of the other side.
        """
        merged, unresolved = self._merge(
            {"boardgroup": "perf_work "},          # local hand-edited a space in
            {"boardgroup": "perf_work"},           # remote untouched
            base={"boardgroup": "perf_work"})
        self.assertEqual(merged["boardgroup"], "perf_work ")
        self.assertNotIn("boardgroup", unresolved)

    def test_whitespace_only_value_reads_as_ungrouped(self):
        merged, unresolved = self._merge(
            {"boardgroup": "   "}, {"boardgroup": ""},
            base={"boardgroup": ""})
        self.assertNotIn("boardgroup", unresolved)

    def test_malformed_value_does_not_raise(self):
        merged, unresolved = self._merge(
            {"boardgroup": []}, {"boardgroup": "perf_work"},
            base={"boardgroup": "perf_work"})
        self.assertNotIn("boardgroup", unresolved)

    # --- it must NOT inherit the layout rule ----------------------------
    def test_boardgroup_is_not_keep_local(self):
        import aitask_merge
        self.assertNotIn("boardgroup", aitask_merge._KEEP_LOCAL_FIELDS)

    def test_one_sided_presence_branch_cannot_see_it(self):
        """Pre-loop resolution is what makes deletion decidable at all.

        Without base_meta the divergence fails closed; the generic one-sided
        rule would instead have silently taken the surviving side.
        """
        merged, unresolved = self._merge({}, {"boardgroup": "perf_work"},
                                         base={"boardgroup": "perf_work"})
        # Remote is unchanged from base, local cleared it -> local wins.
        self.assertEqual(normalize_group_slug(merged.get("boardgroup")), "")


class TestMergeBaselineCharacterization(unittest.TestCase):
    """Characterization of every resolution rule t1243_8 does NOT change.

    t1243_8 adds a fourth `base_meta` parameter to `merge_frontmatter` and a
    pre-loop block for `_BASE_AWARE_FIELDS`. Both edits sit in the single
    function where every checkout's task data converges, so a regression here
    silently loses another machine's edit rather than failing loudly.

    This table is the regression net, and it is deliberately written and run
    green against the PRE-CHANGE function first — a characterization test that
    has never passed against the old code characterizes nothing. Every case
    below therefore uses the three-argument call that exists today.

    `boardgroup` is intentionally ABSENT from this table: it is the field the
    task changes, so pinning today's (generic-fallback) behaviour for it would
    encode the bug being fixed.
    """

    # (name, local, remote, expected_key, expected_value, expect_unresolved)
    CASES = [
        ("boardcol_local_wins",
         {"boardcol": "now"}, {"boardcol": "next"}, "boardcol", "now", False),
        ("boardidx_local_wins",
         {"boardidx": 10}, {"boardidx": 50}, "boardidx", 10, False),
        ("updated_at_newer_wins",
         {"updated_at": "2026-02-20 10:00"}, {"updated_at": "2026-02-24 15:00"},
         "updated_at", "2026-02-24 15:00", False),
        ("anchor_newer_wins",
         {"anchor": "42", "updated_at": "2026-02-20 10:00"},
         {"anchor": "99", "updated_at": "2026-02-24 15:00"},
         "anchor", "99", False),
        ("labels_union_sorted",
         {"labels": ["ui", "backend"]}, {"labels": ["backend", "api"]},
         "labels", ["api", "backend", "ui"], False),
        ("depends_union_sorted",
         {"depends": ["2"]}, {"depends": ["1"]}, "depends", ["1", "2"], False),
        ("priority_remote_wins_in_batch",
         {"priority": "high"}, {"priority": "low"}, "priority", "low", False),
        ("effort_remote_wins_in_batch",
         {"effort": "low"}, {"effort": "high"}, "effort", "high", False),
        ("status_implementing_wins",
         {"status": "Ready"}, {"status": "Implementing"},
         "status", "Implementing", False),
        ("status_both_other_unresolved",
         {"status": "Ready"}, {"status": "Editing"}, "status", "Ready", True),
        ("one_sided_local_included",
         {"issue_type": "bug"}, {}, "issue_type", "bug", False),
        ("one_sided_remote_included",
         {}, {"issue_type": "bug"}, "issue_type", "bug", False),
        ("same_value_kept",
         {"priority": "high"}, {"priority": "high"}, "priority", "high", False),
        ("unknown_scalar_divergence_unresolved",
         {"custom": "a"}, {"custom": "b"}, "custom", "a", True),
    ]

    def test_baseline_resolution_table(self):
        for name, local, remote, key, expected, expect_unresolved in self.CASES:
            with self.subTest(case=name):
                merged, unresolved = merge_frontmatter(
                    dict(local), dict(remote), batch=True)
                got = merged.get(key)
                if isinstance(expected, list):
                    self.assertEqual(sorted(got), expected)
                else:
                    self.assertEqual(got, expected)
                if expect_unresolved:
                    self.assertIn(key, unresolved)
                else:
                    self.assertNotIn(key, unresolved)

    def test_one_sided_presence_resurrects_a_deleted_field(self):
        """The defect `boardgroup` must escape — pinned so the escape is visible.

        A side that clears a field by OMITTING the key loses to a side that
        still carries it, unconditionally and ahead of every field rule. This is
        correct-by-design for ordinary fields and is exactly why membership
        needs base-aware resolution instead.
        """
        merged, unresolved = merge_frontmatter(
            {"labels": ["ui"]},                      # local dropped `anchor`
            {"labels": ["ui"], "anchor": "42"},      # remote still carries it
            batch=True)
        self.assertEqual(merged["anchor"], "42")
        self.assertNotIn("anchor", unresolved)


if __name__ == "__main__":
    unittest.main()
