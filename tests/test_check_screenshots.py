"""Tests for the screenshot-marker grammar and checker (t2278_1).

`website/screenshots/markers.py` defines the one placeholder grammar doc
authors use; `website/check_screenshots.py` reports markers that do not parse,
markers whose scene is missing or disagrees on ownership, image shortcodes with
no file, and markers still unresolved.

Every assertion runs against a synthetic scratch tree (content / static /
scenes) in a temporary directory, never against `website/content/`.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_check_screenshots.py -v
"""
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

import check_screenshots as cs  # noqa: E402
from screenshots import markers as mk  # noqa: E402

HAVE_YAML = importlib.util.find_spec("yaml") is not None

GOOD = ('<!-- screenshot: scene=board_child_tasks file=aitasks_board_child_tasks.svg '
        'alt="Board with a parent task expanded to show its child tasks" '
        'caption="An expanded parent task with its child tasks." -->')

#: The scene-spec example from the parent design, verbatim (the line with the
#: trailing comment is the case a naive `\S+$` reader rejects).
PARENT_SPEC = """\
id: board_child_tasks
output: aitasks_board_child_tasks.svg   # required; relative to website/static/imgs/
backend: textual            # textual | tmux | pixels
app: board                  # key into registry.APPS
fixture: {name: board_rich, params: {}}
size: [160, 48]
"""


class Tree:
    """A throwaway content / static / scenes tree."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.content = self.root / "content"
        self.static = self.root / "static"
        self.scenes = self.root / "scenes"
        for d in (self.content, self.static / "imgs", self.scenes):
            d.mkdir(parents=True)

    def page(self, rel, body):
        p = self.content / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        return p

    def image(self, rel):
        p = self.static / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<svg/>", encoding="utf-8")

    def spec(self, stem, body):
        (self.scenes / f"{stem}.yaml").write_text(body, encoding="utf-8")

    def run(self, *flags):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cs.main(["--content", str(self.content), "--static", str(self.static),
                          "--scenes", str(self.scenes), *flags])
        return rc, buf.getvalue()

    def cleanup(self):
        self._tmp.cleanup()


class TreeCase(unittest.TestCase):
    def setUp(self):
        self.t = Tree()
        self.addCleanup(self.t.cleanup)


class ParseMarkerTests(unittest.TestCase):
    def test_valid_marker_parses(self):
        m = mk.parse_marker(GOOD)
        self.assertIsInstance(m, mk.Marker)
        self.assertEqual(m.scene, "board_child_tasks")
        self.assertEqual(m.file, "aitasks_board_child_tasks.svg")
        self.assertEqual(m.alt, "Board with a parent task expanded to show its child tasks")
        self.assertEqual(m.caption, "An expanded parent task with its child tasks.")
        self.assertIsNone(m.cls)

    def test_bare_values_class_and_subdir_file(self):
        m = mk.parse_marker('<!-- screenshot: scene=s1 file=home/board.svg alt="A" class=wide -->')
        self.assertIsInstance(m, mk.Marker)
        self.assertEqual((m.file, m.cls), ("home/board.svg", "wide"))

    def test_apostrophe_in_alt_is_accepted(self):
        m = mk.parse_marker('<!-- screenshot: scene=s file=f.svg alt="One trail\'s waves" -->')
        self.assertIsInstance(m, mk.Marker)
        self.assertEqual(m.alt, "One trail's waves")

    def test_leading_spaces_and_trailing_whitespace(self):
        self.assertIsInstance(mk.parse_marker('   <!-- screenshot: scene=s file=f.svg alt="A" -->  '), mk.Marker)
        self.assertIsInstance(mk.parse_marker('    <!-- screenshot: scene=s file=f.svg alt="A" -->'), str)

    def test_legacy_shapes_are_rejected(self):
        for text in (
            "<!-- TODO screenshot: aitasks_ait_ide_startup.svg — the monitor dashboard -->",
            "<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->",
            "<!-- SCREENSHOT: aitasks_trails_main_view.svg — ait trails main view -->",
            "<!-- SCREENSHOT: Close-up of a single task card with annotations -->",
        ):
            with self.subTest(text=text):
                self.assertIsInstance(mk.parse_marker(text), str)

    def test_rejections(self):
        cases = {
            "unknown key": '<!-- screenshot: scene=s file=f.svg alt="A" size=3 -->',
            "duplicate key": '<!-- screenshot: scene=s file=f.svg alt="A" alt="B" -->',
            "missing required key 'alt'": '<!-- screenshot: scene=s file=f.svg -->',
            "missing required key 'scene'": '<!-- screenshot: file=f.svg alt="A" -->',
            "missing required key 'file'": '<!-- screenshot: scene=s alt="A" -->',
            "scene must match": '<!-- screenshot: scene=Board-1 file=f.svg alt="A" -->',
            "relative to static/imgs/": '<!-- screenshot: scene=s file=/imgs/f.svg alt="A" -->',
            "canonical path": '<!-- screenshot: scene=s file=../f.svg alt="A" -->',
            "canonical path ": '<!-- screenshot: scene=s file=./f.svg alt="A" -->',
            "canonical path  ": '<!-- screenshot: scene=s file=home//f.svg alt="A" -->',
            "canonical path   ": '<!-- screenshot: scene=s file=home/ alt="A" -->',
            "becomes the image URL": '<!-- screenshot: scene=s file="a#b.svg" alt="A" -->',
            "becomes the image URL ": '<!-- screenshot: scene=s file="a?b.svg" alt="A" -->',
            "becomes the image URL  ": '<!-- screenshot: scene=s file="a b.svg" alt="A" -->',
            "becomes the image URL   ": '<!-- screenshot: scene=s file="a%20b.svg" alt="A" -->',
            "becomes the image URL    ": '<!-- screenshot: scene=s file="a~b.svg" alt="A" -->',
            "forbidden '--'": '<!-- screenshot: scene=s file=f.svg alt="a -- b" -->',
            "forbidden '\\\\'": '<!-- screenshot: scene=s file=f.svg alt="a\\b" -->',
            "empty value": '<!-- screenshot: scene=s file=f.svg alt="" -->',
            "cannot parse": '<!-- screenshot: scene=s file=f.svg alt="A"junk -->',
        }
        for expect, text in cases.items():
            with self.subTest(expect=expect):
                res = mk.parse_marker(text)
                self.assertIsInstance(res, str, text)
                self.assertIn(expect.strip(), res)

    def test_trailing_backslash_is_rejected(self):
        res = mk.parse_marker('<!-- screenshot: scene=s file=f.svg alt="ends in\\" -->')
        self.assertIsInstance(res, str)

    def test_quote_inside_value_cannot_parse(self):
        self.assertIsInstance(mk.parse_marker('<!-- screenshot: scene=s file=f.svg alt="a"b" -->'), str)


class RenderTests(unittest.TestCase):
    def test_render_with_caption(self):
        m = mk.parse_marker(GOOD)
        self.assertEqual(
            mk.render_static_img(m),
            '{{< static-img src="imgs/aitasks_board_child_tasks.svg" '
            'alt="Board with a parent task expanded to show its child tasks" '
            'caption="An expanded parent task with its child tasks." >}}')

    def test_render_without_caption_with_class(self):
        m = mk.parse_marker('<!-- screenshot: scene=s file=home/b.svg alt="A board" class="wide" -->')
        self.assertEqual(mk.render_static_img(m),
                         '{{< static-img src="imgs/home/b.svg" alt="A board" class="wide" >}}')

    def test_render_refuses_hand_built_bad_marker(self):
        bad = mk.Marker(path="", line=0, text="", scene="s", file="f.svg", alt="ends in\\")
        with self.assertRaises(ValueError):
            mk.render_static_img(bad)
        with self.assertRaises(ValueError):
            mk.render_static_img(mk.Marker("", 0, "", "s", "f.svg", "A", caption='say "hi"'))


class ScanTests(TreeCase):
    def test_fenced_block_is_ignored(self):
        self.t.page("a.md", "x\n```\n<!-- SCREENSHOT: example -->\n```\n~~~~\n<!-- screenshot: nope -->\n~~~~\n")
        markers, bad = mk.scan(self.t.content)
        self.assertEqual((markers, bad), ([], []))

    def test_multiline_screenshot_comment_is_unparseable(self):
        self.t.page("a.md", "x\n<!--\n screenshot: here\n-->\ny\n")
        _, bad = mk.scan(self.t.content)
        self.assertEqual([(b.line, b.reason) for b in bad], [(2, "multi-line")])

    def test_inline_code_opener_does_not_swallow_later_marker(self):
        self.t.page("a.md", "text `<!-- aitask-contribute-metadata` block\nmore\n" + GOOD + "\n")
        markers, bad = mk.scan(self.t.content)
        self.assertEqual(bad, [])
        self.assertEqual([m.line for m in markers], [3])

    def test_inline_screenshot_comment_is_unparseable(self):
        self.t.page("a.md", "See this <!-- screenshot: scene=s file=f.svg alt=\"A\" --> here\n")
        _, bad = mk.scan(self.t.content)
        self.assertEqual([b.reason for b in bad], ["inline comment"])

    def test_unrelated_multiline_comment_is_ignored(self):
        self.t.page("a.md", "<!--\n  Drift note for maintainers\n-->\n" + GOOD + "\n")
        markers, bad = mk.scan(self.t.content)
        self.assertEqual((len(markers), bad), (1, []))

    def test_backtick_info_string_with_backtick_is_not_a_fence(self):
        # CommonMark (and Goldmark in Hugo) render this first line as text, so
        # the marker after it is a real comment and must be found.
        self.t.page("a.md", "```bad`info\n\n" + GOOD + "\n")
        markers, bad = mk.scan(self.t.content)
        self.assertEqual(([m.line for m in markers], bad), ([3], []))

    def test_tilde_info_string_may_contain_backtick(self):
        self.t.page("a.md", "~~~ ok`info\n" + GOOD + "\n~~~\n")
        self.assertEqual(mk.scan(self.t.content), ([], []))

    def test_marker_after_closed_fence_is_found(self):
        self.t.page("a.md", "````\n```\nstill code\n````\n" + GOOD + "\n")
        markers, bad = mk.scan(self.t.content)
        self.assertEqual(([m.line for m in markers], bad), ([5], []))


class SpecOwnerTests(TreeCase):
    #: line -> expected value
    ACCEPTED = {
        "output: aitasks_board_child_tasks.svg   # required; relative to website/static/imgs/":
            "aitasks_board_child_tasks.svg",
        "id: board_child_tasks": "board_child_tasks",
        "output: home/board.svg": "home/board.svg",
        'output: "a b.svg"': "a b.svg",
        "output: 'a#b.svg'": "a#b.svg",
        'id: "123"': "123",
        'id: "on"': "on",
        "id: 'null'": "null",
        'output: "x.svg" # c': "x.svg",
        "output: x.svg ": "x.svg",
    }
    #: (class, line). Classes pin why each rejection is justified (see test).
    REJECTED = [
        *[("typed", ln) for ln in (
            "id: on", "id: off", "id: yes", "id: True", "id: null", "id: 123",
            "output: 1.0", "output: .inf", "id: 2026-11-15", "id: 1_000", "id: 0x1F")],
        ("truncation", "output: a.svg#x"),
        *[("tab", ln) for ln in ("output:\ta.svg", "output: a.svg\t", 'output: "a.svg"\t# c')],
        *[("structural", ln) for ln in (
            'output: "a\\"b.svg"', "output: |", "output: [a.svg]", "output:",
            "output: a.svg extra", 'output: "a.svg"#c')],
    ]

    def test_parent_design_example_reads(self):
        self.t.spec("board_child_tasks", PARENT_SPEC)
        owner = mk.read_spec_owner(self.t.scenes / "board_child_tasks.yaml")
        self.assertEqual((owner.id, owner.output, owner.problems),
                         ("board_child_tasks", "aitasks_board_child_tasks.svg", []))

    def test_accepted_lines(self):
        for line, want in self.ACCEPTED.items():
            with self.subTest(line=line):
                _, value, problem = mk.read_spec_scalar(line)
                self.assertEqual((value, problem), (want, None))

    def test_rejected_lines(self):
        for cls, line in self.REJECTED:
            with self.subTest(line=line):
                _, value, problem = mk.read_spec_scalar(line)
                self.assertIsNone(value)
                if cls == "typed":
                    self.assertIn("quote it", problem)
                else:
                    self.assertIn("not a supported single-line scalar", problem)

    def test_missing_and_duplicated_keys(self):
        self.t.spec("a", "id: a\n")
        self.assertEqual(mk.read_spec_owner(self.t.scenes / "a.yaml").problems, ["output: missing"])
        self.t.spec("b", "id: b\noutput: x.svg\noutput: y.svg\n")
        owner = mk.read_spec_owner(self.t.scenes / "b.yaml")
        self.assertEqual((owner.output, owner.problems), (None, ["output: duplicated"]))

    def test_noncanonical_output_is_a_problem(self):
        for out in ('"./x.svg"', "a//x.svg", "home/", "../x.svg", "/x.svg",
                    '"a#b.svg"', '"a?b.svg"', '"a b.svg"'):
            with self.subTest(output=out):
                self.t.spec("a", f"id: a\noutput: {out}\n")
                owner = mk.read_spec_owner(self.t.scenes / "a.yaml")
                self.assertIsNone(owner.output)
                self.assertEqual(len(owner.problems), 1, owner.problems)
                self.assertIn("output", owner.problems[0])

    def test_nested_keys_do_not_count(self):
        self.t.spec("a", "id: a\nlayout:\n  output: nested.svg\n")
        self.assertEqual(mk.read_spec_owner(self.t.scenes / "a.yaml").problems, ["output: missing"])

    @unittest.skipUnless(HAVE_YAML, "PyYAML not importable")
    def test_agreement_with_pyyaml(self):
        import yaml
        for line, want in self.ACCEPTED.items():
            with self.subTest(accepted=line):
                key = line.split(":", 1)[0]
                got = yaml.safe_load(line)[key]
                self.assertIsInstance(got, str)
                self.assertEqual(got, want)
        for cls, line in self.REJECTED:
            key = line.split(":", 1)[0]
            with self.subTest(rejected=line, cls=cls):
                if cls == "typed":
                    self.assertNotIsInstance(yaml.safe_load(line)[key], str)
                elif cls == "truncation":
                    self.assertEqual(yaml.safe_load(line)[key], "a.svg#x")
                elif cls == "tab":
                    with self.assertRaises(yaml.YAMLError):
                        yaml.safe_load(line)


class CheckerTests(TreeCase):
    def test_unparseable_fails_and_report_exits_zero(self):
        self.t.page("a.md", "<!-- TODO screenshot: f.svg -->\n")
        rc, out = self.t.run()
        self.assertEqual(rc, 1)
        self.assertIn("a.md:1: UNPARSEABLE", out)
        rc, out = self.t.run("--report")
        self.assertEqual(rc, 0)
        self.assertIn("UNPARSEABLE", out)
        self.assertNotIn("SCREENSHOTS:", out)

    def test_valid_marker_without_scene_is_a_warning(self):
        self.t.page("a.md", GOOD + "\n")
        rc, out = self.t.run()
        self.assertEqual(rc, 0)
        self.assertIn("NO_SCENE", out)
        self.assertIn("UNRESOLVED", out)
        self.assertIn("SCREENSHOTS: PASSED", out)

    def test_missing_scene_severity_error_fails(self):
        self.t.page("a.md", GOOD + "\n")
        old = cs.MISSING_SCENE_SEVERITY
        cs.MISSING_SCENE_SEVERITY = "error"
        self.addCleanup(setattr, cs, "MISSING_SCENE_SEVERITY", old)
        rc, _ = self.t.run()
        self.assertEqual(rc, 1)

    def test_strict_fails_on_unresolved(self):
        self.t.page("a.md", GOOD + "\n")
        self.t.spec("board_child_tasks", PARENT_SPEC)
        rc, out = self.t.run()
        self.assertEqual(rc, 0)
        self.assertNotIn("NO_SCENE", out)
        rc, _ = self.t.run("--strict")
        self.assertEqual(rc, 1)

    def test_no_markers_strict_passes(self):
        self.t.page("a.md", "plain\n")
        self.assertEqual(self.t.run("--strict")[0], 0)

    def test_ownership_file_mismatch_fails(self):
        self.t.page("a.md", GOOD + "\n")
        self.t.spec("board_child_tasks", "id: board_child_tasks\noutput: other.svg\n")
        rc, out = self.t.run()
        self.assertEqual(rc, 1)
        self.assertIn("OWNERSHIP: file 'aitasks_board_child_tasks.svg' differs", out)

    def test_ownership_shared_output_fails(self):
        self.t.spec("a", "id: a\noutput: x.svg\n")
        self.t.spec("b", "id: b\noutput: x.svg\n")
        rc, out = self.t.run()
        self.assertEqual(rc, 1)
        self.assertIn("shared by scenes a, b", out)

    def test_two_spellings_of_one_file_cannot_both_pass(self):
        # `x.svg` and `./x.svg` name the same file; the second spelling is
        # rejected, so the pair can never slip past the shared-output check.
        self.t.image("imgs/x.svg")
        self.t.spec("a", "id: a\noutput: x.svg\n")
        self.t.spec("b", 'id: b\noutput: "./x.svg"\n')
        rc, out = self.t.run()
        self.assertEqual(rc, 1)
        self.assertIn("scenes/b.yaml: OWNERSHIP: output './x.svg' must be a canonical path", out)
        rc, out = self.t.run("--owners")
        self.assertEqual(out.splitlines(), ["x.svg\ta"])

    def test_owners_never_labels_an_owned_image_hand_made(self):
        self.t.image("imgs/x.svg")
        self.t.spec("a", 'id: a\noutput: "./x.svg"\n')
        rc, out = self.t.run()
        self.assertEqual(rc, 1)  # the spec fails the check rather than passing silently
        self.assertIn("canonical path", out)

    def test_ownership_id_stem_mismatch_and_missing_output_fail(self):
        self.t.spec("a", "id: b\noutput: x.svg\n")
        rc, out = self.t.run()
        self.assertEqual(rc, 1)
        self.assertIn("differs from the file stem", out)
        self.t.spec("a", "id: a\n")
        rc, out = self.t.run()
        self.assertEqual(rc, 1)
        self.assertIn("output: missing", out)

    def test_ownership_unsupported_scalar_is_named(self):
        self.t.spec("a", "id: a\noutput: a.svg#x\n")
        rc, out = self.t.run()
        self.assertEqual(rc, 1)
        self.assertIn("not a supported single-line scalar", out)
        self.assertNotIn("output: missing", out)

    def test_missing_image_sources_fail(self):
        for body in (
            '{{< static-img src="imgs/nope.svg" alt="A" >}}\n',
            '{{< split-hero\n    title="t"\n    image="imgs/nope.svg"\n>}}{{< /split-hero >}}\n',
            '{{< tour-tile href="/x/" src="imgs/home/nope.svg" alt="A" caption="B" >}}\n',
        ):
            with self.subTest(body=body):
                self.t.page("a.md", body)
                rc, out = self.t.run()
                self.assertEqual(rc, 1)
                self.assertIn("MISSING_IMAGE", out)

    def test_present_image_sources_pass(self):
        self.t.image("imgs/yes.svg")
        self.t.image("imgs/home/yes.svg")
        self.t.page("a.md",
                    '{{< static-img src="imgs/yes.svg" alt="A" >}}\n'
                    '{{< split-hero\n    image="imgs/home/yes.svg"\n>}}{{< /split-hero >}}\n'
                    '{{< tour-tile href="/x/" src="imgs/home/yes.svg" alt="A" >}}\n'
                    '{{</* static-img src="imgs/escaped.svg" */>}}\n')
        rc, out = self.t.run()
        self.assertEqual(rc, 0, out)

    def test_image_source_quoting_follows_hugo(self):
        # Each form was probed against Hugo 0.169; Hugo renders all of them
        # with src=imgs/yes.svg (tests/test_check_screenshots_hugo.py repeats
        # the probe with the real template).
        self.t.image("imgs/yes.svg")
        for call in (
            '{{< static-img alt="Closing >}} text" src="imgs/yes.svg" >}}',
            '{{< static-img src=imgs/yes.svg alt=x >}}',
            '{{< static-img src=`imgs/yes.svg` alt=`raw "q" x` >}}',
            '{{< static-img alt="esc \\" q" src="imgs/yes.svg" >}}',
            '{{< static-img src = "imgs/yes.svg" >}}',
            '{{< static-img alt="b"src="imgs/yes.svg" >}}',
            '{{% static-img src="imgs/yes.svg" alt="pct %}} inside" %}}',
            '{{< static-img\n   alt="m"\n   src="imgs/yes.svg" >}}',
        ):
            with self.subTest(call=call):
                self.t.page("a.md", call + "\n")
                srcs = [s for _, _, _, s in mk.scan_image_sources(self.t.content)]
                self.assertEqual(srcs, ["imgs/yes.svg"])
                rc, out = self.t.run()
                self.assertEqual(rc, 0, out)

    def test_quoted_close_does_not_hide_a_missing_image(self):
        self.t.page("a.md", '{{< static-img alt="x >}} y" src="imgs/nope.svg" >}}\n'
                            '{{< static-img src=imgs/nope2.svg >}}\n')
        rc, out = self.t.run()
        self.assertEqual(rc, 1)
        self.assertIn("src='imgs/nope.svg'", out)
        self.assertIn("src='imgs/nope2.svg'", out)
        self.assertNotIn("has no src=", out)

    def test_image_source_is_checked_as_the_requested_path(self):
        # A file literally named `a#b.svg` exists, but the browser requests
        # `imgs/a` for that src: the check must fail.
        self.t.image("imgs/a#b.svg")
        self.t.image("imgs/a?b.svg")
        for src in ("imgs/a#b.svg", "imgs/a?b.svg"):
            with self.subTest(src=src):
                self.t.page("a.md", f'{{{{< static-img src="{src}" alt="A" >}}}}\n')
                rc, out = self.t.run()
                self.assertEqual(rc, 1)
                self.assertIn("requests 'imgs/a'", out)

    def test_query_fragment_and_encoding_resolve_like_a_browser(self):
        self.t.image("imgs/x.svg")
        self.t.image("imgs/a b.svg")
        for src in ("imgs/x.svg?v=2", "imgs/x.svg#top", "/imgs/x.svg", "imgs/a%20b.svg"):
            with self.subTest(src=src):
                self.t.page("a.md", f'{{{{< static-img src="{src}" alt="A" >}}}}\n')
                rc, out = self.t.run()
                self.assertEqual(rc, 0, out)

    def test_other_shortcodes_are_skipped_whole(self):
        # A non-image shortcode whose quoted value holds an image call's text
        # must not be read as that call.
        self.t.page("a.md", '{{< note text="{{< static-img src=imgs/nope.svg >}}" >}}\n')
        self.assertEqual(mk.scan_image_sources(self.t.content), [])

    def test_owners_maps_image_to_scene_with_no_markers(self):
        self.t.image("imgs/aitasks_board_child_tasks.svg")
        self.t.image("imgs/home/board.svg")
        self.t.spec("board_child_tasks", PARENT_SPEC)
        rc, out = self.t.run("--owners")
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), [
            "aitasks_board_child_tasks.svg\tboard_child_tasks",
            "home/board.svg\thand-made",
        ])


if __name__ == "__main__":
    unittest.main()
