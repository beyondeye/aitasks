#!/usr/bin/env python3
"""agent_sessions.py - lock-free primitive for the framework session store (t1705_2).

One machine-wide record per code agent, across every aitasks tmux session and
project, plus the lifecycle state machine the freeze engine (t1705_4), the
restore coordinator (t1705_5), the viewer (t1705_6) and the monitors (t1705_7)
all drive. The store lives at ``~/.config/aitasks/agent_sessions.json``
(override with ``AITASKS_AGENT_SESSIONS_FILE``); captures live under
``~/.config/aitasks/frozen/<id>/`` (override with ``AITASKS_FROZEN_DIR``).

Mirrored 1:1 on ``lib/agent_marks.py`` / ``aitask_agent_marks.sh``: this module
is the lock-free primitive and ``aitask_agent_sessions.sh`` is the SOLE writer,
holding the ``registry_lock.sh`` mutex around a read-modify-write. Readers (the
TUIs) read the JSON directly with no lock: every write lands via ``os.replace``,
so a reader always observes one whole generation.

THIS MODULE NEVER TOUCHES TMUX. It imports no tmux and spawns no process. The
pane->record join (``@aitask_record``) is stamped by the *caller* -- the
SessionStart hook (t1705_3) and the freeze engine (t1705_4) -- immediately after
a successful ``UPSERTED:`` line, using ``ait_stamp_record`` in
``lib/agent_sessions.sh``. See that helper; the split is deliberate, because
``tests/test_no_raw_tmux.sh`` permits raw ``tmux`` only from the two gateways.

Transitions are PURE: ``(store, args) -> (store', wire_line)``. They never read
or write the file; the shell wrapper does load -> transition -> dump and prints
the wire line. That is what lets the whole state machine be tested with no
filesystem and no tmux.
"""
from __future__ import annotations

import errno
import json
import os
import re
import shutil
import stat
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atomic_write  # noqa: E402

SESSIONS_ENV = "AITASKS_AGENT_SESSIONS_FILE"
DEFAULT_SESSIONS_PATH = "~/.config/aitasks/agent_sessions.json"
FROZEN_DIR_ENV = "AITASKS_FROZEN_DIR"
DEFAULT_FROZEN_DIR = "~/.config/aitasks/frozen"
#: Documented TEST SEAM. Production never sets it; see :func:`standin_command`.
STANDIN_CMD_ENV = "AITASKS_FROZEN_STANDIN_CMD"

SCHEMA_VERSION = 1
OLDEST_READABLE_VERSION = 1

STATE_LIVE = "live"
STATE_FREEZING = "freezing"
STATE_FROZEN = "frozen"
STATE_RESTORING = "restoring"
STATE_ABORTING = "aborting"
STATES = (STATE_LIVE, STATE_FREEZING, STATE_FROZEN, STATE_RESTORING, STATE_ABORTING)

#: States mid-transaction. Never relocated by an unstamped caller, never purged
#: by liveness -- only `aitask_frozen.sh reconcile` resolves them.
TRANSITIONAL_STATES = (STATE_FREEZING, STATE_RESTORING, STATE_ABORTING)

RESTORE_MODES = ("resume", "repick")

_FILE_MODE = 0o600
_DIR_MODE = 0o700

#: Seconds before an operation lease with a dead owner may be taken over.
STALE_OP_GRACE_DEFAULT = 60.0

#: Canonical record id / operation nonce: 8 lowercase hex, from os.urandom(4).
#:
#: Format is load-bearing, not cosmetic (t1705_2 A9). Both values escape into
#: `capture_dir()` -- whose `drop` deletes the tree -- and into
#: `standin_command()`, whose output is handed to `respawn-pane` as a SHELL
#: COMMAND STRING. A `../` or a quote in either would escape the frozen root or
#: inject into the respawn. `os.urandom(4).hex()` can only ever emit this shape,
#: so anything else means a hand-edited store or a hostile pane option.
_ID_RE = re.compile(r"[0-9a-f]{8}")

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"

_AGENT_STRING_RE = re.compile(r"([a-z]+)/[a-z0-9_]+")


class MalformedSessionsError(Exception):
    """The store is corrupt or unreadable. Maps to wrapper exit 4."""


class TransitionRefused(Exception):
    """Illegal (state, verb) pair. Maps to wrapper exit 5; nothing is written."""


class NonceMismatch(Exception):
    """A leased verb carried the wrong nonce. Maps to wrapper exit 6."""


class SessionMismatch(Exception):
    """A `resume` ack reported a different session id. Maps to wrapper exit 7.

    The store has ALREADY persisted ``last_error`` when this is raised -- the
    hook has no return channel to the detached coordinator, so the record is
    the channel.
    """


class LeaseHeld(Exception):
    """A live lease blocks the take-over. Maps to wrapper exit 8."""


# --- schema -----------------------------------------------------------------


@dataclass
class SessionRecord:
    """One code agent. See the t1705 pinned schema; field names match it 1:1."""

    id: str
    root: str
    window: str
    window_slot: int = 0
    pane_id: str = ""
    pane_pid: int = 0
    session: str = ""
    operation: str = ""
    task_id: str = ""
    agent_string: str = ""
    agent_kind: str = ""
    codeagent_session_id: str = ""
    transcript_path: str = ""
    started_at: str = ""
    state: str = STATE_LIVE
    state_at: str = ""
    op_nonce: str = ""
    op_owner_pid: int = 0
    op_started_at: str = ""
    frozen_at: str = ""
    capture_ansi: str = ""
    capture_txt: str = ""
    capture_lines: int = 0
    last_phase: str = ""
    standin_pid: int = 0
    launch_pid: int = 0
    restore_attempts: int = 0
    restore_mode: str = ""
    ack: str = ""
    last_error: str = ""

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.root, self.window, self.window_slot)


@dataclass
class SessionsFile:
    version: int = SCHEMA_VERSION
    sessions: list[SessionRecord] = field(default_factory=list)

    def by_id(self, record_id: str) -> SessionRecord | None:
        for rec in self.sessions:
            if rec.id == record_id:
                return rec
        return None

    def at(self, root: str, window: str) -> list[SessionRecord]:
        """Every record sharing a ``(root, window)``, in slot order."""
        return sorted(
            (r for r in self.sessions if r.root == root and r.window == window),
            key=lambda r: r.window_slot,
        )


def _empty() -> SessionsFile:
    return SessionsFile(version=SCHEMA_VERSION, sessions=[])


# --- paths / identity -------------------------------------------------------


def valid_id(value: object) -> bool:
    """True for a canonical 8-hex record id / nonce.

    An EMPTY string is never a valid id, but IS a valid *empty nonce* (meaning
    "no lease") -- callers that accept the empty form check for it explicitly.
    """
    return isinstance(value, str) and _ID_RE.fullmatch(value) is not None


def sessions_path(path: str | os.PathLike | None = None) -> Path:
    """Resolve the store path: explicit arg > ``$AITASKS_AGENT_SESSIONS_FILE`` >
    default. Not ``realpath``-ed here -- :func:`dump` does that at the write
    site, and a caller may legitimately point at a symlink."""
    if path is not None:
        return Path(path)
    env = os.environ.get(SESSIONS_ENV)
    if env:
        return Path(env)
    return Path(os.path.expanduser(DEFAULT_SESSIONS_PATH))


def frozen_root() -> Path:
    """Directory holding every record's capture files."""
    env = os.environ.get(FROZEN_DIR_ENV)
    if env:
        return Path(env)
    return Path(os.path.expanduser(DEFAULT_FROZEN_DIR))


def record_key(root: str | os.PathLike, window: str, slot: int = 0) -> tuple[str, str, int]:
    """Canonical identity for an agent slot.

    ``realpath`` is applied on BOTH the write and the read side: a record
    written from a symlinked checkout must match a read that resolved the real
    path, and vice versa. Canonicalizing on only one side is the classic way two
    spellings of the same repo end up with two independent records.
    """
    return (os.path.realpath(str(root)), window, int(slot))


def capture_dir(record_id: str) -> Path:
    """The capture directory for a record, guaranteed to sit under the root.

    The containment assertion is defence in depth, not belt-and-braces: `drop`
    and `freeze-abort` both DELETE this directory, so an id that escaped the
    boundary checks would delete outside the frozen root. `_parse` and the CLI
    both validate ids, and this is the third and last line (t1705_2 A9).
    """
    if not valid_id(record_id):
        raise ValueError(f"not a canonical record id: {record_id!r}")
    root = Path(os.path.realpath(frozen_root()))
    candidate = root / record_id
    resolved = os.path.realpath(candidate)
    if resolved != str(root) and not resolved.startswith(str(root) + os.sep):
        raise ValueError(f"capture dir escapes {root}: {resolved}")
    return candidate


def ensure_capture_dir(record_id: str) -> Path:
    """Create the capture directory 0700.

    ``makedirs(mode=)`` is masked by the umask, so the mode is set explicitly
    afterwards -- the same trap :func:`dump` avoids for the store file.
    """
    d = capture_dir(record_id)
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, _DIR_MODE)
    except OSError:
        pass
    return d


def remove_captures(record_id: str) -> None:
    """Best-effort removal of a record's capture directory."""
    try:
        shutil.rmtree(capture_dir(record_id))
    except (OSError, ValueError):
        pass


def standin_command(record_id: str) -> str:
    """The command a frozen pane's stand-in viewer runs.

    ``AITASKS_FROZEN_STANDIN_CMD`` is a documented TEST SEAM so a suite can
    swap in a harmless process; production never sets it.
    """
    if not valid_id(record_id):
        raise ValueError(f"not a canonical record id: {record_id!r}")
    override = os.environ.get(STANDIN_CMD_ENV)
    if override:
        return override
    return f"ait frozenagent --record {record_id}"


def agent_kind_of(agent_string: str | None) -> str:
    """Derive the agent kind from an agent string, non-fatally.

    ``lib/agent_string.sh::parse_agent_string`` is bash-only and ``die``s on a
    malformed value; there is no Python equivalent. Deliberately NOT validated
    against ``SUPPORTED_AGENTS``: the field is display-only, and the store must
    not reject a record because a new agent shipped (t1705_2 A5).
    """
    m = _AGENT_STRING_RE.fullmatch(agent_string or "")
    return m.group(1) if m else ""


# --- timestamps -------------------------------------------------------------


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _iso(epoch: float | None = None) -> str:
    if epoch is None:
        epoch = _now()
    return datetime.fromtimestamp(epoch, timezone.utc).strftime(_TS_FMT)


def _epoch(iso: str) -> float:
    """Epoch seconds for an ISO stamp; 0.0 for an empty or unparseable one."""
    if not iso:
        return 0.0
    try:
        return datetime.strptime(iso, _TS_FMT).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return 0.0


# --- liveness predicates ----------------------------------------------------


def _pid_alive(pid: int) -> bool:
    """Is ``pid`` running?

    Fail-closed: only ``ESRCH`` proves death. ``EPERM`` means the process
    exists but belongs to someone else, and any other error is unverifiable --
    both are treated as ALIVE, because wrongly declaring a live coordinator
    dead lets reconcile seize its work.
    """
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        return True
    return True


# --- serialization ----------------------------------------------------------


def _need_str(entry: dict, name: str, *, allow_empty: bool = True) -> str:
    value = entry.get(name, "")
    if not isinstance(value, str):
        raise MalformedSessionsError(f"bad {name!r} in entry: {entry!r}")
    if not allow_empty and not value:
        raise MalformedSessionsError(f"empty {name!r} in entry: {entry!r}")
    return value


def _need_ts(entry: dict, name: str) -> str:
    """A timestamp field: empty, or exactly the canonical ``_TS_FMT``.

    "Non-empty" is not enough, because :func:`_epoch` maps an unparseable stamp
    to ``0.0`` -- so a lease carrying ``op_started_at="not-a-timestamp"`` would
    load fine and then read as *stale* on the very first check, since a grace
    measured from epoch 0 has always elapsed. Reconcile would then take over an
    operation a live coordinator still owns. That is the same fail-open shape as
    a zero ``op_owner_pid`` (A13), reached through a different field, so it fails
    closed the same way.

    Applied to EVERY timestamp field rather than only the load-bearing one: they
    are all written by :func:`_iso`, which emits nothing else, so any other value
    is a hand-edit; and ``state_at`` feeds the restore-ack grace in the
    coordinator (§C/§D), so the "display only" fields are not a stable category
    to carve out.
    """
    value = _need_str(entry, name)
    if value:
        try:
            datetime.strptime(value, _TS_FMT)
        except ValueError as exc:
            raise MalformedSessionsError(
                f"bad {name!r} (want {_TS_FMT}): {value!r} in entry: {entry!r}"
            ) from exc
    return value


def _need_int(entry: dict, name: str) -> int:
    value = entry.get(name, 0)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MalformedSessionsError(f"bad {name!r} in entry: {entry!r}")
    return value


def _parse(text: str) -> SessionsFile:
    """Parse store JSON, raising :class:`MalformedSessionsError` on anything odd."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise MalformedSessionsError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MalformedSessionsError("top level is not an object")

    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise MalformedSessionsError(f"missing or non-integer version: {version!r}")
    if version > SCHEMA_VERSION or version < OLDEST_READABLE_VERSION:
        raise MalformedSessionsError(
            f"unsupported store version {version} "
            f"(readable: {OLDEST_READABLE_VERSION}..{SCHEMA_VERSION})"
        )

    raw = data.get("sessions")
    if not isinstance(raw, list):
        raise MalformedSessionsError("'sessions' is not a list")

    records: list[SessionRecord] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise MalformedSessionsError(f"session entry is not an object: {entry!r}")

        rid = entry.get("id")
        if not valid_id(rid):
            raise MalformedSessionsError(f"bad 'id' in entry: {entry!r}")
        # First spelling wins; a duplicate is not a corruption.
        if rid in seen:
            continue
        seen.add(rid)

        root = _need_str(entry, "root", allow_empty=False)
        window = _need_str(entry, "window", allow_empty=False)

        state = entry.get("state", STATE_LIVE)
        # A PRESENT but unrecognised state is corruption, not a default: every
        # transition branches on it, so silently defaulting would move a frozen
        # agent back into the live population.
        if state not in STATES:
            raise MalformedSessionsError(f"bad 'state' in entry: {entry!r}")

        nonce = entry.get("op_nonce", "")
        # "" is the legal EMPTY nonce (no lease); anything else must be canonical.
        if nonce != "" and not valid_id(nonce):
            raise MalformedSessionsError(f"bad 'op_nonce' in entry: {entry!r}")

        owner_pid = _need_int(entry, "op_owner_pid")
        if owner_pid < 0:
            raise MalformedSessionsError(f"negative 'op_owner_pid': {entry!r}")

        # The lease is a TRIPLE, written and cleared as a unit by `_mint_lease`
        # / `_clear_lease`. A half-set lease is corruption, not a tolerable
        # oddity: `_lease_stale` is `grace elapsed AND owner dead`, and both
        # broken halves collapse it to "stale" -- an `op_owner_pid` of 0 is
        # never alive, and an empty `op_started_at` epochs to 0.0 so the grace
        # is always long past. Either way a record that is genuinely leased
        # reads as free, and reconcile steals an operation from a live
        # coordinator. That is the A7 failure reached through the store rather
        # than through the wrapper, so it fails closed here too.
        started = _need_ts(entry, "op_started_at")
        leased = (nonce != "", owner_pid != 0, started != "")
        if len(set(leased)) != 1:
            raise MalformedSessionsError(
                "incoherent lease (op_nonce / op_owner_pid / op_started_at must "
                f"be all set or all empty) in entry: {entry!r}"
            )

        restore_mode = _need_str(entry, "restore_mode")
        if restore_mode and restore_mode not in RESTORE_MODES:
            raise MalformedSessionsError(f"bad 'restore_mode' in entry: {entry!r}")

        records.append(
            SessionRecord(
                id=rid,
                # Canonicalize on read too: an entry hand-edited with a
                # symlinked path must still match a strictly-resolved lookup.
                root=os.path.realpath(root),
                window=window,
                window_slot=_need_int(entry, "window_slot"),
                pane_id=_need_str(entry, "pane_id"),
                pane_pid=_need_int(entry, "pane_pid"),
                session=_need_str(entry, "session"),
                operation=_need_str(entry, "operation"),
                task_id=_need_str(entry, "task_id"),
                agent_string=_need_str(entry, "agent_string"),
                agent_kind=_need_str(entry, "agent_kind"),
                codeagent_session_id=_need_str(entry, "codeagent_session_id"),
                transcript_path=_need_str(entry, "transcript_path"),
                started_at=_need_ts(entry, "started_at"),
                state=state,
                state_at=_need_ts(entry, "state_at"),
                op_nonce=nonce,
                op_owner_pid=owner_pid,
                op_started_at=started,
                frozen_at=_need_ts(entry, "frozen_at"),
                capture_ansi=_need_str(entry, "capture_ansi"),
                capture_txt=_need_str(entry, "capture_txt"),
                capture_lines=_need_int(entry, "capture_lines"),
                last_phase=_need_str(entry, "last_phase"),
                standin_pid=_need_int(entry, "standin_pid"),
                launch_pid=_need_int(entry, "launch_pid"),
                restore_attempts=_need_int(entry, "restore_attempts"),
                restore_mode=restore_mode,
                ack=_need_str(entry, "ack"),
                last_error=_need_str(entry, "last_error"),
            )
        )
    return SessionsFile(version=SCHEMA_VERSION, sessions=records)


def load(path: str | os.PathLike | None = None) -> SessionsFile:
    """Read the store, raising on corruption. **The write path uses this.**

    A missing or empty file is not corruption -- it is an empty store, which is
    exactly what the first-ever upsert should build on.
    """
    target = sessions_path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _empty()
    except IsADirectoryError as exc:
        raise MalformedSessionsError(f"{target} is a directory") from exc
    except OSError as exc:
        raise MalformedSessionsError(f"cannot read {target}: {exc}") from exc
    if not text.strip():
        return _empty()
    return _parse(text)


def load_safe(path: str | os.PathLike | None = None) -> SessionsFile:
    """Read the store, never raising. **The TUI read path uses this.**"""
    try:
        return load(path)
    except (MalformedSessionsError, OSError):
        return _empty()


def _target_mode(path: str) -> int:
    """Preserve an existing file's mode; default to 0600 for a new store.

    NOT ``atomic_write.target_mode``: that one defaults to ``0o666 & ~umask``
    for a file that does not exist yet, which would land the first-ever store
    at 0644 under the default umask. This store holds transcript paths and
    codeagent session ids (t1705_2 A2).
    """
    try:
        return stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return _FILE_MODE


def dump(sf: SessionsFile, path: str | os.PathLike | None = None) -> None:
    """Atomically replace the store, preserving 0600.

    ``atomic_write.prepare`` stages a temp beside the target and ``commit``
    renames it, so a concurrent reader never sees a partial file. The mode is
    set on the TEMP, before the rename -- there is no window in which the store
    is world-readable.
    """
    resolved = os.path.realpath(sessions_path(path))
    mode = _target_mode(resolved)
    payload = {
        "version": SCHEMA_VERSION,
        "sessions": [
            {
                "id": r.id,
                "root": r.root,
                "window": r.window,
                "window_slot": r.window_slot,
                "pane_id": r.pane_id,
                "pane_pid": r.pane_pid,
                "session": r.session,
                "operation": r.operation,
                "task_id": r.task_id,
                "agent_string": r.agent_string,
                "agent_kind": r.agent_kind,
                "codeagent_session_id": r.codeagent_session_id,
                "transcript_path": r.transcript_path,
                "started_at": r.started_at,
                "state": r.state,
                "state_at": r.state_at,
                "op_nonce": r.op_nonce,
                "op_owner_pid": r.op_owner_pid,
                "op_started_at": r.op_started_at,
                "frozen_at": r.frozen_at,
                "capture_ansi": r.capture_ansi,
                "capture_txt": r.capture_txt,
                "capture_lines": r.capture_lines,
                "last_phase": r.last_phase,
                "standin_pid": r.standin_pid,
                "launch_pid": r.launch_pid,
                "restore_attempts": r.restore_attempts,
                "restore_mode": r.restore_mode,
                "ack": r.ack,
                "last_error": r.last_error,
            }
            for r in sorted(sf.sessions, key=lambda r: r.key)
        ],
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    tmp = atomic_write.prepare(resolved, lambda fh: fh.write(text))
    try:
        os.chmod(tmp, mode)
    except BaseException:
        atomic_write.discard(tmp)
        raise
    atomic_write.commit(tmp, resolved)


# --- lease ------------------------------------------------------------------


def _mint_nonce() -> str:
    return os.urandom(4).hex()


def _stale_op_grace() -> float:
    """The lease grace, with a TEST-ONLY override (t1705_4).

    ``AITASKS_STALE_OP_GRACE`` is honoured **only** under
    ``AITASKS_TEST_MODE=1``, and only for a positive float. Without the seam the
    live lease-takeover cases would have to sleep past
    ``STALE_OP_GRACE_DEFAULT`` (60 s) twice per run; with it they finish in
    seconds. Gating on the test-mode flag is what stops a stray env var in a
    developer's shell from reconfiguring a real coordinator's lease.

    This shortens only the TIMER half of :func:`_lease_stale`. The liveness half
    is deliberately untouched: the rule is ``grace elapsed AND owner dead``, and
    a shortened grace must never become a way to seize a live owner.
    """
    if os.environ.get("AITASKS_TEST_MODE") != "1":
        return STALE_OP_GRACE_DEFAULT
    raw = os.environ.get("AITASKS_STALE_OP_GRACE", "")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return STALE_OP_GRACE_DEFAULT
    # Non-positive would make every lease instantly stale, which is the one
    # value a test could set by accident and never notice.
    return value if value > 0 else STALE_OP_GRACE_DEFAULT


def _lease_stale(rec: SessionRecord, now: float, pid_alive=None) -> bool:
    """True when a lease may be taken over: grace elapsed AND owner gone.

    Both terms matter. The grace alone would let reconcile seize a slow but
    healthy coordinator; the pid alone would let it seize one that had only
    just started. This is also why ``op_owner_pid`` must be the COORDINATOR's
    pid and never the ephemeral wrapper's -- with an always-dead pid the
    conjunction collapses to a bare timer (t1705_2 A7).
    """
    alive = pid_alive or _pid_alive
    if not rec.op_nonce:
        return True  # no lease at all
    if _epoch(rec.op_started_at) + _stale_op_grace() >= now:
        return False
    return not alive(rec.op_owner_pid)


def _require_nonce(rec: SessionRecord, nonce: str) -> None:
    if not nonce or nonce != rec.op_nonce:
        raise NonceMismatch(f"NONCE_MISMATCH:{rec.id}")


def _require_state(rec: SessionRecord, verb: str, *legal: str) -> None:
    if rec.state not in legal:
        raise TransitionRefused(f"TRANSITION_REFUSED:{rec.id}|{rec.state}|{verb}")


def _require_record(sf: SessionsFile, record_id: str) -> SessionRecord:
    if not valid_id(record_id):
        raise ValueError(f"not a canonical record id: {record_id!r}")
    rec = sf.by_id(record_id)
    if rec is None:
        raise MalformedSessionsError(f"no such record: {record_id}")
    return rec


def _mint_lease(rec: SessionRecord, owner_pid: int, now: float) -> str:
    nonce = _mint_nonce()
    rec.op_nonce = nonce
    rec.op_owner_pid = int(owner_pid)
    rec.op_started_at = _iso(now)
    return nonce


def _clear_lease(rec: SessionRecord) -> None:
    rec.op_nonce = ""
    rec.op_owner_pid = 0
    rec.op_started_at = ""


def _set_state(rec: SessionRecord, state: str, now: float) -> None:
    rec.state = state
    rec.state_at = _iso(now)


def _set_location(rec: SessionRecord, pane: str, pane_pid: int) -> None:
    rec.pane_id = pane
    rec.pane_pid = int(pane_pid)


# --- upsert: identity + conflict policy -------------------------------------

#: Refusal reason per selected state (t1705_2 A4 / plan §C2). A record is
#: SELECTED by `--id` or by pane identity; one that merely shares
#: `(root, window)` is not a candidate and falls through to the create rules.
_UPSERT_REFUSALS = {
    STATE_FREEZING: "freezing_unacknowledged",
    STATE_RESTORING: "restoring_unacknowledged",
    STATE_ABORTING: "aborting_unacknowledged",
    STATE_FROZEN: "frozen",
}


def _next_slot(sf: SessionsFile, root: str, window: str) -> int:
    used = {r.window_slot for r in sf.at(root, window)}
    slot = 0
    while slot in used:
        slot += 1
    return slot


def _apply_upsert_fields(
    rec: SessionRecord,
    *,
    session=None,
    session_id=None,
    transcript=None,
    agent_string=None,
    operation=None,
    task_id=None,
) -> None:
    """Apply the optional descriptive fields. ``None`` means "not supplied"."""
    if session is not None:
        rec.session = session
    if session_id is not None:
        rec.codeagent_session_id = session_id
    if transcript is not None:
        rec.transcript_path = transcript
    if agent_string is not None:
        rec.agent_string = agent_string
        rec.agent_kind = agent_kind_of(agent_string)
    if operation is not None:
        rec.operation = operation
    if task_id is not None:
        rec.task_id = task_id


def upsert(
    sf: SessionsFile,
    *,
    root: str,
    window: str,
    pane: str,
    pane_pid: int,
    id: str | None = None,
    session: str | None = None,
    session_id: str | None = None,
    transcript: str | None = None,
    agent_string: str | None = None,
    operation: str | None = None,
    task_id: str | None = None,
    restore_of: str | None = None,
    nonce: str | None = None,
    now: float | None = None,
    pane_alive=None,
) -> tuple[SessionsFile, str]:
    """The ONLY creator of records. See the pinned conflict policy.

    Resolution order for a caller without ``restore_of``:

    1. ``id`` (from ``@aitask_record`` on the caller's pane) -> that record,
       whatever its ``(root, window)``: a renamed window keeps its record.
    2. Else, among the ``(root, window)`` records, the one whose ``pane_id`` is
       the caller's pane, else the ``live`` ones whose ``pane_pid`` is dead.
       EXACTLY ONE -> the same agent slot, relocated. MORE THAN ONE -> fail
       closed and create beside them (``ambiguous_relocation``); nothing on the
       caller's side can tell two pre-restart agents apart, so guessing would
       silently adopt the wrong record.
    3. Else -> create beside the existing records (``created_slot<N>``).
    4. Else -> create (``created``).
    """
    now = _now() if now is None else now
    alive = pane_alive or _pid_alive
    croot = os.path.realpath(root)

    # --- the restore acknowledgement ----------------------------------------
    if restore_of is not None:
        rec = _require_record(sf, restore_of)
        _require_state(rec, "upsert", STATE_RESTORING)
        _require_nonce(rec, nonce or "")
        if rec.restore_mode == "resume" and (session_id or "") != rec.codeagent_session_id:
            # The hook has no return channel to the detached coordinator, so
            # the RECORD is the channel: persist, then raise. Both the
            # coordinator and reconcile read `last_error` for the current nonce
            # and take the abort branch, never the liveness fallback.
            rec.last_error = f"{rec.op_nonce}:session_mismatch"
            raise SessionMismatch(f"RESTORE_SESSION_MISMATCH:{rec.id}")
        _apply_upsert_fields(
            rec,
            session=session,
            session_id=session_id,
            transcript=transcript,
            agent_string=agent_string,
            operation=operation,
            task_id=task_id,
        )
        _set_location(rec, pane, pane_pid)
        _set_state(rec, STATE_LIVE, now)
        rec.ack = "hook"
        rec.last_error = ""
        # Captures are deleted ONLY on a verified ack. A liveness-only confirm
        # keeps them, which is what stops a malformed resume that starts a
        # fresh session from destroying the only copy.
        remove_captures(rec.id)
        rec.capture_ansi = ""
        rec.capture_txt = ""
        rec.capture_lines = 0
        _clear_lease(rec)
        return sf, f"UPSERTED:{rec.id}|restored"

    # --- selection ----------------------------------------------------------
    selected: SessionRecord | None = None
    if id is not None:
        selected = _require_record(sf, id)
    else:
        siblings = sf.at(croot, window)
        by_pane = [r for r in siblings if pane and r.pane_id == pane]
        if by_pane:
            selected = by_pane[0]
        else:
            dead = [r for r in siblings if r.state == STATE_LIVE and not alive(r.pane_pid)]
            if len(dead) == 1:
                selected = dead[0]
            elif len(dead) > 1:
                # Fail closed on relocation: two agents shared this window
                # before a server restart and nothing distinguishes them. The
                # stale records are left for the liveness purge, never guessed.
                rec = _create(
                    sf, croot, window, pane, pane_pid, now,
                    session=session, session_id=session_id, transcript=transcript,
                    agent_string=agent_string, operation=operation, task_id=task_id,
                )
                return sf, f"UPSERTED:{rec.id}|created_slot{rec.window_slot}|ambiguous_relocation"

    if selected is not None:
        if selected.state != STATE_LIVE:
            reason = _UPSERT_REFUSALS[selected.state]
            return sf, f"UPSERT_REFUSED:{selected.id}|{reason}"
        _apply_upsert_fields(
            selected,
            session=session,
            session_id=session_id,
            transcript=transcript,
            agent_string=agent_string,
            operation=operation,
            task_id=task_id,
        )
        # Follow a renamed window. `id` is the PRIMARY KEY and rule 1 says a
        # renamed window keeps its record -- but "keeps" only holds if the
        # record's own `(root, window)` follows the rename. Left stale, the very
        # next liveness purge sees a window that no longer exists, drops the
        # record as `dead_window`, and the agent silently becomes unfreezable
        # and unrestorable. The slot is re-allocated when the pair actually
        # changes, since the old slot number means nothing under the new key.
        if (selected.root, selected.window) != (croot, window):
            others = [r for r in sf.at(croot, window) if r.id != selected.id]
            used = {r.window_slot for r in others}
            slot = 0
            while slot in used:
                slot += 1
            selected.root = croot
            selected.window = window
            selected.window_slot = slot
        _set_location(selected, pane, pane_pid)
        return sf, f"UPSERTED:{selected.id}|updated"

    # --- create -------------------------------------------------------------
    existing = sf.at(croot, window)
    rec = _create(
        sf, croot, window, pane, pane_pid, now,
        session=session, session_id=session_id, transcript=transcript,
        agent_string=agent_string, operation=operation, task_id=task_id,
    )
    if existing:
        return sf, f"UPSERTED:{rec.id}|created_slot{rec.window_slot}"
    return sf, f"UPSERTED:{rec.id}|created"


def _create(
    sf: SessionsFile,
    croot: str,
    window: str,
    pane: str,
    pane_pid: int,
    now: float,
    **fields,
) -> SessionRecord:
    rec = SessionRecord(
        id=_mint_nonce(),
        root=croot,
        window=window,
        window_slot=_next_slot(sf, croot, window),
        pane_id=pane,
        pane_pid=int(pane_pid),
        state=STATE_LIVE,
        state_at=_iso(now),
        started_at=_iso(now),
    )
    _apply_upsert_fields(rec, **fields)
    sf.sessions.append(rec)
    return rec


# --- transitions ------------------------------------------------------------


def freeze_begin(
    sf: SessionsFile,
    record_id: str,
    *,
    capture_ansi: str,
    capture_txt: str,
    lines: int,
    phase: str = "",
    owner_pid: int,
    now: float | None = None,
) -> tuple[SessionsFile, str]:
    """live -> freezing. Mints the lease."""
    now = _now() if now is None else now
    rec = _require_record(sf, record_id)
    _require_state(rec, "freeze-begin", STATE_LIVE)
    rec.capture_ansi = capture_ansi
    rec.capture_txt = capture_txt
    rec.capture_lines = int(lines)
    rec.last_phase = phase
    _set_state(rec, STATE_FREEZING, now)
    nonce = _mint_lease(rec, owner_pid, now)
    return sf, f"FREEZING:{rec.id}|{nonce}"


def freeze_commit(
    sf: SessionsFile,
    record_id: str,
    *,
    nonce: str,
    pane: str,
    pane_pid: int,
    now: float | None = None,
) -> tuple[SessionsFile, str]:
    """freezing -> frozen. Records the stand-in's location; clears the lease."""
    now = _now() if now is None else now
    rec = _require_record(sf, record_id)
    _require_state(rec, "freeze-commit", STATE_FREEZING)
    _require_nonce(rec, nonce)
    _set_location(rec, pane, pane_pid)
    rec.standin_pid = int(pane_pid)
    rec.frozen_at = _iso(now)
    _set_state(rec, STATE_FROZEN, now)
    _clear_lease(rec)
    return sf, f"FROZEN:{rec.id}"


def freeze_abort(
    sf: SessionsFile, record_id: str, *, nonce: str, now: float | None = None
) -> tuple[SessionsFile, str]:
    """freezing -> live. Captures are deleted: the agent never left."""
    now = _now() if now is None else now
    rec = _require_record(sf, record_id)
    _require_state(rec, "freeze-abort", STATE_FREEZING)
    _require_nonce(rec, nonce)
    remove_captures(rec.id)
    rec.capture_ansi = ""
    rec.capture_txt = ""
    rec.capture_lines = 0
    _set_state(rec, STATE_LIVE, now)
    _clear_lease(rec)
    return sf, f"LIVE:{rec.id}"


def restore_begin(
    sf: SessionsFile,
    record_id: str,
    *,
    mode: str,
    owner_pid: int,
    now: float | None = None,
    pid_alive=None,
) -> tuple[SessionsFile, str]:
    """frozen -> restoring. Captures RETAINED. Mints the lease.

    Deliberately NOT legal from ``aborting``: that state is nonce-owned by the
    aborting attempt until its stand-in is back, so a user or a second
    controller cannot start another restore in the gap.

    **It also refuses a record whose lease is held** (t1705_6). Before that it
    minted unconditionally, walking over an existing claim -- which made a
    holder's claim merely *detect* a concurrent restore instead of preventing
    one. That is not enough for a DESTRUCTIVE holder: `aitask_frozen.sh drop`
    claims the record, checks the pane, and then kills it, and a restore
    squeezing into that window respawns a REPLACEMENT AGENT into the same pane
    -- which the drop then kills. Detecting the race afterwards does not undo a
    killed agent. The same two-term staleness rule `lease_take` uses applies, so
    a crashed coordinator's lease is still taken over and a record can never
    become permanently un-restorable.
    """
    now = _now() if now is None else now
    if mode not in RESTORE_MODES:
        raise ValueError(f"bad restore mode: {mode!r}")
    rec = _require_record(sf, record_id)
    _require_state(rec, "restore-begin", STATE_FROZEN)
    if not _lease_stale(rec, now, pid_alive):
        raise LeaseHeld(f"LEASE_HELD:{rec.id}")
    rec.restore_mode = mode
    rec.restore_attempts += 1
    rec.launch_pid = 0
    rec.last_error = ""
    rec.ack = ""
    _set_state(rec, STATE_RESTORING, now)
    nonce = _mint_lease(rec, owner_pid, now)
    return sf, f"RESTORING:{rec.id}|{nonce}"


def restore_launched(
    sf: SessionsFile,
    record_id: str,
    *,
    nonce: str,
    pane: str,
    pane_pid: int,
    now: float | None = None,
) -> tuple[SessionsFile, str]:
    """Nonce-bound evidence that a replacement agent was actually started."""
    now = _now() if now is None else now
    rec = _require_record(sf, record_id)
    _require_state(rec, "restore-launched", STATE_RESTORING)
    _require_nonce(rec, nonce)
    _set_location(rec, pane, pane_pid)
    rec.launch_pid = int(pane_pid)
    return sf, f"LAUNCHED:{rec.id}"


def restore_confirm(
    sf: SessionsFile,
    record_id: str,
    *,
    nonce: str,
    pane: str,
    pane_pid: int,
    now: float | None = None,
) -> tuple[SessionsFile, str]:
    """restoring -> live by LIVENESS. Captures are KEPT.

    Requires positive evidence that the process in the pane is the one the
    coordinator launched: ``launch_pid`` must be set and equal to the observed
    pid. Without that, a stand-in viewer or an unrelated process could be
    confirmed as a restored agent.
    """
    now = _now() if now is None else now
    rec = _require_record(sf, record_id)
    _require_state(rec, "restore-confirm", STATE_RESTORING)
    _require_nonce(rec, nonce)
    if rec.launch_pid == 0 or rec.launch_pid != int(pane_pid):
        raise TransitionRefused(
            f"TRANSITION_REFUSED:{rec.id}|{rec.state}|restore-confirm"
        )
    _set_location(rec, pane, pane_pid)
    _set_state(rec, STATE_LIVE, now)
    rec.ack = "liveness"
    _clear_lease(rec)
    return sf, f"LIVE:{rec.id}|liveness"


def restore_abort(
    sf: SessionsFile, record_id: str, *, nonce: str, error: str = "",
    now: float | None = None,
) -> tuple[SessionsFile, str]:
    """restoring -> aborting. Captures retained; the lease stays with this nonce.

    ``error`` PERSISTS why the attempt failed, stamped with this attempt's nonce
    in the documented ``"<nonce>:<reason>"`` shape (t1705_6). Before it, only the
    hook's ``session_mismatch`` was ever recorded: every other failure —
    ``agent_exited`` chief among them, the ordinary "the resumed agent died
    immediately" case — left ``last_error`` empty. The coordinator prints its
    reason to a detached `run-shell` job whose stdout nobody reads, and the
    viewer that dispatched the restore is REPLACED by the respawned stand-in, so
    without persisting it the outcome was unobservable to the user: a fresh
    viewer mounted on a `frozen` record with no indication the restore had even
    been attempted.
    """
    now = _now() if now is None else now
    rec = _require_record(sf, record_id)
    _require_state(rec, "restore-abort", STATE_RESTORING)
    _require_nonce(rec, nonce)
    if error:
        rec.last_error = f"{nonce}:{error}"
    _set_state(rec, STATE_ABORTING, now)
    return sf, f"ABORTING:{rec.id}"


def standin_respawned(
    sf: SessionsFile,
    record_id: str,
    *,
    nonce: str,
    pane: str,
    pane_pid: int,
    now: float | None = None,
) -> tuple[SessionsFile, str]:
    """Record a (re)spawned stand-in viewer's location.

    Three legal sources, and the lease treatment differs (t1705_2 A3):

    - ``freezing`` -> ``freezing``: reconcile respawned a dead stand-in mid
      freeze. The freeze is STILL IN FLIGHT, so the lease is KEPT and the next
      reconcile pass commits it. Without this edge the pinned reconcile row
      "freezing / pane dead -> respawn, standin-respawned, re-check" is
      unimplementable.
    - ``aborting`` -> ``frozen``: the stand-in is back after a failed restore;
      the lease is released.
    - ``frozen`` -> ``frozen``: a ``lease-take``n relaunch of a dead stand-in.
    """
    now = _now() if now is None else now
    rec = _require_record(sf, record_id)
    _require_state(
        rec, "standin-respawned", STATE_FREEZING, STATE_ABORTING, STATE_FROZEN
    )
    _require_nonce(rec, nonce)
    _set_location(rec, pane, pane_pid)
    rec.standin_pid = int(pane_pid)
    if rec.state == STATE_FREEZING:
        return sf, f"STANDIN:{rec.id}"
    if rec.state == STATE_ABORTING:
        _set_state(rec, STATE_FROZEN, now)
    _clear_lease(rec)
    return sf, f"STANDIN:{rec.id}"


def lease_take(
    sf: SessionsFile,
    record_id: str,
    *,
    owner_pid: int,
    now: float | None = None,
    pid_alive=None,
) -> tuple[SessionsFile, str]:
    """Acquire ownership of a record whose lease is absent or stale."""
    now = _now() if now is None else now
    rec = _require_record(sf, record_id)
    if not _lease_stale(rec, now, pid_alive):
        raise LeaseHeld(f"LEASE_HELD:{rec.id}")
    nonce = _mint_lease(rec, owner_pid, now)
    return sf, f"LEASED:{rec.id}|{nonce}"


def lease_release(
    sf: SessionsFile, record_id: str, *, nonce: str
) -> tuple[SessionsFile, str]:
    """Give back a lease taken with :func:`lease_take`.

    The counterpart `lease_take` never had (t1705_6). Without it an aborted
    claim leaves the record leased until `stale_op_grace` elapses AND the owner
    pid dies -- so a user whose `drop` was refused mid-way could not simply
    retry, they would have to wait out the grace. Nonce-guarded like every other
    lease-clearing verb, so one coordinator cannot release another's claim.
    """
    rec = _require_record(sf, record_id)
    _require_nonce(rec, nonce)
    _clear_lease(rec)
    return sf, f"RELEASED:{rec.id}"


def drop(
    sf: SessionsFile, record_id: str, *, nonce: str | None = None
) -> tuple[SessionsFile, str]:
    """Remove a record from any state, with its capture files.

    Two forms, and the difference is the whole concurrency story (t1705_6):

    * ``drop(sf, id)`` -- unconditional, any state, no nonce. This is
      `kill_agent_pane_smart`'s contract: the user explicitly killed the pane
      and it is going away regardless.
    * ``drop(sf, id, nonce=n)`` -- the **leased** form, and the only safe one
      for a coordinator. The §A contract already says "every verb that mutates a
      record holding a lease requires ``--nonce``"; `drop` was its sole
      exception, which is what let a `drop` delete the record and the only copy
      of its capture out from under an in-flight restore.

    Why a nonce rather than comparing a snapshotted ``(state, op_nonce)``: that
    pair is **ABA-vulnerable**. ``standin_respawned`` from ``aborting`` does
    ``_set_state(FROZEN)`` *and* ``_clear_lease()``, so a full
    ``frozen -> restoring -> aborting -> frozen`` cycle restores the identical
    pair -- and that closing transition is precisely the one that registers a
    newly respawned stand-in viewer. A comparison would accept the stale delete
    and leave a live stamped viewer whose record and capture are gone. A nonce
    is a fresh token per claim (:func:`_mint_nonce`), so it cannot recur.
    """
    rec = _require_record(sf, record_id)
    if nonce is not None:
        _require_nonce(rec, nonce)
    remove_captures(rec.id)
    sf.sessions = [r for r in sf.sessions if r.id != rec.id]
    return sf, f"DROPPED:{rec.id}"


# --- observation + purge ----------------------------------------------------


@dataclass
class Observation:
    """What a producer actually saw. See the pinned observation protocol."""

    roots: set = field(default_factory=set)
    windows: dict = field(default_factory=dict)
    panes: dict = field(default_factory=dict)
    complete: bool = True
    pane_complete: dict = field(default_factory=dict)


def read_observation(path: str) -> Observation:
    """Parse the observation file, a superset of the agent-marks one.

    ``ROOT<TAB><root>``                           -- successfully enumerated root
    ``WINDOW<TAB><root><TAB><window>``            -- observed agent window
    ``PANE<TAB><root><TAB><window><TAB><pane_id><TAB><pane_pid><TAB><pane_dead>``
    ``INCOMPLETE``                                -- suppress every sweep

    A root with a ``WINDOW`` row but no ``PANE`` row for that window is
    pane-incomplete: ``dead_window`` still applies to it, ``dead_pane`` does
    not. Fail closed -- a visibility gap must never cause a deletion.
    """
    obs = Observation()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            kind = parts[0]
            if kind == "INCOMPLETE":
                obs.complete = False
            elif kind == "ROOT" and len(parts) == 2:
                obs.roots.add(os.path.realpath(parts[1]))
            elif kind == "WINDOW" and len(parts) == 3:
                root = os.path.realpath(parts[1])
                obs.windows.setdefault(root, set()).add(parts[2])
            elif kind == "PANE" and len(parts) == 6:
                root = os.path.realpath(parts[1])
                try:
                    pane_pid = int(parts[4])
                    pane_dead = int(parts[5])
                except ValueError as exc:
                    raise MalformedSessionsError(f"bad PANE row: {line!r}") from exc
                obs.panes.setdefault((root, parts[2]), []).append(
                    (parts[3], pane_pid, pane_dead)
                )
            else:
                raise MalformedSessionsError(f"unknown observation row: {line!r}")

    for root, windows in obs.windows.items():
        obs.pane_complete[root] = all((root, w) in obs.panes for w in windows)
    for root in obs.roots:
        obs.pane_complete.setdefault(root, True)
    return obs


def purge(
    sf: SessionsFile, observed: Observation, *, pid_alive=None
) -> tuple[SessionsFile, list[str]]:
    """Drop records whose agent is provably gone. Fail-closed throughout.

    ``INCOMPLETE`` suppresses everything. Transitional records are NEVER purged
    by liveness -- ``aitask_frozen.sh reconcile`` resolves those.
    """
    alive = pid_alive or _pid_alive
    if not observed.complete:
        return sf, []

    dropped: list[str] = []
    survivors: list[SessionRecord] = []
    for rec in sf.sessions:
        reason = None
        if rec.state == STATE_LIVE and rec.root in observed.roots:
            windows = observed.windows.get(rec.root, set())
            if rec.window not in windows:
                reason = "dead_window"
            elif observed.pane_complete.get(rec.root, False):
                rows = observed.panes.get((rec.root, rec.window), [])
                here = [r for r in rows if r[0] == rec.pane_id]
                gone = (not here) or all(r[2] == 1 for r in here)
                if gone and not alive(rec.pane_pid):
                    reason = "dead_pane"
        elif rec.state == STATE_FROZEN:
            # An EMPTY capture path counts as missing. A frozen record exists to
            # hold a capture the user can still read and restore from; with no
            # path there is nothing to show and nothing to restore, so the record
            # is pure garbage that would otherwise survive every purge forever
            # (it is exempt from the dead_window and dead_pane rules by design).
            # Purged rather than rejected at parse: one corrupt record must not
            # make the whole store unreadable for every other agent.
            if not rec.capture_ansi or not os.path.exists(rec.capture_ansi):
                reason = "capture_missing"

        if reason:
            dropped.append(f"DROPPED:{rec.id}|{reason}")
            remove_captures(rec.id)
        else:
            survivors.append(rec)
    sf.sessions = survivors
    return sf, dropped


# --- TUI-side cached reader -------------------------------------------------


class SessionsView:
    """An mtime-gated reader for the refresh tick.

    Re-reads only when the store's ``(st_mtime_ns, st_size, st_ino)`` changes.

    ``st_ino`` is load-bearing, exactly as in ``agent_marks.MarksView``: this
    store is only ever replaced via ``os.replace`` from a fresh temp file, and
    a state flip is frequently equal-length, so on a filesystem with coarse
    timestamp granularity both other fields can be unchanged across a real
    content change. Every ``os.replace`` yields a new inode, which makes the
    stamp replacement-sensitive by construction.
    """

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self._path = sessions_path(path)
        self._stamp: tuple[int, int, int] | None = None
        self._sf: SessionsFile = _empty()
        self._loaded = False

    @property
    def path(self) -> Path:
        return self._path

    def _stat_stamp(self) -> tuple[int, int, int] | None:
        try:
            st = os.stat(self._path)
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size, st.st_ino)

    def refresh(self) -> bool:
        """Re-read if the file changed. Returns True when a read happened."""
        stamp = self._stat_stamp()
        if self._loaded and stamp == self._stamp:
            return False
        self._stamp = stamp
        self._loaded = True
        self._sf = load_safe(self._path)
        return True

    def invalidate(self) -> None:
        """Force the next :meth:`refresh` to re-read.

        Used right after a write: it may land inside the same coarse mtime tick
        as the previous read, which the stamp alone would not catch.
        """
        self._loaded = False
        self._stamp = None

    def records(self) -> list[SessionRecord]:
        self.refresh()
        return list(self._sf.sessions)

    def frozen(self) -> list[SessionRecord]:
        return [r for r in self.records() if r.state == STATE_FROZEN]

    def by_id(self, record_id: str) -> SessionRecord | None:
        self.refresh()
        return self._sf.by_id(record_id)


# --- transcript fallback ----------------------------------------------------
#
# When the SessionStart hook never fired, the store has no codeagent session id
# and the only remaining source is the agent's own transcript store. This is not
# a rare path: codex 0.153.4 fires SessionStart under `codex exec` but NOT in
# the interactive TUI, which is how the framework launches agents -- so for
# interactive codex this IS the mechanism, not a backstop.
#
# The layouts below are pinned by tests/data/session_hooks/transcript_layout.json,
# captured from real stores. Two of them contradicted the original plan:
#
#   * claude encodes BOTH '/' and '_' as '-' in the project directory name
#     (the '/'-only rule matched 2 of 6 real directories), and whether '.' or
#     ' ' are also encoded remains UNOBSERVED. So the computed name is a fast
#     path only -- a candidate is always VERIFIED by reading cwd out of its
#     transcripts, and a miss falls back to scanning the whole store. That is
#     correct under every candidate escape rule, which is what stops an
#     unobserved character from silently yielding "no session".
#   * codex puts cwd and session_id under `payload`, not at the top level, and
#     partitions by DATE rather than by project.

MISS_NO_STORE_DIR = "no_store_dir"
MISS_NO_PROJECT_DIR = "no_project_dir"
MISS_NO_MATCH = "no_match"
MISS_UNSUPPORTED_AGENT = "unsupported_agent"

_CODEX_ROLLOUT_RE = re.compile(
    r"^rollout-.+?-(?P<session_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$"
)


def claude_project_dirname(root: str) -> str:
    """Encode a project path the way Claude Code names its transcript directory.

    Established rule: '/' and '_' both become '-'. Treat the result as a
    CANDIDATE, never as truth -- see the module note above.
    """
    return root.replace("/", "-").replace("_", "-")


def _claude_transcript_cwd(path: Path) -> str:
    """The first non-empty top-level ``cwd`` in a claude transcript.

    NOT on line 1 (observed at lines 2-5), so the file is scanned rather than
    peeked. Bounded so a huge transcript cannot stall a keypress path.
    """
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 50:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(obj, dict) and obj.get("cwd"):
                    return str(obj["cwd"])
    except OSError:
        pass
    return ""


def _codex_session_meta(path: Path) -> tuple[str, str]:
    """``(cwd, session_id)`` from a codex rollout's first line.

    First line is ``type: session_meta`` and both values live under ``payload``
    -- a top-level lookup returns nothing for every codex session.
    """
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            first = fh.readline()
    except OSError:
        return "", ""
    try:
        obj = json.loads(first)
    except (ValueError, TypeError):
        return "", ""
    payload = obj.get("payload") if isinstance(obj, dict) else None
    if not isinstance(payload, dict):
        return "", ""
    return str(payload.get("cwd") or ""), str(payload.get("session_id") or "")


def _newest(paths: list[Path]) -> list[Path]:
    """Newest first. Ties break on name (descending) so tests cannot flake and
    a reader can predict which of two same-mtime transcripts wins."""
    return sorted(paths, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)


def _claude_store_roots(home: Path, env) -> list[Path]:
    """Candidate claude transcript stores, most specific first.

    CLAUDE_CONFIG_DIR relocates `.claude.json`, but whether it also relocates
    `projects/` is NOT established: tests/test_frozen_standin_spike.sh always
    launches with it set, yet its scratch projects appear under the DEFAULT
    ~/.claude/projects (claude 2.1.263). So both are searched, override first.
    Searching both is correct under either behaviour and cannot regress the
    default path -- which guessing one root could.
    """
    roots: list[Path] = []
    cfg = (env.get("CLAUDE_CONFIG_DIR") or "").strip()
    if cfg:
        roots.append(Path(cfg) / "projects")
    roots.append(home / ".claude" / "projects")
    return roots


def _codex_store_roots(home: Path, env) -> list[Path]:
    """Candidate codex transcript stores, most specific first.

    CODEX_HOME relocating `sessions/` IS established -- the spike reads
    `find "$CODEX_HOME_DIR/sessions"` directly. Without honouring it, an agent
    launched with a custom CODEX_HOME writes its transcripts there while this
    resolver scans ~/.codex/sessions and reports no_store_dir, forcing re-pick
    on exactly the path the fallback exists to rescue.
    """
    roots: list[Path] = []
    ch = (env.get("CODEX_HOME") or "").strip()
    if ch:
        roots.append(Path(ch) / "sessions")
    roots.append(home / ".codex" / "sessions")
    return roots


def _existing(roots: list[Path]) -> list[Path]:
    """Deduplicate (an override may equal the default) and keep real dirs."""
    out: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        try:
            key = str(r.resolve())
        except OSError:
            key = str(r)
        if key in seen:
            continue
        seen.add(key)
        if r.is_dir():
            out.append(r)
    return out


def _claude_newest_transcript(root: str, home: Path, env) -> tuple[str, str, str]:
    stores = _existing(_claude_store_roots(home, env))
    if not stores:
        return "", "", MISS_NO_STORE_DIR

    # Fast path: the computed directory name, in each candidate store.
    computed: list[Path] = []
    for store in stores:
        c = store / claude_project_dirname(root)
        if c.is_dir():
            computed.append(c)

    # Verify the fast path, then fall back to scanning every store. The encode
    # rule is only partially determined, so a computed miss is expected rather
    # than exceptional.
    everything: list[Path] = []
    for store in stores:
        try:
            everything.extend(d for d in store.iterdir() if d.is_dir())
        except OSError:
            continue

    for scope in (computed, everything):
        if not scope:
            continue
        files: list[Path] = []
        for d in scope:
            try:
                files.extend(p for p in d.glob("*.jsonl") if p.is_file())
            except OSError:
                continue
        for path in _newest(files):
            if _claude_transcript_cwd(path) == root:
                return path.stem, str(path), ""
    return "", "", (MISS_NO_MATCH if computed else MISS_NO_PROJECT_DIR)


def _codex_newest_transcript(root: str, home: Path, env) -> tuple[str, str, str]:
    stores = _existing(_codex_store_roots(home, env))
    if not stores:
        return "", "", MISS_NO_STORE_DIR
    rollouts: list[Path] = []
    for store in stores:
        try:
            rollouts.extend(p for p in store.glob("*/*/*/*.jsonl") if p.is_file())
        except OSError:
            continue
    if not rollouts:
        return "", "", MISS_NO_MATCH
    for path in _newest(rollouts):
        cwd, session_id = _codex_session_meta(path)
        if cwd != root:
            continue
        if not session_id:
            m = _CODEX_ROLLOUT_RE.match(path.name)
            session_id = m.group("session_id") if m else ""
        if session_id:
            return session_id, str(path), ""
    return "", "", MISS_NO_MATCH


def newest_transcript_for(
    root: str, agent_kind: str, *, home: Path | None = None, env=None
) -> tuple[str, str, str]:
    """Resolve ``(session_id, transcript_path, miss_reason)`` from the agent's
    own transcript store, for use when the SessionStart hook never fired.

    Honours each agent's store-root override (``CLAUDE_CONFIG_DIR`` /
    ``CODEX_HOME``) IN ADDITION to the default under ``$HOME`` -- an agent
    launched with a custom root writes its transcripts there, and scanning only
    the default would report "no session" for exactly the sessions this
    function exists to find.

    ``home`` and ``env`` are test seams: ``home`` overrides ``$HOME`` for the
    default roots, ``env`` overrides the environment consulted for the
    override roots (pass ``{}`` for a hermetic run).

    On success ``miss_reason`` is ``""``. On a miss BOTH ids are ``""`` and
    ``miss_reason`` says which kind of miss it was -- that third value is the
    whole point: without it a wrong layout assumption is indistinguishable from
    "this agent genuinely has no session", and a store-layout change after an
    agent release would look exactly like normal operation.
    """
    home = Path(os.path.expanduser("~")) if home is None else home
    env = os.environ if env is None else env
    croot = os.path.realpath(root)
    if agent_kind == "claudecode":
        return _claude_newest_transcript(croot, home, env)
    if agent_kind == "codex":
        return _codex_newest_transcript(croot, home, env)
    return "", "", MISS_UNSUPPORTED_AGENT


# --- CLI --------------------------------------------------------------------

_LIST_FIELDS = (
    "id", "state", "root", "window", "pane_id", "task_id", "agent_string", "state_at",
)

#: Exception -> wrapper exit code. The wrapper maps these 1:1.
_EXIT_CODES = {
    MalformedSessionsError: 4,
    TransitionRefused: 5,
    NonceMismatch: 6,
    SessionMismatch: 7,
    LeaseHeld: 8,
}


def _arg(argv: list[str], name: str, default=None):
    """Read ``--name value`` from a flat argv. Returns ``default`` when absent."""
    flag = f"--{name}"
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
        raise ValueError(f"{flag} needs a value")
    return default


def _require_arg(argv: list[str], name: str):
    value = _arg(argv, name)
    if value is None:
        raise ValueError(f"missing required --{name}")
    return value


def _int_arg(argv: list[str], name: str, default=None, *, positive=False):
    raw = _arg(argv, name)
    if raw is None:
        if default is None:
            raise ValueError(f"missing required --{name}")
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"--{name} must be an integer: {raw!r}") from exc
    if positive and value <= 0:
        raise ValueError(f"--{name} must be positive: {value}")
    return value


def _pane_pair(argv: list[str]) -> tuple[str, int]:
    """Read and validate the `--pane` / `--pane-pid` pair.

    Exactly two shapes are legal: a real pane (`%N` + a positive pid) or the
    gone-pane pair (`""` + `0`) that reconcile commits when the pane vanished.
    A mixed pair would persist a location that cannot exist -- a live pid at no
    pane, or a pane with no process -- and `freeze_commit` writes both
    `pane_id`/`pane_pid` and `standin_pid` from it, so reconcile could never
    match the record against a real pane again.

    Enforced here as well as in the shell wrapper: this CLI is a documented
    direct entry point, not merely the wrapper's private backend.
    """
    pane = _require_arg(argv, "pane")
    pane_pid = _int_arg(argv, "pane-pid")
    if pane_pid < 0:
        raise ValueError(f"--pane-pid must be non-negative: {pane_pid}")
    if not pane and pane_pid != 0:
        raise ValueError(
            f"--pane '' requires --pane-pid 0 (the gone-pane pair); got {pane_pid}"
        )
    if pane and pane_pid == 0:
        raise ValueError(
            f"--pane-pid 0 requires --pane '' (the gone-pane pair); got {pane!r}"
        )
    return pane, pane_pid


def _id_arg(value: str, label: str) -> str:
    if not valid_id(value):
        raise ValueError(f"{label} must be 8 lowercase hex: {value!r}")
    return value


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = None
    if "--file" in argv:
        i = argv.index("--file")
        # Bounds-checked BEFORE indexing: this runs above the try block, so a
        # bare `--file` would otherwise raise an uncaught IndexError and hand
        # automation a traceback instead of the documented usage exit 2.
        if i + 1 >= len(argv):
            print("ERROR:--file needs a value", file=sys.stderr)
            return 2
        path = argv[i + 1]
        del argv[i : i + 2]
    if not argv:
        print("usage: agent_sessions.py [--file PATH] <verb> ...", file=sys.stderr)
        return 2

    verb, rest = argv[0], argv[1:]
    now = _now()

    try:
        # Read-only verbs first: no load-modify-dump cycle.
        if verb == "list":
            sf = load(path)
            state = _arg(rest, "state")
            root = _arg(rest, "root")
            croot = os.path.realpath(root) if root else None
            for rec in sorted(sf.sessions, key=lambda r: r.key):
                if state and rec.state != state:
                    continue
                if croot and rec.root != croot:
                    continue
                values = [str(getattr(rec, f)) for f in _LIST_FIELDS]
                print("SESSION:" + "|".join(values))
            return 0

        if verb == "show":
            sf = load(path)
            rec = _require_record(sf, _id_arg(rest[0], "id"))
            for key, value in vars(rec).items():
                print(f"{key}:{value}")
            return 0

        sf = load(path)
        if verb == "upsert":
            sf, line = upsert(
                sf,
                root=_require_arg(rest, "root"),
                window=_require_arg(rest, "window"),
                pane=_pane_pair(rest)[0],
                pane_pid=_pane_pair(rest)[1],
                id=_id_arg(_arg(rest, "id"), "--id") if _arg(rest, "id") else None,
                session=_arg(rest, "session"),
                session_id=_arg(rest, "session-id"),
                transcript=_arg(rest, "transcript"),
                agent_string=_arg(rest, "agent-string"),
                operation=_arg(rest, "operation"),
                task_id=_arg(rest, "task-id"),
                restore_of=(
                    _id_arg(_arg(rest, "restore-of"), "--restore-of")
                    if _arg(rest, "restore-of")
                    else None
                ),
                nonce=(
                    _id_arg(_arg(rest, "nonce"), "--nonce") if _arg(rest, "nonce") else None
                ),
                now=now,
            )
        elif verb == "freeze-begin":
            sf, line = freeze_begin(
                sf,
                _id_arg(rest[0], "id"),
                capture_ansi=_require_arg(rest, "capture-ansi"),
                capture_txt=_require_arg(rest, "capture-txt"),
                lines=_int_arg(rest, "lines"),
                phase=_arg(rest, "phase", ""),
                owner_pid=_int_arg(rest, "owner-pid", positive=True),
                now=now,
            )
        elif verb == "freeze-commit":
            sf, line = freeze_commit(
                sf,
                _id_arg(rest[0], "id"),
                nonce=_id_arg(_require_arg(rest, "nonce"), "--nonce"),
                pane=_pane_pair(rest)[0],
                pane_pid=_pane_pair(rest)[1],
                now=now,
            )
        elif verb == "freeze-abort":
            sf, line = freeze_abort(
                sf,
                _id_arg(rest[0], "id"),
                nonce=_id_arg(_require_arg(rest, "nonce"), "--nonce"),
                now=now,
            )
        elif verb == "restore-begin":
            sf, line = restore_begin(
                sf,
                _id_arg(rest[0], "id"),
                mode=_require_arg(rest, "mode"),
                owner_pid=_int_arg(rest, "owner-pid", positive=True),
                now=now,
            )
        elif verb == "restore-launched":
            sf, line = restore_launched(
                sf,
                _id_arg(rest[0], "id"),
                nonce=_id_arg(_require_arg(rest, "nonce"), "--nonce"),
                pane=_pane_pair(rest)[0],
                pane_pid=_pane_pair(rest)[1],
                now=now,
            )
        elif verb == "restore-confirm":
            sf, line = restore_confirm(
                sf,
                _id_arg(rest[0], "id"),
                nonce=_id_arg(_require_arg(rest, "nonce"), "--nonce"),
                pane=_pane_pair(rest)[0],
                pane_pid=_pane_pair(rest)[1],
                now=now,
            )
        elif verb == "restore-abort":
            sf, line = restore_abort(
                sf,
                _id_arg(rest[0], "id"),
                nonce=_id_arg(_require_arg(rest, "nonce"), "--nonce"),
                error=_arg(rest, "error", ""),
                now=now,
            )
        elif verb == "standin-respawned":
            sf, line = standin_respawned(
                sf,
                _id_arg(rest[0], "id"),
                nonce=_id_arg(_require_arg(rest, "nonce"), "--nonce"),
                pane=_pane_pair(rest)[0],
                pane_pid=_pane_pair(rest)[1],
                now=now,
            )
        elif verb == "lease-take":
            sf, line = lease_take(
                sf,
                _id_arg(rest[0], "id"),
                owner_pid=_int_arg(rest, "owner-pid", positive=True),
                now=now,
            )
        elif verb == "lease-release":
            sf, line = lease_release(
                sf,
                _id_arg(rest[0], "id"),
                nonce=_id_arg(_require_arg(rest, "nonce"), "--nonce"),
            )
        elif verb == "drop":
            raw_nonce = _arg(rest, "nonce")
            sf, line = drop(
                sf,
                _id_arg(rest[0], "id"),
                nonce=_id_arg(raw_nonce, "--nonce") if raw_nonce else None,
            )
        elif verb == "purge":
            obs = read_observation(_require_arg(rest, "observed"))
            sf, lines = purge(sf, obs)
            dump(sf, path)
            for entry in lines:
                print(entry)
            print(f"PURGED:{len(lines)}")
            return 0
        else:
            print(f"unknown verb: {verb}", file=sys.stderr)
            return 2

        dump(sf, path)
        print(line)
        return 0

    except (ValueError, IndexError) as exc:
        print(f"ERROR:{exc}", file=sys.stderr)
        return 2
    except SessionMismatch as exc:
        # THE ONE refusal that must PERSIST before it reports, and so the one
        # that cannot share the write-nothing handler below.
        #
        # The SessionStart hook has no return channel to the detached restore
        # coordinator, so `last_error` on the record IS the channel (§A/§D): the
        # coordinator polls `show <id>` until it sees this nonce, then takes the
        # abort branch. Dropping the write here loses the report entirely, the
        # coordinator times out, and it takes the LIVENESS branch instead --
        # confirming as `live` a pane running a DIFFERENT session than the one
        # being restored, which is precisely what the mismatch check exists to
        # prevent. The transition already mutated `sf` before raising; this is
        # what makes that mutation durable.
        dump(sf, path)
        print(str(exc), file=sys.stderr)
        return _EXIT_CODES[SessionMismatch]
    except tuple(_EXIT_CODES) as exc:
        # Every other refusal writes NOTHING -- that is the exit-code contract
        # (`3/4/5/6/8 ... NOTHING was written`), and the transitions raise
        # before mutating, so there is nothing to persist.
        print(str(exc), file=sys.stderr)
        return _EXIT_CODES[type(exc)]


if __name__ == "__main__":
    sys.exit(main())
