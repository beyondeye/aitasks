"""Pairing-token and URI helpers for ait applink.

Implements the QR-bootstrap side of the protocol defined in
``aidocs/applink/protocol.md`` (the `Pairing flow` section). The wire transport
and the actual TLS server are out of scope for this module — these are pure
helpers consumed by the TUI to render the QR code.
"""
from __future__ import annotations

import ipaddress
import re
import secrets
import socket
from typing import NamedTuple, Sequence
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


class Endpoint(NamedTuple):
    """One advertised endpoint record (protocol.md §Pairing flow,
    "Endpoint & trust model"): where to reach the server and how to trust it.
    ``kind`` is a racing preference hint (``lan`` preferred); ``trust`` is
    ``pin`` (QR fingerprint anchors the TLS check) or ``ca`` (platform CA
    chain + hostname verification).
    """

    host: str
    port: int
    kind: str   # lan | mesh | tunnel
    trust: str  # pin | ca


class ResolvedAdvertise(NamedTuple):
    """Result of :func:`resolve_advertised_endpoints`.

    ``override`` says whether an advertised-endpoint override is active —
    emitters use it to decide between explicit ``kind=``/``trust=`` params
    (override) and the byte-identical legacy LAN-only URI (no override).
    ``warning`` is a user-facing string when a *config* override was invalid
    and silently degraded to the LAN address (never set on the CLI path,
    which rejects invalid input up front).
    """

    primary: Endpoint
    alts: list[Endpoint]
    warning: str | None
    override: bool


def normalize_advertised_host(value: str) -> tuple[str, int | None]:
    """Normalize a user-supplied advertised-endpoint string to ``(host, port)``.

    Users paste endpoint strings from tunnel/mesh docs — accept the common
    forms and reduce them to a bare host plus an optional embedded port:

    - a leading ``scheme://`` (any scheme), path, query, fragment, and
      trailing slashes are stripped;
    - bare hostname/FQDN, IPv4 literal, bracketed IPv6 (``[fd7a::1]``), and
      bare IPv6 literal are accepted, each optionally with ``:port``;
    - the returned host is bracket-free (:func:`format_endpoint_host` adds
      brackets at emission time).

    Raises ``ValueError`` with a human-readable reason for anything that
    cannot be a valid QR authority (empty result, userinfo ``@``, whitespace
    in the host, invalid port, non-IPv6 multi-colon strings).
    """
    s = value.strip()
    if "://" in s:
        s = s.split("://", 1)[1]
    for sep in "/?#":
        s = s.split(sep, 1)[0]
    if not s:
        raise ValueError("empty host")
    if "@" in s:
        raise ValueError("userinfo ('@') is not allowed in the advertised host")
    port: int | None = None
    if s.startswith("["):
        m = re.match(r"^\[([^\]]+)\](?::(\d+))?$", s)
        if not m:
            raise ValueError(f"malformed bracketed IPv6 literal: {s!r}")
        host = m.group(1)
        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            raise ValueError(f"not an IPv6 address: {host!r}") from None
        if m.group(2) is not None:
            port = int(m.group(2))
    elif s.count(":") >= 2:
        # Multiple colons without brackets: only a bare IPv6 literal is valid.
        try:
            ipaddress.IPv6Address(s)
        except ValueError:
            raise ValueError(
                f"invalid host {s!r} (multiple ':' but not an IPv6 literal; "
                "bracket IPv6 to attach a port, e.g. [fd7a::1]:8765)"
            ) from None
        host = s
    elif ":" in s:
        host, port_s = s.rsplit(":", 1)
        if not port_s.isdigit():
            raise ValueError(f"invalid port {port_s!r}")
        port = int(port_s)
    else:
        host = s
    if not host:
        raise ValueError("empty host")
    if re.search(r"\s", host):
        raise ValueError(f"whitespace inside host: {host!r}")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"port out of range: {port}")
    return host, port


def advertise_host_argtype(value: str) -> str:
    """Argparse ``type=`` wrapper for ``--advertise-host`` (shared by the TUI
    and headless argparsers): validates via :func:`normalize_advertised_host`
    so an invalid host fails with a clean argparse error **before any side
    effect**, but returns the raw string — the resolver re-normalizes so the
    CLI and config paths share one code path.
    """
    import argparse

    try:
        normalize_advertised_host(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None
    return value


def advertise_port_argtype(value: str) -> int:
    """Argparse ``type=`` wrapper for ``--advertise-port`` (shared by the TUI
    and headless argparsers): enforces the ``[1, 65535]`` contract with a
    clean argparse error before any side effect (plain ``type=int`` would
    accept 0/70000 and emit an invalid or misleading QR).
    """
    import argparse

    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid port {value!r}") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port out of range [1, 65535]: {port}")
    return port


def format_endpoint_host(host: str) -> str:
    """Bracket a bare IPv6 literal for use in a URL authority / ``alt`` record."""
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def encode_alt_param(alts: Sequence[Endpoint]) -> str:
    """Encode alternate endpoints as the single ``alt=`` param value.

    Wire grammar (protocol.md §Pairing flow, "Endpoint & trust model"): a
    URL-encoded comma-separated list of ``host:port;kind;trust`` records —
    one ``alt=`` param, never repeated (repeated query keys collapse
    last-wins in existing client parsers).
    """
    joined = ",".join(
        f"{format_endpoint_host(e.host)}:{e.port};{e.kind};{e.trust}" for e in alts
    )
    return quote(joined, safe="")


def resolve_advertised_endpoints(
    *,
    serving_port: int,
    detected_ip: str,
    config: dict | None = None,
    cli_host: str | None = None,
    cli_port: int | None = None,
    cli_kind: str | None = None,
    cli_trust: str | None = None,
) -> ResolvedAdvertise:
    """Resolve the advertised endpoint(s) for the pairing QR.

    **Group-level precedence (no cross-source field mixing):** if any
    ``cli_*`` value is set, the CLI group defines the entire override and all
    ``advertised_*`` config keys are ignored — a one-shot CLI host must never
    silently inherit a stale configured ``advertised_kind``/``trust``/``port``.
    Otherwise the config group applies. Within the winning group, unset
    fields default to: port = explicit field > port embedded in the host
    string > *serving_port*; kind = explicit > ``mesh``; trust = explicit >
    ``pin``.

    No override host anywhere → legacy LAN-only result
    (``override=False``: emitters omit ``kind``/``trust``/``alt`` so the QR
    stays byte-identical to the pre-override form). An invalid **config**
    host degrades to the same legacy result with a ``warning`` the caller
    must surface; an invalid **CLI** host raises (callers argparse-reject it
    before any side effect, so this is a defensive backstop).
    """
    cfg = config or {}
    cli_group = any(v is not None for v in (cli_host, cli_port, cli_kind, cli_trust))
    lan_primary = Endpoint(detected_ip, serving_port, "lan", "pin")

    if cli_group:
        if cli_host is None:
            raise ValueError(
                "--advertise-port/--advertise-kind/--advertise-trust require "
                "--advertise-host"
            )
        source = "cli"
        raw_host, explicit_port, kind, trust = cli_host, cli_port, cli_kind, cli_trust
    elif cfg.get("advertised_host"):
        source = "config"
        raw_host = cfg["advertised_host"]
        explicit_port = cfg.get("advertised_port")
        kind = cfg.get("advertised_kind")
        trust = cfg.get("advertised_trust")
    else:
        return ResolvedAdvertise(lan_primary, [], None, False)

    if explicit_port is not None and not 1 <= explicit_port <= 65535:
        # Config ports are range-checked by the loader; this backstops the
        # CLI path (argparse's advertise_port_argtype rejects these earlier).
        raise ValueError(f"advertised port out of range [1, 65535]: {explicit_port}")

    try:
        host, embedded_port = normalize_advertised_host(raw_host)
    except ValueError as exc:
        if source == "cli":
            raise
        warning = (
            f"invalid tmux.applink.advertised_host ({exc}) — "
            "QR advertises the LAN address"
        )
        return ResolvedAdvertise(lan_primary, [], warning, False)

    # Port chain: explicit field > embedded-in-host > serving port. Selected
    # by None-ness, not truthiness, so a (never-valid) 0 can't silently slip
    # down the chain.
    if explicit_port is not None:
        resolved_port = explicit_port
    elif embedded_port is not None:
        resolved_port = embedded_port
    else:
        resolved_port = serving_port

    primary = Endpoint(
        host,
        resolved_port,
        kind or "mesh",
        trust or "pin",
    )
    alts: list[Endpoint] = []
    if detected_ip not in ("0.0.0.0", host):
        alts.append(Endpoint(detected_ip, serving_port, "lan", "pin"))
    return ResolvedAdvertise(primary, alts, None, True)


def build_pairing_uri(
    token: str,
    ip: str,
    port: int,
    fingerprint: str,
    hostname: str | None = None,
    kind: str | None = None,
    trust: str | None = None,
    alt: Sequence[Endpoint] | None = None,
) -> str:
    """Build the ``applink://`` pairing URI.

    Grammar (from ``aidocs/applink/protocol.md`` §Pairing flow)::

        applink://<host>:<port>/pair?t=<base64url(T)>&fp=<fp>[&kind=<kind>][&trust=<trust>][&alt=<alt>][&name=<urlencoded(hostname)>]

    The token is already URL-safe (it comes from :func:`secrets.token_urlsafe`)
    so no extra encoding is needed. ``kind``/``trust``/``alt`` are OPTIONAL and
    additive (t1061_1): all omitted → the legacy LAN-only URI, byte-identical.
    IPv6 authority hosts are bracketed automatically.
    """
    uri = f"applink://{format_endpoint_host(ip)}:{port}/pair?t={token}&fp={fingerprint}"
    if kind:
        uri += f"&kind={kind}"
    if trust:
        uri += f"&trust={trust}"
    if alt:
        uri += f"&alt={encode_alt_param(alt)}"
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
