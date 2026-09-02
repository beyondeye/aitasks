#!/usr/bin/env python3
"""Tests for lib/trail_discovery.py — the trail discovery seams promoted out of
the board in t1647_1.

Imports the lib module DIRECTLY: no board, no Textual. That is the point of the
promotion — the t1647_3 preflight helper and the /aitask-merge-trails skill
consume these seams without a TUI.

Covers: owner-rank dedup precedence, overlap computation, entry-ref extraction,
frontmatter-driven discovery against synthetic trees (including both malformed
shapes the `unreadable` report exists for), the fail-closed load_trail_blob
contract, and the per-call task-dir resolution that keeps the single-process
suite from leaking one fixture tree into the next.

Run: python3 -m unittest tests.test_trail_discovery -v
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

import trail_discovery as td  # noqa: E402


def _info(handle, owner_id="1", archived=False, folded=False, doc=None):
    return td.TrailInfo(handle=handle, owner_id=owner_id,
                        owner_archived=archived, owner_folded=folded, doc=doc)


def _doc(*refs, title="A trail"):
    return {"title": title,
            "waves": [{"entries": [{"task": r} for r in refs]}]}


def _task_file(directory: Path, name: str, handles=(), status="Ready",
               folded_into=None, kind="implementation_trail"):
    """Write a task file whose frontmatter carries `artifacts:` trail entries."""
    directory.mkdir(parents=True, exist_ok=True)
    arts = ", ".join(
        "{handle: '%s', kind: %s, name: T}" % (h, kind) for h in handles)
    extra = f"folded_into: {folded_into}\n" if folded_into else ""
    (directory / name).write_text(
        "---\n"
        "priority: medium\neffort: low\nissue_type: chore\n"
        f"status: {status}\n{extra}"
        + (f"artifacts: [{arts}]\n" if handles else "")
        + "---\n\nbody\n",
        encoding="utf-8")


class OwnerRankTests(unittest.TestCase):
    """Dedup precedence: active non-folded > active folded > archived;
    ties broken by lowest owner id."""

    def test_active_beats_folded_beats_archived(self):
        active = _info("art:t", owner_id="5")
        folded = _info("art:t", owner_id="5", folded=True)
        archived = _info("art:t", owner_id="5", archived=True)
        self.assertLess(td._trail_owner_rank(active), td._trail_owner_rank(folded))
        self.assertLess(td._trail_owner_rank(folded), td._trail_owner_rank(archived))

    def test_tie_breaks_on_lowest_id_numerically(self):
        """'10' must not sort before '9' — the key is numeric, not lexical."""
        low = _info("art:t", owner_id="9")
        high = _info("art:t", owner_id="10")
        self.assertLess(td._trail_owner_rank(low), td._trail_owner_rank(high))

    def test_dedupe_keeps_the_winner_and_preserves_first_seen_order(self):
        recs = [_info("art:b", owner_id="2", archived=True),
                _info("art:a", owner_id="7"),
                _info("art:b", owner_id="3")]          # active beats archived
        out = td.dedupe_trail_records(recs)
        self.assertEqual([i.handle for i in out], ["art:b", "art:a"])
        winner = next(i for i in out if i.handle == "art:b")
        self.assertEqual(winner.owner_id, "3")
        self.assertFalse(winner.owner_archived)


class EntryRefAndOverlapTests(unittest.TestCase):

    def test_trail_entry_refs_collects_every_wave_entry(self):
        doc = {"waves": [{"entries": [{"task": "aitasks#1"}, {"task": "aitasks#2"}]},
                         {"entries": [{"task": "aitasks#3"}]}]}
        self.assertEqual(td.trail_entry_refs(doc),
                         {"aitasks#1", "aitasks#2", "aitasks#3"})

    def test_trail_entry_refs_tolerates_missing_structure(self):
        self.assertEqual(td.trail_entry_refs({}), set())
        self.assertEqual(td.trail_entry_refs({"waves": [{}]}), set())
        self.assertEqual(td.trail_entry_refs({"waves": [{"entries": [{}]}]}), set())

    def test_overlaps_report_only_shared_refs(self):
        a = _info("art:a", doc=_doc("aitasks#1", "aitasks#2", title="Alpha"))
        b = _info("art:b", doc=_doc("aitasks#2", "aitasks#3", title="Beta"))
        overlaps = td.compute_trail_overlaps([a, b])
        self.assertEqual(overlaps["art:a"], [("aitasks#2", "Beta")])
        self.assertEqual(overlaps["art:b"], [("aitasks#2", "Alpha")])

    def test_fully_divergent_membership_yields_no_notes(self):
        a = _info("art:a", doc=_doc("aitasks#1", title="Alpha"))
        b = _info("art:b", doc=_doc("aitasks#9", title="Beta"))
        overlaps = td.compute_trail_overlaps([a, b])
        self.assertEqual(overlaps["art:a"], [])
        self.assertEqual(overlaps["art:b"], [])

    def test_trails_that_failed_to_load_are_skipped(self):
        loaded = _info("art:a", doc=_doc("aitasks#1"))
        broken = _info("art:b", doc=None)
        overlaps = td.compute_trail_overlaps([loaded, broken])
        self.assertNotIn("art:b", overlaps)
        self.assertEqual(overlaps["art:a"], [])


class _TreeTestCase(unittest.TestCase):
    """Base: a synthetic project tree that is cwd for the duration of a test."""

    def _tree(self):
        tmp = tempfile.TemporaryDirectory(prefix="trail_discovery_")
        self.addCleanup(tmp.cleanup)
        tree = Path(tmp.name)
        (tree / "aitasks" / "archived").mkdir(parents=True)
        return tree

    def _chdir(self, tree):
        original = os.getcwd()
        os.chdir(tree)
        self.addCleanup(os.chdir, original)


class DiscoveryTests(_TreeTestCase):
    """Frontmatter-driven discovery, read from disk (RFC par.5, t1365)."""

    def setUp(self):
        self.tree = self._tree()
        self._chdir(self.tree)
        self.tasks = self.tree / "aitasks"
        # load_trail_blob is stubbed on THIS module: discover_trails calls it
        # through trail_discovery's own namespace.
        p = patch.object(td, "load_trail_blob",
                         lambda h: ({"trail_id": h}, "", []))
        p.start()
        self.addCleanup(p.stop)

    def test_discovers_active_and_archived_owners(self):
        _task_file(self.tasks, "t10_alpha.md", handles=["art:trail-a"])
        _task_file(self.tasks / "archived", "t11_beta.md", handles=["art:trail-b"])
        infos, unreadable = td.discover_trails()
        by_handle = {i.handle: i for i in infos}
        self.assertEqual(set(by_handle), {"art:trail-a", "art:trail-b"})
        self.assertFalse(by_handle["art:trail-a"].owner_archived)
        self.assertTrue(by_handle["art:trail-b"].owner_archived)
        self.assertEqual(unreadable, [])

    def test_child_tasks_are_scanned(self):
        _task_file(self.tasks / "t20", "t20_3_child.md", handles=["art:trail-c"])
        infos, _ = td.discover_trails()
        self.assertEqual([i.handle for i in infos], ["art:trail-c"])
        self.assertEqual(infos[0].owner_id, "20_3")

    def test_one_handle_on_two_owners_dedupes_to_the_active_one(self):
        _task_file(self.tasks, "t30_live.md", handles=["art:dup"])
        _task_file(self.tasks / "archived", "t31_old.md", handles=["art:dup"])
        infos, _ = td.discover_trails()
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].owner_id, "30")
        self.assertFalse(infos[0].owner_archived)

    def test_folded_owner_loses_to_an_active_one(self):
        _task_file(self.tasks, "t40_primary.md", handles=["art:dup"])
        _task_file(self.tasks, "t41_folded.md", handles=["art:dup"],
                   status="Folded", folded_into=40)
        infos, _ = td.discover_trails()
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].owner_id, "40")

    def test_non_trail_artifacts_are_ignored(self):
        """Discovery is kind-filtered — the manifest stores no kind (RFC par.5)."""
        _task_file(self.tasks, "t50_other.md", handles=["art:report"],
                   kind="work_report")
        infos, unreadable = td.discover_trails()
        self.assertEqual(infos, [])
        self.assertEqual(unreadable, [])

    def test_malformed_yaml_is_reported_not_raised(self):
        """parse_frontmatter RAISES on malformed YAML; the scan must survive."""
        _task_file(self.tasks, "t60_good.md", handles=["art:trail-ok"])
        (self.tasks / "t61_broken.md").write_text(
            "---\npriority: [unclosed\n---\n\nbody\n", encoding="utf-8")
        infos, unreadable = td.discover_trails()
        self.assertEqual([i.handle for i in infos], ["art:trail-ok"])
        self.assertEqual(unreadable, ["t61_broken.md"])

    def test_truncated_file_parsing_to_none_is_also_reported(self):
        """The other failure shape: no mapping at all, no exception."""
        _task_file(self.tasks, "t70_good.md", handles=["art:trail-ok"])
        (self.tasks / "t71_empty.md").write_text("", encoding="utf-8")
        infos, unreadable = td.discover_trails()
        self.assertEqual([i.handle for i in infos], ["art:trail-ok"])
        self.assertEqual(unreadable, ["t71_empty.md"])

    def test_unreadable_names_only_task_named_files(self):
        """A non-task .md under the task dir is a document, not a torn read."""
        (self.tasks / "README.md").write_text("not a task\n", encoding="utf-8")
        infos, unreadable = td.discover_trails()
        self.assertEqual(infos, [])
        self.assertEqual(unreadable, [],
                         "a non-task document was reported as unreadable")

    def test_empty_tree_reports_no_trails_and_no_failures(self):
        """"No trails" and "the scan broke" must not look alike (t1365)."""
        infos, unreadable = td.discover_trails()
        self.assertEqual(infos, [])
        self.assertEqual(unreadable, [])


class TaskDirResolutionTests(_TreeTestCase):
    """The task dir is resolved PER CALL, never cached at import (t1647_1).

    The board binds `TASKS_DIR = task_dir()` at module load and the test fixture
    gives it a fresh module per synthetic tree, so the constant is re-resolved
    each time. This module has no such luxury: it is imported ONCE for the whole
    single-process suite. The value it would freeze is not constant across that
    suite — `TASK_DIR` is genuinely varied, to **absolute** temp-tree paths, by
    several board test modules (test_board_archived_relation_lookup,
    test_board_refresh_degrade, test_board_decref_doomed_attachments,
    test_board_columns_seam, test_board_movement). A cached constant would
    therefore pin discovery to one module's temp tree — long deleted by the time
    a later test scans it.

    Both tests below are negative controls: each fails against a value captured
    once and passes against the per-call resolver. Note that varying **cwd**
    alone would NOT discriminate — the default value is the relative
    `Path("aitasks")`, which keeps working after a chdir — so the discriminating
    axis has to be the `TASK_DIR` value itself, which is also the axis the real
    suite varies.
    """

    def test_two_trees_in_one_process_each_see_their_own_tasks(self):
        stub = patch.object(td, "load_trail_blob",
                            lambda h: ({"trail_id": h}, "", []))
        stub.start()
        self.addCleanup(stub.stop)

        seen = []
        for handle in ("art:first-tree", "art:second-tree"):
            tree = self._tree()
            _task_file(tree / "aitasks", "t80_owner.md", handles=[handle])
            # Absolute TASK_DIR per tree — the shape five real board test
            # modules use, and the one a frozen constant gets wrong.
            with patch.dict(os.environ, {"TASK_DIR": str(tree / "aitasks")}):
                infos, _ = td.discover_trails()
            seen.append([i.handle for i in infos])

        self.assertEqual(seen, [["art:first-tree"], ["art:second-tree"]],
                         "discovery did not follow TASK_DIR — the task dir was "
                         "resolved once and cached")

    def test_task_dir_env_override_is_honoured_per_call(self):
        tree = self._tree()
        (tree / "custom_tasks").mkdir()
        self._chdir(tree)
        self.assertEqual(str(td._tasks_dir()), "aitasks")
        with patch.dict(os.environ, {"TASK_DIR": "custom_tasks"}):
            self.assertEqual(str(td._tasks_dir()), "custom_tasks")
        self.assertEqual(str(td._tasks_dir()), "aitasks")


class LoadTrailBlobTests(unittest.TestCase):
    """Fail-closed contract (RFC par.12): never a partial document."""

    def test_get_failure_yields_no_doc_an_error_and_the_versions_fallback(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if "versions" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="v1\nv2\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no such handle\n")

        with patch("subprocess.run", side_effect=fake_run):
            doc, error, versions = td.load_trail_blob("art:missing")

        self.assertIsNone(doc)
        self.assertTrue(error, "a failed get must report a non-empty error")
        self.assertIn("artifact unresolved", error)
        self.assertEqual(versions, ["v1", "v2"],
                         "the versions fallback was not attempted")
        self.assertTrue(any("versions" in c for c in calls))

    def test_missing_binary_is_an_error_not_a_raise(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("gone")):
            doc, error, versions = td.load_trail_blob("art:any")
        self.assertIsNone(doc)
        self.assertIn("artifact unresolved", error)
        self.assertEqual(versions, [])

    def test_schema_invalid_document_is_rejected_whole(self):
        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        # The real exception carrying the real issue type, so a change to
        # either signature fails here rather than passing against a replica.
        boom = td.trail_schema.TrailValidationError([
            td.trail_schema.TrailIssue("waves[0]", "required", "missing entries"),
            td.trail_schema.TrailIssue("title", "type", "expected string"),
        ])

        with patch("subprocess.run", side_effect=fake_run), \
                patch.object(td.trail_schema, "load_trail", side_effect=boom):
            doc, error, versions = td.load_trail_blob("art:invalid")

        self.assertIsNone(doc, "an invalid document must not be returned")
        self.assertEqual(error, "invalid trail document: 2 issue(s)")

    def test_success_returns_the_document_with_no_error(self):
        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=fake_run), \
                patch.object(td.trail_schema, "load_trail",
                             return_value={"trail_id": "art:ok"}):
            doc, error, versions = td.load_trail_blob("art:ok")

        self.assertEqual(doc, {"trail_id": "art:ok"})
        self.assertEqual(error, "")
        self.assertEqual(versions, [],
                         "versions must only be read on the error path")

    def test_only_read_verbs_are_ever_spawned(self):
        """Read-only guarantee: no write verb may reach a subprocess."""
        spawned = []

        def fake_run(cmd, **kw):
            spawned.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="x\n")

        with patch("subprocess.run", side_effect=fake_run):
            td.load_trail_blob("art:any")
            td._trail_versions("art:any")

        verbs = {c[1] for c in spawned if len(c) > 1}
        self.assertTrue(verbs <= {"get", "versions"},
                        f"a non-read verb was spawned: {verbs}")


class ReExportContractTests(unittest.TestCase):
    """The board must keep re-exporting these names (tests read them as ab.<n>)."""

    def test_module_exposes_every_promoted_symbol(self):
        for name in ("TRAIL_ARTIFACT_KIND", "ARTIFACT_SCRIPT", "TrailInfo",
                     "trail_entry_refs", "compute_trail_overlaps",
                     "_trail_owner_rank", "dedupe_trail_records",
                     "_iter_active_task_frontmatter",
                     "_iter_trail_frontmatter_records", "_trail_versions",
                     "load_trail_blob", "discover_trails"):
            self.assertTrue(hasattr(td, name), f"{name} missing from lib module")

    def test_no_module_level_task_dir_constant(self):
        """A cached constant is the bug TaskDirResolutionTests guards against."""
        self.assertFalse(hasattr(td, "TASKS_DIR"),
                         "TASKS_DIR was re-introduced as a module constant")


if __name__ == "__main__":
    unittest.main(verbosity=2)
