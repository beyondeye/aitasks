"""Tests for lib/obsolescence_evidence.py (t1981_6, task_relations.md D9).

Scratch repos only (legacy mode: task data on the code branch). Path history is
exercised both on real git history and on synthetic event lists (the lifetime
fixtures), origins on archived / folded / deleted / reverted tasks, relation rows
on records written into a local-only store, and the premise row through the
AIT_OBSOLESCENCE_PREMISE_CMD seam.

Run: python3 tests/test_obsolescence_evidence.py
"""
from __future__ import annotations

import datetime as dt
import os
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(ROOT / ".aitask-scripts" / "lib"))

import obsolescence_evidence as oe  # noqa: E402
import relations_schema as rs  # noqa: E402
import relations_store as rst  # noqa: E402
import test_relations_store as ts  # noqa: E402

C_TASK = "2026-11-01 10:00"
EMPTY_DIGEST = oe.digest([])
NOW = dt.datetime(2026, 11, 8, 12, 0, tzinfo=dt.timezone.utc)


def git(cwd, *args):
    return ts.git(cwd, *args)


def commit(root, msg, files=None, moves=(), removes=()):
    for path, text in (files or {}).items():
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git(root, "add", "--", path)
    for src, dst in moves:
        (root / dst).parent.mkdir(parents=True, exist_ok=True)
        git(root, "mv", src, dst)
    for path in removes:
        git(root, "rm", "-q", path)
    git(root, "commit", "-q", "--allow-empty", "-m", msg)


def write_task(root, tid, body, archived=False, status="Ready", extra=()):
    fm = [f"status: {status}", f"created_at: {C_TASK}", f"updated_at: {C_TASK}", *extra]
    path = root / ts.task_relpath(tid, archived)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body, encoding="utf-8")
    return path


def premise_stub(tmp, decision="SKIP", display="skipped", rc=0):
    path = Path(tmp) / f"premise_{decision}_{rc}.sh"
    path.write_text(f"#!/usr/bin/env bash\necho 'BASELINE:NONE'\necho 'DISPLAY:{display}'\n"
                    f"echo 'DECISION:{decision}'\nexit {rc}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


class EBase(ts.Base):
    def setUp(self):
        super().setUp()
        self.root = self.env.clone("repo", remote=False)
        ts.set_config(self.root, relations_enabled=False)
        commit(self.root, "init")
        self._prem = mock.patch.dict(os.environ, {
            "AIT_OBSOLESCENCE_PREMISE_CMD": premise_stub(self.tmp)})
        self._prem.start()

    def tearDown(self):
        self._prem.stop()
        super().tearDown()

    def collect(self, tid, plan=None):
        store = rst.Store(str(self.root))
        snap = store.read(no_fetch=True)
        text = store.index.lookup(tid).text
        return oe.collect(str(self.root), store, snap, tid, text, plan, now=NOW)

    def kinds(self, ev):
        return sorted((r.kind, r.signal) for r in ev.rows if r.kind not in ("age", "premise"))


# ================================================================== paths

class PathRowTests(EBase):
    def test_deleted_renamed_relative_planned_and_data_paths(self):
        commit(self.root, "code", {"src/a/one.py": "1", "src/a/two.py": "2", "src/r1/old.py": "o",
                                   "lib/m/rel.py": "r"})
        commit(self.root, "hop1", moves=[("src/r1/old.py", "src/r2/mid.py")])
        commit(self.root, "hop2", moves=[("src/r2/mid.py", "src/r3/new.py")])
        commit(self.root, "rm", removes=["src/a/two.py"])
        write_task(self.root, "10", "Cites `src/a/one.py`, `src/a/two.py`, `src/r1/old.py`, "
                   "`m/rel.py`, `src/new/planned.py` and `aitasks/t1_x.md`.\n")
        ev = self.collect("10")
        rows = {r.kind: r for r in ev.rows}
        self.assertEqual(self.kinds(ev), [("path_deleted", False), ("path_renamed", False)])
        self.assertIn("src/a/two.py deleted in", rows["path_deleted"].detail)
        self.assertIn("src/r1/old.py -> src/r2/mid.py -> src/r3/new.py", rows["path_renamed"].detail)
        self.assertIn("lifetimes=1", rows["path_renamed"].detail)
        self.assertEqual(ev.signal_count, 0)
        self.assertEqual(ev.digest, EMPTY_DIGEST)
        self.assertEqual(ev.incomplete, [])

    def test_unique_suffix_of_a_removed_path_and_ambiguous_suffix(self):
        commit(self.root, "code", {"x/a/f.py": "1", "y/a/f.py": "2", "z/q/g.py": "3"})
        commit(self.root, "rm", removes=["x/a/f.py", "y/a/f.py", "z/q/g.py"])
        write_task(self.root, "10", "Cites `a/f.py` and `q/g.py`.\n")
        ev = self.collect("10")
        details = {r.kind: r.detail for r in ev.rows}
        self.assertIn("suffix of several removed paths", details["path_ambiguous"])
        self.assertIn("q/g.py (= z/q/g.py deleted in", details["path_deleted"])

    def test_history_cache_is_keyed_per_head(self):
        commit(self.root, "code", {"src/a/two.py": "2"})
        commit(self.root, "rm", removes=["src/a/two.py"])
        calls = []
        real = oe._git

        def counting(root, *args, **kw):
            calls.append(args[0])
            return real(root, *args, **kw)
        with mock.patch.object(oe, "_git", counting):
            oe.load_history(str(self.root))
            oe.load_history(str(self.root))
            self.assertEqual(calls.count("log"), 1)
            commit(self.root, "more")
            oe.load_history(str(self.root))
            self.assertEqual(calls.count("log"), 2)
        caches = list((self.root / oe.CACHE_SUBDIR).glob("history-*.json"))
        self.assertEqual(len(caches), 1)  # the old HEAD's file was pruned

    def test_citation_removed_and_reintroduced_is_context_only(self):
        """A cited, citation dropped, A->B, A recreated, citation back, new A deleted."""
        commit(self.root, "a", {"src/k/a.py": "v1"})
        write_task(self.root, "10", "Cites `src/k/a.py`.\n")
        commit(self.root, "cite")
        write_task(self.root, "10", "No citation.\n")
        commit(self.root, "uncite")
        commit(self.root, "mv", moves=[("src/k/a.py", "src/k/b.py")])
        commit(self.root, "recreate", {"src/k/a.py": "v2"})
        write_task(self.root, "10", "Cites `src/k/a.py` again.\n")
        commit(self.root, "recite")
        commit(self.root, "rm", removes=["src/k/a.py"])
        ev = self.collect("10")
        rows = [r for r in ev.rows if r.kind.startswith("path_")]
        self.assertEqual([(r.kind, r.signal) for r in rows], [("path_deleted", False)])
        self.assertIn("lifetimes=2", rows[0].detail)
        self.assertEqual(ev.signal_count, 0)
        self.assertEqual(ev.digest, EMPTY_DIGEST)

    def test_uncommitted_planned_recreation_after_a_deletion_is_context_only(self):
        commit(self.root, "a", {"src/k/a.py": "v1"})
        commit(self.root, "rm", removes=["src/k/a.py"])
        write_task(self.root, "10", "Recreate `src/k/a.py` with the new API.\n")  # uncommitted
        ev = self.collect("10")
        self.assertEqual(self.kinds(ev), [("path_deleted", False)])
        self.assertEqual(ev.signal_count, 0)
        self.assertEqual(ev.digest, EMPTY_DIGEST)


class LifetimeTests(unittest.TestCase):
    """path_fact over synthetic, seq-ordered histories."""

    @staticmethod
    def hist(*evs):
        events = [oe.Event(seq=i, sha=f"{i:040x}", ct=1_700_000_000 + i, status=s, src=a, dst=b)
                  for i, (s, a, b) in enumerate(evs)]
        return oe.History(events)

    def test_reused_source_name_reports_the_latest_lifetime(self):
        h = self.hist(("A", None, "A"), ("R", "A", "B"), ("A", None, "A"), ("D", "A", None))
        kind, detail = oe.path_fact("A", h, tracked={"B"})
        self.assertEqual(kind, "path_deleted")
        self.assertIn("lifetimes=2", detail)

    def test_reused_intermediate_name_never_splices_chains(self):
        h = self.hist(("A", None, "A"), ("R", "A", "B"), ("D", "B", None), ("R", "C", "B"))
        kind, detail = oe.path_fact("A", h, tracked={"B"})
        self.assertEqual(kind, "path_deleted")
        self.assertTrue(detail.startswith("A -> B deleted in"), detail)

    def test_rename_cycle_terminates(self):
        h = self.hist(("A", None, "A"), ("R", "A", "B"), ("R", "B", "A"), ("D", "A", None))
        kind, detail = oe.path_fact("A", h, tracked=set())
        self.assertEqual(kind, "path_deleted")
        self.assertIn("lifetimes=2", detail)

    def test_re_added_but_untracked_is_ambiguous(self):
        h = self.hist(("A", None, "A"), ("D", "A", None), ("A", None, "A"))
        self.assertEqual(oe.path_fact("A", h, tracked=set())[0], "path_ambiguous")

    def test_rename_target_neither_tracked_nor_removed_is_ambiguous(self):
        h = self.hist(("A", None, "A"), ("R", "A", "B"))
        self.assertEqual(oe.path_fact("A", h, tracked=set())[0], "path_ambiguous")

    def test_never_removed_yields_nothing(self):
        h = self.hist(("A", None, "X"))
        self.assertIsNone(oe.path_fact("A", h, tracked=set()))

    def test_parse_log_z_rejects_garbage(self):
        with self.assertRaises(oe.HistoryError):
            oe.parse_log_z("\0Cnothex\x00123\0")


# ================================================================ origins

REVERT_COMPLETE = """## Revert Notes
- **Reverted by:** t99
- **Date:** 2026-10-01
- **Type:** Complete (all changes from this child were reverted)
- **Areas reverted:** lib/
"""
REVERT_PARTIAL = """## Revert Notes
- **Reverted by:** t98
- **Date:** 2026-10-02
- **Type:** Partial
- **Areas reverted:** a/
- **Areas kept:** b/
"""


class OriginTests(EBase):
    def test_parse_revert_notes(self):
        notes = oe.parse_revert_notes("---\nx: 1\n---\n\nbody\n\n" + REVERT_COMPLETE
                                      + "\n## Other\n- **Type:** nope\n" + REVERT_PARTIAL)
        self.assertEqual([n["type"] for n in notes], ["Complete", "Partial"])
        self.assertEqual(notes[0]["reverted_by"], "t99")
        self.assertEqual(notes[1]["areas_kept"], "b/")
        self.assertEqual(oe.parse_revert_notes("no notes"), [])

    def origin_case(self, origin_files):
        for path_args in origin_files:
            write_task(self.root, *path_args[:2], **path_args[2])

    def test_origin_states(self):
        write_task(self.root, "20", "Reverted origin.\n\n" + REVERT_COMPLETE, archived=True,
                   status="Done", extra=["completed_at: 2026-09-01 10:00"])
        write_task(self.root, "21", "Superseded origin.\n", archived=True, status="Done",
                   extra=["archived_reason: superseded"])
        write_task(self.root, "22", "Folded origin.\n", status="Folded", extra=["folded_into: 30"])
        write_task(self.root, "30", "Primary.\n")
        write_task(self.root, "24", "Completed origin.\n", archived=True, status="Done",
                   extra=["completed_at: 2026-09-01 10:00"])
        cases = {"20": ("reverted (Complete) by t99", True),
                 "21": ("archived:superseded", True),
                 "22": ("folded into t30", True),
                 "23": ("t23 deleted", True),
                 "24": ("archived:completed@2026-09-01 10:00", False)}
        for oid, (needle, signal) in cases.items():
            with self.subTest(origin=oid):
                write_task(self.root, "12", "Follow-up.\n", extra=[f"verifies: [{oid}]"])
                ev = self.collect("12")
                rows = [r for r in ev.rows if r.kind == "origin_state"]
                self.assertEqual(len(rows), 1, [r.detail for r in ev.rows])
                self.assertIn(needle, rows[0].detail)
                self.assertEqual(rows[0].signal, signal)
                self.assertEqual(rows[0].source, "frontmatter:verifies")

    def test_anchor_is_topic_and_active_origin_gives_no_row(self):
        write_task(self.root, "30", "Active root.\n")
        write_task(self.root, "12", "Child of topic.\n", extra=["anchor: 30"])
        self.assertEqual([r for r in self.collect("12").rows if r.kind == "origin_state"], [])

    def test_malformed_origin_is_incomplete(self):
        write_task(self.root, "12", "Bad.\n", extra=["verifies: [not-an-id]"])
        self.assertTrue(any(x.startswith("origin_malformed:") for x in self.collect("12").incomplete))


# =============================================================== relations

class RelationRowTests(EBase):
    def publish(self, tid, rels):
        out = rst.Store(str(self.root)).write(rs.store_path("records", tid),
                                              ts.record(self.root, tid, rels))
        self.assertTrue(any(x.startswith("PUBLISHED:") for x in out), out)

    def test_superseded_duplicate_and_affected_by_landed(self):
        write_task(self.root, "10", "Target.\n")
        write_task(self.root, "40", "Superseder.\n")
        write_task(self.root, "41", "Duplicate.\n")
        write_task(self.root, "42", "Landed.\n", archived=True, status="Done",
                   extra=["completed_at: 2026-11-05 10:00"])
        write_task(self.root, "43", "Affected by me.\n")
        self.publish("40", [("40", "10", "supersedes")])
        self.publish("41", [("41", "10", "duplicates")])
        self.publish("42", [("42", "10", "affects")])
        self.publish("10", [("10", "43", "affects")])  # outgoing: not evidence about t10
        ev = self.collect("10")
        rels = sorted((r.kind, r.signal) for r in ev.rows if r.source.startswith("store:"))
        self.assertEqual(rels, [("affected_by_landed", True), ("duplicate_of", True),
                                ("superseded_by", True)])
        aff = next(r for r in ev.rows if r.kind == "affected_by_landed")
        self.assertIn("aitasks#42 (landed@", aff.detail)
        self.assertEqual(aff.source, "store:records/t42.json")
        self.assertEqual(ev.signal_count, 3)


# ================================================================ premise

class PremiseTests(EBase):
    def run_with(self, cmd):
        write_task(self.root, "10", "Plain.\n")
        with mock.patch.dict(os.environ, {"AIT_OBSOLESCENCE_PREMISE_CMD": cmd}):
            return self.collect("10")

    def test_skip_is_context_and_ask_stale_is_signal(self):
        ev = self.run_with(premise_stub(self.tmp, "SKIP", "no baseline"))
        row = next(r for r in ev.rows if r.kind == "premise")
        self.assertEqual((row.detail, row.signal), ("SKIP: no baseline", False))
        ev = self.run_with(premise_stub(self.tmp, "ASK_STALE", "3 files changed"))
        row = next(r for r in ev.rows if r.kind == "premise")
        self.assertEqual((row.detail, row.signal), ("ASK_STALE: 3 files changed", True))

    def test_unavailable_when_the_tool_is_absent(self):
        write_task(self.root, "10", "Plain.\n")
        with mock.patch.dict(os.environ, {"AIT_OBSOLESCENCE_PREMISE_CMD": ""}), \
                mock.patch.object(oe, "PREMISE_SCRIPT", str(self.tmp / "absent.sh")):
            ev = self.collect("10")
        row = next(r for r in ev.rows if r.kind == "premise")
        self.assertEqual((row.detail, row.signal), ("unavailable", False))

    def test_failure_is_incomplete_never_all_clear(self):
        ev = self.run_with(premise_stub(self.tmp, "SKIP", "x", rc=1))
        self.assertIn("premise_failed:exit_1", ev.incomplete)
        self.assertFalse(any(r.kind == "premise" for r in ev.rows))


# ================================================================= digest

class DigestTests(unittest.TestCase):
    def test_stable_under_order_and_age_changes_on_signal(self):
        a = oe.Row("duplicate_of", "x", "store:a", True)
        b = oe.Row("origin_state", "t1 deleted", "frontmatter:verifies", True)
        age1 = oe.Row("age", "1 days", "frontmatter:created_at", False)
        age2 = oe.Row("age", "99 days", "frontmatter:created_at", False)
        path = oe.Row("path_deleted", "p deleted", "git log -M HEAD", False)
        self.assertEqual(oe.digest([a, b, age1]), oe.digest([b, age2, a, path]))
        self.assertNotEqual(oe.digest([a, b]), oe.digest([a]))
        ids = [r.id for r in oe._assign_ids([age1, b, a])]
        self.assertEqual(ids, ["duplicate_of:1", "origin_state:1", "age:1"])


if __name__ == "__main__":
    unittest.main()
