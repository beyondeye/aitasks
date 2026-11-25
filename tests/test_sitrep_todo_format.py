#!/usr/bin/env python3
"""Unit tests for the sitrep store format core (lib/sitrep_todo.py, t2175_1).

The bash suite (tests/test_sitrep_todo.sh) owns locking, crashes and recovery;
this file owns the grammar: render∘parse identity, the strict refusals with
their line numbers, the generated-file banner, heading placement, rev bumps
and the id scan's tolerance of garbage.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
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
        self.assertRefusedAt(self.text.replace("format=4", "format=5"), 2)

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


class FormatVersions(unittest.TestCase):
    """todo.md format 4 (t2335_1): reads formats 1 to 3, writes format 4."""

    V1 = os.path.join(os.path.dirname(__file__), "fixtures", "sitrep",
                      "store_v1", "todo.md")

    def test_v1_fixture_round_trips_as_v1(self):
        with open(self.V1, encoding="utf-8") as fh:
            text = fh.read()
        parsed = st.parse_todo(text)
        self.assertEqual(parsed.format, 1)
        self.assertEqual(st.render_todo(parsed), text)

    def test_render_emits_the_parsed_version(self):
        s = _store(_item(1))
        s.format = 1
        self.assertIn("todo format=1 -->", st.render_todo(s).split("\n")[1])
        self.assertIn("todo format=4 -->", st.empty_text("todo").split("\n")[1])

    def test_v1_with_a_push_ref_is_refused_at_the_item_line(self):
        s = _store(_item(1), _item(2, kind="action", ref="push:main@abcdef1"))
        text = st.render_todo(s).replace("todo format=4", "todo format=1")
        lineno = text.split("\n").index(s.items[2].line()) + 1
        with self.assertRaises(st.FormatError) as cm:
            st.parse_todo(text, "todo.md")
        self.assertIn(f"todo.md:{lineno}:", str(cm.exception))
        self.assertIn("push refs need format=2", str(cm.exception))

    def test_v2_with_a_push_ref_parses(self):
        s = _store(_item(1, kind="action", ref="push:main@abcdef1"))
        self.assertEqual(st.parse_todo(st.render_todo(s)).items[1].ref,
                         "push:main@abcdef1")

    V2 = os.path.join(os.path.dirname(__file__), "fixtures", "sitrep",
                      "store_v2", "todo.md")

    def test_v2_fixture_round_trips_as_v2(self):
        with open(self.V2, encoding="utf-8") as fh:
            text = fh.read()
        parsed = st.parse_todo(text)
        self.assertEqual(parsed.format, 2)
        self.assertEqual(st.render_todo(parsed), text)

    V3 = os.path.join(os.path.dirname(__file__), "fixtures", "sitrep",
                      "store_v3", "todo.md")

    def test_current_fixture_is_v4_and_round_trips(self):
        with open(os.path.join(FIXTURE, "todo.md"), encoding="utf-8") as fh:
            text = fh.read()
        parsed = st.parse_todo(text)
        self.assertEqual(parsed.format, 4)
        self.assertEqual(st.render_todo(parsed), text)
        d = parsed.directions["sitrep"]
        self.assertEqual((d.rank, d.freshness, d.next), (1, "stale", "t2175_2"))
        self.assertEqual(st.baseline_status(FIXTURE, d.digest, "sitrep"), "ok")
        self.assertEqual(parsed.directions["board"].has_agent_fields(), False)
        self.assertEqual(parsed.directions["crashed-agents"].situation, [])
        self.assertEqual(st.direction_members(parsed)["crashed-agents"], [7])

    def test_v3_fixture_round_trips_as_v3(self):
        with open(self.V3, encoding="utf-8") as fh:
            text = fh.read()
        parsed = st.parse_todo(text)
        self.assertEqual(parsed.format, 3)
        self.assertEqual(st.render_todo(parsed), text)
        recover = {n: it.ref for n, it in parsed.items.items()
                   if st.parse_recover_ref(it.ref)}
        self.assertEqual(recover, {7: "recover:t42", 8: "recover:t43"})
        self.assertEqual(parsed.items[8].state, "dismissed")
        self.assertEqual(st.context_incarnation(parsed.contexts[7]), "0123456789ab")
        self.assertEqual(st.context_incarnation(parsed.contexts[8]), "89abcdef0123")

    def test_v2_with_a_recover_ref_is_refused_at_the_item_line(self):
        s = _store(_item(1), _item(2, ref="recover:t42"))
        text = st.render_todo(s).replace("todo format=4", "todo format=2")
        lineno = text.split("\n").index(s.items[2].line()) + 1
        with self.assertRaises(st.FormatError) as cm:
            st.parse_todo(text, "todo.md")
        self.assertIn(f"todo.md:{lineno}:", str(cm.exception))
        self.assertIn("recover refs need format=3", str(cm.exception))

    def test_v2_with_an_incarnation_origin_is_refused_at_the_origin_line(self):
        s = _store(_item(1))
        s.contexts[1] = st.ContextEntry("b", [("task", "t1"), ("incarnation", "0123456789ab")])
        text = st.render_todo(s).replace("todo format=4", "todo format=2")
        lineno = text.split("\n").index("- origin: task=t1 incarnation=0123456789ab") + 1
        with self.assertRaises(st.FormatError) as cm:
            st.parse_todo(text, "todo.md")
        self.assertIn(f"todo.md:{lineno}:", str(cm.exception))
        self.assertIn("incarnation origin key needs format=3", str(cm.exception))

    def test_v3_with_recover_and_incarnation_parses(self):
        s = _store(_item(1, ref="recover:t42_3"))
        s.contexts[1] = st.ContextEntry("b", [("task", "t42_3"), ("incarnation", "0123456789ab")])
        parsed = st.parse_todo(st.render_todo(s))
        self.assertEqual(parsed.items[1].ref, "recover:t42_3")
        self.assertEqual(st.context_incarnation(parsed.contexts[1]), "0123456789ab")

    def test_recover_ref_needs_kind_task_at_parse(self):
        s = _store(_item(1, ref="recover:t42"))
        text = st.render_todo(s).replace("kind=task", "kind=action")
        with self.assertRaises(st.FormatError) as cm:
            st.parse_todo(text, "todo.md")
        self.assertIn("recover: ref needs kind=task", str(cm.exception))

    def test_recover_ref_grammar(self):
        self.assertEqual(st.normalize_ref("recover:t42"), "recover:t42")
        self.assertEqual(st.parse_recover_ref("recover:t42"), "42")
        self.assertEqual(st.parse_recover_ref("recover:t42_3"), "42_3")
        for bad in ("recover:42", "recover:T42", "Recover:t42", "recover:t0",
                    "recover:t42_", "recover:t42_0", "recover:t042", "recover:",
                    "recover:proj#42", "recover:t42\n", "recover:t42 x"):
            with self.assertRaises(st.RequestError, msg=bad):
                st.normalize_ref(bad)
            self.assertIsNone(st.parse_recover_ref(bad), bad)
        for other in ("t42", "proj#42", "push:main@abcdef1", "", None):
            self.assertIsNone(st.parse_recover_ref(other), other)

    def test_incarnation_value_grammar(self):
        ok = st.validate_context_input(
            "- background: b\n- origin: task=t1 incarnation=0123456789ab\n")
        self.assertEqual(st.context_incarnation(ok), "0123456789ab")
        self.assertIsNone(st.context_incarnation(
            st.validate_context_input("- background: b\n- origin: task=t1\n")))
        for bad in ("0123456789a", "0123456789abc", "0123456789AB", "0123456789ag"):
            with self.assertRaises(st.RequestError, msg=bad):
                st.validate_context_input(
                    f"- background: b\n- origin: task=t1 incarnation={bad}\n")

    def test_qa_stays_format_1(self):
        qa = st.empty_text("qa")
        self.assertIn("qa format=1 -->", qa.split("\n")[1])
        with self.assertRaises(st.FormatError):
            st.parse_qa(qa.replace("qa format=1", "qa format=2"))

    def test_an_old_empty_generation_is_still_a_template(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "todo.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(st.render_todo(st.TodoStore(format=1)))
            self.assertTrue(st._is_template(path, "todo"))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(st.render_todo(_store(_item(1))))
            self.assertFalse(st._is_template(path, "todo"))

    def test_push_ref_grammar(self):
        self.assertEqual(st.normalize_ref("push:main@ABCDEF1"), "push:main@abcdef1")
        self.assertEqual(st.parse_push_ref("push:feature/x@abcdef1"),
                         ("feature/x", "abcdef1"))
        for bad in ("push:main", "push:@abcdef1", "push:main@abc12", "push:.x@abcdef1",
                    "push:a..b@abcdef1", "push:a//b@abcdef1", "push:a/@abcdef1",
                    "push:a.lock@abcdef1", "push:-x@abcdef1", "push:a/.b@abcdef1",
                    "push:a.@abcdef1", "push:main@abcdef1\n"):
            with self.assertRaises(st.RequestError, msg=bad):
                st.normalize_ref(bad)
            self.assertIsNone(st.parse_push_ref(bad), bad)


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

    def test_the_direction_key(self):
        self.assertEqual(self.ok(self.BASE + "- direction: sitrep\n").direction, "sitrep")
        self.bad(self.BASE + "- direction: Not A Slug\n", "invalid direction")
        # The key formats 1-3 used is not an alias in writer input.
        self.bad(self.BASE + "- theme: sitrep\n",
                 "allowed: background, origin, direction, sources, related")

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
        self.assertIsNone(st.DIRECTION_RE.match("alpha\n"))
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


# --- format 4: direction records (t2335_1) ------------------------------------

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sitrep")
DIGEST = "0123456789abcdef"


def _direction(**kw):
    base = dict(rev=5, title="Sitrep work", situation=["Harvest is next."])
    base.update(kw)
    return st.Direction(**base)


def _core(*argv, stdin_text=None):
    """Run the core CLI in process: (exit code, stdout lines)."""
    out = io.StringIO()
    args = list(argv)
    tmp = None
    if stdin_text is not None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".in", delete=False,
                                          encoding="utf-8")
        tmp.write(stdin_text)
        tmp.close()
        args += ["--input", tmp.name]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = st.main(args)
    finally:
        if tmp is not None:
            os.unlink(tmp.name)
    return rc, out.getvalue().splitlines()


def assert_same_content(test, old, new, *, changed_items=(), changed_directions=(),
                        added_directions=()):
    """The MIGRATION CHECK: two parsed stores hold the same items, the same
    context values and the same situation text, whatever format each was read
    from. `changed_*` name what the write under test changed on purpose."""
    test.assertEqual(sorted(old.items), sorted(new.items), "item ids")
    for num, a in old.items.items():
        b = new.items[num]
        if num in changed_items:
            continue
        test.assertEqual(a, b, f"item c{num}")
    test.assertEqual(sorted(old.contexts), sorted(new.contexts), "context ids")
    for num, a in old.contexts.items():
        b = new.contexts[num]
        for attr in ("background", "origin", "direction", "sources", "related"):
            test.assertEqual(getattr(a, attr), getattr(b, attr), f"c{num} {attr}")
    # An old block with no text holds nothing and is dropped by the migration.
    want = {s for s, d in old.directions.items() if d.situation} | set(added_directions)
    test.assertEqual(want, set(new.directions), "direction blocks")
    for slug in want - set(changed_directions) - set(added_directions):
        test.assertEqual(old.directions[slug].situation,
                         new.directions[slug].situation, f"situation of {slug}")


class DirectionGrammar(unittest.TestCase):
    def full(self):
        s = _store(_item(1), _item(2, state="done"))
        s.contexts[1] = st.ContextEntry("b", [("agent", "a")], direction="sitrep")
        s.directions["sitrep"] = _direction(
            rank=1, trails=["art:trail-a", "art:trail-b"], next="t12_3",
            summary="One paragraph.", digest=DIGEST, freshness="stale",
            checked_at="2026-11-20T10:00:00Z",
            drift=[("member_closed", 17, ["c3", "c5", "c8"]), ("next_invalid", 0, [])])
        s.directions["board"] = st.Direction(rev=6, situation=["Idle.", "", "Later."])
        return s

    def test_format_4_round_trips(self):
        text = st.render_todo(self.full())
        self.assertIn("todo format=4 -->", text.split("\n")[1])
        parsed = st.parse_todo(text)
        self.assertEqual(st.render_todo(parsed), text)
        d = parsed.directions["sitrep"]
        self.assertEqual((d.rev, d.rank, d.trails, d.next, d.digest, d.freshness),
                         (5, 1, ["art:trail-a", "art:trail-b"], "t12_3", DIGEST, "stale"))
        self.assertEqual(d.drift, [("member_closed", 17, ["c3", "c5", "c8"]),
                                   ("next_invalid", 0, [])])
        self.assertEqual(parsed.directions["board"].situation, ["Idle.", "", "Later."])
        self.assertEqual(parsed.contexts[1].direction, "sitrep")

    def test_the_header_is_always_nine_lines_in_order(self):
        lines = st.render_todo(self.full()).split("\n")
        at = lines.index("#### board | rev=6")
        self.assertEqual(lines[at + 1:at + 10],
                         ["- title:", "- rank:", "- trails:", "- next:", "- summary:",
                          "- digest:", "- freshness: unknown", "- checked_at: never",
                          "- drift:"])
        self.assertEqual(lines[at + 10], "Idle.")

    def test_situation_text_can_never_be_read_as_a_header_field(self):
        s = self.full()
        s.directions["board"].situation = ["- title: not a title", "- rank: 9"]
        parsed = st.parse_todo(st.render_todo(s))
        self.assertEqual(parsed.directions["board"].title, "")
        self.assertEqual(parsed.directions["board"].rank, 0)
        self.assertEqual(parsed.directions["board"].situation,
                         ["- title: not a title", "- rank: 9"])

    def refused(self, text, fragment, line=None):
        with self.assertRaises(st.FormatError) as cm:
            st.parse_todo(text, "todo.md")
        self.assertIn(fragment, str(cm.exception))
        if line is not None:
            self.assertIn(f"todo.md:{line}:", str(cm.exception))

    def test_header_refusals_name_their_line(self):
        lines = st.render_todo(self.full()).split("\n")
        at = lines.index("#### sitrep | rev=5")          # 0-based; heading line = at + 1
        swapped = list(lines)
        swapped[at + 1], swapped[at + 2] = swapped[at + 2], swapped[at + 1]
        self.refused("\n".join(swapped), "direction header line 1 must be '- title:", at + 2)
        missing = lines[:at + 9] + lines[at + 10:]        # drop '- drift:'
        self.refused("\n".join(missing), "direction header line 9 must be '- drift:", at + 10)
        short = lines[:at + 3] + ["", "### Pick now"] + lines[lines.index("### Pick now") + 1:]
        self.refused("\n".join(short), "direction header of 'sitrep' is incomplete")
        bad_rank = list(lines)
        bad_rank[at + 2] = "- rank: first"
        self.refused("\n".join(bad_rank), "invalid rank", at + 3)
        self.refused("\n".join(lines).replace("#### sitrep | rev=5", "#### sitrep"),
                     "not a direction heading", at + 1)

    def test_record_invariants(self):
        cases = [
            (dict(summary="s", digest=""), "summary and digest are set together"),
            (dict(summary="", digest=DIGEST), "summary and digest are set together"),
            (dict(freshness="current", checked_at="2026-11-20T10:00:00Z"),
             "'current' needs a digest"),
            (dict(freshness="current", checked_at="2026-11-20T10:00:00Z", summary="s",
                  digest=DIGEST, drift=[("x", 1, [])]), "'current' needs a digest and no drift"),
            (dict(freshness="stale", checked_at="2026-11-20T10:00:00Z"),
             "'stale' needs at least one drift reason"),
            (dict(freshness="stale", drift=[("x", 1, [])]), "needs a checked_at"),
            (dict(trails=["art:trail-a", "art:trail-a"]), "appears twice"),
            (dict(trails=["trail-a"]), "invalid trail handle"),
            (dict(next="12"), "next '12' is not in canonical form"),
            (dict(next="T12"), "invalid next 'T12'"),
            (dict(digest="xyz", summary="s"), "invalid digest"),
            (dict(drift=[("x", 1, []), ("x", 2, [])]), "appears twice"),
        ]
        for fields, fragment in cases:
            with self.subTest(fragment=fragment, fields=fields):
                s = _store(_item(1))
                s.directions["a"] = _direction(**fields)
                self.refused(st.render_todo(s), fragment)

    def test_ranks_are_unique_and_dense(self):
        for ranks, ok in (((1, 2), True), ((2, 1), True), ((1, 1), False),
                          ((1, 3), False), ((2, 0), False), ((0, 0), True)):
            with self.subTest(ranks=ranks):
                s = _store(_item(1))
                s.directions["a"] = _direction(rank=ranks[0])
                s.directions["b"] = _direction(rev=6, rank=ranks[1])
                text = st.render_todo(s)
                if ok:
                    st.parse_todo(text)
                else:
                    self.refused(text, "ranks must be exactly 1..k")

    def test_an_empty_block_does_not_exist(self):
        s = _store(_item(1))
        s.directions["a"] = st.Direction(rev=5)
        self.refused(st.render_todo(s), "holds nothing")
        # ... refresh fields alone do not keep a block either.
        s.directions["a"] = st.Direction(rev=5, freshness="unknown",
                                         checked_at="2026-11-20T10:00:00Z")
        self.refused(st.render_todo(s), "holds nothing")
        # A rank is agent-written: it does.
        s.directions["a"] = st.Direction(rev=5, rank=1)
        st.parse_todo(st.render_todo(s))

    def test_format_gating_both_ways(self):
        s4 = self.full()
        text4 = st.render_todo(s4)
        # Format-4 grammar under an older format= is refused, naming format 4.
        self.refused(text4.replace("todo format=4", "todo format=3"),
                     "direction records need format=4")
        legacy = _store(_item(1))
        legacy.format = 3
        legacy.contexts[1] = st.ContextEntry("b", [("agent", "a")], direction="x")
        text3 = st.render_todo(legacy)
        self.assertIn("- theme: x", text3)
        self.refused(text3.replace("- theme: x", "- direction: x"),
                     "direction context key needs format=4")
        # Old grammar under format=4 is refused too.
        self.refused(text4.replace("- direction: sitrep", "- theme: sitrep"),
                     "unknown context key 'theme'")
        s3 = _store(_item(1))
        s3.format = 3
        s3.directions["a"] = st.Direction(situation=["text"])
        self.refused(st.render_todo(s3).replace("todo format=3", "todo format=4"),
                     "not a direction heading")

    def test_legacy_formats_spell_the_key_theme(self):
        for fmt in (1, 2, 3):
            s = _store(_item(1))
            s.format = fmt
            s.contexts[1] = st.ContextEntry("b", [("agent", "a")], direction="x")
            s.directions["x"] = st.Direction(situation=["text"])
            text = st.render_todo(s)
            self.assertIn("- theme: x", text)
            self.assertIn("\n#### x\ntext\n", text)
            parsed = st.parse_todo(text)
            self.assertEqual(parsed.contexts[1].direction, "x")
            self.assertEqual(parsed.directions["x"].rev, 0)
            self.assertEqual(st.render_todo(parsed), text)
        # `context c<N>` and writer input always use the current spelling.
        self.assertEqual(s.contexts[1].body_lines()[2], "- direction: x")

    def test_a_newer_format_is_not_damage(self):
        text = st.empty_text("todo").replace("todo format=4", "todo format=5")
        with self.assertRaises(st.NewerFormatError) as cm:
            st.parse_todo(text, "todo.md")
        self.assertIn("newer than this writer supports", str(cm.exception))
        self.assertIn("update this checkout", str(cm.exception))
        self.assertEqual(st.newer_format(text), 5)
        self.assertIsNone(st.newer_format(st.empty_text("todo")))
        self.assertIsNone(st.newer_format("garbage\nformat=9\n"))
        # ... or end its lines with CR LF: the question is what line 2 declares.
        for crlf in (text.replace("\n", "\r\n"), text.replace("\n", "\r")):
            self.assertEqual(st.newer_format(crlf), 5)
            with self.assertRaises(st.NewerFormatError):
                st.parse_todo(crlf, "todo.md")
        self.assertIsNone(st.newer_format(st.empty_text("todo").replace("\n", "\r\n")))
        # A newer writer may reword its banner: still newer, not hand-edited.
        reworded = "<!-- some future banner -->\n" + text.split("\n", 1)[1]
        self.assertEqual(st.newer_format(reworded), 5)
        with self.assertRaises(st.NewerFormatError):
            st.parse_todo(reworded, "todo.md")
        self.assertIsNone(st.newer_format(None))

    def test_the_rev_scan_sees_direction_revs(self):
        self.assertEqual(st.max_rev_token("#### sitrep | rev=77\n- c1 | rev=4 | x"), 77)
        self.assertEqual(st.max_rev_token("text #### a | rev=99"), 0)
        self.assertEqual(st.max_rev_token("#### Not-A-Slug | rev=99"), 0)

    def test_the_context_size_limit_is_the_same_in_every_format(self):
        pad = "x" * 300
        entry = st.ContextEntry("b", [("agent", "a")], direction="d",
                                sources=[("file", f"docs/{pad}{i}.md") for i in range(6)])
        while len("\n".join(entry.body_lines(1)).encode()) < st.MAX_CONTEXT_BYTES:
            entry.background += "y"
        self.assertEqual(len("\n".join(entry.body_lines(1)).encode()), st.MAX_CONTEXT_BYTES)
        st._check_context_values(entry, None)     # at the limit as `theme:` ...
        s = _store(_item(1))
        s.contexts[1] = entry
        st.parse_todo(st.render_todo(s))          # ... and still valid as `direction:`
        entry.background += "y"
        with self.assertRaises(st.RequestError):
            st._check_context_values(entry, None)


class DirectionMembership(unittest.TestCase):
    def store(self):
        s = _store(_item(1), _item(2, ref="recover:t42"), _item(3, ref="recover:t43"),
                   _item(4, state="done"), _item(5), _item(6, state="unknown"))
        s.contexts[1] = st.ContextEntry("b", [("agent", "a")], direction="alpha")
        s.contexts[3] = st.ContextEntry("b", [("agent", "a")], direction="alpha")
        s.contexts[4] = st.ContextEntry("b", [("agent", "a")], direction="beta")
        s.contexts[5] = st.ContextEntry("b", [("agent", "a")])
        return s

    def test_item_direction(self):
        s = self.store()
        got = {n: st.item_direction(s, s.items[n]) for n in s.items}
        self.assertEqual(got, {1: "alpha", 2: st.RECOVERY_DIRECTION, 3: "alpha",
                               4: "beta", 5: "", 6: ""})
        self.assertEqual(st.item_direction(None, s.items[2]), st.RECOVERY_DIRECTION)
        self.assertEqual(st.item_direction(s, None), "")
        s.contexts[2] = st.ContextEntry("b", [("agent", "a")], direction="Not A Slug")
        self.assertEqual(st.item_direction(s, s.items[2]), st.RECOVERY_DIRECTION)

    def test_members_known_and_unassigned(self):
        s = self.store()
        self.assertEqual(st.direction_members(s),
                         {"alpha": [1, 3], st.RECOVERY_DIRECTION: [2], "beta": [4]})
        self.assertEqual(st.pending_members(s, "beta"), [])
        self.assertEqual(st.unassigned_items(s), [5, 6])
        s.directions["zeta"] = _direction(rank=1)
        s.directions["beta"] = _direction(rank=2)
        self.assertEqual(st.known_directions(s),
                         ["zeta", "beta", "alpha", st.RECOVERY_DIRECTION])

    def test_the_reserved_slug_is_refused_in_input_only(self):
        with self.assertRaises(st.RequestError) as cm:
            st.validate_context_input(
                f"- background: b\n- origin: agent=a\n- direction: {st.RECOVERY_DIRECTION}\n")
        self.assertIn("reserved", str(cm.exception))
        with self.assertRaises(st.RequestError):
            st.validate_context_input("- background: b\n- origin: agent=a\n- theme: x\n")
        s = _store(_item(1))
        s.contexts[1] = st.ContextEntry("b", [("agent", "a")],
                                        direction=st.RECOVERY_DIRECTION)
        st.parse_todo(st.render_todo(s))          # an existing file still reads

    def test_the_stamp_moves_with_every_store_side_input(self):
        s = self.store()
        base = st.direction_stamp(s, "alpha")
        self.assertRegex(base, r"^[0-9a-f]{16}$")
        self.assertEqual(st.direction_stamp(self.store(), "alpha"), base)
        moved_in = self.store()
        moved_in.contexts[5].direction = "alpha"
        self.assertNotEqual(st.direction_stamp(moved_in, "alpha"), base, "member added")
        moved_out = self.store()
        moved_out.contexts[3].direction = "beta"
        self.assertNotEqual(st.direction_stamp(moved_out, "alpha"), base, "member removed")
        changed = self.store()
        changed.items[1].rev = 99      # what any change to the item or its context does
        self.assertNotEqual(st.direction_stamp(changed, "alpha"), base, "member changed")
        self.assertEqual(st.direction_stamp(s, "alpha", [1, 3]), base, "given members")
        # Negative control: another direction's member does not move it.
        other = self.store()
        other.items[4].rev = 99
        self.assertEqual(st.direction_stamp(other, "alpha"), base)


class Drift(unittest.TestCase):
    def test_more_causes_than_reasons_fit(self):
        pairs = [("member_closed", f"c{i}") for i in range(20, 0, -1)]
        pairs += [("trail_stale", "art:trail-x"), ("never_summarized", "")]
        got = st.aggregate_drift(pairs)
        self.assertEqual(got, [("member_closed", 20, ["c1", "c2", "c3"]),
                               ("trail_stale", 1, ["art:trail-x"]),
                               ("never_summarized", 1, [])])
        self.assertEqual([st.render_reason(r) for r in got],
                         ["member_closed:20:c1+c2+c3", "trail_stale:1:art:trail-x",
                          "never_summarized:1"])
        self.assertEqual([st.parse_reason(st.render_reason(r)) for r in got], got)

    def test_a_key_that_does_not_fit_is_left_out_and_still_counted(self):
        long_handle = "art:trail-" + "x" * 122
        self.assertEqual(len(long_handle), 132)
        too_long = long_handle + "=tasks_changed"
        got = st.aggregate_drift([("trail_stale", too_long), ("trail_stale", long_handle)])
        self.assertEqual(got, [("trail_stale", 2, [long_handle])])
        only_long = st.aggregate_drift([("trail_stale", too_long), ("trail_stale", "a b")])
        self.assertEqual(only_long, [("trail_stale", 2, [])])
        self.assertEqual(st.render_reason(only_long[0]), "trail_stale:2")
        st._check_drift(got)                       # a legal 132-char handle is a valid key

    def test_duplicates_count_once_and_code_order_is_first_seen(self):
        got = st.aggregate_drift([("b", "c2"), ("a", "c1"), ("b", "c2"), ("b", "c10")])
        self.assertEqual(got, [("b", 2, ["c2", "c10"]), ("a", 1, ["c1"])])

    def test_too_many_codes_is_an_error_not_a_cut(self):
        st.aggregate_drift([(f"code{i}", "") for i in range(st.MAX_DRIFT_CODES)])
        with self.assertRaises(st.RequestError):
            st.aggregate_drift([(f"code{i}", "") for i in range(st.MAX_DRIFT_CODES + 1)])

    def test_reason_refusals(self):
        for bad in ("Member", "x:0", "x:1:", "x:one", "x:1:a b", "x:-1", ""):
            with self.subTest(bad):
                with self.assertRaises(st.RequestError):
                    st.parse_drift(bad or "x:")
        for bad in ("x:2:a+b+c+d", "x:1:a+b", "x:2:a+a", "x,x", "x:1," + "x:2"):
            with self.subTest(bad):
                with self.assertRaises(st.RequestError):
                    st.parse_drift(bad)
        self.assertEqual(st.parse_drift("x, y:3:k1+k2 ,z:4"),
                         [("x", 0, []), ("y", 3, ["k1", "k2"]), ("z", 4, [])])


class TrailHandles(unittest.TestCase):
    def test_every_accepted_handle_is_a_legal_artifact_handle(self):
        import artifact_manifest as am
        longest = "art:trail-" + "a" * 122
        samples = ["art:trail-a", "art:trail-sitrep-1", "art:trail-a.b_c-d", longest]
        for h in samples:
            self.assertTrue(st.TRAIL_HANDLE_RE.match(h), h)
            self.assertTrue(am.HANDLE_RE.match(h), h)
        self.assertEqual(len(longest), 132)
        self.assertEqual(st.MAX_DRIFT_KEY, 132)
        self.assertTrue(st.DRIFT_KEY_RE.match(longest))
        for bad in (longest + "a", "art:trail-", "art:trail-A", "art:other-a",
                    "trail-a", "art:trail-a\n", "art:trail-a b"):
            self.assertIsNone(st.TRAIL_HANDLE_RE.match(bad), bad)
        self.assertIsNone(am.HANDLE_RE.match(longest + "a"))


class Baselines(unittest.TestCase):
    GOOD = ("sitrep direction baseline v1\n"
            "direction: sitrep\n"
            "member: c1|open|t2175_2\n"
            "member: c6|unknown|push:main@1a2b3c4d5e6f\n"
            "member: c10|open|\n"
            "task: aitasks#12|Done\n"
            "task: t2175_2|Implementing\n"
            "trail: art:trail-sitrep-1|v3:current\n"
            "next: t2175_2|valid\n")

    def test_a_snapshot_parses(self):
        b = st.parse_baseline(self.GOOD)
        self.assertEqual(b.slug, "sitrep")
        self.assertEqual(b.members, [(1, "open", "t2175_2"),
                                     (6, "unknown", "push:main@1a2b3c4d5e6f"),
                                     (10, "open", "")])
        self.assertEqual(b.tasks, [("aitasks#12", "Done"), ("t2175_2", "Implementing")])
        self.assertEqual(b.trails, [("art:trail-sitrep-1", "v3:current")])
        self.assertEqual(b.next, ("t2175_2", "valid"))
        minimal = st.parse_baseline("sitrep direction baseline v1\ndirection: x\n")
        self.assertEqual((minimal.members, minimal.next), ([], None))

    def test_grammar_refusals(self):
        g = self.GOOD
        cases = {
            "wrong header": g.replace("baseline v1", "baseline v2"),
            "missing newline": g.rstrip("\n"),
            "blank line": g.replace("task: t2175_2", "\ntask: t2175_2"),
            "carriage return": g.replace("\n", "\r\n", 1),
            "unsorted members": g.replace("member: c1|open|t2175_2\nmember: c6",
                                          "member: c7|open|t2175_2\nmember: c6"),
            "ids sort by number": g.replace("member: c10|open|\n", "").replace(
                "member: c6|", "member: c10|open|\nmember: c6|"),
            "duplicate key": g.replace("task: t2175_2|Implementing\n",
                                       "task: t2175_2|Implementing\ntask: t2175_2|Done\n"),
            "kinds out of order": g.replace("next: t2175_2|valid\n", "").replace(
                "task: aitasks#12", "next: t2175_2|valid\ntask: aitasks#12"),
            "two next lines": g + "next: t9|valid\n",
            "closed member": g.replace("c1|open|", "c1|done|"),
            "ref not canonical": g.replace("c1|open|t2175_2", "c1|open|2175_2"),
            "bad trail": g.replace("art:trail-sitrep-1", "trail-sitrep-1"),
            "bad value": g.replace("v3:current", "v3 current"),
            "unknown kind": g + "note: x|y\n",
            "no slug": g.replace("direction: sitrep", "direction: Not A Slug"),
        }
        for name, text in cases.items():
            with self.subTest(name):
                with self.assertRaises(st.RequestError):
                    st.parse_baseline(text)

    def exactly(self, size):
        """A valid snapshot of exactly `size` bytes."""
        head = "sitrep direction baseline v1\ndirection: big\n"
        lines, n, total = [], 0, len(head)
        tail = "next: t1|"
        while True:
            left = size - total - len(tail) - 1
            if 0 <= left <= 120:
                break
            n += 1
            line = f"member: c{n}|open|t{n}\n"
            lines.append(line)
            total += len(line)
        text = head + "".join(lines) + tail + "v" * left + "\n"
        self.assertEqual(len(text.encode()), size)
        return text

    def test_the_size_boundary(self):
        at = self.exactly(st.MAX_BASELINE_BYTES)
        self.assertGreater(len(st.parse_baseline(at).members), 3000)
        over = self.exactly(st.MAX_BASELINE_BYTES + 1)
        with self.assertRaises(st.RequestError) as cm:
            st.parse_baseline(over)
        self.assertIn(f"{st.MAX_BASELINE_BYTES + 1} bytes", str(cm.exception))
        self.assertIn(f"limit {st.MAX_BASELINE_BYTES}", str(cm.exception))

    def write(self, d, text, name=None):
        os.makedirs(os.path.join(d, "baselines"), exist_ok=True)
        digest = name or hashlib.sha256(text.encode()).hexdigest()[:16]
        with open(os.path.join(d, "baselines", f"{digest}.txt"), "w",
                  encoding="utf-8", newline="") as fh:
            fh.write(text)
        return digest

    def test_status_is_ok_only_for_verified_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            digest = self.write(d, self.GOOD)
            path = os.path.join(d, "baselines", f"{digest}.txt")
            self.assertEqual(st.baseline_status(d, digest, "sitrep"), "ok")
            self.assertEqual(st.baseline_status(d, digest, "other"), "wrong_direction")
            self.assertEqual(st.baseline_status(d, "f" * 16, "sitrep"), "missing")
            self.assertEqual(st.baseline_status(d, "", "sitrep"), "missing")
            # A valid-looking but DIFFERENT snapshot at the right path.
            self.write(d, self.GOOD.replace("Implementing", "Done"), name=digest)
            self.assertEqual(st.baseline_status(d, digest, "sitrep"), "hash_mismatch")
            self.write(d, self.GOOD[:40], name=digest)          # truncated
            self.assertEqual(st.baseline_status(d, digest, "sitrep"), "hash_mismatch")
            os.remove(path)
            os.symlink(os.path.join(d, "elsewhere"), path)
            self.assertEqual(st.baseline_status(d, digest, "sitrep"), "not_regular")
            os.remove(path)
            os.mkdir(path)
            self.assertEqual(st.baseline_status(d, digest, "sitrep"), "not_regular")
            os.rmdir(path)
            # Bytes that hash to the name but are not a snapshot.
            junk = "not a snapshot\n"
            self.assertEqual(st.baseline_status(d, self.write(d, junk), "sitrep"),
                             "bad_grammar")

    def test_differences_are_the_store_side_lines(self):
        s = _store(_item(1, ref="t2175_2"), _item(6, state="unknown",
                                                  ref="push:main@1a2b3c4d5e6f"),
                   _item(10), _item(11, state="done"))
        for n in (1, 6, 10, 11):
            s.contexts[n] = st.ContextEntry("b", [("agent", "a")], direction="sitrep")
        rec = st.Direction(trails=["art:trail-sitrep-1"], next="t2175_2")
        b = st.parse_baseline(self.GOOD)
        self.assertEqual(st.baseline_differences(s, "sitrep", rec, b), [])
        s.items[1].state = "done"                      # a member closed
        s.items[6].ref = "push:main@ffffffffffff"      # a member's ref moved
        s.items[11].state = "open"                     # a closed member reopened
        rec.trails = ["art:trail-other"]
        rec.next = ""
        self.assertEqual(st.baseline_differences(s, "sitrep", rec, b),
                         [("member", "c1"), ("member", "c6"), ("member", "c11"),
                          ("trail", "art:trail-other"), ("trail", "art:trail-sitrep-1"),
                          ("next", "t2175_2")])


class Migration(unittest.TestCase):
    """The first changing write upgrades a format 1-3 file: same content, new
    representation -- and the same for the backup it leaves."""

    def upgrade(self, name):
        src = os.path.join(FIXTURES, name)
        with tempfile.TemporaryDirectory() as d:
            store = os.path.join(d, "store")
            shutil.copytree(src, store)
            with open(os.path.join(store, "todo.md"), encoding="utf-8") as fh:
                before = fh.read()
            out, bak = os.path.join(d, "out.md"), os.path.join(d, "bak.md")
            rc, lines = _core("update", "c4", "--title", "CI renamed", "--store", store,
                              "--out", out, "--out-bak", bak)
            self.assertEqual(rc, 0, lines)
            with open(out, encoding="utf-8") as fh:
                live = fh.read()
            with open(bak, encoding="utf-8") as fh:
                backup = fh.read()
        return before, live, backup, lines

    def test_every_older_fixture_keeps_its_content(self):
        for name, fmt in (("store_v1", 1), ("store_v2", 2), ("store_v3", 3)):
            with self.subTest(name):
                before, live, backup, lines = self.upgrade(name)
                old = st.parse_todo(before)
                self.assertEqual(old.format, fmt)
                self.assertTrue(any(d.situation for d in old.directions.values()),
                                "the fixture has situation blocks to migrate")
                self.assertTrue(any(c.direction for c in old.contexts.values()),
                                "the fixture has direction keys to migrate")
                new, bak = st.parse_todo(live), st.parse_todo(backup)
                self.assertEqual((new.format, bak.format), (4, 4))
                assert_same_content(self, old, new, changed_items=(4,))
                self.assertEqual(new.items[4].title, "CI renamed")
                assert_same_content(self, old, bak)
                self.assertIn(f"@BAK_MIGRATED:{fmt}", lines)
                self.assertNotIn("- theme:", live + backup)
                self.assertIn("- direction: sitrep", live)
                # Every block is stamped; an unchanged block has ONE rev in both.
                for slug, d in new.directions.items():
                    self.assertGreater(d.rev, 0)
                    self.assertEqual(bak.directions[slug].rev, d.rev, slug)
                top = max(max(i.rev for i in new.items.values()),
                          max(d.rev for d in new.directions.values()))
                self.assertIn(f"@NEXT_REV:{top + 1}", lines)

    def test_a_changed_block_has_distinct_revs_in_file_and_backup(self):
        src = os.path.join(FIXTURES, "store_v3")
        with tempfile.TemporaryDirectory() as d:
            store = os.path.join(d, "store")
            shutil.copytree(src, store)
            out, bak = os.path.join(d, "out.md"), os.path.join(d, "bak.md")
            rc, _ = _core("situation", "sitrep", "--store", store, "--out", out,
                          "--out-bak", bak, stdin_text="New text.\n")
            self.assertEqual(rc, 0)
            new = st.parse_todo(open(out, encoding="utf-8").read())
            old = st.parse_todo(open(bak, encoding="utf-8").read())
        self.assertEqual(new.directions["sitrep"].situation, ["New text."])
        self.assertEqual(old.directions["sitrep"].situation[0],
                         "Harvest is next; refresh waits on it.")
        self.assertNotEqual(new.directions["sitrep"].rev, old.directions["sitrep"].rev)
        self.assertEqual(new.directions["board"].rev, old.directions["board"].rev)

    def test_an_empty_legacy_block_is_dropped(self):
        s = _store(_item(1))
        s.format = 3
        s.directions["gone"] = st.Direction()
        s.directions["kept"] = st.Direction(situation=["text"])
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "todo.md"), "w", encoding="utf-8", newline="") as fh:
                fh.write(st.render_todo(s))
            out, bak = os.path.join(d, "out.md"), os.path.join(d, "bak.md")
            rc, _ = _core("update", "c1", "--title", "renamed", "--store", d,
                          "--out", out, "--out-bak", bak)
            self.assertEqual(rc, 0)
            for path in (out, bak):
                got = st.parse_todo(open(path, encoding="utf-8").read())
                self.assertEqual(sorted(got.directions), ["kept"])

    def test_a_no_op_writes_nothing(self):
        src = os.path.join(FIXTURES, "store_v3")
        with tempfile.TemporaryDirectory() as d:
            store = os.path.join(d, "store")
            shutil.copytree(src, store)
            out, bak = os.path.join(d, "out.md"), os.path.join(d, "bak.md")
            rc, lines = _core("update", "c4", "--title", "CI on the sitrep branch",
                              "--store", store, "--out", out, "--out-bak", bak)
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(out) and os.path.getsize(out))
            self.assertFalse(os.path.exists(bak) and os.path.getsize(bak))
            self.assertNotIn("@BAK_MIGRATED:3", lines)


if __name__ == "__main__":
    unittest.main()
