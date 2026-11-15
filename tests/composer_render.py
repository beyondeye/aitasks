"""Render a line of text into a measured agent composer capture (t2275).

The minimonitor's recheck delivery proves, before every Enter, that the shadow
composer holds EXACTLY the prompt (``review_loop.composer_payload`` +
``agent_submit.payload_matches``). A test fake that serves a fixed "typed"
capture therefore can no longer stand in for a composer: it has to show the
text that was actually typed, wrapped the way the real agent wraps it.

:func:`wrap_rows` is that wrap -- a greedy layout over the measured grammar
parameters of ``review_loop.ComposerPayload`` (``content_width``,
``wrap_width``, ``hyphen_breaks``). :func:`render` substitutes the rows into a
real capture from ``tests/shadow_recheck_fixtures.py``. Both are checked
against every genuine capture there (``test_agent_submit
.ComposerRenderTests``), so the fake renders what the agents were measured to
render -- including codex's and opencode's break after a hyphen (t2280).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / ".aitask-scripts"
for _p in (str(_HERE), str(_SCRIPTS), str(_SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Bound at import on purpose: this is fixture tooling, and a test that patches
# `review_loop.composer_payload` (to model a weaker gate) must not change what
# the fake renders.
from monitor.review_loop import composer_payload as _measured_payload  # noqa: E402
from monitor.ansi_utils import strip_ansi  # noqa: E402
from shadow_recheck_fixtures import FIXTURES  # noqa: E402

#: The capture each agent's rendering is built from, per width: a multi-row
#: genuine composer (so it carries both a first and a continuation row).
TEMPLATE = "{agent}_w{width}_recheck_plan"

#: Agents that fill the current row before hard-breaking an over-long token.
FILL_LONG = {"claude": True}


def _pieces(text: str, hyphen_breaks: bool):
    """``(piece, sep_before)``: words, split after each hyphen when the agent
    hyphen-breaks (the fragment after a hyphen joins with no separator)."""
    out = []
    for word in text.split(" "):
        frags = re.findall(r"[^-]*-|[^-]+", word) if hyphen_breaks else [word]
        for i, frag in enumerate(frags):
            out.append((frag, " " if i == 0 else ""))
    if out:
        out[0] = (out[0][0], "")
    return out


def wrap_rows(text: str, content_width: int, wrap_width: int,
              hyphen_breaks: bool = False, fill_long: bool = False) -> list:
    """The display rows a measured agent shows for ``text`` (single-spaced).

    A piece fits on the row iff ``row + sep + piece <= limit``, the limit being
    ``wrap_width`` for a piece followed by a space and ``content_width``
    otherwise (a hyphen-ended fragment, or the end of the text) -- the same
    limits ``agent_submit._moved_piece`` justifies a break with. A piece that
    does not fit starts the next row (a space separator is consumed); a piece
    longer than the content width is hard-broken at it. ``fill_long``: such a
    piece first fills the current row (measured: claude; codex and opencode
    start it on a new row -- the ``midtoken`` captures).
    """
    pieces = _pieces(text, hyphen_breaks)
    rows, row = [], ""
    for idx, (piece, sep) in enumerate(pieces):
        nxt = pieces[idx + 1][1] if idx + 1 < len(pieces) else None
        limit = wrap_width if nxt == " " else content_width
        if row and len(row) + len(sep) + len(piece) <= limit:
            row += sep + piece
            continue
        if row and fill_long and len(piece) > content_width:
            room = content_width - len(row) - len(sep)
            if room > 0:
                row, piece = row + sep + piece[:room], piece[room:]
        if row:
            rows.append(row)
            row = ""
        while len(piece) > content_width:
            rows.append(piece[:content_width])
            piece = piece[content_width:]
        row = piece
    if row:
        rows.append(row)
    return rows


def _locate(raw_lines: list, rows: tuple) -> int:
    """Index of the raw line holding ``rows[0]``, searched from the bottom."""
    plain = [strip_ansi(ln).rstrip() for ln in raw_lines]
    for i in range(len(plain) - len(rows), -1, -1):
        if all(plain[i + k].endswith(rows[k]) for k in range(len(rows))):
            return i
    raise ValueError("composer rows not found in the template")


_PAD_RE = re.compile(r"^( *)(\x1b\[[0-9;]*m)( *)(.*)$", re.S)


def _row_line(model: str, old: str, new: str) -> str:
    i = model.rindex(old)
    prefix, suffix = model[:i], model[i + len(old):]
    m = _PAD_RE.match(suffix)
    if suffix and m:                    # a padded box row (opencode): keep the width
        pad = len(m.group(1)) + len(m.group(3)) + len(old) - len(new)
        suffix = m.group(2) + " " * pad + m.group(4)
    return prefix + new + suffix


def render(agent: str, width: int, text: str) -> str:
    """A ``capture-pane`` tail of ``agent``'s composer holding ``text`` at ``width``."""
    _a, w, _state, _req, raw = FIXTURES[TEMPLATE.format(agent=agent, width=width)]
    payload = _measured_payload(raw, agent, w)
    lines = raw.split("\n")
    at = _locate(lines, payload.lines)
    rows = wrap_rows(text, payload.content_width, payload.wrap_width,
                     payload.hyphen_breaks, fill_long=FILL_LONG.get(agent, False))
    first, cont = lines[at], lines[at + 1]
    new = [_row_line(first, payload.lines[0], rows[0])]
    new += [_row_line(cont, payload.lines[1], r) for r in rows[1:]]
    return "\n".join(lines[:at] + new + lines[at + len(payload.lines):])
