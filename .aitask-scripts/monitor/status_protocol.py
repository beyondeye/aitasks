"""status_protocol - codec for the monitor status protocol (t2034_3).

The wire between ONE shared monitor status server and its clients (``ait
monitor``, ``ait minimonitor``, applink, the Go monitor). The specification is
``aidocs/framework/monitor_status_protocol.md``; this module is its Python
codec, and the schema tables below are pinned to the spec's member tables by
``tests/test_monitor_status_protocol.py`` — change both together.

Pure and headless: stdlib plus the ``monitor_core`` dataclasses. No Textual, no
tmux. It provides

- :func:`decode` / :func:`encode` — one NDJSON line ⇄ one validated,
  **normalized** message dict (known members only; unknown members dropped);
- :func:`read_line` — the framing rule for asyncio streams (an over-limit line
  is terminal, never re-framed);
- :func:`pane_record` / :func:`pane_snapshot` / :func:`monitor_pane_record` —
  ``PaneSnapshot`` ⇄ wire record;
- :class:`StreamFrame`, :func:`snapshot_message`, :func:`filter_message`,
  :class:`StreamEncoder` (server side) and :class:`StreamState` (client side) —
  the snapshot/delta stream with its generation and patch rules.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
from dataclasses import dataclass, field

try:  # imported as part of the `monitor` package
    from .monitor_core import (
        COMPARE_MODES,
        DEFAULT_COMPARE_MODE,
        PaneCategory,
        PaneSnapshot,
        TmuxPaneInfo,
    )
except ImportError:  # imported top-level (script run / MONITOR_DIR on sys.path)
    from monitor_core import (  # noqa: E402
        COMPARE_MODES,
        DEFAULT_COMPARE_MODE,
        PaneCategory,
        PaneSnapshot,
        TmuxPaneInfo,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Protocol major version. Additive changes (new optional members, new request
#: types, new error codes, new open-string values) never bump it.
PROTO = 1
#: Recording-file format revision (the ``recording`` header's ``rev``).
RECORDING_REV = 1

#: Line limits in bytes, the terminating ``\n`` not counted.
MAX_CLIENT_LINE_BYTES = 64 * 1024
MAX_SERVER_LINE_BYTES = 64 * 1024 * 1024
#: Per-record ``content`` cap, in characters.
MAX_CONTENT_CHARS = 4 * 1024 * 1024
MAX_CAPTURE_LINES = 10000
#: Cap on every list and map member.
MAX_ITEMS = 4096
MAX_NAME_CHARS = 1024
MAX_PATH_CHARS = 4096
MAX_ID_CHARS = 128
MAX_TEXT_CHARS = 4096
MAX_INT = 2 ** 53 - 1
#: Upper bound for wall-clock seconds and durations (year ~33658).
MAX_SECONDS = 1e12

#: Message directions. ``CLIENT`` = client→server, ``SERVER`` = server→client,
#: ``RECORDING`` = a recording file (its header plus the server's stream).
CLIENT = "client"
SERVER = "server"
RECORDING = "recording"

CLIENT_TYPES = (
    "hello", "subscribe", "set_content", "set_pins", "refresh",
    "set_compare_mode", "cycle_compare_mode", "capture",
)
SERVER_TYPES = ("welcome", "snapshot", "delta", "result", "error")
RECORDING_TYPES = ("recording", "welcome", "snapshot", "delta")
DIRECTION_TYPES = {
    CLIENT: CLIENT_TYPES,
    SERVER: SERVER_TYPES,
    RECORDING: RECORDING_TYPES,
}

#: Error codes this version defines. ``code`` is an OPEN string on the wire.
ERROR_CODES = (
    "bad_message", "too_long", "unknown_type", "proto_mismatch",
    "version_mismatch", "not_subscribed", "not_found", "unavailable",
    "internal",
)

#: Closed enums: a new value is a ``proto`` bump.
CATEGORY_VALUES = tuple(c.value for c in PaneCategory)
COMPARE_MODE_VALUES = tuple(COMPARE_MODES)
#: ``control_state`` is an OPEN string; these are the values sent today.
CONTROL_STATES = ("connected", "reconnecting", "fallback", "stopped")

CONTENT_ALL = "all"
CONTENT_NONE = "none"
PINS_ALL = "all"

#: Matched with fullmatch(): `$` (and match()) would also accept "%1\n".
_PANE_ID_RE = re.compile(r"%[0-9]{1,10}")
_SURROGATE_RE = re.compile("[\ud800-\udfff]")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ProtocolError(ValueError):
    """A line or message that violates the protocol. ``code`` is the wire
    error code a server answers with (``bad_message`` unless a subclass says
    otherwise)."""

    def __init__(self, message: str, code: str = "bad_message"):
        super().__init__(message)
        self.code = code
        #: The offending object's readable ``id`` / ``type`` (see validate()).
        self.request_id = None
        self.request_type = None


class UnknownMessageType(ProtocolError):
    """A well-formed object whose ``type`` this version does not define for the
    direction. Clients ignore it; a server answers ``unknown_type``."""

    def __init__(self, type_name: str):
        super().__init__(f"unknown message type: {_clip(type_name)!r}", "unknown_type")
        self.type_name = type_name


class FramingError(ProtocolError):
    """An over-limit line. Terminal for a connection: the receiver never tries
    to re-frame inside the stream (see "Oversized lines" in the spec)."""

    def __init__(self, message: str = "line exceeds the size limit"):
        super().__init__(message, "too_long")


class StreamError(ProtocolError):
    """A message that cannot be applied to the client's stream state."""


class StreamGap(StreamError):
    """A delta whose ``gen`` skips ahead: the client must resubscribe."""


def _fail(path: str, why: str):
    raise ProtocolError(f"{path}: {why}")


def _clip(text: str, limit: int = 64) -> str:
    """A diagnostic-safe prefix of untrusted text."""
    return text if len(text) <= limit else text[:limit] + "…"


def _readable_id(msg):
    """The request ``id`` of an object, when it is itself valid; else None."""
    if type(msg) is not dict or "id" not in msg:
        return None
    try:
        return _v_request_id(msg["id"], "id")
    except ProtocolError:
        return None


def _readable_type(msg):
    """The ``type`` of an object when it is a string short enough to echo in
    ``error.request``; else None."""
    if type(msg) is not dict:
        return None
    value = msg.get("type")
    return value if type(value) is str and 0 < len(value) <= 64 else None


# ---------------------------------------------------------------------------
# Validators: (value, path) -> normalized value, raising ProtocolError
# ---------------------------------------------------------------------------

def _v_bool(value, path):
    if type(value) is not bool:
        _fail(path, "expected a boolean")
    return value


def _v_int(lo: int = 0, hi: int = MAX_INT):
    def check(value, path):
        # JSON integers only: bool is not an int, and neither is any float
        # (`1.0` / `1e2` are rejected — a Go int64 field refuses them too).
        if type(value) is not int:
            _fail(path, "expected an integer")
        if not lo <= value <= hi:
            _fail(path, f"integer out of range [{lo}, {hi}]")
        return value
    return check


def _v_num(value, path):
    if type(value) is bool or not isinstance(value, (int, float)):
        _fail(path, "expected a number")
    # Range-check BEFORE converting: a JSON integer is unbounded in Python, and
    # `float()` of a 400-digit one raises OverflowError, not a ProtocolError.
    # (int/float comparison is exact and never overflows.)
    if isinstance(value, float) and not math.isfinite(value):
        _fail(path, "expected a finite number")
    if not 0 <= value <= MAX_SECONDS:
        _fail(path, f"number out of range [0, {MAX_SECONDS:g}]")
    return float(value)


def _v_str(max_chars: int = MAX_NAME_CHARS, *, nonempty: bool = False):
    def check(value, path):
        if type(value) is not str:
            _fail(path, "expected a string")
        if len(value) > max_chars:
            _fail(path, f"string longer than {max_chars} characters")
        if nonempty and not value:
            _fail(path, "expected a non-empty string")
        return value
    return check


def _v_pane_id(value, path):
    if type(value) is not str or not _PANE_ID_RE.fullmatch(value):
        _fail(path, "expected a pane id (%N)")
    return value


def _v_shadow_target(value, path):
    if type(value) is not str or (value and not _PANE_ID_RE.fullmatch(value)):
        _fail(path, "expected a pane id (%N) or an empty string")
    return value


def _v_enum(values):
    allowed = tuple(values)

    def check(value, path):
        if type(value) is not str or value not in allowed:
            _fail(path, f"expected one of {list(allowed)}")
        return value
    return check


def _v_nullable(inner):
    def check(value, path):
        return None if value is None else inner(value, path)
    return check


def _v_list(inner, max_items: int = MAX_ITEMS):
    def check(value, path):
        if type(value) is not list:
            _fail(path, "expected an array")
        if len(value) > max_items:
            _fail(path, f"array longer than {max_items} items")
        return [inner(item, f"{path}[{i}]") for i, item in enumerate(value)]
    return check


def _v_pair(value, path):
    if type(value) not in (list, tuple) or len(value) != 2:
        _fail(path, "expected a [session, window] pair")
    return [_v_str()(value[0], f"{path}[0]"), _v_str()(value[1], f"{path}[1]")]


def _v_selection(value, path):
    if value in (CONTENT_ALL, CONTENT_NONE):
        return value
    if type(value) is str:
        _fail(path, 'expected "all", "none" or an array of pane ids')
    return sorted(set(_v_list(_v_pane_id)(value, path)), key=_pane_num)


def _v_pins(value, path):
    if value == PINS_ALL:
        return value
    if type(value) is str:
        _fail(path, 'expected "all" or an array of [session, window] pairs')
    return [list(p) for p in sorted({tuple(p) for p in _v_list(_v_pair)(value, path)})]


def _v_request_id(value, path):
    if type(value) is str:
        if len(value) > MAX_ID_CHARS:
            _fail(path, f"id longer than {MAX_ID_CHARS} characters")
        return value
    if type(value) is int and 0 <= value <= MAX_INT:
        return value
    _fail(path, f"expected a string id or an integer in [0, {MAX_INT}]")


def _v_object(members: dict):
    """An object with declared members ``{name: (required, validator)}``.
    Unknown members are dropped (ignored), required ones must be present."""
    def check(value, path):
        if type(value) is not dict:
            _fail(path, "expected an object")
        out = {}
        for name, (required, validator) in members.items():
            if name in value:
                out[name] = validator(value[name], f"{path}.{name}")
            elif required:
                _fail(path, f"missing required member {name!r}")
        return out
    return check


def _v_map(key_check, value_check, max_items: int = MAX_ITEMS):
    def check(value, path):
        if type(value) is not dict:
            _fail(path, "expected an object")
        if len(value) > max_items:
            _fail(path, f"object with more than {max_items} members")
        out = {}
        for key, item in value.items():
            key_check(key, f"{path} key")
            out[key] = value_check(item, f"{path}[{key!r}]")
        return out
    return check


def _pane_num(pane_id: str) -> int:
    try:
        return int(pane_id[1:])
    except (TypeError, ValueError):
        return -1


# ---------------------------------------------------------------------------
# Schema tables — pinned to the spec's member tables (change both together)
# ---------------------------------------------------------------------------

REQ, OPT = True, False

#: ``pane`` — every ``TmuxPaneInfo`` field.
PANE_SCHEMA = {
    "window_index": (REQ, _v_str()),
    "window_name": (REQ, _v_str()),
    "pane_index": (REQ, _v_str()),
    "pane_id": (REQ, _v_pane_id),
    "pane_pid": (REQ, _v_int()),
    "current_command": (REQ, _v_str()),
    "width": (REQ, _v_int(0, 100000)),
    "height": (REQ, _v_int(0, 100000)),
    "category": (REQ, _v_enum(CATEGORY_VALUES)),
    "session_name": (REQ, _v_str()),
    "shadow_target": (REQ, _v_shadow_target),
    "history_size": (REQ, _v_nullable(_v_int())),
    "frozen_record": (REQ, _v_str()),
    "record_id": (REQ, _v_str()),
    "standin_ready": (REQ, _v_str()),
    "pane_dead": (REQ, _v_bool),
}
_v_pane = _v_object(PANE_SCHEMA)

#: Pane / shadow record (a full record; a patch is any subset of it).
RECORD_SCHEMA = {
    "pane": (REQ, _v_pane),
    "content": (OPT, _v_str(MAX_CONTENT_CHARS)),
    "idle_seconds": (REQ, _v_num),
    "is_idle": (REQ, _v_bool),
    "awaiting_input": (REQ, _v_bool),
    "awaiting_input_kind": (REQ, _v_str()),
    "agent_key": (REQ, _v_str()),
    "scoped": (REQ, _v_bool),
    "parked": (REQ, _v_bool),
    "frozen": (REQ, _v_bool),
    "frozen_record_id": (REQ, _v_str()),
    "compare_mode": (REQ, _v_enum(COMPARE_MODE_VALUES)),
    "compare_override": (REQ, _v_bool),
    "last_change": (REQ, _v_nullable(_v_num)),
}
_v_full_record = _v_object(RECORD_SCHEMA)
_v_patch = _v_object({name: (OPT, check) for name, (_r, check) in RECORD_SCHEMA.items()})

CLIENT_INFO_SCHEMA = {
    "kind": (REQ, _v_str(64, nonempty=True)),
    "pane": (OPT, _v_pane_id),
    "pid": (OPT, _v_int()),
}
SERVER_INFO_SCHEMA = {
    "impl": (REQ, _v_str(64, nonempty=True)),
    "pid": (OPT, _v_int()),
}
REPLAY_INFO_SCHEMA = {
    "recorded_version": (REQ, _v_str(64)),
    "source": (REQ, _v_str(MAX_TEXT_CHARS)),
}
SESSION_SCHEMA = {
    "project_root": (REQ, _v_str(MAX_PATH_CHARS)),
    "project_name": (REQ, _v_str()),
}
DISCOVERY_PANE_SCHEMA = {
    "id": (REQ, _v_pane_id),
    "pid": (REQ, _v_int()),
    "dead": (REQ, _v_bool),
}
DISCOVERY_WINDOW_SCHEMA = {
    "session": (REQ, _v_str()),
    "window": (REQ, _v_str()),
    "panes": (REQ, _v_list(_v_object(DISCOVERY_PANE_SCHEMA))),
}
DISCOVERY_SCHEMA = {
    "enumerated": (REQ, _v_list(_v_str())),
    "agents": (REQ, _v_list(_v_pair)),
    "windows": (REQ, _v_list(_v_object(DISCOVERY_WINDOW_SCHEMA))),
}

#: Nested objects, by the name the spec's tables use.
OBJECT_SCHEMAS = {
    "pane": PANE_SCHEMA,
    "record": RECORD_SCHEMA,
    "hello.client": CLIENT_INFO_SCHEMA,
    "welcome.server": SERVER_INFO_SCHEMA,
    "welcome.replay": REPLAY_INFO_SCHEMA,
    "session": SESSION_SCHEMA,
    "discovery": DISCOVERY_SCHEMA,
    "discovery.window": DISCOVERY_WINDOW_SCHEMA,
    "discovery.pane": DISCOVERY_PANE_SCHEMA,
}


def _record_map(full: bool, key_member: str):
    """``{pane id: record}``. ``key_member`` names the ``pane`` field that must
    equal the key whenever ``pane`` is present (``pane_id`` for panes,
    ``shadow_target`` for shadows, which are keyed by the followed pane)."""
    inner = _v_full_record if full else _v_patch

    def check(value, path):
        out = _v_map(_v_pane_id, inner)(value, path)
        for key, rec in out.items():
            pane = rec.get("pane")
            if pane is not None and pane.get(key_member) != key:
                _fail(f"{path}[{key!r}]", f"pane.{key_member} does not match the key")
        return out
    return check


_v_ts = _v_num
_ID = (OPT, _v_request_id)

MESSAGE_SCHEMAS = {
    # --- client → server ---------------------------------------------------
    "hello": {
        "proto": (REQ, _v_int()),
        "version": (REQ, _v_str(64, nonempty=True)),
        "client": (REQ, _v_object(CLIENT_INFO_SCHEMA)),
    },
    "subscribe": {
        "id": _ID,
        "content": (OPT, _v_selection),
        "include_shadows": (OPT, _v_bool),
        "pins": (OPT, _v_pins),
    },
    "set_content": {"id": _ID, "content": (REQ, _v_selection)},
    "set_pins": {"id": _ID, "pins": (REQ, _v_pins)},
    "refresh": {
        "id": _ID,
        "panes": (OPT, _v_list(_v_pane_id)),
        "shadows": (OPT, _v_list(_v_pane_id)),
    },
    "set_compare_mode": {
        "id": _ID,
        "pane": (REQ, _v_pane_id),
        "mode": (REQ, _v_nullable(_v_enum(COMPARE_MODE_VALUES))),
    },
    "cycle_compare_mode": {"id": _ID, "pane": (REQ, _v_pane_id)},
    "capture": {
        "id": _ID,
        "pane": (REQ, _v_pane_id),
        "lines": (REQ, _v_int(1, MAX_CAPTURE_LINES)),
    },
    # --- server → client ---------------------------------------------------
    "welcome": {
        "ts": (REQ, _v_ts),
        "proto": (REQ, _v_int()),
        "version": (REQ, _v_str(64, nonempty=True)),
        "server": (REQ, _v_object(SERVER_INFO_SCHEMA)),
        "replay": (OPT, _v_object(REPLAY_INFO_SCHEMA)),
    },
    "snapshot": {
        "ts": (REQ, _v_ts),
        "gen": (REQ, _v_int()),
        "id": _ID,
        "panes": (REQ, _record_map(True, "pane_id")),
        "shadows": (REQ, _record_map(True, "shadow_target")),
        "completed": (REQ, _v_list(_v_pane_id)),
        "sessions": (REQ, _v_map(_v_str(), _v_object(SESSION_SCHEMA))),
        "parked": (REQ, _v_list(_v_pair)),
        "discovery": (REQ, _v_object(DISCOVERY_SCHEMA)),
        "control_state": (REQ, _v_str(64)),
    },
    "delta": {
        "ts": (REQ, _v_ts),
        "gen": (REQ, _v_int()),
        "panes": (OPT, _record_map(False, "pane_id")),
        "removed": (OPT, _v_list(_v_pane_id)),
        "shadows": (OPT, _record_map(False, "shadow_target")),
        "shadows_removed": (OPT, _v_list(_v_pane_id)),
        "completed": (OPT, _v_list(_v_pane_id)),
        "sessions": (OPT, _v_map(_v_str(), _v_object(SESSION_SCHEMA))),
        "parked": (OPT, _v_list(_v_pair)),
        "discovery": (OPT, _v_object(DISCOVERY_SCHEMA)),
        "control_state": (OPT, _v_str(64)),
    },
    "result": {
        "ts": (REQ, _v_ts),
        "id": _ID,
        "request": (REQ, _v_str(64, nonempty=True)),
    },
    "error": {
        "ts": (REQ, _v_ts),
        "id": _ID,
        "code": (REQ, _v_str(64, nonempty=True)),
        "message": (REQ, _v_str(MAX_TEXT_CHARS)),
        "request": (OPT, _v_str(64)),
        "server_proto": (OPT, _v_int()),
        "server_version": (OPT, _v_str(64)),
    },
    # --- recording file only -----------------------------------------------
    "recording": {
        "rev": (REQ, _v_int()),
        "proto": (REQ, _v_int()),
        "version": (REQ, _v_str(64, nonempty=True)),
        "source": (REQ, _v_str(MAX_TEXT_CHARS)),
        "created": (REQ, _v_num),
        "note": (OPT, _v_str(MAX_TEXT_CHARS)),
    },
}

#: Members a ``result`` carries per ``request`` (beyond ts / id / request).
#: A result whose ``request`` is not listed keeps only the common members.
RESULT_SCHEMAS = {
    "set_pins": {},
    "refresh": {"gen": (REQ, _v_int())},
    "set_compare_mode": {
        "mode": (REQ, _v_enum(COMPARE_MODE_VALUES)),
        "following_default": (REQ, _v_bool),
    },
    "cycle_compare_mode": {
        "mode": (REQ, _v_enum(COMPARE_MODE_VALUES)),
        "following_default": (REQ, _v_bool),
    },
    "capture": {
        "pane": (REQ, _v_pane_id),
        "content": (REQ, _v_str(MAX_CONTENT_CHARS)),
    },
}


def message_members(type_name: str) -> dict[str, bool]:
    """``{member: required}`` for a message type (``type`` itself excluded)."""
    return {name: req for name, (req, _c) in MESSAGE_SCHEMAS[type_name].items()}


def object_members(name: str) -> dict[str, bool]:
    return {member: req for member, (req, _c) in OBJECT_SCHEMAS[name].items()}


def result_members(request: str) -> dict[str, bool]:
    return {name: req for name, (req, _c) in RESULT_SCHEMAS[request].items()}


# ---------------------------------------------------------------------------
# decode / encode
# ---------------------------------------------------------------------------

def _max_bytes_for(direction: str) -> int:
    return MAX_CLIENT_LINE_BYTES if direction == CLIENT else MAX_SERVER_LINE_BYTES


def _reject_constant(name):
    raise ProtocolError(f"non-finite number {name} is not allowed")


def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ProtocolError(f"duplicate member {_clip(key)!r}")
        out[key] = value
    return out


def validate(msg, *, direction: str) -> dict:
    """Validate a message object for ``direction`` and return its normalized
    form (known members only). Raises :class:`ProtocolError` /
    :class:`UnknownMessageType`.

    Every error raised for an object carries ``request_id`` and
    ``request_type``: the object's ``id`` and ``type`` when each is itself
    readable (a valid id; a type of at most 64 characters), else None — so a
    server can correlate its error reply with the request that caused it."""
    if direction not in DIRECTION_TYPES:
        raise ValueError(f"unknown direction {direction!r}")
    try:
        return _validate(msg, direction)
    except ProtocolError as exc:
        exc.request_id = _readable_id(msg)
        exc.request_type = _readable_type(msg)
        raise
    except (OverflowError, RecursionError, ValueError) as exc:
        # Defence in depth: no validator may leak a non-protocol exception.
        err = ProtocolError(f"invalid message: {_clip(str(exc), 200)}")
        err.request_id = _readable_id(msg)
        err.request_type = _readable_type(msg)
        raise err from None


def _validate(msg, direction: str) -> dict:
    if type(msg) is not dict:
        raise ProtocolError("a message must be a JSON object")
    type_name = msg.get("type")
    if type(type_name) is not str or not type_name:
        raise ProtocolError("missing or invalid member 'type'")
    if type_name not in DIRECTION_TYPES[direction]:
        if type_name in MESSAGE_SCHEMAS:
            raise ProtocolError(
                f"message type {_clip(type_name)!r} is not valid in the {direction} direction")
        raise UnknownMessageType(type_name)
    out = {"type": type_name}
    out.update(_v_object(MESSAGE_SCHEMAS[type_name])(msg, type_name))
    if type_name == "result":
        extra = RESULT_SCHEMAS.get(out["request"])
        if extra:
            out.update(_v_object(extra)(msg, f"result[{out['request']}]"))
    return out


def decode(line, *, direction: str, max_bytes: int | None = None) -> dict:
    """Decode ONE protocol line (bytes or str; one trailing ``\\n`` allowed)."""
    limit = _max_bytes_for(direction) if max_bytes is None else max_bytes
    if isinstance(line, str):
        raw = line.encode("utf-8", "surrogatepass")
    elif isinstance(line, (bytes, bytearray)):
        raw = bytes(line)
    else:
        raise TypeError("decode() takes bytes or str")
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if len(raw) > limit:
        raise FramingError(f"line of {len(raw)} bytes exceeds the {limit}-byte limit")
    if not raw.strip():
        raise ProtocolError("empty line")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ProtocolError("line is not valid UTF-8") from None
    try:
        obj = json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_constant,
        )
    except ProtocolError:
        raise
    except RecursionError:
        raise ProtocolError("JSON nested too deeply") from None
    except ValueError as exc:
        raise ProtocolError(f"not valid JSON: {exc}") from None
    return validate(obj, direction=direction)


def encode(msg: dict, *, direction: str) -> bytes:
    """Validate ``msg`` and serialize its normalized form as one line.

    Compact, sorted keys, UTF-8, no NaN/Infinity; lone surrogates are replaced
    with U+FFFD. Raises :class:`ProtocolError` for an invalid message and
    :class:`FramingError` when the line would exceed the direction's limit."""
    normalized = validate(msg, direction=direction)
    text = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )
    try:
        raw = text.encode("utf-8")
    except UnicodeEncodeError:
        raw = _SURROGATE_RE.sub("�", text).encode("utf-8")
    limit = _max_bytes_for(direction)
    if len(raw) > limit:
        raise FramingError(f"encoded line of {len(raw)} bytes exceeds the {limit}-byte limit")
    return raw + b"\n"


async def read_line(reader: asyncio.StreamReader) -> bytes | None:
    """Read one complete protocol line from an asyncio stream.

    The size limit is the reader's own ``limit`` (set it to the direction's
    line limit when opening the stream). Returns the line including its
    ``\\n``, or ``None`` at EOF — an unterminated tail at EOF is discarded,
    never parsed. An over-limit line raises :class:`FramingError`, which is
    terminal: ``StreamReader.readline`` clears its buffer mid-line for a
    fragmented over-limit line, so the rest of that line would otherwise be read
    as a message of its own.
    """
    try:
        line = await reader.readline()
    except ValueError as exc:  # LimitOverrunError, re-raised by readline()
        raise FramingError(str(exc) or "line exceeds the size limit") from None
    if not line or not line.endswith(b"\n"):
        return None
    return line


# ---------------------------------------------------------------------------
# Records: PaneSnapshot <-> wire record
# ---------------------------------------------------------------------------

def _round_s(value: float | None) -> float | None:
    return None if value is None else round(float(value), 3)


def pane_info_member(pane: TmuxPaneInfo) -> dict:
    """The ``pane`` member: every ``TmuxPaneInfo`` field."""
    return {
        "window_index": str(pane.window_index),
        "window_name": pane.window_name,
        "pane_index": str(pane.pane_index),
        "pane_id": pane.pane_id,
        "pane_pid": int(pane.pane_pid),
        "current_command": pane.current_command,
        "width": int(pane.width),
        "height": int(pane.height),
        "category": pane.category.value,
        "session_name": pane.session_name,
        "shadow_target": pane.shadow_target,
        "history_size": None if pane.history_size is None else int(pane.history_size),
        "frozen_record": pane.frozen_record,
        "record_id": pane.record_id,
        "standin_ready": pane.standin_ready,
        "pane_dead": bool(pane.pane_dead),
    }


def pane_record(
    snap: PaneSnapshot,
    *,
    compare_mode: str = DEFAULT_COMPARE_MODE,
    compare_override: bool = False,
    last_change: float | None = None,
    include_content: bool = True,
) -> dict:
    """A full wire record for one ``PaneSnapshot``. ``timestamp`` (process-local
    monotonic time) is not on the wire; the three producer-held values
    (compare mode, override, wall-clock last change) are passed in."""
    rec = {
        "pane": pane_info_member(snap.pane),
        "idle_seconds": _round_s(snap.idle_seconds),
        "is_idle": bool(snap.is_idle),
        "awaiting_input": bool(snap.awaiting_input),
        "awaiting_input_kind": snap.awaiting_input_kind,
        "agent_key": snap.agent_key,
        "scoped": bool(snap.scoped),
        "parked": bool(snap.parked),
        "frozen": bool(snap.frozen),
        "frozen_record_id": snap.frozen_record_id,
        "compare_mode": compare_mode,
        "compare_override": bool(compare_override),
        "last_change": _round_s(last_change),
    }
    if include_content:
        rec["content"] = snap.content
    return rec


def monitor_pane_record(monitor, snap: PaneSnapshot, *, include_content: bool = True) -> dict:
    """:func:`pane_record` reading the producer-held values from a
    ``TmuxMonitor`` — the one place those accessor names are mapped."""
    pane_id = snap.pane.pane_id
    return pane_record(
        snap,
        compare_mode=monitor.get_compare_mode(pane_id),
        compare_override=monitor.is_compare_mode_overridden(pane_id),
        last_change=monitor.get_last_change_wall(pane_id),
        include_content=include_content,
    )


def pane_snapshot(record: dict, *, timestamp: float | None = None) -> PaneSnapshot:
    """Rebuild a ``PaneSnapshot`` from a full record. A record without
    ``content`` (an unselected pane) gets ``""``; ``timestamp`` is the
    receiver's own monotonic time."""
    p = record["pane"]
    pane = TmuxPaneInfo(
        window_index=p["window_index"],
        window_name=p["window_name"],
        pane_index=p["pane_index"],
        pane_id=p["pane_id"],
        pane_pid=p["pane_pid"],
        current_command=p["current_command"],
        width=p["width"],
        height=p["height"],
        category=PaneCategory(p["category"]),
        session_name=p["session_name"],
        shadow_target=p["shadow_target"],
        history_size=p["history_size"],
        frozen_record=p["frozen_record"],
        record_id=p["record_id"],
        standin_ready=p["standin_ready"],
        pane_dead=p["pane_dead"],
    )
    return PaneSnapshot(
        pane=pane,
        content=record.get("content", ""),
        timestamp=time.monotonic() if timestamp is None else timestamp,
        idle_seconds=record["idle_seconds"],
        is_idle=record["is_idle"],
        awaiting_input=record["awaiting_input"],
        awaiting_input_kind=record["awaiting_input_kind"],
        agent_key=record["agent_key"],
        scoped=record["scoped"],
        parked=record["parked"],
        frozen=record["frozen"],
        frozen_record_id=record["frozen_record_id"],
    )


# ---------------------------------------------------------------------------
# Stream frames
# ---------------------------------------------------------------------------

def empty_discovery() -> dict:
    return {"enumerated": [], "agents": [], "windows": []}


@dataclass
class StreamFrame:
    """The wire-shaped state of one generation.

    ``panes`` / ``shadows`` hold full records (``shadows`` keyed by the FOLLOWED
    pane id); ``completed`` / ``parked`` are sets; ``sessions`` and
    ``discovery`` are already in member form (see :func:`sessions_member` /
    :func:`discovery_member`)."""
    panes: dict = field(default_factory=dict)
    shadows: dict = field(default_factory=dict)
    completed: frozenset = frozenset()
    sessions: dict = field(default_factory=dict)
    parked: frozenset = frozenset()
    discovery: dict = field(default_factory=empty_discovery)
    control_state: str = "stopped"


#: The top-level members a delta may replace wholesale (besides pane maps).
TOP_LEVEL_MEMBERS = ("completed", "sessions", "parked", "discovery", "control_state")


def sessions_member(mapping: dict, names: dict | None = None) -> dict:
    """``{session: {project_root, project_name}}`` from a session→root map
    (``TmuxMonitor.get_session_to_project_mapping``). ``project_name`` defaults
    to the root's last path component."""
    out = {}
    for session in sorted(mapping):
        root = str(mapping[session])
        name = (names or {}).get(session) or root.rstrip("/").rsplit("/", 1)[-1]
        out[session] = {"project_root": root, "project_name": name}
    return out


def discovery_member(enumerated, agents, panes_by_window) -> dict:
    """The ``discovery`` member from the producer's same-generation facts:
    ``last_enumerated_sessions()``, ``last_discovered_agents()`` and
    ``last_discovered_panes()`` (``{(session, window): [(id, pid, dead), …]}``)."""
    windows = []
    for (session, window) in sorted(panes_by_window or {}):
        rows = sorted(panes_by_window[(session, window)], key=lambda r: _pane_num(r[0]))
        windows.append({
            "session": session,
            "window": window,
            "panes": [{"id": pid, "pid": int(ppid), "dead": bool(dead)}
                      for pid, ppid, dead in rows],
        })
    return {
        "enumerated": sorted(enumerated or ()),
        "agents": sorted([s, w] for s, w in (agents or ())),
        "windows": windows,
    }


def _sorted_ids(ids) -> list[str]:
    return sorted(ids, key=_pane_num)


def _copy_record(rec: dict) -> dict:
    out = dict(rec)
    if "pane" in out:
        out["pane"] = dict(out["pane"])
    return out


def _frame_members(frame: StreamFrame) -> dict:
    """The frame in message-member form, validated and normalized exactly as a
    receiver would decode it (so encoder state == decoded client state)."""
    panes = _record_map(True, "pane_id")(frame.panes, "frame.panes")
    shadows = _record_map(True, "shadow_target")(frame.shadows, "frame.shadows")
    return {
        "panes": panes,
        "shadows": shadows,
        "completed": _sorted_ids(_v_list(_v_pane_id)(list(frame.completed), "frame.completed")),
        "sessions": _v_map(_v_str(), _v_object(SESSION_SCHEMA))(dict(frame.sessions), "frame.sessions"),
        "parked": sorted(_v_list(_v_pair)([list(p) for p in frame.parked], "frame.parked")),
        "discovery": _v_object(DISCOVERY_SCHEMA)(frame.discovery, "frame.discovery"),
        "control_state": _v_str(64)(frame.control_state, "frame.control_state"),
    }


def _selected(pane_id: str, content) -> bool:
    if content == CONTENT_ALL:
        return True
    if content == CONTENT_NONE or content is None:
        return False
    return pane_id in content


def _project_entries(entries: dict, content, *, drop_empty: bool) -> dict:
    out = {}
    for key, rec in entries.items():
        if _selected(key, content) or "content" not in rec:
            out[key] = rec
            continue
        rec = {k: v for k, v in rec.items() if k != "content"}
        if rec or not drop_empty:
            out[key] = rec
    return out


def filter_message(msg: dict, *, content=CONTENT_ALL, include_shadows: bool = True) -> dict:
    """Project a ``snapshot`` / ``delta`` for one subscriber.

    Selection affects ONLY the ``content`` member: it is stripped from records
    and patches of unselected panes (a shadow follows its followed pane id). A
    patch left empty by that is dropped. Every other member, and every pane, is
    kept. With ``include_shadows`` off the shadow members are emptied (snapshot)
    or omitted (delta). A delta is never dropped — it is also the heartbeat that
    keeps ``gen`` contiguous. Other message types pass through unchanged."""
    kind = msg.get("type")
    if kind not in ("snapshot", "delta"):
        return msg
    if isinstance(content, (set, frozenset, tuple)):
        content = list(content)
    out = dict(msg)
    is_delta = kind == "delta"
    if "panes" in out:
        out["panes"] = _project_entries(out["panes"], content, drop_empty=is_delta)
        if is_delta and not out["panes"]:
            del out["panes"]
    if not include_shadows:
        if is_delta:
            out.pop("shadows", None)
            out.pop("shadows_removed", None)
        else:
            out["shadows"] = {}
    elif "shadows" in out:
        out["shadows"] = _project_entries(out["shadows"], content, drop_empty=is_delta)
        if is_delta and not out["shadows"]:
            del out["shadows"]
    return out


def snapshot_message(
    frame: StreamFrame,
    *,
    gen: int,
    ts: float,
    content=CONTENT_ALL,
    include_shadows: bool = True,
    id=None,
) -> dict:
    """A ``snapshot`` of ``frame`` at ``gen``, projected for one subscriber."""
    members = _frame_members(frame)
    msg = {"type": "snapshot", "gen": gen, "ts": _round_s(ts)}
    msg.update(members)
    if id is not None:
        msg["id"] = id
    return filter_message(msg, content=content, include_shadows=include_shadows)


def frame_from_members(members: dict) -> StreamFrame:
    """Inverse of the member form: a :class:`StreamFrame` from snapshot-shaped
    members (records are copied)."""
    return StreamFrame(
        panes={k: _copy_record(v) for k, v in members.get("panes", {}).items()},
        shadows={k: _copy_record(v) for k, v in members.get("shadows", {}).items()},
        completed=frozenset(members.get("completed", ())),
        sessions={k: dict(v) for k, v in members.get("sessions", {}).items()},
        parked=frozenset(tuple(p) for p in members.get("parked", ())),
        discovery=members.get("discovery", empty_discovery()),
        control_state=members.get("control_state", "stopped"),
    )


# ---------------------------------------------------------------------------
# Server side: StreamEncoder
# ---------------------------------------------------------------------------

_MISSING = object()


def _diff_entries(old: dict, new: dict, path: str) -> tuple[dict, list[str]]:
    changes = {}
    for key, rec in new.items():
        prev = old.get(key)
        if prev is None:
            changes[key] = _copy_record(rec)
            continue
        dropped = set(prev) - set(rec)
        if dropped:
            # A patch can replace members but never remove one. Encoder input
            # records are full and carry content (selection is per subscriber),
            # so a vanishing member is a caller bug, not a wire event.
            raise ValueError(
                f"{path}[{key!r}]: members {sorted(dropped)} disappeared; "
                "encoder frames must carry the same members every generation")
        patch = {k: v for k, v in rec.items() if prev.get(k, _MISSING) != v}
        if patch:
            changes[key] = _copy_record(patch)
    removed = _sorted_ids(set(old) - set(new))
    return changes, removed


class StreamEncoder:
    """Turns successive producer frames into one snapshot/delta stream.

    One encoder per server, encoding FULL content; each subscriber's view is
    :func:`filter_message` of the shared messages. The state starts empty at
    ``gen`` 0; every :meth:`update` emits the next delta."""

    def __init__(self, *, gen: int = 0):
        self._gen = gen
        self._members = _frame_members(StreamFrame())
        self._ts = 0.0

    @property
    def gen(self) -> int:
        return self._gen

    def frame(self) -> StreamFrame:
        return frame_from_members(self._members)

    def update(self, frame: StreamFrame, *, ts: float) -> dict:
        new = _frame_members(frame)
        old = self._members
        delta = {"type": "delta", "gen": self._gen + 1, "ts": _round_s(ts)}
        panes, removed = _diff_entries(old["panes"], new["panes"], "panes")
        if panes:
            delta["panes"] = panes
        if removed:
            delta["removed"] = removed
        shadows, shadows_removed = _diff_entries(old["shadows"], new["shadows"], "shadows")
        if shadows:
            delta["shadows"] = shadows
        if shadows_removed:
            delta["shadows_removed"] = shadows_removed
        for name in TOP_LEVEL_MEMBERS:
            if new[name] != old[name]:
                delta[name] = new[name]
        self._members = new
        self._gen += 1
        self._ts = delta["ts"]
        return delta

    def snapshot(self, *, ts: float | None = None, content=CONTENT_ALL,
                 include_shadows: bool = True, id=None) -> dict:
        return snapshot_message(
            frame_from_members(self._members), gen=self._gen,
            ts=self._ts if ts is None else ts, content=content,
            include_shadows=include_shadows, id=id)


# ---------------------------------------------------------------------------
# Client side: StreamState
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Applied:
    """What one applied message changed, so a client can skip unchanged
    rows. For a snapshot every held id counts as changed."""
    kind: str
    gen: int
    changed: frozenset = frozenset()
    removed: frozenset = frozenset()
    shadows_changed: frozenset = frozenset()
    shadows_removed: frozenset = frozenset()
    members_changed: frozenset = frozenset()


class StreamState:
    """The client's reconstruction of the server's state.

    Enforces the generation rules: a snapshot replaces the state wholesale; a
    delta with ``gen <= state.gen`` is stale and dropped (``apply`` returns
    ``None``); ``gen == state.gen + 1`` applies; anything larger raises
    :class:`StreamGap` (resubscribe); a delta before any snapshot raises. An
    entry for an id the state does not hold must be a full record.

    ``require_content`` (recordings) additionally requires ``content`` on every
    full record."""

    def __init__(self, *, require_content: bool = False):
        self.require_content = require_content
        self.gen: int | None = None
        self.ts: float | None = None
        self._members: dict | None = None

    @property
    def subscribed(self) -> bool:
        return self._members is not None

    def frame(self) -> StreamFrame:
        if self._members is None:
            raise StreamError("no snapshot applied yet")
        return frame_from_members(self._members)

    def _check_full(self, rec: dict, path: str) -> None:
        try:
            _v_full_record(rec, path)
        except ProtocolError as exc:
            raise StreamError(f"not a full record (an entry for an id the state "
                              f"does not hold must be one): {exc}") from None
        if self.require_content and "content" not in rec:
            raise StreamError(f"{path}: full record without content in a full-content stream")

    def apply(self, msg: dict) -> Applied | None:
        kind = msg.get("type")
        if kind == "snapshot":
            for key, rec in msg["panes"].items():
                self._check_full(rec, f"snapshot.panes[{key!r}]")
            for key, rec in msg["shadows"].items():
                self._check_full(rec, f"snapshot.shadows[{key!r}]")
            self._members = {
                "panes": {k: _copy_record(v) for k, v in msg["panes"].items()},
                "shadows": {k: _copy_record(v) for k, v in msg["shadows"].items()},
                "completed": list(msg["completed"]),
                "sessions": {k: dict(v) for k, v in msg["sessions"].items()},
                "parked": [list(p) for p in msg["parked"]],
                "discovery": msg["discovery"],
                "control_state": msg["control_state"],
            }
            self.gen = msg["gen"]
            self.ts = msg["ts"]
            return Applied(
                kind="snapshot", gen=self.gen,
                changed=frozenset(self._members["panes"]),
                shadows_changed=frozenset(self._members["shadows"]),
                members_changed=frozenset(TOP_LEVEL_MEMBERS),
            )
        if kind != "delta":
            raise StreamError(f"cannot apply a {kind!r} message to the stream state")
        if self._members is None:
            raise StreamError("delta before any snapshot")
        gen = msg["gen"]
        if gen <= self.gen:
            return None
        if gen != self.gen + 1:
            raise StreamGap(f"delta gen {gen} after gen {self.gen}: resubscribe")
        # Validate everything before mutating, so a bad delta leaves the state
        # untouched.
        panes = self._members["panes"]
        shadows = self._members["shadows"]
        for key, rec in msg.get("panes", {}).items():
            if key not in panes:
                self._check_full(rec, f"delta.panes[{key!r}]")
        for key, rec in msg.get("shadows", {}).items():
            if key not in shadows:
                self._check_full(rec, f"delta.shadows[{key!r}]")
        changed = self._merge(panes, msg.get("panes", {}))
        removed = self._remove(panes, msg.get("removed", ()))
        shadows_changed = self._merge(shadows, msg.get("shadows", {}))
        shadows_removed = self._remove(shadows, msg.get("shadows_removed", ()))
        members_changed = set()
        for name in TOP_LEVEL_MEMBERS:
            if name in msg:
                self._members[name] = msg[name]
                members_changed.add(name)
        self.gen = gen
        self.ts = msg["ts"]
        return Applied(
            kind="delta", gen=gen, changed=frozenset(changed),
            removed=frozenset(removed), shadows_changed=frozenset(shadows_changed),
            shadows_removed=frozenset(shadows_removed),
            members_changed=frozenset(members_changed),
        )

    @staticmethod
    def _merge(held: dict, entries: dict) -> set:
        for key, rec in entries.items():
            if key in held:
                merged = dict(held[key])
                merged.update(_copy_record(rec))  # member-wholesale, no deep merge
                held[key] = merged
            else:
                held[key] = _copy_record(rec)
        return set(entries)

    @staticmethod
    def _remove(held: dict, ids) -> set:
        gone = set()
        for key in ids:
            if held.pop(key, None) is not None:
                gone.add(key)
        return gone

    # --- read surface -------------------------------------------------------
    #
    # Held records are never mutated in place (a patch builds a new dict), so
    # the maps below share record objects with the state: callers must treat
    # them as read-only.

    def _held(self) -> dict:
        if self._members is None:
            raise StreamError("no snapshot applied yet")
        return self._members

    def records(self) -> dict:
        return dict(self._held()["panes"])

    def shadow_records(self) -> dict:
        return dict(self._held()["shadows"])

    def snapshots(self, now: float | None = None) -> dict[str, PaneSnapshot]:
        stamp = time.monotonic() if now is None else now
        return {k: pane_snapshot(v, timestamp=stamp) for k, v in self._held()["panes"].items()}

    def shadow_snapshots(self, now: float | None = None) -> dict[str, PaneSnapshot]:
        stamp = time.monotonic() if now is None else now
        return {k: pane_snapshot(v, timestamp=stamp) for k, v in self._held()["shadows"].items()}

    @property
    def completed(self) -> frozenset:
        return frozenset(self._held()["completed"])

    @property
    def parked(self) -> frozenset:
        return frozenset(tuple(p) for p in self._held()["parked"])

    @property
    def sessions(self) -> dict:
        return {k: dict(v) for k, v in self._held()["sessions"].items()}

    def session_roots(self) -> dict[str, str]:
        return {k: v["project_root"] for k, v in self._held()["sessions"].items()}

    @property
    def discovery(self) -> dict:
        return self._held()["discovery"]

    @property
    def control_state(self) -> str:
        return self._held()["control_state"]
