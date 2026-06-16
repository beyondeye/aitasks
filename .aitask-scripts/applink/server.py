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

DEFAULT_HOST = "0.0.0.0"   # accept from the LAN; the QR carries the routable IP
DEFAULT_SESSION = "aitasks"
DEFAULT_PORT = 8765
# v1 default permission profile assigned to a freshly paired device. The single
# source of truth for this default across the package (the TUI runtime, the
# server constructor, and the headless runner all reference it).
DEFAULT_PAIR_PROFILE = "monitor_control"


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
        self._sessions = session_table
        self.error: str | None = None

        project_root = paths.project_root()
        config = load_monitor_config(project_root)
        self._monitor = TmuxMonitor(
            session=DEFAULT_SESSION,
            multi_session=True,
            capture_lines=config["capture_lines"],
            idle_threshold=config["idle_threshold"],
            agent_prefixes=config["agent_prefixes"],
            tui_names=config["tui_names"],
            compare_mode_default=config["compare_mode_default"],
        )
        task_cache = TaskInfoCache(project_root)
        self._router = FrameRouter(
            session_table, profile_gate, self._monitor,
            pair_profile=pair_profile, task_resolver=task_cache,
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
        conn = ConnState()
        self._conns.add(conn)
        self._live[conn] = ws
        self._notify()
        try:
            async for raw in ws:
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
            pusher = self._pushers.pop(conn, None)
            if pusher is not None:
                await pusher.stop()
            self._conns.discard(conn)
            self._live.pop(conn, None)
            # A socket that drops while still holding a valid bearer is
            # Suspended (resumable), not gone — the bearer survives.
            if conn.session is not None and not conn.close_requested:
                self._suspend(conn)
            self._notify()

    def _ensure_pusher(self, conn: ConnState, ws) -> PushScheduler:
        """Return the connection's PushScheduler, starting it on first use."""
        pusher = self._pushers.get(conn)
        if pusher is None:
            pusher = PushScheduler(conn, ws, self._monitor)
            self._pushers[conn] = pusher
            pusher.start()
        return pusher

    def _route_raw(self, raw, conn: ConnState):
        try:
            env = json.loads(raw)
        except (ValueError, TypeError):
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
