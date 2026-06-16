"""Headless runner for the ait applink bridge (t822_13).

Runs the applink WebSocket listener (control plane + binary push loop) with **no
Textual TUI** — for a box nobody is watching. It is reached via
``ait monitor --headless-for-applink`` (the ``aitask_monitor.sh`` launcher routes
the flag here), NOT through ``applink_app.py`` (which imports Textual at module
top).

The whole server stack (``server`` / ``router`` / ``pusher`` / ``sessions`` /
``profiles`` / ``tls`` / ``pairing`` / ``paths`` / ``monitor_core``) is already
Textual-free, so this runner just assembles the collaborators, starts
:class:`server.AppLinkServer`, prints the pairing info to stdout, and idles until
a signal. **This module must never import** ``applink_app`` or ``qr_widget`` —
both pull in Textual; the no-Textual contract is asserted by
``tests/test_applink_headless.sh``.

Pairing (headless): there is no TTY to press ``r``, so the runner prints the
``applink://…`` pairing URI + the cert fingerprint + an ASCII QR to stdout at
startup. ``SIGHUP`` mints a fresh pairing token and reprints (the no-TTY
equivalent of the TUI "regenerate"; it never touches already-issued bearers —
the t822_2 stable-connection-ID invariant). ``SIGINT``/``SIGTERM`` stop cleanly.
Already-paired bearers persist in ``sessions.json`` across restarts.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import signal
import socket
import sys
from pathlib import Path

_APPLINK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _APPLINK_DIR.parent
for _p in (str(_APPLINK_DIR), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import segno  # noqa: E402

from pairing import build_pairing_uri, detect_lan_ip  # noqa: E402
from paths import profiles_dir, sessions_dir  # noqa: E402
from profiles import ProfileGate  # noqa: E402
from sessions import SessionTable  # noqa: E402
from server import (  # noqa: E402
    AppLinkServer, DEFAULT_PORT, DEFAULT_PAIR_PROFILE,
)
from tls import CertManager, CertError  # noqa: E402


def render_pairing_block(uri: str, fingerprint: str, *, show_qr: bool = True) -> str:
    """Build the stdout pairing block (pure — no I/O, unit-testable).

    Returns the header, fingerprint, pair URL, a hint, and (unless *show_qr* is
    False) an ASCII QR of *uri* rendered with ``segno``.
    """
    lines = [
        "",
        "=== ait applink — headless bridge ===",
        f"Fingerprint: {fingerprint}",
        f"Pair URL:    {uri}",
        "Scan the QR (or open the URL) with the ait companion app.",
        "Signals: SIGHUP = new pairing token + reprint · SIGINT/SIGTERM = stop.",
    ]
    block = "\n".join(lines)
    if show_qr:
        buf = io.StringIO()
        segno.make(uri).terminal(buf, border=1)
        block += "\n\n" + buf.getvalue()
    return block


async def serve(*, port: int, profile: str, show_qr: bool = True) -> int:
    """Run the headless applink listener until a stop signal. Returns an exit code.

    Input validation happens **before any state-mutating side effect**: an
    unknown ``--profile`` is rejected before the pairing token is minted, the
    TLS cert is generated, or any socket is opened. ``CertManager`` and
    ``SessionTable`` are referenced as module globals so a test can monkeypatch
    them to prove they are not constructed on the bad-profile path.
    """
    # 1. Validate the profile first — ProfileGate.load only reads YAML (no
    #    token, no cert, no socket), so a typo fails clean with zero side effects.
    profile_gate = ProfileGate.load(profiles_dir())
    valid = profile_gate.names()
    if profile not in valid:
        print(
            f"Unknown applink profile {profile!r}. "
            f"Valid profiles: {', '.join(sorted(valid)) or '(none configured)'}.",
            file=sys.stderr,
        )
        return 2

    # 2. Ensure the persistent self-signed cert (wss:// is the baseline — no
    #    plaintext fallback, mirroring AppLinkServer.start()).
    cert = CertManager(sessions_dir())
    try:
        fingerprint = cert.fingerprint()
        ssl_ctx = cert.ssl_context()
    except (CertError, OSError) as exc:
        print(f"Cannot start applink bridge: {exc}", file=sys.stderr)
        return 1

    # 3. Session table + a fresh single-use pairing token.
    session_table = SessionTable(sessions_dir())
    token = session_table.mint_pairing_token()

    # 4. Build and start the listener.
    server = AppLinkServer(
        session_table=session_table,
        profile_gate=profile_gate,
        ssl_context=ssl_ctx,
        port=port,
        pair_profile=profile,
        on_change=None,
    )
    await server.start()
    if server.error:
        print(f"applink listener error: {server.error}", file=sys.stderr)
        await server.stop()
        return 1

    # 5. Print the pairing block (refreshed on SIGHUP via _emit).
    ip = detect_lan_ip()
    host = socket.gethostname()

    def _emit() -> None:
        uri = build_pairing_uri(token, ip, port, fingerprint, host or None)
        print(render_pairing_block(uri, fingerprint, show_qr=show_qr), flush=True)

    _emit()

    # 6. Signals: SIGINT/SIGTERM stop; SIGHUP re-mints the token and reprints.
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _reprint() -> None:
        nonlocal token
        try:
            token = session_table.mint_pairing_token()
            _emit()
        except Exception:
            # A reprint failure must never take the server down.
            pass

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    if hasattr(signal, "SIGHUP"):
        try:
            loop.add_signal_handler(signal.SIGHUP, _reprint)
        except (NotImplementedError, RuntimeError):
            pass

    # 7. Idle until a stop signal, then shut down cleanly.
    try:
        await stop.wait()
    finally:
        await server.stop()
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ait monitor --headless-for-applink",
        description=(
            "Run the ait applink bridge headless (no TUI) on an unattended box: "
            "serve the mobile companion listener and print pairing info to stdout."
        ),
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"TCP port for the wss:// listener (default {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--profile", default=DEFAULT_PAIR_PROFILE,
        help=(
            "Permission profile assigned to a newly paired device "
            f"(default {DEFAULT_PAIR_PROFILE})."
        ),
    )
    parser.add_argument(
        "--no-qr", action="store_true",
        help="Print only the pairing URL + fingerprint, no ASCII QR "
             "(useful when redirecting stdout to a log file).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    return asyncio.run(
        serve(port=args.port, profile=args.profile, show_qr=not args.no_qr)
    )


if __name__ == "__main__":
    sys.exit(main())
