"""Fuzzy file search widget for the codebrowser TUI.

Provides an always-visible search box at the top of the code pane.
Typing filters git-tracked files using a fuzzy matching algorithm
adapted from toad (https://github.com/batrachianai/toad).
"""

from __future__ import annotations

import re
from functools import lru_cache
from operator import itemgetter
from typing import Iterable, Sequence

from rich.text import Text

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option


# ---------------------------------------------------------------------------
# Fuzzy matching — adapted from toad's PathFuzzySearch
# ---------------------------------------------------------------------------


class PathFuzzySearch:
    """Fuzzy file-path matcher.

    For each query/candidate pair the algorithm discovers *every* valid
    character alignment (query chars appearing in order inside the
    candidate) and returns the highest-scoring one.

    Scoring heuristics:
    - First-letter bonus: matches at position 0 or right after ``/``
    - Consecutive-group bonus: fewer gaps → higher score
    - Filename boost: 2x when the first match falls inside the filename
      (after the last ``/``)
    """

    def __init__(self, case_sensitive: bool = False) -> None:
        self.case_sensitive = case_sensitive

    def match(self, query: str, candidate: str) -> tuple[float, Sequence[int]]:
        """Return ``(score, matched_positions)`` or ``(0.0, [])``."""
        default: tuple[float, Sequence[int]] = (0.0, [])
        result = max(
            self._match(query, candidate),
            key=itemgetter(0),
            default=default,
        )
        return result

    @classmethod
    @lru_cache(maxsize=1024)
    def _first_letters(cls, candidate: str) -> frozenset[int]:
        return frozenset(
            {0, *(m.start() + 1 for m in re.finditer(r"/", candidate))}
        )

    def _score(self, candidate: str, positions: Sequence[int]) -> float:
        first_letters = self._first_letters(candidate)
        offset_count = len(positions)
        score: float = offset_count + len(first_letters.intersection(positions))

        groups = 1
        last_offset, *rest = positions
        for offset in rest:
            if offset != last_offset + 1:
                groups += 1
            last_offset = offset

        normalized_groups = (offset_count - (groups - 1)) / offset_count
        score *= 1 + (normalized_groups * normalized_groups)

        if positions[0] > candidate.rfind("/"):
            score *= 2
        return score

    def _match(
        self, query: str, candidate: str
    ) -> Iterable[tuple[float, Sequence[int]]]:
        if not self.case_sensitive:
            candidate = candidate.casefold()
            query = query.casefold()

        letter_positions: list[list[int]] = []
        position = 0
        for offset, letter in enumerate(query):
            last_index = len(candidate) - offset
            positions: list[int] = []
            letter_positions.append(positions)
            index = position
            while (location := candidate.find(letter, index)) != -1:
                positions.append(location)
                index = location + 1
                if index >= last_index:
                    break
            if not positions:
                yield (0.0, ())
                return
            position = positions[0] + 1

        possible_offsets: list[list[int]] = []
        query_length = len(query)

        def _collect(offsets: list[int], pi: int) -> None:
            for off in letter_positions[pi]:
                if not offsets or off > offsets[-1]:
                    new = [*offsets, off]
                    if len(new) == query_length:
                        possible_offsets.append(new)
                    else:
                        _collect(new, pi + 1)

        _collect([], 0)
        score = self._score
        for offsets in possible_offsets:
            yield score(candidate, offsets), offsets


# ---------------------------------------------------------------------------
# File search widget
# ---------------------------------------------------------------------------

_MAX_RESULTS = 30


class FileSearchWidget(Container):
    """Fuzzy file search: Input + OptionList dropdown."""

    class FileOpened(Message):
        """Posted when the user picks a file from the search results."""

        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    DEFAULT_CSS = """
    FileSearchWidget {
        height: auto;
    }
    FileSearchWidget Input {
        border: tall $surface-lighten-2;
        background: $surface-lighten-1;
        &:focus {
            border: tall $accent;
            background: $surface-lighten-2;
        }
    }
    FileSearchWidget OptionList {
        max-height: 12;
        background: $surface;
        border-bottom: solid $primary;
    }
    FileSearchWidget OptionList.-hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", priority=True, show=False),
        Binding("down", "cursor_down", "Down", priority=True, show=False),
        Binding("enter", "submit", "Open file", priority=True, show=False),
        Binding("escape", "dismiss_search", "Clear", priority=True, show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._all_files: list[str] = []
        self._fuzzy = PathFuzzySearch()

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search files...", id="file_search_input")
        yield OptionList(id="file_search_results", classes="-hidden")

    def set_files(self, files: list[str]) -> None:
        """Populate the searchable file list (relative paths)."""
        self._all_files = sorted(files)

    # --- event handlers ---------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip()
        ol = self.query_one("#file_search_results", OptionList)

        if not query:
            ol.clear_options()
            ol.add_class("-hidden")
            return

        scored: list[tuple[float, Sequence[int], str]] = []
        for path in self._all_files:
            score, positions = self._fuzzy.match(query, path)
            if score > 0:
                scored.append((score, positions, path))

        scored.sort(key=itemgetter(0), reverse=True)
        top = scored[:_MAX_RESULTS]

        ol.clear_options()
        for _score, positions, path in top:
            ol.add_option(Option(self._highlight(path, positions), id=path))

        if top:
            ol.highlighted = 0
            ol.remove_class("-hidden")
        else:
            ol.add_class("-hidden")

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle click/double-click on a result row."""
        event.stop()
        if event.option.id:
            self.post_message(self.FileOpened(event.option.id))
            self._clear_search()

    # --- key actions ------------------------------------------------------

    def action_cursor_up(self) -> None:
        ol = self.query_one("#file_search_results", OptionList)
        if not ol.has_class("-hidden"):
            ol.action_cursor_up()

    def action_cursor_down(self) -> None:
        ol = self.query_one("#file_search_results", OptionList)
        if not ol.has_class("-hidden"):
            ol.action_cursor_down()

    def action_submit(self) -> None:
        ol = self.query_one("#file_search_results", OptionList)
        if ol.has_class("-hidden") or ol.highlighted is None:
            return
        option = ol.get_option_at_index(ol.highlighted)
        if option.id:
            self.post_message(self.FileOpened(option.id))
            self._clear_search()

    def action_dismiss_search(self) -> None:
        self._clear_search()

    # --- helpers ----------------------------------------------------------

    def _clear_search(self) -> None:
        self.query_one("#file_search_input", Input).value = ""
        ol = self.query_one("#file_search_results", OptionList)
        ol.clear_options()
        ol.add_class("-hidden")

    @staticmethod
    def _highlight(path: str, positions: Sequence[int]) -> Text:
        """Rich Text with directory dimmed, filename normal, matches underlined."""
        text = Text(path)
        # Dim the directory portion
        last_sep = path.rfind("/")
        if last_sep >= 0:
            text.stylize("dim", 0, last_sep + 1)
        # Underline matched character positions
        pos_set = set(positions)
        for idx in pos_set:
            if 0 <= idx < len(path):
                text.stylize("underline bold", idx, idx + 1)
        return text
