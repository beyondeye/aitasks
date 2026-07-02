"""WebSocket transport for the ait applink JSON control plane (t822_7).

Wraps the pure :class:`router.FrameRouter` in a ``wss://`` WebSocket server
(``websockets`` + a self-signed TLS context) and owns the per-connection state
machine (Discovering → Pairing → Connected → Suspended → Disconnected,
``aidocs/applink/protocol.md`` §Connection state machine). Verb execution is
delegated to ``monitor_core`` via the router; this module only moves frames and
manages connection lifecycle.

The binary snapshot/data plane is NOT here — it is the next sibling (t822_8).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_APPLINK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _APPLINK_DIR.parent
for _p in (str(_APPLINK_DIR), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from monitor.monitor_core import (  # noqa: E402
    TmuxMonitor, TaskInfoCache, load_monitor_config,
)
from router import (  # noqa: E402
    FrameRouter, ConnState, error_frame,
    ERR_BAD_PAYLOAD, STATE_DISCOVERING, STATE_SUSPENDED,
)
from pusher import PushScheduler  # noqa: E402
import paths  # noqa: E402
import audit  # noqa: E402

DEFAULT_HOST = "0.0.0.0"   # accept from the LAN; the QR carries the routable IP
DEFAULT_SESSION = "aitasks"
DEFAULT_PORT = 8765

# DoS / abuse ceilings (t985). The control plane is a small LAN listener: frames
# are tiny, a handful of devices pair, and a single host should never be able to
# starve the others. Time-based per-IP request throttling is a documented
# residual (follow-up applink_request_rate_limit); these bound the obvious cases.
MAX_CONNECTIONS = 64        # global concurrent-socket ceiling
MAX_PER_IP = 8              # per-source-IP concurrent ceiling
MAX_FRAME_BYTES = 64 * 1024  # max inbound WebSocket frame (control frames are tiny)
MAX_PREAUTH_FRAMES = 16     # frames allowed before a successful pair/resume
PREAUTH_TIMEOUT = 15.0      # seconds an unauthenticated socket may live
OPEN_TIMEOUT = 10.0         # TLS/WS opening-handshake deadline (slow-loris)
# v1 default permission profile assigned to a freshly paired device. The single
# source of truth for this default across the package (the TUI runtime, the
# server constructor, and the headless runner all reference it).
DEFAULT_PAIR_PROFILE = "monitor_control"

# History-RPC scrollback capture ceiling (t1092). Applink-only; decoupled from the
# monitor's live `capture_lines`. The default coincides with tmux's own default
# server `history-limit` (~2000). The config value is clamped to a sane range at
# load (a runtime bound on the per-pull tmux capture, not just a comment).
DEFAULT_HISTORY_CAPTURE_LINES = 2000
HARD_MAX_HISTORY_CAPTURE_LINES = 10000


def load_applink_config(project_root) -> dict:
    """Load applink-specific config from project_config.yaml's ``tmux.applink``
    section. Fault-tolerant: a missing file / missing key / non-dict / non-int /
    out-of-range value falls back to the default, never raises. The
    ``history_capture_lines`` value is clamped to ``[1, HARD_MAX]``.
    """
    lines = DEFAULT_HISTORY_CAPTURE_LINES
    try:
        import yaml
        from pathlib import Path
        cfg = Path(project_root) / "aitasks" / "metadata" / "project_config.yaml"
        data = yaml.safe_load(cfg.read_text()) or {}
        tmux = data.get("tmux") or {}
        applink = tmux.get("applink") or {}
        raw = applink.get("history_capture_lines")
        if raw is not None:
            val = int(raw)                 # non-int (str/list) raises → default below
            if val >= 1:                   # sub-1 is nonsensical → keep the default
                lines = min(val, HARD_MAX_HISTORY_CAPTURE_LINES)
    except Exception:
        pass  # any malformed config → safe default
    return {"history_capture_lines": lines}


class AppLinkServer:
    """Owns the WebSocket listener, the TmuxMonitor, and the frame router."""

    def __init__(
        self,
        *,
        session_table,
        profile_gate,
        ssl_context,
        host: str = DEFAULT_HOST,
        port: int,
        pair_profile: str = DEFAULT_PAIR_PROFILE,
        on_change=None,
    ) -> None:
        self._host = host
        self._port = port
        self._ssl = ssl_context
        self._on_change = on_change
        self._ws_server = None
        self._conns: set[ConnState] = set()
        self._live: dict[ConnState, object] = {}   # conn -> live websocket
        self._pushers: dict[ConnState, PushScheduler] = {}  # conn -> data-plane loop
        self._conns_by_ip: dict[str, int] = {}     # per-source-IP concurrent count
        self._sessions = session_table
        self.error: str | None = None
        # Security audit logger, configured once here (so both the TUI and
        # headless startup paths inherit it) and threaded into the router.
        self._audit = audit.get_logger(paths.sessions_dir())

        project_root = paths.project_root()
        config = load_monitor_config(project_root)
        # Applink-only history scrollback ceiling (t1092), clamped at load.
        self._history_capture_lines = load_applink_config(
            project_root)["history_capture_lines"]
        self._monitor = TmuxMonitor(
            session=DEFAULT_SESSION,
            multi_session=True,
            capture_lines=config["capture_lines"],
            idle_threshold=config["idle_threshold"],
            agent_prefixes=config["agent_prefixes"],
            tui_names=config["tui_names"],
            compare_mode_default=config["compare_mode_default"],
        )
        self._task_cache = TaskInfoCache(project_root)
        self._router = FrameRouter(
            session_table, profile_gate, self._monitor,
            pair_profile=pair_profile, task_resolver=self._task_cache,
            audit=self._audit,
        )

    # -- Lifecycle -------------------------------------------------------------

    async def start(self) -> None:
        """Start the tmux control client and the WebSocket listener."""
        import websockets  # imported lazily so the TUI smoke path needs no dep

        if self._ssl is None:
            # wss:// is the protocol baseline; refuse to fall back to plaintext.
            self.error = "TLS certificate unavailable (is openssl installed?)"
            self._notify()
            return
        try:
            await self._monitor.start_control_client()
        except Exception:
            # Subprocess fallback still works; control client is an optimization.
            pass
        try:
            self._ws_server = await websockets.serve(
                self._handle, self._host, self._port, ssl=self._ssl,
                max_size=MAX_FRAME_BYTES, open_timeout=OPEN_TIMEOUT,
            )
        except Exception as exc:
            self.error = f"listener failed: {exc}"
        self._notify()

    async def stop(self) -> None:
        if self._ws_server is not None:
            self._ws_server.close()
            try:
                await self._ws_server.wait_closed()
            except Exception:
                pass
            self._ws_server = None
        try:
            await self._monitor.close_control_client()
        except Exception:
            pass

    def set_pair_profile(self, profile: str) -> None:
        self._router.set_pair_profile(profile)

    # -- Connection handler ----------------------------------------------------

    async def _handle(self, ws) -> None:
        ip = self._peer_ip(ws)
        # Admission control (t985): global + per-IP concurrent-connection
        # ceilings, enforced BEFORE the connection is registered so a flood
        # cannot grow the bookkeeping sets. Per-IP stops one LAN host from
        # starving the legitimate paired phone of the global pool.
        if len(self._conns) >= MAX_CONNECTIONS:
            self._audit.warning("CONN_REJECTED reason=global_cap ip=%s", ip)
            await ws.close()
            return
        if self._conns_by_ip.get(ip, 0) >= MAX_PER_IP:
            self._audit.warning("CONN_REJECTED reason=per_ip_cap ip=%s", ip)
            await ws.close()
            return

        conn = ConnState()
        self._conns.add(conn)
        self._live[conn] = ws
        self._conns_by_ip[ip] = self._conns_by_ip.get(ip, 0) + 1
        self._audit.info("CONN_ACCEPT ip=%s", ip)
        # Close a socket that never authenticates within PREAUTH_TIMEOUT — bounds
        # the "open a socket, send nothing" slow-loris the frame budget misses.
        watchdog = asyncio.ensure_future(self._preauth_watchdog(conn, ws))
        preauth_frames = 0
        self._notify()
        try:
            async for raw in ws:
                # Pre-auth frame budget: cap frames sent before a session binds,
                # throttling an unauthenticated malformed-frame flood.
                if conn.session is None:
                    preauth_frames += 1
                    if preauth_frames > MAX_PREAUTH_FRAMES:
                        self._audit.warning("CONN_DROP reason=preauth_flood ip=%s", ip)
                        await ws.close()
                        break
                reply = self._route_raw(raw, conn)
                if conn.bearer is not None:
                    self._sessions.touch(conn.bearer)
                if reply is not None:
                    await ws.send(json.dumps(reply))
                # A live subscription means the data plane is active: start (once)
                # a per-connection push loop and wake it so subscribe /
                # request_keyframe flush their forced keyframes immediately.
                if conn.subscription is not None and conn.subscription.panes:
                    self._ensure_pusher(conn, ws).wake()
                if conn.close_requested:
                    await ws.close()
                    break
        except Exception:
            # Connection-closed and decode errors: just drop the connection.
            pass
        finally:
            watchdog.cancel()
            pusher = self._pushers.pop(conn, None)
            if pusher is not None:
                await pusher.stop()
            self._conns.discard(conn)
            self._live.pop(conn, None)
            remaining = self._conns_by_ip.get(ip, 0) - 1
            if remaining <= 0:
                self._conns_by_ip.pop(ip, None)
            else:
                self._conns_by_ip[ip] = remaining
            # A socket that drops while still holding a valid bearer is
            # Suspended (resumable), not gone — the bearer survives.
            if conn.session is not None and not conn.close_requested:
                self._suspend(conn)
            self._audit.info(
                "CONN_CLOSE ip=%s authed=%s", ip, conn.session is not None,
            )
            self._notify()

    @staticmethod
    def _peer_ip(ws) -> str:
        """Best-effort source IP of a websocket for audit + per-IP accounting."""
        addr = getattr(ws, "remote_address", None)
        if isinstance(addr, (tuple, list)) and addr:
            return str(addr[0])
        return "?"

    async def _preauth_watchdog(self, conn: ConnState, ws) -> None:
        """Close *conn* if it has not authenticated within ``PREAUTH_TIMEOUT``.

        Cancelled in ``_handle``'s ``finally`` once the connection ends; if the
        connection authenticated, the post-sleep check no-ops.
        """
        try:
            await asyncio.sleep(PREAUTH_TIMEOUT)
        except asyncio.CancelledError:
            return
        if conn.session is None and not conn.close_requested:
            self._audit.warning("CONN_DROP reason=preauth_timeout ip=%s", self._peer_ip(ws))
            try:
                await ws.close()
            except Exception:
                pass

    def _ensure_pusher(self, conn: ConnState, ws) -> PushScheduler:
        """Return the connection's PushScheduler, starting it on first use."""
        pusher = self._pushers.get(conn)
        if pusher is None:
            pusher = PushScheduler(
                conn, ws, self._monitor, audit=self._audit,
                history_capture_lines=getattr(
                    self, "_history_capture_lines", DEFAULT_HISTORY_CAPTURE_LINES),
                task_resolver=getattr(self, "_task_cache", None),
            )
            self._pushers[conn] = pusher
            pusher.start()
        return pusher

    def _route_raw(self, raw, conn: ConnState):
        try:
            env = json.loads(raw)
        except (ValueError, TypeError, RecursionError):
            # Robust single decode sink (t1007). RecursionError is defense-in-depth:
            # a JSON nested deep enough to recurse needs ~200 KB, which the transport
            # `max_size` (64 KB) already rejects, and a shallower nested-but-decoded
            # value is caught by FrameRouter.handle's isinstance(env, dict) guard — so
            # this only matters if the cap is ever bypassed/raised. Either way the
            # decode failure returns BAD_PAYLOAD instead of escaping to _handle's
            # bare connection drop.
            return error_frame(None, None, ERR_BAD_PAYLOAD, "frame is not valid JSON")
        return self._router.handle(env, conn)

    def _suspend(self, conn: ConnState) -> None:
        try:
            self._sessions.set_state(conn.bearer, STATE_SUSPENDED)
        except Exception:
            pass

    # -- Introspection (for the TUI status display) ----------------------------

    def connection_state(self) -> str:
        if self.error:
            return "Disconnected"
        live = [c for c in self._conns if c.session is not None]
        if live:
            return "Connected"
        if self._conns:
            return "Pairing"
        return STATE_DISCOVERING

    def connected_devices(self) -> list[str]:
        return [
            c.session.device_name or "(unnamed device)"
            for c in self._conns
            if c.session is not None
        ]

    def active_sessions(self):
        """All known bearer sessions (Connected + Suspended), for the Devices screen."""
        return self._sessions.active_sessions()

    async def revoke_session(self, bearer: str) -> bool:
        """Revoke a bearer and close any live socket holding it.

        The device's bearer is invalidated immediately; an attached socket is
        closed now (rather than waiting for its next frame to fail auth).
        """
        revoked = self._sessions.revoke(bearer)
        for conn, ws in list(self._live.items()):
            if conn.session is not None and conn.session.bearer == bearer:
                conn.close_requested = True
                try:
                    await ws.close()
                except Exception:
                    pass
        self._notify()
        return revoked

    def _notify(self) -> None:
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                pass
