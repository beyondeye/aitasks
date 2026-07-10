"""Cloudflare Quick Tunnel supervisor for the ait applink server (t1061_3).

Spawns and supervises a ``cloudflared`` quick tunnel
(``cloudflared tunnel --url https://localhost:<port> --no-tls-verify``) so the
pairing QR can advertise a public ``*.trycloudflare.com`` endpoint alongside
the LAN one — turnkey Phase-2 remote reach (parent plan p1061, §A3).

Origin-TLS trust note (empirically verified in p1061_3): the applink origin is
``wss://`` with a self-signed, no-SAN cert, which cloudflared's default origin
verification rejects. ``--no-tls-verify`` skips that verification for the
**loopback-only** hop cloudflared → ``https://localhost:<port>`` — an accepted,
bounded trust step (the public hop phone → Cloudflare edge stays CA-verified,
and pairing/bearer auth still gates every frame).

Textual-free by design: shared by the TUI (``applink_app.py``) and the
headless runner (``headless.py``), whose test asserts no Textual import.
"""
from __future__ import annotations

import asyncio
import contextlib
import re
import shutil

# Supervisor states (simple string machine, mirrored on status surfaces).
STATE_OFF = "off"              # constructed, not started
STATE_STARTING = "starting"    # child spawned, tunnel URL not seen yet
STATE_UP = "up"                # public URL parsed; tunnel serving
STATE_FAILED = "failed"        # binary missing / spawn failed / child died
STATE_STOPPED = "stopped"      # clean shutdown via stop()

# Registered auto-tunnel backends (config value of tmux.applink.auto_tunnel).
TUNNEL_BACKENDS = ("cloudflared",)

# How long emission call sites wait for the URL before degrading to a
# LAN-only pairing block with a fail-visible warning.
URL_WAIT_TIMEOUT = 15.0

# Strict quick-tunnel URL matcher. cloudflared's log lines contain unrelated
# URLs *before* the tunnel banner (terms-of-use www.cloudflare.com link,
# developers.cloudflare.com docs, the local 127.0.0.1:<port>/metrics address),
# so only https://<sub>.trycloudflare.com may match. The negative lookahead
# rejects lookalike suffixes (sub.trycloudflare.com.evil.net) that a plain
# word-boundary would accept.
_URL_RE = re.compile(
    r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com(?![a-zA-Z0-9.-])"
)


def find_cloudflared() -> str | None:
    """Absolute path of the ``cloudflared`` binary, or None when not on PATH."""
    return shutil.which("cloudflared")


def parse_tunnel_url(line: str) -> str | None:
    """Extract the public quick-tunnel URL from one cloudflared log line.

    Returns ``https://<sub>.trycloudflare.com`` or None. Strict by design —
    see ``_URL_RE``.
    """
    m = _URL_RE.search(line)
    return m.group(0) if m else None


class QuickTunnel:
    """Own one ``cloudflared`` quick-tunnel child process.

    Lifecycle mirrors the asyncio supervision patterns already in-repo:
    ``TmuxControlClient.start`` (subprocess + reader task parsing lines) and
    ``PushScheduler`` (start/stop/cancel shape). The owner is
    ``AppLinkServer`` — spawned after the listener binds, stopped with it.

    ``on_change`` fires on every state transition (best-effort, exceptions
    swallowed) so status surfaces can refresh.
    """

    def __init__(self, port: int, *, binary: str | None = None, on_change=None) -> None:
        self._port = port
        self._binary = binary  # None → find_cloudflared() at start()
        self._on_change = on_change
        self._proc: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task | None = None
        self._url_event = asyncio.Event()
        self._stopping = False
        self.state: str = STATE_OFF
        self.url: str | None = None      # https://<x>.trycloudflare.com
        self.detail: str | None = None   # human-readable failure reason

    # -- Introspection ----------------------------------------------------------

    @property
    def hostname(self) -> str | None:
        """Bare tunnel hostname (``<x>.trycloudflare.com``) when up."""
        return self.url.removeprefix("https://") if self.url else None

    def status_line(self) -> str:
        """One human-readable status line, shared by the TUI advisory and the
        headless output so both surfaces agree."""
        if self.state == STATE_UP:
            return f"Tunnel: up — {self.hostname}"
        if self.state == STATE_STARTING:
            return "Tunnel: starting (waiting for public URL)…"
        if self.state == STATE_FAILED:
            return f"Tunnel: failed — {self.detail or 'unknown error'}"
        if self.state == STATE_STOPPED:
            return "Tunnel: stopped"
        return "Tunnel: off"

    # -- Lifecycle --------------------------------------------------------------

    def _argv(self, binary: str) -> list[str]:
        """The exact child argv (a method so tests can assert it without
        spawning — TmuxControlClient._attach_argv pattern)."""
        return [
            binary, "tunnel",
            "--url", f"https://localhost:{self._port}",
            "--no-tls-verify",
        ]

    async def start(self) -> bool:
        """Spawn cloudflared and start the URL-scanning reader task.

        Returns False (state ``failed``, ``detail`` set) when the binary is
        missing or the spawn fails — callers degrade to LAN-only emission
        with a fail-visible warning; never raise, never block serving.
        """
        if self._proc is not None:
            return self.state in (STATE_STARTING, STATE_UP)
        binary = self._binary or find_cloudflared()
        if binary is None:
            self._set(STATE_FAILED, detail="cloudflared not found on PATH")
            return False
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._argv(binary),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                # cloudflared logs (incl. the URL banner) go to stderr; merge
                # so one reader scans everything.
                stderr=asyncio.subprocess.STDOUT,
            )
        except (FileNotFoundError, OSError) as exc:
            self._proc = None
            self._set(STATE_FAILED, detail=f"spawn failed: {exc}")
            return False
        self._set(STATE_STARTING)
        self._reader_task = asyncio.create_task(self._reader_loop())
        return True

    async def _reader_loop(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        try:
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break  # EOF → child exited
                if self.url is None:
                    url = parse_tunnel_url(line_bytes.decode("utf-8", errors="replace"))
                    if url is not None:
                        self.url = url
                        self._set(STATE_UP)
            rc = await proc.wait()
            if not self._stopping:
                # Unexpected death: clear the URL so no emit path keeps
                # advertising a dead public endpoint.
                self.url = None
                self._set(STATE_FAILED, detail=f"cloudflared exited (rc={rc})")
        except asyncio.CancelledError:
            return

    async def wait_url(self, timeout: float = URL_WAIT_TIMEOUT) -> str | None:
        """Wait until the public URL is known (or the tunnel failed / timed
        out). Returns the URL or None — emission call sites use this before
        the first pairing-block emit."""
        if self.url is not None:
            return self.url
        if self.state in (STATE_OFF, STATE_FAILED, STATE_STOPPED):
            return None
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._url_event.wait(), timeout)
        return self.url

    async def stop(self) -> None:
        """Terminate the child (bounded wait, then kill) and join the reader.
        Idempotent; a failure state set before stop() is preserved."""
        self._stopping = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader_task
            self._reader_task = None
        proc, self._proc = self._proc, None
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError, OSError):
                    proc.kill()
                with contextlib.suppress(Exception):
                    await proc.wait()
        self.url = None
        if self.state != STATE_FAILED:
            self._set(STATE_STOPPED)

    def _set(self, state: str, detail: str | None = None) -> None:
        self.state = state
        self.detail = detail
        if state in (STATE_UP, STATE_FAILED, STATE_STOPPED):
            # Wake any wait_url() waiter — on failure it returns None.
            self._url_event.set()
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                pass
