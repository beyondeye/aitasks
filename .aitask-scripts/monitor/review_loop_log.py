#!/usr/bin/env python3
"""Durable record of why the shadow auto-recheck loop disarmed or held (t1606).

A toast fades in about five seconds. The spurious auto-disarm t1606 exists to
fix was reported live, was never reproducible synthetically, and left **no
trace at all** — so every hypothesis about it was unfalsifiable in production.
This module is the record that makes the next occurrence identifiable after the
fact.

Storage: **per-session, append-only, and the active file is never rewritten.**
---------------------------------------------------------------------------

An earlier design used one shared ``review_loop_events.jsonl`` trimmed to a
fixed-size ring through ``lib/atomic_write.py``. It was rejected as unsafe. The
trim is a read-modify-write, so an append landing on the old inode *after* the
trim read it but *before* ``os.replace`` swaps the path is silently lost — and
the lost events would be exactly the ones this module exists to capture.

Locking every append was not a real alternative either: every mutex in this
framework is a shell script (``lib/registry_lock.sh`` and friends — there is no
``fcntl`` use anywhere under ``.aitask-scripts/``), so it would mean spawning a
subprocess on the Textual event loop on every disarm.

So the race class is removed by construction rather than managed:

* one file per app instance, written by exactly one process for its whole life;
* the active file is only ever appended to — never read-modify-written;
* retention runs at startup and touches **only files no live process owns**,
  so it cannot interleave with an append at all.

Two independent guards protect retention, because deleting a live session's
file is the one unrecoverable mistake here. Liveness is delegated to
``lib/monitor_marker.py`` — the framework's single implementation of that rule,
which exists precisely because a hand-rolled version "diverges silently" — and
only a *provable* absence (``STATE_STALE``) licenses a delete. On top of that an
age floor refuses any recently-modified file whatever liveness reports, which
covers pid reuse that liveness alone cannot.

Nothing here raises. A logging failure must never take the TUI down (the
``applink/audit.py`` ``NullHandler`` doctrine), so :func:`record_event` reports
failure by returning ``False`` — and the caller surfaces that, because a
captured diagnostic nobody sees is not a diagnostic.

Deliberately free of Textual, tmux and subprocess imports, like
``lib/agent_marks.py``, so the whole store is unit-testable with no event loop.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_LIB_DIR = str(Path(__file__).resolve().parents[1] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

try:
    from monitor_marker import STATE_STALE, monitor_marker_state
except ImportError:  # pragma: no cover - flat-import fallback, as review_loop
    from lib.monitor_marker import (  # type: ignore[no-redef]
        STATE_STALE, monitor_marker_state,
    )

#: Env override for the store directory, mirroring ``AITASKS_AGENT_MARKS_FILE``.
LOG_DIR_ENV = "AITASKS_REVIEW_LOOP_LOG_DIR"

DEFAULT_LOG_DIR = "~/.config/aitasks/review_loop_events"

#: Directory mode. A per-user directory naming every project root you run a
#: monitor in gets the same treatment as ``projects.yaml`` beside it.
_DIR_MODE = 0o700
_FILE_MODE = 0o600

SCHEMA_VERSION = 1

#: How many session files to keep. A fixed COUNT, not a byte cap: the only
#: retention precedent in this framework is ``codebrowser/history_list.py``'s
#: ``MAX_RECENT``, and no rotation convention exists to copy.
MAX_SESSION_FILES = 20

#: Retention refuses any file modified within this window, whatever the
#: liveness verdict says. Liveness cannot rule out pid reuse; this can.
RETENTION_AGE_FLOOR_SECONDS = 600.0

#: One record must fit in a single ``write()`` that POSIX makes atomic, so the
#: one-writer-per-file invariant is belt-and-braces rather than load-bearing.
#: ``PIPE_BUF`` is 4096; this leaves room for the newline and any encoding
#: expansion.
MAX_LINE_BYTES = 3800

#: Per-string budget, applied BEFORE serialization so the line is bounded by
#: construction rather than by truncating JSON after the fact (which would
#: produce an unparseable record — the very thing the reader has to tolerate).
_MAX_FIELD_CHARS = 200
_MAX_EXTRA_FIELDS = 24

KIND_DISARM = "disarm"
KIND_HOLD = "hold"

#: ``<YYYYmmddTHHMMSSZ>-<pid>.jsonl``
_SESSION_FILE_RE = re.compile(r"^(\d{8}T\d{6}Z)-(\d+)\.jsonl$")

_session_path: Path | None = None


def log_dir() -> Path:
    """The store directory. Not created here — see :func:`_ensure_dir`."""
    raw = os.environ.get(LOG_DIR_ENV) or DEFAULT_LOG_DIR
    return Path(os.path.expanduser(raw))


def _ensure_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, _DIR_MODE)
    except OSError:
        return False
    return True


def session_path() -> Path:
    """This process's own file. Stable for the life of the process."""
    global _session_path
    if _session_path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        _session_path = log_dir() / f"{stamp}-{os.getpid()}.jsonl"
    return _session_path


def reset_session_for_tests() -> None:
    """Drop the memoized session path (tests point the env var elsewhere)."""
    global _session_path
    _session_path = None


def _clip(value: object) -> object:
    """Bound a field so the serialized line cannot exceed the write budget."""
    if isinstance(value, str) and len(value) > _MAX_FIELD_CHARS:
        return value[:_MAX_FIELD_CHARS] + "…"
    return value


def build_record(kind: str, reason: str, **fields: object) -> dict:
    """The event dict, bounded by construction. Pure — no I/O, so the shape is
    testable without touching the filesystem."""
    record: dict[str, object] = {
        "schema": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": str(kind),
        "reason": str(reason),
    }
    for index, (key, value) in enumerate(sorted(fields.items())):
        if index >= _MAX_EXTRA_FIELDS:
            break
        if value is None:
            continue
        record[str(key)] = _clip(value)
    return record


def _serialize(record: dict) -> str:
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    if len(line.encode("utf-8")) <= MAX_LINE_BYTES:
        return line
    # Should be unreachable given the per-field budget, but a record that
    # cannot fit must still be VALID JSON rather than a torn line: fall back
    # to the four mandatory keys plus a flag saying detail was dropped.
    minimal = {
        "schema": record.get("schema", SCHEMA_VERSION),
        "ts": record.get("ts", ""),
        "kind": record.get("kind", ""),
        "reason": record.get("reason", ""),
        "detail_dropped": True,
    }
    return json.dumps(minimal, ensure_ascii=False, sort_keys=True)


def record_event(kind: str, reason: str, **fields: object) -> bool:
    """Append one event. Returns ``False`` on any failure; never raises.

    The append is a single ``write()`` of one line to a file opened ``"a"``
    (``O_APPEND``). Under ``PIPE_BUF`` that is atomic on POSIX, so even if the
    one-writer-per-file invariant were ever broken, records could interleave
    but never tear.
    """
    path = session_path()
    if not _ensure_dir(path.parent):
        return False
    line = _serialize(build_record(kind, reason, **fields)) + "\n"
    try:
        existed = path.exists()
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
        if not existed:
            os.chmod(path, _FILE_MODE)
    except OSError:
        return False
    return True


# -- retention ---------------------------------------------------------------


def _session_files(directory: Path) -> list[tuple[str, int, Path]]:
    """``(stamp, pid, path)`` for every well-formed session file."""
    found = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    for entry in entries:
        match = _SESSION_FILE_RE.match(entry.name)
        if match is None:
            continue  # not ours — never touch it
        found.append((match.group(1), int(match.group(2)), entry))
    found.sort(key=lambda item: (item[0], item[1]))
    return found


def _is_deletable(pid: int, path: Path, now: float) -> bool:
    """Both guards. Either one refusing keeps the file."""
    # Guard 1: only a PROVABLE absence licenses a delete. monitor_marker
    # classifies an unverifiable read as present, which is the safe direction.
    if monitor_marker_state(f"minimonitor:{pid}") != STATE_STALE:
        return False
    # Guard 2: age floor, which covers the pid reuse guard 1 cannot.
    try:
        age = now - path.stat().st_mtime
    except OSError:
        return False
    return age >= RETENTION_AGE_FLOOR_SECONDS


def prune(directory: Path | None = None, *, keep: int = MAX_SESSION_FILES,
          now: float | None = None) -> list[Path]:
    """Delete oldest-first down to ``keep`` files. Returns what was removed.

    Runs at startup only, and only over files **no live process owns** — which
    is what makes it incapable of interleaving with an append. Never raises.
    """
    directory = directory or log_dir()
    now = time.time() if now is None else now
    files = _session_files(directory)
    removed: list[Path] = []
    excess = len(files) - keep
    if excess <= 0:
        return removed
    for _stamp, pid, path in files:  # oldest first
        if excess <= 0:
            break
        if not _is_deletable(pid, path, now):
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed.append(path)
        excess -= 1
    return removed


# -- reader ------------------------------------------------------------------


def read_events(directory: Path | None = None, *, limit: int = 20
                ) -> tuple[list[dict], list[str]]:
    """``(events_newest_first, notes)``. Tolerant of damage, by line.

    A diagnostic tool that dies on a damaged file fails exactly when it is
    needed. A line that is not valid JSON — or is valid JSON but not an event
    object — is **skipped**, never fatal, and an unopenable file never
    suppresses the others. ``notes`` describes what was skipped; the caller
    sends it to stderr so stdout stays a clean event stream.
    """
    directory = directory or log_dir()
    # (ts, arrival_index, event). The arrival index is the tiebreak: `ts` is
    # second-resolution, so several events routinely share one, and a stable
    # sort on `ts` alone would return same-second events OLDEST-first — the
    # opposite of what this function promises. Files are walked oldest-first
    # and lines are in append order, so a higher index is always the newer
    # record within a tie.
    rows: list[tuple[str, int, dict]] = []
    notes: list[str] = []
    skipped = 0
    arrival = 0
    for _stamp, _pid, path in _session_files(directory):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            notes.append(f"could not read {path.name}: {exc.strerror or exc}")
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except (ValueError, TypeError):
                skipped += 1
                continue
            if not isinstance(parsed, dict) or "reason" not in parsed:
                skipped += 1
                continue
            rows.append((str(parsed.get("ts", "")), arrival, parsed))
            arrival += 1
    if skipped:
        notes.append(f"skipped {skipped} unreadable line(s)")
    # ISO-8601 UTC sorts lexicographically, so a plain string sort is a time
    # sort. A record missing `ts` sorts last but is still shown.
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [row[2] for row in rows[:limit]], notes


def format_event(event: dict) -> str:
    """One line of prose. Reason codes are decoded through review_loop so the
    reader and the toast can never describe the same code differently."""
    try:
        import review_loop
        message = review_loop.loop_reason_message(
            str(event.get("reason", "")), subject=str(event.get("subject", "")))
    except Exception:  # pragma: no cover - reader must work standalone
        message = str(event.get("reason", ""))
    bits = [
        str(event.get("ts", "?")),
        str(event.get("kind", "?")).upper(),
        message,
    ]
    context = []
    for key in ("agent", "shadow_agent", "shadow_pane", "session", "window",
                "state", "rounds_fired", "project_root"):
        if event.get(key) not in (None, ""):
            context.append(f"{key}={event[key]}")
    line = "  ".join(bits)
    if context:
        line += "\n    " + " ".join(context)
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ait minimonitor --loop-log",
        description="Print recent shadow auto-recheck loop events "
                    "(why the loop disarmed or held).")
    parser.add_argument("count", nargs="?", type=int, default=20,
                        help="how many events to show (default 20)")
    parser.add_argument("--dir", default=None,
                        help="read this directory instead of the default")
    args = parser.parse_args(argv)

    directory = Path(os.path.expanduser(args.dir)) if args.dir else log_dir()
    events, notes = read_events(directory, limit=max(1, args.count))
    if not events:
        print("(no review-loop events recorded)")
    else:
        for event in events:
            print(format_event(event))
    for note in notes:
        print(f"({note})", file=sys.stderr)
    # Skipped lines are not a failure: partial diagnosis is the useful
    # outcome, and a non-zero exit would make the reader unusable in exactly
    # the degraded case it exists to serve.
    return 0


if __name__ == "__main__":
    sys.exit(main())
