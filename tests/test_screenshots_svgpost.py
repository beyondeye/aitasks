"""Tests for crop and overlays on docs screenshots (t2278_3).

`website/screenshots/svgpost.py` crops a Rich terminal SVG to a cell rectangle
and draws boxes, tints, numbered callouts and labels on top;
`website/screenshots/session.py` finds rectangles on a screen. No tmux is
needed: the SVGs come from `svg_export.ansi_to_svg` on canned captures, and
the screens are canned rows.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_screenshots_svgpost.py -v
"""
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

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
    with tempfile.TemporaryDirectory(prefix="ait_shots_bbox_") as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(f"<!doctype html><html><body>{svg}{script}</body></html>",
                        encoding="utf-8")
        out = subprocess.run([browser, "--headless", "--disable-gpu", "--dump-dom",
                              f"--user-data-dir={tmp}/profile", page.as_uri()],
                             capture_output=True, text=True, timeout=90).stdout
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
