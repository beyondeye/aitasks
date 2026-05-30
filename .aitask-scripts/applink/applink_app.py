"""ait applink — Textual TUI for pairing a mobile companion via QR.

This child task (t822_2) ships the runnable skeleton:
  - generate a one-time pairing token
  - render the ``applink://`` URI as a QR code on screen
  - placeholder status screen for "no client connected"

Socket / WebSocket wiring is intentionally out of scope; it is scoped by
sibling task t822_3 (monitor port design).
"""
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

# Repo lib path -- pulls in TuiSwitcherMixin alongside the other TUIs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, Vertical  # noqa: E402
from textual.screen import Screen  # noqa: E402
from textual.widgets import Footer, Header, Static  # noqa: E402

# Local imports (sibling modules in the applink package).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pairing import (  # noqa: E402
    build_pairing_uri,
    compute_self_signed_fingerprint,
    detect_lan_ip,
    generate_token,
)
from qr_widget import TerminalQR  # noqa: E402


DEFAULT_PORT = 8765


def _hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return ""


class PairingScreen(ShortcutsMixin, Screen):
    """QR-pairing screen: shows token, URI, and a scannable QR code."""

    _shortcuts_scope = "applink.pairing"

    BINDINGS = [
        Binding("r", "regenerate", "Regenerate token"),
        Binding("s", "show_status", "Status"),
    ]

    DEFAULT_CSS = """
    PairingScreen {
        align: center middle;
    }
    #pairing_title {
        text-style: bold;
        padding: 0 1;
    }
    #pairing_qr {
        padding: 1 2;
    }
    #pairing_hint {
        color: $text-muted;
        padding: 1 2 0 2;
        text-align: center;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._port = DEFAULT_PORT
        self._ip = detect_lan_ip()
        self._fp = compute_self_signed_fingerprint()
        self._host = _hostname()
        self._token = generate_token()
        self._uri = self._build_uri()
        self._qr: TerminalQR | None = None

    def _build_uri(self) -> str:
        return build_pairing_uri(
            token=self._token,
            ip=self._ip,
            port=self._port,
            fingerprint=self._fp,
            hostname=self._host or None,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Static("Pair a device", id="pairing_title")
            self._qr = TerminalQR(self._uri, id="pairing_qr")
            yield self._qr
            yield Static(
                "Scan with the ait companion app. Press 'r' to regenerate, 's' for status.",
                id="pairing_hint",
            )
        yield Footer()

    def action_regenerate(self) -> None:
        # Regenerate only invalidates the unused pairing token — already-paired
        # clients carry a long-lived bearer and keep their connection IDs. See
        # pairing.regenerate_pairing_token() for the invariant.
        self._token = generate_token()
        self._uri = self._build_uri()
        if self._qr is not None:
            self._qr.set_data(self._uri)

    def action_show_status(self) -> None:
        self.app.push_screen(StatusScreen())


class StatusScreen(ShortcutsMixin, Screen):
    """Placeholder status screen until the WebSocket listener lands."""

    _shortcuts_scope = "applink.status"

    BINDINGS = [
        Binding("p", "show_pairing", "Pairing"),
    ]

    DEFAULT_CSS = """
    StatusScreen {
        align: center middle;
    }
    #status_card {
        padding: 2 4;
        border: thick $primary;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="status_card"):
            yield Static("No client connected — socket wiring is a follow-up task (t822_3).")
        yield Footer()

    def action_show_pairing(self) -> None:
        self.app.pop_screen()


class ApplinkApp(TuiSwitcherMixin, ShortcutsMixin, App):
    """Textual app for the App Linker TUI."""

    _shortcuts_scope = "applink"

    TITLE = "ait applink"

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_tui_name = "applink"

    def on_mount(self) -> None:
        self.push_screen(PairingScreen())


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ait applink", description="App Linker TUI")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Headless smoke test: construct the app and exit 0 without entering the event loop.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    if args.smoke:
        # Construct app + initial screen without running the event loop.
        # Surfaces import errors and basic constructor failures in CI.
        app = ApplinkApp()
        # Touch the pairing screen so token + QR widget construction is exercised.
        PairingScreen()
        del app
        return 0
    ApplinkApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
