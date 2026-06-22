"""ait applink — Textual TUI bridging a local ait workspace to a mobile app.

t822_2 shipped the runnable skeleton (pairing token + QR + placeholder status).
t822_7 wires the JSON control plane: on launch the app starts a TLS WebSocket
listener (``server.AppLinkServer``) that accepts the ``pair`` verb, validates
sessions, gates command verbs by permission profile, and dispatches them into
``monitor_core``. The Pairing screen's QR carries the real TLS-cert fingerprint;
the Status screen shows the live connection state.

The binary snapshot/data plane is a follow-up sibling (t822_8).
"""
from __future__ import annotations

import argparse
import asyncio
import socket
import sys
import time
from pathlib import Path

# Repo lib path -- pulls in TuiSwitcherMixin alongside the other TUIs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402

from textual import on, work  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, Horizontal, Vertical  # noqa: E402
from textual.screen import ModalScreen, Screen  # noqa: E402
from textual.widgets import Button, DataTable, Footer, Header, Label, Static  # noqa: E402

# Local imports (sibling modules in the applink package).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pairing import (  # noqa: E402
    build_pairing_uri,
    compute_self_signed_fingerprint,
    detect_lan_ip,
)
from qr_widget import TerminalQR  # noqa: E402
import firewall_doctor  # noqa: E402
from paths import profiles_dir, sessions_dir  # noqa: E402
from sessions import SessionTable  # noqa: E402
from profiles import ProfileGate  # noqa: E402
from tls import CertManager  # noqa: E402
# Pairing-profile/port defaults live in server.py (the Textual-free single
# source of truth shared with the headless runner). A richer QR-time profile
# selector in the TUI is a noted follow-up.
from server import (  # noqa: E402
    AppLinkServer,
    DEFAULT_PORT,
    DEFAULT_PAIR_PROFILE as DEFAULT_PROFILE,
)


def _hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return ""


def _fmt_clock(epoch: float) -> str:
    """Local wall-clock HH:MM for a pairing time (— if unset)."""
    if not epoch:
        return "—"
    return time.strftime("%H:%M", time.localtime(epoch))


def _fmt_ago(epoch: float) -> str:
    """Coarse relative age (e.g. ``12s``/``3m``/``2h`` ago) for last-seen."""
    if not epoch:
        return "—"
    delta = max(0, int(time.time() - epoch))
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


class AppLinkRuntime:
    """Shared runtime: session table, cert, profiles, and the WS server.

    Built once when the app mounts (NOT at construction) so the ``--smoke``
    construct-and-exit path performs no filesystem or network I/O.
    """

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        self.port = port
        self.ip = detect_lan_ip()
        self.host = _hostname()
        self.fingerprint = compute_self_signed_fingerprint()  # ensures the cert
        self.cert_manager = CertManager(sessions_dir())
        self.session_table = SessionTable(sessions_dir())
        self.profile_gate = ProfileGate.load(profiles_dir())
        self.pair_profile = DEFAULT_PROFILE
        self.token = self.session_table.mint_pairing_token()
        self.server: AppLinkServer | None = None
        # Populated off-thread by the mount worker once the listener is up (see
        # ApplinkApp._start_server). Stays None on the --smoke / pre-mount path
        # so construction performs no firewall I/O. A FirewallStatus once set.
        self.firewall: firewall_doctor.FirewallStatus | None = None

    def build_uri(self) -> str:
        return build_pairing_uri(
            token=self.token,
            ip=self.ip,
            port=self.port,
            fingerprint=self.fingerprint,
            hostname=self.host or None,
        )

    def regenerate(self) -> str:
        """Rotate the pairing token and return the fresh QR URI.

        Preserves the t822_2 stable-connection-ID invariant: rotating the token
        only invalidates the *unused* pairing token; already-issued bearers (and
        their live connections) are untouched. Explicit session revocation is a
        separate affordance (noted follow-up), not folded into regenerate.
        """
        self.token = self.session_table.mint_pairing_token()
        return self.build_uri()

    def create_server(self, on_change) -> AppLinkServer:
        try:
            ssl_ctx = self.cert_manager.ssl_context()
        except Exception:
            ssl_ctx = None  # server.start() surfaces the missing-cert error
        self.server = AppLinkServer(
            session_table=self.session_table,
            profile_gate=self.profile_gate,
            ssl_context=ssl_ctx,
            port=self.port,
            pair_profile=self.pair_profile,
            on_change=on_change,
        )
        return self.server


class FirewallFixModal(ModalScreen):
    """Consent modal for opening the bound port on the host firewall (t1043).

    Takes the single :class:`firewall_doctor.FirewallStatus` (it carries
    backend, cidr, port, commands, and the rendered command), so the modal never
    lacks a CIDR source even in generic mode. Two modes:

    - **Detected** — offers "Open it for me" (only when the backend is
      auto-fixable *and* pkexec is present) plus the always-visible, copyable
      exact command.
    - **Generic** (no managed backend detected) — shows the backend-agnostic
      :func:`firewall_doctor.generic_help` block so the fallback always has a UI
      route. No auto-fix.

    Plain ``ModalScreen`` (not ShortcutsMixin) — self-contained, like
    ``lib/stale_entry_modal._RepointInputScreen``.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("c", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    FirewallFixModal { align: center middle; }
    #fw_dialog {
        width: 86;
        max-width: 96%;
        height: auto;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    #fw_title { text-align: center; text-style: bold; padding: 0 0 1 0; }
    #fw_sub { text-align: center; color: $text-muted; padding: 0 0 1 0; }
    #fw_cmd {
        padding: 1 1;
        background: $boost;
        color: $text;
    }
    #fw_actions { height: 3; align: center middle; padding: 1 0 0 0; }
    #fw_actions Button { margin: 0 1; }
    """

    def __init__(self, status: firewall_doctor.FirewallStatus) -> None:
        super().__init__()
        self._status = status

    def compose(self) -> ComposeResult:
        st = self._status
        with Container(id="fw_dialog"):
            if st.detected:
                yield Label(f"Firewall: [bold]{st.backend}[/] is active", id="fw_title")
                yield Label(
                    f"Open port {st.port} for {st.cidr} (LAN-scoped)?",
                    id="fw_sub",
                )
            else:
                yield Label("No managed firewall auto-detected", id="fw_title")
                yield Label(
                    f"If your phone still can't connect, open port {st.port} "
                    f"for {st.cidr} on your firewall:",
                    id="fw_sub",
                )
            # The command is always visible and terminal-selectable — that IS the
            # "show me the command, I'll run it myself" affordance, for every
            # backend (incl. nft/iptables, which have no auto-fix button).
            yield Static(self._command_text(), id="fw_cmd")
            with Horizontal(id="fw_actions"):
                if (
                    st.detected and st.auto_fixable
                    and firewall_doctor.privilege_wrapper() is not None
                ):
                    yield Button("Open it for me", variant="success", id="btn_fw_open")
                yield Button("Cancel", variant="default", id="btn_fw_cancel")

    def _command_text(self) -> str:
        st = self._status
        if st.detected:
            return st.display or ""
        return firewall_doctor.generic_help(st.port, st.cidr)

    @on(Button.Pressed, "#btn_fw_open")
    def _on_open(self) -> None:
        self.app.notify("Requesting privilege to open the firewall port…")
        self._run_open()

    @on(Button.Pressed, "#btn_fw_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @work(thread=True)
    def _run_open(self) -> None:
        # pkexec raises its own polkit dialog; run off the event loop so the TUI
        # is not blocked while the user authenticates.
        ok, detail = firewall_doctor.run_open(self._status)
        self.app.call_from_thread(self._after_open, ok, detail)

    def _after_open(self, ok: bool, detail: str) -> None:
        if ok:
            self.app.notify(
                f"Firewall: {detail} — port {self._status.port} open for "
                f"{self._status.cidr}."
            )
        else:
            self.app.notify(
                f"Could not open the port automatically: {detail}. "
                "Run the shown command manually.",
                severity="error",
            )
        self.dismiss(ok)


class PairingScreen(ShortcutsMixin, Screen):
    """QR-pairing screen: shows a scannable QR for the live pairing token."""

    _shortcuts_scope = "applink.pairing"

    BINDINGS = [
        Binding("r", "regenerate", "Regenerate token"),
        Binding("s", "show_devices", "Devices"),
        Binding("f", "fix_firewall", "Firewall help"),
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
    #firewall_advisory {
        color: $warning;
        padding: 0 2 0 2;
        text-align: center;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._qr: TerminalQR | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Static("Pair a device", id="pairing_title")
            self._qr = TerminalQR(self.app.runtime.build_uri(), id="pairing_qr")
            yield self._qr
            yield Static(
                "Scan with the ait companion app. Press 'r' to regenerate, 's' for status.",
                id="pairing_hint",
            )
            yield Static("", id="firewall_advisory")
        yield Footer()

    def on_mount(self) -> None:
        # The firewall doctor runs asynchronously after the listener binds; poll
        # so the advisory appears once runtime.firewall is populated.
        self._refresh_advisory()
        self.set_interval(2.0, self._refresh_advisory)

    def _refresh_advisory(self) -> None:
        try:
            adv = self.query_one("#firewall_advisory", Static)
        except Exception:
            return
        runtime = getattr(self.app, "runtime", None)
        st = getattr(runtime, "firewall", None) if runtime else None
        if st is None:
            adv.update("")
        elif st.detected:
            adv.update(
                f"⚠ Firewall ({st.backend}) active — if your phone "
                f"can't connect, press 'f' to open port {st.port} for {st.cidr}."
            )
        else:
            adv.update("Press 'f' for firewall help if your phone can't connect.")

    def action_fix_firewall(self) -> None:
        runtime = getattr(self.app, "runtime", None)
        st = getattr(runtime, "firewall", None) if runtime else None
        if st is None:
            self.notify("Firewall: still checking…")
            return
        self.app.push_screen(FirewallFixModal(st))

    def action_regenerate(self) -> None:
        # Rotate the pairing token (already-paired clients keep their bearers —
        # see AppLinkRuntime.regenerate / pairing.generate_token invariant).
        uri = self.app.runtime.regenerate()
        if self._qr is not None:
            self._qr.set_data(uri)

    def action_show_devices(self) -> None:
        self.app.push_screen(DevicesScreen())


class DevicesScreen(ShortcutsMixin, Screen):
    """Paired-device list + revoke, separate from the QR pairing screen.

    Shows the listener state and one row per bearer session (device name/model,
    platform, connection state, paired-at, last-seen, and coarse location when
    the phone provided it). Revoking here is the explicit way to disconnect a
    device — distinct from the 'r' regenerate key, which only rotates the QR and
    leaves paired devices connected (the t822_2 stable-connection-ID invariant).
    """

    _shortcuts_scope = "applink.devices"

    COLUMNS = ("Device", "Platform", "State", "Paired", "Last seen", "Location")

    BINDINGS = [
        Binding("p", "show_pairing", "Pairing"),
        Binding("x", "revoke_selected", "Revoke device"),
    ]

    DEFAULT_CSS = """
    DevicesScreen #devices_status {
        padding: 1 2 0 2;
        text-style: bold;
    }
    DevicesScreen #devices_table {
        padding: 1 2;
        height: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._bearers_by_row: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("", id="devices_status")
        table = DataTable(id="devices_table", cursor_type="row", zebra_stripes=True)
        for col in self.COLUMNS:
            table.add_column(col)
        yield table
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(2.0, self._refresh)

    def _server(self):
        return getattr(self.app.runtime, "server", None) if self.app.runtime else None

    def _refresh(self) -> None:
        server = self._server()
        status = self.query_one("#devices_status", Static)
        table = self.query_one("#devices_table", DataTable)
        if server is None:
            status.update("Starting listener…")
            return
        if server.error:
            status.update(f"Listener error: {server.error}")
            return
        sessions = sorted(server.active_sessions(), key=lambda s: s.created_at)
        status.update(
            f"Listening on port {self.app.runtime.port} — state: "
            f"{server.connection_state()} — {len(sessions)} paired device(s). "
            "Press 'x' to revoke the highlighted device."
        )
        prev_row = table.cursor_row if table.cursor_row is not None else 0
        table.clear()
        self._bearers_by_row = []
        for s in sessions:
            table.add_row(
                s.device_name or "(unnamed)",
                s.platform or "—",
                s.state,
                _fmt_clock(s.created_at),
                _fmt_ago(s.last_seen),
                s.location or "—",
            )
            self._bearers_by_row.append(s.bearer)
        if self._bearers_by_row:
            table.move_cursor(row=min(prev_row, len(self._bearers_by_row) - 1))

    async def action_revoke_selected(self) -> None:
        server = self._server()
        if server is None or not self._bearers_by_row:
            return
        table = self.query_one("#devices_table", DataTable)
        idx = table.cursor_row
        if idx is None or not (0 <= idx < len(self._bearers_by_row)):
            return
        bearer = self._bearers_by_row[idx]
        await server.revoke_session(bearer)
        self.notify("Revoked device session.")
        self._refresh()

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
        self.runtime: AppLinkRuntime | None = None

    def on_mount(self) -> None:
        self.runtime = AppLinkRuntime()
        self.push_screen(PairingScreen())
        self.run_worker(self._start_server(), exclusive=False)

    async def _start_server(self) -> None:
        server = self.runtime.create_server(on_change=self._on_server_change)
        await server.start()
        # Once the listener is up, run the firewall doctor off-thread (it spawns
        # systemctl/ip) so its blocking probes never stall the event loop. Kept
        # out of construction/--smoke entirely (this worker only runs in the live
        # app), preserving the no-I/O smoke contract.
        if server.error is None:
            try:
                self.runtime.firewall = await asyncio.to_thread(
                    firewall_doctor.diagnose, self.runtime.port, self.runtime.ip
                )
            except Exception:
                self.runtime.firewall = None
            if isinstance(self.screen, PairingScreen):
                self.screen._refresh_advisory()

    def _on_server_change(self) -> None:
        # Fired on the event loop; the DevicesScreen polls independently, so this
        # is just a best-effort nudge for any mounted devices view.
        if isinstance(self.screen, DevicesScreen):
            self.screen._refresh()

    async def on_unmount(self) -> None:
        if self.runtime is not None and self.runtime.server is not None:
            await self.runtime.server.stop()


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
        # Construct app + initial screen without running the event loop or any
        # runtime I/O (no cert generation, no socket). Surfaces import errors
        # and basic constructor failures in CI.
        app = ApplinkApp()
        PairingScreen()
        del app
        return 0
    ApplinkApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
