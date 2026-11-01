#!/usr/bin/env python3
"""Unit tests for the sitrep store format core (lib/sitrep_todo.py, t2175_1).

The bash suite (tests/test_sitrep_todo.sh) owns locking, crashes and recovery;
this file owns the grammar: render∘parse identity, the strict refusals with
their line numbers, the generated-file banner, heading placement, rev bumps
and the id scan's tolerance of garbage.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                ".aitask-scripts", "lib"))
import sitrep_todo as st  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sitrep", "store")


def _item(num, **kw):
    base = dict(rev=1, kind="task", state="open", group="next",
                checked_at="never", ref="", derived="script", outcome="",
                title=f"item {num}")
    base.update(kw)
    return st.Item(num, **base)


def _store(*items):
    s = st.TodoStore()
    for it in items:
        s.items[it.num] = it
    return s


class RoundTrip(unittest.TestCase):
    def test_empty_store_round_trips(self):
        text = st.empty_text("todo")
        self.assertEqual(st.render_todo(st.parse_todo(text)), text)
        qa = st.empty_text("qa")
        self.assertEqual(st.render_qa(st.parse_qa(qa)), qa)

    def test_fixture_round_trips(self):
        with open(os.path.join(FIXTURE, "todo.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(st.render_todo(st.parse_todo(text)), text)
        with open(os.path.join(FIXTURE, "qa.md"), encoding="utf-8") as fh:
            qa = fh.read()
        self.assertEqual(st.render_qa(st.parse_qa(qa)), qa)

    def test_banner_is_line_one(self):
        self.assertEqual(st.empty_text("todo").split("\n")[0], st.TODO_BANNER)
        self.assertEqual(st.empty_text("qa").split("\n")[0], st.QA_BANNER)
        self.assertIn("DO NOT EDIT MANUALLY", st.TODO_BANNER)

    def test_title_may_contain_pipe(self):
        s = _store(_item(1, title="a | b | c"))
        parsed = st.parse_todo(st.render_todo(s))
        self.assertEqual(parsed.items[1].title, "a | b | c")


class Placement(unittest.TestCase):
    def test_heading_is_a_function_of_state_and_group(self):
        s = _store(_item(1, group="now"), _item(2, group="waiting"),
                   _item(3, state="done", group="now"),
                   _item(4, state="dismissed", group="now"),
                   _item(5, state="unknown", group="now"))
        lines = st.render_todo(s).split("\n")

        def under(cid):
            idx = next(i for i, ln in enumerate(lines) if ln.startswith(f"- {cid} |"))
            return next(ln for ln in reversed(lines[:idx]) if ln.startswith("### "))
        self.assertEqual(under("c1"), "### Pick now")
        self.assertEqual(under("c2"), "### Waiting")
        self.assertEqual(under("c3"), "### Recently done")
        self.assertEqual(under("c4"), "### Dismissed")
        self.assertEqual(under("c5"), "### Pick now")

    def test_misplaced_item_is_refused(self):
        it = _item(1, group="now")
        text = st.render_todo(_store(it))
        here = f"### Pick now\n\n{it.line()}\n\n### Next\n\n"
        self.assertIn(here, text)
        moved = text.replace(here, f"### Pick now\n\n### Next\n\n{it.line()}\n\n")
        with self.assertRaises(st.FormatError):
            st.parse_todo(moved)


class Refusals(unittest.TestCase):
    def setUp(self):
        self.text = st.render_todo(_store(_item(1)))

    def assertRefusedAt(self, text, line):
        with self.assertRaises(st.FormatError) as cm:
            st.parse_todo(text, "todo.md")
        self.assertIn(f"todo.md:{line}:", str(cm.exception))

    def test_missing_banner(self):
        self.assertRefusedAt("\n".join(self.text.split("\n")[1:]), 1)

    def test_altered_banner(self):
        self.assertRefusedAt(self.text.replace("DO NOT EDIT", "do not edit", 1), 1)

    def test_future_format(self):
        self.assertRefusedAt(self.text.replace("format=1", "format=2"), 2)

    def test_stray_blank_line_names_its_line(self):
        lines = self.text.split("\n")
        idx = lines.index("### Next")
        lines.insert(idx, "")
        self.assertRefusedAt("\n".join(lines), idx + 1)

    def test_bad_item_value(self):
        lines = self.text.split("\n")
        idx = next(i for i, ln in enumerate(lines) if ln.startswith("- c1 |"))
        lines[idx] = lines[idx].replace("kind=task", "kind=bogus")
        self.assertRefusedAt("\n".join(lines), idx + 1)

    def test_duplicate_id(self):
        line = _item(1).line()
        second = self.text.split("\n").index(line) + 2   # 1-based, the copy
        self.assertRefusedAt(self.text.replace(line, line + "\n" + line), second)

    def test_missing_final_newline(self):
        with self.assertRaises(st.FormatError):
            st.parse_todo(self.text.rstrip("\n"))

    def test_context_for_unknown_item(self):
        text = self.text + "### c9\n- background: x\n- origin: agent=a\n\n"
        with self.assertRaises(st.FormatError):
            st.parse_todo(text)


class ContextSchema(unittest.TestCase):
    def ok(self, text):
        return st.validate_context_input(text)

    def bad(self, text, fragment):
        with self.assertRaises(st.RequestError) as cm:
            st.validate_context_input(text)
        self.assertIn(fragment, str(cm.exception))

    BASE = "- background: Why it exists.\n- origin: agent=a1 date=2026-11-01\n"

    def test_minimal(self):
        e = self.ok(self.BASE)
        self.assertEqual(e.origin, [("agent", "a1"), ("date", "2026-11-01")])

    def test_denied_keys(self):
        for key in ("status", "count", "next", "progress", "summary", "Status"):
            self.bad(self.BASE + f"- {key}: x\n", "map of pointers")

    def test_unknown_key(self):
        self.bad(self.BASE + "- colour: red\n", "unknown context key")

    def test_required_keys(self):
        self.bad("- origin: agent=a\n", "background")
        self.bad("- background: x\n", "origin")

    def test_size_caps(self):
        self.bad(f"- background: {'x' * 401}\n- origin: agent=a\n", "longer than 400")
        many = "".join(f"  - url: https://example.com/{i:04d}{'y' * 40}\n" for i in range(40))
        self.bad(self.BASE + "- sources:\n" + many, "limit 2000")

    def test_capture_must_be_retained(self):
        self.bad(self.BASE + "- sources:\n  - capture: ~/.config/aitasks/frozen/x/capture.txt#L1\n",
                 "retain")
        self.bad(self.BASE + "- sources:\n  - capture: capture.txt#L1\n", "sources/<16 hex>")
        self.ok(self.BASE + "- sources:\n  - capture: sources/0123456789abcdef.txt#L2-L9\n")

    def test_retained_range_checked_against_the_store(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sources"))
            with open(os.path.join(d, "sources", "0123456789abcdef.txt"), "w") as fh:
                fh.write("a\nb\nc\n")
            ok = self.BASE + "- sources:\n  - capture: sources/0123456789abcdef.txt#L1-L3\n"
            st.validate_context_input(ok, d)
            with self.assertRaises(st.RequestError):
                st.validate_context_input(ok.replace("L1-L3", "L1-L4"), d)

    def test_repo_relative_paths(self):
        for ptr in ("/etc/passwd", "~/x", "../up.md", "a/../../b"):
            self.bad(self.BASE + f"- sources:\n  - file: {ptr}\n", "pointer")

    def test_canonical_render_reorders_keys(self):
        e = self.ok("- related: c1\n- origin: agent=a\n- background: b\n")
        self.assertEqual(e.body_lines(), ["- background: b", "- origin: agent=a",
                                          "- related: c1"])


class Values(unittest.TestCase):
    def test_refs_normalize(self):
        self.assertEqual(st.normalize_ref("42"), "t42")
        self.assertEqual(st.normalize_ref("t42_3"), "t42_3")
        self.assertEqual(st.normalize_ref("aitasks#t2171"), "aitasks#2171")
        with self.assertRaises(st.RequestError):
            st.normalize_ref("t0")

    def test_rev_changes_only_on_change_and_comes_from_the_store(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "next_rev"), "w") as fh:
                fh.write("40\n")
            revs = st.Revs(d)
            it = _item(1)
            self.assertFalse(st._apply(it, revs, title="item 1", state=None))
            self.assertEqual(it.rev, 1)
            self.assertFalse(revs.used)
            self.assertTrue(st._apply(it, revs, state="done"))
            self.assertEqual(it.rev, 40)
            self.assertEqual(revs.next, 41)

    def test_trailing_newline_never_passes_a_value_grammar(self):
        for bad in ("2026-11-01T10:00:00Z\n", "2026-11-01T10:00:00Z\r"):
            with self.assertRaises(st.RequestError):
                st.normalize_ts(bad, allow_never=True)
        self.assertIsNone(st.THEME_RE.match("alpha\n"))
        self.assertIsNone(st.ID_RE.match("c3\n"))
        self.assertIsNone(st.COMMIT_RE.match("abcdef1\n"))
        with self.assertRaises(st.RequestError):
            st.normalize_ref("t5\n\n" + "x")

    def test_batch_never_sets_dismissed(self):
        with self.assertRaises(st.RequestError):
            st.parse_batch("c1|1|dismissed|now|x\n")

    def test_batch_rejects_duplicates(self):
        with self.assertRaises(st.RequestError):
            st.parse_batch("c1|1|done|now|\nc1|2|open|now|\n")


class StoreFiles(unittest.TestCase):
    def test_unreadable_file_is_not_absent(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "todo.md")
            with open(path, "w") as fh:
                fh.write("x\n")
            os.chmod(path, 0)
            try:
                if os.access(path, os.R_OK):
                    self.skipTest("mode ignored for this user")
                with self.assertRaises(st.FormatError):
                    st._read_tolerant(path)
                with self.assertRaises(st.FormatError):
                    st.alloc_id(d)
            finally:
                os.chmod(path, 0o644)
            self.assertIsNone(st._read_tolerant(os.path.join(d, "absent.md")))

    def test_established_store_skips_content_inspection(self):
        with tempfile.TemporaryDirectory() as d:
            for name, kind in (("todo.md", "todo"), ("qa.md", "qa")):
                with open(os.path.join(d, name), "w") as fh:
                    fh.write(st.empty_text(kind))
            with open(os.path.join(d, "store.init"), "w") as fh:
                fh.write("format=1\n")
            orig = st._is_template
            st._is_template = lambda *_: self.fail("content read on an established store")
            try:
                self.assertIn("ESTABLISHED=1", st.store_state(d))
            finally:
                st._is_template = orig
            os.remove(os.path.join(d, "store.init"))
            self.assertIn("ESTABLISHED=0", st.store_state(d))

    def test_rev_scan_survives_a_lost_counter(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "todo.md.bak"), "w") as fh:
                fh.write(_item(1, rev=33).line() + "\n")
            self.assertEqual(st.alloc_rev(d), 34)


class IdScan(unittest.TestCase):
    def test_garbage_text_is_tolerated(self):
        self.assertEqual(st.max_id_token("\x00not markdown\n- c12 | rev=x\n"), 12)

    def test_commit_shas_do_not_inflate_ids(self):
        text = "- origin: agent=a commit=c1234567\n- sources:\n  - commit: c1234567\n"
        self.assertEqual(st.max_id_token(text), 0)

    def test_qa_items_count(self):
        self.assertEqual(st.max_id_token("## 2026-11-01T00:00:00Z | items: c3,c17\n"), 17)

    def test_alloc_takes_the_max_of_counter_and_scan(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "next_id"), "w") as fh:
                fh.write("4\n")
            with open(os.path.join(d, "qa.md"), "w") as fh:
                fh.write("## 2026-11-01T00:00:00Z | items: c9\n")
            self.assertEqual(st.alloc_id(d), 10)
            os.remove(os.path.join(d, "qa.md"))
            self.assertEqual(st.alloc_id(d), 4)


if __name__ == "__main__":
    unittest.main()
