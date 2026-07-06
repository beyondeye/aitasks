"""relay — spool read/write, schemas, and identity for the Q&A relay.

Normative spec: ``aidocs/chat/qa_relay_protocol.md``. This module is the
single mint point for ``session_id``s and ``custom_id``s and the only code
that touches the relay spool layout.

Contract: **stdlib-only** — no ``chat/`` import, no aitasks framework
import (the agent side of the relay must stay pure; guard-tested by
``tests/test_chatlink_relay.sh``). Atomic writes everywhere: ``*.tmp`` +
``os.replace``; readers ignore ``*.tmp``.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import string
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "ANSWER_STATUSES",
    "Answer",
    "CustomIdError",
    "Option",
    "Question",
    "RelayError",
    "SessionDir",
    "TaskPayload",
    "ValidationError",
    "assign_option_values",
    "build_custom_id",
    "create_session_dir",
    "mint_session_id",
    "parse_custom_id",
]

# --- Protocol constants (aidocs/chat/qa_relay_protocol.md) ---

CUSTOM_ID_PREFIX = "cl1"
CUSTOM_ID_MAX = 100          # platform floor (Discord custom_id limit)
SESSION_ID_MAX = 12
COMPONENT_MAX = 8
SEQ_MAX = 999_999            # ≤ 6 decimal digits
LABEL_MAX = 100              # platform floor (select-option label limit)
MINT_RETRIES = 16

ANSWER_STATUSES = ("answered", "timeout", "cancelled")

# Task-payload limits (contract 7)
PAYLOAD_LEVELS = ("high", "medium", "low")
PAYLOAD_NAME_MAX = 64        # task name slug
PAYLOAD_TITLE_MAX = 120
PAYLOAD_DESCRIPTION_MAX = 64 * 1024   # bytes, UTF-8

_SESSION_ID_RE = re.compile(r"^s[a-z0-9]{1,%d}$" % (SESSION_ID_MAX - 1))
_COMPONENT_RE = re.compile(r"^[a-z0-9_]{1,%d}$" % COMPONENT_MAX)
_OPTION_VALUE_RE = re.compile(r"^[a-z0-9]{1,%d}$" % COMPONENT_MAX)
_NAME_SLUG_RE = re.compile(r"^[a-z0-9_]{1,%d}$" % PAYLOAD_NAME_MAX)
_ISSUE_TYPE_RE = re.compile(r"^[a-z0-9_]{1,64}$")
_LABEL_RE = re.compile(r"^[a-z0-9_-]{1,64}$")

_BASE36 = string.digits + string.ascii_lowercase


class RelayError(Exception):
    """Base error for the relay library."""


class ValidationError(RelayError):
    """A question/answer payload violates the protocol schema."""


class CustomIdError(RelayError):
    """A custom_id violates the encoding or length budget."""


# --- Session identity (contract 1) ---

def _base36(n: int) -> str:
    if n == 0:
        return "0"
    digits = []
    while n:
        n, rem = divmod(n, 36)
        digits.append(_BASE36[rem])
    return "".join(reversed(digits))


def mint_session_id(now: float | None = None) -> str:
    """Mint a session id: ``s<base36-epoch-seconds><2-char random>``.

    Single mint point — validates length/charset at construction.
    """
    epoch = int(time.time() if now is None else now)
    rand = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789")
                   for _ in range(2))
    sid = f"s{_base36(epoch)}{rand}"
    if not _SESSION_ID_RE.match(sid) or len(sid) > SESSION_ID_MAX:
        raise RelayError(f"minted session_id invalid: {sid!r}")
    return sid


def create_session_dir(relay_root: str | Path) -> "SessionDir":
    """Mint a session id and create its spool directory atomically.

    Collision-aware: ``makedirs(exist_ok=False)`` + re-mint on collision
    (bounded) — a collision must never mix two sessions in one directory.
    """
    root = Path(relay_root)
    root.mkdir(parents=True, exist_ok=True)
    for _ in range(MINT_RETRIES):
        sid = mint_session_id()
        path = root / sid
        try:
            os.makedirs(path, exist_ok=False)
        except FileExistsError:
            continue
        return SessionDir(path)
    raise RelayError(
        f"could not mint a unique session dir under {root} "
        f"after {MINT_RETRIES} attempts")


# --- custom_id encoding (contract 4) ---

def build_custom_id(session_id: str, seq: int, component: str) -> str:
    """Build ``cl1:<session_id>:<seq>:<component>`` (reject, never truncate)."""
    if not _SESSION_ID_RE.match(session_id):
        raise CustomIdError(f"invalid session_id: {session_id!r}")
    if not isinstance(seq, int) or isinstance(seq, bool) \
            or seq < 1 or seq > SEQ_MAX:
        raise CustomIdError(f"invalid seq: {seq!r}")
    if not _COMPONENT_RE.match(component):
        raise CustomIdError(f"invalid component tag: {component!r}")
    cid = f"{CUSTOM_ID_PREFIX}:{session_id}:{seq}:{component}"
    if len(cid) > CUSTOM_ID_MAX:
        raise CustomIdError(f"custom_id exceeds {CUSTOM_ID_MAX} chars: {cid!r}")
    return cid


def parse_custom_id(custom_id: str) -> tuple[str, int, str]:
    """Parse a relay custom_id → ``(session_id, seq, component)``."""
    if not isinstance(custom_id, str) or len(custom_id) > CUSTOM_ID_MAX:
        raise CustomIdError(f"custom_id too long or not a string: {custom_id!r}")
    parts = custom_id.split(":")
    if len(parts) != 4 or parts[0] != CUSTOM_ID_PREFIX:
        raise CustomIdError(f"not a relay custom_id: {custom_id!r}")
    _, session_id, seq_s, component = parts
    if not _SESSION_ID_RE.match(session_id):
        raise CustomIdError(f"invalid session_id in custom_id: {custom_id!r}")
    if not seq_s.isdigit() or len(seq_s) > 6:
        raise CustomIdError(f"invalid seq in custom_id: {custom_id!r}")
    seq = int(seq_s)
    if seq < 1:
        raise CustomIdError(f"invalid seq in custom_id: {custom_id!r}")
    if not _COMPONENT_RE.match(component):
        raise CustomIdError(f"invalid component in custom_id: {custom_id!r}")
    return session_id, seq, component


# --- Schemas (contract 3, amended by t1120_1) ---

@dataclass
class Option:
    """One question option. ``value`` is the stable id the answer carries;
    it is auto-assigned by the relay lib (``o<idx>``) — callers pass only
    ``label``/``description``."""

    value: str
    label: str
    description: str = ""

    def validate(self) -> None:
        if not _OPTION_VALUE_RE.match(self.value or ""):
            raise ValidationError(f"invalid option value: {self.value!r}")
        if not isinstance(self.label, str) or not self.label \
                or len(self.label) > LABEL_MAX:
            raise ValidationError(f"invalid option label: {self.label!r}")
        if not isinstance(self.description, str):
            raise ValidationError("option description must be a string")

    def to_dict(self) -> dict:
        return {"value": self.value, "label": self.label,
                "description": self.description}

    @classmethod
    def from_dict(cls, d: dict) -> "Option":
        if not isinstance(d, dict):
            raise ValidationError(f"option must be an object: {d!r}")
        unknown = set(d) - {"value", "label", "description"}
        if unknown:
            raise ValidationError(f"unknown option keys: {sorted(unknown)}")
        opt = cls(value=d.get("value", ""), label=d.get("label", ""),
                  description=d.get("description", ""))
        opt.validate()
        return opt


def assign_option_values(labels_descs: list[tuple[str, str]]) -> list[Option]:
    """Build options with auto-assigned stable values ``o<idx>``."""
    opts = [Option(value=f"o{i}", label=lbl, description=desc)
            for i, (lbl, desc) in enumerate(labels_descs)]
    for o in opts:
        o.validate()
    return opts


@dataclass
class Question:
    """A relay question (contract 3, amended)."""

    id: str
    seq: int
    session_id: str
    text: str
    header: str = ""
    options: list[Option] = field(default_factory=list)
    multi_select: bool = False
    allow_free_text: bool = False
    timeout_s: int = 90

    def validate(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValidationError("question id must be a non-empty string")
        if not isinstance(self.seq, int) or isinstance(self.seq, bool) \
                or self.seq < 1 or self.seq > SEQ_MAX:
            raise ValidationError(f"invalid seq: {self.seq!r}")
        if not _SESSION_ID_RE.match(self.session_id or ""):
            raise ValidationError(f"invalid session_id: {self.session_id!r}")
        if not isinstance(self.text, str) or not self.text:
            raise ValidationError("question text must be a non-empty string")
        if not isinstance(self.header, str):
            raise ValidationError("question header must be a string")
        if not isinstance(self.options, list):
            raise ValidationError("options must be a list")
        for o in self.options:
            if not isinstance(o, Option):
                raise ValidationError(f"option must be an Option: {o!r}")
            o.validate()
        values = [o.value for o in self.options]
        if len(values) != len(set(values)):
            raise ValidationError("option values must be unique")
        if not isinstance(self.multi_select, bool):
            raise ValidationError("multi_select must be a bool")
        if not isinstance(self.allow_free_text, bool):
            raise ValidationError("allow_free_text must be a bool")
        if self.multi_select and not self.options:
            raise ValidationError("multi_select requires options")
        if not self.options and not self.allow_free_text:
            raise ValidationError(
                "unanswerable question: no options and no free text")
        if not isinstance(self.timeout_s, int) or isinstance(self.timeout_s, bool) \
                or self.timeout_s < 1:
            raise ValidationError(f"invalid timeout_s: {self.timeout_s!r}")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "seq": self.seq, "session_id": self.session_id,
            "text": self.text, "header": self.header,
            "options": [o.to_dict() for o in self.options],
            "multi_select": self.multi_select,
            "allow_free_text": self.allow_free_text,
            "timeout_s": self.timeout_s,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        if not isinstance(d, dict):
            raise ValidationError(f"question must be an object: {d!r}")
        required = {"id", "seq", "session_id", "text", "header", "options",
                    "multi_select", "allow_free_text", "timeout_s"}
        missing = required - set(d)
        if missing:
            raise ValidationError(f"question missing keys: {sorted(missing)}")
        unknown = set(d) - required
        if unknown:
            raise ValidationError(f"unknown question keys: {sorted(unknown)}")
        if not isinstance(d["options"], list):
            raise ValidationError("options must be a list")
        q = cls(
            id=d["id"], seq=d["seq"], session_id=d["session_id"],
            text=d["text"], header=d["header"],
            options=[Option.from_dict(o) for o in d["options"]],
            multi_select=d["multi_select"],
            allow_free_text=d["allow_free_text"],
            timeout_s=d["timeout_s"],
        )
        q.validate()
        return q


@dataclass
class Answer:
    """A relay answer (contract 3, amended): ``values`` carries option
    **values**, never labels."""

    id: str
    seq: int
    status: str
    values: list[str] = field(default_factory=list)
    free_text: str | None = None
    answered_by: str | None = None

    def validate(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValidationError("answer id must be a non-empty string")
        if not isinstance(self.seq, int) or isinstance(self.seq, bool) \
                or self.seq < 1 or self.seq > SEQ_MAX:
            raise ValidationError(f"invalid seq: {self.seq!r}")
        if self.status not in ANSWER_STATUSES:
            raise ValidationError(f"invalid status: {self.status!r}")
        if not isinstance(self.values, list) \
                or not all(isinstance(v, str) and v for v in self.values):
            raise ValidationError("values must be a list of non-empty strings")
        if self.free_text is not None and not isinstance(self.free_text, str):
            raise ValidationError("free_text must be a string or null")
        if self.answered_by is not None \
                and not isinstance(self.answered_by, str):
            raise ValidationError("answered_by must be a string or null")
        if self.status != "answered":
            if self.values or self.free_text is not None:
                raise ValidationError(
                    f"{self.status} answer must carry no values/free_text")
        else:
            if not self.values and self.free_text is None:
                raise ValidationError(
                    "answered answer needs values or free_text")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "seq": self.seq, "status": self.status,
            "values": list(self.values), "free_text": self.free_text,
            "answered_by": self.answered_by,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Answer":
        if not isinstance(d, dict):
            raise ValidationError(f"answer must be an object: {d!r}")
        required = {"id", "seq", "status", "values", "free_text",
                    "answered_by"}
        missing = required - set(d)
        if missing:
            raise ValidationError(f"answer missing keys: {sorted(missing)}")
        unknown = set(d) - required
        if unknown:
            raise ValidationError(f"unknown answer keys: {sorted(unknown)}")
        a = cls(id=d["id"], seq=d["seq"], status=d["status"],
                values=d["values"], free_text=d["free_text"],
                answered_by=d["answered_by"])
        a.validate()
        return a


@dataclass
class TaskPayload:
    """The agent's final task-creation payload (contract 7 + contract 1).

    **Shared schema helper — the ownership split is deliberate:**

    - The **producer** (``chatlink/relay_payload.py``, t1120_4) validates
      shape here before writing, so a malformed payload fails inside the
      sandbox where the agent can still fix it.
    - The **gateway validator** (t1120_6) starts from ``from_dict`` and
      layers the *repo-authoritative* checks on top: ``issue_type`` ∈
      ``task_types.txt``, ``labels`` ⊆ ``labels.txt``, control-char
      stripping. Those checks are repo state the sandboxed producer must
      not own.

    ``SessionDir.write_payload``/``read_payload`` stay an opaque dict
    transport — field validation is the caller's job via this class.
    """

    session_id: str
    name: str
    title: str
    priority: str
    effort: str
    issue_type: str
    labels: list[str] = field(default_factory=list)
    description: str = ""

    def validate(self) -> None:
        if not _SESSION_ID_RE.match(self.session_id or ""):
            raise ValidationError(f"invalid session_id: {self.session_id!r}")
        if not isinstance(self.name, str) or not _NAME_SLUG_RE.match(self.name):
            raise ValidationError(
                f"invalid name slug (want [a-z0-9_], ≤ {PAYLOAD_NAME_MAX}): "
                f"{self.name!r}")
        if not isinstance(self.title, str) or not self.title.strip() \
                or len(self.title) > PAYLOAD_TITLE_MAX:
            raise ValidationError(
                f"invalid title (non-empty, ≤ {PAYLOAD_TITLE_MAX} chars): "
                f"{self.title!r}")
        if self.priority not in PAYLOAD_LEVELS:
            raise ValidationError(f"invalid priority: {self.priority!r}")
        if self.effort not in PAYLOAD_LEVELS:
            raise ValidationError(f"invalid effort: {self.effort!r}")
        if not isinstance(self.issue_type, str) \
                or not _ISSUE_TYPE_RE.match(self.issue_type):
            raise ValidationError(f"invalid issue_type: {self.issue_type!r}")
        if not isinstance(self.labels, list) \
                or not all(isinstance(l, str) and _LABEL_RE.match(l)
                           for l in self.labels):
            raise ValidationError(
                f"labels must be a list of slug strings: {self.labels!r}")
        if not isinstance(self.description, str) \
                or not self.description.strip():
            raise ValidationError("description must be a non-empty string")
        if len(self.description.encode("utf-8")) > PAYLOAD_DESCRIPTION_MAX:
            raise ValidationError(
                f"description exceeds {PAYLOAD_DESCRIPTION_MAX} bytes")

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id, "name": self.name,
            "title": self.title, "priority": self.priority,
            "effort": self.effort, "issue_type": self.issue_type,
            "labels": list(self.labels), "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TaskPayload":
        if not isinstance(d, dict):
            raise ValidationError(f"payload must be an object: {d!r}")
        required = {"session_id", "name", "title", "priority", "effort",
                    "issue_type", "labels", "description"}
        missing = required - set(d)
        if missing:
            raise ValidationError(f"payload missing keys: {sorted(missing)}")
        unknown = set(d) - required
        if unknown:
            raise ValidationError(f"unknown payload keys: {sorted(unknown)}")
        p = cls(session_id=d["session_id"], name=d["name"], title=d["title"],
                priority=d["priority"], effort=d["effort"],
                issue_type=d["issue_type"], labels=d["labels"],
                description=d["description"])
        p.validate()
        return p


# --- Spool access (contract 2) ---

def _atomic_write_json(path: Path, payload: dict) -> None:
    """Write ``payload`` atomically: ``<path>.tmp`` → ``os.replace``.

    Pattern: ``applink/sessions.py:200-217``. Readers ignore ``*.tmp``.
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict | None:
    """Read a JSON object, or None if the file is absent."""
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return None
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValidationError(f"{path.name} is not a JSON object")
    return obj


_QUESTION_RE = re.compile(r"^question-(\d{1,6})\.json$")


@dataclass
class SessionDir:
    """One relay session's spool directory (all writes atomic).

    All state is derivable from the directory contents — no in-memory
    session state survives here (restart-derivability, contract 4).
    """

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    @property
    def session_id(self) -> str:
        return self.path.name

    # -- questions/answers --

    def question_path(self, seq: int) -> Path:
        return self.path / f"question-{seq}.json"

    def answer_path(self, seq: int) -> Path:
        return self.path / f"answer-{seq}.json"

    def question_seqs(self) -> list[int]:
        """All seqs with a question file, ascending (ignores ``*.tmp``)."""
        seqs = []
        for entry in self.path.iterdir():
            m = _QUESTION_RE.match(entry.name)
            if m:
                seqs.append(int(m.group(1)))
        return sorted(seqs)

    def next_seq(self) -> int:
        """Next question seq, derived from the spool (no in-memory counter)."""
        seqs = self.question_seqs()
        return (seqs[-1] + 1) if seqs else 1

    def write_question(self, q: Question) -> None:
        q.validate()
        if q.session_id != self.session_id:
            raise ValidationError(
                f"question session_id {q.session_id!r} does not match "
                f"session dir {self.session_id!r}")
        _atomic_write_json(self.question_path(q.seq), q.to_dict())

    def read_question(self, seq: int) -> Question | None:
        d = _read_json(self.question_path(seq))
        return None if d is None else Question.from_dict(d)

    def write_answer(self, a: Answer, *, overwrite: bool = False) -> bool:
        """Write an answer atomically. With ``overwrite=False`` (the
        never-overwrite rule of the durable-timeout contract) the
        check-and-write is **indivisible**: the payload is written to a
        ``*.tmp`` file and published with ``os.link`` — an atomic
        create-no-replace — so a racing gateway answer can never be
        clobbered by a helper timeout write (or vice versa). Returns False
        (writes nothing) when an answer for that seq already exists."""
        a.validate()
        path = self.answer_path(a.seq)
        if overwrite:
            _atomic_write_json(path, a.to_dict())
            return True
        # Stage under a UNIQUE per-writer name (pid + random, still *.tmp so
        # readers skip it): a fixed shared staging name would let a competing
        # writer overwrite the staged payload before the link publishes it.
        tmp = path.with_name(
            f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
        tmp.write_text(json.dumps(a.to_dict(), indent=2) + "\n")
        try:
            os.link(tmp, path)  # atomic: fails iff path already exists
        except FileExistsError:
            return False
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
        return True

    def read_answer(self, seq: int) -> Answer | None:
        d = _read_json(self.answer_path(seq))
        return None if d is None else Answer.from_dict(d)

    def pending_questions(self) -> list[Question]:
        """Questions with no answer file — the stateless pending set
        (``question-<seq>`` present ∧ ``answer-<seq>`` absent)."""
        pending = []
        for seq in self.question_seqs():
            if not self.answer_path(seq).exists():
                q = self.read_question(seq)
                if q is not None:
                    pending.append(q)
        return pending

    # -- opaque gateway/agent artifacts --

    def write_status(self, status: dict) -> None:
        """Atomic write of the gateway-owned ``status.json`` (opaque here)."""
        if not isinstance(status, dict):
            raise ValidationError("status must be a dict")
        _atomic_write_json(self.path / "status.json", status)

    def read_status(self) -> dict | None:
        return _read_json(self.path / "status.json")

    def write_payload(self, payload: dict) -> None:
        """Atomic write of the agent's final ``payload.json`` (validated by
        the gateway per contract 7 — opaque here). Field validation is the
        caller's job via :class:`TaskPayload`."""
        if not isinstance(payload, dict):
            raise ValidationError("payload must be a dict")
        _atomic_write_json(self.path / "payload.json", payload)

    def read_payload(self) -> dict | None:
        return _read_json(self.path / "payload.json")
