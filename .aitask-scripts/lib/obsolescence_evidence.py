#!/usr/bin/env python3
"""obsolescence_evidence.py - static evidence rows for the obsolescence layer (t1981_6).

Design: aidocs/framework/task_relations.md D9 ("Evidence", "Obsolescence API").
Exposed as ``aitask_obsolete.sh evidence <id>``; consumed by the worker's
``obsolescence`` job (``relations_worker.analyse_obsolescence``).

Every row is ``{id, kind, detail, source}`` (the D2 record's closed shape) and is
classified **signal** or **context**:

- signal rows are the scoring inputs: they alone are given to the assessor, are
  citable, are stored in the record, and make up ``evidence_digest``. With no
  signal row the band is ``none`` and no agent runs.
- context rows are for human inspection only (``ait obsolete evidence``): the
  ``age`` prior, a premise reading other than ``ASK_STALE``, a completed origin,
  and EVERY path row. A path row is a factual file event; nothing proves the
  task's current citation means the lifetime that ended, so it never asserts
  obsolescence (attribution is a deferred follow-up).

Invariant: scoring inputs = digest inputs = signal rows. A context row that
reached the prompt could shape a recommendation its later change would never
invalidate (UP_TO_DATE and dismissals key on the digest).

Incomplete evidence is never an all-clear: anything that could not be read is
reported in ``incomplete``, and the worker fails the job instead of writing
``none``.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import bounded_run  # noqa: E402
import followup_origin  # noqa: E402
import plan_paths  # noqa: E402
import relations_consume as rc  # noqa: E402
import relations_schema as rs  # noqa: E402
from task_yaml import parse_frontmatter  # noqa: E402

SCRIPTS = os.path.dirname(_LIB)
PREMISE_SCRIPT = os.path.join(SCRIPTS, "aitask_premise_stale.sh")
PREMISE_TIMEOUT_S = 60
HISTORY_TIMEOUT_S = 60
CACHE_SUBDIR = os.path.join(".aitask-cache", "obsolescence")
DESCRIPTION_CAP = 200

SIGNAL_RELATION_KINDS = ("superseded_by", "duplicate_of", "affected_by_landed")
PATH_KINDS = ("path_deleted", "path_renamed", "path_ambiguous")
DATA_PREFIXES = ("aitasks/", "aiplans/")


@dataclasses.dataclass
class Row:
    kind: str
    detail: str
    source: str
    signal: bool
    id: str = ""

    def as_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "detail": self.detail, "source": self.source}


@dataclasses.dataclass
class EvidenceResult:
    rows: list            # every Row, ids assigned, signal rows first
    incomplete: list      # reasons the evidence could not be fully collected
    digest: str           # evidence_digest over the signal rows only

    def signal_rows(self) -> list:
        return [r.as_dict() for r in self.rows if r.signal]

    @property
    def signal_count(self) -> int:
        return sum(1 for r in self.rows if r.signal)


def digest(rows) -> str:
    """``evidence_digest``: sha256 over the sorted signal ``(kind, detail, source)``.

    Ids are excluded (they are positional), and so is every context row.
    """
    triples = sorted([r.kind, r.detail, r.source] for r in rows if r.signal)
    return hashlib.sha256(json.dumps(triples, ensure_ascii=False).encode("utf-8")).hexdigest()


def _assign_ids(rows) -> list:
    # Signal rows first, so a signal row's id never depends on context rows
    # (origin_state can be either class).
    rows = sorted(rows, key=lambda r: (0 if r.signal else 1, r.kind, r.detail, r.source))
    counts: dict = {}
    for r in rows:
        counts[r.kind] = counts.get(r.kind, 0) + 1
        r.id = f"{r.kind}:{counts[r.kind]}"
    return rows


# =================================================================== metadata

def _meta(text):
    try:
        parsed = parse_frontmatter(text or "")
    except Exception:
        return None
    if not parsed or not isinstance(parsed[0], dict):
        return None
    return parsed[0]


_REVERT_FIELD = re.compile(r"^\s*[-*]\s*\*\*(.+?):\*\*\s*(.*?)\s*$")
_REVERT_KEYS = {"reverted by": "reverted_by", "date": "date", "type": "type",
                "areas reverted": "areas_reverted", "areas kept": "areas_kept"}


def parse_revert_notes(text) -> list:
    """Every ``## Revert Notes`` section (the aitask-revert template) as a dict.

    Keys: ``reverted_by``, ``date``, ``type`` (first word: ``Complete`` /
    ``Partial``), ``areas_reverted``, ``areas_kept``; a field the section does
    not carry is absent. Extra text after the type ("Complete (all changes ...)")
    is tolerated.
    """
    out, cur = [], None
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        if line.startswith("## "):
            if cur is not None:
                out.append(cur)
            cur = {} if line.rstrip() == "## Revert Notes" else None
            continue
        if cur is None:
            continue
        m = _REVERT_FIELD.match(line)
        if not m:
            continue
        key = _REVERT_KEYS.get(m.group(1).strip().lower())
        if key is None:
            continue
        value = m.group(2).strip()
        if key == "type":
            value = value.split()[0] if value.split() else ""
        cur[key] = value
    if cur is not None:
        out.append(cur)
    return out


def _revert_detail(tid, note) -> str:
    kind = note.get("type") or "unknown type"
    by = note.get("reverted_by") or "unknown"
    when = note.get("date") or "unknown date"
    return f"t{tid} reverted ({kind}) by {by} on {when}"


# ================================================================ path history

@dataclasses.dataclass
class Event:
    seq: int          # ascending oldest -> newest
    sha: str
    ct: int
    status: str       # A | D | R
    src: str | None
    dst: str | None


class HistoryError(Exception):
    pass


def parse_log_z(raw: str) -> list:
    """Events (oldest first) from ``git log --topo-order -M --name-status
    --diff-filter=ADR -z --format=%x00C%H%x00%ct``."""
    toks = raw.split("\0")
    commits, i, cur = [], 0, None
    expect_header = True
    while i < len(toks):
        tok = toks[i]
        if tok == "":
            expect_header = True
            i += 1
            continue
        if expect_header:
            if not tok.startswith("C") or i + 1 >= len(toks):
                raise HistoryError(f"unexpected token {tok[:40]!r}")
            sha, ct = tok[1:], toks[i + 1]
            if not re.fullmatch(r"[0-9a-f]{40,64}", sha) or not ct.isdigit():
                raise HistoryError(f"bad commit header {tok[:40]!r}")
            cur = {"sha": sha, "ct": int(ct), "changes": []}
            commits.append(cur)
            expect_header = False
            i += 2
            continue
        status = tok.lstrip("\n")
        if status[:1] in ("A", "D") and len(status) == 1:
            if i + 1 >= len(toks):
                raise HistoryError("truncated change")
            cur["changes"].append((status, toks[i + 1], None))
            i += 2
        elif status[:1] == "R" and status[1:].isdigit():
            if i + 2 >= len(toks):
                raise HistoryError("truncated rename")
            cur["changes"].append(("R", toks[i + 1], toks[i + 2]))
            i += 3
        else:
            raise HistoryError(f"unknown status {status[:20]!r}")
    events = []
    seq = 0
    for commit in reversed(commits):  # git prints newest first
        for status, a, b in commit["changes"]:
            if status == "A":
                events.append(Event(seq, commit["sha"], commit["ct"], "A", None, a))
            elif status == "D":
                events.append(Event(seq, commit["sha"], commit["ct"], "D", a, None))
            else:
                events.append(Event(seq, commit["sha"], commit["ct"], "R", a, b))
            seq += 1
    return events


class History:
    """Seq-ordered additions / removals per path (one HEAD)."""

    def __init__(self, events):
        self.events = events
        self.additions: dict = {}
        self.removals: dict = {}
        for ev in events:
            if ev.status in ("A", "R"):
                self.additions.setdefault(ev.dst, []).append(ev)
            if ev.status in ("D", "R"):
                self.removals.setdefault(ev.src, []).append(ev)

    def removed_paths(self):
        return self.removals.keys()


def _git(root, *args, timeout=HISTORY_TIMEOUT_S):
    return bounded_run.run_bounded(["git", "-C", str(root), *args], timeout)


def load_history(root) -> History:
    """The HEAD's ordered history, cached at ``.aitask-cache/obsolescence/history-<HEAD>.json``."""
    res = _git(root, "rev-parse", "--verify", "HEAD")
    if res.returncode != 0:
        raise HistoryError("no HEAD")
    head = res.stdout.strip()
    cache_dir = Path(root, CACHE_SUBDIR)
    cache = cache_dir / f"history-{head}.json"
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("head") == head:
            return History([Event(**e) for e in data["events"]])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    res = _git(root, "log", "--topo-order", "-M", "--name-status", "--diff-filter=ADR", "-z",
               "--format=%x00C%H%x00%ct", "HEAD")
    if res.returncode != 0:
        raise HistoryError(f"git log exit {res.returncode}")
    events = parse_log_z(res.stdout)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_name(f"{cache.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"head": head, "events": [dataclasses.asdict(e) for e in events]}),
                       encoding="utf-8")
        os.replace(tmp, cache)
        for old in cache_dir.glob("history-*.json"):
            if old != cache:
                try:
                    old.unlink()
                except OSError:
                    pass
    except OSError:
        pass  # the cache is an optimisation, never the authority
    return History(events)


def _date(ct) -> str:
    return _dt.datetime.fromtimestamp(ct, _dt.timezone.utc).strftime("%Y-%m-%d")


def path_fact(token, hist: History, tracked: set):
    """``(kind, detail)`` for an untracked cited path with history, or None.

    Reports how the name's LATEST lifetime ended, following renames forward in
    sequence only (a reused intermediate name never splices an older chain).
    """
    removals = hist.removals.get(token, [])
    if not removals:
        return None  # planned-new or phantom: never existed under this name
    last = removals[-1]
    lifetimes = len(removals)
    if any(a.seq > last.seq for a in hist.additions.get(token, [])):
        return ("path_ambiguous", f"{token}: re-added after its last removal yet absent at HEAD "
                                  f"(lifetimes={lifetimes})")
    chain = [token]
    ev = last
    seen = set()
    while True:
        if ev.status == "D":
            return ("path_deleted", f"{' -> '.join(chain)} deleted in {ev.sha[:12]} {_date(ev.ct)} "
                                    f"(lifetimes={lifetimes})")
        nxt, seq = ev.dst, ev.seq
        if (nxt, seq) in seen:
            return ("path_ambiguous", f"{' -> '.join(chain)}: rename cycle (lifetimes={lifetimes})")
        seen.add((nxt, seq))
        chain.append(nxt)
        later = [r for r in hist.removals.get(nxt, []) if r.seq > seq]
        if not later:
            if nxt in tracked:
                return ("path_renamed", f"{' -> '.join(chain)} (renamed in {ev.sha[:12]} {_date(ev.ct)}; "
                                        f"lifetimes={lifetimes})")
            return ("path_ambiguous", f"{' -> '.join(chain)}: rename target neither tracked nor removed "
                                      f"(lifetimes={lifetimes})")
        ev = later[0]


def path_rows(root, body, plan, incomplete) -> list:
    tokens = set()
    for text in (body, plan):
        if text:
            tokens.update(plan_paths.extract(text))
    cands = []
    for tok in sorted(tokens):
        tok = tok[2:] if tok.startswith("./") else tok
        if plan_paths.is_malformed(tok) or "/" not in tok.strip("/") or tok.startswith(DATA_PREFIXES):
            continue
        cands.append(tok)
    if not cands:
        return []
    try:
        tracked, _dirs = plan_paths.tracked_sets(root)
    except (subprocess.SubprocessError, OSError) as exc:
        incomplete.append(f"tracked_files_unavailable:{exc.__class__.__name__}")
        return []
    untracked = []
    for tok in cands:
        if tok in tracked:
            continue
        suffix = "/" + tok
        if any(p.endswith(suffix) for p in tracked):
            continue  # a relative reference to a file that exists
        untracked.append(tok)
    if not untracked:
        return []
    try:
        hist = load_history(root)
    except (HistoryError, subprocess.SubprocessError, OSError) as exc:
        incomplete.append(f"path_history_unavailable:{exc}"[:120])
        return []
    rows = []
    removed = list(hist.removed_paths())
    for tok in untracked:
        name = tok
        if name not in hist.removals:
            matches = sorted(p for p in removed if p.endswith("/" + tok))
            if len(matches) > 1:
                rows.append(Row("path_ambiguous",
                                f"{tok}: suffix of several removed paths ({', '.join(matches[:5])})",
                                "git log -M HEAD", False))
                continue
            if not matches:
                continue
            name = matches[0]
        fact = path_fact(name, hist, tracked)
        if fact is None:
            continue
        kind, detail = fact
        if name != tok:
            detail = f"{tok} (= {detail})"
        rows.append(Row(kind, detail, "git log -M HEAD", False))
    return rows


# ==================================================================== origins

def origin_rows(store, tid, meta, incomplete) -> list:
    result = followup_origin.resolve_detailed(meta or {})
    if result["residue"]:
        incomplete.append("origin_malformed:" + ",".join(str(t) for t in result["residue"])[:80])
    field = {"exact": "verifies", "topic": "anchor"}.get(result["quality"], "origin")
    claimed = [(o, f"frontmatter:{field}") for o in result["origins"]]
    claimed += [(o, "frontmatter:verifies(degraded)") for o in result["degraded_origins"]]
    rows, me = [], rs.norm_id(tid)
    for oid, source in claimed:
        oid = rs.norm_id(oid)
        if oid == me:
            continue
        entry = store.index.lookup(oid)
        if entry is None:
            exists = store.index.exists(oid)
            if exists is None:
                incomplete.append(f"origin_unreadable:t{oid}")
            elif exists is False:
                rows.append(Row("origin_state", f"t{oid} deleted", source, True))
            else:
                rows.append(Row("origin_state", f"t{oid} folded into t{store.index.canonical(oid)}",
                                source, True))
            continue
        if entry.text is None:
            incomplete.append(f"origin_unreadable:t{oid}")
            continue
        notes = parse_revert_notes(entry.text)
        if notes:
            rows.append(Row("origin_state", _revert_detail(oid, notes[-1]), source, True))
            continue
        if entry.folded_into:
            rows.append(Row("origin_state", f"t{oid} folded into t{entry.folded_into}", source, True))
            continue
        if entry.location != "active":
            ometa = _meta(entry.text) or {}
            reason = ometa.get("archived_reason")
            status = str(ometa.get("status") or entry.status or "")
            if reason:
                rows.append(Row("origin_state", f"t{oid} archived:{reason}", source, True))
            elif status == "Done":
                when = ometa.get("completed_at") or ometa.get("updated_at") or "unknown"
                rows.append(Row("origin_state", f"t{oid} archived:completed@{when}", source, False))
            else:
                rows.append(Row("origin_state", f"t{oid} archived:{status.lower() or 'unknown'}",
                                source, True))
    return rows


# ================================================================== relations

def snapshot_incomplete(snap) -> list:
    """Reasons the store snapshot cannot vouch for "no relation rows".

    ``Store.read`` leaves corrupt records out of ``files`` (reported in
    ``corrupt``), and an ``unreachable`` store holds no data at all: either way a
    missing ``superseded_by`` / ``duplicate_of`` row would be read as an
    all-clear. An empty store (fetched, nothing written), a local-only store and
    the latest-known store after a failed fetch (``stale:``) do vouch for it.
    """
    out = [f"store_corrupt:{c.split('|', 1)[0]}" for c in (snap.corrupt or [])]
    if str(snap.state).startswith("unreachable"):
        out.append(f"store_{snap.state}")
    return out


def relation_rows(store, snap, tid, created_at) -> list:
    me = store.canonical_ref(tid)
    created = rc.parse_time(created_at) if created_at else None
    rows = []
    for rel in store.relations(me, snap):
        other = rel.other
        kind = None
        if rel.type == "supersedes" and rel.from_ == other:
            kind = "superseded_by"
        elif rel.type == "duplicates":
            kind = "duplicate_of"
        end = rc.end_state(store, other)
        if rel.type == "affects" and rel.from_ == other and end.kind == "landed":
            if created is not None and end.at is not None and end.at > created:
                kind = "affected_by_landed"
        if kind is None:
            continue
        rec_id = store.local_id(rel.record_task)
        source = f"store:records/t{rec_id}.json" if rec_id else f"store:{rel.record_task}"
        desc = " ".join(rel.description.split())[:DESCRIPTION_CAP]
        rows.append(Row(kind, f"{other} ({end.label()}, {rel.freshness}): {desc}", source, True))
    return rows


# ==================================================================== premise

def _premise_cmd():
    seam = os.environ.get("AIT_OBSOLESCENCE_PREMISE_CMD")
    if seam:
        return shlex.split(seam)
    if not os.path.exists(PREMISE_SCRIPT):
        return None
    return [PREMISE_SCRIPT, "check"]


def premise_row(root, task_file, incomplete):
    cmd = _premise_cmd()
    if cmd is None:
        return Row("premise", "unavailable", "aitask_premise_stale.sh", False)
    try:
        res = bounded_run.run_bounded(cmd + [str(task_file)], PREMISE_TIMEOUT_S, cwd=str(root))
    except subprocess.TimeoutExpired:
        incomplete.append("premise_timeout")
        return None
    except OSError as exc:
        incomplete.append(f"premise_error:{exc.__class__.__name__}")
        return None
    lines = res.stdout.splitlines()
    decision = next((ln.split(":", 1)[1].strip() for ln in reversed(lines)
                     if ln.startswith("DECISION:")), None)
    if res.returncode != 0 or decision not in ("FRESH", "ASK_STALE", "SKIP"):
        incomplete.append(f"premise_failed:exit_{res.returncode}")
        return None
    display = next((ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("DISPLAY:")), "")
    return Row("premise", f"{decision}: {display}".rstrip(": "), "aitask_premise_stale.sh check",
               decision == "ASK_STALE")


# ======================================================================== age

def age_row(meta, now=None):
    now = now or _dt.datetime.now(_dt.timezone.utc)
    for key in ("updated_at", "created_at"):
        ts = rc.parse_time(meta.get(key)) if meta and meta.get(key) is not None else None
        if ts is not None:
            days = max(0, (now - ts).days)
            return Row("age", f"{days} days since {key} {meta.get(key)} (weak prior)",
                       f"frontmatter:{key}", False)
    return None


# ================================================================== collector

def active_task_file(root, tid):
    tid = rs.norm_id(tid)
    task_dir = Path(root, os.environ.get("TASK_DIR", "aitasks"))
    if "_" in tid:
        parent = tid.split("_", 1)[0]
        matches = sorted((task_dir / f"t{parent}").glob(f"t{tid}_*.md"))
    else:
        matches = sorted(p for p in task_dir.glob(f"t{tid}_*.md")
                         if re.match(rf"^t{tid}_(?!\d+_)", p.name))
    return matches[0] if matches else None


def collect(root, store, snap, tid, body_raw, plan_raw, *, now=None) -> EvidenceResult:
    """All evidence rows of ``tid``.

    ``body_raw`` is the task file text, ``plan_raw`` the plan text under the D5
    rule (the stamp's plan for a stamped task), or None.
    """
    tid = rs.norm_id(tid)
    incomplete: list = []
    meta = _meta(body_raw)
    if meta is None:
        incomplete.append("frontmatter_unreadable")
        meta = {}
    rows = []
    body = rs.normalize_body(body_raw) if body_raw is not None else ""
    plan = rs.normalize_plan(plan_raw) if plan_raw is not None else ""
    rows += path_rows(root, body, plan, incomplete)
    rows += origin_rows(store, tid, meta, incomplete)
    snap_gaps = snapshot_incomplete(snap)
    incomplete += snap_gaps
    if not snap_gaps:
        rows += relation_rows(store, snap, tid, meta.get("created_at"))
    task_file = active_task_file(root, tid)
    if task_file is not None:
        prem = premise_row(root, task_file, incomplete)
        if prem is not None:
            rows.append(prem)
    age = age_row(meta, now)
    if age is not None:
        rows.append(age)
    rows = _assign_ids(rows)
    return EvidenceResult(rows=rows, incomplete=incomplete, digest=digest(rows))
