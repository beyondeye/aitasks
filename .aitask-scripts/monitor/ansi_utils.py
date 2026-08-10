"""ANSI escape stripping — the single implementation, shared by the tmux core
and the pure concern grammar.

Kept in its own dependency-free module (`re` only) so `concern_parser` — which
documents itself as pure: no tmux, no Textual, no I/O — can normalise an
ANSI-bearing capture without importing `monitor_core` and its asyncio /
subprocess / gateway import graph (t1216_1).
"""
from __future__ import annotations

import re

ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

# OSC sequence: ESC ] <body> ST, where ST is BEL (\x07) or ESC \ .
#
# `tmux capture-pane -p -e` re-emits OSC 8 hyperlinks verbatim —
# ESC]8;;<url>ESC\ <text> ESC]8;;ESC\ — so a CSI-only strip left the URL sitting
# in the "stripped" text, polluting `compare_value` and every match built on it,
# prompt detection included (t1474).
#
# The body is BOUNDED (`[^\x07\x1b]*`) rather than a non-greedy `.*?`, and the
# terminator is REQUIRED. An OSC body can never legitimately contain BEL or ESC,
# so this can only ever consume one real sequence: a truncated / unterminated
# OSC is left intact instead of reaching forward to some later terminator and
# deleting the visible text in between. That direction is the dangerous one —
# the text most likely to sit there is the prompt footer, and eating it turns a
# pane that is blocked on the user back into a silently "idle" one.
#
# `applink/content.py::_OSC_SEQ` uses the `.*?` form deliberately: it *parses*
# the body into hyperlink spans and needs to capture it. This one only strips,
# so it takes the fail-safe bound.
ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def strip_ansi(s: str) -> str:
    """Remove OSC and CSI escape sequences, preserving the visible text."""
    return ANSI_CSI_RE.sub("", ANSI_OSC_RE.sub("", s))
