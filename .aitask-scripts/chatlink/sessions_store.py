"""Persistent chatlink session records (t1120_3).

One JSON file per gateway session under
``aitasks/metadata/chatlink_sessions/sessions/<session_id>.json`` — the
gateway-side companion of the relay spool. **The relay spool is the source of
truth for interaction outcomes** (contract 4/6: pending = question present ∧
answer absent); the record's ``interaction_outcomes`` map is derived
bookkeeping, healed FROM the spool by startup reconciliation. Everything else
here (initiator, thread ref, state) is gateway-owned truth the spool does not
carry.

All writes are atomic (``*.tmp`` + ``os.replace``; readers skip ``*.tmp`` —
the applink ``sessions.py`` pattern) and happen only from the daemon's single
event loop (loop-only mutation — the binding async invariant of p1120_3).

Chat-import-free by design (like ``config``): platform handles are stored as
plain dicts — the thread ``ConversationRef.to_dict()`` (the reconnect token)
and message refs as ``{"conversation": <ref dict>, "message_id": str}`` —
so this module stays importable without the chat tier; the daemon
reconstructs typed refs at the adapter boundary.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .relay import ValidationError

#: The session state machine (pinned in p1120_3). ``spawning`` is written
#: BEFORE launch, so a crash mid-intake leaves a record startup
#: reconciliation fail-closes (no live agent ⇒ ``failed``, never resumed).
STATES = ("spawning", "asking", "working", "awaiting_payload", "done", "failed")
TERMINAL_STATES = frozenset({"done", "failed"})

SESSIONS_SUBDIR = "sessions"


def conversation_key(ref_dict: dict) -> str:
    """Canonical string key for a serialized ``ConversationRef`` dict.

    Used to index ``last_seen`` cursors; mirrors ``ConversationRef``
    equality (provider/workspace/conversation/thread, metadata ignored).
    """
    return "|".join(
        str(ref_dict.get(k) or "")
        for k in ("provider", "workspace_id", "conversation_id", "thread_id")
    )


def message_ref_dict(conversation: dict, message_id: str) -> dict:
    """The pinned serialized-``MessageRef`` shape (chat-import-free)."""
    return {"conversation": dict(conversation), "message_id": message_id}


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


@dataclass
class SessionRecord:
    """One gateway session's persisted state (see module docstring)."""

    session_id: str
    initiator_id: str
    state: str
    #: ``ConversationRef.to_dict()`` of the session thread — the reconnect
    #: token (``None`` only transiently; a loaded record must carry it).
    thread: dict | None = None
    #: Serialized ``MessageRef`` of the originating bug-report message.
    bug_report_message: dict | None = None
    #: ``conversation_key(ref)`` → serialized ``MessageRef`` — the
    #: ``fetch_history(after=)`` cursor per watched conversation.
    last_seen: dict = field(default_factory=dict)
    #: str(seq) → answer dict (JSON keys are strings) — DERIVED bookkeeping;
    #: the spool answer file is the durable outcome (healed at startup).
    interaction_outcomes: dict = field(default_factory=dict)
    #: str(seq) → serialized ``MessageRef`` of the posted question message —
    #: what component-disabling edits and re-prompts target. Best-effort
    #: bookkeeping (a crash between post and save just loses the disable
    #: affordance, never correctness).
    question_messages: dict = field(default_factory=dict)
    #: Current status reaction on the bug-report message (pinned vocabulary
    #: ⏳/❓/✅/❌; ``""`` = none yet). Best-effort bookkeeping — lets the
    #: next transition remove the previous emoji before adding its own.
    status_reaction: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def validate(self) -> None:
        _require(isinstance(self.session_id, str) and bool(self.session_id),
                 "session_id must be a non-empty string")
        _require(isinstance(self.initiator_id, str) and bool(self.initiator_id),
                 "initiator_id must be a non-empty string")
        _require(self.state in STATES, f"unknown state {self.state!r}")
        _require(self.thread is None or isinstance(self.thread, dict),
                 "thread must be a dict or None")
        _require(self.bug_report_message is None
                 or isinstance(self.bug_report_message, dict),
                 "bug_report_message must be a dict or None")
        _require(isinstance(self.last_seen, dict), "last_seen must be a dict")
        _require(isinstance(self.interaction_outcomes, dict),
                 "interaction_outcomes must be a dict")
        _require(isinstance(self.question_messages, dict),
                 "question_messages must be a dict")
        _require(isinstance(self.status_reaction, str),
                 "status_reaction must be a string")
        _require(isinstance(self.created_at, (int, float)),
                 "created_at must be a number")
        _require(isinstance(self.updated_at, (int, float)),
                 "updated_at must be a number")

    def set_outcome(self, seq: int, outcome: dict) -> None:
        """Record a derived interaction outcome (idempotent per seq)."""
        self.interaction_outcomes[str(int(seq))] = dict(outcome)

    def has_outcome(self, seq: int) -> bool:
        return str(int(seq)) in self.interaction_outcomes

    def set_last_seen(self, conversation: dict, message_id: str) -> None:
        """Advance the history cursor for one conversation."""
        self.last_seen[conversation_key(conversation)] = message_ref_dict(
            conversation, message_id)

    def to_dict(self) -> dict:
        self.validate()
        return {
            "session_id": self.session_id,
            "initiator_id": self.initiator_id,
            "state": self.state,
            "thread": self.thread,
            "bug_report_message": self.bug_report_message,
            "last_seen": self.last_seen,
            "interaction_outcomes": self.interaction_outcomes,
            "question_messages": self.question_messages,
            "status_reaction": self.status_reaction,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionRecord":
        _require(isinstance(d, dict), "record must be a dict")
        try:
            rec = cls(
                session_id=d["session_id"],
                initiator_id=d["initiator_id"],
                state=d["state"],
                thread=d.get("thread"),
                bug_report_message=d.get("bug_report_message"),
                last_seen=dict(d.get("last_seen", {})),
                interaction_outcomes=dict(d.get("interaction_outcomes", {})),
                question_messages=dict(d.get("question_messages", {})),
                status_reaction=d.get("status_reaction", ""),
                created_at=d.get("created_at", 0.0),
                updated_at=d.get("updated_at", 0.0),
            )
        except (KeyError, TypeError) as exc:
            raise ValidationError(f"malformed session record: {exc}") from exc
        rec.validate()
        return rec


class SessionsStore:
    """Directory of session-record JSON files (atomic writes, 0700 dir).

    ``clock`` is the injected time source (the deterministic test seam);
    it stamps ``created_at``/``updated_at``.
    """

    def __init__(self, root: str | Path, clock=time.time):
        self.root = Path(root)
        self._clock = clock

    # -- paths ---------------------------------------------------------- #

    def record_path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.json"

    def _ensure_dir(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    # -- creation / persistence ----------------------------------------- #

    def new_record(
        self,
        session_id: str,
        initiator_id: str,
        *,
        thread: dict | None = None,
        bug_report_message: dict | None = None,
    ) -> SessionRecord:
        """Build (NOT persist) a fresh ``spawning`` record, clock-stamped."""
        now = float(self._clock())
        return SessionRecord(
            session_id=session_id,
            initiator_id=initiator_id,
            state="spawning",
            thread=thread,
            bug_report_message=bug_report_message,
            created_at=now,
            updated_at=now,
        )

    def save(self, record: SessionRecord) -> None:
        """Atomic persist (tmp + replace; 0600 before publish)."""
        record.updated_at = float(self._clock())
        payload = record.to_dict()
        self._ensure_dir()
        path = self.record_path(record.session_id)
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        os.replace(tmp, path)

    # -- reads ----------------------------------------------------------- #

    def load(self, session_id: str) -> SessionRecord | None:
        """Load one record; missing/unreadable/malformed ⇒ ``None``
        (fail-closed — a corrupt record is a half-created session)."""
        try:
            raw = self.record_path(session_id).read_text(encoding="utf-8")
            return SessionRecord.from_dict(json.loads(raw))
        except (OSError, ValueError, ValidationError):
            return None

    def list_ids(self) -> list[str]:
        """All session ids with a record file (ignores ``*.tmp`` and the
        gateway-level ``watch_cursors.json``), sorted. The TUI roots its
        store at the sessions dir itself, where the wizard's resumable
        draft (``wizard_draft.DRAFT_FILENAME``) also lives — that file is
        not a session record."""
        if not self.root.is_dir():
            return []
        return sorted(
            p.stem for p in self.root.iterdir()
            if p.suffix == ".json" and p.is_file()
            and p.name != "watch_cursors.json"
            and p.name != "wizard_draft.json"
        )

    def list_records(self) -> tuple[list[SessionRecord], list[str]]:
        """``(records, corrupt_ids)`` — corrupt = present but unloadable.

        Corrupt ids are the fail-closed half-created set: reconciliation
        must mark them failed, never resume them.
        """
        records: list[SessionRecord] = []
        corrupt: list[str] = []
        for sid in self.list_ids():
            rec = self.load(sid)
            if rec is None:
                corrupt.append(sid)
            else:
                records.append(rec)
        return records, corrupt

    # -- gateway-level watch cursors (intake-channel history recovery) --- #
    #
    # The intake channel is watched by the daemon, not by any one session,
    # so its ``fetch_history(after=)`` cursor lives in a single
    # ``watch_cursors.json`` beside the records: conversation_key →
    # serialized MessageRef. Atomic like everything else here.

    def _cursors_path(self) -> Path:
        return self.root / "watch_cursors.json"

    def load_watch_cursors(self) -> dict:
        """conversation_key → serialized ``MessageRef`` (missing ⇒ ``{}``)."""
        try:
            raw = json.loads(self._cursors_path().read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_watch_cursor(self, conversation: dict, message_id: str) -> None:
        cursors = self.load_watch_cursors()
        cursors[conversation_key(conversation)] = message_ref_dict(
            conversation, message_id)
        self._ensure_dir()
        path = self._cursors_path()
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(cursors, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    # -- ceiling queries (intake bounds derive from persisted state) ----- #

    def count_nonterminal(self) -> int:
        """Live-session bound for ``max_concurrent_sandboxes``. Corrupt
        records count as occupied (fail-closed) until reconciled."""
        records, corrupt = self.list_records()
        return sum(1 for r in records if not r.is_terminal) + len(corrupt)

    def count_recent_by_initiator(self, initiator_id: str, window_s: float) -> int:
        """Sessions this initiator created within the last ``window_s``
        seconds — the restart-proof per-user rate-ceiling input."""
        now = float(self._clock())
        records, _corrupt = self.list_records()
        return sum(
            1 for r in records
            if r.initiator_id == initiator_id
            and (now - r.created_at) <= window_s
        )
