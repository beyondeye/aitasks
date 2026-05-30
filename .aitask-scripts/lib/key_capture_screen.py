"""One-shot key-capture overlay used by the in-TUI shortcut editor (t848_4).

Pushed by ``ShortcutEditorModal`` when the user rebinds a row. It swallows the
next key event and dismisses itself with the captured key combo (e.g. ``"o"``,
``"ctrl+r"``), or with ``None`` if the user presses Escape to cancel.

Carries its own ``DEFAULT_CSS`` (per the ``feedback_modal_self_contained_css``
convention) since ``lib/`` screens pushed by multiple Apps do not inherit any
App-level CSS.
"""

from __future__ import annotations

from textual import events
from textual.screen import ModalScreen
from textual.widgets import Label


class KeyCaptureScreen(ModalScreen[str | None]):
    """Capture a single key combo. Dismisses with the combo, or ``None`` on Esc."""

    DEFAULT_CSS = """
    KeyCaptureScreen {
        align: center middle;
    }
    KeyCaptureScreen > Label {
        width: auto;
        height: auto;
        padding: 1 3;
        border: round $accent;
        background: $surface;
        color: $text;
    }
    """

    # Bare modifier names that some terminals deliver as their own key events.
    # Ignore them and keep waiting for the full combo (e.g. "ctrl+r"). No other
    # allow-list is applied yet — t848_5's row editor can share one from here.
    _MODIFIERS = frozenset({"ctrl", "shift", "alt", "meta", "super", "hyper"})

    def compose(self):
        yield Label("Press a key to bind…  (Esc to cancel)")

    def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()
        if event.key == "escape":
            self.dismiss(None)
            return
        if event.key in self._MODIFIERS:
            return  # wait for the full combo
        self.dismiss(event.key)
