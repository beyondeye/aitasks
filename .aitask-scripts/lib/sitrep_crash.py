#!/usr/bin/env python3
"""sitrep_crash.py - the sitrep crash detector (t2299_2).

Finds tasks whose agent is gone, records the evidence about each one, and
keeps ONE recovery item per task (`kind=task`, `ref=recover:t<N>`) through the
store writer's atomic `recovery-apply` verb (t2299_1). Driven by
`aitask_sitrep_harvest.sh crashed`; t2299_3 wires it into refresh, the monitor
tick and the TUI.

ADVISORY ONLY. Nothing here reclaims, unlocks, edits task status or types into
a pane. Helpers report evidence; the agent (and the user) judge.

THE ONE ORDERED DECISION TABLE (`recovery_verdict`; refresh shares it). The
first matching row wins, and lock evidence comes before task completion:

  1  any input for the task is unreadable   -> no write: CRASH_WARN only, the
                                               existing item byte-identical
  2  lock on another host / host `unknown`  -> other_host (skip); item unknown
  3  lock holder alive                      -> alive (skip);      item done
  4  lock holder unknown (numeric pid)      -> unknown (skip);    item unknown
  5  lock without a PID anchor              -> stale_lock (stored)
  6  holder dead, task Implementing         -> crashed (stored)
  7  holder dead, task not Implementing /
     archived / Done / folded / missing     -> stale_lock (stored)
  8  no lock, task Implementing             -> orphan (stored)
  9  no lock, any other status / archived /
     folded / missing                       -> none;              item done

Row 1 is STRICTER than the task file's table (which marked an existing item
`unknown`): an unreadable input says nothing about the task, so it never
writes. The host guard runs before the no-anchor check and before any `dead`
verdict, and `unknown` is never rounded up to `crashed`.

EPISODE KEY (the context origin `incarnation=<12 hex>`, written only through
`recovery-apply`). A new key is minted only from a lock that represents a
claim: an anchored lock hashes task_id, hostname, pid, pid_starttime,
pid_starttime_kind (NOT locked_at, so a session refreshing its own lock keeps
its key); an unanchored one hashes task_id, locked_by, hostname, locked_at; no
lock carries the item's recorded key forward (a brand-new item: `nolock`).

STRICT INPUTS. Locks come from `refs/remotes/origin/aitask-locks`, else the
local `aitask-locks` (never fetched), read with ONE `ls-tree --full-tree` and
ONE `cat-file --batch`. A file absent from the tree is the only route to "no
lock". A malformed blob, an unreadable task file (active OR archived, loose
or bundled), unparseable frontmatter or a missing/invalid `status:` is a
per-task error (row 1). An unreadable ref, tree or task directory fails the
whole pass with no writes.

EVIDENCE. Source-tagged and advisory. Shared-tree work is attributed to a task
only when its plan or task text names the path; ownership matching runs over
tracked AND dirty paths (`--untracked-files=all`, so a crashed task's new file
counts), commit history only over tracked ones, and task/plan data
(`aitasks/`, `aiplans/`) is excluded as `gate_ledger.code_digest` excludes it.
A failed `ls-files` / `status` ends the pass before any write; an unreadable
plan makes its own task warn (no write) and another task's overlap evidence
`?`. Unattributed shared-tree edits and unread evidence still raise the tree
warning, without being attributed to anyone.

IDEMPOTENCE. Stored evidence holds only time-invariant facts: `locked_at` is
absolute and `lock_age` is a coarse bucket (<1h, 1h-1d, 1d-7d, >7d) against the
clock seam AITASK_SITREP_NOW. Before any retain or apply, the proposed item
fields and context entry (with retain pointers derived locally, the way
`retain` names them) are compared with the recorded ones; equal => nothing is
written and the result is `unchanged`. So a recover item's `checked_at` means
"evidence last changed", not "last scanned"; the pass's final line is the scan
record.

TEST SEAMS (test-only). AITASK_SITREP_CRASH_FAULT=<point> (before_apply,
after_retain) fails the pass at that point. AITASK_SITREP_CRASH_PAUSE_FIFO: at
`before_apply` the pass writes the point name to `<fifo>.reached`, then blocks
reading one line from the fifo. AITASK_SITREP_NOW pins the clock.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if __name__ == "__main__":
    sys.modules.setdefault("sitrep_crash", sys.modules[__name__])

import agent_sessions  # noqa: E402
import archive_iter  # noqa: E402
import gate_ledger as gl  # noqa: E402
import parallel_admission_collect as pac  # noqa: E402
import sitrep_harvest as sh  # noqa: E402
import sitrep_refresh  # noqa: E402
import sitrep_todo as st  # noqa: E402
import task_yaml  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKTREE_SH = os.path.join(SCRIPTS_DIR, "aitask_task_worktree.sh")

LOCK_REFS = ("refs/remotes/origin/aitask-locks", "refs/heads/aitask-locks")
LOCK_FILE_RE = re.compile(r"^t([1-9][0-9]*(?:_[1-9][0-9]*)?)_lock\.yaml\Z")
TASK_ID_RE = re.compile(r"^t?([1-9][0-9]*(?:_[1-9][0-9]*)?)\Z")
PARENT_FILE_RE = re.compile(r"^t([1-9][0-9]*)_.*\.md\Z")
CHILD_FILE_RE = re.compile(r"^t([1-9][0-9]*)_([1-9][0-9]*)_.*\.md\Z")
CHILD_DIR_RE = re.compile(r"^t([1-9][0-9]*)\Z")
PID_RE = re.compile(r"^[0-9]+\Z")
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
LINE_SUFFIX_RE = re.compile(r"(?::[0-9]+(?:-[0-9]+)?|#L[0-9]+(?:-L?[0-9]+)?)\Z")
VALID_STATUSES = sitrep_refresh.VALID_STATUSES
STORED = ("crashed", "orphan", "stale_lock")
SKIP_ROWS = (2, 3, 4)

GIT_TIMEOUT = 20
# Task and plan data are not code work (they churn with every claim and note):
# the same pathspec excludes `gate_ledger.code_digest` applies.
DATA_EXCLUDES = (":(exclude)aitasks/**", ":(exclude)aiplans/**", ":(exclude).aitask-data/**")
CAPTURE_TAIL_LINES = 200
CAPTURE_TAIL_BYTES = 32 * 1024
MAX_COMMIT_SOURCES = 5
COMMIT_SCAN_LIMIT = 50

SURVEY_HEADER = "SITREP_RECOVERY_SURVEY v1"
SURVIVOR_WARNING = "surviving work - do not git restore / git stash / checkout the tree"
UNATTRIBUTED_WARNING = ("unattributed shared-tree edits (owner unknown) - do not git restore "
                        "/ git stash / checkout the tree")
INCOMPLETE_WARNING = ("evidence incomplete ({what}) - do not git restore / git stash / "
                      "checkout the tree")

BACKGROUND = {
    "crashed": ("The agent holding this task's lock is gone (its PID anchor is dead "
                "on this host) while the task is Implementing; its work may "
                "survive in the tree."),
    "orphan": ("This task is Implementing but no lock holds it; the session that "
               "claimed it left no lock behind."),
    "stale_lock": ("A lock remains for this task: either it records no PID "
                   "anchor, so whether its holder still runs cannot be checked, "
                   "or its holder is gone and the task is no longer "
                   "Implementing. Check who holds it before releasing it."),
}

# Test hooks (module level so the unit tests can drive the table directly).
_LIVENESS = pac.lock_holder_liveness
_LOCAL_HOST = None      # None => platform.node(), the same rule as pac._local_host


class SourceError(Exception):
    """A whole-pass input failure: CRASH_FAILED, nothing written."""


class CrashFailure(Exception):
    """A failure that ends the pass (CRASH_FAILED:<reason>)."""


# --- records -----------------------------------------------------------------

@dataclass
class LockRec:
    id: str
    fields: dict = field(default_factory=dict)
    state: str = "ok"           # ok | error
    why: str = ""


@dataclass
class TaskRec:
    id: str
    where: str                  # active | archived | fold_scan | missing | error
    status: str = ""
    path: str = ""              # absolute path of an active file
    rel: str = ""               # repo-relative pointer for a `task:` source
    stem: str = ""              # filename stem (t<N>_<slug>), the worktree task name
    slug: str = ""
    folded: bool = False
    meta: dict = field(default_factory=dict)
    text: str = ""
    why: str = ""

    @property
    def implementing(self) -> bool:
        return self.where == "active" and self.status == "Implementing" and not self.folded


@dataclass
class Verdict:
    row: int
    category: str               # stored category, or the label of a non-stored row
    stored: bool
    item_state: str             # target state of an existing item ("" = no write)
    evidence: str

    @property
    def outcome(self) -> str:
        return format_outcome(self.category, self.evidence)


# --- small helpers -----------------------------------------------------------

def _bare(tid) -> str:
    return str(tid).strip().lstrip("t")


def id_key(tid: str) -> tuple:
    parts = _bare(tid).split("_")
    return tuple(int(p) for p in parts)


def _git(root: str, *args: str, data: bytes | None = None, timeout: int = GIT_TIMEOUT):
    """(rc, stdout bytes). rc 124 on a timeout, 127 when git cannot spawn."""
    try:
        p = subprocess.run(["git", "-C", root, *args], input=data, capture_output=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, b""
    except OSError:
        return 127, b""
    return p.returncode, p.stdout


def _git_text(root: str, *args: str) -> tuple:
    rc, out = _git(root, *args)
    return rc, out.decode("utf-8", "replace")


def _one_line(s: str) -> str:
    return re.sub(r"[\r\n]+", " ", s).replace("|", "/").strip()


def format_outcome(label: str, evidence: str) -> str:
    """`<label> · <short evidence>`, one line, no `|`, at most MAX_OUTCOME."""
    text = f"{label} · {_one_line(evidence)}" if evidence else label
    text = _one_line(text)
    if len(text) > st.MAX_OUTCOME:
        text = text[: st.MAX_OUTCOME - 1].rstrip() + "…"
    return text


def parse_outcome(text: str) -> tuple:
    """(label, evidence) of a format_outcome string; display only."""
    label, sep, evidence = (text or "").partition(" · ")
    return label, evidence if sep else ""


def now_utc() -> datetime:
    pinned = os.environ.get("AITASK_SITREP_NOW", "")
    if st.TS_RE.match(pinned):
        return datetime.strptime(pinned, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def parse_locked_at(value: str):
    """A lock's `locked_at` (`aitask_lock.sh get_timestamp`: local wall clock,
    `%Y-%m-%d %H:%M`) as an aware datetime, or None."""
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d %H:%M").astimezone()
    except ValueError:
        return None


def age_bucket(locked_at: str, now: datetime) -> str:
    when = parse_locked_at(locked_at)
    if when is None:
        return "unknown"
    secs = (now - when).total_seconds()
    if secs < 3600:
        return "<1h"
    if secs < 86400:
        return "1h-1d"
    if secs < 7 * 86400:
        return "1d-7d"
    return ">7d"


def retain_pointer(data: bytes) -> str:
    """The pointer `aitask_sitrep_todo.sh retain` returns for `data`."""
    n = data.count(b"\n") + (0 if data.endswith(b"\n") else 1)
    return f"sources/{sh.hex16(data)}.txt#L1-L{n}"


def fault_point(point: str) -> None:
    if os.environ.get("AITASK_SITREP_CRASH_FAULT", "") == point:
        raise CrashFailure(f"fault:{point}")


def pause_point(point: str) -> None:
    fifo = os.environ.get("AITASK_SITREP_CRASH_PAUSE_FIFO", "")
    if not fifo:
        return
    with open(fifo + ".reached", "w", encoding="utf-8") as fh:
        fh.write(point + "\n")
    # One byte at a time, like the shell seams' `read -r`: a buffered readline
    # would swallow the lines meant for the NEXT pause and block it forever.
    fd = os.open(fifo, os.O_RDONLY)
    try:
        while os.read(fd, 1) not in (b"\n", b""):
            pass
    finally:
        os.close(fd)


# --- strict lock reader ------------------------------------------------------

def resolve_lock_ref(root: str) -> str:
    for ref in LOCK_REFS:
        rc, out = _git(root, "rev-parse", "--verify", "-q", ref + "^{commit}")
        if rc == 0 and out.strip():
            return ref
        if rc != 1:
            raise SourceError(f"lock_ref_unreadable:{ref}")
    raise SourceError("no_lock_ref")


def parse_lock_blob(name_id: str, data: bytes) -> LockRec:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return LockRec(name_id, state="error", why="lock is not UTF-8")
    fields = {}
    for ln in text.splitlines():
        if not ln.strip():
            continue
        k, sep, v = ln.partition(":")
        k = k.strip()
        if not sep or not k:
            return LockRec(name_id, state="error", why="malformed lock line")
        if k in fields:
            return LockRec(name_id, state="error", why=f"duplicate lock key {k}")
        fields[k] = v.strip()
    if not fields.get("task_id") or not fields.get("hostname"):
        return LockRec(name_id, fields, "error", "lock has no task_id or hostname")
    if _bare(fields["task_id"]) != name_id:
        return LockRec(name_id, fields, "error",
                       f"lock task_id {fields['task_id']} does not match its file")
    return LockRec(name_id, fields)


def read_locks(root: str) -> dict:
    """{task id: LockRec}. Raises SourceError when the ref or tree is unreadable."""
    ref = resolve_lock_ref(root)
    # --full-tree: ls-tree is cwd-relative otherwise, and an empty listing from
    # a subdirectory would read as "no locks" -- a silent false all-clear.
    rc, out = _git(root, "ls-tree", "-z", "--full-tree", ref)
    if rc != 0:
        raise SourceError("lock_tree_unreadable")
    wanted = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, tab, name = rec.partition(b"\t")
        parts = meta.split(b" ")
        if not tab or len(parts) != 3:
            raise SourceError("lock_tree_unparseable")
        name_s = name.decode("utf-8", "replace")
        m = LOCK_FILE_RE.match(name_s)
        if parts[1] != b"blob" or not m:
            continue
        wanted.append((m.group(1), parts[2].decode("ascii", "replace")))
    locks = {}
    if not wanted:
        return locks
    data = "".join(oid + "\n" for _, oid in wanted).encode("ascii")
    rc, out = _git(root, "cat-file", "--batch", data=data, timeout=60)
    if rc != 0:
        raise SourceError("lock_blobs_unreadable")
    pos = 0
    for tid, oid in wanted:
        nl = out.find(b"\n", pos)
        if nl < 0:
            locks[tid] = LockRec(tid, state="error", why="lock blob missing from batch")
            pos = len(out)
            continue
        header = out[pos:nl].decode("ascii", "replace").split(" ")
        if len(header) == 3 and header[0] == oid and header[1] == "blob" \
                and header[2].isdigit():
            size = int(header[2])
            body = out[nl + 1: nl + 1 + size]
            if len(body) != size or out[nl + 1 + size: nl + 2 + size] != b"\n":
                locks[tid] = LockRec(tid, state="error", why="lock blob truncated")
                pos = len(out)
                continue
            locks[tid] = parse_lock_blob(tid, body)
            pos = nl + 2 + size
        else:
            locks[tid] = LockRec(tid, state="error", why="lock blob unreadable")
            pos = nl + 1
    return locks


# --- strict task reader ------------------------------------------------------

def strict_meta(name: str, text: str) -> tuple:
    """(meta, why). `why` non-empty => the record is unreadable (row 1)."""
    try:
        parsed = task_yaml.parse_frontmatter(text)
    except Exception as exc:  # noqa: BLE001 - any YAML failure is "unreadable"
        return {}, f"{name}: unparseable frontmatter ({type(exc).__name__})"
    if parsed is None or not isinstance(parsed[0], dict):
        return {}, f"{name}: no frontmatter"
    meta = parsed[0]
    why = sitrep_refresh.status_problem(meta)
    if why:
        return meta, f"{name}: {why}"
    return meta, ""


def _record(tid: str, where: str, name: str, rel: str, path: str, text: str) -> TaskRec:
    meta, why = strict_meta(name, text)
    stem = name[:-3] if name.endswith(".md") else name
    prefix = f"t{tid}_"
    slug = stem[len(prefix):] if stem.startswith(prefix) else stem
    if why:
        return TaskRec(tid, "error", path=path, rel=rel, stem=stem, slug=slug, why=why)
    status = meta["status"].strip()
    fi = meta.get("folded_into")
    folded = status == "Folded" or fi not in (None, "")
    return TaskRec(tid, where, status=status, path=path, rel=rel, stem=stem, slug=slug,
                   folded=folded, meta=meta, text=text)


def _read_active(root: str, tid: str, path: str) -> TaskRec:
    name = os.path.basename(path)
    rel = os.path.relpath(path, root)
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return TaskRec(tid, "error", path=path, rel=rel, why=f"{name}: {exc}")
    return _record(tid, "active", name, rel, path, text)


def _scan(path: str) -> list:
    try:
        with os.scandir(path) as it:
            return sorted(it, key=lambda e: e.name)
    except OSError as exc:
        raise SourceError(f"task_dir_unreadable:{os.path.basename(path)}:"
                          f"{exc.strerror or exc}") from None


def read_active_tasks(root: str) -> dict:
    """{task id: TaskRec} for every active task file. Raises SourceError when a
    task directory cannot be listed."""
    base = os.path.join(root, "aitasks")
    found = {}
    dupes = set()

    def add(tid, path):
        if tid in found:
            dupes.add(tid)
            return
        found[tid] = path

    for e in _scan(base):
        if CHILD_FILE_RE.match(e.name):
            continue
        m = PARENT_FILE_RE.match(e.name)
        if m and e.is_file():
            add(m.group(1), e.path)
        elif CHILD_DIR_RE.match(e.name) and e.is_dir():
            for c in _scan(e.path):
                cm = CHILD_FILE_RE.match(c.name)
                if cm and cm.group(1) == e.name[1:] and c.is_file():
                    add(f"{cm.group(1)}_{cm.group(2)}", c.path)
    out = {}
    for tid, path in found.items():
        if tid in dupes:
            out[tid] = TaskRec(tid, "error", path=path,
                               why=f"t{tid}: more than one active task file")
        else:
            out[tid] = _read_active(root, tid, path)
    return out


def read_inactive_task(root: str, tid: str, index) -> TaskRec:
    """A task with no active file: archived (loose or bundled, validated like
    an active file), folded by a receiver's `folded_tasks`, missing, or error."""
    errs: list = []
    archived = Path(root) / "aitasks" / "archived"
    try:
        found = archive_iter.find_archived_markdown_by_id(tid, archived, errors=errs)
    except Exception as exc:  # noqa: BLE001 - an archive read failure is not absence
        return TaskRec(tid, "error", why=f"archive: {exc}")
    if errs:
        return TaskRec(tid, "error", why=f"archive: {errs[0]}")
    if found is not None:
        name, text = found
        if "_" in tid:
            loose = os.path.join("aitasks", "archived", f"t{tid.split('_', 1)[0]}", name)
        else:
            loose = os.path.join("aitasks", "archived", name)
        rel = loose if os.path.isfile(os.path.join(root, loose)) else ""
        return _record(tid, "archived", name, rel, "", text)
    facts = index.lookup(tid)
    if facts.found == "fold_scan":
        return TaskRec(tid, "fold_scan", status="Folded", folded=True)
    if facts.found == "missing":
        return TaskRec(tid, "missing")
    if facts.found == "error":
        return TaskRec(tid, "error", why=facts.detail or "task lookup failed")
    return TaskRec(tid, "error", why="archive_changed_during_read")


# --- classification ----------------------------------------------------------

def local_host() -> str:
    return _LOCAL_HOST if _LOCAL_HOST is not None else platform.node()


def host_ok(host: str, local: str) -> bool:
    """The host guard of `parallel_admission_collect.classify_liveness`: only a
    lock recorded on THIS host can be judged by the local process table."""
    return bool(host) and host != "unknown" and host == local


def anchored(fields: dict) -> bool:
    pid = fields.get("pid", "")
    return bool(PID_RE.match(pid)) and int(pid) > 0


def liveness_of(lock: LockRec) -> str:
    """other_host | noanchor | alive | dead | unknown -- host guard FIRST."""
    f = lock.fields
    if not host_ok(f.get("hostname", ""), local_host()):
        return "other_host"
    if not anchored(f):
        return "noanchor"
    v = _LIVENESS(f.get("pid"), f.get("pid_starttime") or "-",
                  f.get("pid_starttime_kind") or "proc")
    return v if v in ("alive", "dead", "unknown") else "unknown"


def _status_word(task: TaskRec) -> str:
    if task.where in ("missing", "fold_scan"):
        return "folded" if task.where == "fold_scan" else "missing"
    if task.where == "archived":
        return f"archived {task.status}"
    if task.folded:
        return "folded"
    return task.status or "unknown"


def recovery_verdict(lock, task: TaskRec, liveness: str = "") -> Verdict:
    """THE ordered decision table (module docstring). `lock` is a LockRec or
    None; `liveness` is liveness_of(lock), computed by the caller."""
    if lock is not None and lock.state == "error":
        return Verdict(1, "unreadable", False, "", f"unreadable: {lock.why}")
    if task.where == "error":
        return Verdict(1, "unreadable", False, "", f"unreadable: {task.why}")
    if lock is not None:
        host = lock.fields.get("hostname", "") or "unknown"
        if liveness == "other_host":
            return Verdict(2, "other_host", False, "unknown",
                           f"held on {host}: not verifiable here")
        if liveness == "alive":
            return Verdict(3, "alive", False, "done", "held by a live session")
        if liveness == "noanchor":
            return Verdict(5, "stale_lock", True, "open",
                           f"lock without a PID anchor; task {_status_word(task)}")
        if liveness == "dead":
            if task.implementing:
                return Verdict(6, "crashed", True, "open",
                               f"holder pid {lock.fields.get('pid')} is gone")
            return Verdict(7, "stale_lock", True, "open",
                           f"holder gone; task {_status_word(task)}")
        return Verdict(4, "unknown", False, "unknown", "liveness unknown")
    if task.implementing:
        return Verdict(8, "orphan", True, "open", "Implementing with no lock")
    return Verdict(9, "recovered", False, "done", f"recovered: {_status_word(task)}")


def _h(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:12]


def episode_key(tid: str, lock, recorded) -> str:
    tid = _bare(tid)
    if lock is None or lock.state != "ok":
        return recorded or _h("nolock", tid)
    f = lock.fields
    if anchored(f):
        return _h("anchored", tid, f.get("hostname", ""), f.get("pid", ""),
                  f.get("pid_starttime", ""), f.get("pid_starttime_kind", ""))
    return _h("unanchored", tid, f.get("locked_by", ""), f.get("hostname", ""),
              f.get("locked_at", ""))


# --- evidence ----------------------------------------------------------------

def parse_porcelain(out: bytes) -> list:
    """Paths of `git status --porcelain -z` (the rename source is skipped)."""
    paths = []
    recs = out.split(b"\0")
    i = 0
    while i < len(recs):
        rec = recs[i]
        i += 1
        if len(rec) < 4:
            continue
        xy, path = rec[:2], rec[3:].decode("utf-8", "replace")
        paths.append(path)
        if xy[:1] in (b"R", b"C"):
            i += 1
    return sorted(set(paths))


def _match_path(cand: str, universe: set, suffix_index: dict):
    """The one path of `universe` that `cand` names, or None: exact, or (with
    a `/`) the unique trailing sub-path of one path. Only an explicit `./`
    prefix and trailing sentence punctuation / directory slashes are
    normalized -- every other character, a leading dot or a space included, is
    part of the name."""
    while cand.startswith("./"):
        cand = cand[2:]
    cand = cand.rstrip("./")
    if not cand:
        return None
    if cand in universe:
        return cand
    if "/" in cand:
        hits = suffix_index.get(cand)
        if hits and len(hits) == 1:
            return hits[0]
    return None


def _whole(cand: str) -> str:
    """A complete-path candidate (metadata entry / backticked span): trimmed,
    with a trailing line reference (`:12`, `:12-30`, `#L12-L30`) removed."""
    return LINE_SUFFIX_RE.sub("", cand.strip())


def named_paths(text: str, universe: set, suffix_index: dict, explicit=()) -> set:
    """Paths of `universe` a text names. Explicit entries (`file_references:`)
    and backticked spans are matched as COMPLETE paths first, so a name with a
    space or other non-word characters survives; then the bare-word scan."""
    out = set()
    for cand in list(explicit) + BACKTICK_RE.findall(text or ""):
        hit = _match_path(_whole(str(cand)), universe, suffix_index)
        if hit:
            out.add(hit)
    for tok in PATH_TOKEN_RE.findall(text or ""):
        hit = _match_path(tok, universe, suffix_index)
        if hit:
            out.add(hit)
    return out


def build_suffix_index(tracked: set) -> dict:
    idx: dict = {}
    for p in tracked:
        parts = p.split("/")
        for i in range(1, len(parts) - 1):
            idx.setdefault("/".join(parts[i:]), []).append(p)
    return idx


class DigestMemo:
    """The once-per-pass `current_digest` provider of read_task_gate_state."""

    def __init__(self, root: str):
        self.root = root
        self.done = False
        self.value = None

    def __call__(self):
        if not self.done:
            self.value = gl.code_digest(self.root)
            self.done = True
        return self.value


@dataclass
class Survey:
    task: TaskRec
    verdict: Verdict
    key: str
    lock: object = None
    lock_age: str = "none"
    phase: str = "unknown"
    phase_provenance: str = "unknown"
    pending_gates: list = field(default_factory=list)
    plan: str = "none"
    plan_rel: str = ""
    plan_signature: str = "none"
    plan_fresh: str = "unknown:no_plan"
    worktree: str = "shared"
    attributed: list = field(default_factory=list)     # [(path, source)]
    unattributed: int = 0
    overlaps: list = field(default_factory=list)       # [(path, task, live|crashed)]
    commits: list = field(default_factory=list)        # [sha]
    branch_head: str = ""
    agent: str = ""
    pane: str = ""
    tail: bytes = b""
    incomplete: list = field(default_factory=list)     # evidence that could not be read

    @property
    def survivors(self) -> bool:
        """THIS task's own surviving work (ranks the item)."""
        return bool(self.attributed or self.commits or self.branch_head)

    def warning(self) -> str:
        """The tree warning. Unattributed shared-tree edits and unread evidence
        warn too -- without being attributed to this task."""
        if self.survivors:
            return SURVIVOR_WARNING
        if self.unattributed:
            return UNATTRIBUTED_WARNING
        if self.incomplete:
            return INCOMPLETE_WARNING.format(what=",".join(self.incomplete))
        return "none"


class Pass:
    """One detector pass over one repository root."""

    def __init__(self, root: str, dry_run: bool):
        self.root = root
        self.dry_run = dry_run
        self.lines: list = []
        self.counts = dict(crashed=0, orphans=0, stale_locks=0, skipped=0,
                           added=0, reopened=0, warned=0)
        self.store = sh.Store(root, os.path.join(root, sh.STORE_NAME))
        self.digest = DigestMemo(root)
        self.registry = os.path.join(root, "aitasks", "metadata", "gates.yaml")
        self._tracked = None
        self._suffix = None
        self._shared = None
        self._names: dict = {}
        self._universe = None
        self.plan_errors: dict = {}

    # -- output --
    def emit(self, line: str) -> None:
        self.lines.append(line)
        print(line, flush=True)

    def warn(self, tid: str, reason: str) -> None:
        self.counts["warned"] += 1
        self.emit(f"CRASH_WARN:t{tid}|{_one_line(reason)[:300]}")

    # -- per-pass git facts --
    # A failed `ls-files` / `status` would read as "nothing tracked / nothing
    # dirty" and certify freshness from incomplete inputs, so either failure
    # ends the pass before anything is written (run() reads both up front).
    def tracked(self) -> set:
        if self._tracked is None:
            rc, out = _git(self.root, "ls-files", "-z")
            if rc != 0:
                raise CrashFailure("tracked_files_unreadable")
            self._tracked = set(out.decode("utf-8", "replace").split("\0")) - {""}
        return self._tracked

    def shared_dirty(self) -> list:
        """Every dirty path of the shared tree, untracked FILES included
        (`--untracked-files=all`: a crashed task's new file is surviving work)."""
        if self._shared is None:
            rc, out = _git(self.root, "status", "--porcelain", "-z", "--untracked-files=all",
                           "--", ".", *DATA_EXCLUDES)
            if rc != 0:
                raise CrashFailure("shared_status_unreadable")
            self._shared = parse_porcelain(out)
        return self._shared

    def universe(self) -> set:
        """Ownership matching runs over tracked AND dirty paths (an untracked
        named file is attributable); commit history only over tracked ones."""
        if self._suffix is None:
            self._universe = self.tracked() | set(self.shared_dirty())
            self._suffix = build_suffix_index(self._universe)
        return self._universe

    def names(self, task: TaskRec, plan_text: str) -> tuple:
        """(plan-named, task-named) paths, memoized per task."""
        if task.id not in self._names:
            universe = self.universe()
            refs = task.meta.get("file_references") or []
            refs = [r for r in refs if isinstance(r, str)] if isinstance(refs, list) else []
            self._names[task.id] = (
                named_paths(plan_text, universe, self._suffix),
                named_paths(task.text, universe, self._suffix, explicit=refs),
            )
        return self._names[task.id]

    # -- inputs --
    def read_inputs(self) -> tuple:
        locks = read_locks(self.root)
        active = read_active_tasks(self.root)
        try:
            self.store.load()
        except sh.HarvestFailure as e:
            raise CrashFailure(str(e)) from None
        items = {}
        for num, item in self.store.items.items():
            tid = st.parse_recover_ref(item.ref)
            if tid:
                items[tid] = (item, self.store.contexts.get(num))
        return locks, active, items

    def targets(self, locks, active, items) -> list:
        ids = set(locks) | set(items)
        ids |= {t for t, r in active.items() if r.implementing or r.where == "error"}
        return sorted(ids, key=id_key)

    # -- evidence extraction --
    def plan_text(self, task: TaskRec) -> tuple:
        """(repo-relative plan path, text), memoized per task. An unreadable
        plan is recorded in `plan_errors` -- never an empty plan."""
        cache = self.__dict__.setdefault("_plans", {})
        if task.id in cache:
            return cache[task.id]
        result = ("", "")
        path = pac.plan_path_for(self.root, task.id) if task.where == "active" else None
        if path:
            rel = os.path.relpath(path, self.root)
            try:
                with open(path, "rb") as fh:
                    result = (rel, fh.read().decode("utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                self.plan_errors[task.id] = f"{rel}: {exc}"
                result = (rel, "")
        cache[task.id] = result
        return result

    def survey(self, task: TaskRec, verdict: Verdict, lock, key: str,
               verdicts: dict, tasks: dict) -> Survey:
        s = Survey(task=task, verdict=verdict, key=key, lock=lock)
        if lock is not None:
            s.lock_age = age_bucket(lock.fields.get("locked_at", ""), now_utc())
        plan_rel, plan_text = self.plan_text(task)
        s.plan_rel = plan_rel
        self._phase_and_plan(s, plan_rel, plan_text)
        self._work(s, plan_text, verdicts, tasks)
        self._pane(s)
        return s

    def _phase_and_plan(self, s: Survey, plan_rel: str, plan_text: str) -> None:
        task = s.task
        state = None
        if task.text and gl.has_gate_markers(task.text):
            try:
                rp = gl.resume_point_from_text(task.text)
                s.phase = {"PLAN": "planning", "IMPLEMENT": "implementing",
                           "POSTIMPL": "post_impl"}.get(rp, "unknown")
                s.phase_provenance = "ledger"
                if task.where == "active":
                    state = gl.read_task_gate_state(
                        task.path,
                        registry_file=os.path.join(self.root, "aitasks", "metadata",
                                                   "gates.yaml"),
                        current_digest=self.digest)
            except Exception:  # noqa: BLE001 - an unreadable ledger is evidence
                s.phase, s.phase_provenance, state = "error", "error", None
        if s.phase == "post_impl" and state is not None:
            s.pending_gates = list(state.archive_pending)
        run = state.current.get("plan_approved") if state is not None else None
        ledger_pass = run is not None and run.status == "pass"
        approved_at = str(task.meta.get("plan_approved_at") or "").strip()
        if ledger_pass or approved_at:
            s.plan = "approved"
        elif plan_rel:
            s.plan = "draft"
        if ledger_pass:
            s.plan_signature = "stale" if "plan_approved" in state.stale_signed else "valid"
        approval_ts = (run.fields.get("run", "") if ledger_pass else "") or approved_at
        s.plan_fresh = self._fresh(s, plan_text, approval_ts)

    def _fresh(self, s: Survey, plan_text: str, approval_ts: str) -> str:
        task = s.task
        if task.where != "active":
            return "unknown:not_active"
        plan_named, task_named = self.names(task, plan_text)
        files = sorted(plan_named | task_named)
        if not files:
            return "unknown:no_files"
        history = [f for f in files if f in self.tracked()]
        base = ""
        pb = str(task.meta.get("premise_baseline") or "").strip()
        if pb:
            base = pb.split(" @ ", 1)[0].strip()
        elif approval_ts:
            rc, out = _git_text(self.root, "rev-list", "-1", f"--before={approval_ts}", "HEAD")
            if rc != 0:
                return "unknown:git"
            base = out.strip()
        if not base:
            return "unknown:no_baseline"
        out = ""
        if history:
            rc, out = _git_text(self.root, "log", "--format=%H", f"{base}..HEAD", "--", *history)
            if rc != 0:
                return "unknown:git"
        reasons = []
        if s.plan_signature == "stale":
            reasons.append("signature_stale")
        n = len([ln for ln in out.splitlines() if ln.strip()])
        if n:
            reasons.append(f"{n}_commits")
        # Authorship rule: in a dedicated worktree, dirty files are this task's
        # own surviving work; only the SHARED tree can make the plan stale.
        if self._worktree_state(task)[0] == "NONE":
            dirty = set(self.shared_dirty()) & set(files)
            if dirty:
                reasons.append(f"dirty_referenced:{len(dirty)}")
        return "fresh" if not reasons else "stale:" + ",".join(reasons)

    def _worktree_state(self, task: TaskRec) -> tuple:
        """(state, path) from aitask_task_worktree.sh resolve, memoized."""
        cache = self.__dict__.setdefault("_wt", {})
        if task.id in cache:
            return cache[task.id]
        if not task.stem:
            cache[task.id] = ("NONE", "")
            return cache[task.id]
        try:
            p = subprocess.run([WORKTREE_SH, "resolve", task.stem], capture_output=True,
                               text=True, cwd=self.root, timeout=GIT_TIMEOUT)
            out = p.stdout.strip()
            rc = p.returncode
        except (OSError, subprocess.SubprocessError):
            out, rc = "", 127
        if rc != 0 or not out:
            cache[task.id] = (f"error:{rc}", "")
        else:
            state, _, path = out.partition(" ")
            cache[task.id] = (state, path)
        return cache[task.id]

    def _work(self, s: Survey, plan_text: str, verdicts: dict, tasks: dict) -> None:
        task = s.task
        state, path = self._worktree_state(task)
        if state == "USABLE":
            s.worktree = f"worktree {path}"
            rc, out = _git(path, "status", "--porcelain", "-z", "--untracked-files=all",
                           "--", ".", *DATA_EXCLUDES)
            if rc == 0:
                s.attributed = [(p, "worktree") for p in parse_porcelain(out)]
            else:
                s.worktree = f"worktree {path} (status unreadable)"
                s.incomplete.append("worktree_status")
        elif state == "NONE":
            s.worktree = "shared"
            if task.where == "active":
                plan_named, task_named = self.names(task, plan_text)
                for p in self.shared_dirty():
                    if p in plan_named:
                        s.attributed.append((p, "plan"))
                    elif p in task_named:
                        s.attributed.append((p, "task"))
                dirty = set(self.shared_dirty())
                mine = (plan_named | task_named) & dirty
                for other_id, other in sorted(tasks.items(), key=lambda kv: id_key(kv[0])):
                    if other_id == task.id or not other.implementing:
                        continue
                    op_rel, op_text = self.plan_text(other)
                    if other_id in self.plan_errors:
                        s.overlaps.append(("?", f"t{other_id}", "plan_unreadable"))
                        continue
                    o_plan, o_task = self.names(other, op_text)
                    v = verdicts.get(other_id)
                    tag = "live" if v is not None and v.row == 3 else \
                        "crashed" if v is not None and v.stored else "unknown"
                    for p in sorted(mine & (o_plan | o_task)):
                        s.overlaps.append((p, f"t{other_id}", tag))
        else:
            s.worktree = state
            s.incomplete.append(f"worktree_{state}")
        # Commits referencing (t<N>), excluding administrative `ait:` subjects.
        args = ["log", f"-n{COMMIT_SCAN_LIMIT}", "--format=%H%x09%s", "-F",
                f"--grep=(t{task.id})"]
        if s.lock is not None and parse_locked_at(s.lock.fields.get("locked_at", "")):
            args.append(f"--since={s.lock.fields.get('locked_at')}")
        args.append("HEAD")
        rc, out = _git_text(self.root, *args)
        if rc != 0:
            s.incomplete.append("commits")
        else:
            for ln in out.splitlines():
                sha, _, subj = ln.partition("\t")
                if sha and not subj.startswith("ait:"):
                    s.commits.append(sha)
        if task.stem:
            rc, out = _git_text(self.root, "rev-parse", "-q", "--verify",
                                f"refs/heads/aitask/{task.stem}")
            if rc == 0:
                s.branch_head = out.strip()

    def _pane(self, s: Survey) -> None:
        recs = []
        for rec in agent_sessions.load_safe().sessions:
            if _bare(rec.task_id) != s.task.id or not rec.root:
                continue
            try:
                rroot, _ = sh.canonical_root(rec.root)
            except sh.HarvestFailure:
                continue
            if rroot == self.root:
                recs.append(rec)
        if not recs:
            return
        rec = max(recs, key=lambda r: (r.state_at or r.started_at or "", r.id))
        s.agent = sh._token(rec.agent_string or "")
        s.pane = sh._token(rec.pane_id or "")
        if rec.capture_txt:
            try:
                with open(rec.capture_txt, "rb") as fh:
                    data = fh.read()
            except OSError:
                return
            lines = data.replace(b"\0", b"").decode("utf-8", "replace").splitlines()
            tail = "\n".join(lines[-CAPTURE_TAIL_LINES:]).encode("utf-8")
            if len(tail) > CAPTURE_TAIL_BYTES:
                tail = tail[-CAPTURE_TAIL_BYTES:].decode("utf-8", "ignore").encode("utf-8")
            if tail.strip():
                s.tail = tail + b"\n"

    # -- rendering --
    @staticmethod
    def survey_text(s: Survey) -> bytes:
        lock = s.lock
        if lock is not None:
            f = lock.fields
            lock_line = (f"host={f.get('hostname', '')} pid={f.get('pid', '') or '-'} "
                         f"locked_at={f.get('locked_at', '') or '-'}")
        else:
            lock_line = "none"
        attributed = s.attributed
        out = [SURVEY_HEADER,
               f"task: t{s.task.id}",
               f"category: {s.verdict.category}",
               f"incarnation: {s.key}",
               f"lock: {lock_line}",
               f"lock_age: {s.lock_age}",
               f"phase: {s.phase}",
               f"phase_provenance: {s.phase_provenance}",
               f"pending_gates: {','.join(s.pending_gates) or '-'}",
               f"plan: {s.plan}",
               f"plan_signature: {s.plan_signature}",
               f"plan_fresh: {s.plan_fresh}",
               f"worktree: {s.worktree}",
               f"uncommitted_files: attributed={len(attributed)} unattributed={s.unattributed}"]
        out += [f"attributed: {p} [{src}]" for p, src in attributed]
        out += [f"overlap: {p} {t}({tag})" for p, t, tag in s.overlaps]
        commits = "unknown" if "commits" in s.incomplete else str(len(s.commits))
        out.append(f"commits: {commits}" + (f" branch_head={s.branch_head}"
                                            if s.branch_head else ""))
        out.append(f"warning: {s.warning()}")
        return ("\n".join(_one_line(x) if i else x for i, x in enumerate(out)) + "\n").encode("utf-8")

    @staticmethod
    def rank_of(s: Survey) -> int:
        if s.plan == "approved":
            if (s.phase in ("implementing", "post_impl") and s.plan_signature != "stale"
                    and s.plan_fresh == "fresh" and s.survivors):
                return 1
            return 2
        return 3 if s.plan == "draft" else 4

    @classmethod
    def group_of(cls, s: Survey) -> str:
        if s.verdict.category == "orphan":
            return "next"
        if s.verdict.category == "stale_lock":
            return "waiting"
        return "now" if cls.rank_of(s) <= 2 else "next"

    @staticmethod
    def title_of(s: Survey) -> str:
        fresh = s.plan_fresh
        if fresh.startswith("stale:"):
            short = "stale: " + ",".join(r.split(":", 1)[0] for r in fresh[6:].split(","))
        else:
            short = fresh.split(":", 1)[0]
        plan = "no plan" if s.plan == "none" else f"{s.plan} plan ({short})"
        ov = sorted({t for _, t, _ in s.overlaps}, key=lambda t: id_key(t))
        parts = [s.phase, plan, f"{len(s.attributed)} files"]
        if ov:
            parts.append("overlaps " + " ".join(ov))
        head = f"Recover t{s.task.id}" + (f" {s.task.slug}" if s.task.slug else "")
        return sh._title(f"{head} ({s.verdict.category}): " + ", ".join(parts))

    def context_entry(self, s: Survey, survey_ptr: str, tail_ptr: str) -> st.ContextEntry:
        origin = [("task", f"t{s.task.id}"), ("incarnation", s.key)]
        if s.agent:
            origin.append(("agent", s.agent))
        if s.pane:
            origin.append(("pane", s.pane))
        sources = []
        if s.task.rel:
            sources.append(("task", s.task.rel))
        if s.plan_rel:
            sources.append(("plan", s.plan_rel))
        sources.append(("capture", survey_ptr))
        if tail_ptr:
            sources.append(("capture", tail_ptr))
        commits = [("commit", c) for c in s.commits[:MAX_COMMIT_SOURCES]]
        entry = st.ContextEntry(background=BACKGROUND[s.verdict.category][: st.MAX_BACKGROUND],
                                origin=origin, sources=sources + commits)
        while len("\n".join(entry.body_lines()).encode("utf-8")) > st.MAX_CONTEXT_BYTES:
            if commits:
                commits.pop()
            elif tail_ptr:
                sources = [x for x in sources if x[1] != tail_ptr]
                tail_ptr = ""
            else:
                break
            entry.sources = sources + commits
        return entry

    # -- writes --
    def apply(self, args: list, context: str | None = None) -> str:
        cmd = ["recovery-apply", *args]
        if context is not None:
            cmd += ["--context-file", "-"]
        try:
            out = self.store.run(cmd, (context or "").encode("utf-8"))
        except sh.HarvestFailure as e:
            msg = str(e)
            if msg.startswith("writer:request:"):
                return "WARN:writer_request:" + msg[len("writer:request:"):]
            raise CrashFailure(msg) from None
        for line in out:
            if re.match(r"^(ADDED|APPLIED|UNCHANGED|REOPENED|STALE|KEPT|ABSENT):", line):
                return line
        return "WARN:writer_no_result"

    def retain(self, data: bytes, want: str) -> None:
        try:
            got = self.store.retain(data)
        except sh.HarvestFailure as e:
            raise CrashFailure(str(e)) from None
        if got != want:
            raise CrashFailure(f"retain_pointer_mismatch:{got}")

    def reply(self, tid: str, reply: str, category: str) -> None:
        kind, _, rest = reply.partition(":")
        num = rest.split("|", 1)[0]
        words = {"ADDED": "added", "APPLIED": "applied", "UNCHANGED": "unchanged",
                 "REOPENED": "reopened", "KEPT": "kept_dismissed"}
        if kind in words:
            if kind == "ADDED":
                self.counts["added"] += 1
            elif kind == "REOPENED":
                self.counts["reopened"] += 1
            self.emit(f"CRASH_ITEM:t{tid}|{num}|{words[kind]}|{category}")
        elif kind == "STALE":
            self.warn(tid, "stale")
        elif kind == "ABSENT":
            self.warn(tid, "absent")
        else:
            self.warn(tid, rest or reply)

    # -- the pass --
    def run(self) -> int:
        locks, active, items = self.read_inputs()
        index = sitrep_refresh.TaskIndex(self.root)
        ids = self.targets(locks, active, items)
        if not ids:
            self.emit("CRASH_NONE:nothing_inflight")
            return 0
        # An item that is done or dismissed, with no lock and no active file,
        # can only land on row 9 (or row 1, which never writes): skip it
        # without reading the archive, or old items would cost a bundle read
        # on every pass.
        ids = [t for t in ids if t in locks or t in active
               or items[t][0].state not in ("done", "dismissed")]
        if not ids:
            self.emit("CRASH_NONE:nothing_inflight")
            return 0
        tasks = {}
        for tid in ids:
            tasks[tid] = active.get(tid) or read_inactive_task(self.root, tid, index)
        # Implementing tasks without a lock or item still matter for overlaps.
        for tid, rec in active.items():
            if rec.implementing and tid not in tasks:
                tasks[tid] = rec
        if any(t.implementing for t in tasks.values()) or locks:
            self.universe()     # ls-files + status: a failure ends the pass here
        verdicts = {}
        liveness = {}
        for tid in ids:
            lock = locks.get(tid)
            live = liveness_of(lock) if lock is not None and lock.state == "ok" else ""
            liveness[tid] = live
            verdicts[tid] = recovery_verdict(lock, tasks[tid], live)
        for tid in ids:
            self.one(tid, locks.get(tid), tasks[tid], verdicts[tid], items.get(tid),
                     verdicts, tasks)
        c = self.counts
        self.emit(f"CRASHED:crashed={c['crashed']}|orphans={c['orphans']}|"
                  f"stale_locks={c['stale_locks']}|skipped={c['skipped']}|"
                  f"added={c['added']}|reopened={c['reopened']}|warned={c['warned']}")
        return 0

    def one(self, tid, lock, task, v: Verdict, held, verdicts, tasks) -> None:
        item, ctx = held if held else (None, None)
        recorded = st.context_incarnation(ctx)
        if v.row == 1:
            self.warn(tid, v.evidence)
            return
        if v.row in SKIP_ROWS:
            self.counts["skipped"] += 1
            tag = f"other_host:{lock.fields.get('hostname', '') or 'unknown'}" \
                if v.row == 2 else v.category
            self.emit(f"CRASH_SKIP:t{tid}|{tag}")
        if not v.stored:
            self.state_only(tid, v, item, recorded)
            return
        self.counts[{"crashed": "crashed", "orphan": "orphans",
                     "stale_lock": "stale_locks"}[v.category]] += 1
        key = episode_key(tid, lock, recorded)
        cid = f"c{item.num}" if item else "-"
        if item is not None and item.state == "dismissed" and recorded == key:
            self.emit(f"CRASH_ITEM:t{tid}|{cid}|kept_dismissed|{v.category}")
            return
        self.plan_text(task)
        if tid in self.plan_errors:
            self.warn(tid, f"unreadable: plan {self.plan_errors[tid]}")
            return
        s = self.survey(task, v, lock, key, verdicts, tasks)
        s.unattributed = len(self._unattributed(verdicts, tasks))
        survey = self.survey_text(s)
        survey_ptr = retain_pointer(survey)
        tail_ptr = retain_pointer(s.tail) if s.tail else ""
        entry = self.context_entry(s, survey_ptr, tail_ptr)
        if tail_ptr and not any(p == tail_ptr for _, p in entry.sources):
            tail_ptr = ""
        title, group, outcome = self.title_of(s), self.group_of(s), v.outcome
        if (item is not None and item.state == "open" and recorded == key
                and item.title == title and item.group == group
                and item.outcome == outcome and ctx is not None
                and ctx.body_lines() == entry.body_lines()):
            self.emit(f"CRASH_ITEM:t{tid}|{cid}|unchanged|{v.category}")
            return
        if self.dry_run:
            self.emit(f"CRASH_ITEM:t{tid}|{cid}|dry_run|{v.category}")
            return
        self.retain(survey, survey_ptr)
        fault_point("after_retain")
        if tail_ptr:
            self.retain(s.tail, tail_ptr)
        fault_point("before_apply")
        pause_point("before_apply")
        args = ["--ref", f"recover:t{tid}",
                "--expect-rev", str(item.rev) if item else "absent",
                "--incarnation", key, "--state", "open", "--outcome", outcome,
                "--title", title, "--group", group, "--checked-at", "now"]
        context = "\n".join(entry.body_lines()) + "\n"
        self.reply(tid, self.apply(args, context), v.category)

    def state_only(self, tid, v: Verdict, item, recorded) -> None:
        if item is None or item.state == "dismissed":
            return
        if item.state == v.item_state and item.outcome == v.outcome:
            return
        if not recorded:
            self.warn(tid, "no_recorded_incarnation")
            return
        if self.dry_run:
            self.emit(f"CRASH_ITEM:t{tid}|c{item.num}|dry_run|{v.category}")
            return
        fault_point("before_apply")
        pause_point("before_apply")
        args = ["--ref", f"recover:t{tid}", "--expect-rev", str(item.rev),
                "--incarnation", recorded, "--state", v.item_state,
                "--outcome", v.outcome, "--checked-at", "now"]
        self.reply(tid, self.apply(args), v.category)

    def _unattributed(self, verdicts, tasks) -> set:
        cache = self.__dict__.get("_unattr")
        if cache is not None:
            return cache
        named = set()
        for tid, task in tasks.items():
            v = verdicts.get(tid)
            if v is None or not v.stored or task.where != "active":
                continue
            _, ptext = self.plan_text(task)
            p_named, t_named = self.names(task, ptext)
            named |= p_named | t_named
        cache = set(self.shared_dirty()) - named
        self.__dict__["_unattr"] = cache
        return cache


# --- CLI ---------------------------------------------------------------------

def _root_of(args) -> str:
    raw = getattr(args, "root_canonical", None) or args.root
    try:
        root, is_git = sh.canonical_root(raw)
    except sh.HarvestFailure as e:
        raise CrashFailure(str(e)) from None
    if not is_git:
        raise CrashFailure("not_a_git_repository")
    return root


def cmd_plan(args) -> int:
    root = _root_of(args)
    os.chdir(root)
    p = Pass(root, dry_run=True)
    locks, active, items = p.read_inputs()
    open_items = {t for t, (it, _) in items.items() if it.state in ("open", "unknown")}
    live_ids = set(locks) | open_items | {
        t for t, r in active.items() if r.implementing or r.where == "error"}
    if not live_ids:
        print("CRASH_NONE:nothing_inflight")
        return 0
    print(sh._work(root))
    return 0


def cmd_run(args, dry_run: bool) -> int:
    root = _root_of(args)
    os.chdir(root)
    return Pass(root, dry_run=dry_run).run()


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sitrep_crash.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "apply", "dry-run"):
        sp = sub.add_parser(name)
        sp.add_argument("--root", default=None)
        sp.add_argument("--root-canonical", default=None)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not (args.root or args.root_canonical):
        print("Error: --root is required", file=sys.stderr)
        return 2
    try:
        if args.cmd == "plan":
            return cmd_plan(args)
        return cmd_run(args, dry_run=(args.cmd == "dry-run"))
    except SourceError as e:
        print(f"CRASH_FAILED:{e}", flush=True)
        return 1
    except CrashFailure as e:
        print(f"CRASH_FAILED:{_one_line(str(e))}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
