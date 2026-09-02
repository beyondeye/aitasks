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

A mark carries a ``kind`` (t1685): ``priority`` (the ★ the feature shipped with)
or ``parked`` ("stop listing and stop checking this one"). One entry, one kind —
an agent is starred or parked, never both.

STORE VERSIONS. The current version is 2. Version 1 — which has no ``kind`` key
at all — is **migrated on read**: every v1 record is a priority mark, so it
parses through the same path and the in-memory generation is normalised to
version 2. Anything newer than 2 is still rejected outright, because a file
written by a newer framework must not be truncated to the fields this one knows.
The migration is one-directional and that cost is accepted: a pre-t1685 ``ait``
reading a v2 store renders **no marks at all**, in every project, until it is
upgraded. That is fail-safe (marks are advisory) but it is not silent about
itself — see :func:`load_safe`.

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
SCHEMA_VERSION = 2

#: The oldest on-disk version :func:`_parse` will migrate rather than reject.
OLDEST_READABLE_VERSION = 1

#: Mark kinds (t1685). A mark is priority OR parked, never both — that is what
#: keeps the cycle unambiguous and the mark column one cell wide.
KIND_PRIORITY = "priority"
KIND_PARKED = "parked"
MARK_KINDS = (KIND_PRIORITY, KIND_PARKED)

#: The "no mark here" answer from a lookup. Never stored — a record always
#: carries one of :data:`MARK_KINDS`. Exists so callers can thread one total
#: ``str`` through the render path instead of an ``Optional[str]``.
KIND_NONE = ""

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
    """One mark. ``root`` is always already-canonical (see :func:`mark_key`).

    ``kind`` defaults to :data:`KIND_PRIORITY` for the same reason an absent
    ``"kind"`` key reads as priority: that is what every v1 record means.
    """

    root: str
    window: str
    marked_at: int
    kind: str = KIND_PRIORITY

    @property
    def key(self) -> tuple[str, str]:
        return (self.root, self.window)

    @property
    def parked(self) -> bool:
        return self.kind == KIND_PARKED


@dataclass
class MarksFile:
    """An in-memory store generation. ``version`` is carried so a writer can
    refuse to downgrade a file written by a newer framework."""

    version: int
    marks: list[MarkRecord]

    def keys(self) -> set[tuple[str, str]]:
        return {m.key for m in self.marks}

    def kinds(self) -> dict[tuple[str, str], str]:
        return {m.key: m.kind for m in self.marks}

    def kind_of(self, root: str, window: str) -> str:
        """The stored kind for a key, or :data:`KIND_NONE` when unmarked."""
        return self.kinds().get(mark_key(root, window), KIND_NONE)

    def is_marked(self, root: str, window: str) -> bool:
        """True for a **priority** mark only.

        Deliberately the same narrow meaning as ``MarksView.is_marked``: two
        methods of the same name that disagreed about whether a parked agent is
        "marked" would be a trap, and every caller of either means "does this
        row show a ★". Ask :meth:`kind_of` when you mean "carries any mark".
        """
        return self.kind_of(root, window) == KIND_PRIORITY


@dataclass(frozen=True)
class CycleResult:
    """Outcome of one :func:`cycle` call.

    ``kind`` is the state the key is in **after** the call: one of
    :data:`MARK_KINDS`, or ``None`` when the mark was removed. ``record`` is the
    record that was written, or the one that was removed.
    """

    kind: str | None
    record: MarkRecord | None

    @property
    def now_marked(self) -> bool:
        """True while the key still carries a mark of either kind."""
        return self.kind is not None


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
    if version > SCHEMA_VERSION or version < OLDEST_READABLE_VERSION:
        # A NEWER file is still refused outright: it must not be truncated to
        # the fields this version understands. An OLDER one is no longer refused
        # — t1685 wrote the v1 -> v2 migration this comment used to say did not
        # exist. v1 has no `kind` key by construction, so every v1 record parses
        # as KIND_PRIORITY through the path below and the returned generation is
        # normalised to SCHEMA_VERSION (see the return statement).
        raise MalformedMarksError(
            f"unsupported store version {version} "
            f"(readable: {OLDEST_READABLE_VERSION}..{SCHEMA_VERSION})"
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
        # Absent `kind` means priority — the v1 migration and the forward-compat
        # rule for a hand-edited file, in one branch. A PRESENT but unrecognised
        # value is a corruption, not a default: fail closed like every other
        # field check here, rather than silently un-parking a parked agent.
        kind = entry.get("kind", KIND_PRIORITY)
        if kind not in MARK_KINDS:
            raise MalformedMarksError(f"bad 'kind' in entry: {entry!r}")
        # Canonicalize on read too: an entry hand-edited with a symlinked path
        # must still match a strictly-resolved lookup.
        key = mark_key(root, window)
        if key in seen:
            continue  # first spelling wins; a duplicate is not a corruption
        seen.add(key)
        marks.append(
            MarkRecord(root=key[0], window=window, marked_at=marked_at, kind=kind)
        )
    # NORMALISED, not carried: whatever the file said, the object in hand is a
    # v2 generation, and `dump` writes SCHEMA_VERSION unconditionally. Returning
    # the on-disk number would make a migrated v1 store claim to still be v1.
    return MarksFile(version=SCHEMA_VERSION, marks=marks)


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
            {
                "root": m.root,
                "window": m.window,
                "marked_at": m.marked_at,
                "kind": m.kind,
            }
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


def cycle(
    mf: MarksFile,
    root: str | os.PathLike,
    window: str,
    *,
    now: int | None = None,
) -> CycleResult:
    """Advance the mark for ``(root, window)``. Mutates ``mf`` in place.

    The cycle is **unmarked -> priority -> parked -> unmarked**. Named ``cycle``
    rather than ``toggle`` because it has three states, not two: a name that
    said "toggle" would be wrong at exactly the step that matters.

    The priority -> parked step writes a **fresh** ``marked_at``. Parking is a
    new decision with its own age, and the two kinds are aged differently
    (:func:`expire` exempts parked marks), so inheriting the star's timestamp
    would date the park from a decision the user has since changed.
    """
    key = mark_key(root, window)
    stamp = int(now if now is not None else time.time())
    for existing in mf.marks:
        if existing.key != key:
            continue
        if existing.kind == KIND_PRIORITY:
            parked = MarkRecord(
                root=key[0], window=window, marked_at=stamp, kind=KIND_PARKED
            )
            mf.marks[mf.marks.index(existing)] = parked
            return CycleResult(kind=KIND_PARKED, record=parked)
        mf.marks.remove(existing)
        return CycleResult(kind=None, record=existing)
    record = MarkRecord(
        root=key[0], window=window, marked_at=stamp, kind=KIND_PRIORITY
    )
    mf.marks.append(record)
    return CycleResult(kind=KIND_PRIORITY, record=record)


def expire(
    mf: MarksFile, *, ttl: float | None = None, now: float | None = None
) -> list[MarkRecord]:
    """Drop **priority** marks older than the TTL. Returns the dropped records.

    Needs no tmux visibility, so this is the safe general reaper: it is what
    bounds the store when a repo is never opened again.

    **Parked marks are exempt (t1685), and the asymmetry is deliberate.** A star
    is a "look at this one soon" note, and one that has gone stale is noise worth
    reaping. Parking is the opposite: a long-lived "ignore this one" intent, and
    a two-day TTL silently un-parking a background agent would re-list and
    re-check exactly the agent the user asked to stop paying for — defeating the
    feature on a timer. Parked marks are still reaped by
    :func:`sweep_liveness` when their window is actually gone, so the store
    stays bounded by something real rather than by a clock.
    """
    window_days = ttl_days(ttl)
    cutoff = (now if now is not None else time.time()) - window_days * 86400.0
    dropped = [
        m for m in mf.marks if m.kind != KIND_PARKED and m.marked_at < cutoff
    ]
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
) -> dict[tuple[str, str], str]:
    """Key -> kind for the marks that should render, applying age expiry.

    Filters rather than writes: materializing every tick would spawn a locked
    subprocess every few seconds. :func:`expire` is the materializing twin, run
    periodically by the wrapper — and this function applies the TTL to the same
    kinds it does, so the two never disagree about what is visible.
    """
    window_days = ttl_days(ttl)
    cutoff = (now if now is not None else time.time()) - window_days * 86400.0
    return {
        m.key: m.kind
        for m in mf.marks
        if m.kind == KIND_PARKED or m.marked_at >= cutoff
    }


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
        self._kinds: dict[tuple[str, str], str] = {}
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
        self._kinds = visible_marks(load_safe(self._path), now=now)
        return True

    def invalidate(self) -> None:
        """Force the next :meth:`refresh` to re-read.

        Used right after a toggle: the write may land inside the same coarse
        mtime tick as the previous read, which the stamp alone would not catch.
        """
        self._loaded = False
        self._stamp = None

    def kind_for(self, root: str | os.PathLike, window: str) -> str:
        """The visible kind for an agent, or :data:`KIND_NONE` when unmarked.

        Total by construction: every caller can thread the result straight into
        the render path without an ``Optional`` branch.
        """
        return self._kinds.get(mark_key(root, window), KIND_NONE)

    def is_marked(self, root: str | os.PathLike, window: str) -> bool:
        """True for a **priority** mark only — parked is not "marked" here.

        Kept narrow on purpose: every existing caller means "does this row show
        a star", and widening it to "carries any mark" would silently paint
        parked agents as prioritized.
        """
        return self.kind_for(root, window) == KIND_PRIORITY

    def is_parked(self, root: str | os.PathLike, window: str) -> bool:
        return self.kind_for(root, window) == KIND_PARKED

    def parked_windows(self) -> set[tuple[str, str]]:
        """Every visible parked key. The source of the per-tick capture-skip set."""
        return {k for k, kind in self._kinds.items() if kind == KIND_PARKED}


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


#: Wire verb per resulting kind. `None` (mark removed) is the third row.
_CYCLE_VERBS = {KIND_PRIORITY: "MARKED", KIND_PARKED: "PARKED", None: "UNMARKED"}


def _cli_cycle(args) -> int:
    mf = load(args.file)
    result = cycle(mf, args.root, args.window)
    dump(mf, args.file)
    verb = _CYCLE_VERBS[result.kind]
    print(f"{verb}:{mark_key(args.root, args.window)[0]}|{args.window}")
    return 0


def _cli_list(args) -> int:
    mf = load(args.file)
    for m in sorted(mf.marks, key=lambda m: (m.root, m.window)):
        print(f"MARK:{m.root}|{m.window}|{m.marked_at}|{m.kind}")
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
        description="Cross-repo agent marks store — prioritized and parked "
        "(lock-free; callers own concurrency).",
    )
    parser.add_argument("--file", default=None, help="store path override")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cycle = sub.add_parser("cycle")
    p_cycle.add_argument("root")
    p_cycle.add_argument("window")
    p_cycle.set_defaults(func=_cli_cycle)

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
