#!/usr/bin/env python3
"""Tests for the trail discovery cache (lib/trail_discovery_cache.py, t2173_1).

Every test runs discovery over a synthetic tree that is cwd, with its own
``AIT_TRAIL_CACHE_DIR``. Covered:

- owner layer: hit/miss table (unchanged, edited, new, removed, renamed, bundle
  unchanged/changed, folded/archived state changes), measured in real parses
  and bundle decompressions;
- faulty units are never cached and are reported on every scan — including a
  best-effort scan followed by a diagnostic one over the same faulty input;
- doc layer: hit/miss table against a fake ``artifact get`` and a real
  manifest; a warmed cache never survives a manifest ``get`` would reject; the
  non-exiting ``artifact_manifest`` interface agrees with the CLI;
- ``proven_manifest_dir`` agrees with bash ``artifact_manifest_dir``;
- corrupt cache files, ``AIT_TRAIL_CACHE=0``, ``read_seq`` / lock ordering and
  the read-only contract;
- identities are bound to the loaded code: a process that imported the old code
  cannot populate entries a process on the new code accepts (two real
  subprocesses over a copy of lib/);
- empty discovery never builds a thread pool;
- a scripted mutation sequence where cached and uncached discovery must agree
  after every step.

Run: python3 tests/test_trail_discovery_cache.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB_DIR))

import archive_iter  # noqa: E402
import artifact_manifest  # noqa: E402
import trail_discovery as td  # noqa: E402
import trail_discovery_cache as tdc  # noqa: E402
import trail_schema  # noqa: E402

FIXTURE_DOC = json.loads(
    (REPO_ROOT / "aidocs" / "implementation_trail_examples"
     / "gate_framework.json").read_text(encoding="utf-8"))


def _doc(title):
    doc = copy.deepcopy(FIXTURE_DOC)
    doc["title"] = title
    return doc


def _task_text(handles=(), *, status="Ready", folded_into=None, name="N"):
    lines = ["---", f"status: {status}"]
    if folded_into is not None:
        lines.append(f"folded_into: {folded_into}")
    if handles:
        lines.append("artifacts:")
        for handle in handles:
            lines += [f"- handle: {handle}", "  kind: implementation_trail",
                      f"  name: {name}"]
    lines += ["---", "", "body", ""]
    return "\n".join(lines)


def _tar(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for member, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


#: Bound at import: the doc-layer tests patch ``subprocess.run`` with the fake
#: store, and building a bundle must still reach the real ``zstd``.
_REAL_RUN = subprocess.run


def _write_bundle(path, files, trailer=b""):
    path.parent.mkdir(parents=True, exist_ok=True)
    zst = _REAL_RUN(["zstd", "-q", "-c"], input=_tar(files),
                    capture_output=True, check=True).stdout
    path.write_bytes(zst + trailer)


def _summary(infos):
    """Everything discovery reports per handle, comparable across runs."""
    return {i.handle: (i.owner_id, i.owner_archived, i.owner_folded, i.name,
                       i.load_error, json.dumps(i.doc, sort_keys=True),
                       list(i.versions)) for i in infos}


BAD_FM = "---\npriority: [unclosed\n---\n"


class FakeStore:
    """A fake ``aitask_artifact.sh`` over REAL manifest files: ``get``
    validates the manifest exactly like the CLI, then writes the blob."""

    def __init__(self, manifest_dir: Path):
        self.manifest_dir = manifest_dir
        self.blobs: dict = {}
        self.argv: list = []
        self.fail_get: set = set()
        self._lock = threading.Lock()

    def path(self, handle):
        return self.manifest_dir / (handle[len("art:"):] + ".json")

    def publish(self, handle, doc, raw=None):
        raw = raw if raw is not None else json.dumps(doc).encode("utf-8")
        h = "sha256:" + hashlib.sha256(raw).hexdigest()
        self.blobs[h] = raw
        rec = {"handle": handle, "current": h, "versions": [h],
               "backend": "local", "created_at": 1, "updated_at": 1}
        if self.path(handle).exists():
            old = json.loads(self.path(handle).read_text())
            rec["versions"] = old["versions"] + (
                [] if h in old["versions"] else [h])
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self.path(handle).write_text(json.dumps(rec))
        return h

    def gets(self):
        return sum(1 for a in self.argv if a[1] == "get")

    def run(self, cmd, **kw):
        cmd = list(cmd)
        with self._lock:
            self.argv.append(cmd)
        verb, handle = cmd[1], cmd[2]
        try:
            rec = artifact_manifest.read_manifest(str(self.path(handle)))
        except artifact_manifest.ManifestError as exc:
            return subprocess.CompletedProcess(cmd, 1, "", f"{exc}\n")
        if rec is None or (verb == "get" and handle in self.fail_get):
            return subprocess.CompletedProcess(cmd, 1, "",
                                               f"no manifest for {handle}\n")
        if verb == "versions":
            return subprocess.CompletedProcess(
                cmd, 0, "".join(f"* {v}\n" for v in rec["versions"]), "")
        out = cmd[cmd.index("--out") + 1]
        Path(out).write_bytes(self.blobs[rec["current"]])
        return subprocess.CompletedProcess(cmd, 0, f"Wrote {out}\n", "")


class _Base(unittest.TestCase):
    """A synthetic project tree as cwd, with its own cache dir."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="trail_cache_")
        self.addCleanup(tmp.cleanup)
        self.tree = Path(tmp.name)
        self.tasks = self.tree / "aitasks"
        self.archived = self.tasks / "archived"
        self.archived.mkdir(parents=True)
        self.cache = self.tree / ".cache"
        original = os.getcwd()
        os.chdir(self.tree)
        self.addCleanup(os.chdir, original)
        env = patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ["AIT_TRAIL_CACHE_DIR"] = str(self.cache)
        for var in ("TASK_DIR", "AIT_TRAIL_CACHE", "GIT_DIR", "GIT_WORK_TREE"):
            os.environ.pop(var, None)
        self.parses = 0
        self.decompressions = 0
        real_parse = td.parse_frontmatter
        real_iter = archive_iter.iter_archive_file

        def counting_parse(text):
            self.parses += 1
            return real_parse(text)

        def counting_iter(*a, **kw):
            self.decompressions += 1
            return real_iter(*a, **kw)

        for target, name, repl in ((td, "parse_frontmatter", counting_parse),
                                   (archive_iter, "iter_archive_file",
                                    counting_iter)):
            p = patch.object(target, name, repl)
            p.start()
            self.addCleanup(p.stop)

    def write(self, rel, text):
        path = self.tasks / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def reset_counts(self):
        self.parses = 0
        self.decompressions = 0

    def owner_entries(self):
        path = self.cache / tdc.OWNERS_FILE
        if not path.exists():
            return {}
        return json.loads(path.read_text())["entries"]

    def doc_entries(self):
        path = self.cache / tdc.DOCS_FILE
        if not path.exists():
            return {}
        return json.loads(path.read_text())["entries"]


class _StubbedBlobs(_Base):
    """Owner-layer tests: blob loads stubbed (plain tuples are never cached)."""

    def setUp(self):
        super().setUp()
        p = patch.object(td, "load_trail_blob",
                         lambda h: ({"title": h}, "", []))
        p.start()
        self.addCleanup(p.stop)

    def scan(self, **kw):
        infos, unreadable = td.discover_trails(**kw)
        return _summary(infos), unreadable


class OwnerLayerTests(_StubbedBlobs):

    def setUp(self):
        super().setUp()
        self.write("t10_alpha.md", _task_text(["art:a"]))
        self.write("t11/t11_2_kid.md", _task_text(["art:b"]))
        self.write("t12_plain.md", _task_text())
        self.write("archived/t20_old.md", _task_text(["art:c"]))
        _write_bundle(self.archived / "_b0" / "old0.tar.zst", {
            "t30_bundled.md": _task_text(["art:d"]),
            "t31_plain.md": _task_text(),
        })
        self.cold = self.scan()
        self.reset_counts()

    def test_unchanged_tree_is_served_without_parsing(self):
        warm = self.scan()
        self.assertEqual(warm, self.cold)
        self.assertEqual((self.parses, self.decompressions), (0, 0))
        self.assertEqual(set(warm[0]), {"art:a", "art:b", "art:c", "art:d"})

    def test_files_owning_nothing_are_cached_too(self):
        keys = set(self.owner_entries())
        self.assertIn("active:t12_plain.md", keys)
        self.assertIn("archived:_b0/old0.tar.zst", keys)
        self.assertEqual(self.owner_entries()["active:t12_plain.md"]["records"],
                         [])

    def test_edited_file_is_reparsed(self):
        self.write("t10_alpha.md", _task_text(["art:a"], name="Renamed"))
        warm, _ = self.scan()
        self.assertEqual(warm["art:a"][3], "Renamed")
        self.assertEqual(self.parses, 1)

    def test_new_file_appears(self):
        self.write("t13_new.md", _task_text(["art:e"]))
        warm, _ = self.scan()
        self.assertEqual(warm["art:e"][0], "13")
        self.assertEqual(self.parses, 1)

    def test_removed_file_drops_out_and_its_entry_is_pruned(self):
        (self.tasks / "t10_alpha.md").unlink()
        warm, _ = self.scan()
        self.assertNotIn("art:a", warm)
        self.assertNotIn("active:t10_alpha.md", self.owner_entries())
        self.assertEqual(self.parses, 0)

    def test_renamed_file_with_the_same_content_follows_its_name(self):
        (self.tasks / "t10_alpha.md").rename(self.tasks / "t14_alpha.md")
        warm, _ = self.scan()
        self.assertEqual(warm["art:a"][0], "14")

    def test_bundle_unchanged_vs_changed(self):
        self.scan()
        self.assertEqual(self.decompressions, 0)
        _write_bundle(self.archived / "_b0" / "old0.tar.zst",
                      {"t30_bundled.md": _task_text(["art:d2"])})
        warm, _ = self.scan()
        self.assertEqual(self.decompressions, 1)
        self.assertIn("art:d2", warm)
        self.assertNotIn("art:d", warm)

    def test_folded_state_change_is_seen(self):
        self.write("t10_alpha.md", _task_text(["art:a"], status="Folded",
                                              folded_into=12))
        warm, _ = self.scan()
        self.assertTrue(warm["art:a"][2])

    def test_archiving_a_task_is_seen(self):
        (self.tasks / "t10_alpha.md").rename(self.archived / "t10_alpha.md")
        warm, _ = self.scan()
        self.assertTrue(warm["art:a"][1])

    def test_lookups_return_fresh_infos(self):
        infos, _ = td.discover_trails()
        infos[0].name = "MUTATED"
        again, _ = td.discover_trails()
        self.assertNotIn("MUTATED", [i.name for i in again])


class FaultyUnitTests(_StubbedBlobs):
    """A faulty unit is never cached, so it is reported on every scan."""

    def _faulty_archive(self):
        self.write("t40_live.md", _task_text(["art:live"]))
        bundles = self.archived / "_b0"
        bundles.mkdir(parents=True)
        (bundles / "old0.tar.zst").write_bytes(b"not zstd at all")
        _write_bundle(bundles / "old1.tar.zst",
                      {"t150_ok.md": _task_text(["art:t"])},
                      trailer=b"\x00trailing garbage")
        _write_bundle(bundles / "old2.tar.zst",
                      {"t250_bad.md": BAD_FM,
                       "t251_ok.md": _task_text(["art:u"])})
        return ["archived:_b0/old0.tar.zst", "archived:_b0/old1.tar.zst",
                "archived:_b0/old2.tar.zst"]

    def test_best_effort_scan_then_diagnostic_scan_over_the_same_input(self):
        faulty_keys = self._faulty_archive()
        first, _ = self.scan()                       # best-effort, no list
        self.assertTrue(set(faulty_keys).isdisjoint(self.owner_entries()))
        errs: list = []
        second, _ = self.scan(scan_errors=errs)
        names = " ".join(errs)
        self.assertIn("old0.tar.zst", names)
        self.assertIn("old1.tar.zst: zstd exited", names)
        self.assertIn("t250_bad.md: unparseable frontmatter", names)
        self.assertTrue(set(faulty_keys).isdisjoint(self.owner_entries()))
        self.assertEqual(first, second)
        self.assertIn("art:t", second)   # records before the failure still count

    def test_diagnostic_scans_report_faults_every_time(self):
        self._faulty_archive()
        for _ in range(2):
            errs: list = []
            self.scan(scan_errors=errs)
            self.assertEqual(len(errs), 3, errs)

    def test_scan_errors_match_the_uncached_scan(self):
        self._faulty_archive()
        self.write("archived/t5/t5_1_bad.md", BAD_FM)
        cached: list = []
        self.scan(scan_errors=cached)
        self.scan(scan_errors=[])
        warm: list = []
        self.scan(scan_errors=warm)
        with patch.dict(os.environ, {"AIT_TRAIL_CACHE": "0"}):
            uncached: list = []
            self.scan(scan_errors=uncached)
        self.assertEqual(cached, uncached)
        self.assertEqual(warm, uncached)

    def test_unreadable_active_file_is_reported_on_every_scan(self):
        self.write("t41_broken.md", BAD_FM)
        self.write("t42_empty.md", "")
        for _ in range(2):
            _, unreadable = self.scan()
            self.assertEqual(sorted(unreadable),
                             ["t41_broken.md", "t42_empty.md"])
        self.assertNotIn("active:t41_broken.md", self.owner_entries())

    def test_a_plain_record_scan_does_not_hide_it_from_discovery(self):
        self.write("t41_broken.md", BAD_FM)
        list(td._iter_trail_frontmatter_records(None))
        _, unreadable = self.scan()
        self.assertEqual(unreadable, ["t41_broken.md"])


class _DocBase(_Base):
    """A provable legacy layout (``.git`` dir in cwd) with a fake store."""

    def setUp(self):
        super().setUp()
        (self.tree / ".git").mkdir()
        self.store = FakeStore(self.tree / "artifacts" / "manifests")
        p = patch("subprocess.run", side_effect=self.store.run)
        p.start()
        self.addCleanup(p.stop)
        self.write("t10_alpha.md", _task_text(["art:trail-a"]))
        self.write("t11_beta.md", _task_text(["art:trail-b"]))
        self.store.publish("art:trail-a", _doc("Alpha"))
        self.store.publish("art:trail-b", _doc("Beta"))

    def scan(self, **kw):
        infos, unreadable = td.discover_trails(**kw)
        return {i.handle: i for i in infos}


class DocLayerTests(_DocBase):

    def test_second_scan_spawns_nothing_and_returns_an_equal_doc(self):
        cold = self.scan()
        self.assertEqual(self.store.gets(), 2)
        warm = self.scan()
        self.assertEqual(self.store.gets(), 2, "a warm scan spawned get")
        self.assertEqual(_summary(warm.values()), _summary(cold.values()))
        self.assertEqual(warm["art:trail-a"].doc["title"], "Alpha")

    def test_a_changed_current_is_a_miss(self):
        self.scan()
        self.store.publish("art:trail-a", _doc("Alpha v2"))
        warm = self.scan()
        self.assertEqual(self.store.gets(), 3)
        self.assertEqual(warm["art:trail-a"].doc["title"], "Alpha v2")
        self.assertEqual(warm["art:trail-b"].doc["title"], "Beta")

    def test_a_doc_identity_change_is_a_miss(self):
        self.scan()
        with patch.object(tdc, "DOC_IDENTITY", "another-generation"):
            self.scan()
        self.assertEqual(self.store.gets(), 4)

    def test_a_failing_get_is_never_cached(self):
        self.store.fail_get.add("art:trail-a")
        for expected_gets in (2, 3):
            infos = self.scan()
            self.assertIn("artifact unresolved",
                          infos["art:trail-a"].load_error)
            self.assertEqual(len(infos["art:trail-a"].versions), 1,
                             "the versions fallback did not run")
            self.assertEqual(self.store.gets(), expected_gets)
        self.assertEqual(
            sum(1 for a in self.store.argv if a[1] == "versions"), 2)
        self.assertNotIn("art:trail-a", self.doc_entries())
        self.assertIn("art:trail-b", self.doc_entries())

    def test_an_invalid_document_is_never_cached(self):
        self.store.publish("art:trail-a", None, raw=b'{"title": "nope"}')
        for expected_gets in (2, 3):
            infos = self.scan()
            self.assertIn("invalid trail document",
                          infos["art:trail-a"].load_error)
            self.assertEqual(self.store.gets(), expected_gets)
        self.assertNotIn("art:trail-a", self.doc_entries())

    def test_a_plain_tuple_loader_is_never_stored(self):
        with patch.object(td, "load_trail_blob",
                          lambda h: (_doc("stub"), "", [])):
            self.scan()
        self.assertEqual(self.doc_entries(), {})

    def test_unproven_layouts_turn_the_layer_off(self):
        shutil.rmtree(self.tree / ".git")
        (self.tree / ".git").write_text("gitdir: /elsewhere\n")
        self.scan()
        self.scan()
        self.assertEqual(self.store.gets(), 4)
        self.assertFalse((self.cache / tdc.DOCS_FILE).exists())
        (self.tree / ".git").unlink()
        self.scan()
        self.assertEqual(self.store.gets(), 6)

    def test_reads_are_sequenced_and_the_manifest_is_read_under_the_lock(self):
        self.scan()
        held = []
        real = tdc.manifest_current

        def checking(handle, manifest_dir=None):
            held.append(td._trail_read_lock(handle).locked())
            return real(handle, manifest_dir)

        with patch.object(tdc, "manifest_current", checking):
            warm = self.scan()
        self.assertEqual(held, [True, True])
        seqs = [i.read_seq for i in warm.values()]
        self.assertTrue(all(s > 0 for s in seqs), seqs)
        self.assertEqual(len(set(seqs)), 2)

    def test_only_read_verbs_are_spawned(self):
        self.store.fail_get.add("art:trail-b")
        self.scan()
        self.scan()
        verbs = {a[1] for a in self.store.argv}
        self.assertTrue(verbs <= {"get", "versions"}, verbs)
        self.assertIn("versions", verbs)


#: One manifest mutation per ``validate`` invariant (current left unchanged).
def _break(kind):
    def mutate(rec):
        rec = dict(rec)
        if kind == "backend":
            rec["backend"] = "bad/name"
        elif kind == "missing_updated_at":
            del rec["updated_at"]
        elif kind == "string_created_at":
            rec["created_at"] = "1"
        elif kind == "duplicate_versions":
            rec["versions"] = rec["versions"] * 2
        elif kind == "invalid_version_hash":
            rec["versions"] = rec["versions"] + ["sha256:XYZ"]
        elif kind == "handle_mismatch":
            rec["handle"] = "art:someone-else"
        elif kind == "not_an_object":
            rec = [rec]
        return rec
    return mutate


INVARIANT_CASES = ["backend", "missing_updated_at", "string_created_at",
                   "duplicate_versions", "invalid_version_hash",
                   "handle_mismatch", "not_an_object", "invalid_json"]


class MalformedManifestTests(_DocBase):
    """A warmed cache never serves a document for a manifest ``get`` rejects."""

    def _corrupt(self, kind):
        path = self.store.path("art:trail-a")
        if kind == "invalid_json":
            path.write_text("{not json")
            return
        rec = json.loads(path.read_text())
        path.write_text(json.dumps(_break(kind)(rec)))

    def test_each_invariant_violation_is_a_miss(self):
        for kind in INVARIANT_CASES:
            with self.subTest(kind=kind):
                self.store.publish("art:trail-a", _doc("Alpha"))
                self.scan()
                before = self.store.gets()
                self.scan()
                self.assertEqual(self.store.gets(), before, "not warmed")
                self._corrupt(kind)
                infos = self.scan()
                self.assertEqual(self.store.gets(), before + 1,
                                 "the real get was not spawned")
                self.assertIn("artifact unresolved",
                              infos["art:trail-a"].load_error)
                self.assertIsNone(infos["art:trail-a"].doc)
                self.store.path("art:trail-a").unlink()


class ManifestInterfaceParityTests(unittest.TestCase):
    """``manifest_violation`` / ``read_manifest`` agree with the dying CLI."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        h = "sha256:" + "a" * 64
        self.good = {"handle": "art:x", "current": h, "versions": [h],
                     "backend": "local", "created_at": 1, "updated_at": 2}

    def _cli(self, path):
        return subprocess.run(
            [sys.executable, str(LIB_DIR / "artifact_manifest.py"),
             "--manifest-dir", str(path.parent), "get", "art:x"],
            capture_output=True, text=True)

    def test_valid_manifest(self):
        path = self.dir / "x.json"
        path.write_text(json.dumps(self.good))
        self.assertIsNone(artifact_manifest.manifest_violation(self.good,
                                                               str(path)))
        self.assertEqual(artifact_manifest.read_manifest(str(path)), self.good)
        self.assertEqual(self._cli(path).returncode, 0)

    def test_absent_manifest(self):
        self.assertIsNone(artifact_manifest.read_manifest(
            str(self.dir / "x.json")))

    def test_each_violation_matches_the_cli(self):
        for kind in INVARIANT_CASES:
            with self.subTest(kind=kind):
                path = self.dir / "x.json"
                if kind == "invalid_json":
                    path.write_text("{not json")
                else:
                    rec = _break(kind)(self.good)
                    path.write_text(json.dumps(rec))
                    self.assertIsNotNone(
                        artifact_manifest.manifest_violation(rec, str(path)))
                with self.assertRaises(artifact_manifest.ManifestError) as cm:
                    artifact_manifest.read_manifest(str(path))
                cli = self._cli(path)
                self.assertEqual(cli.returncode, 1)
                self.assertEqual(cli.stderr.strip(),
                                 "artifact_manifest.py: " + str(cm.exception))
                self.assertIn("-- repair or remove it", cli.stderr)


class ProvenManifestDirParityTests(unittest.TestCase):
    """The Python prover agrees with bash ``artifact_manifest_dir`` wherever it
    answers at all."""

    def _bash(self, cwd):
        script = (f'source "{LIB_DIR}/task_utils.sh"; '
                  f'source "{LIB_DIR}/artifact_manifest.sh"; '
                  'artifact_manifest_dir')
        env = {k: v for k, v in os.environ.items()
               if k not in ("GIT_DIR", "GIT_WORK_TREE")}
        return subprocess.run(["bash", "-c", script], cwd=cwd, env=env,
                              capture_output=True, text=True,
                              check=True).stdout.strip()

    def _python(self, cwd):
        original = os.getcwd()
        os.chdir(cwd)
        try:
            return tdc.proven_manifest_dir()
        finally:
            os.chdir(original)

    def test_branch_mode_and_legacy_layouts(self):
        for layout in ("branch", "legacy"):
            with self.subTest(layout=layout), \
                    tempfile.TemporaryDirectory() as tmp:
                subprocess.run(["git", "init", "-q", tmp], check=True)
                if layout == "branch":
                    (Path(tmp) / ".aitask-data" / ".git").mkdir(parents=True)
                py = self._python(tmp)
                self.assertIsNotNone(py)
                self.assertEqual(os.path.normpath(py),
                                 os.path.normpath(self._bash(tmp)))

    def test_unprovable_layouts_answer_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self._python(tmp))          # no repository
            (Path(tmp) / ".git").write_text("gitdir: x\n")  # linked worktree
            self.assertIsNone(self._python(tmp))


class CacheFileRobustnessTests(_DocBase):

    def _expected(self):
        with patch.dict(os.environ, {"AIT_TRAIL_CACHE": "0"}):
            return _summary(self.scan().values())

    def test_corrupt_cache_files_are_a_miss_and_get_rewritten(self):
        expected = self._expected()
        bad_contents = [b"garbage", b'{"format": 1, "identity"', b"[]",
                        json.dumps({"format": 1, "identity": "x",
                                    "entries": {}}).encode(),
                        json.dumps({"format": 99, "entries": {}}).encode(),
                        json.dumps({"format": 1,
                                    "identity": tdc.OWNER_IDENTITY,
                                    "entries": []}).encode()]
        for content in bad_contents:
            with self.subTest(content=content[:30]):
                self.cache.mkdir(exist_ok=True)
                for name in (tdc.OWNERS_FILE, tdc.DOCS_FILE):
                    (self.cache / name).write_bytes(content)
                self.assertEqual(_summary(self.scan().values()), expected)
                owners = json.loads((self.cache / tdc.OWNERS_FILE).read_text())
                docs = json.loads((self.cache / tdc.DOCS_FILE).read_text())
                self.assertEqual(owners["identity"], tdc.OWNER_IDENTITY)
                self.assertEqual(docs["identity"], tdc.DOC_IDENTITY)
                self.assertTrue(owners["entries"])

    def test_malformed_entries_are_a_miss(self):
        self.scan()
        path = self.cache / tdc.OWNERS_FILE
        data = json.loads(path.read_text())
        data["entries"]["active:t10_alpha.md"]["records"] = [["x"]]
        path.write_text(json.dumps(data))
        docs = json.loads((self.cache / tdc.DOCS_FILE).read_text())
        docs["entries"]["art:trail-b"]["raw"] = ["not", "text"]
        (self.cache / tdc.DOCS_FILE).write_text(json.dumps(docs))
        self.assertEqual(_summary(self.scan().values()), self._expected())

    def test_disabled_cache_writes_nothing(self):
        with patch.dict(os.environ, {"AIT_TRAIL_CACHE": "0"}):
            self.scan()
            self.scan()
        self.assertFalse(self.cache.exists())
        self.assertEqual(self.store.gets(), 4)

    def test_an_unwritable_cache_dir_is_not_an_error(self):
        self.cache.write_text("a file where the directory should be")
        self.assertEqual(_summary(self.scan().values()), self._expected())


class DocEntryIntegrityTests(_DocBase):
    """A doc-layer hit is re-proved from the entry's own bytes: they must hash
    to the manifest's ``current`` and validate. A corrupted or forged entry of
    ANY shape — with ``blob`` and the layer identity left intact — is a miss
    that falls back to the real ``get``, never a document served."""

    def _forge(self, handle, raw_text):
        path = self.cache / tdc.DOCS_FILE
        docs = json.loads(path.read_text())
        docs["entries"][handle]["raw"] = raw_text
        path.write_text(json.dumps(docs))

    def _expected(self):
        with patch.dict(os.environ, {"AIT_TRAIL_CACHE": "0"}):
            return _summary(self.scan().values())

    def test_dict_shaped_corruption_is_a_miss(self):
        forgeries = {
            "waves of a non-dict": '{"waves": [0]}',
            "empty document": "{}",
            "another valid trail": json.dumps(_doc("Beta")),
            "deeply nested": "[" * 200000 + "]" * 200000,
            "lone surrogate": "\ud800",
            "not JSON": "{",
        }
        for label, forged in forgeries.items():
            with self.subTest(label=label):
                self.scan()                    # warm (and repair) the entry
                before = self.store.gets()
                self._forge("art:trail-a", forged)
                infos = self.scan()
                self.assertEqual(self.store.gets(), before + 1,
                                 "the forged entry was served")
                self.assertEqual(infos["art:trail-a"].doc["title"], "Alpha")
                self.assertEqual(infos["art:trail-a"].load_error, "")
                td.compute_trail_overlaps(list(infos.values()))
                self.assertEqual(_summary(infos.values()), self._expected())

    def test_the_real_blob_bytes_are_still_revalidated(self):
        """An entry whose bytes ARE the manifest's blob is still validated:
        a schema-invalid blob forged into the cache is not served."""
        bad = b'{"title": "not a trail"}'
        current = self.store.publish("art:trail-a", None, raw=bad)
        self.scan()                            # get fails validation: no entry
        path = self.cache / tdc.DOCS_FILE
        docs = json.loads(path.read_text())
        docs["entries"]["art:trail-a"] = {"blob": current,
                                          "raw": bad.decode("utf-8")}
        path.write_text(json.dumps(docs))
        before = self.store.gets()
        infos = self.scan()
        self.assertEqual(self.store.gets(), before + 1)
        self.assertIn("invalid trail document",
                      infos["art:trail-a"].load_error)

    def test_hits_are_parsed_fresh_each_time(self):
        self.scan()
        first = self.scan()["art:trail-a"].doc
        first["title"] = "MUTATED"
        self.assertEqual(self.scan()["art:trail-a"].doc["title"], "Alpha")


class EmptyDiscoveryTests(_Base):
    """Zero trails never build a thread pool (``max_workers=0`` raises)."""

    def setUp(self):
        super().setUp()

        def no_pool(*a, **kw):
            raise AssertionError("a thread pool was built")

        p = patch.object(td, "ThreadPoolExecutor", no_pool)
        p.start()
        self.addCleanup(p.stop)
        stub = patch.object(td, "load_trail_blob",
                            lambda h: ({"title": h}, "", []))
        stub.start()
        self.addCleanup(stub.stop)

    def _both_modes(self):
        for mode in ("1", "0"):
            with self.subTest(cache=mode), \
                    patch.dict(os.environ, {"AIT_TRAIL_CACHE": mode}):
                yield

    def test_empty_tree(self):
        for _ in self._both_modes():
            errs: list = []
            self.assertEqual(td.discover_trails(scan_errors=errs), ([], []))
            self.assertEqual(errs, [])

    def test_every_owner_unreadable(self):
        self.write("t1_bad.md", BAD_FM)
        self.write("t2_empty.md", "")
        for _ in self._both_modes():
            infos, unreadable = td.discover_trails()
            self.assertEqual(infos, [])
            self.assertEqual(sorted(unreadable), ["t1_bad.md", "t2_empty.md"])

    def test_last_owner_removed_after_a_warm_scan(self):
        self.write("t1_only.md", _task_text(["art:only"]))
        infos, _ = td.discover_trails()
        self.assertEqual([i.handle for i in infos], ["art:only"])  # 1: inline
        (self.tasks / "t1_only.md").unlink()
        for _ in self._both_modes():
            self.assertEqual(td.discover_trails(), ([], []))

    def test_the_existing_empty_tree_test_passes_in_both_modes(self):
        sys.path.insert(0, str(REPO_ROOT / "tests"))
        self.addCleanup(sys.path.remove, str(REPO_ROOT / "tests"))
        import test_trail_discovery as ttd
        for _ in self._both_modes():
            result = unittest.TestResult()
            ttd.DiscoveryTests(
                "test_empty_tree_reports_no_trails_and_no_failures").run(result)
            self.assertTrue(result.wasSuccessful(),
                            result.failures + result.errors)


class FrozenSchemaTests(unittest.TestCase):
    """``load_trail(schema=)`` validates with the given schema, not a re-read."""

    def test_a_given_schema_is_what_validates(self):
        raw = json.dumps(FIXTURE_DOC).encode("utf-8")
        strict = copy.deepcopy(tdc.FROZEN_SCHEMA)
        strict["required"] = list(strict["required"]) + ["zzz_required"]
        with self.assertRaises(trail_schema.TrailValidationError):
            trail_schema.load_trail(raw, schema=strict)
        self.assertEqual(trail_schema.load_trail(raw, schema=tdc.FROZEN_SCHEMA),
                         FIXTURE_DOC)
        with patch.object(trail_schema, "load_schema",
                          side_effect=AssertionError("re-read")):
            trail_schema.load_trail(raw, schema=tdc.FROZEN_SCHEMA)

    def test_frozen_schema_is_the_shipped_schema(self):
        self.assertEqual(tdc.FROZEN_SCHEMA, trail_schema.load_schema())

    def test_load_schema_messages_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps({"title": "Other"}))
            with self.assertRaisesRegex(RuntimeError,
                                        "not the Implementation Trail schema"):
                trail_schema.load_schema(str(path))
            path.write_text(json.dumps({"title": "Implementation Trail"}))
            with self.assertRaisesRegex(RuntimeError,
                                        "missing schema_version const"):
                trail_schema.load_schema(str(path))


_GENERATION_RUNNER = textwrap.dedent('''
    import json, os, subprocess, sys
    from pathlib import Path
    lib, edit = sys.argv[1], sys.argv[2]
    sys.path.insert(0, lib)
    import trail_discovery as td
    import trail_discovery_cache as tdc
    import artifact_manifest
    pre = [tdc.owner_identity(), tdc.doc_identity()]
    if edit == "owner":
        p = Path(lib) / "trail_discovery.py"
        old = 'str(rec.get("name") or "")))'
        src = p.read_text()
        assert src.count(old) == 1, "owner edit target moved"
        p.write_text(src.replace(old, 'str(rec.get("name") or "") + "+NEW"))'))
    elif edit == "schema":
        p = Path(lib) / "implementation_trail.schema.json"
        schema = json.loads(p.read_text())
        schema["required"].append("zzz_required")
        p.write_text(json.dumps(schema))
    gets = []
    parses = []
    real_parse = td.parse_frontmatter
    td.parse_frontmatter = lambda t: (parses.append(1), real_parse(t))[1]
    def run(cmd, **kw):
        cmd = list(cmd)
        manifest = Path("artifacts/manifests") / (cmd[2][4:] + ".json")
        rec = artifact_manifest.read_manifest(str(manifest))
        if cmd[1] == "versions":
            return subprocess.CompletedProcess(cmd, 0, "* " + rec["current"], "")
        gets.append(cmd[2])
        Path(cmd[cmd.index("--out") + 1]).write_bytes(
            Path("blobs", rec["current"][7:]).read_bytes())
        return subprocess.CompletedProcess(cmd, 0, "", "")
    subprocess.run = run
    infos, _ = td.discover_trails()
    print(json.dumps({
        "pre": pre, "post": [tdc.owner_identity(), tdc.doc_identity()],
        "gets": len(gets), "parses": len(parses),
        "infos": {i.handle: [i.name, i.load_error,
                             (i.doc or {}).get("title")] for i in infos}}))
''')


class IdentityGenerationTests(unittest.TestCase):
    """A process that imported the OLD code cannot populate cache entries that
    a process on the NEW code accepts (identities are frozen at import)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="trail_cache_gen_")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.lib = root / "lib"
        shutil.copytree(LIB_DIR, self.lib,
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.project = root / "project"
        (self.project / ".git").mkdir(parents=True)
        (self.project / "aitasks" / "archived").mkdir(parents=True)
        (self.project / "aitasks" / "t10_alpha.md").write_text(
            _task_text(["art:trail-a"], name="Alpha"))
        raw = json.dumps(_doc("Alpha doc")).encode("utf-8")
        h = hashlib.sha256(raw).hexdigest()
        (self.project / "blobs").mkdir()
        (self.project / "blobs" / h).write_bytes(raw)
        manifests = self.project / "artifacts" / "manifests"
        manifests.mkdir(parents=True)
        (manifests / "trail-a.json").write_text(json.dumps({
            "handle": "art:trail-a", "current": "sha256:" + h,
            "versions": ["sha256:" + h], "backend": "local",
            "created_at": 1, "updated_at": 1}))
        self.runner = root / "runner.py"
        self.runner.write_text(_GENERATION_RUNNER)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("TASK_DIR", "AIT_TRAIL_CACHE", "GIT_DIR",
                                 "GIT_WORK_TREE")}
        self.env["AIT_TRAIL_CACHE_DIR"] = str(root / "cache")
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"

    def _run(self, edit="none", cache=True):
        env = dict(self.env)
        if not cache:
            env["AIT_TRAIL_CACHE"] = "0"
        out = subprocess.run(
            [sys.executable, str(self.runner), str(self.lib), edit],
            cwd=self.project, env=env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_negative_control_same_code_hits(self):
        a = self._run()
        b = self._run()
        self.assertEqual(a["gets"], 1)
        self.assertEqual((b["gets"], b["parses"]), (0, 0))
        self.assertEqual(b["infos"], a["infos"])

    def test_owner_code_upgraded_under_a_running_process(self):
        a = self._run(edit="owner")
        self.assertEqual(a["pre"], a["post"], "identity re-read from disk")
        self.assertEqual(a["infos"]["art:trail-a"][0], "Alpha")  # old code
        b = self._run()
        self.assertNotEqual(b["pre"][0], a["pre"][0])
        self.assertGreater(b["parses"], 0, "B accepted A's owner entries")
        b_uncached = self._run(cache=False)
        self.assertEqual(b["infos"], b_uncached["infos"])
        self.assertEqual(b["infos"]["art:trail-a"][0], "Alpha+NEW")

    def test_schema_upgraded_under_a_running_process(self):
        a = self._run(edit="schema")
        self.assertEqual(a["pre"], a["post"], "identity re-read from disk")
        self.assertEqual(a["infos"]["art:trail-a"][2], "Alpha doc")
        b = self._run()
        self.assertNotEqual(b["pre"][1], a["pre"][1])
        self.assertEqual(b["gets"], 1, "B accepted A's document entry")
        self.assertIn("invalid trail document", b["infos"]["art:trail-a"][1])
        self.assertEqual(b["infos"], self._run(cache=False)["infos"])


class CachedEqualsUncachedTests(_DocBase):
    """Post-phase differential: cached discovery equals uncached discovery
    after every step of a scripted mutation sequence."""

    def _check(self, step):
        cached = _summary(self.scan().values())
        with patch.dict(os.environ, {"AIT_TRAIL_CACHE": "0"}):
            uncached = _summary(self.scan().values())
        self.assertEqual(cached, uncached, step)
        return cached

    def test_scripted_mutation_sequence(self):
        self._check("cold")
        self._check("warm")
        self.write("t10_alpha.md", _task_text(["art:trail-a"], name="Edited"))
        self.assertEqual(self._check("edit")["art:trail-a"][3], "Edited")
        self.write("t12_gamma.md", _task_text(["art:trail-c"]))
        self.store.publish("art:trail-c", _doc("Gamma"))
        self.assertIn("art:trail-c", self._check("add"))
        (self.tasks / "t11_beta.md").unlink()
        self.assertNotIn("art:trail-b", self._check("remove"))
        text = (self.tasks / "t12_gamma.md").read_text()
        (self.tasks / "t12_gamma.md").unlink()
        _write_bundle(self.archived / "_b0" / "old0.tar.zst",
                      {"t12_gamma.md": text})
        self.assertTrue(self._check("archive into a bundle")["art:trail-c"][1])
        self.store.publish("art:trail-a", _doc("Alpha v2"))
        self.assertIn('"Alpha v2"', self._check("repoint")["art:trail-a"][5])
        self.write("t13_dup.md", _task_text(["art:trail-a"], status="Folded",
                                            folded_into=10))
        self._check("folded duplicate owner")
        # A FRESH handle whose store is unreachable: never cached, so cached
        # and uncached agree on the error card.
        self.write("t14_delta.md", _task_text(["art:trail-d"]))
        self.store.publish("art:trail-d", _doc("Delta"))
        self.store.fail_get.add("art:trail-d")
        self.assertTrue(self._check("store failure")["art:trail-d"][4])
        self.store.fail_get.clear()
        self._check("store recovered")

    def test_the_stated_boundary_blob_availability_is_not_reproven(self):
        """The one deliberate divergence (module docstring): a hit re-proves
        the manifest, not that the store can still serve the blob — so an
        unreachable store shows the last VERIFIED document, the one the
        manifest's ``current`` names, instead of an error card."""
        self.scan()
        self.store.fail_get.add("art:trail-a")
        cached = self.scan()["art:trail-a"]
        self.assertEqual(cached.load_error, "")
        current = json.loads(self.store.path("art:trail-a").read_text())[
            "current"]
        self.assertEqual(cached.doc, json.loads(self.store.blobs[current]))
        with patch.dict(os.environ, {"AIT_TRAIL_CACHE": "0"}):
            self.assertTrue(self.scan()["art:trail-a"].load_error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
