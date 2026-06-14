"""Pairing-token and bearer session table for the ait applink server (t822_7).

Single-use pairing tokens (in-memory, TTL'd) are exchanged for long-lived
bearer tokens per ``aidocs/applink/protocol.md`` §Pairing flow. Active bearers
are persisted to ``aitasks/metadata/applink_sessions/sessions.json``
(gitignored, per-PC) so a paired device survives a TUI restart (Suspended →
resume). Pairing tokens themselves are **never** persisted — they live only in
memory and expire.

Stable-connection-ID invariant (from t822_2): regenerating the pairing token
only rotates the unused token; it never invalidates already-issued bearers.
Revoking is the separate, explicit operation (the TUI ``r`` keybinding revokes).
"""
from __future__ import annotations

import json
import secrets
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# Reuse the token generator that documents the stable-connection-ID invariant.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pairing import generate_token  # noqa: E402

DEFAULT_TOKEN_TTL = 300.0            # 5 min (protocol.md §Pairing flow step 1)
DEFAULT_BEARER_TTL = 7 * 24 * 3600.0  # bearers are long-lived
SESSIONS_FILENAME = "sessions.json"

# Connection-state-machine labels (protocol.md §Connection state machine).
STATE_CONNECTED = "Connected"
STATE_SUSPENDED = "Suspended"
STATE_DISCONNECTED = "Disconnected"


@dataclass
class Session:
    """One paired device's bearer session.

    ``location`` is an optional coarse locality string the phone may include in
    its ``pair`` payload (additive — older clients omit it); the server never
    derives it. ``last_seen`` is updated each time a frame arrives on the
    bearer, for the Devices screen.
    """
    bearer: str
    profile: str
    device_name: str = ""
    platform: str = ""
    location: str = ""
    created_at: float = 0.0
    expires_at: float = 0.0
    last_seen: float = 0.0
    state: str = STATE_CONNECTED


class SessionTable:
    """Owns pairing tokens (ephemeral) and bearer sessions (persisted)."""

    def __init__(
        self,
        sessions_dir: Path,
        *,
        token_ttl: float = DEFAULT_TOKEN_TTL,
        bearer_ttl: float = DEFAULT_BEARER_TTL,
        clock=time.time,
        persist: bool = True,
    ) -> None:
        self._dir = sessions_dir
        self._token_ttl = token_ttl
        self._bearer_ttl = bearer_ttl
        self._clock = clock
        self._persist = persist
        self._current_token: str | None = None
        self._token_issued_at: float = 0.0
        self._bearers: dict[str, Session] = {}
        self._load()

    # -- Pairing tokens (in-memory, single-use) --------------------------------

    def mint_pairing_token(self) -> str:
        """Rotate to a fresh pairing token, invalidating the previous one.

        Returns the new token (to embed in the QR). The old token becomes
        invalid immediately — matching the TUI "regenerate" semantics.
        """
        self._current_token = generate_token()
        self._token_issued_at = self._clock()
        return self._current_token

    def current_pairing_token(self) -> str | None:
        return self._current_token

    def validate_and_consume_token(self, token: str) -> bool:
        """Return True iff *token* is the live, unexpired pairing token.

        Single-use: a successful match clears the current token so a replay
        fails even before the next regenerate (protocol.md: tokens are
        single-use; once consumed, ``T`` is invalidated).
        """
        if not token or token != self._current_token:
            return False
        if self._clock() - self._token_issued_at > self._token_ttl:
            self._current_token = None
            return False
        self._current_token = None
        return True

    # -- Bearer sessions (persisted) -------------------------------------------

    def issue_bearer(
        self, profile: str, *,
        device_name: str = "", platform: str = "", location: str = "",
    ) -> Session:
        now = self._clock()
        session = Session(
            bearer=secrets.token_urlsafe(32),
            profile=profile,
            device_name=device_name,
            platform=platform,
            location=location,
            created_at=now,
            expires_at=now + self._bearer_ttl,
            last_seen=now,
            state=STATE_CONNECTED,
        )
        self._bearers[session.bearer] = session
        self._save()
        return session

    def touch(self, bearer: str) -> None:
        """Record activity on a bearer (updates last_seen in memory).

        Not persisted on its own — kept cheap so per-frame calls don't churn
        the disk; the value rides along on the next state-changing ``_save``.
        """
        session = self._bearers.get(bearer)
        if session is not None:
            session.last_seen = self._clock()

    def lookup(self, bearer: str | None) -> Session | None:
        """Return the live session for *bearer*, or None if absent/expired.

        An expired bearer is reaped (and persisted) on lookup.
        """
        if not bearer:
            return None
        session = self._bearers.get(bearer)
        if session is None:
            return None
        if self._clock() > session.expires_at:
            del self._bearers[bearer]
            self._save()
            return None
        return session

    def set_state(self, bearer: str, state: str) -> None:
        session = self._bearers.get(bearer)
        if session is not None and session.state != state:
            session.state = state
            self._save()

    def revoke(self, bearer: str) -> bool:
        if bearer in self._bearers:
            del self._bearers[bearer]
            self._save()
            return True
        return False

    def active_sessions(self) -> list[Session]:
        return list(self._bearers.values())

    # -- Persistence -----------------------------------------------------------

    def _path(self) -> Path:
        return self._dir / SESSIONS_FILENAME

    def _load(self) -> None:
        if not self._persist:
            return
        path = self._path()
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return
        for raw in data.get("bearers", []):
            try:
                session = Session(**raw)
            except TypeError:
                continue
            # Drop already-expired bearers at load time.
            if self._clock() <= session.expires_at:
                # A device reloaded from disk has no live socket — mark Suspended.
                session.state = STATE_SUSPENDED
                self._bearers[session.bearer] = session

    def _save(self) -> None:
        if not self._persist:
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = {"bearers": [asdict(s) for s in self._bearers.values()]}
        tmp = self._path().with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2))
            tmp.replace(self._path())
        except OSError:
            pass
