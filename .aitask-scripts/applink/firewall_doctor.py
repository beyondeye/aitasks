"""Launch-time firewall doctor for ait applink (t1043).

When the applink server binds ``0.0.0.0:<port>`` but a host firewall silently
drops inbound TCP on that port, the phone can't connect and the only symptom is
a generic "NETWORK, try again". This module detects an active host firewall at
launch, surfaces a clear advisory, and (on explicit consent) opens the bound
port with a single LAN-scoped privileged command — so the user never crafts
firewall rules by hand.

**Why not a self-connect probe.** The original task design proposed probing
reachability by connecting from the host to ``<lan-ip>:<port>``. That cannot
detect a real firewall drop: on Linux a connection from the host to *its own*
LAN IP is routed through the loopback device (``lo``), which ufw/iptables/
nftables accept unconditionally via the standard ``-i lo -j ACCEPT`` before-rule.
So a self-connect succeeds even when the firewall blocks *external* inbound — it
would report "reachable" in exactly the scenario this doctor exists to catch.
We therefore detect the active firewall *backend* instead and never claim the
port is "blocked" (no false positives); the advisory is conditional ("if your
phone can't connect…") and the definitive open happens only on consent.

**Scope of auto-detection vs. backend-agnostic coverage.** ``detect_backend``
only drives the *auto-advisory* and is honestly limited to managed/active
backends we can detect without root (ufw/firewalld/nftables via
``systemctl is-active``). Backend-agnostic coverage is delivered separately by
:func:`generic_help` — the always-reachable show-command fallback (TUI ``f`` key
and a headless hint) that covers bare iptables, Docker-managed rules,
iptables-nft, and nft rules without ``nftables.service``.

Pure, stdlib-only (no Textual/segno) so it is unit-testable and safe to import
from both the TUI (``applink_app.py``) and the headless runner (``headless.py``).
All subprocess calls are isolated in thin wrappers; the parse/synthesis
functions take their input as arguments so tests inject fixtures.
"""
from __future__ import annotations

import ipaddress
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field

# Service names probed via ``systemctl is-active``, in priority order. ufw and
# firewalld are front-ends preferred over a raw nftables service.
_BACKEND_SERVICES = (
    ("ufw", "ufw"),
    ("firewalld", "firewalld"),
    ("nftables", "nftables"),
)

# Backends whose "add allow rule" command is natively idempotent and safe to
# auto-run on consent. Raw nft/iptables have no clean idempotent one-liner, so
# they are show-command-only (see :func:`auto_fixable`).
_AUTO_FIXABLE = ("ufw", "firewalld")

# All four backends, for the backend-agnostic generic-help fallback.
_ALL_BACKENDS = ("ufw", "firewalld", "nftables", "iptables")

_PROBE_TIMEOUT_S = 1.5


def _default_probe(service: str) -> str:
    """Return ``systemctl is-active <service>`` output ("active"/"inactive"/…).

    Timeout-bound and failure-silent: a missing ``systemctl`` (non-systemd host,
    container, WSL, minimal distro), a timeout (slow DBus), or any OS error
    yields ``""`` rather than hanging or raising — the caller treats anything
    other than ``"active"`` as "not this backend".
    """
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""
    return (proc.stdout or "").strip()


def detect_backend(probe=_default_probe) -> str | None:
    """Return the first active firewall backend, or ``None`` if none detected.

    Priority order: ``ufw`` > ``firewalld`` > ``nftables``. Detection is
    unprivileged (``systemctl is-active``), timeout-bound, and failure-silent
    (see :func:`_default_probe`). ``probe`` is injectable so tests can drive
    every branch — including the missing-``systemctl`` / timeout paths (probe
    returns ``""``) — without touching the host.

    Returns ``None`` when no service-managed firewall is cheaply detectable;
    backend-agnostic coverage then comes from :func:`generic_help`.
    """
    for backend, service in _BACKEND_SERVICES:
        if probe(service).strip() == "active":
            return backend
    return None


def parse_lan_cidr(ip_addr_output: str, lan_ip: str) -> str:
    """Derive the LAN network CIDR for *lan_ip* from ``ip -o -4 addr show`` text.

    Finds the ``inet <ip>/<prefix>`` entry whose address equals *lan_ip* and
    returns its real ``<network>/<prefix>`` (e.g. ``192.168.1.0/24``). Falls
    back to a ``/24`` derived from *lan_ip* when no matching entry is present
    (or the output is empty / ``ip`` was unavailable).
    """
    for line in ip_addr_output.splitlines():
        # `-o` output is one address per line: "... inet 192.168.1.23/24 brd ..."
        tokens = line.split()
        for i, tok in enumerate(tokens):
            if tok == "inet" and i + 1 < len(tokens):
                addr = tokens[i + 1]            # e.g. "192.168.1.23/24"
                if "/" in addr and addr.split("/", 1)[0] == lan_ip:
                    try:
                        return str(ipaddress.ip_interface(addr).network)
                    except ValueError:
                        pass
    return _fallback_cidr(lan_ip)


def _fallback_cidr(lan_ip: str) -> str:
    """A best-effort ``/24`` network for *lan_ip* (last octet zeroed)."""
    try:
        return str(ipaddress.ip_network(f"{lan_ip}/24", strict=False))
    except ValueError:
        return f"{lan_ip}/24"


def host_lan_cidr(lan_ip: str) -> str:
    """Run ``ip -o -4 addr show`` and return *lan_ip*'s network CIDR.

    Failure-silent: if ``ip`` is missing or errors, falls back to a ``/24``.
    """
    try:
        proc = subprocess.run(
            ["ip", "-o", "-4", "addr", "show"],
            capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S,
        )
        return parse_lan_cidr(proc.stdout or "", lan_ip)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return _fallback_cidr(lan_ip)


def build_open_commands(
    backend: str, port: int, cidr: str, proto: str = "tcp",
) -> list[list[str]]:
    """Return the privileged argv(s) that open *port* for *cidr* on *backend*.

    A list of argv lists: ufw/nft/iptables are one command; firewalld is two
    (add the rich rule, then reload). The rule is always scoped to *cidr*, never
    world-open.
    """
    port_s = str(port)
    if backend == "ufw":
        return [["ufw", "allow", "from", cidr, "to", "any",
                 "port", port_s, "proto", proto]]
    if backend == "firewalld":
        rich = (f"rule family=ipv4 source address={cidr} "
                f"port port={port_s} protocol={proto} accept")
        return [
            ["firewall-cmd", "--permanent", f"--add-rich-rule={rich}"],
            ["firewall-cmd", "--reload"],
        ]
    if backend == "nftables":
        return [["nft", "add", "rule", "inet", "filter", "input",
                 "ip", "saddr", cidr, proto, "dport", port_s, "accept"]]
    if backend == "iptables":
        return [["iptables", "-I", "INPUT", "-p", proto, "-s", cidr,
                 "--dport", port_s, "-j", "ACCEPT"]]
    return []


def auto_fixable(backend: str | None) -> bool:
    """True when *backend*'s allow command is idempotent and safe to auto-run."""
    return backend in _AUTO_FIXABLE


def privilege_wrapper() -> list[str] | None:
    """Return the privilege-escalation prefix, or ``None`` if none usable.

    Prefers ``pkexec`` — it raises its own polkit dialog, which (unlike an
    interactive ``sudo``) does not fight Textual's hold on the terminal. We do
    NOT shell out to interactive ``sudo`` from inside the TUI; when pkexec is
    absent the caller falls back to showing the exact command.
    """
    if shutil.which("pkexec"):
        return ["pkexec"]
    return None


def display_command(commands: list[list[str]]) -> str:
    """Render *commands* as a copy-pasteable, ``sudo``-prefixed shell string.

    Uses :func:`shlex.join` (NOT a naive space-join) so multi-word argv elements
    stay valid when pasted — critically the firewalld rich rule, whose
    ``--add-rich-rule=rule family=ipv4 … accept`` is a single argv element
    containing spaces. Multiple commands are joined with `` && ``.
    """
    return " && ".join("sudo " + shlex.join(argv) for argv in commands)


def generic_help(port: int, cidr: str) -> str:
    """Backend-agnostic show-command fallback (no backend was auto-detected).

    Lists the exact LAN-scoped allow command for each of ufw/firewalld/nft/
    iptables, prefaced by a cautious line, so the user can apply whichever
    matches their host. This is the always-reachable UI route to the fallback.
    """
    lines = [
        "No managed firewall was auto-detected. If your phone still can't "
        f"connect, open port {port} for {cidr} with the command for your host:",
    ]
    for backend in _ALL_BACKENDS:
        cmds = build_open_commands(backend, port, cidr)
        lines.append(f"  {backend}: {display_command(cmds)}")
    return "\n".join(lines)


def interpret_result(
    backend: str | None, returncode: int, output: str,
) -> tuple[bool, str]:
    """Classify a privileged command's outcome, backend-aware.

    A no-op re-run (rule already present) must report *success*, not failure:
    ufw prints "Skipping adding existing rule" (exit 0) and firewalld prints
    "Warning: ALREADY_ENABLED" — both map to ``(True, "already open")`` even on
    a non-zero exit. Otherwise: exit 0 → opened; any other exit → failure with
    the captured output.
    """
    low = (output or "").lower()
    already_markers = (
        "skipping adding existing rule",   # ufw
        "already_enabled",                 # firewalld (ALREADY_ENABLED)
        "already enabled",
        "rule already exists",
    )
    if any(m in low for m in already_markers):
        return True, "already open"
    if returncode == 0:
        return True, "opened"
    detail = (output or "").strip() or f"exit {returncode}"
    return False, detail


@dataclass
class FirewallStatus:
    """Result of :func:`diagnose`. Always carries a real ``cidr`` and ``port``.

    ``backend`` is ``None`` when no managed firewall was auto-detected — but
    ``cidr``/``port`` are still set so the generic-help fallback has the real
    LAN-scoped values. ``detected`` is the convenience predicate.
    """

    backend: str | None
    cidr: str
    port: int
    auto_fixable: bool = False
    commands: list[list[str]] = field(default_factory=list)
    display: str | None = None

    @property
    def detected(self) -> bool:
        return self.backend is not None


def diagnose(port: int, lan_ip: str) -> FirewallStatus:
    """Detect the active firewall backend and synthesize the open command(s).

    **Always returns a FirewallStatus, never None** — the generic-help fallback
    needs ``cidr`` even when nothing is detected, so ``cidr`` is computed via
    :func:`host_lan_cidr` regardless. Runs subprocesses (``systemctl``/``ip``),
    so it must only be called off the construct/``--smoke`` path; both call sites
    invoke it via ``asyncio.to_thread`` so its blocking calls never stall the
    event loop.
    """
    cidr = host_lan_cidr(lan_ip)
    backend = detect_backend()
    if backend is None:
        return FirewallStatus(backend=None, cidr=cidr, port=port)
    commands = build_open_commands(backend, port, cidr)
    return FirewallStatus(
        backend=backend,
        cidr=cidr,
        port=port,
        auto_fixable=auto_fixable(backend),
        commands=commands,
        display=display_command(commands),
    )


def run_open(status: FirewallStatus) -> tuple[bool, str]:
    """Run *status*'s open command(s) under :func:`privilege_wrapper`.

    Takes the whole :class:`FirewallStatus` so it carries ``status.backend`` for
    :func:`interpret_result`. Returns ``(ok, detail)``. Real privileged
    execution is not unit-tested (it needs root/polkit); command synthesis and
    :func:`interpret_result` classification are, and live execution is the
    manual-verification follow-up.
    """
    wrapper = privilege_wrapper()
    if wrapper is None:
        return False, "no privilege helper (pkexec) available"
    if not status.commands:
        return False, "no command for this backend"
    last_msg = "opened"
    for argv in status.commands:
        try:
            proc = subprocess.run(
                wrapper + argv, capture_output=True, text=True,
            )
        except (FileNotFoundError, OSError) as exc:
            return False, str(exc)
        ok, msg = interpret_result(
            status.backend, proc.returncode,
            (proc.stdout or "") + (proc.stderr or ""),
        )
        if not ok:
            return False, msg
        last_msg = msg
    return True, last_msg


def render_firewall_block(status: FirewallStatus) -> str:
    """Stdout advisory block for the headless runner (a detected backend)."""
    return "\n".join([
        "",
        "=== ait applink — firewall ===",
        f"⚠ Firewall ({status.backend}) is active. If your phone can't "
        f"connect, open port {status.port} for {status.cidr}:",
        f"    {status.display}",
        "(LAN-scoped; run it yourself, or press 'f' in the TUI to open it "
        "with one consent.)",
    ])
