"""Shared section-aware viewer widgets for aitasks TUIs.

Provides reusable Textual widgets for rendering markdown content that has
been structured with `<!-- section: name [dimensions: ...] -->` markers
(parsed by :mod:`brainstorm.brainstorm_sections`):

- :class:`SectionRow`         Focusable minimap row
- :class:`SectionMinimap`     Vertical list of SectionRows
- :class:`SectionAwareMarkdown` Markdown with scroll-to-section helper
- :class:`SectionViewerScreen`  Full-screen modal with split minimap/content

Keyboard contract (enforced uniformly across all host TUIs that embed these
widgets; see t571_5 plan):

- ``tab`` on minimap/row  → emit :class:`SectionMinimap.ToggleFocus` message
  (host moves focus to companion content widget)
- ``tab`` on companion content → (host responsibility) focus returns to
  minimap via :meth:`SectionMinimap.focus_first_row`
- ``up`` / ``down`` on a row → move focus to previous/next sibling row
- ``enter`` on a row → emit :class:`SectionMinimap.SectionSelected`
- ``escape`` in :class:`SectionViewerScreen` → dismiss
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

from brainstorm.brainstorm_sections import (  # noqa: E402
    ContentSection,
    ParsedContent,
    parse_sections,
)

from rich.text import Text  # noqa: E402

from textual.app import ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, Horizontal, VerticalScroll  # noqa: E402
from textual.message import Message  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import Label, Markdown, Static  # noqa: E402


def _focus_sibling_row(row: "SectionRow", direction: int) -> bool:
    """Move focus to prev (-1) or next (+1) focusable sibling row. Return True on move."""
    parent = row.parent
    if parent is None:
        return False
    focusable = [w for w in parent.children if isinstance(w, SectionRow) and w.can_focus]
    try:
        idx = focusable.index(row)
    except ValueError:
        return False
    target = idx + direction
    if 0 <= target < len(focusable):
        focusable[target].focus()
        focusable[target].scroll_visible()
        return True
    return False


def _filter_sections(
    parsed: ParsedContent, names: list[str] | None
) -> list[ContentSection]:
    """Return sections from *parsed* preserving original order, optionally
    restricted to ``names`` (set membership). Names not present in
    *parsed* are silently skipped."""
    if names is None:
        return list(parsed.sections)
    name_set = set(names)
    return [s for s in parsed.sections if s.name in name_set]


def estimate_section_y(
    parsed: ParsedContent,
    name: str,
    total_lines: int,
    virtual_height: float,
) -> float | None:
    """Estimate the Y scroll position for a named section.

    Uses a line-ratio approximation (``section.start_line / total_lines``)
    against the virtual content height. Intentionally approximate — Textual's
    ``Markdown`` widget does not expose per-line offsets.

    Returns ``None`` if the section is not found or inputs are degenerate.
    """
    if total_lines <= 0 or virtual_height <= 0:
        return None
    for section in parsed.sections:
        if section.name == name:
            ratio = section.start_line / total_lines
            return ratio * virtual_height
    return None


# ---------------------------------------------------------------------------
# Section -> rendered-heading correlation
# ---------------------------------------------------------------------------
#
# Textual's ``Markdown`` widget does not expose per-line offsets, so a section
# cannot be located by source line number. It does, however, publish a table of
# contents (``Markdown.TableOfContentsUpdated``) listing every rendered heading
# as ``(level, title, header_id)`` in document order, where each ``header_id``
# is a queryable widget id. We map each parsed section to its first heading's
# ``header_id`` and scroll to that widget — an exact rendered position instead
# of a line-ratio guess.

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")


def _first_heading(content: str) -> tuple[int, str] | None:
    """Return ``(level, title)`` of the first ATX heading in *content*.

    Fenced code blocks (``` ``` ``` / ``~~~``) are skipped so a ``#`` comment
    inside a code sample is not mistaken for a heading. ``level`` is the number
    of leading ``#`` characters (1–6). Returns ``None`` when *content* has no
    heading.
    """
    fence: str | None = None
    for line in content.split("\n"):
        stripped = line.strip()
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence = stripped[:3]
            continue
        m = _HEADING_RE.match(line)
        if m:
            return len(m.group(1)), m.group(2)
    return None


def _norm_title(title: str) -> str:
    """Normalize a heading title for comparison only (never for slugging).

    Textual de-formats inline markdown in TOC titles (it stores ``foo``, not
    ``` `foo` ```). Strip the inline markers Textual drops — backticks and
    ``*`` / ``_`` emphasis — collapse whitespace, and lowercase, so a section's
    raw markdown heading matches the de-formatted TOC entry.
    """
    title = title.replace("`", "")
    title = re.sub(r"[*_]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip().lower()


def correlate_sections_to_toc(
    sections: list[ContentSection],
    toc: list[tuple[int, str, str]],
) -> dict[str, str]:
    """Map each section name to its first heading's ``header_id`` in *toc*.

    *toc* is Textual's table of contents: ``(level, title, header_id)`` entries
    in document order. Sections are walked in order against a **monotonic**
    pointer into *toc*, so duplicate heading titles resolve to their own
    occurrence by position rather than always matching the first. A section is
    matched to the next TOC entry whose level equals the section's first-heading
    level and whose normalized title matches. Sections without a heading, or
    whose heading is absent from *toc*, are simply omitted (callers fall back to
    the line-ratio estimate).
    """
    anchors: dict[str, str] = {}
    pointer = 0
    for section in sections:
        heading = _first_heading(section.content)
        if heading is None:
            continue
        level, raw_title = heading
        norm = _norm_title(raw_title)
        j = pointer
        while j < len(toc):
            entry = toc[j]
            t_level, t_title, t_id = entry[0], entry[1], entry[2]
            if t_level == level and _norm_title(t_title) == norm:
                if t_id:
                    anchors[section.name] = t_id
                pointer = j + 1
                break
            j += 1
    return anchors


class SectionRow(Static):
    """Focusable row in a :class:`SectionMinimap` — shows section name + dimension tags."""

    can_focus = True

    DEFAULT_CSS = """
    SectionRow {
        width: 100%;
        padding: 0 1;
        background: $surface;
    }
    SectionRow.-compact {
        height: 1;
        text-overflow: ellipsis;
    }
    SectionRow.-expanded {
        height: 2;
    }
    SectionRow:focus {
        background: $accent;
        color: $text;
    }
    SectionRow:hover {
        background: $accent 30%;
    }
    """

    class Selected(Message):
        """Emitted when the user activates a row (click or Enter)."""

        def __init__(self, section_name: str) -> None:
            self.section_name = section_name
            super().__init__()

    def __init__(
        self,
        name: str,
        dimensions: list[str],
        compact: bool = True,
        depth: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.section_name = name
        self.dimensions = dimensions
        self._compact = compact
        self.depth = depth
        self.add_class("-compact" if compact else "-expanded")

    def render(self):
        # Indent nested rows so the minimap reflects the section hierarchy.
        indent = "  " * self.depth
        if self._compact:
            dim_str = f" [{', '.join(self.dimensions)}]" if self.dimensions else ""
            return f" {indent}{self.section_name}{dim_str}"
        text = Text()
        text.append(f" {indent}{self.section_name}", style="bold")
        if self.dimensions:
            text.append(f"\n   {indent}{', '.join(self.dimensions)}", style="dim")
        return text

    def on_click(self) -> None:
        self.post_message(self.Selected(self.section_name))

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Selected(self.section_name))
            event.stop()
        elif event.key == "up":
            if _focus_sibling_row(self, -1):
                event.stop()
                event.prevent_default()
        elif event.key == "down":
            if _focus_sibling_row(self, 1):
                event.stop()
                event.prevent_default()


class SectionMinimap(VerticalScroll):
    """Scrollable list of :class:`SectionRow` widgets.

    The `tab` binding emits :class:`ToggleFocus`; hosts handle the message to
    move focus to the companion content widget.
    """

    BINDINGS = [
        Binding("tab", "toggle_focus", "Content", show=True, priority=True),
    ]

    DEFAULT_CSS = """
    SectionMinimap {
        max-width: 50;
        height: auto;
        max-height: 12;
        border-right: solid $primary;
        background: $panel;
    }
    """

    class SectionSelected(Message):
        """Rebroadcast of :class:`SectionRow.Selected` so hosts listen at the minimap level."""

        def __init__(self, section_name: str) -> None:
            self.section_name = section_name
            super().__init__()

        @property
        def control(self) -> "SectionMinimap | None":
            return self._sender  # type: ignore[return-value]

    class ToggleFocus(Message):
        """Emitted when Tab is pressed while the minimap (or a row) has focus."""

        @property
        def control(self) -> "SectionMinimap | None":
            return self._sender  # type: ignore[return-value]

    def __init__(self, compact: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self._last_focused_row_index: int = 0
        self._compact = compact

    def populate(
        self, parsed: ParsedContent, names: list[str] | None = None,
    ) -> None:
        """Replace all rows with one per section in *parsed*.

        If *names* is provided, only sections whose name is in that list are
        mounted (preserving original parse order; *names* order is ignored).
        Default behavior (``names=None``) is unchanged from prior callers.
        """
        self.remove_children()
        for section in _filter_sections(parsed, names):
            self.mount(SectionRow(
                section.name, section.dimensions,
                compact=self._compact, depth=section.depth,
            ))
        self._last_focused_row_index = 0

    def _rows(self) -> list[SectionRow]:
        return [w for w in self.children if isinstance(w, SectionRow)]

    def focus_first_row(self) -> None:
        """Focus the last-highlighted row (or the first row if none)."""
        rows = self._rows()
        if not rows:
            return
        idx = max(0, min(self._last_focused_row_index, len(rows) - 1))
        rows[idx].focus()
        rows[idx].scroll_visible()

    def on_descendant_focus(self, event) -> None:
        widget = getattr(event, "widget", None)
        if isinstance(widget, SectionRow):
            rows = self._rows()
            if widget in rows:
                self._last_focused_row_index = rows.index(widget)

    def on_section_row_selected(self, event: SectionRow.Selected) -> None:
        self.post_message(self.SectionSelected(event.section_name))
        event.stop()

    def action_toggle_focus(self) -> None:
        self.post_message(self.ToggleFocus())


class SectionAwareMarkdown(VerticalScroll):
    """Scrollable Markdown pane with ``scroll_to_section()`` for named-section navigation."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._section_positions: dict[str, float] = {}
        self._total_lines: int = 0
        self._parsed: ParsedContent | None = None
        # Textual's table of contents (``(level, title, header_id)`` list),
        # captured from ``Markdown.TableOfContentsUpdated`` once rendering
        # completes, and the resulting section-name -> header_id map.
        self._toc: list[tuple[int, str, str]] | None = None
        self._section_anchors: dict[str, str] = {}
        # The section an auto-scroll is currently homing in on. Held while the
        # markdown lays out so the scroll can be re-applied until it settles,
        # then cleared (see request_scroll_to_section / _apply_pending_scroll).
        self._active_scroll_section: str | None = None

    def compose(self) -> ComposeResult:
        yield Markdown(id="section_md")

    @property
    def toc_ready(self) -> bool:
        """True once Textual has published the rendered table of contents."""
        return self._toc is not None

    def update_content(self, text: str, parsed: ParsedContent | None = None) -> None:
        self.query_one("#section_md", Markdown).update(text)
        self._parsed = parsed
        self._total_lines = text.count("\n") + 1
        self._section_positions.clear()
        # Reset rendered-offset state — the Markdown.update() above triggers a
        # fresh async parse that will re-emit TableOfContentsUpdated.
        self._toc = None
        self._section_anchors = {}
        self._active_scroll_section = None
        if parsed and self._total_lines > 0:
            for section in parsed.sections:
                self._section_positions[section.name] = section.start_line / self._total_lines

    def request_scroll_to_section(self, name: str) -> None:
        """Auto-scroll to *name*, deferring until the markdown has rendered.

        ``Markdown.update()`` parses asynchronously, so on first open the
        heading widgets (and the table of contents we resolve anchors from) do
        not exist yet. The request is recorded as the active scroll target and
        applied once the ``TableOfContentsUpdated`` handler fires (or
        immediately, on the next refresh, if the TOC is already available).
        This replaces the previous poll-timer approach, which did not fire
        reliably from a freshly-pushed modal screen.
        """
        self._active_scroll_section = name
        if self.toc_ready:
            self.call_after_refresh(self._apply_pending_scroll)

    def on_markdown_table_of_contents_updated(
        self, event: Markdown.TableOfContentsUpdated
    ) -> None:
        """Capture the rendered heading list and build the section anchor map."""
        self._toc = event.table_of_contents
        if self._parsed is not None:
            self._section_anchors = correlate_sections_to_toc(
                self._parsed.sections, self._toc
            )
        event.stop()
        # Perform any auto-scroll requested before rendering finished.
        if self._active_scroll_section is not None:
            self.call_after_refresh(self._apply_pending_scroll)

    def _apply_pending_scroll(
        self, attempts: int = 5, last_offset: float | None = None
    ) -> None:
        """Re-apply the active auto-scroll until the layout settles.

        A long markdown body lays out over several refresh cycles, so the first
        ``scroll_visible()`` can target an intermediate heading position. Re-run
        the scroll after each refresh until the resulting scroll offset stops
        moving (or the attempt budget is exhausted), which pins the heading to
        the top once layout is final, then clear the target. ``call_after_refresh``
        fires reliably from a modal screen (unlike ``set_interval``).
        """
        name = self._active_scroll_section
        if name is None:
            return
        self.scroll_to_section(name)
        current = self.scroll_offset.y
        if attempts > 0 and current != last_offset:
            self.call_after_refresh(self._apply_pending_scroll, attempts - 1, current)
        else:
            self._active_scroll_section = None

    def scroll_to_section(self, name: str) -> None:
        # Preferred path: scroll to the section's first rendered heading widget.
        # ``scroll_visible(top=True)`` bubbles to this VerticalScroll and aligns
        # the heading to the top of the viewport — an exact rendered position.
        header_id = self._section_anchors.get(name)
        if header_id:
            try:
                md = self.query_one("#section_md", Markdown)
                md.query_one(f"#{header_id}").scroll_visible(top=True, animate=False)
                return
            except Exception:
                pass  # fall through to the defensive line-ratio fallback

        # Fallback: line-ratio estimate (used before the TOC is ready or when a
        # heading can't be resolved). Map ratio to scroll *progress* (0.0 = top,
        # 1.0 = bottom of scrollable range), not raw virtual height.
        ratio = self._section_positions.get(name)
        if ratio is None:
            return
        max_y = getattr(self, "max_scroll_y", None)
        if max_y is None or max_y <= 0:
            max_y = max(0.0, self.virtual_size.height - self.size.height)
        target_y = ratio * max_y
        self.scroll_to(y=target_y, animate=False)


class SectionViewerScreen(ModalScreen):
    """Full-screen split-layout modal: minimap on the left, Markdown on the right.

    When ``section_filter`` is set, the **minimap row list** is restricted to
    those section names, while the full markdown body is still rendered in
    :class:`SectionAwareMarkdown`. Navigation via the minimap is naturally
    scoped to the filtered set (only those rows exist); the underlying
    ``scroll_to_section()`` lookup table is unchanged.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("tab", "focus_minimap", "Minimap", priority=True),
    ]

    DEFAULT_CSS = """
    SectionViewerScreen {
        align: center middle;
    }
    SectionViewerScreen #section_viewer {
        width: 100%;
        height: 100%;
        background: $background;
    }
    SectionViewerScreen #sv_title {
        height: 1;
        padding: 0 1;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    SectionViewerScreen #sv_split {
        width: 100%;
        height: 1fr;
    }
    SectionViewerScreen #sv_minimap {
        width: 32;
        max-width: 32;
        max-height: 100%;
        height: 1fr;
        border-right: tall $panel;
    }
    SectionViewerScreen #sv_minimap:focus-within {
        border-right: tall $accent;
    }
    SectionViewerScreen #sv_content {
        width: 1fr;
        border-left: tall $panel;
    }
    SectionViewerScreen #sv_content:focus {
        border-left: tall $accent;
    }
    """

    def __init__(
        self,
        content: str,
        title: str = "Plan Viewer",
        section_filter: list[str] | None = None,
        scroll_target: str | None = None,
    ) -> None:
        super().__init__()
        self._content = content
        self._title = title
        self._section_filter = section_filter
        # Explicit auto-scroll target (overrides the default "first filtered
        # section"). Used to land on a specific nested subsection rather than
        # its wrapper when navigating from a dimension.
        self._scroll_target = scroll_target

    def compose(self) -> ComposeResult:
        with Container(id="section_viewer"):
            yield Label(self._title, id="sv_title")
            with Horizontal(id="sv_split"):
                yield SectionMinimap(id="sv_minimap", compact=False)
                yield SectionAwareMarkdown(id="sv_content")

    def on_mount(self) -> None:
        parsed = parse_sections(self._content)
        minimap = self.query_one("#sv_minimap", SectionMinimap)
        content = self.query_one("#sv_content", SectionAwareMarkdown)
        content.update_content(self._content, parsed)
        if parsed.sections:
            minimap.populate(parsed, names=self._section_filter)
            minimap.focus_first_row()
            # Auto-scroll so the user lands at relevant content without pressing
            # Enter on the minimap. Prefer an explicit scroll_target (e.g. a
            # specific nested subsection); otherwise fall back to the first
            # filtered section. Markdown.update() parses asynchronously, so the
            # heading widgets don't exist yet — request_scroll_to_section defers
            # the scroll until the table of contents arrives.
            target = self._scroll_target
            if target is None and self._section_filter is not None:
                filtered = _filter_sections(parsed, self._section_filter)
                if filtered:
                    target = filtered[0].name
            if target is not None:
                content.request_scroll_to_section(target)
        else:
            minimap.display = False
            content.focus()

    def on_section_minimap_section_selected(self, event: SectionMinimap.SectionSelected) -> None:
        self.query_one("#sv_content", SectionAwareMarkdown).scroll_to_section(event.section_name)
        event.stop()

    def on_section_minimap_toggle_focus(self, event: SectionMinimap.ToggleFocus) -> None:
        self.query_one("#sv_content", SectionAwareMarkdown).focus()
        event.stop()

    def on_key(self, event) -> None:
        if event.key == "tab":
            self._cycle_focus()
            event.stop()
            event.prevent_default()

    def _cycle_focus(self) -> None:
        minimap = self.query_one("#sv_minimap", SectionMinimap)
        content = self.query_one("#sv_content", SectionAwareMarkdown)
        focused = self.focused
        on_minimap_side = focused is minimap or (
            focused is not None and focused in minimap.walk_children()
        )
        if on_minimap_side:
            content.focus()
        elif minimap.display:
            minimap.focus_first_row()
        else:
            content.focus()

    def action_focus_minimap(self) -> None:
        self._cycle_focus()

    def action_close(self) -> None:
        self.dismiss()


__all__ = [
    "SectionRow",
    "SectionMinimap",
    "SectionAwareMarkdown",
    "SectionViewerScreen",
    "_filter_sections",
    "estimate_section_y",
    "correlate_sections_to_toc",
    "parse_sections",
    "ParsedContent",
    "ContentSection",
]
