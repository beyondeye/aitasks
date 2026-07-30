#!/usr/bin/env python3
"""Cross-repo prioritized-agent marks — store + policy (t1326).

LOCK-FREE PRIMITIVE: this module NEVER takes a lock -- callers own concurrency.
The sole writer is ``aitask_agent_marks.sh``, which holds the ``registry_lock.sh``
mutex around a read-modify-write. Readers (the monitor TUIs) read the file
directly without a lock: every write lands via ``os.replace``, so a reader always
observes one whole generation.

Identity is ``(realpath(project_root), window_name)`` — never the tmux session
name, which is not unique across repos (unconfigured repos all fall back to the
literal ``"aitasks"``; see ``AitasksSession.key`` in ``agent_launch_utils.py``).
``pane_id`` is not durable either: tmux recycles ``%N`` across server restarts.

The module is deliberately free of Textual, tmux and subprocess imports so the
policy (expiry, liveness) is unit-testable with no tmux server and no event loop.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

#: Env override for the store path, mirroring ``AITASKS_PROJECTS_INDEX``.
MARKS_ENV = "AITASKS_AGENT_MARKS_FILE"
#: Env override for the age-expiry window, in days.
TTL_ENV = "AITASKS_AGENT_MARK_TTL_DAYS"

DEFAULT_MARKS_PATH = "~/.config/aitasks/agent_marks.json"
DEFAULT_TTL_DAYS = 2.0
SCHEMA_VERSION = 1

#: Store mode. The registry beside it (``projects.yaml``) is 0600; a per-user
#: file naming every project root you work in gets the same treatment.
_FILE_MODE = 0o600

#: Reasons reported by the purge verbs, so a caller can say *why* an entry went.
REASON_EXPIRED = "expired"
REASON_DEAD_WINDOW = "dead_window"


class MalformedMarksError(Exception):
    """The store exists but could not be parsed.

    Raised only by :func:`load` (the write path), never by :func:`load_safe`
    (the read path). The asymmetry is the point: a writer that silently treated
    a corrupt file as ``{}`` would round-trip an empty store back over the user's
    marks and destroy them. Cf. ``MalformedUserConfigError`` in
    ``userconfig_persist.py``.
    """


@dataclass(frozen=True)
class MarkRecord:
    """One mark. ``root`` is always already-canonical (see :func:`mark_key`)."""

    root: str
    window: str
    marked_at: int

    @property
    def key(self) -> tuple[str, str]:
        return (self.root, self.window)


@dataclass
class MarksFile:
    """An in-memory store generation. ``version`` is carried so a writer can
    refuse to downgrade a file written by a newer framework."""

    version: int
    marks: list[MarkRecord]

    def keys(self) -> set[tuple[str, str]]:
        return {m.key for m in self.marks}

    def is_marked(self, root: str, window: str) -> bool:
        return mark_key(root, window) in self.keys()


@dataclass(frozen=True)
class ToggleResult:
    now_marked: bool
    record: MarkRecord | None  # the added record, or the removed one


def _empty() -> MarksFile:
    return MarksFile(version=SCHEMA_VERSION, marks=[])


# --- paths / identity -------------------------------------------------------


def marks_path(path: str | os.PathLike | None = None) -> Path:
    """Resolve the store path: explicit arg > ``$AITASKS_AGENT_MARKS_FILE`` >
    default. Not ``realpath``-ed here — :func:`_atomic_write` does that at the
    write site, and a caller may legitimately point at a symlink."""
    if path is not None:
        return Path(path)
    env = os.environ.get(MARKS_ENV)
    if env:
        return Path(env)
    return Path(os.path.expanduser(DEFAULT_MARKS_PATH))


def mark_key(root: str | os.PathLike, window: str) -> tuple[str, str]:
    """Canonical identity for a marked agent.

    ``realpath`` is applied on BOTH the write and the read side: a mark written
    from a symlinked checkout must match a read that resolved the real path, and
    vice versa. Canonicalizing on only one side is the classic way two spellings
    of the same repo end up with two independent marks.
    """
    return (os.path.realpath(str(root)), window)


def ttl_days(override: float | None = None) -> float:
    """Age-expiry window in days.

    A malformed or non-positive ``$AITASKS_AGENT_MARK_TTL_DAYS`` falls back to
    the default rather than being honoured — a typo (``0``, ``""``, ``2 days``)
    must never silently expire every mark on the next tick.
    """
    if override is not None:
        return override if override > 0 else DEFAULT_TTL_DAYS
    raw = os.environ.get(TTL_ENV)
    if not raw:
        return DEFAULT_TTL_DAYS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_TTL_DAYS
    return value if value > 0 else DEFAULT_TTL_DAYS


# --- serialization ----------------------------------------------------------


def _parse(text: str) -> MarksFile:
    """Parse store JSON, raising :class:`MalformedMarksError` on anything odd."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise MalformedMarksError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MalformedMarksError("top level is not an object")

    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise MalformedMarksError(f"missing or non-integer version: {version!r}")
    if version != SCHEMA_VERSION:
        # EXACT equality, not just `> SCHEMA_VERSION`. A newer file must not be
        # truncated to fields we do not understand; an *older* one must not be
        # silently rewritten as the current version either, because that is a
        # migration and no migration exists. Readers render nothing and writers
        # refuse until one is written.
        raise MalformedMarksError(
            f"unsupported store version {version} (expected {SCHEMA_VERSION})"
        )

    raw_marks = data.get("marks")
    if not isinstance(raw_marks, list):
        raise MalformedMarksError("'marks' is not a list")

    marks: list[MarkRecord] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw_marks:
        if not isinstance(entry, dict):
            raise MalformedMarksError(f"mark entry is not an object: {entry!r}")
        root = entry.get("root")
        window = entry.get("window")
        marked_at = entry.get("marked_at")
        if not isinstance(root, str) or not root:
            raise MalformedMarksError(f"bad 'root' in entry: {entry!r}")
        if not isinstance(window, str) or not window:
            raise MalformedMarksError(f"bad 'window' in entry: {entry!r}")
        if not isinstance(marked_at, int) or isinstance(marked_at, bool):
            raise MalformedMarksError(f"bad 'marked_at' in entry: {entry!r}")
        # Canonicalize on read too: an entry hand-edited with a symlinked path
        # must still match a strictly-resolved lookup.
        key = mark_key(root, window)
        if key in seen:
            continue  # first spelling wins; a duplicate is not a corruption
        seen.add(key)
        marks.append(MarkRecord(root=key[0], window=window, marked_at=marked_at))
    return MarksFile(version=version, marks=marks)


def load(path: str | os.PathLike | None = None) -> MarksFile:
    """Read the store, raising on corruption. **The write path uses this.**

    A missing file is not corruption — it is an empty store, which is exactly
    what the first-ever toggle should build on.
    """
    target = marks_path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _empty()
    except IsADirectoryError as exc:
        raise MalformedMarksError(f"{target} is a directory") from exc
    except OSError as exc:
        raise MalformedMarksError(f"cannot read {target}: {exc}") from exc
    if not text.strip():
        return _empty()
    return _parse(text)


def load_safe(path: str | os.PathLike | None = None) -> MarksFile:
    """Read the store, never raising. **The TUI read path uses this.**

    Any failure — malformed JSON, a truncated write, a directory at the path,
    bad permissions, a version from the future — yields an empty store. Marks
    are an advisory annotation; they must never be able to crash a refresh tick.
    """
    try:
        return load(path)
    except MalformedMarksError:
        return _empty()
    except OSError:
        return _empty()


def _target_mode(path: Path) -> int:
    """Preserve an existing file's mode; default to 0600 for a new store.

    Without this, ``mkstemp``'s 0600 would be the only mode ever produced — fine
    here, but the explicit read keeps a user's deliberate chmod intact.
    """
    try:
        return stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return _FILE_MODE


def dump(mf: MarksFile, path: str | os.PathLike | None = None) -> None:
    """Atomically replace the store.

    Temp file in the same directory + ``os.replace``, so a concurrent reader
    never sees a partial file. Atomic *visibility*, not crash durability — no
    fsync, matching ``gate_ledger`` / ``attachment_meta`` / ``config_utils``.

    ``path`` is resolved with ``realpath`` first: ``open(..., "w")`` follows a
    symlink but ``os.replace`` would replace the link itself, orphaning the real
    backing file while reads kept succeeding.
    """
    target = Path(os.path.realpath(marks_path(path)))
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = _target_mode(target)
    payload = {
        "version": SCHEMA_VERSION,
        "marks": [
            {"root": m.root, "window": m.window, "marked_at": m.marked_at}
            for m in sorted(mf.marks, key=lambda m: (m.root, m.window))
        ],
    }
    fd, tmp = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except BaseException:
        _discard(tmp)
        raise
    try:
        os.replace(tmp, target)
    except BaseException:
        _discard(tmp)
        raise


def _discard(tmp: str) -> None:
    try:
        os.unlink(tmp)
    except OSError:
        pass


# --- policy (pure) ----------------------------------------------------------


def toggle(
    mf: MarksFile,
    root: str | os.PathLike,
    window: str,
    *,
    now: int | None = None,
) -> ToggleResult:
    """Flip the mark for ``(root, window)``. Mutates ``mf`` in place."""
    key = mark_key(root, window)
    for existing in mf.marks:
        if existing.key == key:
            mf.marks.remove(existing)
            return ToggleResult(now_marked=False, record=existing)
    record = MarkRecord(
        root=key[0], window=window, marked_at=int(now if now is not None else time.time())
    )
    mf.marks.append(record)
    return ToggleResult(now_marked=True, record=record)


def expire(
    mf: MarksFile, *, ttl: float | None = None, now: float | None = None
) -> list[MarkRecord]:
    """Drop marks older than the TTL. Returns the dropped records.

    Needs no tmux visibility, so this is the safe general reaper: it is what
    bounds the store when a repo is never opened again.
    """
    window_days = ttl_days(ttl)
    cutoff = (now if now is not None else time.time()) - window_days * 86400.0
    dropped = [m for m in mf.marks if m.marked_at < cutoff]
    if dropped:
        stale = {id(m) for m in dropped}
        mf.marks = [m for m in mf.marks if id(m) not in stale]
    return dropped


def sweep_liveness(
    mf: MarksFile,
    observed: dict[str, set[str]],
    sweepable_roots: set[str],
    *,
    complete: bool = True,
) -> list[MarkRecord]:
    """Drop marks whose agent window is gone. Returns the dropped records.

    **Fail-closed, and keyed on successful enumeration — not on presence.**

    - ``sweepable_roots`` holds the canonical roots whose tmux session was
      *successfully enumerated* this tick. A root absent from it is never
      touched, because "session not running", "``list-panes`` failed" and
      "session lives on another tmux socket" are indistinguishable from the
      outside and none of them is evidence that an agent died.
    - ``observed`` maps a canonical root to the agent window names seen for it.
      A sweepable root with an **empty** set is legitimate: the session is up and
      simply has no agents left, so its marks are dead and go. That is the whole
      reason the sweepable set is passed separately rather than inferred from
      ``observed`` keys — inferring it would leave a zero-agent session's marks
      alive until the TTL, which is the behaviour this feature exists to avoid.
    - ``complete=False`` suppresses the sweep entirely for this tick. Callers set
      it when any captured pane failed strict root resolution: such a pane is
      missing from ``observed[root]`` while its root may still be sweepable, so
      its perfectly live mark would otherwise be deleted. A visibility gap must
      never be able to cause a deletion.
    """
    if not complete or not sweepable_roots:
        return []
    dropped = [
        m
        for m in mf.marks
        if m.root in sweepable_roots and m.window not in observed.get(m.root, set())
    ]
    if dropped:
        stale = {id(m) for m in dropped}
        mf.marks = [m for m in mf.marks if id(m) not in stale]
    return dropped


def visible_marks(
    mf: MarksFile,
    *,
    ttl: float | None = None,
    now: float | None = None,
) -> set[tuple[str, str]]:
    """Keys that should render, applying age expiry without mutating the store.

    The render path filters rather than writes: materializing every tick would
    spawn a locked subprocess every few seconds. :func:`expire` is the
    materializing twin, run periodically by the wrapper.
    """
    window_days = ttl_days(ttl)
    cutoff = (now if now is not None else time.time()) - window_days * 86400.0
    return {m.key for m in mf.marks if m.marked_at >= cutoff}


# --- TUI-side cached reader -------------------------------------------------


class MarksView:
    """An mtime-gated reader for the refresh tick.

    Re-reads only when the store's ``(st_mtime_ns, st_size, st_ino)`` changes,
    so a steady state costs one ``os.stat`` per tick.

    ``st_ino`` is load-bearing here, unlike in ``GateSummaryCache`` which keys
    on ``(mtime_ns, size)`` alone. That pair is sufficient for a file rewritten
    **in place**, but this store is only ever replaced via ``os.replace`` from a
    fresh temp file, and a cross-repo mark flip is frequently *equal length*
    (one window name swapped for another of the same width). On a filesystem
    with coarse timestamp granularity both fields can therefore be unchanged
    across a real content change, leaving another repo's final state invisible
    indefinitely — reproduced, not hypothetical. Every ``os.replace`` yields a
    new inode, which makes the stamp replacement-sensitive by construction.
    """

    def __init__(self, path: str | os.PathLike | None = None) -> None:
        self._path = marks_path(path)
        self._stamp: tuple[int, int, int] | None = None
        self._keys: set[tuple[str, str]] = set()
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

    def refresh(self, *, now: float | None = None) -> bool:
        """Re-read if the file changed. Returns True when a read happened."""
        stamp = self._stat_stamp()
        if self._loaded and stamp == self._stamp:
            return False
        self._stamp = stamp
        self._loaded = True
        self._keys = visible_marks(load_safe(self._path), now=now)
        return True

    def invalidate(self) -> None:
        """Force the next :meth:`refresh` to re-read.

        Used right after a toggle: the write may land inside the same coarse
        mtime tick as the previous read, which the stamp alone would not catch.
        """
        self._loaded = False
        self._stamp = None

    def is_marked(self, root: str | os.PathLike, window: str) -> bool:
        return mark_key(root, window) in self._keys


# --- CLI (driven by aitask_agent_marks.sh, under the lock) ------------------


def _read_observed(path: str) -> tuple[dict[str, set[str]], set[str], bool]:
    """Parse the observation file the TUI writes before a purge.

    Format, one record per line:

        ``ROOT<TAB><canonical-root>``            -- a successfully enumerated root
        ``WINDOW<TAB><canonical-root><TAB><name>`` -- an observed agent window
        ``INCOMPLETE``                            -- suppress the liveness sweep

    Roots are declared separately from windows precisely so a *zero-window*
    enumerated root can be expressed; a windows-only format could not say it.
    """
    observed: dict[str, set[str]] = {}
    roots: set[str] = set()
    complete = True
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            kind = parts[0]
            if kind == "INCOMPLETE":
                complete = False
            elif kind == "ROOT" and len(parts) == 2:
                roots.add(os.path.realpath(parts[1]))
            elif kind == "WINDOW" and len(parts) == 3:
                root = os.path.realpath(parts[1])
                observed.setdefault(root, set()).add(parts[2])
    return observed, roots, complete


def _cli_toggle(args) -> int:
    mf = load(args.file)
    result = toggle(mf, args.root, args.window)
    dump(mf, args.file)
    verb = "MARKED" if result.now_marked else "UNMARKED"
    print(f"{verb}:{mark_key(args.root, args.window)[0]}|{args.window}")
    return 0


def _cli_list(args) -> int:
    mf = load(args.file)
    for m in sorted(mf.marks, key=lambda m: (m.root, m.window)):
        print(f"MARK:{m.root}|{m.window}|{m.marked_at}")
    return 0


def _cli_purge(args) -> int:
    mf = load(args.file)
    dropped: list[tuple[MarkRecord, str]] = [
        (m, REASON_EXPIRED) for m in expire(mf)
    ]
    if args.observed:
        observed, roots, complete = _read_observed(args.observed)
        dropped += [
            (m, REASON_DEAD_WINDOW)
            for m in sweep_liveness(mf, observed, roots, complete=complete)
        ]
    if dropped:
        dump(mf, args.file)
    for record, reason in dropped:
        print(f"DROPPED:{record.root}|{record.window}|{reason}")
    print(f"PURGED:{len(dropped)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent_marks",
        description="Cross-repo prioritized-agent marks store (lock-free; "
        "callers own concurrency).",
    )
    parser.add_argument("--file", default=None, help="store path override")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_toggle = sub.add_parser("toggle")
    p_toggle.add_argument("root")
    p_toggle.add_argument("window")
    p_toggle.set_defaults(func=_cli_toggle)

    sub.add_parser("list").set_defaults(func=_cli_list)

    p_purge = sub.add_parser("purge")
    p_purge.add_argument("--observed", default=None)
    p_purge.set_defaults(func=_cli_purge)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except MalformedMarksError as exc:
        print(f"ERROR:{exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
