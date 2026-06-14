"""Pairing-token and URI helpers for ait applink.

Implements the QR-bootstrap side of the protocol defined in
``aidocs/applink/protocol.md`` (the `Pairing flow` section). The wire transport
and the actual TLS server are out of scope for this module — these are pure
helpers consumed by the TUI to render the QR code.
"""
from __future__ import annotations

import secrets
import socket
from urllib.parse import quote


def generate_token() -> str:
    """Return a fresh 256-bit URL-safe pairing token.

    The token is used once during pairing and exchanged for a long-lived bearer
    by the server. See ``aidocs/applink/protocol.md`` §Pairing flow.

    **Stable-connection-ID invariant.** Regenerating this token only
    invalidates any *unused* pairing token for new device pairings — it does
    NOT invalidate bearers that have already been issued. Already-paired
    clients keep their connection IDs and stay connected across a "regenerate"
    action in the TUI. The follow-up that wires the WebSocket listener
    (scoped by t822_3) must preserve this invariant when it implements bearer
    issuance.
    """
    return secrets.token_urlsafe(32)


def detect_lan_ip() -> str:
    """Best-effort LAN IPv4 detection.

    Tries to resolve the local hostname through ``getaddrinfo`` and pick the
    first non-loopback IPv4 entry. If nothing usable is found (e.g. host has
    no network configured), falls back to ``"0.0.0.0"`` so the rest of the
    pairing flow can still render the QR for offline testing.
    """
    try:
        infos = socket.getaddrinfo(
            socket.gethostname(), None, family=socket.AF_INET, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror:
        infos = []
    for _family, _type, _proto, _canon, sockaddr in infos:
        ip = sockaddr[0]
        if not ip.startswith("127."):
            return ip
    # Fallback: bind a UDP socket to a public-looking destination and read back
    # the kernel's chosen source address. No packets are sent.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "0.0.0.0"


def build_pairing_uri(
    token: str,
    ip: str,
    port: int,
    fingerprint: str,
    hostname: str | None = None,
) -> str:
    """Build the ``applink://`` pairing URI.

    Grammar (from ``aidocs/applink/protocol.md`` §Pairing flow)::

        applink://<lan-ip>:<port>/pair?t=<base64url(T)>&fp=<fp>[&name=<urlencoded(hostname)>]

    The token is already URL-safe (it comes from :func:`secrets.token_urlsafe`)
    so no extra encoding is needed.
    """
    uri = f"applink://{ip}:{port}/pair?t={token}&fp={fingerprint}"
    if hostname:
        uri += f"&name={quote(hostname, safe='')}"
    return uri


def compute_self_signed_fingerprint() -> str:
    """Return the SHA-256/base64url fingerprint of the server's TLS certificate.

    Ensures the persistent self-signed cert exists (generating it once via
    ``openssl``) and returns its fingerprint for embedding in the pairing QR;
    the mobile client pins this value at pairing time
    (``aidocs/applink/protocol.md`` §Pairing flow step 2). Implemented in t822_7,
    replacing the original stub as a single-function swap.

    On failure (e.g. ``openssl`` missing) returns the sentinel ``"CERT-ERROR"``
    so the TUI still opens — the WebSocket listener surfaces the same failure in
    its connection-state display rather than crashing the app at construction.
    """
    from tls import CertManager, CertError
    from paths import sessions_dir

    try:
        return CertManager(sessions_dir()).fingerprint()
    except (CertError, OSError):
        return "CERT-ERROR"
