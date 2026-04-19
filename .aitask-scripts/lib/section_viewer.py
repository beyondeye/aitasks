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
        self, name: str, dimensions: list[str], compact: bool = True, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.section_name = name
        self.dimensions = dimensions
        self._compact = compact
        self.add_class("-compact" if compact else "-expanded")

    def render(self):
        if self._compact:
            dim_str = f" [{', '.join(self.dimensions)}]" if self.dimensions else ""
            return f" {self.section_name}{dim_str}"
        text = Text()
        text.append(f" {self.section_name}", style="bold")
        if self.dimensions:
            text.append(f"\n   {', '.join(self.dimensions)}", style="dim")
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

    class ToggleFocus(Message):
        """Emitted when Tab is pressed while the minimap (or a row) has focus."""

    def __init__(self, compact: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self._last_focused_row_index: int = 0
        self._compact = compact

    def populate(self, parsed: ParsedContent) -> None:
        """Replace all rows with one per section in *parsed*."""
        self.remove_children()
        for section in parsed.sections:
            self.mount(SectionRow(section.name, section.dimensions, compact=self._compact))
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

    def compose(self) -> ComposeResult:
        yield Markdown(id="section_md")

    def update_content(self, text: str, parsed: ParsedContent | None = None) -> None:
        self.query_one("#section_md", Markdown).update(text)
        self._parsed = parsed
        self._total_lines = text.count("\n") + 1
        self._section_positions.clear()
        if parsed and self._total_lines > 0:
            for section in parsed.sections:
                self._section_positions[section.name] = section.start_line / self._total_lines

    def scroll_to_section(self, name: str) -> None:
        ratio = self._section_positions.get(name)
        if ratio is None:
            return
        target_y = ratio * self.virtual_size.height
        self.scroll_to(y=target_y, animate=False)


class SectionViewerScreen(ModalScreen):
    """Full-screen split-layout modal: minimap on the left, Markdown on the right."""

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

    def __init__(self, content: str, title: str = "Plan Viewer") -> None:
        super().__init__()
        self._content = content
        self._title = title

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
            minimap.populate(parsed)
            minimap.focus_first_row()
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
    "estimate_section_y",
    "parse_sections",
    "ParsedContent",
    "ContentSection",
]
