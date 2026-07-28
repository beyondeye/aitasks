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


def strip_ansi(s: str) -> str:
    return ANSI_CSI_RE.sub("", s)
