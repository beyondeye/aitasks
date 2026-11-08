#!/usr/bin/env python3
"""relations_consume.py - the consumer side of the task-relations store (t1981_5).

aidocs/framework/task_relations.md D8 ("Consumption: hybrid") and its "Consumer
API" section. Pull by default, push narrowly:

* :func:`related_work` -- the display-only "related work" check, run at pick time
  (task-workflow Step 3 Check 8), again at the target's own Step 8 ("related work
  during this implementation"), and as the sender view of ``/aitask-note`` with
  no target.
* :func:`notify_candidates` -- the Step 8e push/pull split: a PUSH row only for an
  ``affects`` / ``coordinates_with`` relation whose direction fits, whose impact
  the source's own landed change confirms, and whose recipient is in flight and
  still cites the confirmed basis. Every other connected relation is a PULL row
  with a reason. Nothing is discarded.
* :func:`confirm` -- the one confirmation function, shared by push (against S's
  change) and pull (against a landed task's own change).
* :func:`plain_summary` -- the one plain-words rendering of the state lines, so
  every surface says "disabled" / "not analysed yet" / "unknown" the same way and
  none of them ever reads an incomplete or unreachable state as "no relations".
* :func:`append_ledger` -- the local ``pull.jsonl`` / ``notify.jsonl`` ledgers
  (D13.3) under ``<git-common-dir>/aitask-relations/``.

This module is read-only except for those two ledgers. It never writes task
data, never commits and never sends a note: offers are made (and notes sent) by
the agent, through ``/aitask-note``.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import os
import re
import socket
import sys

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import archive_iter  # noqa: E402
import note_inbox  # noqa: E402
import orphan_ref_store as ors  # noqa: E402
import plan_paths  # noqa: E402
import relations_schema as rs  # noqa: E402
import relations_store as rst  # noqa: E402
from task_yaml import parse_frontmatter  # noqa: E402

PUSH_TYPES = ("affects", "coordinates_with")
SYMMETRIC = tuple(t for t, kind in rs.TYPES.items() if kind == "symmetric")
MAX_ITEMS = 8
POINTS = ("pick", "review", "note")
OPTIONS = ("complete", "disabled", "wait", "wait_failed", "wait_refused_cap",
           "fallback", "fallback_unavailable", "proceed")
OUTCOMES = ("sent", "declined", "not_offered")
# PULL reasons, in rule order (design doc D8 "Consumer API").
PULL_REASONS = ("relations_disabled", "type_not_pushed", "reverse_direction", "other_project",
                "target_closed", "unconfirmed_impact", "target_state", "target_moved")
GROUP_ORDER = ("landed", "dropped", "late", "in_flight", "own", "pending")

DISABLED_TEXT = "relations analysis is disabled in this project — no relation data"


# ===================================================================== encoding

def enc(value) -> str:
    """Percent-encode a line-protocol field: ``%`` first, then ``|``, CR, LF."""
    return (str(value).replace("%", "%25").replace("|", "%7C")
            .replace("\r", "%0D").replace("\n", "%0A"))


def dec(value: str) -> str:
    """Inverse of :func:`enc`, in the documented order (%0D, %0A, %7C, then %25)."""
    return (value.replace("%0D", "\r").replace("%0A", "\n")
            .replace("%7C", "|").replace("%25", "%"))


# ======================================================================== times

def parse_time(value):
    """Aware UTC datetime for an ISO ``...Z`` instant or a local ``YYYY-MM-DD HH:MM[:SS]``.

    Task frontmatter times and the lock's ``locked_at`` are naive local times;
    store records carry ISO UTC. None when the value cannot be parsed -- callers
    treat that as "time unknown", never as "before" or "after".
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            ts = _dt.datetime.fromisoformat(text)
        else:
            ts = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    ts = _dt.datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            if ts is None:
                return None
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.astimezone()  # naive == local time
    return ts.astimezone(_dt.timezone.utc)


def iso(ts) -> str:
    return ts.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else "unknown"


def now_utc():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def after(ts, since) -> bool:
    """``ts`` is after ``since``; an unknown ``ts`` counts as after (fail-open display)."""
    return ts is None or since is None or ts > since


# =================================================================== change sets

@dataclasses.dataclass
class ChangeSet:
    origin: str                      # "commits:<rev>" or "diff:<range>"
    commits: list                    # commit ids (empty for a range)
    paths: dict                      # changed path -> the commit (or range) that changed it
    hunks: list                      # (commit, file, line) for every +/- content line
    error: str | None = None

    @property
    def empty(self) -> bool:
        return not self.paths and not self.hunks


def _git(root, *args) -> str:
    return ors.git(root, *args).stdout.decode("utf-8", "surrogateescape")


def _name_status(raw: str, label: str, paths: dict):
    toks = raw.split("\0")
    i = 0
    while i < len(toks):
        status = toks[i]
        if not status:
            i += 1
            continue
        n = 2 if status[:1] in ("R", "C") else 1
        for p in toks[i + 1:i + 1 + n]:
            if p:
                paths.setdefault(p, label)
        i += 1 + n


_CQUOTE = {"a": "\a", "b": "\b", "t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
           '"': '"', "\\": "\\"}


def _unquote(path: str) -> str:
    """Undo git's C-style path quoting (``"sp\\ta\\303\\251"``); plain paths pass through."""
    if not (len(path) >= 2 and path.startswith('"') and path.endswith('"')):
        return path
    body, out, i = path[1:-1], bytearray(), 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if i + 4 <= len(body) and all(c in "01234567" for c in body[i + 1:i + 4]):
                out.append(int(body[i + 1:i + 4], 8))
                i += 4
                continue
            out += _CQUOTE.get(nxt, nxt).encode("utf-8", "surrogateescape")
            i += 2
            continue
        out += ch.encode("utf-8", "surrogateescape")
        i += 1
    return out.decode("utf-8", "surrogateescape")


def _side(header: str, prefix: str):
    """The path of a ``--- a/x`` / ``+++ b/y`` header, or None for ``/dev/null``.

    Git ends the header with a TAB when the name contains a space; a real name
    cannot end in a TAB (a TAB forces C-quoting), so one trailing TAB is dropped.
    """
    if header.endswith("\t"):
        header = header[:-1]
    value = _unquote(header)
    if value == "/dev/null":
        return None
    return value[len(prefix):] if value.startswith(prefix) else value


def _hunks(raw: str, label: str, out: list):
    """Content lines of a ``-U0`` patch: ``+``/``-`` lines inside ``@@`` hunks only.

    Header lines (``+++`` / ``---``) appear only between ``diff --git`` and the
    first ``@@``, so tracking the hunk state keeps a removed line whose content
    starts with ``--`` from being mistaken for a header. A deletion's ``+++`` side
    is ``/dev/null``: its lines are attributed to the OLD path, never to
    ``/dev/null``. Git-quoted paths are unquoted.
    """
    in_hunk, old, current = False, None, ""
    for line in raw.split("\n"):
        if line.startswith("diff --git "):
            in_hunk, old, current = False, None, ""
            continue
        if not in_hunk:
            if line.startswith("--- "):
                old = _side(line[4:], "a/")
                current = old or ""
            elif line.startswith("+++ "):
                new = _side(line[4:], "b/")
                current = new if new is not None else (old or "")
            elif line.startswith("@@"):
                in_hunk = True
            continue
        if line.startswith("@@"):
            continue
        if line[:1] in ("+", "-"):
            out.append((label, current, line[1:]))


def commits_for(root, tid, rev="HEAD") -> list:
    """Commits reachable from ``rev`` whose SUBJECT carries the literal ``(t<tid>)``.

    The closing paren is what keeps ``(t1981_50)`` from matching ``(t1981_5)``.
    Newest first, as ``git log`` lists them.
    """
    token = f"(t{rs.norm_id(tid)})"
    raw = _git(root, "log", "-z", "--format=%H%x1f%s", rev, "--")
    out = []
    for entry in raw.split("\0"):
        if "\x1f" not in entry:
            continue
        sha, subject = entry.split("\x1f", 1)
        if token in subject:
            out.append(sha.strip())
    return out


def changeset_for_commits(root, commits, origin) -> ChangeSet:
    paths, hunks = {}, []
    for c in commits:
        _name_status(_git(root, "diff-tree", "-r", "-M", "--root", "--name-status", "-z",
                          "--no-commit-id", c), c, paths)
        _hunks(_git(root, "show", "-U0", "-M", "--format=", "--no-color", c), c, hunks)
    return ChangeSet(origin, list(commits), paths, hunks)


def changeset_for_range(root, rng) -> ChangeSet:
    if not rng or rng.startswith("-"):
        raise ValueError(f"refusing diff range {rng!r}")
    paths, hunks = {}, []
    _name_status(_git(root, "diff", "-M", "-z", "--name-status", rng, "--"), rng, paths)
    _hunks(_git(root, "diff", "-U0", "-M", "--no-color", rng, "--"), rng, hunks)
    return ChangeSet(f"diff:{rng}", [], paths, hunks)


class Changes:
    """Per-invocation cache of ``(t<id>)`` change sets (one history walk per id)."""

    def __init__(self, root, rev="HEAD"):
        self.root, self.rev = root, rev
        self._cache: dict = {}

    def of(self, tid) -> ChangeSet:
        tid = rs.norm_id(tid)
        if tid not in self._cache:
            try:
                commits = commits_for(self.root, tid, self.rev)
                self._cache[tid] = changeset_for_commits(self.root, commits,
                                                         f"commits:{self.rev}")
            except (ors.GitError, OSError) as exc:
                self._cache[tid] = ChangeSet(f"commits:{self.rev}", [], {}, [],
                                             error=str(exc).splitlines()[0][:200])
        return self._cache[tid]


# ================================================================= confirmation

def _ident_re(value):
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(value) + r"(?![A-Za-z0-9_])")


def _strip(path: str) -> str:
    return path[2:] if path.startswith("./") else path


def confirm(basis, cs: ChangeSet):
    """``(status, matched)`` of a relation's bases against a change set.

    Only impact bases can confirm: a ``path`` in the changed files (rename
    endpoints included), a ``symbol`` (identifier-bounded) or a ``token``
    (literal) in the diff's content lines. ``task_ref`` never confirms.
    ``matched`` is ``[(kind, value, commit, file)]``. A change set that could not
    be read gives ``unverified``, never ``unconfirmed``.
    """
    if cs.error:
        return "unverified", []
    matched = []
    for b in basis or []:
        kind, value = b.get("kind"), b.get("value")
        if kind not in rs.IMPACT_BASES or not isinstance(value, str) or not value:
            continue
        if kind == "path":
            p = _strip(value)
            if p in cs.paths:
                matched.append((kind, value, cs.paths[p], p))
            continue
        rx = _ident_re(value) if kind == "symbol" else None
        for commit, path, line in cs.hunks:
            if (rx.search(line) if rx else value in line):
                matched.append((kind, value, commit, path))
                break
    return ("confirmed_impact" if matched else "unconfirmed_impact"), matched


# ================================================================== end states

@dataclasses.dataclass
class End:
    kind: str            # landed|dropped|implementing|plan_holder|pending|other_project|unknown
    at: object = None    # landed/dropped time (aware UTC) or None
    detail: str = ""     # status, archived_reason, ...

    def label(self) -> str:
        if self.kind in ("landed", "dropped"):
            extra = f":{self.detail}" if self.kind == "dropped" and self.detail else ""
            return f"{self.kind}{extra}@{iso(self.at)}"
        if self.kind == "pending" and self.detail:
            return f"pending:{self.detail}"
        return self.kind


def _meta(text):
    if text is None:
        return {}
    try:
        parsed = parse_frontmatter(text)
    except Exception:  # malformed YAML: no metadata, never a crash
        return {}
    return parsed[0] if parsed and isinstance(parsed[0], dict) else {}


def active_plan_path(index: rst.TaskIndex, tid):
    """The task's plan in the ACTIVE plan dir, or None (archived plans don't count)."""
    tid = rs.norm_id(tid)
    if "_" in tid:
        parent, child = tid.split("_", 1)
        directory, name_re = index.plan_dir / f"p{parent}", re.compile(rf"^p{parent}_{child}_")
    else:
        directory, name_re = index.plan_dir, re.compile(rf"^p{tid}_(?!\d+_)")
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return None
    for name in names:
        if name.endswith(".md") and name_re.match(name):
            return directory / name
    return None


def archived_plan_path(index: rst.TaskIndex, tid, extract_dir=None):
    """Where the archived plan of a landed task can be READ, or ``-``.

    A loose archived plan is reported repo-relative. A plan that only exists
    inside a numbered (``_bN/oldM.tar.zst``) or legacy bundle is extracted to
    ``<extract_dir>/<member name>`` (runtime state under the relations state
    dir, overwritten each time) and that absolute path is reported, so the
    reader always gets a file it can open. The lookup order is
    ``TaskIndex._find_plan``'s: loose, numbered bundle, legacy bundle.
    """
    tid = rs.norm_id(tid)
    if "_" in tid:
        parent, child = tid.split("_", 1)
        directory, name_re = index.plan_archived_dir / f"p{parent}", re.compile(rf"^p{parent}_{child}_")
    else:
        parent = tid
        directory, name_re = index.plan_archived_dir, re.compile(rf"^p{tid}_(?!\d+_)")
    try:
        for name in sorted(os.listdir(directory)):
            if name.endswith(".md") and name_re.match(name):
                return os.path.relpath(directory / name, index.root)
    except OSError:
        pass
    if extract_dir is None:
        return "-"
    found = None
    errs: list = []
    zst = archive_iter.archive_path_for_id(int(parent), index.plan_archived_dir)
    for bundle in (zst, zst.with_suffix("").with_suffix(".tar.gz")):
        if found is None and bundle.exists():
            for name, text in archive_iter.iter_archive_file(bundle, errors=errs):
                if name_re.match(os.path.basename(name)):
                    found = (os.path.basename(name), text)
                    break
    if found is None:
        for name, text in archive_iter.iter_legacy_archive(index.plan_archived_dir, errors=errs):
            if name_re.match(os.path.basename(name)):
                found = (os.path.basename(name), text)
                break
    if found is None:
        return "-"
    try:
        os.makedirs(extract_dir, exist_ok=True)
        target = os.path.join(extract_dir, found[0])
        tmp = f"{target}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(found[1])
        os.replace(tmp, target)
    except OSError:
        return "-"
    return target


def end_state(store: rst.Store, ref) -> End:
    tid = store.local_id(ref)
    if tid is None:
        return End("other_project")
    entry = store.index.lookup(tid)
    if entry is None:
        return End("unknown")
    meta = _meta(entry.text)
    status = str(meta.get("status") or entry.status or "")
    # "Landed" means ARCHIVED as Done with no archived_reason (D8). An active task
    # whose status is Done (done but not yet archived) is not landed: it stays
    # pending, so neither the pull "landed" group nor the push target_closed rule
    # treats an unarchived task as closed.
    if entry.location != "active":
        reason = meta.get("archived_reason")
        at = parse_time(meta.get("completed_at") or meta.get("updated_at"))
        if reason:
            return End("dropped", at, str(reason))
        if status == "Done":
            return End("landed", at)
        return End("dropped", at, status.lower() or "archived")
    if status == "Implementing":
        return End("implementing", detail=status)
    if active_plan_path(store.index, tid) is not None or meta.get("plan_approved_at"):
        return End("plan_holder", detail=status)
    return End("pending", detail=status)


def cites_now(store: rst.Store, tid, matched) -> list:
    """The confirmed bases the target's CURRENT body or working plan still cites."""
    entry = store.index.lookup(tid)
    text = plan_paths.task_body_text(entry.text) if entry and entry.text else ""
    plan = active_plan_path(store.index, tid)
    if plan is not None:
        try:
            text += "\n" + plan.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    still = []
    for kind, value, *_rest in matched:
        if kind == "path":
            hit = bool(plan_paths.find_references(text, [_strip(value)]))
        elif kind == "symbol":
            hit = bool(_ident_re(value).search(text))
        else:
            hit = value in text
        if hit:
            still.append((kind, value))
    return still


# ================================================================== summaries

def plain_summary(relations_state, store_state, analysis_line) -> str:
    """The one plain-words rendering of RELATIONS_STATE / STORE / ANALYSIS.

    Every surface (Step 3 Check 8, the Step 8 re-check, Step 8e and
    ``/aitask-note``) displays this line verbatim. An unreachable store or an
    incomplete analysis is "unknown", never "none".
    """
    if relations_state == "disabled":
        return DISABLED_TEXT
    parts = []
    if relations_state == "host_off":
        parts.append("analysis is switched off on this host (AIT_RELATIONS=0) — showing stored data")
    store_state = store_state or ""
    if store_state.startswith("unreachable"):
        parts.append("the relations store could not be read — related work is unknown, not none")
        return "; ".join(parts)
    if store_state.startswith("stale"):
        when = store_state.rsplit("@", 1)[-1] if "@" in store_state else "never"
        parts.append(f"store data may be stale (last fetched {when})")
    a = analysis_line or ""
    m = re.match(r"^analysed:(\d+)\(([^)]*)\)$", a)
    if m:
        n, flags = int(m.group(1)), m.group(2).split(",")
        text = f"analysed, {n} relation{'s' if n != 1 else ''}"
        stage = next((f for f in flags if f.startswith("stage=")), None)
        if stage:
            text += f" ({stage.replace('=', ' ')})"
        if "stale" in flags:
            text += ", stale: the task changed since the analysis"
        if "partial" in flags:
            text += ", partial coverage"
        parts.append(text)
    elif a == "never":
        parts.append("not analysed yet")
    elif a.startswith("pending("):
        parts.append(f"analysis {a[len('pending('):-1]}")
    elif a.startswith("failed("):
        parts.append(f"analysis failed ({a[len('failed('):-1]})")
    elif a == "unknown(other_project)":
        parts.append("another project's task — not checkable here")
    elif a.startswith("unknown("):
        parts.append(f"analysis state unknown ({a[len('unknown('):-1]}) — not none")
    elif a == "disabled":
        parts.append(DISABLED_TEXT)
    elif a:
        parts.append(f"analysis: {a}")
    return "; ".join(parts) or "analysis state unknown — not none"


def plain_analysis_state(state: str) -> str:
    """Plain words for an ``analysis-state`` verdict (Step 8e)."""
    if state == "disabled":
        return DISABLED_TEXT
    if state == "complete":
        return "analysis complete for the approved plan"
    inner = state[len("incomplete:"):] if state.startswith("incomplete:") else state
    words = {
        "missing": "no analysis record for the approved plan has been published yet",
        "inputs_mismatch": "the analysis record is for other inputs (the plan or the body changed since)",
    }
    if inner in words:
        text = words[inner]
    elif inner.startswith("unverifiable("):
        text = f"completeness cannot be verified ({inner[len('unverifiable('):-1]})"
    elif inner.startswith("pending("):
        text = f"analysis is {inner[len('pending('):-1]}"
    elif inner.startswith("failed("):
        text = f"analysis failed ({inner[len('failed('):-1]})"
    else:
        text = inner
    return f"analysis INCOMPLETE — {text}; an empty list here is NOT an all-clear"


# ===================================================================== ledgers

def append_ledger(sdir: str, name: str, row: dict) -> None:
    """Append ONE JSON line to ``<sdir>/<name>.jsonl`` (O_APPEND, single write)."""
    if name not in ("pull", "notify"):
        raise ValueError(f"unknown ledger {name!r}")
    os.makedirs(sdir, exist_ok=True)
    data = (json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(os.path.join(sdir, f"{name}.jsonl"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _rel_key(rel) -> dict:
    return {"from": rel.from_, "to": rel.to, "type": rel.type, "record_task": rel.record_task}


# ================================================================ related work

@dataclasses.dataclass
class Item:
    group: str
    rel: object
    end: End
    confirmation: str
    plan: str = "-"
    covered_by_note: str | None = None
    published_at: object = None


def _record_at(store, snap, rel):
    tid = store.local_id(rel.record_task)
    rec = snap.files.get(rs.store_path("records", tid)) if tid else None
    try:
        return parse_time(rec["run"]["at"]) if rec else None
    except (KeyError, TypeError):
        return None


def _incoming(rel, me) -> bool:
    """The edge runs from the other end toward ``me``, or it is symmetric."""
    return rel.type in SYMMETRIC or rel.from_ != me


def notes_from(text, since) -> dict:
    """``{sender 't<id>': note id}`` of validated notes in ``## Inbox`` after ``since``.

    Read and unread alike: an acknowledged note still covers the relation.
    """
    out = {}
    for b in note_inbox.parse(text or ""):
        if note_inbox.is_receipt(b) or not note_inbox.validate_block(b):
            continue
        at = parse_time(b.fields.get("at"))
        if since is not None and at is not None and at <= since:
            continue
        out.setdefault(b.fields.get("from", ""), b.fields.get("id", ""))
    return out


def reference_time(store, snap, tid, point, since=None, lock_reader=None):
    """``(aware UTC or None, source)`` -- the reference time of the check (D8)."""
    if since is not None:
        return since, "since"
    entry = store.index.lookup(tid)
    meta = _meta(entry.text if entry else None)
    if point == "review" and lock_reader is not None:
        ts = parse_time(lock_reader(tid))
        if ts is not None:
            return ts, "lock"
    if point == "pick":
        ts = parse_time(meta.get("plan_approved_at"))
        if ts is not None:
            return ts, "plan_approved_at"
        st = snap.files.get(rs.store_path("approvals", tid))
        if st and entry is not None and st.get("task_created_at") == entry.created_at:
            ts = parse_time(st.get("approved_at"))
            if ts is not None:
                return ts, "approval_stamp"
    ts = parse_time(meta.get("created_at") or (entry.created_at if entry else None))
    return ts, ("created_at" if ts else "unknown")


def related_work(store, snap, task_id, point, since, changes: Changes, extract_dir=None):
    """``(items, more, before_reference)`` for the related-work display (D8 pull)."""
    me = store.canonical_ref(task_id)
    tid = store.local_id(me)
    entry = store.index.lookup(tid) if tid else None
    covered = notes_from(entry.text if entry else "", since) if point == "review" else {}
    items, before = [], 0
    for rel in store.relations(me, snap):
        end = end_state(store, rel.other)
        incoming = _incoming(rel, me)
        closed = end.kind in ("landed", "dropped")
        conf = "not_landed"
        other_id = store.local_id(rel.other)
        if end.kind == "landed" and other_id:
            conf, _m = confirm(rel.basis, changes.of(other_id))
        published = _record_at(store, snap, rel)
        group = None
        if point == "note":
            if closed:
                continue
            group = "in_flight" if end.kind == "implementing" else ("pending" if incoming else "own")
        elif point == "pick":
            if closed:
                if not after(end.at, since):
                    before += 1
                    continue
                group = end.kind if incoming else "own"
            elif end.kind == "implementing":
                group = "in_flight"
            else:
                group = "pending" if incoming else "own"
        else:  # review
            if closed and incoming and after(end.at, since):
                group = end.kind
            elif published is not None and since is not None and published > since:
                group = "late"
            else:
                continue
        note = None
        if point == "review" and other_id:
            note = covered.get(f"t{other_id}")
        items.append(Item(group, rel, end, conf, "-", note, published))

    def key(it):
        rank = GROUP_ORDER.index(it.group)
        return (rank, 0 if it.confirmation == "confirmed_impact" else 1, it.rel.other, it.rel.type)
    items.sort(key=key)
    shown = items[:MAX_ITEMS]
    # Locate (and, for a bundled plan, extract) archived plans only for the rows
    # actually shown: filtered-out and capped rows cost no archive read or write.
    for it in shown:
        other_id = store.local_id(it.rel.other)
        if it.end.kind in ("landed", "dropped") and other_id:
            it.plan = archived_plan_path(store.index, other_id, extract_dir)
    return shown, max(0, len(items) - MAX_ITEMS), before


def note_target(store, ref) -> str:
    """The ``/aitask-note`` target for a qualified ref: ``<id>`` for a local task,
    ``<id>|project=<name>`` for another project's (pass ``--project <name>``).

    Relation identity and the ledgers keep the qualified ref; only the writer
    needs the bare id, which is all ``aitask_note.sh`` accepts.
    """
    tid = store.local_id(ref)
    if tid is not None:
        return tid
    project, other = rs.parse_ref(ref)
    return f"{other}|project={project}"


def item_lines(it: Item, store=None) -> list:
    tail = f"|covered_by_note={enc(it.covered_by_note)}" if it.covered_by_note else ""
    rel = it.rel
    return [f"ITEM:{it.group}|{enc(rel.direction)}|{rel.type}|{enc(rel.other)}|{rel.freshness}"
            f"|{it.confirmation}|{enc(it.end.label())}|{enc(it.plan)}{tail}",
            f"  {enc(rel.description)}"] + (
        [f"  NOTE_TARGET:{note_target(store, rel.other)}"] if store is not None else [])


def item_dict(it: Item, store=None) -> dict:
    rel = it.rel
    return {"group": it.group, "direction": rel.direction, "type": rel.type, "other": rel.other,
            "from": rel.from_, "to": rel.to, "freshness": rel.freshness,
            "confirmation": it.confirmation, "end": it.end.label(), "archived_plan": it.plan,
            "covered_by_note": it.covered_by_note, "description": rel.description,
            "published_at": iso(it.published_at) if it.published_at else None,
            "note_target": note_target(store, rel.other) if store is not None else None}


# ============================================================ notify candidates

@dataclasses.dataclass
class Row:
    kind: str            # PUSH | PULL
    rel: object
    recipient: str
    reason: str = ""
    matched: list = dataclasses.field(default_factory=list)
    confirmation: str = "unconfirmed_impact"


def notify_candidates(store, snap, source, cs: ChangeSet, relations_state) -> list:
    """The D8 push rules, in a fixed order; the first failing rule is the PULL reason."""
    me = store.canonical_ref(source)
    rows = []
    for rel in store.relations(me, snap):
        recipient = rel.to if rel.type == "affects" else rel.other
        status, matched = confirm(rel.basis, cs)
        row = Row("PULL", rel, rel.other, matched=matched, confirmation=status)
        if relations_state == "disabled":
            row.reason = "relations_disabled"
        elif rel.type not in PUSH_TYPES:
            row.reason = "type_not_pushed"
        elif rel.type == "affects" and rel.from_ != me:
            row.reason = "reverse_direction"
        elif store.local_id(recipient) is None:
            row.reason = "other_project"
        else:
            end = end_state(store, recipient)
            if end.kind in ("landed", "dropped"):
                row.reason = "target_closed"
            elif status != "confirmed_impact":
                row.reason = "unconfirmed_impact"
            elif end.kind not in ("implementing", "plan_holder"):
                row.reason = "target_state"
            else:
                still = cites_now(store, store.local_id(recipient), matched)
                if not still:
                    row.reason = "target_moved"
                else:
                    keep = {(k, v) for k, v in still}
                    row = Row("PUSH", rel, recipient,
                              matched=[m for m in matched if (m[0], m[1]) in keep],
                              confirmation=status)
        rows.append(row)
    rows.sort(key=lambda r: (0 if r.kind == "PUSH" else 1, r.recipient, r.rel.type))
    return rows


def row_lines(row: Row, store=None) -> list:
    rel = row.rel
    if row.kind == "PUSH":
        bases = ",".join(f"{k}:{v}" for k, v, *_ in row.matched)
        out = [f"PUSH:{enc(row.recipient)}|{rel.type}|{enc(bases)}|{enc(rel.description)}"]
        if store is not None:
            out.append(f"  NOTE_TARGET:{note_target(store, row.recipient)}")
        for kind, value, commit, path in row.matched:
            out.append(f"  EVIDENCE:{kind}:{enc(value)}|{enc(commit)}|{enc(path)}")
        return out
    return [f"PULL:{enc(row.recipient)}|{rel.type}|{row.reason}"]


def row_dict(row: Row, store=None) -> dict:
    rel = row.rel
    return {"kind": row.kind, "to": row.recipient,
            "note_target": note_target(store, row.recipient) if store is not None else None, "type": rel.type, "reason": row.reason or None,
            "from": rel.from_, "relation_to": rel.to, "direction": rel.direction,
            "freshness": rel.freshness, "confirmation": row.confirmation,
            "description": rel.description,
            "evidence": [{"kind": k, "value": v, "commit": c, "file": f}
                         for k, v, c, f in row.matched]}


def ledger_base(store, task_id) -> dict:
    return {"at": iso(now_utc()), "host": socket.gethostname(),
            "task": store.canonical_ref(task_id)}


def read_lock_time(root, tid):
    """The task lock's ``locked_at`` (local time) from the LOCAL lock ref, or None.

    Reads ``refs/remotes/origin/aitask-locks:t<id>_lock.yaml`` as last fetched
    (the claim refreshed it) -- never ``aitask_lock.sh --check``, which fetches.
    A reference time does not need a fresher lock, and the related-work check
    must never pay a network round trip. Never raises.
    """
    name = f"t{rs.norm_id(tid)}_lock.yaml"
    for ref in ("refs/remotes/origin/aitask-locks", "refs/heads/aitask-locks"):
        try:
            proc = ors.git(root, "show", f"{ref}:{name}", check=False)
        except OSError:
            return None
        if proc.returncode != 0:
            continue
        for line in proc.stdout.decode("utf-8", "replace").splitlines():
            if line.startswith("locked_at:"):
                return line.split(":", 1)[1].strip().strip("'\"")
    return None
