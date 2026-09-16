"""Producer-to-adapter parity for the task-description surface (t1688_1).

Two producers build an in-flight task's surface. The live collector
(`parallel_admission_collect.collect`) classifies against the code AND the
task-data corpora. The trail gatherer (`trail_gather.emit_inflight`) sees the
code branch only and hands its records to
`parallel_admission.surfaces_from_inflight_records`, which holds the task-data
corpus. Adapter-only tests cannot catch evidence the gatherer DISCARDS upstream,
so this drives the real gatherer over a real git repo and asserts that it and
the collector agree on `(paths, resolution, provenance)` -- for
description-derived surfaces and, as the closed blind spot, for a plan that
proposes a new task-data file.
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, ".aitask-scripts", "lib"))

import parallel_admission as pa               # noqa: E402
import parallel_admission_collect as col      # noqa: E402
import plan_paths                             # noqa: E402
import trail_gather                           # noqa: E402

PROJECT = "proj"
NOW = 1_800_000_000
CODE = "src/real.py"
TRACKED_DATA = "aitasks/metadata/profiles/fast.yaml"
NEW_DATA = "aitasks/metadata/profiles/custom.yaml"
DATA_DIRS = {"aitasks", "aitasks/metadata", "aitasks/metadata/profiles"}


class TaskDeclaredParityTests(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pa_parity_"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
               "GIT_CONFIG_SYSTEM": os.devnull}

        def git(*args):
            subprocess.run(["git", "-C", str(self.root), *args], check=True,
                           env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "T")
        (self.root / "src").mkdir()
        (self.root / CODE).write_text("x\n", encoding="utf-8")
        git("add", CODE)
        git("commit", "-q", "-m", "init")
        # aitasks/ and aiplans/ exist on disk but are NOT tracked on this code
        # branch -- the real layout, where they are gitignored symlinks.
        (self.root / "aitasks" / "metadata" / "profiles").mkdir(parents=True)
        (self.root / "aiplans").mkdir()

        self._save(trail_gather, ("_GATE_PROBE", "_LOCK_PROBE"))
        self._save(col, ("_GATE_PROBE", "_LOCK_PROBE", "_STATUS_PROBE",
                         "_DATA_TREE"))
        trail_gather._GATE_PROBE = self._gatherer_source(
            "gate", {"100": ("PLAN", "NO_GATES")})
        trail_gather._LOCK_PROBE = self._gatherer_source("lock", {})
        col._GATE_PROBE = lambda root: (pa.SourceEvidence("gate"), {"100": {}})
        col._LOCK_PROBE = lambda root: (pa.SourceEvidence("lock"), {})
        col._STATUS_PROBE = lambda root, **kw: (pa.SourceEvidence("status"), {})

    def _save(self, module, names):
        saved = {n: getattr(module, n) for n in names}

        def restore():
            for name, value in saved.items():
                setattr(module, name, value)
        self.addCleanup(restore)

    @staticmethod
    def _gatherer_source(name, ids):
        def probe(root):
            res = trail_gather.SourceResult(name)
            res.ids = dict(ids)
            res.status, res.age, res.reason = "ok", None, None
            return res
        return probe

    def _write_task(self, body):
        (self.root / "aitasks" / "t100_x.md").write_text(
            "---\nstatus: Implementing\npriority: high\neffort: low\n---\n\n"
            + body, encoding="utf-8")

    def _write_plan(self, body):
        (self.root / "aiplans" / "p100_x.md").write_text(body, encoding="utf-8")

    def _gatherer(self, data_tracked, data_dirs):
        tree = trail_gather.load_tree(PROJECT, self.root, is_local=False)
        out = io.StringIO()
        trail_gather.emit_inflight(out, tree, {}, PROJECT)
        lines = [l for l in out.getvalue().splitlines()
                 if l.startswith("INFLIGHT_PATH:")]
        self.assertTrue(lines, "the gatherer must classify the in-flight task")
        s = pa.surfaces_from_inflight_records(
            lines, local_name=PROJECT, data_tracked=set(data_tracked),
            data_dirs=set(data_dirs), classify=plan_paths.classify)["100"]
        return (s.paths, s.resolution, s.provenance)

    def _collector(self, data_tracked, data_dirs):
        col._DATA_TREE = lambda root: (set(data_tracked), set(data_dirs), None)
        base = col.collect(str(self.root), "999", source="plan",
                           freshness="allow-cached", batch_lines=[], now=NOW)
        s = {c.ref: c for c in base.inflight}["100"].surface
        return (s.paths, s.resolution, s.provenance)

    def assert_parity(self, data_tracked, data_dirs, expected):
        gathered = self._gatherer(data_tracked, data_dirs)
        collected = self._collector(data_tracked, data_dirs)
        self.assertEqual(gathered, collected, "the two producers disagree")
        self.assertEqual(collected, expected)

    # -- description-derived ------------------------------------------------

    def test_a_description_naming_a_tracked_task_data_file(self):
        self._write_task("Tune `%s`.\n" % TRACKED_DATA)
        self.assert_parity({TRACKED_DATA}, DATA_DIRS,
                           ((TRACKED_DATA,), "resolved", "task_declared"))

    def test_control_the_same_file_outside_the_data_corpus_is_no_plan(self):
        self._write_task("Tune `%s`.\n" % TRACKED_DATA)
        self.assert_parity(set(), set(), ((), "no_plan", "plan_declared"))

    def test_a_description_proposing_a_new_file_under_a_data_directory(self):
        self._write_task("Add `%s`.\n" % NEW_DATA)
        self.assert_parity({TRACKED_DATA}, DATA_DIRS,
                           ((NEW_DATA,), "resolved", "task_declared"))

    def test_control_a_new_file_under_an_untracked_directory_is_no_plan(self):
        self._write_task("Add `%s`.\n" % NEW_DATA)
        self.assert_parity({TRACKED_DATA}, {"aitasks", "aitasks/metadata"},
                           ((), "no_plan", "plan_declared"))

    def test_a_description_naming_a_code_path(self):
        self._write_task("Refactor `%s`.\n" % CODE)
        self.assert_parity(set(), set(), ((CODE,), "resolved", "task_declared"))

    # -- plan-derived -------------------------------------------------------

    def test_a_plan_proposing_a_new_task_data_file_resolves_on_both(self):
        """The adapter's pre-existing blind spot, closed by the classifier."""
        self._write_task("A description that names no path.\n")
        self._write_plan("# t100\n\nAdd `%s`.\n" % NEW_DATA)
        self.assert_parity({TRACKED_DATA}, DATA_DIRS,
                           ((NEW_DATA,), "resolved", "plan_declared"))

    def test_a_plan_beats_the_description_on_both(self):
        self._write_task("Refactor `%s`.\n" % CODE)
        self._write_plan("# t100\n\nTune `%s`.\n" % TRACKED_DATA)
        self.assert_parity({TRACKED_DATA}, DATA_DIRS,
                           ((TRACKED_DATA,), "resolved", "plan_declared"))


if __name__ == "__main__":
    unittest.main()
