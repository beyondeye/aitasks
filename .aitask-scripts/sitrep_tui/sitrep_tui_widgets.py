"""sitrep_tui_widgets.py - widgets shared by the sitrep TUI's screens (t2211_10).

Kept apart from ``sitrep_tui_app`` so the dialog modules (``sitrep_tui_actions``,
``sitrep_tui_trails``), which the app imports, can use them without a circular
import. ``sitrep_tui_app`` re-exports ``SelectOnClickList`` under its old name.
"""

from __future__ import annotations

from textual import events
from textual.widgets import OptionList


class SelectOnClickList(OptionList):
    """An OptionList where a mouse click only SELECTS (highlights) a row.

    Opening is Enter's job -- the footer-visible "Details" / "Open" binding,
    which fires the list's own ``action_select`` -- so ``OptionSelected``
    stays the one open path and a stray click never opens anything.
    ``OptionList._on_click`` highlights AND selects; ``prevent_default`` stops
    Textual's MRO walk before it runs (t2211_8)."""

    async def _on_click(self, event: events.Click) -> None:
        event.prevent_default()
        idx = event.style.meta.get("option")
        if idx is None or not 0 <= idx < self.option_count:
            return
        if not self.get_option_at_index(idx).disabled:
            self.highlighted = idx
