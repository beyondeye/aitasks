#!/usr/bin/env python3
"""frozen_sitrep.py - a frozen agent's sitrep state, for the monitor badge (t2337).

Answers "can I drop this frozen agent, and are its follow-ups handled?" from
evidence that already exists: the record's harvest receipt
(`<capture.txt>.harvested`) and the sitrep store's `todo.md`. Nothing is
marked by hand, nothing is written, and nothing here decides for the user:
the states are evidence, rendered by the monitor TUIs as an advisory badge.
Dropping stays the guarded `h` -> Drop path (lib/agent_freeze.py drop_record),
which re-checks everything itself.

THE STATES
  unharvested     the receipt does not certify the current capture
  nothing         harvested (or no text to lose), no linked sitrep item
  triage_open     harvested; a linked wrap-up triage question is still open
  triaged         harvested; every linked triage question is `done`
  closed          harvested; every linked item is closed, but not all as
                  "triaged" (a dismissed triage question, or only a closed
                  parser-review item)
  review_pending  harvested (raw output kept); its review case is open
  unlinked        certified by a receipt from before the link lines; the
                  maintenance harvest (`all --backfill-links`) records them
  unknown         anything unreadable, inconsistent or in flight -- never safe

"Safe" (`FrozenSitrepState.safe`) comes ONLY from the certification rule the
drop gate itself uses (agent_sessions.receipt_certifies); triage state alone
never implies it. The record -> item link is the harvest's own record in the
receipt (`links=` / `triage=c<N>` / `review=c<N>`, lib/sitrep_harvest.py),
never title or text matching.

ONE SNAPSHOT, ONE PUBLISH GATE. A verdict is derived from ONE read of the
capture and ONE read of the receipt (fstat on the open fd), plus the store's
todo.md when an item is linked. It is published -- and cached -- only after a
post-read check that every consumed input still has the version it was
derived from: the record's (state, op_nonce, capture_txt, pane_id,
standin_pid, frozen_at), the capture's, the receipt's and todo.md's
(st_ino, st_size, st_mtime_ns, st_ctime_ns -- ctime so a permission change
alone invalidates a cached verdict). That gate covers the fresh read, the cache hit
and the empty capture alike; an `unknown` verdict is never cached, since its
cause can clear with no change to any version the cache rechecks. The record
must be SETTLED (state `frozen`, no
operation lease) before and after: agent_freeze rewrites capture.txt in place
(O_TRUNC, same inode), so an empty capture is trusted only under a settled
record whose versions held. A mismatch retries once, then reports
`unknown(changed_during_read)`, uncached.

INSTANCE. A record id survives a restore + re-freeze. Each verdict carries the
frozen INSTANCE it was settled against -- (record id, pane id, stand-in pid) --
so a consumer showing it on a pane snapshot can withhold a verdict that
belongs to an earlier freeze of the same record.

REVERSE INDEX (t2350). The sitrep TUI asks the opposite question -- "is this
item's source agent still frozen?" -- through :class:`FrozenSourceIndex`. It
derives nothing of its own: it runs the tracker above over every frozen record
and inverts the verdicts that carry links (:data:`LINKED_STATES`), keeping a
record only when its receipt's ``store=`` is the asking store and its verdict
is bound to the record's current instance. Every other verdict (unknown,
unharvested, unlinked, nothing) is skipped, so a missing hint is the
fail-closed direction; the index never raises.

Stdlib only; no monitor or Textual import (lib/ never reaches into a TUI).
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import agent_sessions  # noqa: E402
import sitrep_todo  # noqa: E402

UNHARVESTED = "unharvested"
NOTHING = "nothing"
TRIAGE_OPEN = "triage_open"
TRIAGED = "triaged"
CLOSED = "closed"
REVIEW_PENDING = "review_pending"
UNLINKED = "unlinked"
UNKNOWN = "unknown"
STATES = (UNHARVESTED, NOTHING, TRIAGE_OPEN, TRIAGED, CLOSED, REVIEW_PENDING,
          UNLINKED, UNKNOWN)
SAFE_STATES = frozenset(STATES) - {UNHARVESTED, UNKNOWN}
#: The states whose verdict carries linked item ids from a certified receipt
#: (all of them safe): what the reverse index (t2350) inverts.
LINKED_STATES = frozenset({TRIAGE_OPEN, TRIAGED, CLOSED, REVIEW_PENDING})

#: The store directory's basename (lib/sitrep_harvest.py STORE_NAME).
STORE_NAME = ".aitask-sitrep"
_CID_RE = re.compile(r"\Ac([1-9][0-9]*)\Z")
#: Item states that are not closed: `unknown` is never treated as handled.
_OPEN_ITEM_STATES = frozenset({"open", "unknown"})


@dataclass(frozen=True)
class FrozenSitrepState:
    state: str
    #: ``((cid, item_state), ...)`` of the linked triage questions / review.
    triage: tuple = ()
    review: tuple = ()
    reason: str = ""
    #: ``(record id, pane id, stand-in pid)`` the verdict was settled against.
    instance: "tuple | None" = None
    #: The receipt's ``store=`` directory, on a linked verdict only (t2350).
    store: str = ""

    @property
    def safe(self) -> bool:
        return self.state in SAFE_STATES


def _unknown(reason: str, instance=None) -> FrozenSitrepState:
    return FrozenSitrepState(UNKNOWN, reason=reason, instance=instance)


class _Changed(Exception):
    """A file changed while it was being read."""


class _StoreUnreadable(Exception):
    pass


# --- versions -----------------------------------------------------------------

def _version(st) -> tuple:
    # ctime too: a chmod (a receipt made unreadable) changes nothing else, and
    # a warm cache must not keep a positive verdict past it.
    return (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def stat_version(path: str) -> "tuple | None":
    """``(ino, size, mtime_ns, ctime_ns)`` of ``path``, None when absent.
    Other errors raise."""
    try:
        return _version(os.stat(path))
    except FileNotFoundError:
        return None


def record_version(rec) -> tuple:
    return (rec.state, rec.op_nonce, rec.capture_txt, rec.pane_id,
            rec.standin_pid, rec.frozen_at)


def instance_of(rec) -> tuple:
    return (rec.id, rec.pane_id, rec.standin_pid)


def settled(rec) -> bool:
    return rec.state == agent_sessions.STATE_FROZEN and not rec.op_nonce


def _read_versioned(path: str):
    """``(bytes, version)`` from ONE open: fstat on the fd, then a full read.

    ``(None, None)`` when the file is absent. A short read (the file shrank or
    grew under the fd) raises :class:`_Changed`.
    """
    try:
        fh = open(path, "rb")
    except FileNotFoundError:
        return None, None
    with fh:
        ver = _version(os.fstat(fh.fileno()))
        data = fh.read()
    if len(data) != ver[1]:
        raise _Changed(path)
    return data, ver


# --- evidence ------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    no_text: bool
    data: bytes = b""
    #: The receipt as lines, or None when absent or undecodable.
    receipt: "list | None" = None
    #: A receipt exists but is not UTF-8: unreadable, so `unknown` -- distinct
    #: from an absent receipt (`unharvested`). Both are unsafe.
    receipt_unreadable: bool = False
    capture_ver: "tuple | None" = None
    receipt_ver: "tuple | None" = None


def read_evidence(rec) -> Evidence:
    """The capture and its receipt, each read once. See the module doc."""
    txt = rec.capture_txt
    if not txt:
        return Evidence(no_text=True)
    receipt_path = txt + agent_sessions.HARVEST_RECEIPT_SUFFIX
    data, cver = _read_versioned(txt)
    if data is None:
        # No capture, nothing to lose. The receipt is not read, but its
        # version is still recorded: the publish gate stats both paths, and a
        # leftover receipt must not look like a change on every attempt.
        return Evidence(no_text=True, receipt_ver=stat_version(receipt_path))
    rdata, rver = _read_versioned(receipt_path)
    receipt = None
    unreadable = False
    if rdata is not None:
        try:
            receipt = rdata.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            unreadable = True
    return Evidence(no_text=not data, data=data, receipt=receipt,
                    receipt_unreadable=unreadable, capture_ver=cver,
                    receipt_ver=rver)


def parse_links(lines: list) -> tuple:
    """``(linked, triage nums, review nums)`` from a receipt's lines.

    Raises ValueError on a malformed link line, an unknown `links=` version,
    or link ids without a `links=` line.
    """
    linked = False
    triage: list = []
    review: list = []
    for line in lines:
        key, sep, value = line.partition("=")
        if not sep:
            continue
        if key == "links":
            if value != str(agent_sessions.HARVEST_RECEIPT_LINKS):
                raise ValueError(f"links={value}")
            linked = True
        elif key in ("triage", "review"):
            m = _CID_RE.match(value)
            if not m:
                raise ValueError(f"{key}={value}")
            bucket = triage if key == "triage" else review
            num = int(m.group(1))
            if num not in bucket:
                bucket.append(num)
    if (triage or review) and not linked:
        raise ValueError("link ids without links=")
    return linked, tuple(triage), tuple(review)


def _receipt_store(lines: list) -> str:
    for line in lines:
        if line.startswith("store="):
            store = line[len("store="):]
            if os.path.isabs(store) and os.path.basename(store) == STORE_NAME:
                return store
            raise ValueError(f"store={store}")
    raise ValueError("no store=")


def derive(rec, ev: Evidence, todo_reader) -> tuple:
    """``(state, todo consumed or None)`` from ONE :class:`Evidence`.

    ``todo_reader(store_dir)`` returns ``(items, version, sha256)`` --
    ``items`` maps item number -> state -- or raises. The returned "consumed"
    triple ``(store_dir, version, sha256)`` is what the publish gate rechecks.
    """
    inst = instance_of(rec)
    if ev.no_text:
        return FrozenSitrepState(NOTHING, instance=inst), None
    if ev.receipt_unreadable:
        return _unknown("receipt_unreadable", inst), None
    lines = ev.receipt
    if lines is None or not agent_sessions.receipt_certifies(lines, ev.data):
        return FrozenSitrepState(UNHARVESTED, instance=inst), None
    try:
        linked, triage, review = parse_links(lines)
    except ValueError:
        return _unknown("receipt_malformed", inst), None
    if not linked:
        return FrozenSitrepState(UNLINKED, instance=inst), None
    if not triage and not review:
        return FrozenSitrepState(NOTHING, instance=inst), None
    try:
        store = _receipt_store(lines)
    except ValueError:
        return _unknown("receipt_store", inst), None
    try:
        items, tver, digest = todo_reader(store)
    except _Changed:
        raise
    except Exception:  # noqa: BLE001 - an unreadable store is unknown, never safe
        return _unknown("store_unreadable", inst), None
    consumed = (store, tver, digest)
    for num in triage + review:
        if num not in items:
            return _unknown(f"item_missing:c{num}", inst), consumed
    t = tuple((f"c{n}", items[n]) for n in triage)
    r = tuple((f"c{n}", items[n]) for n in review)
    if any(s in _OPEN_ITEM_STATES for _c, s in r):
        state = REVIEW_PENDING
    elif any(s in _OPEN_ITEM_STATES for _c, s in t):
        state = TRIAGE_OPEN
    elif t and all(s == "done" for _c, s in t):
        state = TRIAGED
    else:
        state = CLOSED
    return (FrozenSitrepState(state, triage=t, review=r, instance=inst, store=store),
            consumed)


# --- the tracker ---------------------------------------------------------------

class FrozenSitrepTracker:
    """Per-record verdicts for the monitor's background pass. See the module doc.

    ``seam`` (test-only) is called as ``seam(point, record_id)`` at
    ``"todo_read"`` (after todo.md was read, inside the reader) and at
    ``"candidate"`` (after a candidate verdict exists, before the post-check).
    """

    def __init__(self, sessions_path=None, *, seam=None) -> None:
        self._view = agent_sessions.SessionsView(sessions_path)
        #: record id -> (pre versions, todo consumed or None, state)
        self._cache: dict = {}
        #: todo.md path -> (sha256, {num: state})
        self._todo: dict = {}
        self.seam = seam
        self.derives = 0
        self.parses = 0
        self._rid = ""

    def frozen_records(self) -> list:
        """Every record the registry lists as frozen (the reverse index's input)."""
        return self._view.frozen()

    def current_records(self) -> dict:
        """``{record id: record}`` as the registry lists it NOW -- ONE fresh,
        stamp-gated read; empty when the registry has become unreadable."""
        self._view.refresh()
        return {r.id: r for r in self._view.records()}

    def states(self, record_ids) -> dict:
        out = {}
        for rid in dict.fromkeys(record_ids):
            try:
                out[rid] = self._state(rid)
            except Exception as exc:  # noqa: BLE001 - one record never breaks the rest
                # Unsafe and uncached, but still bound to the frozen instance
                # when the record resolves, so the row shows `sitrep ?` rather
                # than losing its badge (an OS-level read failure, e.g. a
                # receipt the user cannot read).
                self._cache.pop(rid, None)
                out[rid] = _unknown(type(exc).__name__, self._instance(rid))
        for rid in list(self._cache):
            if rid not in out:
                del self._cache[rid]
        return out

    def _state(self, rid: str) -> FrozenSitrepState:
        self._rid = rid
        for _attempt in range(2):
            try:
                got = self._attempt(rid)
            except _Changed:
                got = None
            if got is not None:
                return got
        self._cache.pop(rid, None)
        rec = self._view.by_id(rid)
        return _unknown("changed_during_read",
                        instance_of(rec) if rec is not None else None)

    def _instance(self, rid: str) -> "tuple | None":
        try:
            rec = self._view.by_id(rid)
        except Exception:  # noqa: BLE001 - no instance, the badge stays hidden
            return None
        return instance_of(rec) if rec is not None else None

    def _seam(self, point: str) -> None:
        if self.seam is not None:
            self.seam(point, self._rid)

    def _read_todo(self, store: str) -> tuple:
        path = os.path.join(store, "todo.md")
        data, ver = _read_versioned(path)
        if data is None:
            raise _StoreUnreadable(path)
        digest = hashlib.sha256(data).hexdigest()
        cached = self._todo.get(path)
        if cached is not None and cached[0] == digest:
            items = cached[1]
        else:
            self.parses += 1
            parsed = sitrep_todo.parse_todo(data.decode("utf-8"), path)
            items = {n: it.state for n, it in parsed.items.items()}
            self._todo[path] = (digest, items)
        self._seam("todo_read")
        return items, ver, digest

    def _file_versions(self, rec) -> tuple:
        txt = rec.capture_txt
        if not txt:
            return None, None
        return (stat_version(txt),
                stat_version(txt + agent_sessions.HARVEST_RECEIPT_SUFFIX))

    def _attempt(self, rid: str) -> "FrozenSitrepState | None":
        """One derivation through the publish gate; None when it must retry."""
        rec = self._view.by_id(rid)
        if rec is None:
            self._cache.pop(rid, None)
            return _unknown("no_record")
        if not settled(rec):
            self._cache.pop(rid, None)
            return _unknown("operation_in_flight", instance_of(rec))
        rver = record_version(rec)
        candidate = consumed = pre = None
        cached = self._cache.get(rid)
        if cached is not None:
            probe = (rver,) + self._file_versions(rec)
            cpre, ctodo, cstate = cached
            if probe == cpre:
                if ctodo is None:
                    candidate, consumed, pre = cstate, None, probe
                else:
                    try:
                        _items, tver, digest = self._read_todo(ctodo[0])
                    except _StoreUnreadable:
                        digest = None
                    if digest == ctodo[2]:
                        candidate, consumed, pre = cstate, (ctodo[0], tver, digest), probe
        if candidate is None:
            ev = read_evidence(rec)
            pre = (rver, ev.capture_ver, ev.receipt_ver)
            self.derives += 1
            candidate, consumed = derive(rec, ev, self._read_todo)
        self._seam("candidate")
        # --- the publish gate: every consumed input still at its version ---
        self._view.refresh()
        rec2 = self._view.by_id(rid)
        if rec2 is None or not settled(rec2) or record_version(rec2) != rver:
            return None
        if (rver,) + self._file_versions(rec2) != pre:
            return None
        if consumed is not None and \
                stat_version(os.path.join(consumed[0], "todo.md")) != consumed[1]:
            return None
        # An `unknown` verdict is never cached: its cause (a store not yet
        # readable, an item not yet written, ...) can clear with no change to
        # the record, capture or receipt -- the inputs a cache hit rechecks --
        # so a cached one would stick until those changed.
        if candidate.state != UNKNOWN:
            self._cache[rid] = (pre, consumed, candidate)
        else:
            self._cache.pop(rid, None)
        return candidate


# --- wording -------------------------------------------------------------------

#: At most this many ids are named in one `describe` line; the rest are counted.
#: The line sits in the 40-column minimonitor's `h` dialog, so it stays short.
_MAX_NAMED = 3


def _named(parts: list) -> str:
    if len(parts) <= _MAX_NAMED:
        return ", ".join(parts)
    return ", ".join(parts[:_MAX_NAMED]) + f" +{len(parts) - _MAX_NAMED} more"


def _cids(pairs, *, open_only: bool = False) -> str:
    return _named([c for c, s in pairs if not open_only or s in _OPEN_ITEM_STATES])


def describe(st: FrozenSitrepState) -> str:
    """The long wording for the `h` dialog. Never calls ``unknown`` safe."""
    s = st.state
    if s == UNHARVESTED:
        return ("not harvested yet — Drop harvests it first and keeps the "
                "agent if that fails")
    if s == NOTHING:
        return "harvested — safe to drop; nothing to triage"
    if s == TRIAGE_OPEN:
        return ("harvested — safe to drop; follow-ups still to triage "
                f"({_cids(st.triage, open_only=True)})")
    if s == TRIAGED:
        return f"harvested — safe to drop; follow-ups triaged ({_cids(st.triage)})"
    if s == CLOSED:
        parts = [f"{c} {state}" for c, state in st.triage]
        parts += [f"{c} review {state}" for c, state in st.review]
        return ("harvested — safe to drop; linked sitrep items closed "
                f"({_named(parts)})")
    if s == REVIEW_PENDING:
        return ("harvested — safe to drop (raw output kept); review pending "
                f"({_cids(st.review, open_only=True)})")
    if s == UNLINKED:
        return ("harvested — safe to drop; triage link not recorded yet (the "
                "next maintenance harvest records it)")
    return f"sitrep state unknown ({st.reason or 'unreadable'})"


def describe_record(record_id: str, sessions_path=None) -> str:
    """A one-shot fresh derivation, described. Best effort: ``""`` on failure."""
    try:
        st = FrozenSitrepTracker(sessions_path).states([record_id])[record_id]
        return describe(st)
    except Exception:  # noqa: BLE001 - dialog decoration only
        return ""


# --- the reverse index (t2350) ----------------------------------------------------

@dataclass(frozen=True)
class FrozenSource:
    """One frozen record linked to one sitrep item (the reverse direction)."""
    record_id: str
    window: str
    task_id: str
    frozen_at: str
    #: ``"triage"`` (a wrap-up triage question) or ``"review"`` (a review case).
    link: str
    #: The record's verdict (one of :data:`LINKED_STATES`).
    state: FrozenSitrepState


class FrozenSourceIndex:
    """item number -> the frozen records it came from. See the module doc.

    One instance owns one :class:`FrozenSitrepTracker`, so its version-keyed
    cache carries across scans: a warm scan hashes no capture.
    """

    def __init__(self, sessions_path=None, *, tracker=None) -> None:
        self._tracker = tracker or FrozenSitrepTracker(sessions_path)

    def scan(self, store_dir: str) -> dict:
        """``{item num: (FrozenSource, ...)}`` for the store ``store_dir``.

        Never raises: any failure is ``{}`` -- nothing shown, never a guess.
        """
        try:
            return self._scan(store_dir)
        except Exception:  # noqa: BLE001 - decoration only; absent is fail-closed
            return {}

    def _scan(self, store_dir: str) -> dict:
        want = os.path.realpath(store_dir)
        recs = self._tracker.frozen_records()
        verdicts = self._tracker.states([r.id for r in recs])
        kept = []
        for rec in recs:
            v = verdicts.get(rec.id)
            if v is None or v.state not in LINKED_STATES or not v.store:
                continue
            if os.path.realpath(v.store) != want:
                continue
            # The verdict must be the one settled against THIS freeze of the
            # record; a restore + re-freeze between the list read and the
            # derivation keeps the id but is another instance.
            if v.instance != instance_of(rec):
                continue
            kept.append((rec, v))
        # The verdicts are derived one record after another, each through its
        # own publish gate -- so an earlier record's verdict can be stale by
        # the time the last one is derived (a lease taken on it, or the
        # registry turned unreadable, meanwhile). Re-read the registry once
        # more and keep only records still settled at the very version they
        # were listed with: the map is published from one final snapshot.
        out: dict = {}
        current = self._tracker.current_records() if kept else {}
        for rec, v in kept:
            now = current.get(rec.id)
            if now is None or not settled(now) or record_version(now) != record_version(rec):
                continue
            for link, pairs in (("triage", v.triage), ("review", v.review)):
                for cid, _state in pairs:
                    m = _CID_RE.match(cid)
                    if not m:
                        continue
                    src = FrozenSource(rec.id, rec.window, rec.task_id,
                                       rec.frozen_at, link, v)
                    out.setdefault(int(m.group(1)), []).append(src)
        return {num: tuple(sorted(srcs, key=lambda s: (s.frozen_at, s.record_id)))
                for num, srcs in out.items()}


def describe_source(src: FrozenSource) -> str:
    """The sitrep TUI's details line for one source. Display only: it names the
    two ways to drop the agent and does neither.

    The fallback is `ait frozenagent` LIST mode (open with Enter, drop with
    `k`), which works with no monitor card and does not stamp the pane it runs
    in -- never `ait frozenagent --record <id>`, which stamps its own pane as
    the record's stand-in. The keys named are those TUIs' defaults.
    """
    who = src.window or src.record_id
    bits = [f"t{src.task_id}"] if src.task_id else []
    if src.frozen_at:
        bits.append(f"frozen {src.frozen_at}")
    head = f"{who} ({', '.join(bits)})" if bits else who
    kept = " (raw output kept)" if src.state.state == REVIEW_PENDING else ""
    return (f"{head} is still frozen — harvested, safe to drop{kept}. Drop it "
            "with  h  (Harvest) on its card in ait monitor / minimonitor; if the "
            "card is missing (e.g. after a tmux restart), run  ait frozenagent , "
            "open it (Enter) and press  k  (Drop).")
