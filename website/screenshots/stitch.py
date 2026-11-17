"""A tmux window of several panes as ONE grid of cells, drawn as tmux draws it.

``capture-pane`` captures one pane and never the borders between panes. This
module puts each pane's capture at its ``(left, top)`` in a grid of the window's
size and draws the one-cell borders between them, so a window exports through
``svg_export.rows_to_svg`` like a single pane.

The border rules are tmux's (``screen-redraw.c``) for ONE configuration, the one
``session.BORDER_OPTIONS`` pins on every screenshot server:

* a border cell is a cell no pane covers; its glyph comes from which of its four
  neighbours are border cells, a neighbour outside the window counting as one
  (``screen_redraw_type_of_cell``);
* a border cell on the active pane's border ring is drawn in
  ``pane-active-border-style`` (``fg=green``), every other one in
  ``pane-border-style`` (``default``). With ``pane-border-indicators off`` tmux
  never half-colours a border, which it does by default in a window of exactly
  two panes.

:func:`stitch` refuses any other configuration rather than mis-draw it. The
rules are checked against a real tmux client's render in the live tests, not
only against themselves.

Pure: no tmux here. ``cli.py`` reads the geometry and the captures.
"""
from __future__ import annotations

from dataclasses import dataclass

from rich.ansi import AnsiDecoder
from rich.style import Style
from rich.text import Text

#: The options :func:`stitch` draws by (see ``session.BORDER_OPTIONS``).
REQUIRED_OPTIONS = {
    "pane-border-indicators": "off",
    "pane-border-lines": "single",
    "pane-border-status": "off",
    "pane-border-style": "default",
    "pane-active-border-style": "fg=green",
}

BORDER_STYLE = Style()
ACTIVE_BORDER_STYLE = Style(color="green")

# Neighbour bits as tmux numbers them: left 8, right 4, up 2, down 1.
_GLYPHS = {
    15: "┼", 14: "┴", 13: "┬", 12: "─", 11: "┤", 10: "┘", 9: "┐",
    7: "├", 6: "└", 5: "┌", 3: "│",
}


class StitchError(Exception):
    """The panes do not make one window, or the configuration is not the one
    the border rules are written for."""


@dataclass(frozen=True)
class Pane:
    left: int
    top: int
    width: int
    height: int
    active: bool
    ansi: str          # ``capture-pane -e -p -N`` output of this pane


def check_options(options: dict[str, str]) -> None:
    wrong = {k: options.get(k, "") for k, v in REQUIRED_OPTIONS.items()
             if options.get(k, "") != v}
    if wrong:
        shown = ", ".join(f"{k}={v!r}" for k, v in sorted(wrong.items()))
        raise StitchError(f"tmux border options differ from the pinned ones ({shown}); "
                          "the stitched borders would not be what tmux draws")


def on_border_ring(pane: Pane, x: int, y: int) -> bool:
    """Whether cell ``(x, y)`` lies on ``pane``'s border (tmux's
    ``screen_redraw_pane_border`` with pane status off)."""
    ex, ey = pane.left + pane.width, pane.top + pane.height
    if (pane.top == 0 or y >= pane.top - 1) and y <= ey:
        if pane.left != 0 and x == pane.left - 1:
            return True
        if x == ex:
            return True
    if (pane.left == 0 or x >= pane.left - 1) and x <= ex:
        if pane.top != 0 and y == pane.top - 1:
            return True
        if y == ey:
            return True
    return False


def _decode(pane: Pane, index: int) -> list[Text]:
    # One decoder PER PANE: tmux carries SGR state from line to line within a
    # pane's capture, never from one pane into another.
    rows = list(AnsiDecoder().decode(pane.ansi))[:pane.height]
    for number, row in enumerate(rows):
        if row.cell_len > pane.width:
            raise StitchError(f"pane {index} row {number} is {row.cell_len} cells wide, "
                              f"the pane is {pane.width}: a capture error")
    return rows + [Text("") for _ in range(pane.height - len(rows))]


def _cover(width: int, height: int, panes: list[Pane]) -> list[list[int]]:
    """Which pane covers each cell (-1 = none)."""
    owner = [[-1] * width for _ in range(height)]
    for index, pane in enumerate(panes):
        if pane.width < 1 or pane.height < 1 or pane.left < 0 or pane.top < 0 \
                or pane.left + pane.width > width or pane.top + pane.height > height:
            raise StitchError(f"pane {index} ({pane.left},{pane.top} "
                              f"{pane.width}x{pane.height}) lies outside the "
                              f"{width}x{height} window")
        for y in range(pane.top, pane.top + pane.height):
            row = owner[y]
            for x in range(pane.left, pane.left + pane.width):
                if row[x] != -1:
                    raise StitchError(f"panes {row[x]} and {index} overlap at {x},{y}")
                row[x] = index
    return owner


def border_cells(width: int, height: int, panes: list[Pane]
                 ) -> dict[tuple[int, int], tuple[str, bool]]:
    """``{(x, y): (glyph, active)}`` for every border cell of the window."""
    owner = _cover(width, height, panes)

    def border(x: int, y: int) -> bool:
        # Outside the window counts as border, as in tmux.
        if x < 0 or y < 0 or x >= width or y >= height:
            return True
        return owner[y][x] == -1

    active = [p for p in panes if p.active]
    out = {}
    for y in range(height):
        for x in range(width):
            if owner[y][x] != -1:
                continue
            bits = ((8 if border(x - 1, y) else 0) | (4 if border(x + 1, y) else 0)
                    | (2 if border(x, y - 1) else 0) | (1 if border(x, y + 1) else 0))
            glyph = _GLYPHS.get(bits, " ")
            out[(x, y)] = (glyph, any(on_border_ring(p, x, y) for p in active))
    return out


def stitch(width: int, height: int, panes: list[Pane],
           options: dict[str, str] | None = None) -> list[Text]:
    """The window as ``height`` rows of ``width`` cells.

    ``options`` are the server's border options (``session.window_options``);
    anything but :data:`REQUIRED_OPTIONS` raises :class:`StitchError`.
    """
    if options is not None:
        check_options(options)
    if not panes:
        raise StitchError("a window has at least one pane")
    decoded = [_decode(pane, index) for index, pane in enumerate(panes)]
    borders = border_cells(width, height, panes)
    starts = {}
    for index, pane in enumerate(panes):
        for y in range(pane.top, pane.top + pane.height):
            starts[(pane.left, y)] = index
    rows = []
    for y in range(height):
        row = Text(no_wrap=True, overflow="crop", end="")
        x = 0
        while x < width:
            if (x, y) in starts:
                index = starts[(x, y)]
                pane = panes[index]
                line = decoded[index][y - pane.top].copy()
                # Pad the pane's row to its width, so the next cell lands at
                # the right column (and a background reaches the pane's edge).
                line.pad_right(pane.width - line.cell_len)
                row.append_text(line)
                x += pane.width
                continue
            glyph, active = borders.get((x, y), (" ", False))
            row.append(glyph, ACTIVE_BORDER_STYLE if active else BORDER_STYLE)
            x += 1
        rows.append(row)
    return rows


def plain_rows(rows: list[Text]) -> list[str]:
    return [row.plain.rstrip() for row in rows]
