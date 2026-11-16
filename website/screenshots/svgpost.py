"""Crop and annotate a Rich terminal SVG, on cell rectangles (t2278_3).

Everything here is a pure function on SVG text. A rectangle is
``(column, row, width, height)`` in terminal cells of the captured pane,
border cells included; the agent finds it on the live screen (``find
--box``, ``screen``).

Geometry of a Rich 15 export (``rich.console.Console.export_svg``, fixed): a
cell is ``CHAR_W`` x ``LINE_H`` SVG units; the content group is translated to
``ORIGIN``; a row's background starts ``ROW_OFFSET`` below its line. So the
cell ``(c, r)`` covers ``x = 9 + c*12.2`` and ``y = 41 + 1.5 + r*24.4``.

Overlays are drawn in that full-image coordinate space, in one
``<g class="shot-overlay">`` placed after the content group (on top of it,
outside its clip path). A crop then only changes what is visible, so the
order is fixed: overlay first, then crop (:func:`postprocess`).

The structure is found by the fixed shape of Rich's template
(``rich/_export_format.py``). Anything unexpected raises
:class:`SvgPostError`; a half-processed file is never returned.
"""
from __future__ import annotations

import html
import re

CHAR_W = 12.2
LINE_H = 24.4
ORIGIN = (9, 41)
ROW_OFFSET = 1.5

#: Space kept around a cropped rectangle, in SVG units.
CROP_PAD = 8
#: A box is drawn this far inside its rectangle, so two adjacent zones keep
#: two distinct outlines.
BOX_INSET = 2
ACCENT = "#ffc24b"
INK = "#1e1e1e"
STROKE_W = 3
TINT_OPACITY = 0.18
CALLOUT_R = 17
#: Space between a callout and the left edge of its rectangle.
CALLOUT_GAP = 4
CALLOUT_FONT_PX = 22
LABEL_FONT_PX = 16
#: Width of one label CELL: the label font is Fira Code, whose advance is
#: 0.61 of its size (the same aspect Rich uses for the terminal text). A label
#: is drawn with ``textLength`` = its Rich cell width times this, so the
#: renderer fits it to exactly the width the extent assumes, whatever glyphs
#: (CJK, emoji) it holds.
LABEL_CHAR_W = LABEL_FONT_PX * 0.61
LEADER_PX = 24
LABEL_GAP = 6
LEADER_W = 2
FONT_FAMILY = "Fira Code, monospace"

TYPES = ("box", "tint", "anchor")


class SvgPostError(Exception):
    """The SVG does not have the structure this module works on."""


def num(value: float) -> str:
    """Every number this module writes: at most two decimals, no trailing zeros."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def cell_rect_to_px(rect) -> tuple[float, float, float, float]:
    """``(c, r, w, h)`` cells -> ``(x, y, w, h)`` SVG units of the full image."""
    c, r, w, h = rect
    return (round(ORIGIN[0] + c * CHAR_W, 2), round(ORIGIN[1] + ROW_OFFSET + r * LINE_H, 2),
            round(w * CHAR_W, 2), round(h * LINE_H, 2))


# --- structure ---------------------------------------------------------------

_VIEWBOX = re.compile(r'viewBox="(-?[0-9.]+) (-?[0-9.]+) ([0-9.]+) ([0-9.]+)"')
_CHROME = re.compile(r'<rect fill="(#[0-9a-fA-F]{6})" stroke="rgba\(255,255,255,0\.35\)" '
                     r'stroke-width="1" x="1" y="1" width="[0-9.]+" height="[0-9.]+" rx="8"/>')
_TITLE = re.compile(r'<text class="[^"]*-title"[^>]*>.*?</text>', re.S)
_DOTS = re.compile(r'\s*<g transform="translate\(26,22\)">\s*'
                   r'(?:<circle [^>]*/>\s*){3}</g>')
_CONTENT = re.compile(r'<g transform="translate\(9, 41\)" '
                      r'clip-path="url\(#([A-Za-z0-9_-]+)-clip-terminal\)">')


def _one(pattern: re.Pattern, svg: str, what: str) -> re.Match:
    found = list(pattern.finditer(svg))
    if len(found) != 1:
        raise SvgPostError(f"expected exactly one {what} in the SVG, found {len(found)}")
    return found[0]


def _content_group(svg: str) -> tuple[int, int, str]:
    """``(start, end, unique_id)`` of the content group, ``end`` past its ``</g>``.

    The group holds the background rects and exactly one matrix group of
    ``<text>`` elements; no other group may be nested in it.
    """
    opening = _one(_CONTENT, svg, "content group")
    uid = opening.group(1)
    matrix = f'<g class="{uid}-matrix">'
    at = svg.find(matrix, opening.end())
    if at == -1 or "<g" in svg[opening.end():at]:
        raise SvgPostError("the content group does not hold exactly the matrix group")
    close_matrix = svg.find("</g>", at)
    close_content = svg.find("</g>", close_matrix + 4) if close_matrix != -1 else -1
    if close_content == -1 or "<g" in svg[at + len(matrix):close_content]:
        raise SvgPostError("the content group is not closed as Rich writes it")
    return opening.start(), close_content + len("</g>"), uid


def viewbox(svg: str) -> tuple[float, float, float, float]:
    match = _one(_VIEWBOX, svg, "viewBox")
    return tuple(float(v) for v in match.groups())  # type: ignore[return-value]


# --- overlays ------------------------------------------------------------------


def _item_rect(item: dict) -> tuple[float, float, float, float]:
    return cell_rect_to_px(item["target"]["cells"])


def _callout_centre(item: dict) -> tuple[float, float]:
    """Just outside the rectangle's left edge, at its vertical middle: a
    callout never covers what it numbers. The image grows to take it in
    (:func:`postprocess`)."""
    x, y, _, h = _item_rect(item)
    return round(x - CALLOUT_GAP - CALLOUT_R - STROKE_W / 2, 2), round(y + h / 2, 2)


def label_width(label: str) -> float:
    """The width a label is drawn at (its ``textLength``), in SVG units."""
    from rich.cells import cell_len

    return round(cell_len(label) * LABEL_CHAR_W, 2)


def _leader(item: dict) -> tuple[float, float, float]:
    """``(x_start, x_end, y)`` of a label's leader line."""
    x, y, w, h = _item_rect(item)
    return round(x + w, 2), round(x + w + LEADER_PX, 2), round(y + h / 2, 2)


def _parts(item: dict) -> list[tuple[str, tuple[float, float, float, float]]]:
    """What one overlay item draws, as ``(kind, bounding box)``; the single
    source of geometry for both :func:`overlay` and :func:`overlay_extent`."""
    parts = []
    x, y, w, h = _item_rect(item)
    if item["type"] in ("box", "tint"):
        rect = (x + BOX_INSET, y + BOX_INSET, w - 2 * BOX_INSET, h - 2 * BOX_INSET)
        half = STROKE_W / 2 if item["type"] == "box" else 0
        parts.append((item["type"], (rect[0] - half, rect[1] - half,
                                     rect[0] + rect[2] + half, rect[1] + rect[3] + half)))
    if item.get("callout") is not None:
        cx, cy = _callout_centre(item)
        reach = CALLOUT_R + STROKE_W / 2
        parts.append(("callout", (cx - reach, cy - reach, cx + reach, cy + reach)))
    if item.get("label"):
        x0, x1, ly = _leader(item)
        parts.append(("leader", (x0, ly - LEADER_W / 2, x1, ly + LEADER_W / 2)))
        tx = x1 + LABEL_GAP
        parts.append(("label", (tx, ly - LABEL_FONT_PX / 2,
                                tx + label_width(item["label"]), ly + LABEL_FONT_PX / 2)))
    return parts


def overlay_extent(items):
    """``(x0, y0, x1, y1)`` covering everything :func:`overlay` draws, or None."""
    boxes = [box for item in items for _, box in _parts(item)]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _draw(item: dict) -> list[str]:
    out = []
    x, y, w, h = _item_rect(item)
    if item["type"] == "box":
        out.append(f'<rect class="shot-box" x="{num(x + BOX_INSET)}" y="{num(y + BOX_INSET)}" '
                   f'width="{num(w - 2 * BOX_INSET)}" height="{num(h - 2 * BOX_INSET)}" '
                   f'fill="none" stroke="{ACCENT}" stroke-width="{STROKE_W}" rx="3"/>')
    elif item["type"] == "tint":
        out.append(f'<rect class="shot-tint" x="{num(x + BOX_INSET)}" y="{num(y + BOX_INSET)}" '
                   f'width="{num(w - 2 * BOX_INSET)}" height="{num(h - 2 * BOX_INSET)}" '
                   f'fill="{ACCENT}" fill-opacity="{TINT_OPACITY}"/>')
    if item.get("label"):
        x0, x1, ly = _leader(item)
        out.append(f'<line class="shot-leader" x1="{num(x0)}" y1="{num(ly)}" x2="{num(x1)}" '
                   f'y2="{num(ly)}" stroke="{ACCENT}" stroke-width="{LEADER_W}"/>')
        out.append(f'<text class="shot-label" x="{num(x1 + LABEL_GAP)}" '
                   f'y="{num(ly + LABEL_FONT_PX * 0.35)}" fill="{ACCENT}" '
                   f'font-family="{FONT_FAMILY}" font-size="{LABEL_FONT_PX}" font-weight="bold" '
                   f'textLength="{num(label_width(item["label"]))}" '
                   f'lengthAdjust="spacingAndGlyphs">'
                   f'{html.escape(item["label"], quote=False)}</text>')
    if item.get("callout") is not None:
        cx, cy = _callout_centre(item)
        out.append(f'<circle class="shot-callout" cx="{num(cx)}" cy="{num(cy)}" '
                   f'r="{CALLOUT_R}" fill="{ACCENT}" stroke="{INK}" '
                   f'stroke-width="{STROKE_W}"/>')
        out.append(f'<text class="shot-callout-number" x="{num(cx)}" '
                   f'y="{num(cy + CALLOUT_FONT_PX * 0.35)}" fill="{INK}" text-anchor="middle" '
                   f'font-family="{FONT_FAMILY}" font-size="{CALLOUT_FONT_PX}" '
                   f'font-weight="bold">{int(item["callout"])}</text>')
    return out


def overlay(svg: str, items) -> str:
    """Draw ``items`` (validated recipe overlays) on top of the terminal."""
    items = list(items)
    if not items:
        return svg
    if 'class="shot-overlay"' in svg:
        raise SvgPostError("the SVG already carries an overlay group")
    for item in items:
        if item.get("type") not in TYPES:
            raise SvgPostError(f"unknown overlay type {item.get('type')!r}")
    viewbox(svg)
    _, end, _ = _content_group(svg)
    body = "\n    ".join(part for item in items for part in _draw(item))
    group = f'\n    <g class="shot-overlay">\n    {body}\n    </g>'
    return svg[:end] + group + svg[end:]


# --- crop ----------------------------------------------------------------------


def crop(svg: str, rect, gutter: int = 0, extent=None) -> str:
    """Show only ``rect`` (cells) without the window chrome.

    The terminal content is clipped to exactly the rectangle, so nothing
    beside it shows. The ``viewBox`` adds :data:`CROP_PAD` of plain
    background around it, ``gutter`` empty cells on the right (room for
    labels), and grows further to take in ``extent`` (the overlay's bounding
    box), so an annotation is never cut off. The chrome rect is also the
    default background, so it is replaced by a plain background over the
    whole view.
    """
    chrome = _one(_CHROME, svg, "window frame (chrome rect)")
    _one(_DOTS, svg, "window buttons group")
    titles = list(_TITLE.finditer(svg))
    if len(titles) > 1:
        raise SvgPostError(f"expected at most one title in the SVG, found {len(titles)}")
    start, end, uid = _content_group(svg)
    viewbox(svg)
    defs_end = svg.find("</defs>")
    if defs_end == -1:
        raise SvgPostError("the SVG has no <defs>")

    clip = cell_rect_to_px(rect)
    x0, y0 = clip[0] - CROP_PAD, clip[1] - CROP_PAD
    x1 = clip[0] + clip[2] + CROP_PAD + gutter * CHAR_W
    y1 = clip[1] + clip[3] + CROP_PAD
    if extent is not None:
        x0, y0 = min(x0, extent[0] - CROP_PAD), min(y0, extent[1] - CROP_PAD)
        x1, y1 = max(x1, extent[2] + CROP_PAD), max(y1, extent[3] + CROP_PAD)
    view = (round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2))

    background = (f'<rect class="shot-crop-background" fill="{chrome.group(1)}" '
                  f'x="{num(view[0])}" y="{num(view[1])}" width="{num(view[2])}" '
                  f'height="{num(view[3])}"/>')
    clip_def = (f'<clipPath id="{uid}-clip-crop">\n      <rect x="{num(clip[0])}" '
                f'y="{num(clip[1])}" width="{num(clip[2])}" height="{num(clip[3])}" />\n'
                f'    </clipPath>\n    ')

    # Edit from the end of the file backwards, so earlier offsets stay valid.
    out = svg[:end] + "\n    </g>" + svg[end:]
    out = out[:start] + f'<g clip-path="url(#{uid}-clip-crop)">\n    ' + out[start:]
    head, tail = out[:start], out[start:]
    head = _DOTS.sub("", head, count=1)
    head = _TITLE.sub("", head, count=1)
    head = _CHROME.sub(background, head, count=1)
    head = head.replace("</defs>", clip_def + "</defs>", 1)
    head = _VIEWBOX.sub('viewBox="{} {} {} {}"'.format(*map(num, view)), head, count=1)
    return head + tail


def grow(svg: str, extent) -> str:
    """Widen an uncropped image's ``viewBox`` so ``extent`` (plus
    :data:`CROP_PAD`) is inside it. The added margin is left transparent:
    callouts then sit beside the window, on the page."""
    x, y, w, h = viewbox(svg)
    x0, y0 = min(x, extent[0] - CROP_PAD), min(y, extent[1] - CROP_PAD)
    x1, y1 = max(x + w, extent[2] + CROP_PAD), max(y + h, extent[3] + CROP_PAD)
    if (x0, y0, x1, y1) == (x, y, x + w, y + h):
        return svg
    view = (round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2))
    return _VIEWBOX.sub('viewBox="{} {} {} {}"'.format(*map(num, view)), svg, count=1)


def postprocess(svg: str, crop_spec=None, overlays=()) -> str:
    """The one entry point: overlays first, then the crop (if any).

    ``crop_spec`` and ``overlays`` are validated recipe values
    (``recipe.validate_crop`` / ``recipe.validate_overlays``). Either way the
    final ``viewBox`` contains everything the overlays draw.
    """
    overlays = list(overlays or ())
    out = overlay(svg, overlays)
    extent = overlay_extent(overlays)
    if crop_spec:
        return crop(out, crop_spec["cells"], crop_spec.get("gutter", 0), extent)
    return grow(out, extent) if extent else out
