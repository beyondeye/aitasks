"""Unit tests for the section-header filter in aitask_verification_parse.py (t604).

A ``- [ ]`` bullet is a section header when its text ends with ``:`` and the
next non-blank line inside the verification section is another checklist item
with strictly deeper indent. Headers are filtered out at ``_iter_items`` time
so every downstream consumer (parse, summary, terminal_only, set, followup)
shares the same filtered view.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, cast


def _load_module():
    script = (
        Path(__file__).resolve().parents[1]
        / ".aitask-scripts"
        / "aitask_verification_parse.py"
    )
    spec = importlib.util.spec_from_file_location("aitask_verification_parse", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


vp = cast(Any, _load_module())


def _make_file(tmp: Path, body: str, frontmatter: str = "") -> Path:
    path = tmp / "task.md"
    if frontmatter:
        content = f"---\n{frontmatter}\n---\n{body}"
    else:
        content = body
    path.write_text(content, encoding="utf-8")
    return path


def _run(argv):
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = vp.main(argv)
    except SystemExit as exc:
        rc = int(exc.code or 0)
    return rc, buf.getvalue()


def _item_lines(out: str):
    return [ln for ln in out.splitlines() if ln.startswith("ITEM:")]


FM = "status: Ready\nupdated_at: 2020-01-01 00:00"


class TestSectionHeaderFilter(unittest.TestCase):
    def test_top_level_header_with_children_is_filtered(self):
        body = (
            "## Verification Checklist\n\n"
            "- [ ] `c` opens config modal:\n"
            "  - [ ] All four presets are listed\n"
            "  - [ ] Switching preset works\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = _item_lines(out)
            self.assertEqual(len(lines), 2)
            self.assertIn("All four presets", lines[0])
            self.assertTrue(lines[0].startswith("ITEM:1:pending:"))
            self.assertIn("Switching preset", lines[1])
            self.assertTrue(lines[1].startswith("ITEM:2:pending:"))

    def test_header_mid_list_keeps_indices_dense(self):
        body = (
            "## Verification Checklist\n\n"
            "- [ ] first leaf\n"
            "- [ ] group:\n"
            "  - [ ] child a\n"
            "  - [ ] child b\n"
            "- [ ] last leaf\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = _item_lines(out)
            self.assertEqual(len(lines), 4)
            self.assertIn("first leaf", lines[0])
            self.assertTrue(lines[0].startswith("ITEM:1:"))
            self.assertIn("child a", lines[1])
            self.assertTrue(lines[1].startswith("ITEM:2:"))
            self.assertIn("child b", lines[2])
            self.assertTrue(lines[2].startswith("ITEM:3:"))
            self.assertIn("last leaf", lines[3])
            self.assertTrue(lines[3].startswith("ITEM:4:"))

    def test_colon_line_with_same_indent_sibling_is_not_header(self):
        body = (
            "## Verification Checklist\n\n"
            "- [ ] ends with colon:\n"
            "- [ ] also a sibling\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = _item_lines(out)
            self.assertEqual(len(lines), 2)
            self.assertIn("ends with colon:", lines[0])
            self.assertIn("also a sibling", lines[1])

    def test_colon_line_at_end_of_section_is_not_header(self):
        body = (
            "## Verification Checklist\n\n"
            "- [ ] lonely colon line:\n"
            "\n"
            "## Another Section\n\n"
            "Not part of checklist.\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = _item_lines(out)
            self.assertEqual(len(lines), 1)
            self.assertIn("lonely colon line:", lines[0])

    def test_pre_marked_header_still_recognized(self):
        body = (
            "## Verification Checklist\n\n"
            "- [x] group header: — PASS 2026-04-21 08:00\n"
            "  - [x] first child — PASS 2026-04-21 08:01\n"
            "  - [x] second child — PASS 2026-04-21 08:02\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = _item_lines(out)
            self.assertEqual(len(lines), 2)
            self.assertNotIn("group header:", "\n".join(lines))

    def test_summary_counts_exclude_headers(self):
        body = (
            "## Verification Checklist\n\n"
            "- [ ] header one:\n"
            "  - [x] leaf 1a\n"
            "  - [x] leaf 1b\n"
            "- [ ] header two:\n"
            "  - [defer] leaf 2a\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["summary", str(path)])
            self.assertEqual(rc, 0)
            self.assertIn("TOTAL:3 PENDING:0 PASS:2 FAIL:0 SKIP:0 DEFER:1", out)

    def test_terminal_only_ignores_pending_header(self):
        body = (
            "## Verification Checklist\n\n"
            "- [ ] unmarked header with terminal kids:\n"
            "  - [x] kid a\n"
            "  - [skip] kid b\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            rc, _out = _run(["terminal_only", str(path)])
            self.assertEqual(rc, 0)

    def test_set_targets_filtered_index(self):
        body = (
            "## Verification Checklist\n\n"
            "- [ ] header:\n"
            "  - [ ] child a\n"
            "  - [ ] child b\n"
            "- [ ] standalone leaf\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            rc, _ = _run(["set", str(path), "3", "pass"])
            self.assertEqual(rc, 0)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = _item_lines(out)
            self.assertEqual(len(lines), 3)
            self.assertTrue(lines[2].startswith("ITEM:3:pass:"))
            self.assertIn("standalone leaf", lines[2])
            self.assertTrue(lines[0].startswith("ITEM:1:pending:"))
            self.assertTrue(lines[1].startswith("ITEM:2:pending:"))


if __name__ == "__main__":
    unittest.main()
