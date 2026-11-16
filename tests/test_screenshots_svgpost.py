"""Tests for crop and overlays on docs screenshots (t2278_3).

`website/screenshots/svgpost.py` crops a Rich terminal SVG to a cell rectangle
and draws boxes, tints, numbered callouts and labels on top;
`website/screenshots/session.py` finds rectangles on a screen. No tmux is
needed: the SVGs come from `svg_export.ansi_to_svg` on canned captures, and
the screens are canned rows.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_svgpost.py -v
"""
import contextlib
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))

from screenshots import recipe as recipes  # noqa: E402
from screenshots import session as sessions  # noqa: E402
from screenshots import svg_export as sx  # noqa: E402
from screenshots import svgpost as sp  # noqa: E402

ROWS = [
    "  hello",
    " ┌────┐",
    " │ ab │ x",
    " └────┘",
]
SIZE = (12, 4)
RENDERERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
             "rsvg-convert")


def export(rows=ROWS, size=SIZE, scene="scene_a"):
    return sx.ansi_to_svg("\n".join(rows), size[0], size[1], title="aitasks <board>",
                          scene_id=scene)


def overlays(items, size=SIZE, crop=None):
    return recipes.validate_overlays(items, size, crop)


def attrs(svg, cls):
    """The attributes of every element of class ``cls``, as dicts of strings."""
    out = []
    for tag in re.findall(rf'<[a-z]+ class="{cls}"([^>]*?)/?>', svg):
        out.append(dict(re.findall(r'([A-Za-z0-9-]+)="([^"]*)"', tag)))
    return out


def vb(svg):
    return tuple(float(v) for v in re.search(
        r'viewBox="(-?[0-9.]+) (-?[0-9.]+) ([0-9.]+) ([0-9.]+)"', svg).groups())


BOX = {"type": "box", "target": {"cells": [1, 1, 6, 3]}, "callout": 1}
LABEL = {"type": "anchor", "target": {"cells": [2, 2, 5, 1]}, "label": "A <b> & c"}


class GeometryTests(unittest.TestCase):
    def test_cell_rect_to_px(self):
        self.assertEqual(sp.cell_rect_to_px((0, 0, 1, 1)), (9, 42.5, 12.2, 24.4))
        self.assertEqual(sp.cell_rect_to_px((2, 6, 38, 6)), (33.4, 188.9, 463.6, 146.4))

    def test_numbers_are_written_with_at_most_two_decimals(self):
        self.assertEqual(sp.num(72.19999999999999), "72.2")
        self.assertEqual(sp.num(-0.0), "0")
        self.assertEqual(sp.num(12.0), "12")


class CropTests(unittest.TestCase):
    def test_exact_viewbox_without_and_with_gutter(self):
        # (1,1,6,3) -> x 21.2, y 66.9, w 73.2, h 73.2; padded by 8.
        self.assertEqual(vb(sp.crop(export(), (1, 1, 6, 3))), (13.2, 58.9, 89.2, 89.2))
        self.assertEqual(vb(sp.crop(export(), (1, 1, 6, 3), gutter=5)),
                         (13.2, 58.9, 150.2, 89.2))

    def test_chrome_is_gone_and_its_fill_is_the_background(self):
        out = sp.crop(export(), (1, 1, 6, 3))
        self.assertNotIn('stroke="rgba(255,255,255,0.35)"', out)
        self.assertNotRegex(out, r'<text class="[^"]*-title"')
        self.assertNotIn("<circle", out)
        self.assertNotIn("translate(26,22)", out)
        background = attrs(out, "shot-crop-background")
        self.assertEqual(len(background), 1)
        self.assertEqual(background[0]["fill"], "#292929")
        self.assertEqual((background[0]["x"], background[0]["y"], background[0]["width"],
                          background[0]["height"]), ("13.2", "58.9", "89.2", "89.2"))

    def test_content_is_clipped_to_exactly_the_rectangle(self):
        out = sp.crop(export(scene="sc"), (1, 1, 6, 3), gutter=5)
        clip = re.search(r'<clipPath id="terminal-sc-clip-crop">\s*<rect x="([0-9.]+)" '
                         r'y="([0-9.]+)" width="([0-9.]+)" height="([0-9.]+)"', out)
        self.assertEqual(clip.groups(), ("21.2", "66.9", "73.2", "73.2"))
        # The wrapper encloses the whole content group.
        wrapper = out.index('<g clip-path="url(#terminal-sc-clip-crop)">')
        content = out.index('<g transform="translate(9, 41)"')
        self.assertGreater(wrapper, out.index("</defs>"))
        self.assertLess(wrapper, content)
        content_end = out.index("</g>", out.index("</g>", out.index(
            '<g class="terminal-sc-matrix">')) + 4) + 4
        self.assertEqual(out[content_end:].lstrip()[:4], "</g>")

    def test_text_survives_the_crop(self):
        self.assertIn("│ ab │", sx.svg_plain_text(sp.crop(export(), (1, 1, 6, 3))))

    def test_cropping_twice_raises(self):
        once = sp.crop(export(), (1, 1, 6, 3))
        with self.assertRaisesRegex(sp.SvgPostError, "chrome"):
            sp.crop(once, (1, 1, 6, 3))

    def test_missing_structure_raises(self):
        svg = export()
        no_dots = re.sub(r'<g transform="translate\(26,22\)">.*?</g>', "", svg, flags=re.S)
        with self.assertRaisesRegex(sp.SvgPostError, "buttons"):
            sp.crop(no_dots, (1, 1, 6, 3))
        start = svg.index('<g transform="translate(9, 41)"')
        doubled = svg[:start] + svg[start:svg.index("</svg>")] + svg[start:]
        with self.assertRaisesRegex(sp.SvgPostError, "content group"):
            sp.crop(doubled, (1, 1, 6, 3))
        other = '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        for fn in (lambda s: sp.crop(s, (0, 0, 1, 1)), lambda s: sp.overlay(s, overlays([BOX]))):
            with self.assertRaises(sp.SvgPostError):
                fn(other)


class OverlayTests(unittest.TestCase):
    def test_box_callout_and_label_coordinates(self):
        out = sp.overlay(export(), overlays([BOX, LABEL]))
        box = attrs(out, "shot-box")[0]
        # Rect (21.2, 66.9, 73.2, 73.2) inset by 2.
        self.assertEqual((box["x"], box["y"], box["width"], box["height"]),
                         ("23.2", "68.9", "69.2", "69.2"))
        self.assertEqual((box["fill"], box["stroke"]), ("none", sp.ACCENT))
        circle = attrs(out, "shot-callout")[0]
        # Left of the rect: 21.2 - 4 - 17 - 1.5; vertical middle 66.9 + 36.6.
        self.assertEqual((circle["cx"], circle["cy"], circle["r"]), ("-1.3", "103.5", "17"))
        self.assertIn('class="shot-callout-number" x="-1.3"', out)
        self.assertRegex(out, r'class="shot-callout-number"[^>]*>1</text>')
        leader = attrs(out, "shot-leader")[0]
        # Rect (33.4, 91.3, 61, 24.4): leader from its right edge, 24 long.
        self.assertEqual((leader["x1"], leader["x2"], leader["y1"], leader["y2"]),
                         ("94.4", "118.4", "103.5", "103.5"))
        label = attrs(out, "shot-label")[0]
        self.assertEqual(label["x"], "124.4")
        # Drawn at exactly the width the extent assumes: 9 cells * 9.76.
        self.assertEqual((label["textLength"], label["lengthAdjust"]),
                         ("87.84", "spacingAndGlyphs"))
        self.assertIn(">A &lt;b&gt; &amp; c</text>", out)

    def test_tint(self):
        out = sp.overlay(export(), overlays([{"type": "tint", "target": {"cells": [1, 1, 6, 3]}}]))
        tint = attrs(out, "shot-tint")[0]
        self.assertEqual((tint["x"], tint["fill"], tint["fill-opacity"]),
                         ("23.2", sp.ACCENT, str(sp.TINT_OPACITY)))
        self.assertNotIn("shot-callout", out)

    def test_overlay_is_after_the_content_group_and_outside_its_clip(self):
        svg = export(scene="sc")
        out = sp.overlay(svg, overlays([BOX]))
        start = out.index('<g transform="translate(9, 41)"')
        group = out.index('<g class="shot-overlay">')
        matrix_end = out.index("</g>", out.index('<g class="terminal-sc-matrix">'))
        content_end = out.index("</g>", matrix_end + 4)
        self.assertLess(start, content_end)
        self.assertGreater(group, content_end)
        # Nothing but whitespace between the content group's end and the overlay.
        self.assertEqual(out[content_end + 4:group].strip(), "")
        # The original SVG is untouched apart from the inserted group.
        self.assertEqual(out[:content_end + 4], svg[:content_end + 4])

    def test_a_second_overlay_pass_raises(self):
        once = sp.overlay(export(), overlays([BOX]))
        with self.assertRaisesRegex(sp.SvgPostError, "already"):
            sp.overlay(once, overlays([BOX]))

    def test_overlay_then_crop_keeps_overlay_coordinates(self):
        items = overlays([BOX, LABEL])
        plain = sp.overlay(export(), items)
        both = sp.postprocess(export(), {"cells": [1, 1, 6, 3]}, items)
        group = re.compile(r'<g class="shot-overlay">.*?</g>', re.S)
        self.assertEqual(group.search(plain).group(0), group.search(both).group(0))
        # The overlay is not inside the crop clip wrapper: between the end of
        # the content group and the overlay there is exactly the wrapper's </g>.
        content_end = both.index("</g>", both.index("</g>", both.index(
            '<g class="terminal-scene_a-matrix">')) + 4) + 4
        between = both[content_end:both.index('<g class="shot-overlay">')]
        self.assertEqual(between.split(), ["</g>"])


class ExtentTests(unittest.TestCase):
    def test_a_callout_at_an_interior_crop_corner_is_inside_the_viewbox(self):
        rows = ["0123456789abcdef"] * 8
        size = (16, 8)
        crop = recipes.validate_crop({"cells": [4, 3, 6, 2]}, size)
        items = overlays([{"type": "box", "target": {"cells": [4, 3, 3, 1]}, "callout": 7}],
                         size, crop)
        out = sp.postprocess(export(rows, size), crop, items)
        x, y, w, h = vb(out)
        circle = attrs(out, "shot-callout")[0]
        cx, cy, r = float(circle["cx"]), float(circle["cy"]), float(circle["r"])
        reach = r + sp.STROKE_W / 2
        self.assertGreaterEqual(cx - reach, x)
        self.assertGreaterEqual(cy - reach, y)
        self.assertLessEqual(cx + reach, x + w)
        self.assertLessEqual(cy + reach, y + h)
        # The clip stays the rectangle itself: the extent widens only the view.
        clip = re.search(r'-clip-crop">\s*<rect x="([0-9.]+)"', out).group(1)
        self.assertEqual(float(clip), sp.cell_rect_to_px((4, 3, 6, 2))[0])
        # Control: without the overlay the view is just the padded rectangle,
        # and that would have cut the circle.
        bare = vb(sp.postprocess(export(rows, size), crop, None))
        self.assertGreater(bare[0], cx - reach)

    def test_a_label_longer_than_the_gutter_widens_the_view(self):
        rows = ["0123456789abcdef"] * 8
        size = (16, 8)
        crop = recipes.validate_crop({"cells": [4, 3, 6, 2], "gutter": 1}, size)
        label = "a much longer label than one cell"
        items = overlays([{"type": "anchor", "target": {"cells": [4, 3, 6, 1]},
                           "label": label}], size, crop)
        x, _, w, _ = vb(sp.postprocess(export(rows, size), crop, items))
        rx, _, rw, _ = sp.cell_rect_to_px((4, 3, 6, 1))
        label_end = rx + rw + sp.LEADER_PX + sp.LABEL_GAP + sp.label_width(label)
        self.assertGreaterEqual(x + w, label_end)
        bare = vb(sp.postprocess(export(rows, size), crop, None))
        self.assertLess(bare[0] + bare[2], label_end)

    def test_an_uncropped_image_grows_to_take_in_its_callouts(self):
        svg = export()
        out = sp.postprocess(svg, None, overlays([{**BOX, "target": {"cells": [0, 0, 12, 1]}}]))
        self.assertLess(vb(out)[0], 0)
        self.assertEqual(vb(out)[0] + vb(out)[2], vb(svg)[2])
        self.assertEqual(sp.postprocess(svg, None, ()), svg)


BROWSERS = RENDERERS[:-1]


def rendered_label_bounds(svg):
    """``(viewBox, [(x0, x1) per label])`` as headless Chromium lays the SVG out
    (``getBBox`` of each ``.shot-label``): the rendered extent, not the
    module's own arithmetic."""
    import json
    import subprocess

    browser = next(b for b in BROWSERS if shutil.which(b))
    script = ("<script>const v=document.querySelector('svg').viewBox.baseVal;"
              "document.body.setAttribute('data-out',JSON.stringify({vb:[v.x,v.y,v.width,"
              "v.height],labels:[...document.querySelectorAll('.shot-label')].map(t=>{"
              "const b=t.getBBox();return [b.x,b.x+b.width]})}));</script>")
    # The same short private TMPDIR as render_png: Chromium's url-fetcher dirs
    # land in it, and a long $TMPDIR cannot abort it on its socket path.
    tmp = sx._chrome_scratch_dir()
    try:
        page = Path(tmp) / "page.html"
        page.write_text(f"<!doctype html><html><body>{svg}{script}</body></html>",
                        encoding="utf-8")
        out = subprocess.run([browser, "--headless", "--disable-gpu", "--dump-dom",
                              f"--user-data-dir={tmp}/profile", page.as_uri()],
                             capture_output=True, text=True, timeout=90,
                             env={**os.environ, "TMPDIR": tmp}).stdout
    except BaseException as exc:
        leftover = sx._remove_scratch(tmp)
        if leftover is not None:
            exc.add_note(f"its scratch dir {tmp} could not be removed: {leftover}")
        raise
    # A leftover is the defect these dirs exist to prevent: fail, never accept.
    leftover = sx._remove_scratch(tmp)
    if leftover is not None:
        raise AssertionError(f"Chromium scratch dir {tmp} could not be removed: {leftover}")
    import html as html_mod

    data = json.loads(html_mod.unescape(re.search(r'data-out="([^"]*)"', out).group(1)))
    return data["vb"], data["labels"]


class RenderedBoundsTests(unittest.TestCase):
    @unittest.skipUnless(any(shutil.which(b) for b in BROWSERS), "no headless browser")
    def test_wide_labels_stay_inside_the_rendered_view(self):
        rows = ["0123456789abcdef"] * 8
        size = (16, 8)
        crop = recipes.validate_crop({"cells": [4, 3, 6, 2]}, size)
        # One label per image: a longer label in the same image would set the
        # view's width and hide another label's overflow.
        for label in ("標籤" * 8, "🚀" * 12, "Mark / Task number and title"):
            items = overlays([{"type": "anchor", "target": {"cells": [4, 3, 6, 1]},
                               "label": label}], size, crop)
            view, bounds = rendered_label_bounds(
                sp.postprocess(export(rows, size), crop, items))
            with self.subTest(label=label):
                self.assertEqual(len(bounds), 1)
                x0, x1 = bounds[0]
                self.assertGreaterEqual(x0, view[0])
                self.assertLessEqual(x1, view[0] + view[2])
                # The renderer draws it at the width the extent assumes.
                self.assertAlmostEqual(x1 - x0, sp.label_width(label), delta=1.0)

    def test_label_width_counts_rich_cells(self):
        self.assertEqual(sp.label_width("ab"), round(2 * sp.LABEL_CHAR_W, 2))
        self.assertEqual(sp.label_width("標籤"), round(4 * sp.LABEL_CHAR_W, 2))
        self.assertEqual(sp.label_width("👩‍💻"), round(2 * sp.LABEL_CHAR_W, 2))


class PreviewTests(unittest.TestCase):
    def test_viewbox_of_any_origin(self):
        self.assertEqual(sp.viewbox('<svg viewBox="13.2 58.9 150.2 89.2">'),
                         (13.2, 58.9, 150.2, 89.2))
        self.assertEqual(sp.viewbox('<svg viewBox="-40.3 0 1600 1124.4">'),
                         (-40.3, 0, 1600, 1124.4))

    @unittest.skipUnless(any(shutil.which(r) for r in RENDERERS), "no SVG renderer installed")
    def test_a_cropped_svg_renders_a_png_of_its_viewbox_size(self):
        out = sp.postprocess(export(), {"cells": [1, 1, 6, 3], "gutter": 5},
                             overlays([BOX, LABEL]))
        _, _, w, h = vb(out)
        with tempfile.TemporaryDirectory() as tmp:
            svg_path, png_path = Path(tmp) / "a.svg", Path(tmp) / "a.png"
            svg_path.write_text(out, encoding="utf-8")
            renderer = sx.render_png(svg_path, png_path)
            data = png_path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        if renderer != "rsvg-convert":
            self.assertEqual((width, height), (int(w + 0.999), int(h + 0.999)))
        else:
            self.assertGreater(width, 0)


def private_dir(test, parent="/tmp"):
    """A fresh dir removed when ``test`` ends. Under the short ``/tmp`` by
    default, so a test controls which side of Chromium's socket limit it is on
    whatever ``$TMPDIR`` the run has."""
    path = tempfile.mkdtemp(prefix="shots_", dir=parent)
    test.addCleanup(shutil.rmtree, path, True)
    return path


def long_dir(test):
    path = os.path.join(private_dir(test), "d" * 100)
    os.mkdir(path)
    return path


@contextlib.contextmanager
def temp_root(path):
    """``path`` as the temp dir for both Python (``tempfile``) and Chromium."""
    with mock.patch.dict(os.environ, {"TMPDIR": path}), \
            mock.patch.object(tempfile, "tempdir", path):
        yield


class ChromiumScratchTests(unittest.TestCase):
    """Chromium's temp files and its singleton socket (t2316)."""

    def cropped_svg(self):
        out = sp.postprocess(export(), {"cells": [1, 1, 6, 3], "gutter": 5},
                             overlays([BOX, LABEL]))
        work = Path(private_dir(self))
        (work / "a.svg").write_text(out, encoding="utf-8")
        return out, work / "a.svg", work / "a.png"

    def test_a_short_temp_dir_is_used_as_is(self):
        root = private_dir(self)
        with temp_root(root):
            scratch = sx._chrome_scratch_dir()
        self.addCleanup(shutil.rmtree, scratch, True)
        self.assertEqual(os.path.dirname(scratch), root)

    def test_a_long_temp_dir_falls_back_to_the_short_base(self):
        root, fallback = long_dir(self), private_dir(self)
        with temp_root(root), mock.patch.object(sx, "_SHORT_TMP_FALLBACK", fallback):
            scratch = sx._chrome_scratch_dir()
        self.addCleanup(shutil.rmtree, scratch, True)
        self.assertEqual(os.path.dirname(scratch), fallback)
        self.assertEqual(os.listdir(root), [])

    def test_a_non_ascii_temp_dir_is_measured_in_bytes(self):
        base, fallback = private_dir(self), private_dir(self)
        budget = sx._SUN_PATH_MAX - sx._SOCKET_TAIL
        # Longest run of "é" (2 bytes each) whose scratch path still fits in
        # CHARACTERS; it then overflows in bytes.
        tail = len("/ait_shots_chrome_") + 8          # mkdtemp's 8-char suffix
        n = budget - len(base) - 1 - tail
        root = os.path.join(base, "é" * n)
        os.mkdir(root)
        probe = os.path.join(root, "ait_shots_chrome_" + "x" * 8)
        self.assertLessEqual(len(probe), budget)               # fits as characters
        self.assertGreater(len(os.fsencode(probe)), budget)    # not as bytes
        with temp_root(root), mock.patch.object(sx, "_SHORT_TMP_FALLBACK", fallback):
            scratch = sx._chrome_scratch_dir()
        self.addCleanup(shutil.rmtree, scratch, True)
        self.assertEqual(os.path.dirname(scratch), fallback)
        self.assertEqual(os.listdir(root), [])

    def test_no_short_dir_raises_before_launching_chromium(self):
        _, svg_path, png_path = self.cropped_svg()
        root = long_dir(self)
        missing = os.path.join(private_dir(self), "missing")
        which = lambda name: "/usr/bin/chromium" if name == "chromium" else None  # noqa: E731
        with temp_root(root), mock.patch.object(sx, "_SHORT_TMP_FALLBACK", missing), \
                mock.patch.object(sx.shutil, "which", which), \
                mock.patch.object(sx.subprocess, "run") as run:
            with self.assertRaisesRegex(sx.ExportError, "too long for Chromium's socket"):
                sx.render_png(svg_path, png_path)
        run.assert_not_called()
        self.assertEqual(os.listdir(root), [])
        self.assertFalse(os.path.exists(missing))

    @contextlib.contextmanager
    def fake_chromium(self, root):
        """A ``chromium`` on PATH whose run writes the PNG, under temp dir
        ``root``; no real browser and no real waits."""
        def run(argv, **kwargs):
            png = next(a for a in argv if a.startswith("--screenshot="))
            Path(png.split("=", 1)[1]).write_bytes(b"\x89PNG\r\n\x1a\n")
        which = lambda name: "/usr/bin/chromium" if name == "chromium" else None  # noqa: E731
        with temp_root(root), mock.patch.object(sx.shutil, "which", which), \
                mock.patch.object(sx.subprocess, "run", side_effect=run) as fake_run, \
                mock.patch.object(sx.time, "sleep"):
            yield fake_run

    def flaky_rmtree(self, failures):
        """``shutil.rmtree`` that leaves the dir in place, as a late writer
        would, on its first ``failures`` calls."""
        real, calls = shutil.rmtree, []

        def rmtree(path, *args, **kwargs):
            calls.append(path)
            if len(calls) <= failures:
                raise OSError(39, "Directory not empty", path)
            return real(path, *args, **kwargs)
        return rmtree, calls

    def test_a_transient_cleanup_failure_is_retried(self):
        _, svg_path, png_path = self.cropped_svg()
        root = private_dir(self)
        rmtree, calls = self.flaky_rmtree(failures=2)
        with self.fake_chromium(root), mock.patch.object(sx.shutil, "rmtree", rmtree):
            self.assertEqual(sx.render_png(svg_path, png_path), "chromium")
        self.assertEqual(len(calls), 3)
        self.assertEqual(os.listdir(root), [])

    def test_a_scratch_dir_that_cannot_be_removed_is_an_error(self):
        _, svg_path, png_path = self.cropped_svg()
        root = private_dir(self)
        rmtree, calls = self.flaky_rmtree(failures=99)
        with self.fake_chromium(root), mock.patch.object(sx.shutil, "rmtree", rmtree):
            with self.assertRaisesRegex(sx.ExportError, "could not be removed"):
                sx.render_png(svg_path, png_path)
        self.assertEqual(len(calls), 1 + len(sx._CLEANUP_DELAYS))
        self.assertEqual(len(os.listdir(root)), 1)     # reported, not hidden

    def test_the_cli_shows_both_a_render_failure_and_a_leftover(self):
        from screenshots import cli

        out_svg, _, _ = self.cropped_svg()
        root = private_dir(self)
        # A staging path longer than the CLI's whole 300-character line: no
        # path length may push either failure out of what it prints.
        batch = Path(private_dir(self)) / ("staging_" + "b" * 200) / ("c" * 100)
        batch.mkdir(parents=True)
        image = batch / "scene_a.svg"
        self.assertGreater(len(str(image)), 300)
        image.write_text(out_svg, encoding="utf-8")
        rmtree, _ = self.flaky_rmtree(failures=99)
        fatal = ("[1:1:1116/153339.358377:FATAL:chrome/browser/process_singleton_posix.cc"
                 ":315] Socket path too long: /" + "p" * 150 + "/SingletonSocket")
        crash = subprocess.CalledProcessError(-6, ["chromium"], stderr=fatal.encode())
        with self.fake_chromium(root) as run, \
                mock.patch.object(sx.shutil, "rmtree", rmtree), \
                contextlib.redirect_stdout(io.StringIO()) as printed:
            run.side_effect = crash
            self.assertFalse(cli.preview_png(batch, "scene_a", image))
        line = printed.getvalue()
        self.assertIn("PNG_UNAVAILABLE:chromium could not render", line)
        self.assertIn("killed by SIGABRT", line)                  # the primary error
        self.assertIn("could not be removed either", line)        # and the leftover
        self.assertEqual(len(os.listdir(root)), 1)

    def test_the_bounds_helper_fails_on_a_leftover(self):
        root = private_dir(self)
        rmtree, _ = self.flaky_rmtree(failures=99)
        dom = subprocess.CompletedProcess(
            [], 0, stdout='<body data-out="{&quot;vb&quot;:[0,0,1,1],&quot;labels&quot;:[]}">')
        which = lambda name: "/usr/bin/chromium" if name == "chromium" else None  # noqa: E731
        with temp_root(root), mock.patch.object(sx.shutil, "which", which), \
                mock.patch.object(sx.subprocess, "run", return_value=dom), \
                mock.patch.object(sx.shutil, "rmtree", rmtree), \
                mock.patch.object(sx.time, "sleep"):
            with self.assertRaisesRegex(AssertionError, "could not be removed"):
                rendered_label_bounds(export())
        self.assertEqual(len(os.listdir(root)), 1)

    def test_a_profile_setup_failure_is_an_export_error(self):
        _, svg_path, png_path = self.cropped_svg()
        root = private_dir(self)
        real_mkdir = os.mkdir

        def mkdir(path, *args, **kwargs):
            if os.path.basename(path) == "profile":
                raise OSError(28, "No space left on device", path)
            return real_mkdir(path, *args, **kwargs)
        with self.fake_chromium(root) as run, mock.patch.object(sx.os, "mkdir", mkdir):
            with self.assertRaisesRegex(sx.ExportError, "Chromium profile"):
                sx.render_png(svg_path, png_path)
        run.assert_not_called()
        self.assertEqual(os.listdir(root), [])

    def test_a_scratch_dir_creation_failure_is_an_export_error(self):
        _, svg_path, png_path = self.cropped_svg()
        root = private_dir(self)
        with self.fake_chromium(root) as run, mock.patch.object(
                tempfile, "mkdtemp", side_effect=OSError(28, "No space left on device")):
            with self.assertRaisesRegex(sx.ExportError, "no scratch dir for Chromium"):
                sx.render_png(svg_path, png_path)
        run.assert_not_called()

    def test_a_too_long_fallback_raises_and_cleans_up(self):
        root, fallback = long_dir(self), long_dir(self)
        with temp_root(root), mock.patch.object(sx, "_SHORT_TMP_FALLBACK", fallback):
            with self.assertRaisesRegex(sx.ExportError, "no temp dir short enough"):
                sx._chrome_scratch_dir()
        self.assertEqual(os.listdir(root), [])
        self.assertEqual(os.listdir(fallback), [])

    @unittest.skipUnless(any(shutil.which(b) for b in BROWSERS), "no Chromium installed")
    def test_a_preview_leaves_nothing_in_the_temp_dir(self):
        _, svg_path, png_path = self.cropped_svg()
        root = private_dir(self)
        with temp_root(root):
            # Chromium leaks its url-fetcher dir on most runs, not all.
            for _ in range(3):
                self.assertNotEqual(sx.render_png(svg_path, png_path), "rsvg-convert")
                self.assertEqual(os.listdir(root), [])

    @unittest.skipUnless(any(shutil.which(b) for b in BROWSERS), "no Chromium installed")
    def test_a_long_temp_dir_still_renders(self):
        out, svg_path, png_path = self.cropped_svg()
        root, fallback = long_dir(self), private_dir(self)
        with temp_root(root), mock.patch.object(sx, "_SHORT_TMP_FALLBACK", fallback):
            sx.render_png(svg_path, png_path)
        data = png_path.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        _, _, w, h = vb(out)
        self.assertEqual(struct.unpack(">II", data[16:24]),
                         (int(w + 0.999), int(h + 0.999)))
        self.assertEqual(os.listdir(root), [])
        self.assertEqual(os.listdir(fallback), [])


class ScreenRectTests(unittest.TestCase):
    def test_box_around_a_text(self):
        self.assertEqual(sessions.box_around(ROWS, "ab"), (1, 1, 6, 3))

    def test_a_wide_glyph_before_the_box_counts_two_cells(self):
        rows = ["💪 ┌──┐", "💪 │ab│", "💪 └──┘"]
        self.assertEqual(sessions.box_around(rows, "ab"), (3, 0, 4, 3))
        # A ZWJ sequence is one two-cell grapheme, as Rich measures it.
        zwj = ["👩‍💻 ┌──┐", "👩‍💻 │ab│", "👩‍💻 └──┘"]
        self.assertEqual(sessions.box_around(zwj, "ab"), (3, 0, 4, 3))
        self.assertEqual(sessions.cell_grid("👩‍💻x"), ["👩‍💻", "", "x"])
        self.assertEqual(sessions.cell_grid("💪x")[:3], ["💪", "", "x"])
        self.assertEqual(sessions.cell_grid("🏷️x"), ["🏷️", "", "x"])
        # The grid and the finder measure the same way, cell for cell.
        line = "║ 💪 high | 🏷️ checkout ║"
        col, _ = sessions.find_in_rows([line], "checkout")[0]
        self.assertEqual("".join(sessions.cell_grid(line)[col:col + 8]), "checkout")

    def test_the_innermost_box_wins(self):
        rows = ["╭────────╮",
                "│╔════╗  │",
                "│║ ab ║  │",
                "│╚════╝  │",
                "╰────────╯"]
        self.assertEqual(sessions.box_around(rows, "ab"), (1, 1, 6, 3))

    def test_a_smaller_box_beside_the_text_is_skipped(self):
        rows = ["┌──────────┐",
                "│┌─┐       │",
                "││x│ ab    │",
                "│└─┘       │",
                "└──────────┘"]
        self.assertEqual(sessions.box_around(rows, "ab"), (0, 0, 12, 5))

    def test_the_text_must_occur_exactly_once(self):
        with self.assertRaisesRegex(sessions.SessionError, "0 times"):
            sessions.box_around(ROWS, "zz")
        with self.assertRaisesRegex(sessions.SessionError, "2 times"):
            sessions.box_around(ROWS + [" │ ab │"], "ab")

    def test_an_unclosed_box_raises(self):
        unclosed = {
            "no bottom corners": [" ┌────┐", " │ ab │", " │    │"],
            "no top-right corner": [" ┌────", " │ ab │", " └────┘"],
            "no left border": ["  ab"],
            "gap in the right edge": ["┌────┐", "│ ab  ", "└────┘"],
            "gap in the bottom edge": ["┌────┐", "│ ab │", "└    ┘"],
            "gap in the top edge": ["┌─  ─┐", "│ ab │", "└────┘"],
            "box too narrow for the text": ["┌─┐", "│ abc", "└─┘"],
        }
        for name, rows in unclosed.items():
            with self.subTest(case=name):
                with self.assertRaisesRegex(sessions.SessionError, "no closed box"):
                    sessions.box_around(rows, "ab" if name != "box too narrow for the text"
                                        else "abc")
        # Control: the same box, closed, is found.
        self.assertEqual(sessions.box_around(["┌────┐", "│ ab │", "└────┘"], "ab"),
                         (0, 0, 6, 3))

    def test_rect_holds(self):
        self.assertTrue(sessions.rect_holds(ROWS, (1, 1, 6, 3), "ab"))
        self.assertFalse(sessions.rect_holds(ROWS, (1, 1, 6, 3), "hello"))
        # Partly inside is not inside.
        self.assertFalse(sessions.rect_holds(ROWS, (1, 2, 4, 1), "ab │ x"))
        self.assertFalse(sessions.rect_holds(ROWS, (1, 2, 3, 1), "ab"))


if __name__ == "__main__":
    unittest.main()
