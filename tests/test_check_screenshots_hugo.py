"""Real-Hugo rendering check for screenshot-marker values (t2278_1).

`markers.render_static_img` writes marker values verbatim into a double-quoted
Hugo shortcode parameter, and the `static-img` template places `alt` inside a
single-quoted JavaScript string in `onclick`. This module builds a minimal
scratch Hugo site with the real `website/layouts/shortcodes/static-img.html`
and checks that every kind of value the grammar accepts survives that trip:
the build succeeds and the built `alt`, `<figcaption>` and `onclick` decode back
to the original text.

The control proves the fixture can see a breakage, and records why `\\` is in
`markers.FORBIDDEN_IN_VALUE`: a value ending in a backslash, written raw into
the shortcode, does not render as itself.

Skips when `hugo` is not on PATH. No Docsy or npm is needed.

Run: python3 -m pytest tests/test_check_screenshots_hugo.py -v
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

import check_screenshots as cs  # noqa: E402
from screenshots import markers as mk  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "website" / "layouts" / "shortcodes" / "static-img.html"
HUGO = shutil.which("hugo")

#: Values the grammar accepts that stress the shortcode lexer, the HTML
#: attribute escaping or the JS string in onclick.
ACCEPTED_CORPUS = [
    "One trail's waves",
    "Fish & chips",
    "a < b > c",
    "closing }} braces",
    "shortcode close >}} inside",
    "hash # sign",
    "Em dash — and ünïcödé",
    "Ends with a full stop.",
    "-",
]

CONFIG = """\
baseURL = "http://example.org/"
disableKinds = ["taxonomy", "term", "RSS", "sitemap", "robotsTXT", "404", "home", "section"]
[markup.goldmark.renderer]
  unsafe = true
"""


class _Figures(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.figs = []
        self._in_cap = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "figure" and "static-img-zoom" in (a.get("class") or ""):
            self.figs.append({"onclick": a.get("onclick"), "alt": None, "caption": ""})
        elif tag == "img" and self.figs and self.figs[-1]["alt"] is None and a.get("id") is None:
            self.figs[-1]["alt"] = a.get("alt")
        elif tag == "figcaption":
            self._in_cap = True

    def handle_endtag(self, tag):
        if tag == "figcaption":
            self._in_cap = False

    def handle_data(self, data):
        if self._in_cap and self.figs:
            self.figs[-1]["caption"] += data


_JS_STR = re.compile(r"'((?:[^'\\]|\\.)*)'")


def _js_unescape(s):
    def rep(m):
        e = m.group(1)
        if e[0] == "x":
            return chr(int(e[1:], 16))
        if e[0] == "u":
            return chr(int(e[1:], 16))
        return {"n": "\n", "t": "\t", "r": "\r"}.get(e, e)
    return re.sub(r"\\(x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|.)", rep, s)


def _onclick_alt(onclick):
    strings = _JS_STR.findall(onclick or "")
    return _js_unescape(strings[1]) if len(strings) == 2 else None


@unittest.skipUnless(HUGO, "hugo not on PATH")
class HugoRenderTests(unittest.TestCase):
    def build(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        site = Path(tmp.name)
        (site / "hugo.toml").write_text(CONFIG, encoding="utf-8")
        (site / "layouts" / "_default").mkdir(parents=True)
        (site / "layouts" / "_default" / "single.html").write_text("{{ .Content }}\n", encoding="utf-8")
        (site / "layouts" / "shortcodes").mkdir(parents=True)
        shutil.copy(TEMPLATE, site / "layouts" / "shortcodes" / "static-img.html")
        (site / "content").mkdir()
        (site / "content" / "p.md").write_text('---\ntitle: "p"\n---\n\n' + body, encoding="utf-8")
        proc = subprocess.run([HUGO, "--quiet", "--destination", str(site / "public")],
                              cwd=site, capture_output=True, text=True, timeout=120)
        html = None
        out = site / "public" / "p" / "index.html"
        if proc.returncode == 0 and out.is_file():
            html = out.read_text(encoding="utf-8")
        return proc, html

    def test_accepted_corpus_round_trips(self):
        rendered = []
        for value in ACCEPTED_CORPUS:
            line = f'<!-- screenshot: scene=s file=x.svg alt="{value}" caption="{value}" -->'
            marker = mk.parse_marker(line)
            self.assertIsInstance(marker, mk.Marker, value)
            rendered.append(mk.render_static_img(marker))
        proc, html = self.build("\n\n".join(rendered) + "\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        p = _Figures()
        p.feed(html)
        self.assertEqual(len(p.figs), len(ACCEPTED_CORPUS))
        for value, fig in zip(ACCEPTED_CORPUS, p.figs):
            with self.subTest(value=value):
                self.assertEqual(fig["alt"], value)
                self.assertEqual(fig["caption"], value)
                self.assertEqual(_onclick_alt(fig["onclick"]), value, fig["onclick"])

    def _scan_page(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        content = Path(tmp.name)
        (content / "p.md").write_text(body, encoding="utf-8")
        return content

    def test_shortcode_argument_forms_match_hugo(self):
        """Differential: the checker's image-source scan reads every argument
        form the same way Hugo's shortcode lexer does."""
        calls = [
            '{{< static-img alt="Closing >}} text" src="imgs/f0.svg" >}}',
            '{{< static-img src=imgs/f1.svg alt=x >}}',
            '{{< static-img src=`imgs/f2.svg` alt=`raw "q" x` >}}',
            '{{< static-img alt="esc \\" q" src="imgs/f3.svg" >}}',
            '{{< static-img src = "imgs/f4.svg" >}}',
            '{{< static-img alt="b"src="imgs/f5.svg" >}}',
            '{{< static-img\n   alt="m"\n   src="imgs/f6.svg" >}}',
        ]
        body = "\n\n".join(calls) + "\n"
        proc, html = self.build(body)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        hugo_srcs = re.findall(r'<img src="/(imgs/f\d\.svg)"', html)
        scanned = [s for _, _, _, s in mk.scan_image_sources(self._scan_page(body))]
        self.assertEqual(hugo_srcs, [f"imgs/f{i}.svg" for i in range(len(calls))])
        self.assertEqual(scanned, hugo_srcs)

    def test_fence_rules_match_goldmark(self):
        """Differential: a marker the scanner finds is exactly a marker
        Goldmark keeps as a raw HTML comment (not code)."""
        def mark(scene):
            return f'<!-- screenshot: scene={scene} file={scene}.svg alt="A" -->'
        body = "\n".join([
            "```bad`info", "", mark("after_bad_fence"), "",
            "```ok", mark("in_backtick_fence"), "```", "",
            "~~~ ok`info", mark("in_tilde_fence"), "~~~", "",
            "````", "```", mark("in_long_fence"), "````", "",
            mark("plain"), "",
        ])
        proc, html = self.build(body)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        kept = sorted(re.findall(r"<!-- screenshot: scene=(\w+)", html))
        markers, bad = mk.scan(self._scan_page(body))
        self.assertEqual(bad, [])
        self.assertEqual(sorted(m.scene for m in markers), kept)
        self.assertEqual(kept, ["after_bad_fence", "plain"])

    def test_marker_file_is_the_requested_path(self):
        """Marker -> rendered shortcode -> Hugo -> browser request path: every
        accepted filename shape is requested as exactly `imgs/<file>`, so the
        file the checker validates is the file the page loads."""
        files = ["x.svg", "home/board.svg", "a.b-c_D9.svg", "deep/er/path.png"]
        rendered = []
        for f in files:
            m = mk.parse_marker(f'<!-- screenshot: scene=s file={f} alt="A" -->')
            self.assertIsInstance(m, mk.Marker, f)
            rendered.append(mk.render_static_img(m))
        proc, html = self.build("\n\n".join(rendered) + "\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        srcs = re.findall(r'<img src="([^"]*)" alt="A">', html)
        requested = [unquote(urlsplit(s).path).lstrip("/") for s in srcs]
        self.assertEqual(requested, [f"imgs/{f}" for f in files])
        self.assertEqual([cs.request_path(s) for s in srcs], requested)
        for f in ("a#b.svg", "a?b.svg", "a b.svg", "a%20b.svg"):
            with self.subTest(rejected=f):
                self.assertIsInstance(
                    mk.parse_marker(f'<!-- screenshot: scene=s file="{f}" alt="A" -->'), str)

    def test_delimiter_filename_would_request_another_file(self):
        """Control: rendered raw, `a#b.svg` is requested as `imgs/a` -- why
        `path_problem` rejects URL delimiters."""
        proc, html = self.build('{{< static-img src="imgs/a#b.svg" alt="A" >}}\n'
                                '{{< static-img src="imgs/a?b.svg" alt="A" >}}\n')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        srcs = re.findall(r'<img src="([^"]*)" alt="A">', html)
        self.assertEqual([cs.request_path(s) for s in srcs], ["imgs/a", "imgs/a"])

    def test_trailing_backslash_breaks_the_shortcode(self):
        value = "ends in\\"
        self.assertIsInstance(
            mk.parse_marker(f'<!-- screenshot: scene=s file=x.svg alt="{value}" -->'), str)
        raw = '{{< static-img src="imgs/x.svg" alt="' + value + '" >}}\n'
        proc, html = self.build(raw)
        if proc.returncode != 0 or html is None:
            return  # the build failed: the breakage is visible
        p = _Figures()
        p.feed(html)
        alts = [f["alt"] for f in p.figs]
        self.assertNotEqual(alts, [value], "a trailing backslash rendered intact; "
                            "revisit FORBIDDEN_IN_VALUE")


if __name__ == "__main__":
    unittest.main()
