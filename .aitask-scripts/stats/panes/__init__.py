"""Pane registry for the stats TUI.

Importing this package imports each category module, whose `register()`
calls at import time populate `PANE_DEFS`. Consumers do:

    from stats.panes import PANE_DEFS
"""
from .base import PANE_DEFS, PaneDef  # noqa: F401 — re-export
from . import overview, labels, agents, velocity  # noqa: F401 — side-effect imports

__all__ = ["PANE_DEFS", "PaneDef"]
