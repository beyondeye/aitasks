#!/usr/bin/env python3
"""Format core for the sitrep store (t2175_1).

The sitrep store (``.aitask-sitrep/``) is ONE per-repo todo list that a sitrep
agent keeps so finished code-agent windows can be closed without losing their
follow-up information. This module is the *pure* half of its writer: it parses,
validates, mutates and renders the store's text files. It never takes a lock
and never replaces a store file — ``aitask_sitrep_todo.sh`` holds the
``registry_lock.sh`` mutex, rolls the backups and lands every write through
``lib/atomic_write.sh``. Mutating ops write the would-be new file to ``--out``
(left empty when nothing changes) and print result lines on stdout; lines that
start with ``@`` are directives for the wrapper, never shown to a caller.

FILES (all under the store root):

* ``todo.md`` / ``todo.md.bak`` -- Part 1 (one block per direction: its record
  and situation text; items grouped Pick now / Next / Waiting / Recently done /
  Dismissed) and Part 2 (one context entry per item: a MAP of pointers, never
  a summary).
* ``qa.md`` / ``qa.md.bak`` -- the dated Q&A log.
* ``store.init`` -- written LAST by the one-time initialization; see
  :func:`store_state`.
* ``next_id`` / ``next_rev`` -- the id and revision high-water marks; see
  :func:`alloc_id` and :func:`alloc_rev` (revs are store-wide stamps, never
  reused -- not per-item counters).
* ``sources/<16 hex>.txt`` -- retained passages (content-addressed, immutable).
  Agent captures under ``~/.config/aitasks/frozen/`` are deleted by drop,
  re-registration and freeze_abort, so a ``capture:`` source may only point
  here.
* ``raw/<16 hex>.txt`` -- whole raw inputs kept VERBATIM for a harvest review
  case (``retain-raw``, t2175_6; content-addressed, immutable, never pruned).
* ``cases/<16 hex>.txt`` -- the TRUSTED review-case records (origin, analysis,
  review, key; ``retain-case``, which accepts only those headers). Context
  pointers reach them through byte-identical ``sources/`` copies;
  ``check-sources`` follows a pointer to the raw input only when the trusted
  origin record exists.
* ``baselines/<16 hex>.txt`` -- direction baseline snapshots (``retain-baseline``;
  content-addressed, immutable, never pruned). A direction's ``digest`` is the
  name of the snapshot its summary was written from.
* ``recovered/`` -- damaged files preserved by ``restore``, and the pre-upgrade
  bytes of a todo.md that a write moved to a newer format.

STRICT FORMAT. Line 1 of every data file is a fixed generated-file banner and
line 2 a ``format=`` header. :func:`parse_todo` / :func:`parse_qa` build the
model loosely and then require ``render(model) == text``: any byte that the
renderer would not have produced -- a hand edit, a reordered record, a stray
blank line -- is a :class:`FormatError` naming the first differing line. So
render∘parse is the identity on writer output by construction.

CONSUMER CONTRACT. ``tests/fixtures/sitrep/`` holds a writer-produced store and
``tests/test_sitrep_todo.sh`` pins its ``list``/``context``/``check-sources``
output. A format change edits that fixture and bumps ``format=``.

FORMAT VERSIONS. todo.md is format 4:
* format 2 adds the ``push:<branch>@<sha>`` ref (a push reminder, created by the
  sitrep skill and checked by the refresh, t2175_3);
* format 3 adds the ``recover:t<N>[_<M>]`` ref (one crash-recovery item per
  task, kind=task, written only by ``recovery-apply``) and the ``incarnation``
  origin key (the 12-hex episode that item's evidence belongs to, t2299_1);
* format 4 adds the direction record (t2335_1): every block under
  ``### Situation`` is ``#### <slug> | rev=<N>`` plus nine fixed header lines,
  and the context key naming an item's direction is ``direction`` (formats 1-3
  spell it ``theme``).
Older files are still read -- render emits the parsed version, so render∘parse
stays the identity -- and the first write that CHANGES one upgrades it to the
current format (a no-op leaves it byte-identical). A file holding a ref, key or
heading newer than its own format is refused.
``tests/fixtures/sitrep/store_v1/``, ``store_v2/`` and ``store_v3/`` pin the
older reads. qa.md is unchanged and stays format 1.

MIXED VERSIONS. A writer older than a file's format fails closed on it, but
its ``restore`` would install any backup its own parser accepts. So the write
that upgrades a file also hands the wrapper the previous generation rendered
in the new format (``--out-bak``): no older-format backup is ever left behind
a newer live file. And a file whose format is NEWER than this module supports
raises :class:`NewerFormatError`; the wrapper's ``restore`` refuses it.

DIRECTIONS. A direction is a slug (``DIRECTION_RE``). Its members are the
items whose context names it -- membership is never stored in the block -- plus,
for the reserved ``crashed-agents`` slug, every ``recover:`` item whose context
names none. Its record (:class:`Direction`) holds the agent-written fields
(title, rank, trails, next, summary, digest) and the refresh-written ones
(freshness, checked_at, drift). ``digest`` names the retained baseline snapshot
the summary was written from; a hash alone could say that something changed,
never what. A direction's ``rev`` covers its whole block and nothing else, so
a freshness verdict also carries a membership stamp (:func:`direction_stamp`)
that is re-checked under the writer lock. A write that changes membership
resets the freshness of the blocks it touches.

RECOVERY ITEMS. ``recovery-apply`` is the one verb that creates a ``recover:``
item or changes its recorded incarnation; ``add`` refuses the ref, ``update``
cannot set, change or re-kind it, and ``upsert-context`` must keep the recorded
incarnation. A dismissal is scoped to the recorded incarnation: an apply that
names the same episode keeps the item dismissed, a different one (with its
context, ``--state open``) reopens it. A state-only apply (no context) passes
the item's RECORDED incarnation, never a newly observed one.

REVISIONS cover the item AND its context entry: every change to either gives
the item a fresh store-wide rev, so a refresh verdict computed from an older
state of either (e.g. a swapped ``trail:`` source) fails the batch's rev check.

Exit codes of the CLI: 0 ok, 2 bad request (:class:`RequestError`), 4 store
unusable (:class:`FormatError`).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field

# todo.md is format 4 since t2335_1 (direction records and the `direction`
# context key); formats 1-3 are still READ (render emits the parsed version,
# so render∘parse stays the identity) and are upgraded by the first write that
# changes them. qa.md did not change and stays format 1.
TODO_FORMAT_VERSION = 4
TODO_READ_FORMATS = (1, 2, 3, 4)
QA_FORMAT_VERSION = 1

TODO_BANNER = (
    "<!-- GENERATED FILE - DO NOT EDIT MANUALLY. Machine-written by "
    ".aitask-scripts/aitask_sitrep_todo.sh in a strict format; a manual edit "
    "makes the store unreadable (recover with: aitask_sitrep_todo.sh restore "
    "todo). -->"
)
QA_BANNER = (
    "<!-- GENERATED FILE - DO NOT EDIT MANUALLY. Machine-written by "
    ".aitask-scripts/aitask_sitrep_todo.sh in a strict format; a manual edit "
    "makes the store unreadable (recover with: aitask_sitrep_todo.sh restore "
    "qa). -->"
)
QA_HEADER = f"<!-- aitask-sitrep qa format={QA_FORMAT_VERSION} -->"
_TODO_HEADER_RE = re.compile(r"^<!-- aitask-sitrep todo format=([1-9][0-9]*) -->\Z")
# The first format whose grammar has the `push:` ref.
PUSH_REF_FORMAT = 2
# The first format whose grammar has the `recover:` ref and the `incarnation`
# origin key.
RECOVER_FORMAT = 3
# The first format whose grammar has direction records (the `| rev=` heading and
# the nine header lines) and spells the context key `direction`.
DIRECTION_FORMAT = 4


def todo_header(version: int) -> str:
    return f"<!-- aitask-sitrep todo format={version} -->"


TODO_HEADER = todo_header(TODO_FORMAT_VERSION)
TODO_TITLE = "# Sitrep todo"
QA_TITLE = "# Sitrep Q&A log"
PART1 = "## Part 1: Todo"
PART2 = "## Part 2: Context"
SITUATION = "### Situation"

KINDS = ("task", "action", "question", "watch")
STATES = ("open", "done", "dismissed", "unknown")
GROUPS = ("now", "next", "waiting")
DERIVED = ("script", "agent")
# Rendered section order. The heading an item sits under is a pure function of
# (state, group) -- see _slot_of.
SLOTS = (
    ("now", "### Pick now"),
    ("next", "### Next"),
    ("waiting", "### Waiting"),
    ("done", "### Recently done"),
    ("dismissed", "### Dismissed"),
)
SLOT_HEADINGS = {h: s for s, h in SLOTS}

CONTEXT_KEYS = ("background", "origin", "direction", "sources", "related")
#: How formats 1-3 spell the context key that names an item's direction.
LEGACY_DIRECTION_KEY = "theme"


def direction_key(fmt: int) -> str:
    """The context key naming an item's direction in a file of format `fmt`."""
    return "direction" if fmt >= DIRECTION_FORMAT else LEGACY_DIRECTION_KEY


def context_keys(fmt: int) -> tuple:
    return tuple(direction_key(fmt) if k == "direction" else k for k in CONTEXT_KEYS)


DENIED_CONTEXT_KEYS = frozenset({
    "status", "state", "next", "todo", "count", "counts", "progress",
    "summary", "overlap", "eta", "blocked", "done",
})
ORIGIN_KEYS = frozenset({"agent", "task", "commit", "date", "skill", "pane",
                         "incarnation"})
SOURCE_TYPES = ("task", "plan", "trail", "capture", "commit", "artifact",
                "file", "url")

MAX_TITLE = 200
MAX_OUTCOME = 200
MAX_BACKGROUND = 400
MAX_CONTEXT_BYTES = 2000
MAX_SITUATION_BYTES = 1200
MAX_QA_BYTES = 4000
MAX_RETAIN_BYTES = 64 * 1024
#: Cap of one verbatim raw input (`retain-raw`, t2175_6): a whole agent capture
#: kept for review. Above it the harvest fails closed (the capture stays
#: protected) -- a raw input is never truncated.
MAX_RAW_BYTES = 64 * 1024 * 1024
RAW_RE = re.compile(r"^raw/([0-9a-f]{16})\.txt\Z")
#: Line 1 of each TRUSTED harvest review-case record (t2175_6). These live in
#: their own namespace, ``cases/<16 hex>.txt``, written only by `retain-case`
#: (which refuses any other first line). ``sources/`` also holds harvested
#: passages whose text an agent controls, so nothing about a case is ever
#: read from there by header: a forged passage beginning with a header has no
#: `cases/` twin and stays plain passage text.
CASE_ORIGIN_HEADER = "sitrep harvest case origin v1"
CASE_ANALYSIS_HEADER = "sitrep harvest analysis v1"
CASE_REVIEW_HEADER = "sitrep harvest review v1"
CASE_KEY_HEADER = "sitrep harvest case key v1"
CASE_RECORD_HEADERS = (CASE_ORIGIN_HEADER, CASE_ANALYSIS_HEADER,
                       CASE_REVIEW_HEADER, CASE_KEY_HEADER)

# --- directions (t2335_1) ----------------------------------------------------
#: The reserved slug every crash-recovery item belongs to unless its context
#: names another direction. Membership is derived on read; a context may not
#: name it (the detector owns recovery contexts).
RECOVERY_DIRECTION = "crashed-agents"
#: The nine header lines of a format-4 direction block, in rendered order.
DIRECTION_HEADER_KEYS = ("title", "rank", "trails", "next", "summary", "digest",
                         "freshness", "checked_at", "drift")
FRESHNESS = ("current", "stale", "unknown")
MAX_DIRECTION_TITLE = 120
MAX_DIRECTION_SUMMARY = 400
MAX_DIRECTION_TRAILS = 8
#: A drift reason is one per cause CODE; its count carries how many causes
#: share the code, its sample at most this many of their keys.
MAX_DRIFT_CODES = 32
DRIFT_SAMPLE = 3
#: The longest legal artifact handle (`art:` + 128), so a legal trail handle
#: always fits as a drift sample key.
MAX_DRIFT_KEY = 132
#: Line 1 of a direction baseline snapshot (`baselines/<16 hex>.txt`).
BASELINE_HEADER = "sitrep direction baseline v1"
#: Cap of one baseline snapshot. A snapshot is never truncated or sampled: a
#: direction above it keeps its record and reads `unknown` (baseline_too_large).
MAX_BASELINE_BYTES = 256 * 1024
BASELINE_KINDS = ("member", "task", "trail", "next")
#: The fixed background of the context entry `direction-assign` creates for an
#: item that has none (an entry needs a background and an origin).
MINIMAL_CONTEXT_BACKGROUND = ("No context was recorded for this item; this "
                              "entry holds its direction.")

# Value grammars end in \Z, never `$`: Python's `$` also matches just before a
# final newline, so "2026-11-01T10:00:00Z\n" would pass and forge a line break.
TS_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
ID_RE = re.compile(r"^c?([1-9][0-9]*)\Z")
DIRECTION_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*\Z")
# A format-4 direction heading. Structural: situation text may not start with
# `#`, so nothing else in a store file can put a rev at this position.
DIRECTION_HEADING_RE = re.compile(r"^#### ([a-z0-9][a-z0-9_-]*) \| rev=([1-9][0-9]*)\Z")
# The `art:trail-` subset of artifact_manifest.HANDLE_RE (`art:` + 1..128 of
# [a-z0-9._-], first one alphanumeric): at most 132 characters.
TRAIL_HANDLE_RE = re.compile(r"^art:trail-[a-z0-9._-]{1,122}\Z")
# The name of a retained baseline snapshot: sha256 of its bytes, 16 hex.
DIGEST_RE = re.compile(r"^[0-9a-f]{16}\Z")
BASELINE_RE = re.compile(r"^baselines/([0-9a-f]{16})\.txt\Z")
DRIFT_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}\Z")
DRIFT_KEY_RE = re.compile(r"^[A-Za-z0-9._:#@/=-]{1,%d}\Z" % MAX_DRIFT_KEY)
_DRIFT_REASON_RE = re.compile(
    r"^([a-z][a-z0-9_]{0,31})(?::([1-9][0-9]*)(?::(.+))?)?\Z")
# A baseline line's opaque value (task status, trail version, next validity).
BASELINE_VALUE_RE = re.compile(r"^[A-Za-z0-9._:#@/+=,-]{0,120}\Z")
LOCAL_REF_RE = re.compile(r"^t?([1-9][0-9]*(?:_[1-9][0-9]*)?)\Z")
XREF_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)#t?([1-9][0-9]*(?:_[1-9][0-9]*)?)\Z")
# A push reminder (t2175_3): `push:<branch>@<sha>` -- "push <branch> so <sha>
# reaches its remote". The branch is a shell-safe subset of git's ref grammar
# (no `..`, `//`, a component starting with `.`, trailing `/`, `.` or `.lock`); the refresh additionally runs
# `git check-ref-format --branch` before using it, always as one argv element.
PUSH_REF_RE = re.compile(
    r"^push:([A-Za-z0-9_][A-Za-z0-9._/-]*)@([0-9a-fA-F]{7,40})\Z")
# A crash-recovery item (t2299_1): `recover:t<N>[_<M>]` -- one item per task,
# kind=task. The `t` is mandatory and lower case; the ref is accepted only in
# its canonical spelling (no normalization), so dedup by ref stays exact.
RECOVER_REF_RE = re.compile(r"^recover:t([1-9][0-9]*(?:_[1-9][0-9]*)?)\Z")
# The `incarnation` origin value: the 12-hex episode key of a recovery item.
INCARNATION_RE = re.compile(r"^[0-9a-f]{12}\Z")
CAPTURE_RE = re.compile(r"^sources/([0-9a-f]{16})\.txt#L([1-9][0-9]*)(?:-L([1-9][0-9]*))?\Z")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}\Z")
URL_RE = re.compile(r"^https?://\S+\Z")
ITEM_RE = re.compile(
    r"^- c([1-9][0-9]*) \| rev=([1-9][0-9]*) \| kind=(\S*) \| state=(\S*)"
    r" \| group=(\S*) \| checked_at=(\S*) \| ref=(\S*) \| derived=(\S*)"
    r" \| outcome=([^|]*?) \| (.*)$"
)
# Structural id positions, used by alloc_id. Deliberately NOT a free-text
# `\bc\d+` scan: a commit sha such as `c1234567` in an origin line would
# otherwise inflate the high-water mark.
_ID_POSITIONS = (
    re.compile(r"^- c([1-9][0-9]*) \| "),
    re.compile(r"^### c([1-9][0-9]*)\s*$"),
)
_REV_RE = re.compile(r"^- c[1-9][0-9]* \| rev=([1-9][0-9]*) \| ")
# Direction revs come from the same store-wide counter, so the high-water scan
# reads the heading position too.
_DIRECTION_REV_RE = re.compile(r"^#### [a-z0-9][a-z0-9_-]* \| rev=([1-9][0-9]*)\s*$")
_QA_ITEMS_RE = re.compile(r"^## .* \| items: (.*)$")
_RELATED_RE = re.compile(r"^- related: (.*)$")
_CID_RE = re.compile(r"\bc([1-9][0-9]*)\b")

FROZEN_HINT = ("agent captures under ~/.config/aitasks/frozen/ are deleted by "
               "drop, re-registration and freeze_abort; retain the passage with "
               "`aitask_sitrep_todo.sh retain` and point at the returned "
               "sources/<hex>.txt#L<a>-L<b>")


class RequestError(Exception):
    """The caller's request is invalid (exit 2). Nothing is written."""


class FormatError(Exception):
    """A store file is not in the strict format (exit 4: do not retry)."""

    def __init__(self, path: str, line: int, msg: str):
        super().__init__(f"{path}:{line}: {msg}")


class NewerFormatError(FormatError):
    """The file was written by a NEWER format than this module reads. It is not
    damaged: restoring a backup over it would roll a newer store back. Still
    exit 4, with a message that says to update the checkout."""

    def __init__(self, path: str, found: int):
        super().__init__(path, 2, f"format={found} is newer than this writer "
                         f"supports (up to format={TODO_FORMAT_VERSION}): the store "
                         "was written by a newer aitasks -- update this checkout; "
                         "do not restore over it")
        self.found = found


# --- model -------------------------------------------------------------------

@dataclass
class Item:
    num: int
    rev: int
    kind: str
    state: str
    group: str
    checked_at: str
    ref: str
    derived: str
    outcome: str
    title: str

    @property
    def cid(self) -> str:
        return f"c{self.num}"

    def line(self) -> str:
        return (f"- c{self.num} | rev={self.rev} | kind={self.kind} | "
                f"state={self.state} | group={self.group} | "
                f"checked_at={self.checked_at} | ref={self.ref} | "
                f"derived={self.derived} | outcome={self.outcome} | {self.title}")

    def machine(self) -> str:
        return (f"ITEM:c{self.num}|{self.rev}|{self.kind}|{self.state}|"
                f"{self.group}|{self.checked_at}|{self.ref}|{self.derived}|"
                f"{self.outcome}|{self.title}")


@dataclass
class ContextEntry:
    background: str = ""
    origin: list = field(default_factory=list)      # [(key, value)]
    direction: str = ""
    sources: list = field(default_factory=list)     # [(type, pointer)]
    related: list = field(default_factory=list)     # [int]

    def body_lines(self, fmt: int = TODO_FORMAT_VERSION) -> list:
        """The entry's lines as a file of format `fmt` spells them. Every
        caller outside the renderer wants the current spelling (the default):
        writer input, `context c<N>` output and equality checks."""
        out = [f"- background: {self.background}",
               "- origin: " + " ".join(f"{k}={v}" for k, v in self.origin)]
        if self.direction:
            out.append(f"- {direction_key(fmt)}: {self.direction}")
        if self.sources:
            out.append("- sources:")
            out.extend(f"  - {t}: {p}" for t, p in self.sources)
        if self.related:
            out.append("- related: " + ", ".join(f"c{n}" for n in self.related))
        return out


def render_reason(reason) -> str:
    """One drift reason `(code, count, keys)` as text. count 0 is the bare
    `code` form (no count known)."""
    code, count, keys = reason
    if not count:
        return code
    return f"{code}:{count}" + (":" + "+".join(keys) if keys else "")


def _header_line(key: str, value: str) -> str:
    return f"- {key}: {value}" if value else f"- {key}:"


@dataclass
class Direction:
    """One direction block: the record plus its situation text.

    `rev` 0 means "not stamped yet" -- a block read from a format 1-3 file,
    which has no rev; the write that upgrades the file stamps it.
    """
    rev: int = 0
    title: str = ""
    rank: int = 0                                   # 0 = unranked
    trails: list = field(default_factory=list)      # [handle]
    next: str = ""
    summary: str = ""
    digest: str = ""
    freshness: str = "unknown"
    checked_at: str = "never"
    drift: list = field(default_factory=list)       # [(code, count, [keys])]
    situation: list = field(default_factory=list)   # [lines]

    def header_lines(self) -> list:
        values = (self.title, str(self.rank) if self.rank else "",
                  ", ".join(self.trails), self.next, self.summary, self.digest,
                  self.freshness, self.checked_at,
                  ", ".join(render_reason(r) for r in self.drift))
        return [_header_line(k, v) for k, v in zip(DIRECTION_HEADER_KEYS, values)]

    def has_agent_fields(self) -> bool:
        return bool(self.title or self.rank or self.trails or self.next
                    or self.summary)

    def is_empty(self) -> bool:
        """Nothing agent-written is left: such a block does not exist."""
        return not self.situation and not self.has_agent_fields()

    def reset_freshness(self) -> bool:
        """Back to "not checked". True when that changed the block."""
        if (self.freshness, self.checked_at, self.drift) == ("unknown", "never", []):
            return False
        self.freshness, self.checked_at, self.drift = "unknown", "never", []
        return True


@dataclass
class TodoStore:
    directions: dict = field(default_factory=dict)  # slug -> Direction
    items: dict = field(default_factory=dict)       # num -> Item
    contexts: dict = field(default_factory=dict)    # num -> ContextEntry
    # The `format=` of line 2: the parsed one for a read file, the current one
    # for a new or rewritten file (see _commit_todo).
    format: int = TODO_FORMAT_VERSION
    # Not rendered. `loaded_members` is {item num: direction slug} as the file
    # read it (set by load_todo); _commit_todo compares it with the membership
    # being written and resets the freshness of every block that gained or lost
    # a member, recording their slugs in `reset_directions`.
    loaded_members: "dict | None" = None
    reset_directions: list = field(default_factory=list)


@dataclass
class QaEntry:
    ts: str
    items: list   # [int]
    body: list    # [lines]


@dataclass
class QaLog:
    entries: list = field(default_factory=list)


# --- rendering ---------------------------------------------------------------

def _slot_of(item: Item) -> str:
    if item.state in ("done", "dismissed"):
        return item.state
    return item.group


def render_todo(store: TodoStore) -> str:
    lines = [TODO_BANNER, todo_header(store.format), TODO_TITLE, "", PART1, "",
             SITUATION, ""]
    for slug in sorted(store.directions):
        d = store.directions[slug]
        if store.format >= DIRECTION_FORMAT:
            lines.append(f"#### {slug} | rev={d.rev}")
            lines.extend(d.header_lines())
        else:
            lines.append(f"#### {slug}")
        lines.extend(d.situation)
        lines.append("")
    for slot, heading in SLOTS:
        lines.extend([heading, ""])
        members = [store.items[n] for n in sorted(store.items)
                   if _slot_of(store.items[n]) == slot]
        if members:
            lines.extend(i.line() for i in members)
            lines.append("")
    lines.extend([PART2, ""])
    for num in sorted(store.contexts):
        lines.append(f"### c{num}")
        lines.extend(store.contexts[num].body_lines(store.format))
        lines.append("")
    return "\n".join(lines)


def render_qa(log: QaLog) -> str:
    lines = [QA_BANNER, QA_HEADER, QA_TITLE, ""]
    for e in log.entries:
        items = ",".join(f"c{n}" for n in e.items) if e.items else "-"
        lines.append(f"## {e.ts} | items: {items}")
        lines.extend(e.body)
        lines.append("")
    return "\n".join(lines)


def empty_text(kind: str) -> str:
    return render_todo(TodoStore()) if kind == "todo" else render_qa(QaLog())


# --- parsing -----------------------------------------------------------------

def _canonical_check(path: str, text: str, rendered: str) -> None:
    if rendered == text:
        return
    a, b = text.split("\n"), rendered.split("\n")
    for i, (x, y) in enumerate(zip(a, b), start=1):
        if x != y:
            raise FormatError(path, i, f"not in canonical form (found {x!r})")
    raise FormatError(path, min(len(a), len(b)),
                      "not in canonical form (unexpected end of file or trailing content)")


def _check_preamble(path: str, lines: list, banner: str, header: str) -> None:
    if not lines or lines[0] != banner:
        raise FormatError(path, 1, "missing or altered generated-file banner "
                          "(the file was edited by hand?)")
    if len(lines) < 2 or lines[1] != header:
        found = lines[1] if len(lines) > 1 else ""
        raise FormatError(path, 2, f"unsupported or missing format header {found!r}")


def _todo_format(path: str, lines: list) -> int:
    """Check the todo preamble; return the `format=` of line 2."""
    found = lines[1] if len(lines) > 1 else ""
    m = _TODO_HEADER_RE.match(found)
    # Before the banner check, and whatever the line endings: a newer writer may
    # word its banner or end its lines differently, and its file must still
    # read as newer, never as hand-edited.
    newer = newer_format("\n".join(lines[:2]))
    if newer:
        raise NewerFormatError(path, newer)
    if not lines or lines[0] != TODO_BANNER:
        raise FormatError(path, 1, "missing or altered generated-file banner "
                          "(the file was edited by hand?)")
    if not m or int(m.group(1)) not in TODO_READ_FORMATS:
        raise FormatError(path, 2, f"unsupported or missing format header {found!r}")
    return int(m.group(1))


def newer_format(text: "str | None"):
    """The `format=` of a todo text whose line 2 is a well-formed header NEWER
    than this module supports, else None. Such a file is not damage. Line 1
    is not consulted (a newer writer may word its banner differently) and CR
    line endings are tolerated: the question is only what line 2 declares."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) < 2:
        return None
    m = _TODO_HEADER_RE.match(lines[1].rstrip(" \t"))
    if m and int(m.group(1)) > TODO_FORMAT_VERSION:
        return int(m.group(1))
    return None


def _parse_context_body(lines: list, fmt: int = TODO_FORMAT_VERSION) -> ContextEntry:
    """Parse context-entry body lines as a file of format `fmt` spells them
    (the default is the current format, which is also what writer input
    uses). Raises ValueError((index, msg))."""
    allowed = context_keys(fmt)
    dir_key = direction_key(fmt)
    seen = {}
    sources = []
    in_sources = False
    for idx, raw in enumerate(lines):
        line = raw.rstrip()
        if not line:
            continue
        m = re.match(r"^- ([A-Za-z_][A-Za-z0-9_-]*):(?: (.*))?$", line)
        if m:
            key, val = m.group(1), (m.group(2) or "").strip()
            low = key.lower()
            if low in DENIED_CONTEXT_KEYS:
                raise ValueError((idx, f"context key '{key}' is not allowed: a context "
                                  "entry is a map of pointers, not a status record -- "
                                  "status belongs in Part 1 or is derived from the sources"))
            if key == "direction" and fmt < DIRECTION_FORMAT:
                raise ValueError((idx, f"the direction context key needs "
                                  f"format={DIRECTION_FORMAT} (this file is "
                                  f"format={fmt})"))
            if key not in allowed:
                raise ValueError((idx, f"unknown context key '{key}' (allowed: "
                                  f"{', '.join(allowed)})"))
            if key in seen:
                raise ValueError((idx, f"duplicate context key '{key}'"))
            seen[key] = (idx, val)
            in_sources = key == "sources"
            if in_sources and val:
                raise ValueError((idx, "'- sources:' takes its pointers on the "
                                  "following '  - <type>: <pointer>' lines"))
            continue
        m = re.match(r"^  - ([A-Za-z_][A-Za-z0-9_-]*): (.+)$", line)
        if m and in_sources:
            sources.append((idx, m.group(1), m.group(2).strip()))
            continue
        raise ValueError((idx, f"not a context line: {line!r} (expected "
                          "'- <key>: <value>' or, under '- sources:', "
                          "'  - <type>: <pointer>')"))
    entry = ContextEntry()
    if "background" not in seen or not seen["background"][1]:
        raise ValueError((0, "context entry needs a non-empty '- background:' line"))
    if "origin" not in seen or not seen["origin"][1]:
        raise ValueError((0, "context entry needs a non-empty '- origin:' line"))
    entry.background = seen["background"][1]
    idx, origin = seen["origin"]
    okeys = set()
    for tok in origin.split():
        k, sep, v = tok.partition("=")
        if not sep or not v:
            raise ValueError((idx, f"origin token {tok!r} is not key=value"))
        if k not in ORIGIN_KEYS:
            raise ValueError((idx, f"unknown origin key '{k}' (allowed: "
                              f"{', '.join(sorted(ORIGIN_KEYS))})"))
        if k in okeys:
            raise ValueError((idx, f"duplicate origin key '{k}'"))
        okeys.add(k)
        entry.origin.append((k, v))
    if dir_key in seen:
        entry.direction = seen[dir_key][1]
    if "sources" in seen:
        if not sources:
            raise ValueError((seen["sources"][0], "'- sources:' with no pointers"))
        entry.sources = [(t, p) for _, t, p in sources]
    if "related" in seen:
        idx, rel = seen["related"]
        for tok in [t.strip() for t in rel.split(",")]:
            m = ID_RE.match(tok)
            if not m or not tok.startswith("c"):
                raise ValueError((idx, f"related id {tok!r} is not c<N>"))
            entry.related.append(int(m.group(1)))
    return entry


def parse_reason(tok: str) -> tuple:
    """One drift reason: `code`, `code:<count>` or `code:<count>:<k1>[+<k2>…]`
    -> (code, count, [keys]); count 0 for the bare form. Raises RequestError."""
    m = _DRIFT_REASON_RE.match(tok)
    if not m:
        raise RequestError(f"invalid drift reason {tok!r} (expected <code>, "
                           "<code>:<count> or <code>:<count>:<key>[+<key>[+<key>]])")
    keys = m.group(3).split("+") if m.group(3) else []
    return (m.group(1), int(m.group(2)) if m.group(2) else 0, keys)


def _check_drift(reasons: list) -> None:
    if len(reasons) > MAX_DRIFT_CODES:
        raise RequestError(f"more than {MAX_DRIFT_CODES} drift reasons -- a reason "
                           "is one per cause code; its count carries the causes")
    seen = set()
    for code, count, keys in reasons:
        if not DRIFT_CODE_RE.match(code):
            raise RequestError(f"invalid drift code {code!r}")
        if code in seen:
            raise RequestError(f"drift code {code!r} appears twice -- aggregate "
                               "the causes of one code into its count")
        seen.add(code)
        if count < 0 or (keys and not count):
            raise RequestError(f"drift reason {code!r}: a sample needs a count")
        if len(keys) > DRIFT_SAMPLE:
            raise RequestError(f"drift reason {code!r} samples more than "
                               f"{DRIFT_SAMPLE} keys")
        if len(keys) > count:
            raise RequestError(f"drift reason {code!r}: count {count} is below "
                               f"its sample of {len(keys)} keys")
        if len(set(keys)) != len(keys):
            raise RequestError(f"drift reason {code!r} repeats a sample key")
        for k in keys:
            if not DRIFT_KEY_RE.match(k):
                raise RequestError(f"drift reason {code!r}: invalid sample key {k!r}")


def _drift_sort_key(key: str):
    m = re.match(r"^c([1-9][0-9]*)\Z", key)
    return (0, int(m.group(1)), "") if m else (1, 0, key)


def aggregate_drift(pairs) -> list:
    """`(code, key)` causes -> one reason per code, codes in first-seen order.

    The count is the number of distinct causes of the code (a cause with no key
    counts once per occurrence); the sample is its first DRIFT_SAMPLE keys in
    sorted order (item ids by number, the rest by bytes). A key that does not
    fit the key grammar is LEFT OUT of the sample -- never cut, never a reason
    to fail -- and still counted, so a reason whose keys all fail to fit is the
    count-only form. More than MAX_DRIFT_CODES codes is a RequestError.
    """
    order, keyed, bare = [], {}, {}
    for code, key in pairs:
        if not DRIFT_CODE_RE.match(code or ""):
            raise RequestError(f"invalid drift code {code!r}")
        if code not in keyed:
            order.append(code)
            keyed[code], bare[code] = [], 0
        if key:
            if key not in keyed[code]:
                keyed[code].append(key)
        else:
            bare[code] += 1
    out = []
    for code in order:
        fitting = sorted((k for k in keyed[code] if DRIFT_KEY_RE.match(k)),
                         key=_drift_sort_key)
        out.append((code, len(keyed[code]) + bare[code], fitting[:DRIFT_SAMPLE]))
    _check_drift(out)
    return out


def normalize_next(value: str) -> str:
    """A direction's `next`: "", an item id `c<N>`, or a task ref."""
    value = _no_line_breaks("next", value).strip()
    if not value or re.match(r"^c[1-9][0-9]*\Z", value):
        return value
    m = LOCAL_REF_RE.match(value)
    if m:
        return "t" + m.group(1)
    m = XREF_RE.match(value)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    raise RequestError(f"invalid next {value!r} (expected c<N>, t<N>[_<M>] or "
                       "<project>#<N>[_<M>])")


def _parse_direction_header(lines: list) -> Direction:
    """The nine header lines of a format-4 block, in their fixed order.
    Raises ValueError((index, msg))."""
    vals = {}
    for i, key in enumerate(DIRECTION_HEADER_KEYS):
        m = re.match(rf"^- {key}:(?: (.*))?\Z", lines[i])
        if not m:
            raise ValueError((i, f"direction header line {i + 1} must be "
                              f"'- {key}: <value>' (found {lines[i]!r})"))
        vals[key] = m.group(1) or ""
    d = Direction(title=vals["title"], next=vals["next"], summary=vals["summary"],
                  digest=vals["digest"], freshness=vals["freshness"],
                  checked_at=vals["checked_at"])
    if vals["rank"]:
        if not re.match(r"^[1-9][0-9]*\Z", vals["rank"]):
            raise ValueError((1, f"invalid rank {vals['rank']!r}"))
        d.rank = int(vals["rank"])
    d.trails = vals["trails"].split(", ") if vals["trails"] else []
    try:
        d.drift = ([parse_reason(t) for t in vals["drift"].split(", ")]
                   if vals["drift"] else [])
    except RequestError as e:
        raise ValueError((8, str(e))) from None
    return d


def _check_direction_values(slug: str, d: Direction) -> None:
    if not DIRECTION_RE.match(slug):
        raise RequestError(f"invalid direction {slug!r} (expected [a-z0-9][a-z0-9_-]*)")
    if d.title != _single_line("direction title", d.title, MAX_DIRECTION_TITLE, True):
        raise RequestError("direction title is not in canonical form")
    if len(d.trails) > MAX_DIRECTION_TRAILS:
        raise RequestError(f"more than {MAX_DIRECTION_TRAILS} trails on one direction")
    for h in d.trails:
        if not TRAIL_HANDLE_RE.match(h):
            raise RequestError(f"invalid trail handle {h!r} (expected art:trail-<id>, "
                               "lowercase, at most 132 characters)")
    if len(set(d.trails)) != len(d.trails):
        raise RequestError("a trail handle appears twice")
    if d.next and normalize_next(d.next) != d.next:
        raise RequestError(f"next {d.next!r} is not in canonical form")
    if d.summary != _single_line("summary", d.summary, MAX_DIRECTION_SUMMARY, True):
        raise RequestError("summary is not in canonical form")
    if d.digest and not DIGEST_RE.match(d.digest):
        raise RequestError(f"invalid digest {d.digest!r} (expected 16 hex characters)")
    if bool(d.summary) != bool(d.digest):
        raise RequestError("summary and digest are set together: a summary names "
                           "the baseline it was written from")
    if d.freshness not in FRESHNESS:
        raise RequestError(f"invalid freshness {d.freshness!r} (expected one of "
                           f"{', '.join(FRESHNESS)})")
    if d.checked_at != "never" and not TS_RE.match(d.checked_at):
        raise RequestError(f"invalid checked_at {d.checked_at!r}")
    _check_drift(d.drift)
    if d.freshness == "current" and (not d.digest or d.drift):
        raise RequestError("freshness 'current' needs a digest and no drift reason")
    if d.freshness == "stale" and not d.drift:
        raise RequestError("freshness 'stale' needs at least one drift reason")
    if d.freshness != "unknown" and d.checked_at == "never":
        raise RequestError(f"freshness {d.freshness!r} needs a checked_at")


def _check_ranks(directions: dict) -> None:
    ranks = sorted(d.rank for d in directions.values() if d.rank)
    if ranks != list(range(1, len(ranks) + 1)):
        raise RequestError("direction ranks must be exactly 1..k, each once "
                           f"(found {', '.join(map(str, ranks))})")


def parse_todo(text: str, path: str = "todo.md") -> TodoStore:
    # First of all, before any check a different line ending could trip: a file
    # from a newer writer is never reported as malformed.
    newer = newer_format(text)
    if newer:
        raise NewerFormatError(path, newer)
    if not text.endswith("\n"):
        raise FormatError(path, text.count("\n") + 1, "missing final newline")
    lines = text.split("\n")[:-1]
    store = TodoStore(format=_todo_format(path, lines))
    has_records = store.format >= DIRECTION_FORMAT
    mode = "head"
    cur = None
    blocks: dict = {}     # slug -> (lineno, rev, [lines])
    ctx_num = None
    ctx_lines: dict = {}
    for lineno, line in enumerate(lines[2:], start=3):
        if line == PART1 and mode == "head":
            mode = "p1"
            continue
        if line == SITUATION and mode == "p1":
            mode = "sit"
            continue
        if line in SLOT_HEADINGS and mode in ("sit", "items"):
            mode = "items"
            continue
        if line == PART2 and mode == "items":
            mode = "ctx"
            continue
        if mode == "sit":
            m = re.match(r"^#### (.*)$", line)
            if m:
                rev = 0
                if has_records:
                    hm = DIRECTION_HEADING_RE.match(line)
                    if not hm:
                        raise FormatError(path, lineno, f"not a direction heading: "
                                          f"{line!r} (expected '#### <slug> | rev=<N>')")
                    cur, rev = hm.group(1), int(hm.group(2))
                else:
                    cur = m.group(1)
                    if DIRECTION_HEADING_RE.match(line):
                        raise FormatError(path, lineno, f"direction records need "
                                          f"format={DIRECTION_FORMAT} (this file is "
                                          f"format={store.format})")
                    if not DIRECTION_RE.match(cur):
                        raise FormatError(path, lineno, f"invalid direction {cur!r}")
                if cur in blocks:
                    raise FormatError(path, lineno, f"duplicate direction {cur!r}")
                blocks[cur] = (lineno, rev, [])
            elif line.startswith("#"):
                raise FormatError(path, lineno, f"unexpected heading {line!r}")
            elif cur is not None:
                blocks[cur][2].append(line)
            elif line:
                raise FormatError(path, lineno, "situation text outside a "
                                  "'#### <direction>' block")
        elif mode == "items":
            if not line:
                continue
            m = ITEM_RE.match(line)
            if not m:
                raise FormatError(path, lineno, f"not an item line: {line!r}")
            item = Item(int(m.group(1)), int(m.group(2)), m.group(3), m.group(4),
                        m.group(5), m.group(6), m.group(7), m.group(8),
                        m.group(9), m.group(10))
            try:
                _check_item_values(item)
            except RequestError as e:
                raise FormatError(path, lineno, str(e)) from None
            if store.format < PUSH_REF_FORMAT and item.ref.startswith("push:"):
                raise FormatError(path, lineno, f"push refs need format={PUSH_REF_FORMAT} "
                                  f"(this file is format={store.format})")
            if store.format < RECOVER_FORMAT and item.ref.startswith("recover:"):
                raise FormatError(path, lineno, f"recover refs need format={RECOVER_FORMAT} "
                                  f"(this file is format={store.format})")
            if item.num in store.items:
                raise FormatError(path, lineno, f"duplicate item id c{item.num}")
            store.items[item.num] = item
        elif mode == "ctx":
            m = re.match(r"^### c([1-9][0-9]*)$", line)
            if m:
                ctx_num = int(m.group(1))
                if ctx_num in ctx_lines:
                    raise FormatError(path, lineno, f"duplicate context entry c{ctx_num}")
                ctx_lines[ctx_num] = (lineno, [])
            elif ctx_num is not None:
                ctx_lines[ctx_num][1].append(line)
            elif line:
                raise FormatError(path, lineno, "context text outside a '### c<N>' entry")
        else:
            if line in (TODO_TITLE, ""):
                continue
            raise FormatError(path, lineno, f"unexpected line {line!r}")
    if mode != "ctx":
        raise FormatError(path, len(lines), "missing sections (expected Part 1 and Part 2)")
    nkeys = len(DIRECTION_HEADER_KEYS)
    for slug, (lineno, rev, body) in blocks.items():
        while body and not body[-1]:
            body.pop()
        if has_records:
            if len(body) < nkeys:
                raise FormatError(path, lineno + 1 + len(body),
                                  f"direction header of {slug!r} is incomplete "
                                  f"(expected {nkeys} lines, '- title:' to '- drift:')")
            try:
                d = _parse_direction_header(body[:nkeys])
            except ValueError as e:
                off, msg = e.args[0]
                raise FormatError(path, lineno + 1 + off, msg) from None
            d.rev = rev
            d.situation = body[nkeys:]
            if d.is_empty():
                raise FormatError(path, lineno, f"direction {slug!r} holds nothing "
                                  "(an empty block does not exist)")
        else:
            d = Direction(situation=body)
        try:
            _check_direction_values(slug, d)
        except RequestError as e:
            raise FormatError(path, lineno, str(e)) from None
        store.directions[slug] = d
    try:
        _check_ranks(store.directions)
    except RequestError as e:
        raise FormatError(path, min((b[0] for b in blocks.values()), default=1),
                          str(e)) from None
    for num, (lineno, body) in ctx_lines.items():
        if num not in store.items:
            raise FormatError(path, lineno, f"context entry c{num} names no item")
        try:
            entry = _parse_context_body(body, store.format)
            _check_context_values(entry, None)
        except ValueError as e:
            off, msg = e.args[0]
            raise FormatError(path, lineno + 1 + off, msg) from None
        except RequestError as e:
            raise FormatError(path, lineno, str(e)) from None
        if store.format < RECOVER_FORMAT and context_incarnation(entry) is not None:
            off = next(i for i, ln in enumerate(body) if ln.startswith("- origin:"))
            raise FormatError(path, lineno + 1 + off,
                              f"the incarnation origin key needs format={RECOVER_FORMAT} "
                              f"(this file is format={store.format})")
        store.contexts[num] = entry
    _canonical_check(path, text, render_todo(store))
    return store


def parse_qa(text: str, path: str = "qa.md") -> QaLog:
    if not text.endswith("\n"):
        raise FormatError(path, text.count("\n") + 1, "missing final newline")
    lines = text.split("\n")[:-1]
    _check_preamble(path, lines, QA_BANNER, QA_HEADER)
    log = QaLog()
    cur = None
    for lineno, line in enumerate(lines[2:], start=3):
        if line.startswith("## "):
            m = re.match(r"^## (\S+) \| items: (.*)$", line)
            if not m or not TS_RE.match(m.group(1)):
                raise FormatError(path, lineno, f"not a Q&A entry header: {line!r}")
            try:
                items = _parse_id_list(m.group(2), allow_dash=True)
            except RequestError as e:
                raise FormatError(path, lineno, str(e)) from None
            cur = QaEntry(m.group(1), items, [])
            log.entries.append(cur)
        elif cur is not None:
            cur.body.append(line)
        elif line not in (QA_TITLE, ""):
            raise FormatError(path, lineno, f"unexpected line {line!r}")
    for e in log.entries:
        while e.body and not e.body[-1]:
            e.body.pop()
    _canonical_check(path, text, render_qa(log))
    return log


# --- validation --------------------------------------------------------------

def _single_line(name: str, value: str, limit: int, allow_pipe: bool) -> str:
    if "\n" in value or "\r" in value:
        raise RequestError(f"{name} must be a single line")
    if not allow_pipe and "|" in value:
        raise RequestError(f"{name} must not contain '|'")
    value = value.strip()
    if len(value) > limit:
        raise RequestError(f"{name} is longer than {limit} characters")
    return value


def _no_line_breaks(name: str, value: str) -> str:
    """Refuse a CR or LF anywhere in an argument value -- never strip it: a
    value that quietly loses characters is not the value the caller sent."""
    if "\n" in value or "\r" in value:
        raise RequestError(f"{name} must not contain a line break: {value!r}")
    return value


def normalize_ref(ref: str) -> str:
    ref = _no_line_breaks("ref", ref).strip()
    if not ref:
        return ""
    m = LOCAL_REF_RE.match(ref)
    if m:
        return "t" + m.group(1)
    m = XREF_RE.match(ref)
    if m:
        return f"{m.group(1)}#{m.group(2)}"
    if RECOVER_REF_RE.match(ref):
        return ref
    m = PUSH_REF_RE.match(ref)
    if m and _push_branch_ok(m.group(1)):
        return f"push:{m.group(1)}@{m.group(2).lower()}"
    raise RequestError(f"invalid ref {ref!r} (expected t<N>[_<M>], "
                       "<project>#<N>[_<M>] for a cross-repo task, "
                       "push:<branch>@<sha> for a push reminder, or "
                       "recover:t<N>[_<M>] for a crash-recovery item)")


def parse_recover_ref(ref: str):
    """The task id (``"12"`` / ``"12_3"``) of a canonical `recover:` ref, or None."""
    m = RECOVER_REF_RE.match(ref or "")
    return m.group(1) if m else None


def context_incarnation(entry) -> "str | None":
    """The `incarnation` origin value of a context entry, or None."""
    if entry is None:
        return None
    for k, v in entry.origin:
        if k == "incarnation":
            return v
    return None


def _push_branch_ok(branch: str) -> bool:
    """The parts of git's ref-name rules the character class cannot express."""
    return not (".." in branch or "//" in branch or "/." in branch
                or branch.endswith(("/", ".", ".lock")))


def parse_push_ref(ref: str):
    """(branch, sha) of a canonical `push:` ref, or None."""
    m = PUSH_REF_RE.match(ref or "")
    if not m or not _push_branch_ok(m.group(1)):
        return None
    return m.group(1), m.group(2).lower()


def normalize_ts(value: str, allow_never: bool) -> str:
    _no_line_breaks("timestamp", value)
    if value == "now":
        return now_ts()
    if allow_never and value == "never":
        return value
    if not TS_RE.match(value):
        raise RequestError(f"invalid timestamp {value!r} (expected YYYY-MM-DDTHH:MM:SSZ"
                           + (", 'now' or 'never')" if allow_never else " or 'now')"))
    return value


def parse_id(value: str) -> int:
    m = ID_RE.match(_no_line_breaks("item id", value).strip())
    if not m:
        raise RequestError(f"invalid item id {value!r} (expected c<N> or <N>)")
    return int(m.group(1))


def _parse_id_list(value: str, allow_dash: bool = False) -> list:
    value = value.strip()
    if not value or (allow_dash and value == "-"):
        return []
    out = []
    for tok in value.split(","):
        n = parse_id(tok)
        if n not in out:
            out.append(n)
    return out


def _check_item_values(item: Item) -> None:
    if item.kind not in KINDS:
        raise RequestError(f"invalid kind {item.kind!r} (expected one of {', '.join(KINDS)})")
    if item.state not in STATES:
        raise RequestError(f"invalid state {item.state!r} (expected one of {', '.join(STATES)})")
    if item.group not in GROUPS:
        raise RequestError(f"invalid group {item.group!r} (expected one of {', '.join(GROUPS)})")
    if item.derived not in DERIVED:
        raise RequestError(f"invalid derived {item.derived!r} (expected one of {', '.join(DERIVED)})")
    if item.checked_at != "never" and not TS_RE.match(item.checked_at):
        raise RequestError(f"invalid checked_at {item.checked_at!r}")
    if item.ref and normalize_ref(item.ref) != item.ref:
        raise RequestError(f"ref {item.ref!r} is not in canonical form")
    if parse_recover_ref(item.ref) and item.kind != "task":
        raise RequestError(f"a recover: ref needs kind=task (found kind={item.kind})")
    if item.outcome != _single_line("outcome", item.outcome, MAX_OUTCOME, False):
        raise RequestError("outcome is not in canonical form")
    if not item.title or item.title != _single_line("title", item.title, MAX_TITLE, True):
        raise RequestError("title must be non-empty, single-line and trimmed")


def _retained_lines(store_dir: str, hexname: str):
    path = os.path.join(store_dir, "sources", f"{hexname}.txt")
    if not os.path.isfile(path) or os.path.islink(path):
        return None
    with open(path, "rb") as fh:
        data = fh.read()
    return data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)


def _check_pointer(stype: str, ptr: str, store_dir) -> None:
    if "/.config/aitasks/frozen/" in ptr or ptr.startswith("~/.config/aitasks/frozen"):
        raise RequestError(f"source {stype}: {ptr!r} points into the agent capture "
                           f"store -- {FROZEN_HINT}")
    if stype == "capture":
        m = CAPTURE_RE.match(ptr)
        if not m:
            raise RequestError(f"capture pointer {ptr!r} must be "
                               f"sources/<16 hex>.txt#L<a>[-L<b>] -- {FROZEN_HINT}")
        a = int(m.group(2))
        b = int(m.group(3) or a)
        if b < a:
            raise RequestError(f"capture pointer {ptr!r}: range end before start")
        if store_dir is not None:
            n = _retained_lines(store_dir, m.group(1))
            if n is None:
                raise RequestError(f"capture pointer {ptr!r}: no retained file "
                                   f"sources/{m.group(1)}.txt in the store")
            if b > n:
                raise RequestError(f"capture pointer {ptr!r}: range past the end "
                                   f"of the retained file ({n} lines)")
    elif stype in ("task", "plan", "file"):
        if ptr.startswith(("/", "~")) or "\\" in ptr:
            raise RequestError(f"{stype} pointer {ptr!r} must be a repo-relative path")
        if ".." in ptr.split("#", 1)[0].split("/"):
            raise RequestError(f"{stype} pointer {ptr!r} must not contain '..'")
    elif stype == "commit":
        if not COMMIT_RE.match(ptr):
            raise RequestError(f"commit pointer {ptr!r} is not a 7-40 char hex sha")
    elif stype == "url":
        if not URL_RE.match(ptr):
            raise RequestError(f"url pointer {ptr!r} is not an http(s) URL")
    elif stype in ("trail", "artifact"):
        if any(c.isspace() for c in ptr):
            raise RequestError(f"{stype} pointer {ptr!r} must not contain whitespace")


def _check_context_values(entry: ContextEntry, store_dir) -> None:
    if "|" in entry.background:
        raise RequestError("background must not contain '|'")
    if len(entry.background) > MAX_BACKGROUND:
        raise RequestError(f"background is longer than {MAX_BACKGROUND} characters "
                           "-- keep 1-2 sentences, long material stays behind a pointer")
    for k, v in entry.origin:
        if "|" in v:
            raise RequestError("origin values must not contain '|'")
        if k == "incarnation" and not INCARNATION_RE.match(v):
            raise RequestError(f"origin incarnation {v!r} is not 12 lowercase hex characters")
    if entry.direction and not DIRECTION_RE.match(entry.direction):
        raise RequestError(f"invalid direction {entry.direction!r} "
                           "(expected [a-z0-9][a-z0-9_-]*)")
    for stype, ptr in entry.sources:
        if stype not in SOURCE_TYPES:
            raise RequestError(f"unknown source type '{stype}' (allowed: "
                               f"{', '.join(SOURCE_TYPES)})")
        _check_pointer(stype, ptr, store_dir)
    # Measured in the format-1 spelling, whose direction key is the shorter
    # one: the limit is then the same in every format, so an entry that fitted
    # before an upgrade still fits after it.
    size = len("\n".join(entry.body_lines(1)).encode("utf-8"))
    if size > MAX_CONTEXT_BYTES:
        raise RequestError(f"context entry is {size} bytes (limit {MAX_CONTEXT_BYTES}) "
                           "-- long material stays behind a pointer")


def validate_context_input(text: str, store_dir=None) -> ContextEntry:
    if "\r" in text:
        raise RequestError("context input must not contain carriage returns")
    try:
        entry = _parse_context_body(text.split("\n"))
    except ValueError as e:
        off, msg = e.args[0]
        raise RequestError(f"context input line {off + 1}: {msg}") from None
    _check_context_values(entry, store_dir)
    if entry.direction == RECOVERY_DIRECTION:
        # Input only: an existing file that names it still parses.
        raise RequestError(f"direction '{RECOVERY_DIRECTION}' is reserved: its "
                           "members are derived from the recover: items, a "
                           "context never names it")
    return entry


def validate_situation(text: str) -> list:
    if "\r" in text:
        raise RequestError("situation text must not contain carriage returns")
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    for ln in lines:
        if ln.startswith("#"):
            raise RequestError(f"situation text line {ln!r} starts with '#'")
    if len("\n".join(lines).encode("utf-8")) > MAX_SITUATION_BYTES:
        raise RequestError(f"situation text is longer than {MAX_SITUATION_BYTES} bytes")
    return lines


def validate_qa_body(text: str) -> list:
    if "\r" in text:
        raise RequestError("Q&A text must not contain carriage returns")
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        raise RequestError("no Q&A text on stdin")
    for ln in lines:
        if ln.startswith("## "):
            raise RequestError(f"Q&A line {ln!r} starts with '## ' (it would forge "
                               "an entry boundary)")
    if len("\n".join(lines).encode("utf-8")) > MAX_QA_BYTES:
        raise RequestError(f"Q&A entry is longer than {MAX_QA_BYTES} bytes")
    return lines


def parse_batch(text: str) -> list:
    """`<id>|<rev>|<state>|<checked_at>|<outcome>` per line."""
    out = []
    seen = set()
    for n, raw in enumerate(text.split("\n"), start=1):
        if not raw.strip():
            continue
        parts = raw.split("|")
        if len(parts) != 5:
            raise RequestError(f"batch line {n}: expected <id>|<rev>|<state>|"
                               "<checked_at>|<outcome>")
        num = parse_id(parts[0])
        if num in seen:
            raise RequestError(f"batch line {n}: c{num} appears twice")
        seen.add(num)
        if not re.match(r"^[1-9][0-9]*\Z", parts[1].strip()):
            raise RequestError(f"batch line {n}: invalid rev {parts[1]!r}")
        state = parts[2].strip()
        if state not in STATES:
            raise RequestError(f"batch line {n}: invalid state {state!r}")
        if state == "dismissed":
            raise RequestError(f"batch line {n}: a batch never sets 'dismissed' -- "
                               "dismissal is a user decision (use `dismiss`)")
        ts = normalize_ts(parts[3].strip(), allow_never=False)
        outcome = _single_line("outcome", parts[4], MAX_OUTCOME, False)
        out.append((num, int(parts[1]), state, ts, outcome))
    if not out:
        raise RequestError("no batch lines on stdin")
    return out


# --- directions: membership ---------------------------------------------------

def item_direction(store, item) -> str:
    """The direction `item` belongs to, or "".

    An explicit context direction wins (when it is a valid slug); otherwise a
    crash-recovery item (`recover:` ref) belongs to the reserved
    RECOVERY_DIRECTION. The mapping is read-side only: the crash detector owns
    recovery contexts and nothing writes a direction into them.
    """
    if item is None:
        return ""
    ctx = store.contexts.get(item.num) if store is not None else None
    slug = getattr(ctx, "direction", "") if ctx is not None else ""
    if slug and DIRECTION_RE.match(slug):
        return slug
    return RECOVERY_DIRECTION if parse_recover_ref(item.ref or "") else ""


def membership(store) -> dict:
    """{item num: direction slug} for every item that is in a direction."""
    out = {}
    for num in sorted(store.items):
        slug = item_direction(store, store.items[num])
        if slug:
            out[num] = slug
    return out


def direction_members(store) -> dict:
    """{slug: [item nums, ascending]} -- every state, closed items included."""
    out: dict = {}
    for num, slug in membership(store).items():
        out.setdefault(slug, []).append(num)
    return out


def pending_members(store, slug: str) -> list:
    """The members of `slug` that are not closed (state open or unknown): the
    ones a baseline snapshot lists."""
    return [n for n in direction_members(store).get(slug, [])
            if store.items[n].state in ("open", "unknown")]


def known_directions(store) -> list:
    """Every direction that has a block or at least one member: the ranked
    ones by rank, then the unranked ones by slug."""
    slugs = set(store.directions) | set(direction_members(store))
    ranked = sorted((s for s in slugs if s in store.directions
                     and store.directions[s].rank),
                    key=lambda s: store.directions[s].rank)
    return ranked + sorted(s for s in slugs if s not in ranked)


def unassigned_items(store) -> list:
    """Item nums in state open or unknown that are in no direction."""
    return [n for n in sorted(store.items)
            if store.items[n].state in ("open", "unknown")
            and not item_direction(store, store.items[n])]


def direction_stamp(store, slug: str, members: "list | None" = None) -> str:
    """16 hex over the direction's members and their item revs.

    A direction's rev covers its block only; which items are members, and
    their state and ref, live in the items. An item's rev changes with every
    change to the item or its context, so this stamp moves when a member is
    added, removed, re-pointed or changed in any field. A freshness verdict
    carries the stamp it was computed from and applies only while it holds.
    `members` is the direction's member list when the caller already has it
    (`direction_members(store)[slug]`), so a listing builds the map once.
    """
    if members is None:
        members = direction_members(store).get(slug, [])
    text = "\n".join(f"c{n}@{store.items[n].rev}" for n in members)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# --- directions: baseline snapshots --------------------------------------------

@dataclass
class Baseline:
    """A parsed baseline snapshot (`baselines/<16 hex>.txt`)."""
    slug: str
    members: list = field(default_factory=list)   # [(num, state, ref)]
    tasks: list = field(default_factory=list)     # [(ref, value)]
    trails: list = field(default_factory=list)    # [(handle, value)]
    next: "tuple | None" = None                   # (key, value)


def _task_ref(value: str):
    """The canonical form of a task ref (local or cross-repo), or None."""
    m = LOCAL_REF_RE.match(value)
    if m:
        return "t" + m.group(1)
    m = XREF_RE.match(value)
    return f"{m.group(1)}#{m.group(2)}" if m else None


def parse_baseline(text: str) -> Baseline:
    """Strict parse of a baseline snapshot. Raises RequestError.

    Line 1 is BASELINE_HEADER, line 2 `direction: <slug>`, then one input per
    line, `<kind>: <key>|<value>`: kinds in BASELINE_KINDS order, keys strictly
    ascending within a kind (item ids by number, the rest by bytes), at most
    one `next` line, a final newline and no blank line. A member's value is
    `<state>|<ref>` with state open or unknown -- only pending members are
    listed, so a snapshot does not grow with a direction's history. The other
    values are opaque here (BASELINE_VALUE_RE); the refresh owns them.
    """
    size = len(text.encode("utf-8"))
    if size > MAX_BASELINE_BYTES:
        raise RequestError(f"baseline snapshot is {size} bytes (limit "
                           f"{MAX_BASELINE_BYTES}): the direction has too many "
                           "pending members to summarise as one")
    if "\r" in text:
        raise RequestError("baseline snapshot must not contain carriage returns")
    if not text.endswith("\n"):
        raise RequestError("baseline snapshot is missing its final newline")
    lines = text.split("\n")[:-1]
    if not lines or lines[0] != BASELINE_HEADER:
        raise RequestError(f"baseline line 1 must be {BASELINE_HEADER!r}")
    m = re.match(r"^direction: (.*)\Z", lines[1]) if len(lines) > 1 else None
    if not m or not DIRECTION_RE.match(m.group(1)):
        raise RequestError("baseline line 2 must be 'direction: <slug>'")
    b = Baseline(slug=m.group(1))
    last = None
    for n, line in enumerate(lines[2:], start=3):
        m = re.match(r"^(member|task|trail|next): ([^|]*)\|(.*)\Z", line)
        if not m:
            raise RequestError(f"baseline line {n}: not '<kind>: <key>|<value>' "
                               f"with kind one of {', '.join(BASELINE_KINDS)}")
        kind, key, value = m.groups()
        order = (BASELINE_KINDS.index(kind), 0, key)
        if kind == "member":
            km = re.match(r"^c([1-9][0-9]*)\Z", key)
            state, sep, ref = value.partition("|")
            if not km or not sep or state not in ("open", "unknown"):
                raise RequestError(f"baseline line {n}: a member line is "
                                   "'member: c<N>|<open|unknown>|<ref>'")
            try:
                canonical = normalize_ref(ref)
            except RequestError:
                canonical = None
            if canonical != ref:
                raise RequestError(f"baseline line {n}: ref {ref!r} is not in "
                                   "canonical form")
            order = (0, int(km.group(1)), "")
            b.members.append((int(km.group(1)), state, ref))
        else:
            if kind == "task":
                ok = _task_ref(key) == key
            elif kind == "trail":
                ok = bool(TRAIL_HANDLE_RE.match(key))
            else:
                try:
                    ok = bool(key) and normalize_next(key) == key
                except RequestError:
                    ok = False
            if not ok:
                raise RequestError(f"baseline line {n}: invalid {kind} key {key!r}")
            if not BASELINE_VALUE_RE.match(value):
                raise RequestError(f"baseline line {n}: invalid value {value!r}")
            if kind == "task":
                b.tasks.append((key, value))
            elif kind == "trail":
                b.trails.append((key, value))
            elif b.next is not None:
                raise RequestError(f"baseline line {n}: more than one next line")
            else:
                b.next = (key, value)
        if last is not None and order <= last:
            raise RequestError(f"baseline line {n}: out of order or repeated "
                               "(lines are sorted by kind, then by key)")
        last = order
    return b


def load_baseline(store_dir: str, digest: str, slug: str) -> tuple:
    """(status, Baseline or None) of the snapshot a record's digest names.

    status is `ok` only for a readable regular file whose bytes hash to its
    name, satisfy the snapshot grammar and describe `slug`. Otherwise one of
    missing / not_regular / unreadable / hash_mismatch / bad_grammar /
    wrong_direction: presence alone is never trust.
    """
    if not DIGEST_RE.match(digest or ""):
        return "missing", None
    path = os.path.join(store_dir, "baselines", f"{digest}.txt")
    if not os.path.lexists(path):
        return "missing", None
    if os.path.islink(path) or not os.path.isfile(path):
        return "not_regular", None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return "unreadable", None
    if hashlib.sha256(data).hexdigest()[:16] != digest:
        return "hash_mismatch", None
    try:
        b = parse_baseline(data.decode("utf-8"))
    except (UnicodeDecodeError, RequestError):
        return "bad_grammar", None
    if b.slug != slug:
        return "wrong_direction", None
    return "ok", b


def baseline_status(store_dir: str, digest: str, slug: str) -> str:
    return load_baseline(store_dir, digest, slug)[0]


def baseline_differences(store, slug: str, record: Direction, b: Baseline) -> list:
    """Where a baseline's STORE-SIDE lines differ from the store as it is:
    [(kind, key)]. Members are compared with the direction's pending members
    (id, state, ref), trail keys with the record's trails, the next key with
    the record's next. Task lines are not the store's to check."""
    out = []
    want = {n: (store.items[n].state, store.items[n].ref)
            for n in pending_members(store, slug)}
    have = {n: (state, ref) for n, state, ref in b.members}
    for n in sorted(set(want) | set(have)):
        if want.get(n) != have.get(n):
            out.append(("member", f"c{n}"))
    for h in sorted(set(record.trails) ^ {k for k, _ in b.trails}):
        out.append(("trail", h))
    b_next = b.next[0] if b.next else ""
    if b_next != record.next:
        out.append(("next", record.next or b_next))
    return out


# --- directions: batch inputs -------------------------------------------------

def parse_slug(value: str) -> str:
    value = _no_line_breaks("direction", value).strip()
    if not DIRECTION_RE.match(value):
        raise RequestError(f"invalid direction {value!r} (expected [a-z0-9][a-z0-9_-]*)")
    return value


def _batch_lines(text: str):
    for n, raw in enumerate(text.split("\n"), start=1):
        if raw.strip():
            yield n, [p.strip() for p in raw.split("|")]


def _batch_rev(n: int, value: str) -> int:
    if not re.match(r"^[1-9][0-9]*\Z", value):
        raise RequestError(f"batch line {n}: invalid rev {value!r}")
    return int(value)


def parse_assign_batch(text: str) -> list:
    """`<id>|<rev>|<slug or ->` per line -> [(num, rev, slug or "")]."""
    out, seen = [], set()
    for n, parts in _batch_lines(text):
        if len(parts) != 3:
            raise RequestError(f"batch line {n}: expected <id>|<rev>|<direction or ->")
        num = parse_id(parts[0])
        if num in seen:
            raise RequestError(f"batch line {n}: c{num} appears twice")
        seen.add(num)
        slug = "" if parts[2] == "-" else parse_slug(parts[2])
        if slug == RECOVERY_DIRECTION:
            raise RequestError(f"batch line {n}: direction '{RECOVERY_DIRECTION}' "
                               "is reserved -- its members are derived from the "
                               "recover: items")
        out.append((num, _batch_rev(n, parts[1]), slug))
    if not out:
        raise RequestError("no batch lines on stdin")
    return out


def parse_rank_batch(text: str) -> list:
    """`<slug>|<rev or absent>` per line, in rank order -> [(slug, rev|None)].
    An empty list is valid input here (the caller requires --clear for it)."""
    out, seen = [], set()
    for n, parts in _batch_lines(text):
        if len(parts) != 2:
            raise RequestError(f"batch line {n}: expected <direction>|<rev or absent>")
        slug = parse_slug(parts[0])
        if slug in seen:
            raise RequestError(f"batch line {n}: direction {slug} appears twice")
        seen.add(slug)
        out.append((slug, None if parts[1] == "absent" else _batch_rev(n, parts[1])))
    return out


def parse_order(value: str) -> list:
    """`--expect-ranked`: `-` (nothing ranked) or slugs in rank order."""
    value = _no_line_breaks("--expect-ranked", value).strip()
    if value == "-":
        return []
    out = [parse_slug(tok) for tok in value.split(",")]
    if len(set(out)) != len(out):
        raise RequestError("--expect-ranked names a direction twice")
    return out


def parse_drift(value: str) -> list:
    """A comma-separated list of drift reasons (batch input) -> validated list."""
    reasons = [parse_reason(tok.strip()) for tok in value.split(",") if tok.strip()]
    _check_drift(reasons)
    return reasons


def parse_freshness_batch(text: str) -> list:
    """`<slug>|<rev>|<stamp>|<freshness>|<checked_at>|<drift>` per line."""
    out, seen = [], set()
    for n, parts in _batch_lines(text):
        if len(parts) != 6:
            raise RequestError(f"batch line {n}: expected <direction>|<rev>|<stamp>|"
                               "<freshness>|<checked_at>|<drift>")
        slug = parse_slug(parts[0])
        if slug in seen:
            raise RequestError(f"batch line {n}: direction {slug} appears twice")
        seen.add(slug)
        rev = _batch_rev(n, parts[1])
        if not DIGEST_RE.match(parts[2]):
            raise RequestError(f"batch line {n}: invalid stamp {parts[2]!r} "
                               "(expected 16 hex characters)")
        if parts[3] not in FRESHNESS:
            raise RequestError(f"batch line {n}: invalid freshness {parts[3]!r}")
        ts = normalize_ts(parts[4], allow_never=False)
        try:
            drift = parse_drift(parts[5])
        except RequestError as e:
            raise RequestError(f"batch line {n}: {e}") from None
        if parts[3] == "current" and drift:
            raise RequestError(f"batch line {n}: 'current' takes no drift reason")
        if parts[3] == "stale" and not drift:
            raise RequestError(f"batch line {n}: 'stale' needs at least one "
                               "drift reason")
        out.append((slug, rev, parts[2], parts[3], ts, drift))
    if not out:
        raise RequestError("no batch lines on stdin")
    return out


# --- store helpers -----------------------------------------------------------

def now_ts() -> str:
    seam = os.environ.get("AITASK_SITREP_NOW", "")
    if seam:
        if not TS_RE.match(seam):
            raise RequestError(f"AITASK_SITREP_NOW={seam!r} is not YYYY-MM-DDTHH:MM:SSZ")
        return seam
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: str):
    """Strict UTF-8 text of `path`, or None when it does not exist."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        raise FormatError(path, 1, "not valid UTF-8") from None
    except OSError as e:
        raise FormatError(path, 0, f"cannot read: {e.strerror or e}") from None


def _read_tolerant(path: str):
    """Text of `path` with undecodable bytes replaced, or None when it does not
    exist. Tolerance is about CONTENT only: any other I/O failure is a
    FormatError, because an unreadable source-of-truth file must never read as
    empty data (and an id scan that skips it could re-issue an id)."""
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return None
    except OSError as e:
        raise FormatError(path, 0, f"cannot read: {e.strerror or e}") from None


def load_todo(store_dir: str) -> TodoStore:
    path = os.path.join(store_dir, "todo.md")
    text = _read(path)
    if text is None:
        raise FormatError(path, 0, "todo.md is missing")
    store = parse_todo(text, path)
    store.loaded_members = membership(store)
    return store


def load_qa(store_dir: str) -> QaLog:
    path = os.path.join(store_dir, "qa.md")
    text = _read(path)
    if text is None:
        raise FormatError(path, 0, "qa.md is missing")
    return parse_qa(text, path)


def _id_files(store_dir: str) -> list:
    files = [os.path.join(store_dir, n)
             for n in ("todo.md", "todo.md.bak", "qa.md", "qa.md.bak")]
    rec = os.path.join(store_dir, "recovered")
    if os.path.isdir(rec):
        try:
            names = sorted(os.listdir(rec))
        except OSError as e:
            raise FormatError(rec, 0, f"cannot list: {e.strerror or e}") from None
        files.extend(os.path.join(rec, n) for n in names)
    return files


def max_id_token(text: str) -> int:
    """Highest item id found at a structural position in `text` (any text)."""
    best = 0
    for line in text.split("\n"):
        for rx in _ID_POSITIONS:
            m = rx.match(line)
            if m:
                best = max(best, int(m.group(1)))
        m = _QA_ITEMS_RE.match(line) or _RELATED_RE.match(line)
        if m:
            for cm in _CID_RE.finditer(m.group(1)):
                best = max(best, int(cm.group(1)))
    return best


def max_rev_token(text: str) -> int:
    """Highest rev found on an item line or a direction heading in `text`
    (any text): both draw from the one store-wide counter."""
    best = 0
    for line in text.split("\n"):
        m = _REV_RE.match(line) or _DIRECTION_REV_RE.match(line)
        if m:
            best = max(best, int(m.group(1)))
    return best


def _high_water(store_dir: str, counter_name: str, scan) -> int:
    """max(counter file, 1 + highest value `scan` finds in any store file)."""
    counter = 0
    raw = (_read_tolerant(os.path.join(store_dir, counter_name)) or "").strip()
    if re.match(r"^[1-9][0-9]*\Z", raw):
        counter = int(raw)
    seen = 0
    for path in _id_files(store_dir):
        if os.path.isfile(path):
            seen = max(seen, scan(_read_tolerant(path) or ""))
    return max(counter, seen + 1, 1)


def alloc_id(store_dir: str) -> int:
    """Next id: max(next_id file, 1 + highest id seen in any store file).

    The scan covers the backups, qa.md and recovered/ and works on unparseable
    text, so restoring an older generation, losing the counter, or a Q&A entry
    naming an item the backup lacks can never re-issue an id.
    """
    return _high_water(store_dir, "next_id", max_id_token)


def alloc_rev(store_dir: str) -> int:
    """Next revision stamp, by the same rule as alloc_id over `next_rev`.

    Revs are STORE-WIDE and never reused, not per-item counters: a restore puts
    an older generation (older revs) back, and a per-item counter would climb
    back to a rev someone had already observed -- an outstanding refresh
    computed for the pre-restore item would then pass its rev check against a
    different state. With fresh store-wide stamps an (id, rev) pair names
    exactly one state of one item, forever.
    """
    return _high_water(store_dir, "next_rev", max_rev_token)


class Revs:
    """Hands out fresh revision stamps for one mutation."""

    def __init__(self, store_dir: str):
        self.next = alloc_rev(store_dir)
        self.used = False

    def take(self) -> int:
        r = self.next
        self.next += 1
        self.used = True
        return r


def _is_template(path: str, kind: str) -> bool:
    text = _read_tolerant(path)
    if kind == "todo":
        # An empty generation written by an older writer is still a template.
        return text in {render_todo(TodoStore(format=v)) for v in TODO_READ_FORMATS}
    return text == empty_text(kind)


def store_state(store_dir: str) -> str:
    """One line: ESTABLISHED=<0|1> MARKER=<0|1> TODO=<ok|missing> QA=<ok|missing>.

    Data is only ever written after `store.init` exists, so a store without the
    marker holds no data UNLESS a post-init artifact (next_id, sources/, raw/,
    cases/, baselines/, recovered/) or a non-template data file says otherwise -- then the marker
    was lost, not never written, and a missing data file is DAMAGE, never
    something to re-initialize over.
    """
    j = lambda n: os.path.join(store_dir, n)  # noqa: E731
    marker = os.path.isfile(j("store.init"))
    established = (marker or os.path.exists(j("next_id"))
                   or os.path.exists(j("next_rev")))
    for d in ("sources", "raw", "cases", "baselines", "recovered"):
        if not established and os.path.isdir(j(d)) and os.listdir(j(d)):
            established = True
    # Content is inspected only when no decisive artifact settled it -- i.e.
    # only while telling an interrupted init apart from a lost marker.
    if not established:
        for name, kind in (("todo.md", "todo"), ("todo.md.bak", "todo"),
                           ("qa.md", "qa"), ("qa.md.bak", "qa")):
            if os.path.exists(j(name)) and not _is_template(j(name), kind):
                established = True
                break
    todo = "ok" if os.path.exists(j("todo.md")) else "missing"
    qa = "ok" if os.path.exists(j("qa.md")) else "missing"
    return (f"ESTABLISHED={int(established)} MARKER={int(marker)} "
            f"TODO={todo} QA={qa}")


def _write_out(out: str, text: str) -> None:
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _emit(lines) -> None:
    for ln in lines:
        print(ln)


def _find(store: TodoStore, num: int) -> Item:
    if num not in store.items:
        print(f"NOT_FOUND:c{num}")
        raise RequestError(f"no item c{num}")
    return store.items[num]


def _ref_owner(store: TodoStore, ref: str):
    for n in sorted(store.items):
        if ref and store.items[n].ref == ref:
            return n
    return None


def _apply(item: Item, revs: Revs, **changes) -> bool:
    changed = False
    for k, v in changes.items():
        if v is not None and getattr(item, k) != v:
            setattr(item, k, v)
            changed = True
    if changed:
        item.rev = revs.take()
    return changed


def _commit_text(args, text: str, parse) -> None:
    """Hand the would-be file to the wrapper -- after parsing it back. A value
    that slipped past validation but would not survive the strict parser is
    refused here (exit 2), never written as a store the next read rejects."""
    try:
        parse(text, "rendered output")
    except FormatError as e:
        raise RequestError(f"refused: the result would not be a valid store ({e})") from None
    _write_out(args.out, text)


def _prune_empty_directions(store: TodoStore) -> None:
    for slug in [s for s, d in store.directions.items() if d.is_empty()]:
        del store.directions[slug]


def _reset_changed_memberships(store: TodoStore, revs: Revs) -> None:
    """A membership write resets freshness: every block that gained or lost a
    member since the file was loaded goes back to `unknown`, with a fresh rev
    when that changed it. `store.reset_directions` then lists `(slug, changed)`
    for each touched slug that has a block, so a verb can report their revs."""
    store.reset_directions = []
    before = store.loaded_members
    if before is None:
        return
    after = membership(store)
    touched = set()
    for num in set(before) | set(after):
        if before.get(num) != after.get(num):
            touched.update(s for s in (before.get(num), after.get(num)) if s)
    for slug in sorted(touched):
        d = store.directions.get(slug)
        if d is None:
            continue
        moved = d.reset_freshness()
        if moved:
            d.rev = revs.take()
        store.reset_directions.append((slug, moved))


def _migrated_previous_generation(args, store: TodoStore, revs: Revs) -> str:
    """The generation on disk, re-rendered in the current format.

    A writer older than the new format treats a file it cannot parse as
    damaged, and its `restore` installs any backup it CAN parse. So the write
    that upgrades a store never leaves the old-format file behind as the
    backup: the wrapper installs this text as `todo.md.bak` instead (and keeps
    the original bytes under recovered/). It is the same items, contexts and
    situation text; every block gets a fresh rev, and a block the current write
    did not change (its rev is still 0 in `store`) takes the same one, so one
    (slug, rev) names one state in both files.
    """
    base = load_todo(args.store)
    _prune_empty_directions(base)
    for slug in sorted(base.directions):
        base.directions[slug].rev = revs.take()
    for slug, d in store.directions.items():
        if not d.rev and slug in base.directions:
            d.rev = base.directions[slug].rev
    base.format = TODO_FORMAT_VERSION
    text = render_todo(base)
    try:
        parse_todo(text, "migrated backup")
    except FormatError as e:
        raise RequestError(f"refused: the store cannot be upgraded to format "
                           f"{TODO_FORMAT_VERSION} ({e})") from None
    return text


def _commit_todo(args, store: TodoStore, revs=None) -> None:
    # Every write that changes todo.md writes the CURRENT format: an older
    # store is upgraded by its first changing write. Ops call this only when
    # something changed, so a no-op leaves an old file byte-identical.
    if revs is None:
        revs = Revs(args.store)
    _reset_changed_memberships(store, revs)
    _prune_empty_directions(store)
    old_format = store.format
    bak_text = None
    if old_format < TODO_FORMAT_VERSION:
        bak_text = _migrated_previous_generation(args, store, revs)
    for d in store.directions.values():
        if not d.rev:
            d.rev = revs.take()
    store.format = TODO_FORMAT_VERSION
    _commit_text(args, render_todo(store), parse_todo)
    if bak_text is not None and getattr(args, "out_bak", ""):
        _write_out(args.out_bak, bak_text)
        print(f"@BAK_MIGRATED:{old_format}")
    if revs.used:
        print(f"@NEXT_REV:{revs.next}")


# --- ops ---------------------------------------------------------------------

def _read_input(args) -> str:
    if not getattr(args, "input", None):
        return ""
    data = sys.stdin.buffer.read() if args.input == "-" else open(args.input, "rb").read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise RequestError("input is not valid UTF-8") from None


def op_add(args, text):
    title = _single_line("title", args.title, MAX_TITLE, True)
    if not title:
        raise RequestError("title must not be empty")
    ref = normalize_ref(args.ref or "")
    if parse_recover_ref(ref):
        raise RequestError("recover: items are written by recovery-apply, not add")
    checked = normalize_ts(args.checked_at, allow_never=True)
    proto = Item(1, 1, args.kind, args.state, args.group, checked, ref,
                 args.derived, "", title)
    _check_item_values(proto)
    if args.state not in ("open", "unknown"):
        raise RequestError("add takes --state open or unknown")
    entry = validate_context_input(text, None) if args.input else None
    if args.check_only:
        return
    store = load_todo(args.store)
    owner = _ref_owner(store, ref)
    if owner is not None:
        print(f"EXISTS:c{owner}")
        return
    num = alloc_id(args.store)
    if entry is not None:
        _check_context_values(entry, args.store)
        _check_related(entry, num, num)
    revs = Revs(args.store)
    proto.num = num
    proto.rev = revs.take()
    store.items[num] = proto
    if entry is not None:
        store.contexts[num] = entry
    _commit_todo(args, store, revs)
    print(f"ADDED:c{num}")
    print(f"@NEXT_ID:{num + 1}")


def _check_related(entry: ContextEntry, limit: int, own: int) -> None:
    """`related` may only name items that exist or existed (below the
    allocation high-water mark) -- a forward reference would otherwise inflate
    alloc_id's scan and skip ids."""
    for n in entry.related:
        if n == own:
            raise RequestError(f"context of c{own} lists itself as related")
        if n >= limit:
            raise RequestError(f"related c{n} never existed")


def _expect(item: Item, expect_rev) -> bool:
    if expect_rev is not None and item.rev != expect_rev:
        print(f"STALE:c{item.num}|{item.rev}")
        return False
    return True


def op_update(args, _text):
    num = parse_id(args.id)
    title = None
    if args.title is not None:
        title = _single_line("title", args.title, MAX_TITLE, True)
        if not title:
            raise RequestError("title must not be empty")
    ref = normalize_ref(args.ref) if args.ref is not None else None
    if ref and parse_recover_ref(ref):
        raise RequestError("recover: items are written by recovery-apply, not update")
    if args.kind is not None and args.kind not in KINDS:
        raise RequestError(f"invalid kind {args.kind!r}")
    if args.group is not None and args.group not in GROUPS:
        raise RequestError(f"invalid group {args.group!r}")
    if args.check_only:
        return
    store = load_todo(args.store)
    item = _find(store, num)
    if not _expect(item, args.expect_rev):
        return
    if parse_recover_ref(item.ref):
        if ref is not None and ref != item.ref:
            raise RequestError(f"c{num} is a recovery item: its ref {item.ref} is fixed")
        if args.kind is not None and args.kind != "task":
            raise RequestError(f"c{num} is a recovery item: its kind stays task")
    if ref:
        owner = _ref_owner(store, ref)
        if owner is not None and owner != num:
            raise RequestError(f"ref {ref} is already used by c{owner}")
    revs = Revs(args.store)
    if _apply(item, revs, title=title, ref=ref, kind=args.kind, group=args.group):
        _commit_todo(args, store, revs)
    print(f"UPDATED:c{num}|{item.rev}")


def op_set_state(args, _text):
    num = parse_id(args.id)
    if args.state not in STATES:
        raise RequestError(f"invalid state {args.state!r}")
    ts = normalize_ts(args.checked_at, allow_never=False)
    outcome = (_single_line("outcome", args.outcome, MAX_OUTCOME, False)
               if args.outcome is not None else None)
    if args.check_only:
        return
    store = load_todo(args.store)
    item = _find(store, num)
    if not _expect(item, args.expect_rev):
        return
    revs = Revs(args.store)
    if _apply(item, revs, state=args.state, checked_at=ts, outcome=outcome):
        _commit_todo(args, store, revs)
    print(f"STATE:c{num}|{item.state}|{item.rev}")


def op_set_state_batch(args, text):
    lines = parse_batch(text)
    if args.check_only:
        return
    store = load_todo(args.store)
    revs = Revs(args.store)
    changed = False
    results = []
    for num, rev, state, ts, outcome in lines:
        item = store.items.get(num)
        if item is None:
            results.append(f"NOT_FOUND:c{num}")
        elif item.rev != rev:
            results.append(f"STALE:c{num}|{item.rev}")
        elif item.state == "dismissed":
            results.append(f"KEPT:c{num}|dismissed")
        else:
            changed |= _apply(item, revs, state=state, checked_at=ts, outcome=outcome)
            results.append(f"STATE:c{num}|{item.state}|{item.rev}")
    if changed:
        _commit_todo(args, store, revs)
    _emit(results)


def op_situation(args, text):
    """Set or clear a direction's situation text. Clearing removes the TEXT
    only: the record stays, and the block goes when nothing agent-written is
    left in it (_commit_todo prunes it). Members keep naming the direction."""
    slug = parse_slug(args.direction)
    lines = validate_situation(text)
    if args.check_only:
        return
    store = load_todo(args.store)
    d = store.directions.get(slug)
    if not lines:
        if d is None or not d.situation:
            print(f"SITUATION:{slug}|absent")
            return
        revs = Revs(args.store)
        d.situation = []
        d.rev = revs.take()
        _commit_todo(args, store, revs)
        print(f"SITUATION:{slug}|removed")
        return
    if d is None or d.situation != lines:
        revs = Revs(args.store)
        if d is None:
            d = store.directions[slug] = Direction()
        d.situation = lines
        d.rev = revs.take()
        _commit_todo(args, store, revs)
    print(f"SITUATION:{slug}|set")


def _expect_direction(slug: str, d, expect) -> bool:
    """The rev guard of a direction write. `expect` None is `absent`: no
    stamped record -- no block, or a block read from an older format, which
    has no rev yet."""
    cur = d.rev if d is not None else 0
    if expect is None:
        if cur:
            print(f"STALE:{slug}|{cur}")
            return False
        return True
    if d is None:
        print(f"ABSENT:{slug}")
        return False
    if cur != expect:
        print(f"STALE:{slug}|{cur or '-'}")
        return False
    return True


def _copy_direction(d: Direction) -> Direction:
    return Direction(d.rev, d.title, d.rank, list(d.trails), d.next, d.summary,
                     d.digest, d.freshness, d.checked_at, list(d.drift),
                     list(d.situation))


def op_direction_set(args, text):
    """Create or update a direction's agent-written fields (t2335_1).

    A summary travels with `--digest`, the name of the retained baseline it
    was written from. That baseline must verify (load_baseline) and its
    store-side lines must match the store AS IT IS NOW, under the lock: a
    member that changed while the proposal waited for confirmation answers
    EVIDENCE_CHANGED and writes nothing. A change to summary, digest, trails
    or next resets the freshness -- this verb can never write `current`.
    """
    slug = parse_slug(args.direction)
    expect = _parse_expect_rev(args.expect_rev)
    title = (None if args.title is None
             else _single_line("title", args.title, MAX_DIRECTION_TITLE, True))
    trails = None
    if args.trails is not None:
        trails = [t.strip() for t in _no_line_breaks("--trails", args.trails).split(",")
                  if t.strip()]
    nxt = None if args.next is None else normalize_next(args.next)
    summary = digest = None
    if args.input:
        if "\r" in text:
            raise RequestError("summary must not contain carriage returns")
        body = text[:-1] if text.endswith("\n") else text
        if "\n" in body:
            raise RequestError("summary must be one line (one paragraph)")
        summary = _single_line("summary", body, MAX_DIRECTION_SUMMARY, True)
        if summary:
            if args.digest is None:
                raise RequestError("a summary needs --digest: the baseline it was "
                                   "written from (retain it with retain-baseline)")
            digest = _no_line_breaks("--digest", args.digest).strip()
            if not DIGEST_RE.match(digest):
                raise RequestError(f"invalid --digest {digest!r} (expected 16 hex "
                                   "characters)")
        elif args.digest is not None:
            raise RequestError("--digest goes with a non-empty summary")
        else:
            digest = ""
    elif args.digest is not None:
        raise RequestError("--digest goes with --summary-file -")
    if title is None and trails is None and nxt is None and summary is None:
        raise RequestError("nothing to set (give --title, --trails, --next or "
                           "--summary-file -)")
    proto = Direction(title=title or "", trails=trails or [], next=nxt or "")
    _check_direction_values(slug, proto)
    if args.check_only:
        return
    store = load_todo(args.store)
    old = store.directions.get(slug)
    if not _expect_direction(slug, old, expect):
        return
    new = _copy_direction(old) if old is not None else Direction()
    if title is not None:
        new.title = title
    if trails is not None:
        new.trails = trails
    if nxt is not None:
        item_ref = re.match(r"^c([1-9][0-9]*)\Z", nxt)
        if item_ref and int(item_ref.group(1)) not in store.items:
            raise RequestError(f"next {nxt} names no item")
        new.next = nxt
    if summary is not None:
        new.summary, new.digest = summary, digest
    if summary:
        status, baseline = load_baseline(args.store, digest, slug)
        if status != "ok":
            raise RequestError(f"baseline baselines/{digest}.txt is {status}: retain "
                               "the snapshot this summary was written from with "
                               "retain-baseline, for this direction")
        diffs = baseline_differences(store, slug, new, baseline)
        if diffs:
            _emit(f"EVIDENCE_CHANGED:{slug}|{kind}|{key}" for kind, key in diffs)
            return
    if new.is_empty():
        raise RequestError(f"direction {slug} would hold nothing (no title, rank, "
                           "trails, next, summary or situation text)"
                           + ("; remove it with direction-remove" if old else ""))
    before = old if old is not None else Direction()
    if ((new.summary, new.digest, new.trails, new.next)
            != (before.summary, before.digest, before.trails, before.next)):
        new.reset_freshness()
    _check_direction_values(slug, new)
    if old is not None and old.header_lines() == new.header_lines():
        print(f"DIRECTION:{slug}|unchanged|{old.rev or '-'}")
        return
    revs = Revs(args.store)
    new.rev = revs.take()
    store.directions[slug] = new
    _commit_todo(args, store, revs)
    print(f"DIRECTION:{slug}|{'updated' if old is not None else 'created'}|{new.rev}")


def op_direction_assign_batch(args, text):
    """Put items into / take them out of directions, all or nothing.

    Only the context's direction key changes. An ordinary item with no context
    entry gets the minimal one that can carry the key (a fixed background and
    today's date as origin) under the same rev check. A `recover:` item is
    never reassigned: its context is the crash detector's and it belongs to
    RECOVERY_DIRECTION.
    """
    lines = parse_assign_batch(text)
    if args.check_only:
        return
    store = load_todo(args.store)
    refusals = []
    for num, rev, _slug in lines:
        item = store.items.get(num)
        if item is None:
            refusals.append(f"NOT_FOUND:c{num}")
        elif item.rev != rev:
            refusals.append(f"STALE:c{num}|{item.rev}")
        elif parse_recover_ref(item.ref):
            refusals.append(f"KEPT:c{num}|recovery")
    if refusals:
        _emit(refusals)
        return
    revs = Revs(args.store)
    today = now_ts()[:10]
    changed = False
    for num, _rev, slug in lines:
        ctx = store.contexts.get(num)
        if (ctx.direction if ctx is not None else "") == slug:
            continue
        if ctx is None:
            ctx = store.contexts[num] = ContextEntry(
                background=MINIMAL_CONTEXT_BACKGROUND, origin=[("date", today)])
        ctx.direction = slug
        _check_context_values(ctx, None)
        store.items[num].rev = revs.take()
        changed = True
    if changed:
        _commit_todo(args, store, revs)
    _emit(f"ASSIGNED:c{num}|{slug or '-'}|{store.items[num].rev}"
          for num, _rev, slug in lines)
    if changed:
        _emit(f"DIRECTION:{slug}|{'updated' if moved else 'unchanged'}|"
              f"{store.directions[slug].rev}"
              for slug, moved in store.reset_directions)


def op_direction_rank(args, text):
    """Replace the whole rank order atomically from one ordered list.

    `--expect-ranked` is the full ranked order the caller saw. Without it, a
    rank another session added meanwhile would be cleared just by not being
    named: adding B at rank 2 changes neither A's rank nor A's rev.
    """
    order = parse_rank_batch(text)
    expected = parse_order(args.expect_ranked)
    if not order and not args.clear:
        raise RequestError("no order on stdin (pass --clear to remove every rank)")
    if order and args.clear:
        raise RequestError("--clear takes no order on stdin")
    if args.check_only:
        return
    store = load_todo(args.store)
    known = known_directions(store)
    for slug, _rev in order:
        if slug not in known:
            raise RequestError(f"unknown direction {slug!r}: it has no record "
                               "and no member")
    current = [s for s in known if s in store.directions and store.directions[s].rank]
    if current != expected:
        print(f"STALE_ORDER:{','.join(current) or '-'}")
        return
    refusals = []
    for slug, rev in order:
        d = store.directions.get(slug)
        cur = d.rev if d is not None else 0
        if rev is None:
            if cur:
                refusals.append(f"STALE:{slug}|{cur}")
        elif d is None:
            refusals.append(f"ABSENT:{slug}")
        elif cur != rev:
            refusals.append(f"STALE:{slug}|{cur or '-'}")
    if refusals:
        _emit(refusals)
        return
    revs = Revs(args.store)
    named = [slug for slug, _rev in order]
    changed = False
    for rank, slug in enumerate(named, start=1):
        d = store.directions.get(slug)
        if d is None:
            d = store.directions[slug] = Direction()
        if d.rank != rank:
            d.rank = rank
            d.rev = revs.take()
            changed = True
    unranked = []
    for slug in sorted(store.directions):
        d = store.directions[slug]
        if d.rank and slug not in named:
            d.rank = 0
            d.rev = revs.take()
            unranked.append(slug)
            changed = True
    if changed:
        _commit_todo(args, store, revs)
    _emit(f"RANKED:{slug}|{store.directions[slug].rank}|{store.directions[slug].rev}"
          for slug in named)
    # A block that held nothing but its rank no longer exists.
    _emit(f"UNRANKED:{slug}|{store.directions[slug].rev if slug in store.directions else '-'}"
          for slug in unranked)


def op_direction_freshness_batch(args, text):
    """The refresh-only write: freshness, checked_at and drift, nothing else.

    A line applies only while the direction still has the rev AND the
    membership stamp its verdict was computed from (the rev does not cover
    which items are members or their state). `current` and `stale` on a record
    with a baseline need that baseline to verify; `current` needs one at all.
    """
    lines = parse_freshness_batch(text)
    if args.check_only:
        return
    store = load_todo(args.store)
    members = direction_members(store)      # no line of this verb changes it
    revs = Revs(args.store)
    changed = False
    results = []
    for slug, rev, stamp, fresh, ts, drift in lines:
        d = store.directions.get(slug)
        if d is None:
            results.append(f"NOT_FOUND:{slug}")
            continue
        now_stamp = direction_stamp(store, slug, members.get(slug, []))
        if d.rev != rev or now_stamp != stamp:
            results.append(f"STALE:{slug}|{d.rev or '-'}|{now_stamp}")
            continue
        if fresh != "unknown":
            if not d.digest:
                if fresh == "current":
                    results.append(f"KEPT:{slug}|no_baseline")
                    continue
            else:
                status = baseline_status(args.store, d.digest, slug)
                if status != "ok":
                    results.append(f"KEPT:{slug}|baseline_{status}")
                    continue
        if (d.freshness, d.checked_at, d.drift) != (fresh, ts, drift):
            d.freshness, d.checked_at, d.drift = fresh, ts, drift
            d.rev = revs.take()
            changed = True
        results.append(f"FRESHNESS:{slug}|{d.freshness}|{d.rev}")
    if changed:
        _commit_todo(args, store, revs)
    _emit(results)


def op_direction_remove(args, _text):
    """Delete a direction's block (record and situation text) and close the
    gap in the ranks. Membership is not touched: items that still name the
    slug keep it, and the direction stays listed from them with no record."""
    slug = parse_slug(args.direction)
    expect = _parse_expect_rev(args.expect_rev)
    if args.check_only:
        return
    store = load_todo(args.store)
    d = store.directions.get(slug)
    if d is None:
        print(f"ABSENT:{slug}")
        return
    if not _expect_direction(slug, d, expect):
        return
    revs = Revs(args.store)
    del store.directions[slug]
    shifted = []
    if d.rank:
        for other in sorted(store.directions, key=lambda s: store.directions[s].rank):
            o = store.directions[other]
            if o.rank > d.rank:
                o.rank -= 1
                o.rev = revs.take()
                shifted.append(other)
    _commit_todo(args, store, revs)
    print(f"DIRECTION_REMOVED:{slug}|{len(direction_members(store).get(slug, []))}")
    _emit(f"RANKED:{s}|{store.directions[s].rank}|{store.directions[s].rev}"
          for s in shifted)


def op_upsert_context(args, text):
    num = parse_id(args.id)
    entry = validate_context_input(text, None)
    if args.check_only:
        return
    store = load_todo(args.store)
    item = _find(store, num)
    if not _expect(item, args.expect_rev):
        return
    _check_context_values(entry, args.store)
    _check_related(entry, alloc_id(args.store), num)
    old = store.contexts.get(num)
    if parse_recover_ref(item.ref):
        # The incarnation scopes a dismissal; only recovery-apply may move it.
        recorded = context_incarnation(old)
        if context_incarnation(entry) != recorded:
            raise RequestError(f"c{num} is a recovery item: the context must keep "
                               f"incarnation={recorded or '(none)'}; a new episode "
                               "goes through recovery-apply")
    if old is not None and old.body_lines() == entry.body_lines():
        print(f"CONTEXT:c{num}|unchanged")
        return
    store.contexts[num] = entry
    # A changed context entry gives its ITEM a fresh rev (t2175_3): a refresh
    # verdict computed from the old entry (e.g. its trail: source) must not
    # pass the batch's rev check against the new one.
    revs = Revs(args.store)
    store.items[num].rev = revs.take()
    _commit_todo(args, store, revs)
    print(f"CONTEXT:c{num}|{'replaced' if old is not None else 'created'}")


def _parse_expect_rev(value: str):
    """`absent` -> None; a positive int -> int. Anything else is exit 2."""
    value = _no_line_breaks("--expect-rev", value).strip()
    if value == "absent":
        return None
    if not re.match(r"^[1-9][0-9]*\Z", value):
        raise RequestError(f"--expect-rev {value!r} is not 'absent' or a positive integer")
    return int(value)


def op_recovery_apply(args, text):
    """One atomic, rev-guarded write of a crash-recovery item (t2299_1).

    `--incarnation` names the episode the RECORDED evidence belongs to. With a
    context it is the context's own origin incarnation (create, evidence
    refresh, reopen) -- the only way a recorded incarnation changes. Without a
    context (a state-only verdict) it must be the item's recorded incarnation:
    passing a newly observed key there would claim a new episode while keeping
    the old evidence, and a later dismissal would be scoped to the wrong one.
    """
    ref = normalize_ref(args.ref)
    if not parse_recover_ref(ref):
        raise RequestError(f"recovery-apply takes a recover:t<N>[_<M>] ref (got {args.ref!r})")
    expect = _parse_expect_rev(args.expect_rev)
    inc = _no_line_breaks("--incarnation", args.incarnation)
    if not INCARNATION_RE.match(inc):
        raise RequestError(f"--incarnation {inc!r} is not 12 lowercase hex characters")
    if args.state not in ("open", "unknown", "done"):
        raise RequestError("recovery-apply takes --state open, unknown or done")
    outcome = _single_line("outcome", args.outcome, MAX_OUTCOME, False)
    ts = normalize_ts(args.checked_at, allow_never=False)
    title = None
    if args.title is not None:
        title = _single_line("title", args.title, MAX_TITLE, True)
        if not title:
            raise RequestError("title must not be empty")
    if args.group is not None and args.group not in GROUPS:
        raise RequestError(f"invalid group {args.group!r}")
    entry = validate_context_input(text, None) if args.input else None
    if entry is not None and context_incarnation(entry) != inc:
        raise RequestError(f"the context's origin incarnation "
                           f"({context_incarnation(entry) or 'missing'}) must equal "
                           f"--incarnation {inc}")
    if expect is None and (entry is None or title is None):
        raise RequestError("creating a recovery item (--expect-rev absent) needs "
                           "--title and a context (--context-file -)")
    if args.check_only:
        return
    store = load_todo(args.store)
    owner = _ref_owner(store, ref)
    if expect is None:
        if owner is not None:
            print(f"STALE:c{owner}|{store.items[owner].rev}")
            return
        num = alloc_id(args.store)
        _check_context_values(entry, args.store)
        _check_related(entry, num, num)
        revs = Revs(args.store)
        item = Item(num, revs.take(), "task", args.state, args.group or "next",
                    ts, ref, "script", outcome, title)
        _check_item_values(item)
        store.items[num] = item
        store.contexts[num] = entry
        _commit_todo(args, store, revs)
        print(f"ADDED:c{num}|{item.rev}")
        print(f"@NEXT_ID:{num + 1}")
        return
    if owner is None:
        print(f"ABSENT:{ref}")
        return
    item = store.items[owner]
    if item.rev != expect:
        print(f"STALE:c{owner}|{item.rev}")
        return
    recorded = context_incarnation(store.contexts.get(owner))
    reopen = False
    if item.state == "dismissed":
        # Dismissal is scoped to the recorded episode: only a different one,
        # crashed again (--state open) and carrying its evidence, reopens it.
        if entry is None:
            print(f"KEPT:c{owner}|dismissed")
            return
        if recorded is None:
            print(f"KEPT:c{owner}|dismissed_no_incarnation")
            return
        if recorded == inc or args.state != "open":
            print(f"KEPT:c{owner}|dismissed")
            return
        reopen = True
    else:
        if entry is None and inc != recorded:
            raise RequestError(f"--incarnation {inc} differs from c{owner}'s recorded "
                               f"incarnation ({recorded or 'none'}) and no context was "
                               "given: a state-only apply passes the recorded "
                               "incarnation; a new episode needs its context")
        reopen = item.state == "done" and args.state == "open"
    if entry is not None:
        _check_context_values(entry, args.store)
        _check_related(entry, alloc_id(args.store), owner)
    revs = Revs(args.store)
    changed = _apply(item, revs, state=args.state, outcome=outcome, checked_at=ts,
                     title=title, group=args.group)
    old = store.contexts.get(owner)
    if entry is not None and (old is None or old.body_lines() != entry.body_lines()):
        store.contexts[owner] = entry
        if not changed:
            item.rev = revs.take()
        changed = True
    if not changed:
        print(f"UNCHANGED:c{owner}|{item.rev}")
        return
    _check_item_values(item)
    _commit_todo(args, store, revs)
    print(f"{'REOPENED' if reopen else 'APPLIED'}:c{owner}|{item.rev}")


def op_qa(args, text):
    body = validate_qa_body(text)
    items = _parse_id_list(args.items or "", allow_dash=True)
    if args.check_only:
        return
    log = load_qa(args.store)
    limit = alloc_id(args.store)
    for n in items:
        if n >= limit:
            raise RequestError(f"Q&A names c{n}, which never existed")
    ts = now_ts()
    log.entries.append(QaEntry(ts, items, body))
    _commit_text(args, render_qa(log), parse_qa)
    print(f"QA:{ts}")


def op_retain(args, _text):
    data = sys.stdin.buffer.read()
    if not data:
        raise RequestError("no passage on stdin")
    if len(data) > MAX_RETAIN_BYTES:
        raise RequestError(f"passage is larger than {MAX_RETAIN_BYTES} bytes")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise RequestError("passage is not valid UTF-8") from None
    if b"\0" in data:
        raise RequestError("passage contains NUL bytes")
    if args.check_only:
        return
    hexname = hashlib.sha256(data).hexdigest()[:16]
    rel = f"sources/{hexname}.txt"
    path = os.path.join(args.store, rel)
    nlines = data.count(b"\n") + (0 if data.endswith(b"\n") else 1)
    if os.path.lexists(path):
        if os.path.islink(path) or not os.path.isfile(path):
            raise FormatError(path, 0, "retained source path is not a regular file")
        with open(path, "rb") as fh:
            if fh.read() != data:
                raise FormatError(path, 0, "hash collision: a different passage is "
                                  "retained under this name")
    else:
        # The wrapper writes the passage (atomically, under its lock).
        print(f"@TARGET:{rel}")
    print(f"RETAINED:{rel}#L1-L{nlines}")


def _raw_max() -> int:
    """MAX_RAW_BYTES, or a SMALLER test-only override (AITASK_SITREP_RAW_MAX)."""
    v = os.environ.get("AITASK_SITREP_RAW_MAX", "")
    if v.isdigit() and 0 < int(v) < MAX_RAW_BYTES:
        return int(v)
    return MAX_RAW_BYTES


def op_retain_raw(args, _text):
    """Retain one raw input VERBATIM under raw/<16 hex>.txt (t2175_6).

    Unlike `retain` (a passage: UTF-8, <= 64 KiB) the bytes are any non-NUL
    bytes up to MAX_RAW_BYTES: a review case keeps the whole capture, never a
    truncated or re-encoded copy. Content-addressed and immutable like
    sources/; the reported sha256 lets the caller prove the bytes arrived
    unchanged (bash cannot carry NUL, so NUL is refused rather than lost)."""
    data = sys.stdin.buffer.read()
    if not data:
        raise RequestError("no raw input on stdin")
    if len(data) > _raw_max():
        raise RequestError(f"raw input is larger than {_raw_max()} bytes")
    if b"\0" in data:
        raise RequestError("raw input contains NUL bytes")
    if args.check_only:
        return
    digest = hashlib.sha256(data).hexdigest()
    rel = f"raw/{digest[:16]}.txt"
    path = os.path.join(args.store, rel)
    if os.path.lexists(path):
        if os.path.islink(path) or not os.path.isfile(path):
            raise FormatError(path, 0, "retained raw path is not a regular file")
        with open(path, "rb") as fh:
            if fh.read() != data:
                raise FormatError(path, 0, "hash collision: a different raw input "
                                  "is retained under this name")
    else:
        print(f"@TARGET:{rel}")
    print(f"RETAINED_RAW:{rel}|{digest}|{len(data)}")


def op_retain_case(args, _text):
    """Retain one TRUSTED review-case record under cases/<16 hex>.txt (t2175_6).

    Content-addressed and immutable like sources/, but a separate namespace:
    only harvest-built records (line 1 one of CASE_RECORD_HEADERS) can land
    here, so harvested text can never pose as case metadata."""
    data = sys.stdin.buffer.read()
    if not data:
        raise RequestError("no case record on stdin")
    if len(data) > MAX_RETAIN_BYTES:
        raise RequestError(f"case record is larger than {MAX_RETAIN_BYTES} bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise RequestError("case record is not valid UTF-8") from None
    if "\0" in text or "\r" in text:
        raise RequestError("case record contains NUL or CR")
    if text.split("\n", 1)[0] not in CASE_RECORD_HEADERS:
        raise RequestError("case record must start with a case record header")
    if args.check_only:
        return
    hexname = hashlib.sha256(data).hexdigest()[:16]
    rel = f"cases/{hexname}.txt"
    path = os.path.join(args.store, rel)
    if os.path.lexists(path):
        if os.path.islink(path) or not os.path.isfile(path):
            raise FormatError(path, 0, "case record path is not a regular file")
        with open(path, "rb") as fh:
            if fh.read() != data:
                raise FormatError(path, 0, "hash collision: a different case "
                                  "record is retained under this name")
    else:
        print(f"@TARGET:{rel}")
    print(f"RETAINED_CASE:{rel}")


def op_retain_baseline(args, _text):
    """Retain one direction baseline snapshot under baselines/<16 hex>.txt.

    Content-addressed and immutable, in its own namespace (the retain-case
    pattern): only text in the snapshot grammar lands here. The name is the
    `digest` a direction's summary is saved with. A snapshot above
    MAX_BASELINE_BYTES is refused whole -- never truncated or sampled. A file
    already at the name whose bytes do not hash to it is damage, and is
    replaced by the right bytes (the name says what they are)."""
    data = sys.stdin.buffer.read()
    if not data:
        raise RequestError("no baseline snapshot on stdin")
    if len(data) > MAX_BASELINE_BYTES:
        raise RequestError(f"baseline snapshot is {len(data)} bytes (limit "
                           f"{MAX_BASELINE_BYTES}): the direction has too many "
                           "pending members to summarise as one")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise RequestError("baseline snapshot is not valid UTF-8") from None
    if "\0" in text:
        raise RequestError("baseline snapshot contains NUL")
    parse_baseline(text)
    if args.check_only:
        return
    hexname = hashlib.sha256(data).hexdigest()[:16]
    rel = f"baselines/{hexname}.txt"
    path = os.path.join(args.store, rel)
    write = True
    if os.path.lexists(path):
        if os.path.islink(path) or not os.path.isfile(path):
            raise FormatError(path, 0, "baseline path is not a regular file")
        with open(path, "rb") as fh:
            found = fh.read()
        if found == data:
            write = False
        elif hashlib.sha256(found).hexdigest()[:16] == hexname:
            raise FormatError(path, 0, "hash collision: a different snapshot is "
                              "retained under this name")
    if write:
        print(f"@TARGET:{rel}")
    print(f"RETAINED_BASELINE:{rel}|{hexname}")


def read_case_record(store_dir: str, hexname: str):
    """The text of the TRUSTED record cases/<hexname>.txt, or None."""
    if not re.fullmatch(r"[0-9a-f]{16}", hexname or ""):
        return None
    path = os.path.join(store_dir, "cases", f"{hexname}.txt")
    try:
        if os.path.islink(path):
            return None
        with open(path, "rb") as fh:
            data = fh.read(MAX_RETAIN_BYTES + 1)
    except OSError:
        return None
    text = data.decode("utf-8", "replace")
    return text if text.split("\n", 1)[0] in CASE_RECORD_HEADERS else None


def case_origin_input(store_dir: str, hexname: str):
    """``(raw rel path, sha256)`` named by the TRUSTED case origin record
    cases/<hexname>.txt, or None (a sources/ passage that merely starts with
    the origin header has no trusted twin and is never followed)."""
    path = os.path.join(store_dir, "cases", f"{hexname}.txt")
    try:
        if os.path.islink(path):
            return None
        with open(path, "rb") as fh:
            data = fh.read(MAX_RETAIN_BYTES + 1)
    except OSError:
        return None
    lines = data.decode("utf-8", "replace").split("\n")
    if not lines or lines[0] != CASE_ORIGIN_HEADER:
        return None
    vals = dict(ln.partition("=")[::2] for ln in lines[1:] if "=" in ln)
    rel, sha = vals.get("input", ""), vals.get("input_sha256", "")
    if not RAW_RE.match(rel) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return None
    return rel, sha


def raw_input_ok(store_dir: str, rel: str, sha: str) -> bool:
    """Is the raw input there, a regular file, with exactly that sha256?"""
    path = os.path.join(store_dir, rel)
    if os.path.islink(path) or not os.path.isfile(path):
        return False
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return False
    return h.hexdigest() == sha


def load_todo_for_read(store_dir: str) -> TodoStore:
    """load_todo for the read-only verbs: a never-initialized store is empty,
    a missing todo.md in an established store is damage (exit 4)."""
    if not os.path.exists(os.path.join(store_dir, "todo.md")):
        _require_not_damaged(store_dir, "todo")
        return TodoStore()
    return load_todo(store_dir)


def load_qa_for_read(store_dir: str) -> QaLog:
    """load_qa for read-only consumers (the sitrep TUI, t2211_1): a
    never-initialized store has an empty log, a missing qa.md in an
    established store is damage (exit 4)."""
    if not os.path.exists(os.path.join(store_dir, "qa.md")):
        _require_not_damaged(store_dir, "qa")
        return QaLog()
    return load_qa(store_dir)


def op_list(args, _text):
    store = load_todo_for_read(args.store)
    if not store.items:
        print("NO_ITEMS")
        return
    _emit(store.items[n].machine() for n in sorted(store.items))


def op_context(args, _text):
    num = parse_id(args.id)
    store = load_todo_for_read(args.store)
    _find(store, num)
    entry = store.contexts.get(num)
    if entry is None:
        print(f"NO_CONTEXT:c{num}")
        return
    _emit([f"### c{num}"] + entry.body_lines())


def op_directions(args, _text):
    """The directions and their members: one DIRECTION line each (the ranked
    ones by rank, then the unranked by slug), followed by its summary, drift
    and member lines; the full listing ends with the items in no direction."""
    only = parse_slug(args.direction) if args.direction else None
    store = load_todo_for_read(args.store)
    members = direction_members(store)
    slugs = known_directions(store)
    if only is not None:
        if only not in slugs:
            print(f"NOT_FOUND:{only}")
            raise RequestError(f"no direction {only}")
        slugs = [only]
    out = []
    for slug in slugs:
        d = store.directions.get(slug)
        rec = d if d is not None else Direction()
        nums = members.get(slug, [])
        pending = sum(1 for n in nums if store.items[n].state in ("open", "unknown"))
        out.append("DIRECTION:" + "|".join([
            slug, str(rec.rev) if rec.rev else "-", direction_stamp(store, slug, nums),
            str(rec.rank) if rec.rank else "-", rec.freshness, rec.checked_at,
            rec.digest, rec.next, ",".join(rec.trails), str(pending),
            str(len(nums)), rec.title]))
        if rec.summary:
            out.append(f"DIRECTION_SUMMARY:{slug}|{rec.summary}")
        out.extend(f"DIRECTION_DRIFT:{slug}|{code}|{count}|{'+'.join(keys)}"
                   for code, count, keys in rec.drift)
        for n in nums:
            it = store.items[n]
            out.append(f"DIRECTION_MEMBER:{slug}|c{n}|{it.state}|{it.kind}|{it.ref}")
    if only is None:
        if not slugs:
            out.append("NO_DIRECTIONS")
        free = unassigned_items(store)
        out.append(f"UNASSIGNED:{len(free)}|{','.join(f'c{n}' for n in free)}")
    _emit(out)


def op_check_sources(args, _text):
    """Retained-capture pointers only: task/plan/file targets move on archival.

    A pointer at a review case ORIGIN file (t2175_6) is followed one step: the
    raw input it names must exist with its recorded sha256, reported as its
    own SOURCE_OK / SOURCE_MISSING line (a mismatch is missing).

    Each direction with a digest adds one line for its baseline snapshot:
    SOURCE_OK, SOURCE_MISSING, or SOURCE_INVALID with the load_baseline status
    (a file that is there but does not verify is unusable, not present)."""
    store = load_todo_for_read(args.store)
    out = []
    for num in sorted(store.contexts):
        raws = []
        for stype, ptr in store.contexts[num].sources:
            if stype != "capture":
                continue
            try:
                _check_pointer(stype, ptr, args.store)
                out.append(f"SOURCE_OK:c{num}|{ptr}")
            except RequestError:
                out.append(f"SOURCE_MISSING:c{num}|{ptr}")
                continue
            m = CAPTURE_RE.match(ptr)
            raw = case_origin_input(args.store, m.group(1)) if m else None
            if raw and raw not in raws:
                raws.append(raw)
        for rel, sha in raws:
            ok = raw_input_ok(args.store, rel, sha)
            out.append(f"{'SOURCE_OK' if ok else 'SOURCE_MISSING'}:c{num}|{rel}")
    for slug in sorted(store.directions):
        digest = store.directions[slug].digest
        if not digest:
            continue
        rel = f"baselines/{digest}.txt"
        status = baseline_status(args.store, digest, slug)
        if status == "ok":
            out.append(f"SOURCE_OK:{slug}|{rel}")
        elif status == "missing":
            out.append(f"SOURCE_MISSING:{slug}|{rel}")
        else:
            out.append(f"SOURCE_INVALID:{slug}|{rel}|{status}")
    _emit(out or ["NO_SOURCES"])


def op_verify(args, _text):
    text = _read(args.file)
    if text is None:
        raise FormatError(args.file, 0, "file is missing")
    (parse_todo if args.kind == "todo" else parse_qa)(text, args.file)
    print(f"VERIFIED:{args.kind}")


def op_newer_format(args, _text):
    """NEWER:<n> when the file's line 2 is a well-formed format header above
    the one this module writes, else NOT_NEWER. The wrapper's `restore` asks
    before it treats an unparsable file as damaged: a newer store is not."""
    text = _read_tolerant(args.file)
    found = None
    if args.kind == "todo":
        found = newer_format(text)
    else:
        lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        m = (re.match(r"^<!-- aitask-sitrep qa format=([1-9][0-9]*) -->\Z",
                      lines[1].rstrip(" \t")) if len(lines) > 1 else None)
        if m and int(m.group(1)) > QA_FORMAT_VERSION:
            found = int(m.group(1))
    print(f"NEWER:{found}" if found else "NOT_NEWER")


def op_empty(args, _text):
    sys.stdout.write(empty_text(args.kind))


def op_state(args, _text):
    print(store_state(args.store))


def op_alloc(args, _text):
    print(alloc_id(args.store))


def op_alloc_rev(args, _text):
    print(alloc_rev(args.store))


def _require_not_damaged(store_dir: str, kind: str) -> None:
    state = store_state(store_dir)
    if "ESTABLISHED=1" in state:
        raise FormatError(os.path.join(store_dir, f"{kind}.md"), 0,
                          f"{kind}.md is missing from an established store -- "
                          f"run `aitask_sitrep_todo.sh restore {kind}`")


def op_read(args, _text):
    kind = "qa" if args.part == "qa" else "todo"
    path = os.path.join(args.store, f"{kind}.md")
    if not os.path.exists(path):
        if os.path.isdir(args.store):
            _require_not_damaged(args.store, kind)
        return
    text = _read_tolerant(path) or ""
    if args.part in ("all", "qa"):
        sys.stdout.write(text)
        return
    lines = text.split("\n")
    cut = lines.index(PART2) if PART2 in lines else len(lines)
    part = lines[:cut] if args.part == "todo" else lines[cut:]
    out = "\n".join(part).rstrip("\n")
    if out:
        sys.stdout.write(out + "\n")


def op_path(args, _text):
    print(os.path.realpath(args.store))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sitrep_todo.py")
    sub = p.add_subparsers(dest="op", required=True)

    def mk(name, fn, mutating=False, needs_input=False):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        sp.add_argument("--store", default=".aitask-sitrep")
        sp.add_argument("--check-only", action="store_true")
        if mutating:
            sp.add_argument("--out", default="")
            # Where a todo write that UPGRADES the format leaves the previous
            # generation, re-rendered in the new format (see _commit_todo).
            sp.add_argument("--out-bak", default="")
        if needs_input:
            sp.add_argument("--input", default="")
        return sp

    sp = mk("add", op_add, True, True)
    sp.add_argument("--kind", required=True)
    sp.add_argument("--title", required=True)
    sp.add_argument("--ref", default="")
    sp.add_argument("--group", default="next")
    sp.add_argument("--state", default="open")
    sp.add_argument("--derived", default="script")
    sp.add_argument("--checked-at", default="never")
    sp = mk("update", op_update, True)
    sp.add_argument("id")
    for flag in ("--title", "--group", "--ref", "--kind"):
        sp.add_argument(flag, default=None)
    sp.add_argument("--expect-rev", type=int, default=None)
    sp = mk("set-state", op_set_state, True)
    sp.add_argument("id")
    sp.add_argument("state")
    sp.add_argument("--checked-at", default="now")
    sp.add_argument("--outcome", default=None)
    sp.add_argument("--expect-rev", type=int, default=None)
    mk("set-state-batch", op_set_state_batch, True, True)
    sp = mk("recovery-apply", op_recovery_apply, True, True)
    for flag in ("--ref", "--expect-rev", "--incarnation", "--state", "--outcome",
                 "--checked-at"):
        sp.add_argument(flag, required=True)
    sp.add_argument("--title", default=None)
    sp.add_argument("--group", default=None)
    sp = mk("situation", op_situation, True, True)
    sp.add_argument("direction")
    sp = mk("upsert-context", op_upsert_context, True, True)
    sp.add_argument("id")
    sp.add_argument("--expect-rev", type=int, default=None)
    sp = mk("direction-set", op_direction_set, True, True)
    sp.add_argument("direction")
    sp.add_argument("--expect-rev", required=True)
    for flag in ("--title", "--trails", "--next", "--digest"):
        sp.add_argument(flag, default=None)
    mk("direction-assign-batch", op_direction_assign_batch, True, True)
    sp = mk("direction-rank", op_direction_rank, True, True)
    sp.add_argument("--expect-ranked", required=True)
    sp.add_argument("--clear", action="store_true")
    mk("direction-freshness-batch", op_direction_freshness_batch, True, True)
    sp = mk("direction-remove", op_direction_remove, True)
    sp.add_argument("direction")
    sp.add_argument("--expect-rev", required=True)
    sp = mk("qa", op_qa, True, True)
    sp.add_argument("--items", default="")
    mk("retain", op_retain, True)
    mk("retain-raw", op_retain_raw, True)
    mk("retain-case", op_retain_case, True)
    mk("retain-baseline", op_retain_baseline, True)
    mk("list", op_list)
    sp = mk("context", op_context)
    sp.add_argument("id")
    sp = mk("directions", op_directions)
    sp.add_argument("direction", nargs="?", default="")
    mk("check-sources", op_check_sources)
    sp = mk("verify", op_verify)
    sp.add_argument("kind", choices=("todo", "qa"))
    sp.add_argument("file")
    sp = mk("newer-format", op_newer_format)
    sp.add_argument("kind", choices=("todo", "qa"))
    sp.add_argument("file")
    sp = mk("empty", op_empty)
    sp.add_argument("kind", choices=("todo", "qa"))
    mk("state", op_state)
    mk("alloc", op_alloc)
    mk("alloc-rev", op_alloc_rev)
    sp = mk("read", op_read)
    sp.add_argument("part", nargs="?", default="all",
                    choices=("all", "todo", "context", "qa"))
    mk("path", op_path)
    return p


def main(argv=None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        text = _read_input(args)
        args.fn(args, text)
    except RequestError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except FormatError as e:
        print(f"Error: store unusable: {e}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
