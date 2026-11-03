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

* ``todo.md`` / ``todo.md.bak`` -- Part 1 (situation per theme, items grouped
  Pick now / Next / Waiting / Recently done / Dismissed) and Part 2 (one
  context entry per item: a MAP of pointers, never a summary).
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
* ``recovered/`` -- damaged files preserved by ``restore``.

STRICT FORMAT. Line 1 of every data file is a fixed generated-file banner and
line 2 a ``format=`` header. :func:`parse_todo` / :func:`parse_qa` build the
model loosely and then require ``render(model) == text``: any byte that the
renderer would not have produced -- a hand edit, a reordered record, a stray
blank line -- is a :class:`FormatError` naming the first differing line. So
render∘parse is the identity on writer output by construction.

CONSUMER CONTRACT. ``tests/fixtures/sitrep/`` holds a writer-produced store and
``tests/test_sitrep_todo.sh`` pins its ``list``/``context``/``check-sources``
output. A format change edits that fixture and bumps ``format=``.

FORMAT VERSIONS. todo.md is format 2: format 1 plus the ``push:<branch>@<sha>``
ref (a push reminder, created by the sitrep skill and checked by the refresh,
t2175_3). Format 1 files are still read -- render emits the parsed version, so
render∘parse stays the identity -- and the first write that CHANGES one upgrades
it to 2 (a no-op leaves it byte-identical); a format 1 file holding a ``push:``
ref is refused. ``tests/fixtures/sitrep/store_v1/`` pins the format 1 read.
qa.md is unchanged and stays format 1.

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

# todo.md is format 2 since t2175_3 (the `push:` ref form); format 1 files are
# still READ (render emits the parsed version, so render∘parse stays the
# identity) and are upgraded to 2 by the first write that changes them. qa.md
# did not change and stays format 1.
TODO_FORMAT_VERSION = 2
TODO_READ_FORMATS = (1, 2)
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

CONTEXT_KEYS = ("background", "origin", "theme", "sources", "related")
DENIED_CONTEXT_KEYS = frozenset({
    "status", "state", "next", "todo", "count", "counts", "progress",
    "summary", "overlap", "eta", "blocked", "done",
})
ORIGIN_KEYS = frozenset({"agent", "task", "commit", "date", "skill", "pane"})
SOURCE_TYPES = ("task", "plan", "trail", "capture", "commit", "artifact",
                "file", "url")

MAX_TITLE = 200
MAX_OUTCOME = 200
MAX_BACKGROUND = 400
MAX_CONTEXT_BYTES = 2000
MAX_SITUATION_BYTES = 1200
MAX_QA_BYTES = 4000
MAX_RETAIN_BYTES = 64 * 1024

# Value grammars end in \Z, never `$`: Python's `$` also matches just before a
# final newline, so "2026-11-01T10:00:00Z\n" would pass and forge a line break.
TS_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
ID_RE = re.compile(r"^c?([1-9][0-9]*)\Z")
THEME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*\Z")
LOCAL_REF_RE = re.compile(r"^t?([1-9][0-9]*(?:_[1-9][0-9]*)?)\Z")
XREF_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)#t?([1-9][0-9]*(?:_[1-9][0-9]*)?)\Z")
# A push reminder (t2175_3): `push:<branch>@<sha>` -- "push <branch> so <sha>
# reaches its remote". The branch is a shell-safe subset of git's ref grammar
# (no `..`, `//`, a component starting with `.`, trailing `/`, `.` or `.lock`); the refresh additionally runs
# `git check-ref-format --branch` before using it, always as one argv element.
PUSH_REF_RE = re.compile(
    r"^push:([A-Za-z0-9_][A-Za-z0-9._/-]*)@([0-9a-fA-F]{7,40})\Z")
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
    theme: str = ""
    sources: list = field(default_factory=list)     # [(type, pointer)]
    related: list = field(default_factory=list)     # [int]

    def body_lines(self) -> list:
        out = [f"- background: {self.background}",
               "- origin: " + " ".join(f"{k}={v}" for k, v in self.origin)]
        if self.theme:
            out.append(f"- theme: {self.theme}")
        if self.sources:
            out.append("- sources:")
            out.extend(f"  - {t}: {p}" for t, p in self.sources)
        if self.related:
            out.append("- related: " + ", ".join(f"c{n}" for n in self.related))
        return out


@dataclass
class TodoStore:
    situations: dict = field(default_factory=dict)  # theme -> [lines]
    items: dict = field(default_factory=dict)       # num -> Item
    contexts: dict = field(default_factory=dict)    # num -> ContextEntry
    # The `format=` of line 2: the parsed one for a read file, the current one
    # for a new or rewritten file (see _commit_todo).
    format: int = TODO_FORMAT_VERSION


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
    for theme in sorted(store.situations):
        lines.append(f"#### {theme}")
        lines.extend(store.situations[theme])
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
        lines.extend(store.contexts[num].body_lines())
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
    if not lines or lines[0] != TODO_BANNER:
        raise FormatError(path, 1, "missing or altered generated-file banner "
                          "(the file was edited by hand?)")
    found = lines[1] if len(lines) > 1 else ""
    m = _TODO_HEADER_RE.match(found)
    if not m or int(m.group(1)) not in TODO_READ_FORMATS:
        raise FormatError(path, 2, f"unsupported or missing format header {found!r}")
    return int(m.group(1))


def _parse_context_body(lines: list) -> ContextEntry:
    """Parse context-entry body lines. Raises ValueError((index, msg))."""
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
            if key not in CONTEXT_KEYS:
                raise ValueError((idx, f"unknown context key '{key}' (allowed: "
                                  f"{', '.join(CONTEXT_KEYS)})"))
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
    if "theme" in seen:
        entry.theme = seen["theme"][1]
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


def parse_todo(text: str, path: str = "todo.md") -> TodoStore:
    if not text.endswith("\n"):
        raise FormatError(path, text.count("\n") + 1, "missing final newline")
    lines = text.split("\n")[:-1]
    store = TodoStore(format=_todo_format(path, lines))
    mode = "head"
    theme = None
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
                theme = m.group(1)
                if not THEME_RE.match(theme):
                    raise FormatError(path, lineno, f"invalid theme {theme!r}")
                if theme in store.situations:
                    raise FormatError(path, lineno, f"duplicate theme {theme!r}")
                store.situations[theme] = []
            elif line.startswith("#"):
                raise FormatError(path, lineno, f"unexpected heading {line!r}")
            elif theme is not None:
                store.situations[theme].append(line)
            elif line:
                raise FormatError(path, lineno, "situation text outside a '#### <theme>' block")
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
    for theme_lines in store.situations.values():
        while theme_lines and not theme_lines[-1]:
            theme_lines.pop()
    for num, (lineno, body) in ctx_lines.items():
        if num not in store.items:
            raise FormatError(path, lineno, f"context entry c{num} names no item")
        try:
            entry = _parse_context_body(body)
            _check_context_values(entry, None)
        except ValueError as e:
            off, msg = e.args[0]
            raise FormatError(path, lineno + 1 + off, msg) from None
        except RequestError as e:
            raise FormatError(path, lineno, str(e)) from None
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
    m = PUSH_REF_RE.match(ref)
    if m and _push_branch_ok(m.group(1)):
        return f"push:{m.group(1)}@{m.group(2).lower()}"
    raise RequestError(f"invalid ref {ref!r} (expected t<N>[_<M>], "
                       "<project>#<N>[_<M>] for a cross-repo task, or "
                       "push:<branch>@<sha> for a push reminder)")


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
    for _, v in entry.origin:
        if "|" in v:
            raise RequestError("origin values must not contain '|'")
    if entry.theme and not THEME_RE.match(entry.theme):
        raise RequestError(f"invalid theme {entry.theme!r} (expected [a-z0-9][a-z0-9_-]*)")
    for stype, ptr in entry.sources:
        if stype not in SOURCE_TYPES:
            raise RequestError(f"unknown source type '{stype}' (allowed: "
                               f"{', '.join(SOURCE_TYPES)})")
        _check_pointer(stype, ptr, store_dir)
    size = len("\n".join(entry.body_lines()).encode("utf-8"))
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
    return parse_todo(text, path)


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
    """Highest item rev found on an item line in `text` (any text)."""
    best = 0
    for line in text.split("\n"):
        m = _REV_RE.match(line)
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
    marker holds no data UNLESS a post-init artifact (next_id, sources/,
    recovered/) or a non-template data file says otherwise -- then the marker
    was lost, not never written, and a missing data file is DAMAGE, never
    something to re-initialize over.
    """
    j = lambda n: os.path.join(store_dir, n)  # noqa: E731
    marker = os.path.isfile(j("store.init"))
    established = (marker or os.path.exists(j("next_id"))
                   or os.path.exists(j("next_rev")))
    for d in ("sources", "recovered"):
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


def _commit_todo(args, store: TodoStore, revs=None) -> None:
    # Every write that changes todo.md writes the CURRENT format: a format=1
    # store is upgraded by its first changing write. Ops call this only when
    # something changed, so a no-op leaves a v1 file byte-identical.
    store.format = TODO_FORMAT_VERSION
    _commit_text(args, render_todo(store), parse_todo)
    if revs is not None and revs.used:
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
    if not THEME_RE.match(args.theme):
        raise RequestError(f"invalid theme {args.theme!r} (expected [a-z0-9][a-z0-9_-]*)")
    lines = validate_situation(text)
    if args.check_only:
        return
    store = load_todo(args.store)
    if not lines:
        if args.theme in store.situations:
            del store.situations[args.theme]
            _commit_todo(args, store)
            print(f"SITUATION:{args.theme}|removed")
        else:
            print(f"SITUATION:{args.theme}|absent")
        return
    if store.situations.get(args.theme) != lines:
        store.situations[args.theme] = lines
        _commit_todo(args, store)
    print(f"SITUATION:{args.theme}|set")


def op_upsert_context(args, text):
    num = parse_id(args.id)
    entry = validate_context_input(text, None)
    if args.check_only:
        return
    store = load_todo(args.store)
    _find(store, num)
    _check_context_values(entry, args.store)
    _check_related(entry, alloc_id(args.store), num)
    old = store.contexts.get(num)
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


def load_todo_for_read(store_dir: str) -> TodoStore:
    """load_todo for the read-only verbs: a never-initialized store is empty,
    a missing todo.md in an established store is damage (exit 4)."""
    if not os.path.exists(os.path.join(store_dir, "todo.md")):
        _require_not_damaged(store_dir, "todo")
        return TodoStore()
    return load_todo(store_dir)


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


def op_check_sources(args, _text):
    """Retained-capture pointers only: task/plan/file targets move on archival."""
    store = load_todo_for_read(args.store)
    out = []
    for num in sorted(store.contexts):
        for stype, ptr in store.contexts[num].sources:
            if stype != "capture":
                continue
            try:
                _check_pointer(stype, ptr, args.store)
                out.append(f"SOURCE_OK:c{num}|{ptr}")
            except RequestError:
                out.append(f"SOURCE_MISSING:c{num}|{ptr}")
    _emit(out or ["NO_SOURCES"])


def op_verify(args, _text):
    text = _read(args.file)
    if text is None:
        raise FormatError(args.file, 0, "file is missing")
    (parse_todo if args.kind == "todo" else parse_qa)(text, args.file)
    print(f"VERIFIED:{args.kind}")


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
    sp = mk("situation", op_situation, True, True)
    sp.add_argument("theme")
    sp = mk("upsert-context", op_upsert_context, True, True)
    sp.add_argument("id")
    sp = mk("qa", op_qa, True, True)
    sp.add_argument("--items", default="")
    mk("retain", op_retain, True)
    mk("list", op_list)
    sp = mk("context", op_context)
    sp.add_argument("id")
    mk("check-sources", op_check_sources)
    sp = mk("verify", op_verify)
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
