"""A captured tmux pane (text with SGR escapes) as a Rich terminal SVG.

The result has the same chrome as the site's existing screenshots: Rich's
default export theme and window frame.

Two rules found on the first real capture (t2278_2):

* tmux carries SGR state from one line to the next (``capture-pane -e`` only
  emits *changes*), so the whole capture goes through ONE decoder. Decoding
  row by row loses every background that was set on an earlier line.
* The capture must be taken with ``-N`` (``session.capture``), or trailing
  cells are dropped and the right part of a row loses its background.
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
from pathlib import Path

from rich.ansi import AnsiDecoder
from rich.console import Console
from rich.terminal_theme import SVG_EXPORT_THEME
from rich.text import Text

from .svgpost import SvgPostError, viewbox

_ID_RE = re.compile(r"^[a-z0-9_]+$")


class ExportError(Exception):
    pass


def ansi_to_svg(ansi: str, width: int, height: int, *, title: str, scene_id: str) -> str:
    """``ansi`` is a whole ``capture-pane -e -p -N`` output of a ``width`` x
    ``height`` pane."""
    if not _ID_RE.match(scene_id):
        raise ExportError(f"scene id {scene_id!r} must match [a-z0-9_]+")
    rows = list(AnsiDecoder().decode(ansi))[:height]
    rows += [Text("") for _ in range(height - len(rows))]
    console = Console(width=width, height=height, file=io.StringIO(), force_terminal=True,
                      color_system="truecolor", record=True, legacy_windows=False,
                      safe_box=False)
    for index, row in enumerate(rows):
        if row.cell_len > width:
            raise ExportError(
                f"row {index} is {row.cell_len} cells wide, the pane is {width}")
        console.print(row, end="" if index == height - 1 else "\n", soft_wrap=False,
                      no_wrap=True, overflow="crop", highlight=False)
    return console.export_svg(title=title, theme=SVG_EXPORT_THEME,
                              unique_id=f"terminal-{scene_id}")


def ansi_plain_text(ansi: str) -> str:
    """The text of a captured frame, without its escapes (one line per row)."""
    return "\n".join(row.plain.rstrip() for row in AnsiDecoder().decode(ansi))


def svg_plain_text(svg: str) -> str:
    """The text content of an exported SVG, for checks (no-break spaces as spaces)."""
    import html

    from rich.cells import cell_len

    # Rich writes one <text> per styled run, placed by x and clipped to its
    # line. Rebuild each row by column, so a text reads as it does on screen
    # even where its style changes ("t12" bold orange, then the title).
    run = re.compile(r'<text class="[^"]*" x="([0-9.]+)" y="[0-9.]+" textLength="[0-9.]+" '
                     r'clip-path="url\(#[^)]*-line-(\d+)\)">(.*?)</text>', re.S)
    rows: dict[int, list[tuple[float, str]]] = {}
    for x, line, content in run.findall(svg):
        rows.setdefault(int(line), []).append(
            (float(x), html.unescape(content).replace("\xa0", " ")))
    out = []
    for line in range(max(rows, default=-1) + 1):
        text = ""
        for x, content in sorted(rows.get(line, [])):
            column = round(x / CHAR_WIDTH)
            text += " " * max(0, column - cell_len(text)) + content
        out.append(text.rstrip())
    title = re.search(r'<text class="[^"]*-title"[^>]*>(.*?)</text>', svg, re.S)
    head = [html.unescape(title.group(1)).replace("\xa0", " ")] if title else []
    return "\n".join(head + out)


#: Width of one terminal cell in a Rich SVG export, in SVG units (fixed by
#: ``rich.console.Console.export_svg``: 20px font, 0.61 aspect ratio).
CHAR_WIDTH = 12.2


_BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


def render_png(svg_path: Path, png_path: Path, *, timeout: float = 90.0) -> str:
    """Render a PNG *preview* of the SVG and return the renderer's name.

    A headless Chromium shows what a site visitor sees. ``rsvg-convert`` is the
    fallback and is NOT faithful (it drops leading no-break spaces and has no
    emoji font); the caller says so. Raises :class:`ExportError` when neither
    is available or the render fails. The SVG stays the deliverable.
    """
    svg_path, png_path = Path(svg_path).resolve(), Path(png_path).resolve()
    try:
        # Any origin: a cropped SVG's viewBox does not start at 0 0.
        _x, _y, width, height = viewbox(svg_path.read_text(encoding="utf-8"))
    except SvgPostError as exc:
        raise ExportError(f"no usable viewBox in {svg_path}: {exc}") from exc
    width, height = int(width + 0.999), int(height + 0.999)
    browser = next((b for b in _BROWSERS if shutil.which(b)), None)
    if browser:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="ait_shots_chrome_") as profile:
            argv = [browser, "--headless", "--disable-gpu", "--hide-scrollbars",
                    f"--user-data-dir={profile}", f"--window-size={width},{height}",
                    f"--screenshot={png_path}", svg_path.as_uri()]
            try:
                subprocess.run(argv, capture_output=True, timeout=timeout, check=True)
            except (OSError, subprocess.SubprocessError) as exc:
                raise ExportError(f"{browser} could not render {svg_path}: {exc}") from exc
        if png_path.is_file():
            return browser
        raise ExportError(f"{browser} wrote no PNG for {svg_path}")
    if shutil.which("rsvg-convert"):
        try:
            subprocess.run(["rsvg-convert", "-o", str(png_path), str(svg_path)],
                           capture_output=True, timeout=timeout, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExportError(f"rsvg-convert could not render {svg_path}: {exc}") from exc
        return "rsvg-convert"
    raise ExportError("no PNG renderer found (chromium or rsvg-convert)")
