"""Characterization of the archive_iter readers on one mixed archived tree.

Pins, before and after the t2173_1 refactor that rebuilt the readers on a shared
unit partition (``archived_markdown_sources`` / ``iter_archive_file`` /
``parse_archived_frontmatter``), the exact ``(name, text)`` sequence — order
included — and the ``errors`` list of every public reader, both best-effort
(``errors=None``) and diagnostic (``errors=[]``). archive_iter is shared by
stats, explain, codebrowser history, the board and trail discovery, so an order
or error-reporting change here is a change for all of them.

The expected values were recorded against the pre-refactor code; error reasons
coming from tarfile/zstd are pinned by path plus a stable reason fragment
rather than verbatim, so a Python or zstd upgrade does not read as a regression.

Run: python3 tests/test_archive_iter_characterization.py
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

_lib_dir = Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"
sys.path.insert(0, str(_lib_dir))

import archive_iter  # noqa: E402
from task_yaml import parse_frontmatter  # noqa: E402


def _tar_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _zstd(data: bytes) -> bytes:
    return subprocess.run(["zstd", "-q", "-c"], input=data,
                          capture_output=True, check=True).stdout


def _write_zst(path: Path, files: dict[str, str], trailer: bytes = b"") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_zstd(_tar_bytes(files)) + trailer)


def _write_gz(path: Path, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tf:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def _fm(task_id: str) -> str:
    return f"---\nstatus: Done\nid: '{task_id}'\n---\n\nbody {task_id}\n"


BAD_FM = "---\npriority: [unclosed\n---\n"


def build_tree(root: Path) -> Path:
    """The mixed archived dir every test reads (returns its path)."""
    archived = root / "archived"
    archived.mkdir(parents=True)
    # Loose parents (one is a child name at top level: never yielded).
    (archived / "t2_beta.md").write_text(_fm("2"), encoding="utf-8")
    (archived / "t1_alpha.md").write_text(_fm("1"), encoding="utf-8")
    (archived / "t3_1_stray.md").write_text(_fm("3_1"), encoding="utf-8")
    (archived / "notes.md").write_text("not a task\n", encoding="utf-8")
    (archived / "t4_crlf.md").write_bytes(b"---\r\nstatus: Done\r\n---\r\nx\r\n")
    # Loose children.
    (archived / "t5").mkdir()
    (archived / "t5" / "t5_1_child.md").write_text(_fm("5_1"),
                                                   encoding="utf-8")
    (archived / "t5" / "t5_2_bad.md").write_text(BAD_FM, encoding="utf-8")
    # Numbered bundles.
    _write_zst(archived / "_b0" / "old0.tar.zst", {
        "t10_a.md": _fm("10"),
        "sub/t11_b.md": _fm("11"),
        "readme.txt": "skip me",
        "t12_bad.md": BAD_FM,
        "t13_1_kid.md": _fm("13_1"),
    })
    _write_gz(archived / "_b0" / "old1.tar.gz",
              {"t100_c.md": _fm("100")})
    _write_zst(archived / "_b0" / "old2.tar.zst", {"t200_z.md": _fm("200")})
    _write_gz(archived / "_b0" / "old2.tar.gz", {"t200_g.md": _fm("200g")})
    (archived / "_b1").mkdir()
    (archived / "_b1" / "old10.tar.zst").write_bytes(b"garbage, not zstd")
    # A whole archive followed by trailing garbage: tarfile reads to its
    # end-of-archive cleanly, zstd then exits non-zero.
    _write_zst(archived / "_b1" / "old11.tar.zst", {"t1100_t.md": _fm("1100")},
               trailer=b"\x00garbage-after-frame")
    # Legacy bundle (read by iter_legacy_archive / the by-id lookup only).
    _write_zst(archived / "old.tar.zst", {"t0_legacy.md": _fm("0")})
    return archived


def _meta_parse(text):
    result = parse_frontmatter(text)
    return result[0] if result else None


EXPECTED_ALL = [
    ("t1_alpha.md", _fm("1")),
    ("t2_beta.md", _fm("2")),
    ("t4_crlf.md", "---\nstatus: Done\n---\nx\n"),
    ("t5_1_child.md", _fm("5_1")),
    ("t5_2_bad.md", BAD_FM),
    ("t10_a.md", _fm("10")),
    ("t11_b.md", _fm("11")),
    ("t12_bad.md", BAD_FM),
    ("t13_1_kid.md", _fm("13_1")),
    ("t200_z.md", _fm("200")),
    ("t1100_t.md", _fm("1100")),
    ("t100_c.md", _fm("100")),
]

EXPECTED_NUMBERED = EXPECTED_ALL[5:]


def _reason_fragments(errors):
    """``"<path>: <reason>"`` → ``(<basename>, <reason>)``."""
    out = []
    for entry in errors:
        path, _, reason = entry.partition(": ")
        out.append((Path(path).name, reason))
    return out


class _Tree(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.archived = build_tree(Path(tmp.name))

    def assert_corrupt_bundle_errors(self, errors, *, with_frontmatter):
        frags = _reason_fragments(errors)
        names = [n for n, _ in frags]
        expected = ["old10.tar.zst", "old11.tar.zst"]
        if with_frontmatter:
            expected = ["t5_2_bad.md", "t12_bad.md", "old10.tar.zst",
                        "old11.tar.zst"]
        self.assertEqual(sorted(names), sorted(expected), errors)
        self.assertEqual(len(errors), len(set(errors)), "duplicate notes")
        reasons = dict(frags)
        self.assertEqual(reasons["old11.tar.zst"], "zstd exited 1")
        self.assertTrue(reasons["old10.tar.zst"], "empty reason")
        if with_frontmatter:
            self.assertEqual(reasons["t5_2_bad.md"], "unparseable frontmatter")
            self.assertEqual(reasons["t12_bad.md"], "unparseable frontmatter")


class IterAllArchivedMarkdownTests(_Tree):
    def test_best_effort_sequence(self):
        got = list(archive_iter.iter_all_archived_markdown(self.archived))
        self.assertEqual(got, EXPECTED_ALL)

    def test_diagnostic_sequence_and_errors(self):
        errors: list = []
        got = list(archive_iter.iter_all_archived_markdown(self.archived,
                                                           errors=errors))
        self.assertEqual(got, EXPECTED_ALL)
        self.assert_corrupt_bundle_errors(errors, with_frontmatter=False)
        self.assertEqual([Path(e.partition(": ")[0]).name for e in errors],
                         ["old10.tar.zst", "old11.tar.zst"])


class IterNumberedArchivesTests(_Tree):
    def test_best_effort_sequence(self):
        got = list(archive_iter.iter_numbered_archives(self.archived))
        self.assertEqual(got, EXPECTED_NUMBERED)

    def test_diagnostic_sequence_and_errors(self):
        errors: list = []
        got = list(archive_iter.iter_numbered_archives(self.archived,
                                                       errors=errors))
        self.assertEqual(got, EXPECTED_NUMBERED)
        self.assert_corrupt_bundle_errors(errors, with_frontmatter=False)


class IterArchivedFrontmatterTests(_Tree):
    def _expected(self):
        out = []
        for name, text in EXPECTED_ALL:
            meta = _meta_parse_safe(text)
            if meta is not None:
                out.append((name, meta))
        return out

    def test_best_effort_sequence(self):
        got = list(archive_iter.iter_archived_frontmatter(self.archived,
                                                          _meta_parse))
        self.assertEqual(got, self._expected())
        self.assertNotIn("t5_2_bad.md", [n for n, _ in got])

    def test_diagnostic_sequence_and_errors(self):
        errors: list = []
        got = list(archive_iter.iter_archived_frontmatter(
            self.archived, _meta_parse, errors=errors))
        self.assertEqual(got, self._expected())
        self.assert_corrupt_bundle_errors(errors, with_frontmatter=True)
        # Notes land in read order: loose children parse before any bundle.
        self.assertEqual([Path(e.partition(": ")[0]).name for e in errors],
                         ["t5_2_bad.md", "t12_bad.md", "old10.tar.zst",
                          "old11.tar.zst"])

    def test_non_dict_non_none_is_yielded_and_reported(self):
        errors: list = []
        got = list(archive_iter.iter_archived_frontmatter(
            self.archived, lambda text: "scalar", errors=errors))
        self.assertEqual([n for n, _ in got], [n for n, _ in EXPECTED_ALL])
        noted = [Path(e.partition(": ")[0]).name for e in errors
                 if e.endswith("unparseable frontmatter")]
        self.assertEqual(noted, [n for n, _ in EXPECTED_ALL])


def _meta_parse_safe(text):
    try:
        return _meta_parse(text)
    except Exception:
        return None


class FindArchivedMarkdownByIdTests(_Tree):
    CASES = [
        ("1", ("t1_alpha.md", _fm("1"))),
        ("t2", ("t2_beta.md", _fm("2"))),
        ("3_1", None),                    # child name at top level, no dir
        ("5_1", ("t5_1_child.md", _fm("5_1"))),
        ("10", ("t10_a.md", _fm("10"))),
        ("13_1", ("t13_1_kid.md", _fm("13_1"))),
        ("100", ("t100_c.md", _fm("100"))),
        ("200", ("t200_z.md", _fm("200"))),
        ("0", ("t0_legacy.md", _fm("0"))),
        ("999", None),
        ("1000", None),                   # corrupt bundle, then legacy miss
        ("1100", ("t1100_t.md", _fm("1100"))),
        ("bogus", None),
    ]

    def test_best_effort_lookups(self):
        for task_id, expected in self.CASES:
            with self.subTest(task_id=task_id):
                self.assertEqual(archive_iter.find_archived_markdown_by_id(
                    task_id, self.archived), expected)

    def test_diagnostic_lookups(self):
        for task_id, expected in self.CASES:
            with self.subTest(task_id=task_id):
                errors: list = []
                got = archive_iter.find_archived_markdown_by_id(
                    task_id, self.archived, errors=errors)
                self.assertEqual(got, expected)
                names = [Path(e.partition(": ")[0]).name for e in errors]
                # Early exit never checks zstd's status (SIGPIPE is benign);
                # only the corrupt bundle is ever noted.
                self.assertEqual(names,
                                 ["old10.tar.zst"] if task_id == "1000" else [])


class IterLegacyArchiveTests(_Tree):
    def test_sequence(self):
        for errors in (None, []):
            with self.subTest(errors=errors):
                got = list(archive_iter.iter_legacy_archive(self.archived,
                                                            errors=errors))
                self.assertEqual(got, [("t0_legacy.md", _fm("0"))])
                if errors is not None:
                    self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
