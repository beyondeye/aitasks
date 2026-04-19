"""Unit tests for .aitask-scripts/aitask_verification_parse.py."""

from __future__ import annotations

import importlib.util
import io
import re
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
    """Run main(argv), capturing stdout. Returns (exit_code, stdout_str)."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = vp.main(argv)
    except SystemExit as exc:
        rc = int(exc.code or 0)
    return rc, buf.getvalue()


BASIC_BODY = """# Title

Intro.

## Verification Checklist

- [ ] first pending item
- [x] second pass item
- [fail] third fail item
- [skip] fourth skip item
- [defer] fifth defer item
"""

FM = "status: Ready\nupdated_at: 2020-01-01 00:00"


class TestParseSubcommand(unittest.TestCase):
    def test_case_insensitive_header(self):
        for header in ["## Verification Checklist", "## verification", "## CHECKLIST"]:
            with tempfile.TemporaryDirectory() as d:
                body = f"{header}\n\n- [ ] one\n"
                path = _make_file(Path(d), body, FM)
                rc, out = _run(["parse", str(path)])
                self.assertEqual(rc, 0)
                self.assertIn("ITEM:1:pending:", out)

    def test_emits_one_line_per_item(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), BASIC_BODY, FM)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = [ln for ln in out.splitlines() if ln.startswith("ITEM:")]
            self.assertEqual(len(lines), 5)
            self.assertTrue(lines[0].startswith("ITEM:1:pending:"))
            self.assertTrue(lines[1].startswith("ITEM:2:pass:"))
            self.assertTrue(lines[2].startswith("ITEM:3:fail:"))
            self.assertTrue(lines[3].startswith("ITEM:4:skip:"))
            self.assertTrue(lines[4].startswith("ITEM:5:defer:"))

    def test_skips_malformed_lines(self):
        with tempfile.TemporaryDirectory() as d:
            body = (
                "## Verification Checklist\n\n"
                "- [ ] good\n"
                "- [?] malformed\n"
                "not a checkbox line\n"
                "- [x] also good\n"
            )
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = [ln for ln in out.splitlines() if ln.startswith("ITEM:")]
            self.assertEqual(len(lines), 2)

    def test_stops_at_next_h2(self):
        with tempfile.TemporaryDirectory() as d:
            body = (
                "## Verification Checklist\n\n"
                "- [ ] inside\n\n"
                "## Other Section\n\n"
                "- [ ] outside\n"
            )
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["parse", str(path)])
            lines = [ln for ln in out.splitlines() if ln.startswith("ITEM:")]
            self.assertEqual(len(lines), 1)
            self.assertIn("inside", lines[0])

    def test_no_checklist_section(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), "# Title\n\nNo checklist here.\n", FM)
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            self.assertEqual(
                [ln for ln in out.splitlines() if ln.startswith("ITEM:")], []
            )

    def test_first_matching_h2_wins(self):
        with tempfile.TemporaryDirectory() as d:
            body = (
                "## Verification Checklist\n\n"
                "- [ ] first section item\n\n"
                "## Checklist\n\n"
                "- [ ] second section item\n"
            )
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["parse", str(path)])
            lines = [ln for ln in out.splitlines() if ln.startswith("ITEM:")]
            self.assertEqual(len(lines), 1)
            self.assertIn("first section item", lines[0])


class TestSummarySubcommand(unittest.TestCase):
    def test_counts_match_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), BASIC_BODY, FM)
            rc, out = _run(["summary", str(path)])
            self.assertEqual(rc, 0)
            self.assertIn(
                "TOTAL:5 PENDING:1 PASS:1 FAIL:1 SKIP:1 DEFER:1", out
            )

    def test_total_zero_when_no_section(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), "# Title\n\nNothing.\n", FM)
            rc, out = _run(["summary", str(path)])
            self.assertEqual(rc, 0)
            self.assertIn("TOTAL:0", out)


class TestTerminalOnlySubcommand(unittest.TestCase):
    def test_all_terminal_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            body = (
                "## Verification Checklist\n\n"
                "- [x] p1\n- [fail] p2\n- [skip] p3\n"
            )
            path = _make_file(Path(d), body, FM)
            rc, _ = _run(["terminal_only", str(path)])
            self.assertEqual(rc, 0)

    def test_pending_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            body = "## Verification Checklist\n\n- [ ] p\n- [x] q\n"
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["terminal_only", str(path)])
            self.assertEqual(rc, 2)
            self.assertIn("PENDING:1", out)
            self.assertNotIn("DEFERRED:", out)

    def test_deferred_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            body = "## Verification Checklist\n\n- [x] a\n- [defer] b\n"
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["terminal_only", str(path)])
            self.assertEqual(rc, 2)
            self.assertIn("DEFERRED:1", out)
            self.assertNotIn("PENDING:", out)

    def test_both_pending_and_deferred(self):
        with tempfile.TemporaryDirectory() as d:
            body = (
                "## Verification Checklist\n\n"
                "- [ ] a\n- [defer] b\n- [x] c\n"
            )
            path = _make_file(Path(d), body, FM)
            rc, out = _run(["terminal_only", str(path)])
            self.assertEqual(rc, 2)
            self.assertIn("PENDING:1", out)
            self.assertIn("DEFERRED:1", out)

    def test_empty_checklist_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), "## Verification Checklist\n\n", FM)
            rc, _ = _run(["terminal_only", str(path)])
            self.assertEqual(rc, 0)


class TestSetSubcommand(unittest.TestCase):
    def _setup(self, d):
        return _make_file(Path(d), BASIC_BODY, FM)

    def test_flip_pending_to_pass(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._setup(d)
            rc, _ = _run(["set", str(path), "1", "pass"])
            self.assertEqual(rc, 0)
            text = path.read_text(encoding="utf-8")
            self.assertIn("- [x] first pending item \u2014 PASS", text)

    def test_flip_to_fail_marker(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._setup(d)
            _run(["set", str(path), "1", "fail"])
            text = path.read_text(encoding="utf-8")
            self.assertIn("- [fail] first pending item \u2014 FAIL", text)

    def test_note_appended(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._setup(d)
            _run(["set", str(path), "1", "pass", "--note", "verified ok"])
            text = path.read_text(encoding="utf-8")
            self.assertRegex(
                text,
                r"- \[x\] first pending item \u2014 PASS \d{4}-\d{2}-\d{2} \d{2}:\d{2} verified ok",
            )

    def test_second_set_strips_prior_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._setup(d)
            _run(["set", str(path), "1", "pass", "--note", "note_alpha"])
            _run(["set", str(path), "1", "fail", "--note", "note_beta"])
            text = path.read_text(encoding="utf-8")
            # Only one annotation suffix should survive.
            line = [
                ln for ln in text.splitlines() if "first pending item" in ln
            ][0]
            self.assertEqual(line.count("\u2014"), 1)
            # The surviving annotation must be the most recent one only.
            annotation = line.split(" \u2014 ", 1)[1]
            self.assertIn("FAIL", annotation)
            self.assertIn("note_beta", annotation)
            self.assertNotIn("note_alpha", annotation)
            self.assertNotIn("PASS", annotation)

    def test_hyphens_not_stripped(self):
        with tempfile.TemporaryDirectory() as d:
            body = "## Verification Checklist\n\n- [ ] foo - bar and a \u2013 en-dash\n"
            path = _make_file(Path(d), body, FM)
            _run(["set", str(path), "1", "pass"])
            text = path.read_text(encoding="utf-8")
            # Original dashes preserved; exactly one em-dash added as annotation separator.
            line = [ln for ln in text.splitlines() if "- [x]" in ln][0]
            self.assertIn("foo - bar and a \u2013 en-dash", line)
            self.assertEqual(line.count("\u2014"), 1)

    def test_updated_at_bumped(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._setup(d)
            before = path.read_text(encoding="utf-8")
            _run(["set", str(path), "1", "pass"])
            after = path.read_text(encoding="utf-8")
            self.assertIn("updated_at: 2020-01-01 00:00", before)
            self.assertNotIn("updated_at: 2020-01-01 00:00", after)
            self.assertRegex(after, r"updated_at: \d{4}-\d{2}-\d{2} \d{2}:\d{2}")

    def test_other_frontmatter_preserved(self):
        fm = "status: Ready\npriority: high\nlabels: [a, b]\nupdated_at: 2020-01-01 00:00"
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), BASIC_BODY, fm)
            _run(["set", str(path), "1", "pass"])
            text = path.read_text(encoding="utf-8")
            self.assertIn("status: Ready", text)
            self.assertIn("priority: high", text)
            self.assertIn("labels: [a, b]", text)

    def test_invalid_index_exits_nonzero_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._setup(d)
            before = path.read_text(encoding="utf-8")
            rc, _ = _run(["set", str(path), "99", "pass"])
            self.assertNotEqual(rc, 0)
            after = path.read_text(encoding="utf-8")
            self.assertEqual(before, after)

    def test_no_checklist_exits_nonzero_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), "# Title\n\nNo section.\n", FM)
            before = path.read_text(encoding="utf-8")
            rc, _ = _run(["set", str(path), "1", "pass"])
            self.assertNotEqual(rc, 0)
            after = path.read_text(encoding="utf-8")
            self.assertEqual(before, after)

    def test_atomic_write_final_file_parses(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._setup(d)
            _run(["set", str(path), "3", "pass"])
            rc, out = _run(["parse", str(path)])
            self.assertEqual(rc, 0)
            lines = [ln for ln in out.splitlines() if ln.startswith("ITEM:")]
            self.assertEqual(len(lines), 5)


class TestSeedSubcommand(unittest.TestCase):
    def test_creates_section_from_items_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), "# Title\n\nIntro.\n", FM)
            items = Path(d) / "items.txt"
            items.write_text("one\ntwo\nthree\n", encoding="utf-8")
            rc, _ = _run(["seed", str(path), "--items", str(items)])
            self.assertEqual(rc, 0)
            text = path.read_text(encoding="utf-8")
            self.assertIn("## Verification Checklist", text)
            self.assertIn("- [ ] one", text)
            self.assertIn("- [ ] two", text)
            self.assertIn("- [ ] three", text)

    def test_skips_blank_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), "# Title\n", FM)
            items = Path(d) / "items.txt"
            items.write_text("first\n\n\nsecond\n   \nthird\n", encoding="utf-8")
            _run(["seed", str(path), "--items", str(items)])
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("- [ ]"), 3)

    def test_existing_section_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), BASIC_BODY, FM)
            items = Path(d) / "items.txt"
            items.write_text("one\n", encoding="utf-8")
            before = path.read_text(encoding="utf-8")
            rc, _ = _run(["seed", str(path), "--items", str(items)])
            self.assertNotEqual(rc, 0)
            after = path.read_text(encoding="utf-8")
            self.assertEqual(before, after)

    def test_single_trailing_newline(self):
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), "# Title\n", FM)
            items = Path(d) / "items.txt"
            items.write_text("one\n", encoding="utf-8")
            _run(["seed", str(path), "--items", str(items)])
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.endswith("\n"))
            self.assertFalse(text.endswith("\n\n"))


class TestRoundTrip(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            task = _make_file(Path(d), "# Title\n", FM)
            items = Path(d) / "items.txt"
            items.write_text("alpha\nbeta\ngamma\ndelta\nepsilon\n", encoding="utf-8")
            rc, _ = _run(["seed", str(task), "--items", str(items)])
            self.assertEqual(rc, 0)

            rc, out = _run(["parse", str(task)])
            self.assertEqual(rc, 0)
            self.assertEqual(
                len([ln for ln in out.splitlines() if ln.startswith("ITEM:")]), 5
            )

            for idx, state in [
                (1, "pass"),
                (2, "fail"),
                (3, "skip"),
                (4, "defer"),
                (5, "pass"),
            ]:
                rc, _ = _run(["set", str(task), str(idx), state])
                self.assertEqual(rc, 0)

            rc, out = _run(["summary", str(task)])
            self.assertEqual(rc, 0)
            self.assertIn(
                "TOTAL:5 PENDING:0 PASS:2 FAIL:1 SKIP:1 DEFER:1", out
            )

            rc, out = _run(["terminal_only", str(task)])
            self.assertEqual(rc, 2)
            self.assertIn("DEFERRED:1", out)

            _run(["set", str(task), "4", "skip"])
            rc, _ = _run(["terminal_only", str(task)])
            self.assertEqual(rc, 0)


class TestFrontmatterEdgeCases(unittest.TestCase):
    def test_frontmatter_without_closing_fails(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "task.md"
            path.write_text("---\nstatus: Ready\n\nbody here\n", encoding="utf-8")
            rc, _ = _run(["parse", str(path)])
            self.assertNotEqual(rc, 0)

    def test_frontmatter_without_updated_at_inserts(self):
        fm = "status: Ready\npriority: high"
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), BASIC_BODY, fm)
            _run(["set", str(path), "1", "pass"])
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"updated_at: \d{4}-\d{2}-\d{2} \d{2}:\d{2}")
            self.assertIn("status: Ready", text)
            self.assertIn("priority: high", text)

    def test_body_whitespace_preserved(self):
        body = "# Title\n\nIntro with trailing newline.\n\n## Verification Checklist\n\n- [ ] one\n"
        with tempfile.TemporaryDirectory() as d:
            path = _make_file(Path(d), body, FM)
            _run(["set", str(path), "1", "pass"])
            text = path.read_text(encoding="utf-8")
            self.assertIn("Intro with trailing newline.", text)
            self.assertIn("# Title", text)


if __name__ == "__main__":
    unittest.main()
