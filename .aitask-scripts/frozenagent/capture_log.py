#!/usr/bin/env python3
"""`CaptureLog` — a `RichLog` that supports native text selection (t1705_6).

**Why this class exists.** The t1705 parent plan states that Textual 8.2.7's
native mouse selection works out of the box because "`Log`/`RichLog` implement
`get_selection`". Re-verification found that false: of the stock widgets only
``Log``, ``Markdown`` and ``Digits`` override it. ``RichLog`` inherits
``Widget.get_selection``, whose implementation is::

    visual = self._render()
    if isinstance(visual, (Text, Content)): ...
    else: return None

``RichLog`` is a ``ScrollView`` that implements ``render_line`` and never
produces a visual from ``_render()``, so that returns ``None`` — a mouse drag
over a stock ``RichLog`` extracts nothing. Its ``render_line`` also never calls
``Strip.apply_offsets`` (which is what lets the compositor map a mouse position
back to a text offset) and never paints a selection span, so the drag is
invisible too.

Switching to ``Log`` is not an option: it is plain-text only, and this widget's
whole purpose is replaying a captured terminal's **ANSI** faithfully via
``Text.from_ansi``. Rendering into a ``Static`` would get selection for free
(``Visual.to_strips`` applies it), but ``DEFAULT_CAPTURE_MAX_LINES`` is 50000
and a single ``Static`` renders every line on each layout, where ``RichLog``
is O(visible rows).

So this subclass adds the three overrides ``Log`` has and ``RichLog`` lacks,
modelled directly on ``textual/widgets/_log.py``:

* :meth:`get_selection` — extraction, from the ANSI-stripped mirror in
  :attr:`_plain`;
* :meth:`selection_updated` — drop the line cache so a drag repaints;
* :meth:`render_line` / :meth:`_render_line` — ``apply_offsets`` plus span
  painting.

These reach into ``RichLog`` internals (``lines``, ``_line_cache``,
``_start_line``, ``_widest_line_width``) and into ``Strip.apply_offsets``, none
of which carry a compatibility promise. ``tests/test_frozenagent_app.py`` pins
every one of them, so a Textual upgrade that moves them fails by name instead of
silently breaking selection.
"""

from __future__ import annotations

from rich.segment import Segment
from rich.style import Style as RichStyle
from textual.selection import Selection
from textual.strip import Strip
from textual.widgets import RichLog


class CaptureLog(RichLog):
    """A `RichLog` whose content can be mouse-selected and copied."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        #: ANSI-stripped mirror of the written content, one entry per source
        #: line. Kept beside `self.lines` (which holds rendered `Strip`s, from
        #: which the original text cannot be recovered faithfully) and indexed
        #: identically, so a selection offset means the same thing in both.
        self._plain: list[str] = []

    # --- content ------------------------------------------------------------

    def set_plain(self, lines: list[str]) -> None:
        """Set the plain-text mirror used for extraction.

        Called by the app right after it writes the corresponding renderable.
        Kept explicit rather than derived inside `write()`: the app already has
        the ANSI-stripped `capture.txt` on hand, and re-deriving it from the
        rendered strips would be both lossy and wasteful.
        """
        self._plain = list(lines)

    def clear(self) -> "CaptureLog":  # type: ignore[override]
        self._plain.clear()
        return super().clear()  # type: ignore[return-value]

    # --- selection ----------------------------------------------------------

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        """Extract the text under `selection`. See `Log.get_selection`."""
        return selection.extract("\n".join(self._plain)), "\n"

    def selection_updated(self, selection: Selection | None) -> None:
        """Drop the cropped-line cache so the new span is painted.

        `RichLog._line_cache` is keyed on position and width only — it knows
        nothing about the selection — so without this a drag would repaint the
        previously cached, unhighlighted strips.
        """
        self._line_cache.clear()
        self.refresh()

    def _selection_style(self) -> RichStyle:
        """The theme's selection style — the same accessor `Log` uses.

        `get_component_rich_style` resolves `screen--selection`'s
        `$screen-selection-background` / `-foreground` against the live theme.
        Do **not** substitute `Style.from_styles(get_component_styles(...))`:
        outside a real render pass that yields a style whose foreground equals
        its background, i.e. invisible selected text (measured).
        """
        try:
            return self.screen.get_component_rich_style("screen--selection")
        except Exception:
            # No screen (unit construction), or a theme without the component
            # class. `reverse` is universally available and is what a terminal
            # selection looks like anyway.
            return RichStyle(reverse=True)

    def _paint_span(self, strip: Strip, start: int, end: int) -> Strip:
        """Restyle cells `[start, end)` of `strip` with the selection style.

        `end == -1` is Textual's "to the end of the line" sentinel
        (`Selection.get_span`).

        The selection style is applied as an **override** (`segment_style +
        selection`), not as a base. `Strip.apply_style` would do the opposite —
        it passes its argument to `Segment.apply_style` as the base, so every
        cell that carries a colour from the captured ANSI would keep that colour
        and the selection would be invisible on exactly the coloured output this
        viewer exists to show.
        """
        length = strip.cell_length
        if end == -1 or end > length:
            end = length
        start = max(0, min(start, length))
        end = max(start, min(end, length))
        if start == end:
            return strip
        # `divide` needs cumulative cut positions and drops any cut beyond the
        # strip, so the trailing `length` is what keeps the tail segment.
        parts = list(strip.divide([start, end, length]))
        if len(parts) < 2:
            return strip
        selection = self._selection_style()
        middle = parts[1]
        parts[1] = Strip(
            [
                Segment(text, selection if style is None else style + selection,
                        control)
                for text, style, control in middle
            ],
            middle.cell_length,
        )
        return Strip.join(parts)

    # --- rendering ----------------------------------------------------------

    def _render_line(self, y: int, scroll_x: int, width: int) -> Strip:
        """`RichLog._render_line`, plus selection painting.

        The span is painted on the **uncropped** strip, before `crop_extend`, so
        the offsets `Selection.get_span` returns (document columns) index the
        same cells the paint touches. Painting after the crop would shift every
        span left by `scroll_x`.

        The cache is consulted only for unselected lines: a cached strip carries
        no selection, and `_line_cache`'s key cannot distinguish one span from
        another.
        """
        if y >= len(self.lines):
            return Strip.blank(width, self.rich_style)

        selection = self.text_selection
        span = selection.get_span(y) if selection is not None else None

        if span is None:
            key = (y + self._start_line, scroll_x, width, self._widest_line_width)
            cached = self._line_cache.get(key)
            if cached is not None:
                return cached
            line = self.lines[y].crop_extend(
                scroll_x, scroll_x + width, self.rich_style
            )
            self._line_cache[key] = line
            return line

        painted = self._paint_span(self.lines[y], span[0], span[1])
        return painted.crop_extend(scroll_x, scroll_x + width, self.rich_style)

    def render_line(self, y: int) -> Strip:
        """`RichLog.render_line`, plus the offsets the compositor selects with.

        Without `apply_offsets` the strip's segments carry no `offset` meta, so
        the screen cannot translate a mouse position into a text coordinate and
        a drag selects nothing — the second half of the defect this class
        exists for. The `y` passed here must be the same document-line index
        used to query `Selection.get_span` above, or the extracted range and the
        painted range would disagree.
        """
        scroll_x, scroll_y = self.scroll_offset
        strip = self._render_line(
            scroll_y + y, scroll_x, self.scrollable_content_region.width
        )
        strip = strip.apply_style(self.rich_style)
        return strip.apply_offsets(scroll_x, scroll_y + y)
