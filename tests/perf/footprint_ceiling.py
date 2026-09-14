"""RSS floor for a stand-alone trails TUI (t1794_1 footprint baseline).

Imports only what a trails TUI cannot avoid — `textual`, `rich`, `yaml` and the
Textual widgets the extracted trail view uses (`App`, `Static`, `Label`,
`Button`, `VerticalScroll`, `Container`, `ModalScreen`, `Binding`) — and, run as
a script, idles in a minimal App. `tests/perf/board_footprint.sh` measures it
exactly like the board, so its RSS is the floor a trails app is judged against:
the ceiling on the memory a stand-alone TUI can save.

`import footprint_ceiling` (the script's cold-start probe) defines the App
without running it.
"""

from __future__ import annotations

import rich  # noqa: F401  (part of the floor being measured)
import yaml  # noqa: F401
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen  # noqa: F401
from textual.widgets import Button, Label, Static  # noqa: F401


class CeilingApp(App):
    BINDINGS = [Binding("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        with Container():
            with VerticalScroll():
                yield Static("footprint ceiling: textual + rich + yaml only")


if __name__ == "__main__":
    CeilingApp().run()
