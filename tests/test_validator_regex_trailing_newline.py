"""Validator regexes refuse a value with a trailing newline (t2269).

Python's ``$`` also matches just before a final ``\\n``, so a validator ending
in ``$`` accepts ``"art:a\\n"``. The artifact/attachment validators gate
untrusted values that become file names (``manifest_path`` -> ``a\\n.json``),
so they end in ``\\Z``.

One regression case per consumer. Each refusal fixture is built so that the
pre-fix code ACCEPTS it: a malformed manifest is stored under its matching
malformed filename, and a value that another check would refuse anyway is
asserted on the anchor's own diagnostic. Without that, the case would pass
before the fix too and would prove nothing. Each consumer also gets a clean-value
acceptance case, so a regex that refuses everything cannot pass.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_validator_regex_trailing_newline.py -q
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB = REPO_ROOT / ".aitask-scripts" / "lib"
BOARD = REPO_ROOT / ".aitask-scripts" / "board"
for _p in (str(BOARD), str(LIB)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_launch_utils as alu  # noqa: E402
import artifact_manifest as am  # noqa: E402
import artifact_registry as ar  # noqa: E402
import attachment_meta as atm  # noqa: E402
import trail_discovery_cache as tdc  # noqa: E402

H = "sha256:" + "1" * 64
MANIFEST_PY = LIB / "artifact_manifest.py"


def _record(handle="art:a", h=H, backend="local"):
    return {"handle": handle, "current": h, "versions": [h], "backend": backend,
            "created_at": 100, "updated_at": 100}


class _TmpDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="t2269_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write_manifest(self, filename, rec):
        path = os.path.join(self.tmp, filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        return path


class RegexAnchorTests(unittest.TestCase):
    """R1-R5: each module-level regex, valid vs valid + newline."""

    CASES = {
        "artifact_manifest.HANDLE_RE": (am.HANDLE_RE, "art:a"),
        "artifact_manifest.HASH_RE": (am.HASH_RE, H),
        "artifact_manifest.BACKEND_RE": (am.BACKEND_RE, "local"),
        "attachment_meta.HASH_RE": (atm.HASH_RE, H),
        "artifact_registry.BACKEND_RE": (ar.BACKEND_RE, "local"),
    }

    def test_valid_value_matches(self):
        for name, (rx, valid) in self.CASES.items():
            with self.subTest(regex=name):
                self.assertTrue(rx.match(valid))

    def test_trailing_newline_is_refused(self):
        for name, (rx, valid) in self.CASES.items():
            with self.subTest(regex=name):
                self.assertIsNone(rx.match(valid + "\n"))


class ManifestPathTests(_TmpDir):
    """M1: the handle becomes the manifest file name."""

    def test_clean_handle_maps_to_its_file(self):
        self.assertEqual(am.manifest_path(self.tmp, "art:a"),
                         os.path.join(self.tmp, "a.json"))

    def test_newline_handle_dies(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                am.manifest_path(self.tmp, "art:a\n")


class ManifestCliCreateTests(_TmpDir):
    """M2: `artifact_manifest.py create` through the real CLI."""

    def run_create(self, handle, h):
        return subprocess.run(
            [sys.executable, str(MANIFEST_PY), "--manifest-dir", self.tmp,
             "create", handle, h, "now=100"],
            capture_output=True, text=True)

    def test_clean_create_writes_the_manifest(self):
        proc = self.run_create("art:a", H)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.listdir(self.tmp), ["a.json"])

    def test_newline_handle_is_refused_and_writes_nothing(self):
        proc = self.run_create("art:a\n", H)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("invalid handle", proc.stderr)
        self.assertEqual(os.listdir(self.tmp), [])

    def test_newline_hash_is_refused_and_writes_nothing(self):
        proc = self.run_create("art:a", H + "\n")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("invalid hash", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "a.json")))


class ManifestViolationTests(_TmpDir):
    """M3: the schema check shared by `get` and trail discovery. Each malformed
    record is otherwise valid AND stored under its own filename, so the only
    violation left is the anchor's."""

    def violation(self, filename, rec):
        path = self.write_manifest(filename, rec)
        with open(path, encoding="utf-8") as fh:
            return am.manifest_violation(json.load(fh), path)

    def test_clean_record_has_no_violation(self):
        self.assertIsNone(self.violation("a.json", _record()))

    def test_newline_handle_under_its_own_filename(self):
        v = self.violation("a\n.json", _record(handle="art:a\n"))
        self.assertIsNotNone(v)
        self.assertIn("invalid handle", v)

    def test_newline_version_hash(self):
        v = self.violation("a.json", _record(h=H + "\n"))
        self.assertIsNotNone(v)
        self.assertIn("invalid version hash", v)

    def test_newline_backend(self):
        v = self.violation("a.json", _record(backend="local\n"))
        self.assertIsNotNone(v)
        self.assertIn("invalid backend name", v)


class AttachmentMetaPathTests(_TmpDir):
    """A1: the hash becomes the sharded meta file name."""

    def test_clean_hash_maps_to_its_shard(self):
        self.assertEqual(atm.meta_path(self.tmp, H),
                         os.path.join(self.tmp, "11", "1" * 62 + ".json"))

    def test_newline_hash_dies(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                atm.meta_path(self.tmp, H + "\n")


class ArtifactRegistryTests(unittest.TestCase):
    """G1: backend names from the project config."""

    PATH = "aitasks/metadata/project_config.yaml"

    def test_clean_backend_key_is_accepted(self):
        cfg = {"artifacts": {"backends": {"local": {}}}}
        self.assertEqual(ar.registered_backends(cfg, self.PATH), {"local": {}})

    def test_newline_backend_key_dies(self):
        cfg = {"artifacts": {"backends": {"local\n": {}}}}
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ar.registered_backends(cfg, self.PATH)

    def test_newline_default_backend_is_an_invalid_name(self):
        # Before the fix this dies too, but as "not registered". Assert the
        # anchor's own diagnostic so this case shows the fix, not that refusal.
        cfg = {"artifacts": {"default_backend": "local\n"}}
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                ar.cmd_default_backend(cfg, self.PATH)
        self.assertIn("is not a valid backend name", err.getvalue())


class ManifestCurrentTests(_TmpDir):
    """T1: trail discovery's non-exiting manifest read."""

    def test_clean_handle_reads_current(self):
        self.write_manifest("a.json", _record())
        self.assertEqual(tdc.manifest_current("art:a", self.tmp), H)

    def test_newline_handle_is_refused_even_with_a_matching_file(self):
        # A valid manifest stored under the matching malformed name: before the
        # fix this returns H; only the handle guard refuses it.
        self.write_manifest("a\n.json", _record(handle="art:a\n"))
        self.assertIsNone(tdc.manifest_current("art:a\n", self.tmp))


class LaunchOrFocusTrailsTests(unittest.TestCase):
    """L1: the trails writer validates before any tmux call."""

    def test_newline_handle_is_refused_before_tmux(self):
        with patch.object(alu._TMUX, "run", return_value=(1, "")) as run:
            ok, msg = alu.launch_or_focus_trails("s", REPO_ROOT, "art:a\n")
        self.assertFalse(ok)
        self.assertTrue((msg or "").startswith("invalid trail handle"), msg)
        run.assert_not_called()


class _Booted(Exception):
    """Raised by the TrailsApp stub: validation passed and the app would start."""


class TrailsMainTests(unittest.TestCase):
    """P1: `ait trails --trail`. TrailsApp is stubbed so no case boots the app,
    the pre-fix run included."""

    def setUp(self):
        import trails_app
        self.ta = trails_app

        def _boot(*_a, **_k):
            raise _Booted()

        p = patch.object(trails_app, "TrailsApp", side_effect=_boot)
        p.start()
        self.addCleanup(p.stop)

    def test_clean_handle_passes_validation(self):
        with self.assertRaises(_Booted):
            self.ta.main(["--trail", "art:a"])

    def test_newline_handle_is_a_usage_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                self.ta.main(["--trail", "art:a\n"])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("invalid trail handle", err.getvalue())


if __name__ == "__main__":
    unittest.main()
