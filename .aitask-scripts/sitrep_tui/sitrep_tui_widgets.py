"""sitrep_tui_widgets.py - widgets shared by the sitrep TUI's screens (t2211_10).

Kept apart from ``sitrep_tui_app`` so the dialog modules (``sitrep_tui_actions``,
``sitrep_tui_trails``), which the app imports, can use them without a circular
import. ``sitrep_tui_app`` re-exports ``SelectOnClickList`` under its old name.

``ItemTabStrip`` (t2334) is the main list's one-row tab strip. It follows the
pattern of the trails reader's ``TrailTabStrip`` (``board/trails_app.py``: a
``Static`` that draws synchronously and maps a click through the cell spans it
recorded) but is not that class: ``TrailTabStrip`` lives in the trails App
module, which pulls in the board widget layer, and its click calls that App's
private ``_select_trail_tab``. This strip posts a message instead.
"""

from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import OptionList, Static


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


#: Between two tabs, in every layout.
TAB_SEPARATOR = "│"


def _capped(count: int, allowed: int) -> str:
    """``count`` in at most ``allowed`` cells: exact when it fits, otherwise
    ``allowed - 1`` nines and a ``+`` (``999+`` for 4 cells)."""
    text = str(count)
    if len(text) <= allowed:
        return text
    return "9" * max(allowed - 1, 0) + "+" if allowed > 0 else ""


def strip_segments(rows: list, width: int) -> list:
    """The tab texts to draw in ``width`` cells: ``[(tab_id, text, active)]``.

    ``rows`` is ``[(tab_id, label, short, mark, count, active)]``. Candidates,
    each measured as a WHOLE row with the real counts and the separators, the
    first that fits wins:

    1. full, padded -- `` Triage 3 ``
    2. short, padded -- `` Tri 3 ``
    3. compact -- ``Tri3``
    4. mnemonic with the exact count -- ``?3``
    5. mnemonic, capped: only when 4 does not fit. Each tab gets an equal
       budget and a count wider than its budget is capped to nines and a
       ``+``; the width sets the cap (``999+`` at 30 cells, ``99+`` at 28).

    Layout 5 fits five tabs in 19 cells; below that the strip's CSS ellipsis
    clips (30 columns is the documented minimum). An unknown width (0, before
    the first layout) draws the full labels."""
    if not rows:
        return []
    sep = cell_len(TAB_SEPARATOR) * (len(rows) - 1)
    candidates = (
        [f" {label} {count} " for _i, label, _s, _m, count, _a in rows],
        [f" {short} {count} " for _i, _l, short, _m, count, _a in rows],
        [f"{short}{count}" for _i, _l, short, _m, count, _a in rows],
        [f"{mark}{count}" for _i, _l, _s, mark, count, _a in rows],
    )
    texts = None
    if width <= 0:
        texts = candidates[0]
    else:
        for cand in candidates:
            if sum(cell_len(t) for t in cand) + sep <= width:
                texts = cand
                break
    if texts is None:
        budget = (width - sep) // len(rows)
        texts = [f"{mark}{_capped(count, budget - cell_len(mark))}"
                 for _i, _l, _s, mark, count, _a in rows]
    return [(row[0], text, row[5]) for row, text in zip(rows, texts)]


class ItemTabStrip(Static):
    """The main list's tab strip: one row, drawn synchronously from the rows
    the App hands it (``set_tabs``), re-laid out on every resize. A click is
    mapped through the cell spans recorded at draw time and posted as
    ``ItemTabStrip.Selected`` -- the App owns the active tab."""

    DEFAULT_CSS = """
    ItemTabStrip {
        height: 1;
        width: 100%;
        background: $panel;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    """

    class Selected(Message):
        """A tab was clicked."""

        def __init__(self, tab_id: str) -> None:
            super().__init__()
            self.tab_id = tab_id

    def __init__(self, **kwargs) -> None:
        super().__init__("", markup=False, **kwargs)
        self.can_focus = False
        self._rows: list = []
        #: ``(start cell, end cell, tab id)`` of each tab as last drawn.
        self.spans: list = []
        #: The row last drawn: styled, and as plain text.
        self.drawn = Text()
        self.drawn_text = ""

    def set_tabs(self, rows: list) -> None:
        """``rows``: ``[(tab_id, label, short, mark, count, active)]`` in tab
        order."""
        self._rows = list(rows)
        self._draw()

    def _draw(self) -> None:
        text = Text()
        spans = []
        for tab_id, label, active in strip_segments(self._rows, self.size.width):
            if text.cell_len:
                text.append(TAB_SEPARATOR, style="dim")
            start = text.cell_len
            text.append(label, style="bold reverse" if active else "")
            spans.append((start, text.cell_len, tab_id))
        self.spans = spans
        self.drawn = text
        self.drawn_text = text.plain
        self.update(text)

    def on_resize(self, event: events.Resize) -> None:
        self._draw()

    def tab_at(self, x: int) -> "str | None":
        return next((t for start, end, t in self.spans if start <= x < end), None)

    def on_click(self, event: events.Click) -> None:
        tab_id = self.tab_at(event.x)
        if tab_id is not None:
            event.stop()
            self.post_message(self.Selected(tab_id))
