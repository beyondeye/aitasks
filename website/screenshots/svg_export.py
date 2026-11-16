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
import os
import re
import shutil
import signal
import subprocess
import time
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

#: Chromium binds ``$TMPDIR/org.chromium.Chromium.XXXXXX/SingletonSocket`` and
#: aborts at startup when that path does not fit a Unix socket address:
#: ``sun_path`` holds 108 bytes, the terminating NUL included (t2316).
_SOCKET_TAIL = len("/org.chromium.Chromium.XXXXXX/SingletonSocket")
_SUN_PATH_MAX = 107
#: Short base used when the caller's temp dir is too long for that socket.
_SHORT_TMP_FALLBACK = "/tmp"


def _socket_fits(scratch: str) -> bool:
    # sun_path is a BYTE limit: measure the encoded path, not its characters.
    return len(os.fsencode(scratch)) + _SOCKET_TAIL <= _SUN_PATH_MAX


def _chrome_scratch_dir() -> str:
    """A fresh private dir for one Chromium run, short enough for its socket.

    Made under ``tempfile.gettempdir()`` when the resulting socket path fits,
    else under ``_SHORT_TMP_FALLBACK``. Raises :class:`ExportError`, leaving
    nothing behind, when neither fits: Chromium would only abort on it. The
    caller removes the returned dir.
    """
    import tempfile

    try:
        # Measure the created path itself, so no suffix length is assumed.
        scratch = tempfile.mkdtemp(prefix="ait_shots_chrome_")
        if _socket_fits(scratch):
            return scratch
        os.rmdir(scratch)
    except OSError as exc:
        raise ExportError(f"no scratch dir for Chromium could be made in "
                          f"{tempfile.gettempdir()}: {exc}") from exc
    try:
        short = tempfile.mkdtemp(prefix="ait_shots_chrome_", dir=_SHORT_TMP_FALLBACK)
    except OSError as exc:
        raise ExportError(
            f"temp dir {scratch!r} is too long for Chromium's socket and no "
            f"scratch dir could be made in {_SHORT_TMP_FALLBACK}: {exc}") from exc
    if not _socket_fits(short):
        os.rmdir(short)
        raise ExportError("no temp dir short enough for Chromium's socket "
                          f"(tried {scratch!r} and {short!r})")
    return short


#: Waits between attempts to remove a scratch dir: a Chromium helper process
#: can outlive the browser and still be writing in it.
_CLEANUP_DELAYS = (0.05, 0.1, 0.2, 0.4, 0.8)


def _remove_scratch(scratch: str) -> OSError | None:
    """Remove a Chromium scratch dir, retrying while something may still be
    writing in it. Returns the last error when the dir is still there."""
    error: OSError | None = None
    for delay in (0, *_CLEANUP_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            shutil.rmtree(scratch)
        except FileNotFoundError:
            pass                    # an entry vanished mid-walk; check below
        except OSError as exc:
            error = exc
        if not os.path.lexists(scratch):
            return None
    return error or OSError(f"{scratch} still exists")


def _last_line(stderr: bytes | str | None) -> str:
    """The last non-empty line of a process's stderr, as an error-message tail."""
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    lines = [line.strip() for line in (stderr or "").splitlines()]
    lines = [line for line in lines if line]
    return f" — {lines[-1]}" if lines else ""


def _exit_reason(returncode: int) -> str:
    """How a process ended, briefly (its full argv is not worth a line)."""
    if returncode < 0:
        try:
            return f"killed by {signal.Signals(-returncode).name}"
        except ValueError:
            return f"killed by signal {-returncode}"
    return f"exit status {returncode}"


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
        scratch = _chrome_scratch_dir()
        # A failed run as (summary, detail, stderr tail, cause), reported after
        # cleanup. Callers print one line truncated to a few hundred characters,
        # so the message is ordered by importance and only its summaries are
        # guaranteed to survive: summaries carry NO paths (their length is
        # bounded), every path goes in the details after them.
        failure: tuple[str, str, str, BaseException] | None = None
        try:
            profile = os.path.join(scratch, "profile")
            try:
                os.mkdir(profile)
            except OSError as exc:
                failure = ("could not set up a Chromium profile",
                           f"{profile}: {exc.strerror or exc}", "", exc)
            else:
                # Chromium puts its own temp files (url-fetcher dirs, the
                # singleton socket) in $TMPDIR, outside the profile. Point it at
                # the scratch dir: they are removed with it, and the socket path
                # stays short.
                env = {**os.environ, "TMPDIR": scratch}
                argv = [browser, "--headless", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={profile}", f"--window-size={width},{height}",
                        f"--screenshot={png_path}", svg_path.as_uri()]
                head = f"{browser} could not render the SVG"
                try:
                    subprocess.run(argv, capture_output=True, timeout=timeout, check=True,
                                   env=env)
                except subprocess.CalledProcessError as exc:
                    failure = (f"{head}: {_exit_reason(exc.returncode)}", str(svg_path),
                               _last_line(exc.stderr), exc)
                except subprocess.TimeoutExpired as exc:
                    failure = (f"{head}: timed out after {timeout:g}s", str(svg_path),
                               _last_line(exc.stderr), exc)
                except OSError as exc:
                    failure = (f"{browser} could not be started: {exc.strerror or 'error'}",
                               str(exc), "", exc)
                except subprocess.SubprocessError as exc:
                    failure = (head, f"{svg_path}: {exc}", "", exc)
        except BaseException as exc:
            # Interrupted: the interrupt is the error; a leftover rides along.
            leftover = _remove_scratch(scratch)
            if leftover is not None:
                exc.add_note(f"its scratch dir {scratch} could not be removed: {leftover}")
            raise
        leftover = _remove_scratch(scratch)
        left = "" if leftover is None else \
            f"; scratch dir {scratch}: {leftover.strerror or leftover}"
        if failure:
            summary, detail, tail, cause = failure
            also = "" if leftover is None else \
                "; its scratch dir could not be removed either"
            raise ExportError(f"{summary}{also} ({detail}{left}){tail}") from cause
        if leftover is not None:
            raise ExportError(f"{browser} ran, but its scratch dir could not be removed "
                              f"({left[2:]})")
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
