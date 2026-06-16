"""Pure frame router for the ait applink JSON control plane (t822_7).

``FrameRouter.handle(envelope, conn)`` parses one JSON envelope
(``aidocs/applink/protocol.md`` §Message envelope), authenticates it, gates the
verb against the session's permission profile, dispatches the allowed verbs into
``monitor_core``, and returns the ``res``/``err`` reply frame. It is deliberately
free of sockets, TLS, and asyncio so the dispatch logic — pairing, auth,
``PERMISSION_DENIED`` gating, the pull-model confirm round-trip, key translation
— is unit-testable against a stub monitor.

Verb inventory and payload schemas follow the canonical table in
``aidocs/applink/monitor_port_design.md``. The binary data plane
(``snapshot``/``subscribe``/``request_keyframe``) and the workflow verbs
(``pick_next_sibling``/``restart_task``) are recognized but deferred to sibling
tasks — they return ``UNKNOWN_VERB`` here.
"""
from __future__ import annotations

import time

from content import Subscription

PROTOCOL_VERSION = 1

# Error codes (protocol.md §Message envelope error frame).
ERR_AUTH_FAILED = "AUTH_FAILED"
ERR_PERMISSION_DENIED = "PERMISSION_DENIED"
ERR_UNKNOWN_VERB = "UNKNOWN_VERB"
ERR_BAD_PAYLOAD = "BAD_PAYLOAD"
ERR_INTERNAL = "INTERNAL"
# Returned when a known, gated verb's *execution* leg is not yet wired — used by
# the t822_11 modal handshakes whose kill-old-pane + relaunch-agent orchestration
# is deferred until the applink workflow launch policy lands. Additive error code
# per protocol.md §Versioning (clients ignore unknown codes).
ERR_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

# Connection-state labels not already in sessions.py (transport-level).
STATE_DISCOVERING = "Discovering"
STATE_PAIRING = "Pairing"
STATE_CONNECTED = "Connected"
STATE_SUSPENDED = "Suspended"
STATE_DISCONNECTED = "Disconnected"

# Verbs executed by THIS listener (control plane + data-plane control). Each is
# profile-gated.
IMPLEMENTED_COMMAND_VERBS = frozenset({
    "send_enter", "send_keys", "forward_key", "focus", "cycle_compare_mode",
    "kill_pane", "kill_window", "spawn_tui", "task_detail",
    # Data-plane control verbs (t822_8): mutate the per-connection Subscription;
    # the actual binary pushes are driven by server's pusher.PushScheduler.
    "subscribe", "request_keyframe",
    # Workflow modal handshakes (t822_11): the suggest/choose + idle-gated confirm
    # round-trips are served here; their final kill+relaunch execution is deferred
    # (returns NOT_IMPLEMENTED) until the applink launch policy lands.
    "pick_next_sibling", "restart_task",
})

# Destructive / workflow verbs that use the pull-model confirm handshake
# (first call returns details, a re-send with `confirmed:true` executes).
CONFIRM_VERBS = frozenset({"kill_pane", "kill_window", "restart_task"})

# Recognized-but-deferred verbs. `snapshot` is the push-direction read-capability
# token (gated in profiles, never pulled).
DEFERRED_VERBS = frozenset({
    "snapshot",
})

# Session-management verbs (not profile-gated).
SESSION_VERBS = frozenset({"pair", "resume", "bye"})

# The full canonical verb namespace — used by the profile validator to confirm
# every allowed_verbs entry names a real verb (not necessarily one served yet).
KNOWN_VERBS = (
    SESSION_VERBS | IMPLEMENTED_COMMAND_VERBS | DEFERRED_VERBS
)


def _iso8601(epoch: float) -> str:
    """UTC ISO-8601 timestamp (``2026-05-25T18:30:00Z``) for an epoch second."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def error_frame(msg_id, verb, code, message, detail=None):
    """Build an ``err`` envelope. Public so the transport can reply to frames
    that never reach the router (e.g. undecodable JSON)."""
    err = {"code": code, "message": message}
    if detail is not None:
        err["detail"] = detail
    return {"v": PROTOCOL_VERSION, "id": msg_id, "kind": "err", "verb": verb, "payload": err}


def result_frame(msg_id, verb, payload):
    """Build a ``res`` envelope."""
    return {"v": PROTOCOL_VERSION, "id": msg_id, "kind": "res", "verb": verb, "payload": payload}


class ConnState:
    """Per-connection state the router reads and mutates.

    ``close_requested`` is the router's signal to the transport that the socket
    should be closed (after an auth failure or an explicit ``bye``).
    """

    def __init__(self) -> None:
        self.state = STATE_PAIRING
        self.bearer: str | None = None
        self.session = None
        self.close_requested = False
        # Data-plane subscription (None until the first `subscribe`). Mutated by
        # the router; consumed by server's per-connection PushScheduler (t822_8).
        self.subscription: Subscription | None = None

    def bind(self, session) -> None:
        self.bearer = session.bearer
        self.session = session


class FrameRouter:
    def __init__(
        self,
        session_table,
        profile_gate,
        monitor,
        *,
        pair_profile: str = "monitor_control",
        task_resolver=None,
    ) -> None:
        self._sessions = session_table
        self._gate = profile_gate
        self._monitor = monitor
        self._pair_profile = pair_profile
        self._tasks = task_resolver

    def set_pair_profile(self, profile: str) -> None:
        self._pair_profile = profile

    # -- Entry point -----------------------------------------------------------

    def handle(self, env, conn: ConnState):
        if not isinstance(env, dict):
            return self._err(None, None, ERR_BAD_PAYLOAD, "frame is not a JSON object")
        msg_id = env.get("id")
        verb = env.get("verb")
        if env.get("kind") != "req" or not isinstance(verb, str) or not isinstance(msg_id, str):
            return self._err(
                msg_id if isinstance(msg_id, str) else None,
                verb if isinstance(verb, str) else None,
                ERR_BAD_PAYLOAD, "missing or invalid envelope fields (id, kind, verb)",
            )
        payload = env.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return self._err(msg_id, verb, ERR_BAD_PAYLOAD, "payload must be an object")

        # Pairing is the only frame allowed without a bearer.
        if verb == "pair":
            return self._do_pair(msg_id, conn, payload)

        # Everything else requires a valid bearer.
        session = self._sessions.lookup(env.get("auth"))
        if session is None:
            conn.close_requested = True
            return self._err(msg_id, verb, ERR_AUTH_FAILED, "missing or invalid bearer")
        conn.bind(session)

        if verb == "resume":
            self._sessions.set_state(session.bearer, STATE_CONNECTED)
            conn.state = STATE_CONNECTED
            return self._res(msg_id, verb, {"profile": session.profile})
        if verb == "bye":
            self._sessions.revoke(session.bearer)
            conn.state = STATE_DISCONNECTED
            conn.close_requested = True
            return self._res(msg_id, verb, {"ok": True})

        if verb in IMPLEMENTED_COMMAND_VERBS:
            if not self._gate.is_allowed(session.profile, verb):
                return self._err(
                    msg_id, verb, ERR_PERMISSION_DENIED,
                    f"verb '{verb}' is not permitted for profile '{session.profile}'",
                    detail={"required_profile": self._gate.required_profile(verb)},
                )
            return self._dispatch(msg_id, verb, payload, conn)

        if verb in DEFERRED_VERBS:
            return self._err(
                msg_id, verb, ERR_UNKNOWN_VERB,
                f"verb '{verb}' is not served by the v1 control listener",
                detail={"reason": "deferred"},
            )
        return self._err(msg_id, verb, ERR_UNKNOWN_VERB, f"unknown verb '{verb}'")

    # -- Pairing ---------------------------------------------------------------

    def _do_pair(self, msg_id, conn, payload):
        token = payload.get("token")
        if not isinstance(token, str) or not self._sessions.validate_and_consume_token(token):
            conn.close_requested = True
            return self._err(msg_id, "pair", ERR_AUTH_FAILED, "invalid or expired pairing token")
        device = payload.get("device")
        device_name = ""
        platform = ""
        location = ""
        if isinstance(device, dict):
            device_name = str(device.get("name", ""))
            platform = str(device.get("platform", ""))
            # Optional, additive: a coarse locality string the phone may send.
            location = str(device.get("location", ""))
        session = self._sessions.issue_bearer(
            self._pair_profile,
            device_name=device_name, platform=platform, location=location,
        )
        conn.bind(session)
        conn.state = STATE_CONNECTED
        return self._res(msg_id, "pair", {
            "bearer": session.bearer,
            "profile": session.profile,
            "expires_at": _iso8601(session.expires_at),
        })

    # -- Command dispatch ------------------------------------------------------

    def _dispatch(self, msg_id, verb, payload, conn):
        if verb == "send_enter":
            pane_id = self._req_str(payload, "pane_id")
            if pane_id is None:
                return self._bad_field(msg_id, verb, "pane_id")
            return self._res(msg_id, verb, {"ok": bool(self._monitor.send_enter(pane_id))})

        if verb == "send_keys":
            pane_id = self._req_str(payload, "pane_id")
            keys = payload.get("keys")
            if pane_id is None or not isinstance(keys, str):
                return self._bad_field(msg_id, verb, "pane_id/keys")
            literal = bool(payload.get("literal", False))
            ok = self._monitor.send_keys(pane_id, keys, literal=literal)
            return self._res(msg_id, verb, {"ok": bool(ok)})

        if verb == "forward_key":
            pane_id = self._req_str(payload, "pane_id")
            key = self._req_str(payload, "key")
            if pane_id is None or key is None:
                return self._bad_field(msg_id, verb, "pane_id/key")
            ok = self._monitor.forward_key(pane_id, key)
            return self._res(msg_id, verb, {"ok": bool(ok)})

        if verb == "focus":
            pane_id = self._req_str(payload, "pane_id")
            if pane_id is None:
                return self._bad_field(msg_id, verb, "pane_id")
            prefer = bool(payload.get("prefer_companion", False))
            ok = self._monitor.switch_to_pane(pane_id, prefer_companion=prefer)
            # Raise this pane's data-plane cadence (single focused pane). Read-only
            # clients cannot reach this verb (it is monitor_control+); they raise
            # cadence by subscribing to the pane with a fast cadence instead.
            if conn.subscription is not None:
                conn.subscription.set_focus(pane_id)
            return self._res(msg_id, verb, {"ok": bool(ok)})

        if verb == "subscribe":
            panes = payload.get("panes")
            if not isinstance(panes, list):
                return self._bad_field(msg_id, verb, "panes")
            if conn.subscription is None:
                conn.subscription = Subscription()
            accepted = conn.subscription.apply_subscribe(payload)
            return self._res(msg_id, verb, {"ok": True, "panes": sorted(accepted)})

        if verb == "request_keyframe":
            pane_id = self._req_str(payload, "pane_id")
            if pane_id is None:
                return self._bad_field(msg_id, verb, "pane_id")
            if conn.subscription is not None:
                conn.subscription.request_keyframe(pane_id)
            return self._res(msg_id, verb, {"ok": True})

        if verb == "cycle_compare_mode":
            pane_id = self._req_str(payload, "pane_id")
            if pane_id is None:
                return self._bad_field(msg_id, verb, "pane_id")
            mode, following = self._monitor.cycle_compare_mode(pane_id)
            return self._res(msg_id, verb, {"mode": mode, "following_default": bool(following)})

        if verb == "spawn_tui":
            tui_name = self._req_str(payload, "tui_name")
            if tui_name is None:
                return self._bad_field(msg_id, verb, "tui_name")
            return self._res(msg_id, verb, {"ok": bool(self._monitor.spawn_tui(tui_name))})

        if verb == "kill_pane":
            return self._kill_pane(msg_id, payload)

        if verb == "kill_window":
            return self._kill_window(msg_id, payload)

        if verb == "restart_task":
            return self._restart_task(msg_id, payload)

        if verb == "pick_next_sibling":
            return self._pick_next_sibling(msg_id, payload)

        if verb == "task_detail":
            task_id = self._req_str(payload, "task_id")
            if task_id is None:
                return self._bad_field(msg_id, verb, "task_id")
            return self._task_detail(msg_id, task_id)

        # Should be unreachable (verb membership checked by the caller).
        return self._err(msg_id, verb, ERR_INTERNAL, f"no dispatcher for '{verb}'")

    # -- Modal-dialog handshakes (t822_11) -------------------------------------

    def _two_phase(self, msg_id, verb, payload, *, build_details, execute):
        """Pull-model confirm round-trip shared by kill/restart.

        ``build_details`` returns either a ``dict`` of detail fields for the
        ``confirm_required`` reply, or an ``err`` frame (``kind == "err"``) that
        short-circuits **both** phases (e.g. a ``not_idle`` / ``not_found``
        rejection). The client re-sends the same verb with ``confirmed:true`` to
        run ``execute``; the server never blocks waiting for a reply, so the
        action stays client-initiated and idempotent.
        """
        details = build_details()
        if isinstance(details, dict) and details.get("kind") == "err":
            return details
        if not payload.get("confirmed"):
            reply = {"confirm_required": True}
            reply.update(details)
            return self._res(msg_id, verb, reply)
        return execute()

    def _resolve_pane_task(self, pane_id):
        """Resolve ``(pane, task_id, session_name)`` from a pane id.

        Uses the monitor's cached pane metadata (no live capture) and the task
        resolver. ``session_name`` is threaded into every downstream task-cache
        call so a pane owned by another project/session resolves against the
        right task family (mirrors the desktop's ``snap.pane.session_name``
        plumbing). Returns ``(None, None, "")`` when the pane is unknown.
        """
        pane = None
        get_pane = getattr(self._monitor, "get_pane", None)
        if callable(get_pane):
            pane = get_pane(pane_id)
        if pane is None:
            return None, None, ""
        session_name = getattr(pane, "session_name", "") or ""
        task_id = None
        if self._tasks is not None:
            task_id = self._tasks.get_task_id_for_pane(pane)
        return pane, task_id, session_name

    def _pane_target(self, pane_id):
        """Confirm-dialog target for a pane: ``{pane_id, window_name?, task?}``.

        Degrades to just ``pane_id`` when the pane is not in the monitor cache
        (the design table marks ``window_name``/``task`` optional)."""
        target = {"pane_id": pane_id}
        pane, task_id, _session = self._resolve_pane_task(pane_id)
        if pane is not None:
            window_name = getattr(pane, "window_name", "") or ""
            if window_name:
                target["window_name"] = window_name
        if task_id:
            target["task"] = task_id
        return target

    def _kill_pane(self, msg_id, payload):
        pane_id = self._req_str(payload, "pane_id")
        if pane_id is None:
            return self._bad_field(msg_id, "kill_pane", "pane_id")

        def build_details():
            return {"target": self._pane_target(pane_id)}

        def execute():
            ok, killed_window = self._monitor.kill_agent_pane_smart(pane_id)
            return self._res(msg_id, "kill_pane",
                             {"ok": bool(ok), "killed_window": bool(killed_window)})

        return self._two_phase(msg_id, "kill_pane", payload,
                               build_details=build_details, execute=execute)

    def _kill_window(self, msg_id, payload):
        window_id = self._req_str(payload, "window_id")
        if window_id is None:
            return self._bad_field(msg_id, "kill_window", "window_id")

        def build_details():
            return {"target": {"window_id": window_id}}

        def execute():
            return self._res(msg_id, "kill_window",
                             {"ok": bool(self._monitor.kill_window(window_id))})

        return self._two_phase(msg_id, "kill_window", payload,
                               build_details=build_details, execute=execute)

    def _restart_task(self, msg_id, payload):
        """Idle-gated restart confirm (gate: full). Execution is deferred."""
        pane_id = self._req_str(payload, "pane_id")
        if pane_id is None:
            return self._bad_field(msg_id, "restart_task", "pane_id")

        def build_details():
            snap = self._monitor.capture_pane(pane_id)
            if snap is None:
                return self._err(msg_id, "restart_task", ERR_BAD_PAYLOAD,
                                 f"pane '{pane_id}' not found",
                                 detail={"reason": "not_found"})
            if not getattr(snap, "is_idle", False):
                return self._err(msg_id, "restart_task", ERR_BAD_PAYLOAD,
                                 "pane is not idle", detail={"reason": "not_idle"})
            pane = snap.pane
            session_name = getattr(pane, "session_name", "") or ""
            task_id = None
            if self._tasks is not None:
                task_id = self._tasks.get_task_id_for_pane(pane)
            if not task_id:
                return self._err(msg_id, "restart_task", ERR_BAD_PAYLOAD,
                                 "pane has no resolvable task id",
                                 detail={"reason": "no_task"})
            title, status = "", ""
            if self._tasks is not None:
                self._tasks.invalidate(task_id, session_name)
                info = self._tasks.get_task_info(task_id, session_name)
                if info is not None:
                    title, status = info.title, info.status
            return {
                "task_id": task_id, "title": title, "status": status,
                "idle_seconds": getattr(snap, "idle_seconds", 0),
            }

        def execute():
            _pane, task_id, _session = self._resolve_pane_task(pane_id)
            return self._err(msg_id, "restart_task", ERR_NOT_IMPLEMENTED,
                             "restart execution is deferred (no launch policy yet)",
                             detail={"reason": "deferred", "task_id": task_id})

        return self._two_phase(msg_id, "restart_task", payload,
                               build_details=build_details, execute=execute)

    def _pick_next_sibling(self, msg_id, payload):
        """Suggest/choose sibling round-trip (gate: full). Execution deferred."""
        pane_id = self._req_str(payload, "pane_id")
        if pane_id is None:
            return self._bad_field(msg_id, "pick_next_sibling", "pane_id")
        pane, task_id, session_name = self._resolve_pane_task(pane_id)
        if pane is None:
            return self._err(msg_id, "pick_next_sibling", ERR_BAD_PAYLOAD,
                             f"pane '{pane_id}' not found",
                             detail={"reason": "not_found"})
        if not task_id:
            return self._err(msg_id, "pick_next_sibling", ERR_BAD_PAYLOAD,
                             "pane has no resolvable task id",
                             detail={"reason": "no_task"})

        sibling_id = payload.get("sibling_id")
        if isinstance(sibling_id, str) and sibling_id:
            # Choose phase — the kill+relaunch execution is deferred.
            return self._err(msg_id, "pick_next_sibling", ERR_NOT_IMPLEMENTED,
                             "sibling launch is deferred (no launch policy yet)",
                             detail={"reason": "deferred", "sibling_id": sibling_id})

        if self._tasks is None:
            return self._err(msg_id, "pick_next_sibling", ERR_INTERNAL,
                             "task resolver unavailable")
        # Suggest phase — force-refresh current task info, then suggest + list.
        self._tasks.invalidate(task_id, session_name)
        info = self._tasks.get_task_info(task_id, session_name)
        current_title = info.title if info is not None else ""
        current_status = info.status if info is not None else "Done"
        suggested = self._tasks.find_next_sibling(task_id, session_name)
        ready = self._tasks.find_ready_siblings(task_id, session_name)
        parent_id = self._tasks.get_parent_id(task_id) or task_id
        suggested_payload = None
        if suggested is not None:
            sug_id, sug_title = suggested
            suggested_payload = {"id": sug_id, "title": sug_title}
        ready_payload = [
            {"id": sid, "title": stitle, "blocked_by": list(blocked)}
            for (sid, stitle, blocked) in ready
        ]
        return self._res(msg_id, "pick_next_sibling", {
            "suggested": suggested_payload,
            "current": {"id": task_id, "title": current_title, "status": current_status},
            "parent_id": parent_id,
            "ready_siblings": ready_payload,
        })

    def _task_detail(self, msg_id, task_id):
        if self._tasks is None:
            return self._err(msg_id, "task_detail", ERR_INTERNAL, "task resolver unavailable")
        # Force-refresh, matching the desktop force-refresh on task-detail open.
        self._tasks.invalidate(task_id)
        info = self._tasks.get_task_info(task_id)
        if info is None:
            return self._err(
                msg_id, "task_detail", ERR_BAD_PAYLOAD,
                f"task '{task_id}' not found", detail={"reason": "not_found"},
            )
        return self._res(msg_id, "task_detail", {
            "task_id": info.task_id,
            "task_file": info.task_file,
            "title": info.title,
            "priority": info.priority,
            "effort": info.effort,
            "issue_type": info.issue_type,
            "status": info.status,
            "body": info.body,
            "plan_content": info.plan_content,
        })

    # -- Frame builders --------------------------------------------------------

    @staticmethod
    def _req_str(payload: dict, key: str) -> str | None:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        return None

    def _bad_field(self, msg_id, verb, field):
        return self._err(msg_id, verb, ERR_BAD_PAYLOAD, f"missing or invalid field: {field}")

    _res = staticmethod(result_frame)
    _err = staticmethod(error_frame)
