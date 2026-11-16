#!/usr/bin/env python3
"""Unit tests for the sitrep refresh core (lib/sitrep_refresh.py, t2175_3).

The bash suite (tests/test_sitrep_refresh.sh) owns the end-to-end runs: the
writer, the worker process group, the deadline, concurrency and progress across
runs. This file owns the rules: target selection and ordering, the task lookup
and its two verdicts (the reminder rule and the trail "landed" rule), the push
evidence rule against real scratch git repositories, the trail verdict, outcome
hygiene, the deadline arithmetic and the parent's stream-to-batch conversion.

Run: python3 tests/test_sitrep_refresh.py
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

import sitrep_refresh as sr  # noqa: E402
import sitrep_todo as st  # noqa: E402


# --- scratch task trees -------------------------------------------------------

def _task_text(status="Ready", **fields):
    lines = ["---", f"status: {status}"]
    for k, v in fields.items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines + ["---", "", "body", ""])


class Tree:
    """A scratch project root with `aitasks/` and `aitasks/archived/`."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.base = Path(self.root) / "aitasks"
        (self.base / "archived").mkdir(parents=True)

    def cleanup(self):
        for dirpath, dirnames, _files in os.walk(self.root):
            for d in dirnames:
                os.chmod(os.path.join(dirpath, d), 0o755)
        self._tmp.cleanup()

    def _path(self, tid, archived):
        top = self.base / "archived" if archived else self.base
        if "_" in tid:
            par = tid.split("_", 1)[0]
            return top / f"t{par}" / f"t{tid}_x.md"
        return top / f"t{tid}_x.md"

    def task(self, tid, status="Ready", archived=False, **fields):
        p = self._path(tid, archived)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_task_text(status, **fields), encoding="utf-8")
        return p

    def bundle(self, files: dict, name="old0.tar.gz", subdir="_b0"):
        """A numbered .tar.gz bundle (the gzip fallback path: no zstd needed).
        `subdir=""` writes at the archived/ top (the legacy old.tar.gz)."""
        d = self.base / "archived" / subdir if subdir else self.base / "archived"
        d.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for member, text in files.items():
                data = text.encode("utf-8")
                info = tarfile.TarInfo(member)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        (d / name).write_bytes(buf.getvalue())


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.tree = Tree()
        self.idx = sr.TaskIndex(self.tree.root)

    def tearDown(self):
        self.tree.cleanup()

    def verdict(self, tid):
        return sr.Checker._reminder(self.idx, tid)


# --- the task lookup and the reminder rule -------------------------------------

class ReminderVerdicts(TreeCase):
    def test_open_statuses_stay_open_with_the_live_status(self):
        for i, status in enumerate(("Ready", "Editing", "Implementing", "Postponed"), 10):
            self.tree.task(str(i), status)
            self.assertEqual(self.verdict(str(i)),
                             sr.Verdict("open", f"status: {status}"))

    def test_child_task(self):
        self.tree.task("12_3", "Implementing")
        self.assertEqual(self.verdict("12_3"), sr.Verdict("open", "status: Implementing"))

    def test_active_done_is_done(self):
        self.tree.task("20", "Done")
        self.assertEqual(self.verdict("20"),
                         sr.Verdict("done", "status: Done (not yet archived)"))

    def test_archived_loose_done(self):
        self.tree.task("21", "Done", archived=True, completed_at="2026-11-02 10:00")
        self.assertEqual(self.verdict("21"),
                         sr.Verdict("done", "archived (completed 2026-11-02)"))

    def test_archived_inside_a_bundle(self):
        self.tree.bundle({"t22_x.md": _task_text("Done", completed_at="2026-10-01 09:00"),
                          "t23_4_y.md": _task_text("Done")})
        self.assertEqual(self.verdict("22"),
                         sr.Verdict("done", "archived (completed 2026-10-01)"))
        self.assertEqual(self.verdict("23_4").state, "done")

    def test_archived_with_another_status_is_unknown(self):
        self.tree.task("24", "Ready", archived=True)
        self.assertEqual(self.verdict("24"),
                         sr.Verdict("unknown", "archived with status Ready"))

    def test_folded_with_and_without_folded_into(self):
        self.tree.task("30", "Ready")
        self.tree.task("31", "Folded", folded_into=30)
        self.tree.task("32", "Folded")
        self.assertEqual(self.verdict("31"),
                         sr.Verdict("done", "folded into t30 (t30: Ready)"))
        self.assertEqual(self.verdict("32"), sr.Verdict("done", "folded"))

    def test_fold_scan_hit_after_the_folded_file_was_deleted(self):
        self.tree.task("40", "Done", archived=True, folded_tasks="[41, 't42']")
        self.assertEqual(self.verdict("41"),
                         sr.Verdict("done", "folded into t40 (t40: archived)"))
        self.assertEqual(self.verdict("42").state, "done")

    def test_fold_scan_reads_bundles_too(self):
        self.tree.bundle({"t50_x.md": _task_text("Done", folded_tasks="[51]")})
        self.assertEqual(self.verdict("51").outcome, "folded into t50 (t50: archived)")

    def test_fold_scan_miss_is_unknown_never_done(self):
        self.tree.task("60", "Ready")
        self.assertEqual(self.verdict("61"), sr.Verdict("unknown", "task file not found"))

    def test_listed_by_two_receivers_is_unknown(self):
        self.tree.task("70", "Ready", folded_tasks="[72]")
        self.tree.task("71", "Ready", folded_tasks="[72]")
        self.assertEqual(self.verdict("72").state, "unknown")

    @unittest.skipIf(os.geteuid() == 0, "root reads unreadable dirs")
    def test_an_unlistable_directory_is_unknown_not_missing(self):
        """The active location cannot be listed, and a (stale) archived copy
        says Done: the active file would win if it exists, so the archived copy
        is not the answer -- unknown, never done."""
        self.tree.task("80_1", "Ready")
        self.tree.task("80_1", "Done", archived=True)
        os.chmod(self.tree.base / "t80", 0)
        v = self.verdict("80_1")
        self.assertEqual(v.state, "unknown")
        self.assertTrue(v.outcome.startswith("lookup failed:"), v.outcome)
        self.assertNotIn("fold scan", v.outcome)

    @unittest.skipIf(os.geteuid() == 0, "root reads unreadable dirs")
    def test_an_unreadable_archive_blocks_the_fold_scan(self):
        self.tree.bundle({"t90_x.md": _task_text("Done")})
        os.chmod(self.tree.base / "archived" / "_b0", 0)
        v = self.verdict("91")
        self.assertEqual(v.state, "unknown")

    def test_unparseable_frontmatter_is_unknown(self):
        p = self.tree.task("95", "Ready")
        p.write_text("---\nstatus: [unclosed\n---\n", encoding="utf-8")
        self.assertEqual(self.verdict("95").state, "unknown")


class FoldIndex(TreeCase):
    """The fold scan reads each task's AUTHORITATIVE record only (active, then
    loose archived, then its own numbered bundle, then legacy), and any
    unparseable task record makes the scan -- and so the lookup -- unknown."""

    def test_a_stale_archived_copy_does_not_invent_a_second_receiver(self):
        self.tree.task("30", "Ready", folded_tasks="[12]")
        self.tree.task("30", "Done", archived=True, folded_tasks="[12, 13]")  # stale
        self.tree.task("31", "Done", folded_tasks="[13]")
        self.assertEqual(self.verdict("13"),
                         sr.Verdict("done", "folded into t31 (t31: Done)"))
        self.assertEqual(self.verdict("12"),
                         sr.Verdict("done", "folded into t30 (t30: Ready)"))

    def test_an_obsolete_archived_relationship_does_not_close_a_reminder(self):
        self.tree.task("40", "Ready")                                   # lists nothing now
        self.tree.task("40", "Done", archived=True, folded_tasks="[41]")  # stale
        self.assertEqual(self.verdict("41"), sr.Verdict("unknown", "task file not found"))
        self.assertEqual(sr.landed_state("41", self.idx.lookup)[0], "unverifiable")

    def test_a_copy_in_another_bundle_is_not_authoritative(self):
        self.tree.bundle({"t30_x.md": _task_text("Done", folded_tasks="[12]")},
                         name="old5.tar.gz", subdir="_b0")
        self.assertEqual(self.verdict("12"), sr.Verdict("unknown", "task file not found"))

    def _zst_bundle(self, files: dict, name="old0.tar.zst"):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for member, text in files.items():
                data = text.encode("utf-8")
                info = tarfile.TarInfo(member)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        d = self.tree.base / "archived" / "_b0"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(subprocess.run(["zstd", "-q", "-c"], input=buf.getvalue(),
                                              capture_output=True, check=True).stdout)

    @unittest.skipUnless(shutil.which("zstd"), "zstd is not installed")
    def test_a_gzip_record_absent_from_the_coexisting_zstd_bundle_is_read(self):
        self._zst_bundle({"t31_x.md": _task_text("Ready")})
        self.tree.bundle({"t30_x.md": _task_text("Done", folded_tasks="[12]")})
        self.assertEqual(self.idx.lookup("30").found, "archived")       # direct lookup
        self.assertEqual(self.verdict("12"),
                         sr.Verdict("done", "folded into t30 (t30: archived)"))
        self.assertEqual(sr.landed_state("12", self.idx.lookup), ("landed", ["12", "30"]))

    @unittest.skipUnless(shutil.which("zstd"), "zstd is not installed")
    def test_control_the_zstd_record_wins_when_both_bundles_hold_it(self):
        self._zst_bundle({"t30_x.md": _task_text("Done", folded_tasks="[12]")})
        self.tree.bundle({"t30_x.md": _task_text("Done", folded_tasks="[13]")})  # stale
        self.assertEqual(self.verdict("12").state, "done")
        self.assertEqual(self.verdict("13"), sr.Verdict("unknown", "task file not found"))

    def test_the_legacy_bundle_is_scanned(self):
        """A deleted folded task whose receiver lives only in the legacy
        old.tar.gz: the reminder closes and the trail entry lands."""
        self.tree.bundle({"t30_x.md": _task_text("Done", folded_tasks="[12]")},
                         name="old.tar.gz", subdir="")
        self.assertEqual(self.idx.lookup("30").found, "archived")       # direct lookup
        self.assertEqual(self.verdict("12"),
                         sr.Verdict("done", "folded into t30 (t30: archived)"))
        self.assertEqual(sr.landed_state("12", self.idx.lookup), ("landed", ["12", "30"]))

    def test_an_active_file_without_frontmatter_makes_the_scan_unknown(self):
        self.tree.task("30", "Done", folded_tasks="[12]")
        (self.tree.base / "t31_x.md").write_text("no frontmatter here\n", encoding="utf-8")
        v = self.verdict("12")
        self.assertEqual(v.state, "unknown")
        self.assertIn("fold scan", v.outcome)

    def test_malformed_yaml_makes_the_scan_unknown(self):
        self.tree.task("30", "Done", folded_tasks="[12]")
        (self.tree.base / "t31_x.md").write_text("---\nstatus: [unclosed\n---\n",
                                                 encoding="utf-8")
        self.assertEqual(self.verdict("12").state, "unknown")
        self.tree.bundle({"t32_x.md": "---\nstatus: [bad\n---\n"}, name="old.tar.gz",
                         subdir="")
        (self.tree.base / "t31_x.md").unlink()
        self.idx = sr.TaskIndex(self.tree.root)
        self.assertEqual(self.verdict("12").state, "unknown")    # legacy parse error


# The shapes this repo's archived t20-t22 (_b0/old0.tar.zst) had before t2190
# gave them an empty frontmatter block: prose (with a later markdown `---`
# rule) and the legacy inline header `--- effort:… pri:…` with a `---` further
# down. MIGRATED is the block t2190 prepended -- exactly what
# `task_yaml.serialize_frontmatter({}, body, [])` writes.
T20_SHAPE = ("there is already a skill of handling aitask selection\n"
             "## the new aitask-create skill\nthe skill should\n---\nmore prose\n")
T21_SHAPE = ("--- effort:med pri:med\nI want to rewrite the aitask-create slash command\n\n"
             "---\nCOMPLETED: 2026-02-01 11:33\n")
T22_SHAPE = ("--- effort:med pri:hi\n\nI would like to modify the task creation scripts\n\n"
             "---\nCOMPLETED: 2026-02-01 14:33\n")
HEADERLESS = {"20": T20_SHAPE, "21": T21_SHAPE, "22": T22_SHAPE}
MIGRATED = "---\n{}\n---\n"


class HeaderlessArchivedRecords(TreeCase):
    """A record with no frontmatter fails the fold scan closed, archived or
    active alike; the same records given an empty frontmatter block (the t2190
    migration) complete it without ever making the historical task done."""

    def setUp(self):
        super().setUp()
        self._bundle_with({})     # t30 (Done) lists t12 in folded_tasks

    def _bundle_with(self, records: dict):
        files = {f"t{tid}_x.md": text for tid, text in records.items()}
        files["t30_x.md"] = _task_text("Done", folded_tasks="[12]")
        self.tree.bundle(files)
        self.idx = sr.TaskIndex(self.tree.root)

    def test_the_baseline_scan_is_clean(self):
        """Control: every scan error below is caused by the record under test."""
        self.assertEqual(self.verdict("12"),
                         sr.Verdict("done", "folded into t30 (t30: archived)"))
        self.assertEqual(self.idx._fold_errors, [])

    def test_headerless_archived_records_fail_the_scan(self):
        for tid, shape in HEADERLESS.items():
            with self.subTest(tid=tid):
                self.tree.cleanup()
                self.tree = Tree()
                self._bundle_with({tid: shape})
                self.assertScanError()
                self.assertEqual(len(self.idx._fold_errors), 1)
                self.assertIn(f"t{tid}_x.md: unparseable frontmatter",
                              self.idx._fold_errors[0])

    def test_headerless_archived_task_itself_stays_unknown(self):
        self._bundle_with(HEADERLESS)
        for tid in HEADERLESS:
            v = self.verdict(tid)
            self.assertEqual(v.state, "unknown", tid)
            self.assertIn("unparseable frontmatter", v.outcome)
            self.assertEqual(sr.landed_state(tid, self.idx.lookup)[0], "unverifiable")

    def test_migrated_records_complete_the_scan(self):
        self._bundle_with({tid: MIGRATED + shape for tid, shape in HEADERLESS.items()})
        self.assertEqual(self.verdict("12"),
                         sr.Verdict("done", "folded into t30 (t30: archived)"))
        self.assertEqual(self.idx._fold_errors, [])
        self.assertEqual(sr.landed_state("12", self.idx.lookup), ("landed", ["12", "30"]))

    def test_a_migrated_historical_task_is_never_made_done(self):
        self._bundle_with({tid: MIGRATED + shape for tid, shape in HEADERLESS.items()})
        for tid in HEADERLESS:
            v = self.verdict(tid)
            self.assertEqual(v.state, "unknown", tid)
            self.assertIn(f"t{tid}_x.md: no status", v.outcome)
            self.assertEqual(sr.landed_state(tid, self.idx.lookup)[0], "unverifiable")

    def assertScanError(self):
        """Unknown BECAUSE the scan failed -- not merely "not found"."""
        v = self.verdict("12")
        self.assertEqual(v.state, "unknown")
        self.assertIn("fold scan", v.outcome)

    def _with_archived(self, text):
        self.tree.task("40", "Done", archived=True)
        (self.tree.base / "archived" / "t40_x.md").write_text(text, encoding="utf-8")
        self.idx = sr.TaskIndex(self.tree.root)

    def test_incomplete_modern_frontmatter_stays_an_error(self):
        self._with_archived("---\nstatus: Done\nfolded_tasks: [12]\n")    # no close
        self.assertScanError()

    def test_an_unknown_dash_header_stays_an_error(self):
        self._with_archived("--- not a key value header\nbody\n")
        self.assertScanError()

    def test_malformed_archived_yaml_stays_an_error(self):
        self._with_archived("---\nstatus: [bad\n---\n")
        self.assertScanError()

    def test_a_headerless_ACTIVE_file_stays_an_error(self):
        (self.tree.base / "t41_x.md").write_text(T20_SHAPE, encoding="utf-8")
        self.assertScanError()

    @unittest.skipIf(os.geteuid() == 0, "root reads unreadable files")
    def test_an_unreadable_archived_record_stays_an_error(self):
        self._with_archived(T20_SHAPE)
        os.chmod(self.tree.base / "archived" / "t40_x.md", 0)
        self.assertScanError()


VALID = ("Ready", "Editing", "Implementing", "Postponed", "Done", "Folded")

# Frontmatter bodies whose status is unusable, keyed by the reason the lookup
# must name. Raw text: `_task_text(None)` would write `status: None`, which YAML
# reads as the string "None".
BAD_STATUS = {
    "banana": ("---\nstatus: Banana\n---\nbody\n", "invalid status 'Banana'"),
    "empty": ("---\nstatus:\n---\nbody\n", "no status"),
    "absent": ("---\npriority: high\n---\nbody\n", "no status"),
    "list": ("---\nstatus: [Done]\n---\nbody\n", "no status"),
    "number": ("---\nstatus: 5\n---\nbody\n", "no status"),
}


class StatusValidation(TreeCase):
    """t2307: a direct lookup validates the status against the task vocabulary.
    A record whose status is missing, not a string or outside the vocabulary is
    an error -- refresh says `unknown` and the trail entry is `unverifiable`,
    never an open or done verdict."""

    def write(self, rel, text):
        p = self.tree.base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def assertRejected(self, tid, reason):
        facts = self.idx.lookup(tid)
        self.assertEqual(facts.found, "error", (tid, facts))
        self.assertIn(reason, facts.detail)
        v = self.verdict(tid)
        self.assertEqual(v.state, "unknown", (tid, v))
        self.assertTrue(v.outcome.startswith("lookup failed:"), v.outcome)
        self.assertIn(reason, v.outcome)
        self.assertEqual(sr.landed_state(tid, self.idx.lookup)[0], "unverifiable", tid)

    def test_active_records(self):
        for i, (key, (text, reason)) in enumerate(BAD_STATUS.items(), 10):
            with self.subTest(key=key):
                self.write(f"t{i}_x.md", text)
                self.assertRejected(str(i), reason)

    def test_active_child_record(self):
        self.write("t13/t13_1_x.md", BAD_STATUS["banana"][0])
        self.assertRejected("13_1", "invalid status 'Banana'")

    def test_archived_loose_records(self):
        for i, (key, (text, reason)) in enumerate(BAD_STATUS.items(), 20):
            with self.subTest(key=key):
                self.write(f"archived/t{i}_x.md", text)
                self.assertRejected(str(i), reason)

    def test_archived_child_record(self):
        self.write("archived/t14/t14_1_x.md", BAD_STATUS["banana"][0])
        self.assertRejected("14_1", "invalid status 'Banana'")

    def test_archived_bundled_records(self):
        self.tree.bundle({"t30_x.md": BAD_STATUS["banana"][0],
                          "t31_x.md": BAD_STATUS["absent"][0]})
        self.assertRejected("30", "t30_x.md: invalid status 'Banana'")
        self.assertRejected("31", "t31_x.md: no status")

    def test_a_completion_date_does_not_make_a_bad_record_done(self):
        self.write("archived/t40_x.md",
                   "---\nstatus: Completed\ncompleted_at: 2026-11-02 10:00\n---\nbody\n")
        self.assertRejected("40", "invalid status 'Completed'")

    def test_a_receiver_with_a_bad_status(self):
        """The folded task's own reminder still closes (it is Folded), but the
        receiver is unreadable: no live-state parenthetical, and the trail
        entry cannot land."""
        self.tree.task("31", "Folded", folded_into=30)
        self.write("t30_x.md", BAD_STATUS["banana"][0])
        self.assertEqual(self.verdict("31"), sr.Verdict("done", "folded into t30"))
        self.assertEqual(sr.landed_state("31", self.idx.lookup), ("unverifiable", ["31", "30"]))
        self.assertEqual(sr.describe(self.idx.lookup("30")), "unreadable")

    def test_the_fold_scan_still_reads_a_bad_status_record(self):
        """The scan answers who lists the id, not the receiver's state."""
        self.write("t30_x.md", "---\nstatus: Banana\nfolded_tasks: [41]\n---\nbody\n")
        self.assertEqual(self.verdict("41"), sr.Verdict("done", "folded into t30"))
        self.assertEqual(sr.landed_state("41", self.idx.lookup), ("unverifiable", ["41", "30"]))
        self.assertEqual(self.idx._fold_errors, [])

    def test_control_every_valid_status_is_accepted(self):
        for i, status in enumerate(VALID, 50):
            with self.subTest(status=status):
                self.tree.task(str(i), status)
                facts = self.idx.lookup(str(i))
                self.assertEqual((facts.found, facts.status), ("active", status))
        for i, status in enumerate(VALID, 60):
            with self.subTest(status=status, archived=True):
                self.tree.task(str(i), status, archived=True)
                facts = self.idx.lookup(str(i))
                self.assertEqual((facts.found, facts.status), ("archived", status))

    def test_control_surrounding_whitespace_still_validates(self):
        self.write("t70_x.md", '---\nstatus: " Done "\n---\nbody\n')
        self.assertEqual(self.verdict("70"),
                         sr.Verdict("done", "status: Done (not yet archived)"))

    def test_the_vocabulary(self):
        self.assertEqual(sr.VALID_STATUSES, VALID)
        import sitrep_crash
        self.assertIs(sitrep_crash.VALID_STATUSES, sr.VALID_STATUSES)


# --- the trail "landed" rule ---------------------------------------------------

class LandedState(TreeCase):
    def landed(self, tid):
        return sr.landed_state(tid, self.idx.lookup)

    def test_done_lands_and_open_statuses_do_not(self):
        self.tree.task("1", "Done", archived=True)
        self.tree.task("2", "Implementing")
        self.assertEqual(self.landed("1"), ("landed", ["1"]))
        self.assertEqual(self.landed("2"), ("open", ["2"]))

    def test_an_existing_folded_entry_follows_its_receiver(self):
        """(a) a Folded entry is landed only when the task it was merged into
        is Done; while the receiver is Ready / Implementing it stays open."""
        self.tree.task("12", "Folded", folded_into=30)
        self.tree.task("30", "Ready")
        self.assertEqual(self.landed("12"), ("open", ["12", "30"]))
        self.tree.task("30", "Implementing")
        self.idx = sr.TaskIndex(self.tree.root)
        self.assertEqual(self.landed("12"), ("open", ["12", "30"]))
        (self.tree.base / "t30_x.md").unlink()
        self.tree.task("30", "Done", archived=True)
        self.idx = sr.TaskIndex(self.tree.root)
        self.assertEqual(self.landed("12"), ("landed", ["12", "30"]))
        # The settled reminder rule, pinned beside it: the folded task's own
        # item closes on Folded whatever its receiver's state.
        self.assertEqual(self.verdict("12").state, "done")

    def test_a_deleted_folded_entry_found_by_the_scan_follows_its_receiver(self):
        """(b) the folded file is gone; the receiver lists it in folded_tasks."""
        self.tree.task("30", "Ready", folded_tasks="[12]")
        self.assertEqual(self.landed("12"), ("open", ["12", "30"]))
        self.assertEqual(self.verdict("12"),
                         sr.Verdict("done", "folded into t30 (t30: Ready)"))
        (self.tree.base / "t30_x.md").unlink()
        self.tree.task("30", "Done", archived=True, folded_tasks="[12]")
        self.idx = sr.TaskIndex(self.tree.root)
        self.assertEqual(self.landed("12"), ("landed", ["12", "30"]))

    def test_a_receiver_chain_lands_when_its_end_is_done(self):
        """(c) t12 → t30 → t31 (Done)."""
        self.tree.task("12", "Folded", folded_into=30)
        self.tree.task("30", "Folded", folded_into=31)
        self.tree.task("31", "Done")
        self.assertEqual(self.landed("12"), ("landed", ["12", "30", "31"]))

    def test_a_cycle_is_unverifiable(self):
        self.tree.task("12", "Folded", folded_into=30)
        self.tree.task("30", "Folded", folded_into=12)
        self.assertEqual(self.landed("12")[0], "unverifiable")

    def test_more_than_five_hops_is_unverifiable(self):
        for i in range(1, 8):
            self.tree.task(str(i), "Folded", folded_into=i + 1)
        self.tree.task("8", "Done")
        self.assertEqual(self.landed("3")[0], "landed")      # 3→…→8: 5 hops
        self.assertEqual(self.landed("2")[0], "unverifiable")  # 6 hops

    def test_missing_and_receiverless_entries_are_unverifiable(self):
        self.tree.task("5", "Folded")
        self.assertEqual(self.landed("4")[0], "unverifiable")
        self.assertEqual(self.landed("5")[0], "unverifiable")


# --- trail verdicts ------------------------------------------------------------

def _doc(waves, owner="proj#9"):
    return {"owner": owner, "generation": {"generated_at": "2026-10-30T10:00:00Z"},
            "waves": [{"wave_id": f"w{i}", "ordinal": i, "title": title,
                       "entries": [{"task": t} for t in tasks]}
                      for i, (title, tasks) in enumerate(waves, start=1)]}


class TrailVerdicts(unittest.TestCase):
    def state_of(self, table):
        return lambda ref: (table[ref], ref.replace("proj#", "t"))

    def test_next_wave_is_the_first_with_an_unlanded_entry(self):
        doc = _doc([("Base", ["proj#1"]), ("Core", ["proj#2", "proj#3"]), ("End", ["proj#4"])])
        v = sr.trail_verdict(doc, self.state_of({"proj#1": "landed", "proj#2": "open",
                                                 "proj#3": "landed", "proj#4": "open"}),
                             "drift CURRENT", "owner t9 Ready")
        self.assertEqual(v.state, "open")
        self.assertEqual(v.outcome, "next wave 2/3 Core: 1 pending (t2) · drift CURRENT"
                                    " · generated 2026-10-30 · owner t9 Ready")

    def test_all_landed_is_done(self):
        doc = _doc([("A", ["proj#1"]), ("B", ["proj#2"])])
        v = sr.trail_verdict(doc, self.state_of({"proj#1": "landed", "proj#2": "landed"}),
                             "drift STALE (2)")
        self.assertEqual(v, sr.Verdict("done", "all 2 waves landed · drift STALE (2)"
                                               " · generated 2026-10-30"))

    def test_one_unverifiable_entry_with_the_rest_landed_is_unknown(self):
        doc = _doc([("A", ["proj#1", "proj#2"])])
        v = sr.trail_verdict(doc, self.state_of({"proj#1": "landed", "proj#2": "unverifiable"}),
                             "drift unavailable")
        self.assertEqual(v.state, "unknown")
        self.assertIn("(t2?)", v.outcome)

    def test_a_folded_entry_with_an_open_receiver_holds_the_wave(self):
        doc = _doc([("A", ["proj#12"]), ("B", ["proj#13"])])
        v = sr.trail_verdict(doc, lambda ref: (("open", "t12→t30") if ref == "proj#12"
                                               else ("open", "t13")), "drift error")
        self.assertTrue(v.outcome.startswith("next wave 1/2 A: 1 pending (t12→t30)"), v.outcome)

    def test_a_long_wave_title_never_crowds_out_the_facts(self):
        doc = _doc([("T" * 150, ["proj#1", "proj#2"])])
        v = sr.trail_verdict(doc, lambda ref: ("open", ref.replace("proj#", "t")),
                             "drift CURRENT", "owner t9 Ready")
        self.assertLessEqual(len(v.outcome), st.MAX_OUTCOME)
        self.assertIn("T" * 59 + "…", v.outcome)
        for fact in ("(t1, t2)", "drift CURRENT", "generated 2026-10-30", "owner t9 Ready"):
            self.assertIn(fact, v.outcome)

    def test_a_long_member_list_is_shortened_first(self):
        tasks = [f"proj#{i}" for i in range(100, 160)]
        doc = _doc([("A very long wave title " * 2, tasks)])
        v = sr.trail_verdict(doc, lambda ref: ("open", ref.replace("proj#", "t")),
                             "drift CURRENT", "owner t9 Ready")
        self.assertLessEqual(len(v.outcome), st.MAX_OUTCOME)
        self.assertIn("…+", v.outcome)
        self.assertIn("drift CURRENT", v.outcome)


class TrailCheckSeams(TreeCase):
    def test_unreadable_trail_and_bad_pointers_are_unknown(self):
        c = sr.Checker(self.tree.root)
        self.assertEqual(c.check_trail(("art:trail-a", "art:trail-b")),
                         sr.Verdict("unknown", "several trail sources"))
        self.assertEqual(c.check_trail(("trail-x",)).state, "unknown")


# --- push ----------------------------------------------------------------------

def _git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True, env=env).stdout.strip()


class PushVerdicts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.remote_a = base / "a.git"
        self.remote_b = base / "b.git"
        _git(base, "init", "-q", "--bare", "-b", "main", str(self.remote_a))
        _git(base, "init", "-q", "--bare", "-b", "main", str(self.remote_b))
        self.repo = base / "repo"
        _git(base, "init", "-q", "-b", "main", str(self.repo))
        _git(self.repo, "commit", "-q", "--allow-empty", "-m", "one")
        _git(self.repo, "remote", "add", "origin", str(self.remote_a))
        _git(self.repo, "push", "-q", "-u", "origin", "main")
        _git(self.repo, "commit", "-q", "--allow-empty", "-m", "two")
        self.sha = _git(self.repo, "rev-parse", "HEAD")
        os.environ["GIT_CONFIG_GLOBAL"] = "/dev/null"
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"

    def tearDown(self):
        os.environ.pop("GIT_CONFIG_GLOBAL", None)
        os.environ.pop("GIT_CONFIG_NOSYSTEM", None)
        self._tmp.cleanup()

    def v(self, branch="main", sha=None):
        return sr.push_verdict(str(self.repo), branch, sha or self.sha)

    def push(self):
        _git(self.repo, "push", "-q", "origin", "main")

    def test_ahead_is_open_with_counts_then_pushed_is_done(self):
        v = self.v()
        self.assertEqual(v.state, "open")
        self.assertTrue(v.outcome.startswith("not pushed: main 1 ahead / 0 behind origin/main"),
                        v.outcome)
        self.push()
        self.assertEqual(self.v(), sr.Verdict("done", f"pushed: {self.sha[:7]} is on origin/main"))

    def test_controls_pushurl_equal_to_url_and_no_pushurl_are_done(self):
        self.push()
        self.assertEqual(self.v().state, "done")
        _git(self.repo, "config", "remote.origin.pushurl", str(self.remote_a))
        self.assertEqual(self.v().state, "done")

    def test_two_endpoints_pushurl_differs_is_unknown(self):
        """origin.url = A holds the sha (and is fetched into
        refs/remotes/origin/main); origin.pushurl = empty B. The ancestry check
        alone would say done although B lacks the commit."""
        self.push()
        _git(self.repo, "fetch", "-q", "origin")
        _git(self.repo, "config", "remote.origin.pushurl", str(self.remote_b))
        self.assertEqual(_git(self.repo, "rev-parse", "--symbolic-full-name", "main@{push}"),
                         "refs/remotes/origin/main")
        _git(self.repo, "merge-base", "--is-ancestor", self.sha, "refs/remotes/origin/main")
        v = self.v()
        self.assertEqual(v.state, "unknown")
        self.assertIn("push URL differs from fetch URL", v.outcome)

    def test_several_push_or_fetch_urls_are_unknown(self):
        self.push()
        _git(self.repo, "config", "--add", "remote.origin.pushurl", str(self.remote_a))
        _git(self.repo, "config", "--add", "remote.origin.pushurl", str(self.remote_b))
        self.assertEqual(self.v().state, "unknown")
        _git(self.repo, "config", "--unset-all", "remote.origin.pushurl")
        _git(self.repo, "config", "--add", "remote.origin.url", str(self.remote_b))
        self.assertEqual(self.v().state, "unknown")

    def test_a_push_insteadof_rewrite_is_unknown(self):
        self.push()
        _git(self.repo, "config", f"url.{self.remote_b}.pushInsteadOf", str(self.remote_a))
        self.assertEqual(self.v().state, "unknown")

    def test_no_upstream_is_unknown(self):
        _git(self.repo, "branch", "--unset-upstream")
        self.assertEqual(self.v().state, "unknown")

    def test_a_local_upstream_is_unknown_never_done(self):
        _git(self.repo, "branch", "integration")          # holds the sha
        _git(self.repo, "config", "branch.main.remote", ".")
        _git(self.repo, "config", "branch.main.merge", "refs/heads/integration")
        # Under push.default=upstream git RESOLVES @{push} to the local branch
        # (under the default `simple` it refuses, which would not reach the
        # guard): the case the remote-destination check exists for.
        _git(self.repo, "config", "push.default", "upstream")
        self.assertEqual(_git(self.repo, "rev-parse", "--symbolic-full-name", "main@{push}"),
                         "refs/heads/integration")
        _git(self.repo, "merge-base", "--is-ancestor", self.sha, "integration")
        self.assertEqual(self.v(), sr.Verdict("unknown", "no remote push destination for main"))

    def test_a_remote_without_a_url_is_unknown(self):
        self.push()
        _git(self.repo, "config", "--unset", "remote.origin.url")
        self.assertEqual(self.v().state, "unknown")

    def test_no_remotes_at_all_is_unknown(self):
        _git(self.repo, "remote", "remove", "origin")
        self.assertEqual(self.v().state, "unknown")

    def test_unknown_sha_missing_branch_and_non_git(self):
        self.assertEqual(self.v(sha="0" * 40).state, "unknown")
        self.assertEqual(self.v(branch="nope").outcome, "no local branch nope")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sr.push_verdict(d, "main", self.sha),
                             sr.Verdict("unknown", "not a git repository"))

    def test_a_shell_metacharacter_branch_is_refused(self):
        marker = Path(self._tmp.name) / "pwned"
        v = self.v(branch=f"a$(touch {marker})")
        self.assertEqual(v.state, "unknown")
        self.assertFalse(marker.exists())


# --- targets, ordering, hygiene, deadline, stream -------------------------------

def _store_with(*items, contexts=None):
    s = st.TodoStore()
    for it in items:
        s.items[it.num] = it
    s.contexts = contexts or {}
    return s


def _item(num, **kw):
    base = dict(rev=num, kind="task", state="open", group="next", checked_at="never",
                ref="", derived="script", outcome="", title=f"item {num}")
    base.update(kw)
    return st.Item(num, **base)


class Targets(unittest.TestCase):
    def test_only_checkable_open_or_unknown_items_are_targets(self):
        s = _store_with(
            _item(1, ref="t10"),
            _item(2, ref="t11", state="unknown"),
            _item(3, ref="t12", state="done"),
            _item(4, ref="t13", state="dismissed"),
            _item(5, kind="question"),
            _item(6, kind="action", derived="agent"),
            _item(7, kind="action", ref="push:main@abcdef1"),
            _item(8, kind="watch"),
            _item(9, kind="watch"),
            _item(10, kind="task"),
            _item(11, ref="proj#5"),
            contexts={9: st.ContextEntry("b", [("agent", "x")], sources=[("trail", "art:trail-x")]),
                      8: st.ContextEntry("b", [("agent", "x")], sources=[("task", "aitasks/t1_x.md")])})
        got = [(t.num, t.check) for t in sr.select_targets(s)]
        self.assertEqual(got, [(1, "task"), (2, "task"), (7, "push"), (9, "trail"), (11, "task")])

    def test_a_recovery_item_gets_its_own_check_and_recorded_incarnation(self):
        # A recover: item's state comes from the recovery decision table, never
        # from the task's status (t2299_3): check="recovery", never "task".
        s = _store_with(
            _item(1, ref="recover:t10"), _item(2, ref="t10"),
            _item(3, ref="recover:t11", state="unknown"),
            _item(4, ref="recover:t12", state="done"),
            _item(5, ref="recover:t13", state="dismissed"),
            contexts={1: st.ContextEntry("b", [("task", "t10"), ("incarnation", "0123456789ab")]),
                      3: st.ContextEntry("b", [("task", "t11")])})
        got = [(t.num, t.check, t.incarnation) for t in sr.select_targets(s)]
        self.assertEqual(got, [(1, "recovery", "0123456789ab"), (2, "task", ""),
                               (3, "recovery", "")])

    def test_order_is_oldest_check_first(self):
        ts = [sr.Target(n, n, "task", "open", "", c, "task") for n, c in
              ((1, "2026-11-02T10:00:00Z"), (2, "never"), (3, "2026-11-01T10:00:00Z"),
               (4, "never"), (5, "2026-11-01T10:00:00Z"))]
        self.assertEqual([t.num for t in sr.order_targets(ts)], [2, 4, 3, 5, 1])


class Hygiene(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(sr.clean_text("a|b\nc\x07d\t e"), "a/b c d e")

    def test_fit_outcome_bounds_and_drops_trailing_segments(self):
        out = sr.fit_outcome(["x" * 120, "y" * 60, "z" * 60])
        self.assertEqual(out, "x" * 120 + " · " + "y" * 60)
        long_ = sr.fit_outcome(["w" * 500])
        self.assertEqual(len(long_), st.MAX_OUTCOME)
        self.assertTrue(long_.endswith("…"))
        self.assertEqual(sr.fit_outcome(["a|b", ""]), "a/b")

    def test_outcomes_are_writer_valid(self):
        for text in (sr.fit_outcome(["p" * 400]), sr.fit_with_members("h", ["m"] * 200, ["t"])):
            self.assertEqual(st._single_line("outcome", text, st.MAX_OUTCOME, False), text)


class DeadlineMath(unittest.TestCase):
    def test_reserve_and_lefts(self):
        clock = [100.0]
        d = sr.Deadline(60, now=lambda: clock[0])
        self.assertEqual(d.reserve, 15.0)
        self.assertEqual(d.check_left(), 45.0)
        self.assertEqual(d.run_left(), 60.0)
        clock[0] = 150.0
        self.assertEqual(d.check_left(), -5.0)
        self.assertEqual(d.run_left(), 10.0)
        self.assertEqual(sr.Deadline(12).reserve, 3.0)
        self.assertEqual(sr.Deadline(0).reserve, 0.0)


class BudgetValidation(unittest.TestCase):
    def run_main(self, argv, env_budget=None):
        old = os.environ.pop("AITASK_SITREP_REFRESH_BUDGET", None)
        try:
            if env_budget is not None:
                os.environ["AITASK_SITREP_REFRESH_BUDGET"] = env_budget
            with tempfile.TemporaryDirectory() as d:
                return sr.main(["run", "--root", d] + argv)
        finally:
            os.environ.pop("AITASK_SITREP_REFRESH_BUDGET", None)
            if old is not None:
                os.environ["AITASK_SITREP_REFRESH_BUDGET"] = old

    def test_non_finite_and_out_of_range_budgets_are_usage_errors(self):
        for bad in ("inf", "-inf", "nan", "1e400", "-1", "86401", "abc"):
            self.assertEqual(self.run_main(["--budget", bad]) if bad != "abc"
                             else self.run_main([], env_budget=bad), 2, bad)
            self.assertEqual(self.run_main([], env_budget=bad), 2, f"env {bad}")

    def test_a_valid_budget_runs(self):
        self.assertEqual(self.run_main(["--budget", "30"]), 0)   # no store: NONE, exit 0


class StreamToBatch(unittest.TestCase):
    def feed(self, *lines):
        s = sr.Stream()
        for ln in lines:
            s.feed(ln)
        return s

    def test_finished_and_interrupted_lines(self):
        s = self.feed("ROOT:/r|with pipe", "TARGETS:3",
                      "START:c4|17|task|open|status: Ready", "VERDICT:c4|done|archived",
                      "START:c9|23|action|unknown|old text")
        self.assertEqual(s.root, "/r|with pipe")
        lines = s.close(interrupted=True, budget=12)
        self.assertEqual([(ln.num, ln.rev, ln.state) for ln in lines],
                         [(4, 17, "done"), (9, 23, "unknown")])
        self.assertEqual(lines[1].outcome, "check did not finish within the 12s budget")
        self.assertEqual(lines[1].old_outcome, "old text")
        self.assertTrue(lines[1].interrupted)

    def test_not_started_targets_are_not_lines(self):
        s = self.feed("ROOT:/r", "TARGETS:3", "START:c1|1|task|open|", "VERDICT:c1|open|x")
        self.assertEqual(len(s.close(interrupted=True, budget=5)), 1)

    def test_protocol_errors(self):
        for bad in (["ROOT:/r", "VERDICT:c1|open|x"],
                    ["ROOT:/r", "START:c1|1|task|open|", "START:c2|2|task|open|"],
                    ["ROOT:/r", "START:c1|1|task|open|", "VERDICT:c2|open|x"],
                    ["ROOT:/r", "START:c1|1|task|open|", "VERDICT:c1|dismissed|x"],
                    ["ROOT:/r", "START:c1|x|task|open|"],
                    ["ROOT:/r", "garbage"]):
            with self.assertRaises(sr.ProtocolError, msg=bad):
                self.feed(*bad)

    def test_an_open_start_without_a_kill_is_a_protocol_error(self):
        s = self.feed("ROOT:/r", "TARGETS:1", "START:c1|1|task|open|")
        with self.assertRaises(sr.ProtocolError):
            s.close(interrupted=False, budget=5)


# --- recovery targets (t2299_3) --------------------------------------------------

import sitrep_crash as sc  # noqa: E402

_REC = "0123456789ab"


def _v(row, category, stored, item_state, evidence="ev"):
    return sc.Verdict(row, category, stored, item_state, evidence)


class RecoveryVerdictMapping(unittest.TestCase):
    """Every decision row onto refresh's Verdict (open / done / unknown, or the
    two never-written words)."""

    ROWS = (
        (1, "unreadable", False, "", "unverified"),
        (2, "other_host", False, "unknown", "unknown"),
        (3, "alive", False, "done", "done"),
        (4, "unknown", False, "unknown", "unknown"),
        (5, "stale_lock", True, "open", "open"),
        (6, "crashed", True, "open", "open"),
        (7, "stale_lock", True, "open", "open"),
        (8, "orphan", True, "open", "open"),
        (9, "recovered", False, "done", "done"),
    )

    def test_every_row_from_open_and_unknown(self):
        for row, cat, stored, item_state, want in self.ROWS:
            v = _v(row, cat, stored, item_state)
            key = _REC if stored else None
            for old in ("open", "unknown"):
                got = sr.recovery_refresh_verdict(v, key, _REC, old, "some other outcome")
                self.assertEqual(got.state, want, (row, old))
                self.assertEqual(got.outcome, v.outcome, (row, old))

    def test_an_unreadable_input_is_never_done_or_unknown(self):
        got = sr.recovery_refresh_verdict(_v(1, "unreadable", False, "", "unreadable: x"),
                                          None, _REC, "open", "crashed · y")
        self.assertEqual(got.state, "unverified")
        self.assertNotIn(got.state, ("done", "unknown", "open"))

    def test_an_equal_verdict_is_unchanged(self):
        v = _v(6, "crashed", True, "open", "holder pid 9 is gone")
        got = sr.recovery_refresh_verdict(v, _REC, _REC, "open", v.outcome)
        self.assertEqual((got.state, got.outcome), ("unchanged", v.outcome))
        v = _v(4, "unknown", False, "unknown", "liveness unknown")
        got = sr.recovery_refresh_verdict(v, None, _REC, "unknown", v.outcome)
        self.assertEqual(got.state, "unchanged")

    def test_a_new_episode_belongs_to_the_detector(self):
        v = _v(6, "crashed", True, "open")
        got = sr.recovery_refresh_verdict(v, "fedcba987654", _REC, "open", "x")
        self.assertEqual((got.state, got.outcome), ("unverified", sr.NEW_EPISODE))
        # a state-only row carries no key: never an episode question
        got = sr.recovery_refresh_verdict(_v(3, "alive", False, "done"), None, _REC, "open", "x")
        self.assertEqual(got.state, "done")

    def test_no_recorded_incarnation_writes_nothing(self):
        for row, cat, stored, item_state, _want in self.ROWS[1:]:
            got = sr.recovery_refresh_verdict(_v(row, cat, stored, item_state),
                                              _REC if stored else None, "", "open", "x")
            self.assertEqual(got.state, "unverified", row)


class RecoveryCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._saved = (sc.read_locks, sc.read_active_tasks, sc._LIVENESS, sc._LOCAL_HOST)
        sc._LOCAL_HOST = "here"

        def restore():
            sc.read_locks, sc.read_active_tasks, sc._LIVENESS, sc._LOCAL_HOST = self._saved
        self.addCleanup(restore)

    def target(self, state="open", outcome="", incarnation=_REC):
        return sr.Target(7, 3, "task", state, outcome, "2026-11-01T00:00:00Z", "recovery",
                         ref="recover:t10", incarnation=incarnation)

    def test_unreadable_inputs_are_unverified_for_every_target(self):
        calls = []

        def boom(root):
            calls.append(root)
            raise sc.SourceError("lock_tree_unreadable")
        sc.read_locks = boom
        checker = sr.Checker(self.tmp)
        for _ in range(2):
            v = checker.check(self.target())
            self.assertEqual(v.state, "unverified")
            self.assertIn("lock_tree_unreadable", v.outcome)
        self.assertEqual(len(calls), 1, "the inputs are read once per run")

    def test_a_dead_holder_on_an_implementing_task(self):
        lock = sc.LockRec("10", {"task_id": "10", "hostname": "here", "pid": "4242",
                                 "pid_starttime": "1", "pid_starttime_kind": "proc"})
        sc.read_locks = lambda root: {"10": lock}
        sc.read_active_tasks = lambda root: {"10": sc.TaskRec("10", "active", status="Implementing")}
        sc._LIVENESS = lambda pid, start, kind: "dead"
        key = sc.episode_key("10", lock, _REC)
        v = sr.Checker(self.tmp).check(self.target(incarnation=key))
        self.assertEqual(v.state, "open")
        self.assertEqual(v.outcome, "crashed · holder pid 4242 is gone")
        # the same facts against the stored outcome: nothing to write
        v2 = sr.Checker(self.tmp).check(self.target(outcome=v.outcome, incarnation=key))
        self.assertEqual(v2.state, "unchanged")
        # a recorded incarnation from an older claim: the detector's
        v3 = sr.Checker(self.tmp).check(self.target(incarnation=_REC))
        self.assertEqual((v3.state, v3.outcome), ("unverified", sr.NEW_EPISODE))


class AttemptLedger(unittest.TestCase):
    def rt(self, n, check, checked_at):
        return sr.Target(n, n, "task", "open", "", checked_at, check)

    def test_recovery_targets_order_by_attempt_not_checked_at(self):
        ts = [self.rt(1, "recovery", "never"), self.rt(2, "task", "2026-11-02T00:00:00Z"),
              self.rt(3, "recovery", "2020-01-01T00:00:00Z"), self.rt(4, "recovery", "never")]
        attempts = {1: "2026-11-03T00:00:00Z", 3: "2026-11-01T00:00:00Z"}
        got = [t.num for t in sr.order_targets(ts, attempts)]
        self.assertEqual(got, [4, 3, 2, 1])

    def test_without_a_ledger_recovery_orders_by_checked_at(self):
        ts = [self.rt(1, "recovery", "2026-11-03T00:00:00Z"),
              self.rt(2, "task", "2026-11-02T00:00:00Z")]
        self.assertEqual([t.num for t in sr.order_targets(ts)], [2, 1])

    def test_merge_stamps_reached_and_prunes_old(self):
        old = {1: "2026-11-01T00:00:00Z", 2: "2026-11-09T00:00:00Z", 3: "2026-11-15T00:00:00Z"}
        got = sr.merge_attempts(old, [3, 4], "2026-11-16T00:00:00Z")
        self.assertEqual(got, {2: "2026-11-09T00:00:00Z", 3: "2026-11-16T00:00:00Z",
                               4: "2026-11-16T00:00:00Z"})

    def test_read_never_raises_and_drops_bad_entries(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, "a.json")
        self.assertEqual(sr.read_attempts(p), {})          # absent
        self.assertEqual(sr.read_attempts(""), {})
        for text in ("garbage", "[]", '{"version": 2, "attempts": {}}',
                     '{"version": 1, "attempts": []}', "\xff"):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertEqual(sr.read_attempts(p), {}, text)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write('{"version": 1, "attempts": {"3": "2026-11-16T00:00:00Z", '
                     '"0": "2026-11-16T00:00:00Z", "x": "2026-11-16T00:00:00Z", '
                     '"5": "yesterday", "6": 7}}')
        self.assertEqual(sr.read_attempts(p), {3: "2026-11-16T00:00:00Z"})
        # a key past int()'s digit limit, and nesting past the JSON parser's
        # recursion limit, are malformed too -- never an exception
        with open(p, "w", encoding="utf-8") as fh:
            fh.write('{"version": 1, "attempts": {"%s": "2026-11-16T00:00:00Z", '
                     '"4": "2026-11-16T00:00:00Z"}}' % ("1" * 4500))
        self.assertEqual(sr.read_attempts(p), {4: "2026-11-16T00:00:00Z"})
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("[" * 200000)
        self.assertEqual(sr.read_attempts(p), {})

    def test_write_round_trip(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, "aitask-sitrep", "refresh_attempts.json")
        sr.write_attempts(p, {5: "2026-11-16T00:00:00Z", 2: "2026-11-15T00:00:00Z"})
        self.assertEqual(sr.read_attempts(p), {2: "2026-11-15T00:00:00Z", 5: "2026-11-16T00:00:00Z"})
        self.assertEqual(os.listdir(os.path.dirname(p)), ["refresh_attempts.json"])

    def test_the_path_lives_under_the_git_common_dir(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        subprocess.run(["git", "init", "-q", d], check=True)
        got = sr.attempts_path(d)
        self.assertEqual(got, os.path.join(os.path.realpath(d), ".git", "aitask-sitrep",
                                           "refresh_attempts.json"))
        self.assertIsNone(sr.attempts_path(os.path.join(d, "missing")))


class RecoveryStream(unittest.TestCase):
    def feed(self, *lines):
        s = sr.Stream()
        for ln in lines:
            s.feed(ln)
        return s

    def test_skip_states_only_after_a_recovery_start(self):
        s = self.feed("ROOT:/r", "ATTEMPTS:/r/.git/aitask-sitrep/refresh_attempts.json",
                      "TARGETS:2",
                      "START:c1|1|recovery|open|crashed · x", "VERDICT:c1|unchanged|crashed · x",
                      "START:c2|2|recovery|open|crashed · y", "VERDICT:c2|unverified|unreadable: z")
        self.assertEqual(s.attempts, "/r/.git/aitask-sitrep/refresh_attempts.json")
        lines = s.close(interrupted=False, budget=5)
        self.assertEqual([(ln.state, ln.skipped) for ln in lines],
                         [("unchanged", True), ("unverified", True)])
        for kind in ("task", "action", "watch"):
            for word in sr.SKIP_STATES:
                with self.assertRaises(sr.ProtocolError, msg=(kind, word)):
                    self.feed("ROOT:/r", "TARGETS:1", f"START:c1|1|{kind}|open|",
                              f"VERDICT:c1|{word}|x")

    def test_attempts_line_only_between_root_and_targets(self):
        for bad in (["ATTEMPTS:/x"],
                    ["ROOT:/r", "TARGETS:1", "ATTEMPTS:/x"],
                    ["ROOT:/r", "ATTEMPTS:relative/x"],
                    ["ROOT:/r", "ATTEMPTS:/x", "ATTEMPTS:/y"]):
            with self.assertRaises(sr.ProtocolError, msg=bad):
                self.feed(*bad)

    def test_an_interrupted_recovery_target_is_unverified(self):
        s = self.feed("ROOT:/r", "TARGETS:2", "START:c4|9|recovery|open|crashed · x")
        (ln,) = s.close(interrupted=True, budget=8)
        self.assertEqual((ln.state, ln.skipped, ln.interrupted), ("unverified", True, True))
        self.assertEqual(ln.outcome, "check did not finish within the 8s budget")


if __name__ == "__main__":
    unittest.main(verbosity=2)
