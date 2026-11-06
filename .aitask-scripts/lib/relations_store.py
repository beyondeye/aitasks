#!/usr/bin/env python3
"""relations_store.py - the task-relations store on the orphan ref ``aitask-relations``.

Design: aidocs/framework/task_relations.md (D1 store, D2 schema, D3 lookup, D11
freshness), and its "Store API" section. Plumbing: ``orphan_ref_store``.
Schema, digests and the ``wins()`` comparison: ``relations_schema``.

Ref model (the t1981_1 plan's M1-M6)
------------------------------------
* ``refs/heads/aitask-relations`` (L) is this clone's DURABLE, latest-known
  store in every mode. It only moves forward: local-only commits are built on
  it, and in remote mode every remote commit enters it through
  ``integrate()``, which fast-forwards or makes an "absorb" merge. So L holds
  every record this clone observed or published plus its unpublished work, and
  survives a failed fetch, ``--no-fetch`` and ``git remote remove``. The
  remote-tracking ref is never read or written.
* ``refs/aitask-relations/observed`` (O) is advisory only: the last remote tip
  seen, used to mark ``pending_push``.
* Fetches land in a private temp ref and every operation works on the
  immutable shas it resolved; every push is leased on the exact base it was
  built on (``--force-with-lease``).
* Merges are three-way over ``merge-base --all`` (zero bases = one synthetic
  empty base) through ONE total per-path function, ``merge_path``; a deletion
  only wins when the record it removes is deletion-eligible (gc's rule).

Writes go through the outbox first (D1): validate, write
``<git-common-dir>/aitask-relations/outbox/<kind>/t<id>.json`` atomically, then
publish all entries in one commit. An entry is cleared only after the local
store provably contains its result (``integrate()`` returned INTEGRATED), and
only when its bytes still equal what the flusher read (content-conditional,
under ``outbox.lock``, which is never held across network steps).

``gc`` is the documented single-writer exception (D1/D11): it deletes files
only for ids that exist nowhere, or whose recorded ``task_created_at`` no
longer matches the live task. Eligibility is re-checked against the exact tree
the deletion is built from, on every attempt.
"""
from __future__ import annotations

import contextlib
import dataclasses
import datetime as _dt
import fcntl
import glob
import hashlib
import json
import os
import random
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import archive_iter  # noqa: E402
import orphan_ref_store as ors  # noqa: E402
import relations_schema as rs  # noqa: E402
from relations_schema import digests, normalize_body, normalize_plan, sha256_text, wins  # noqa: E402,F401
from task_yaml import parse_frontmatter  # noqa: E402

BRANCH = "aitask-relations"
L_REF = f"refs/heads/{BRANCH}"
O_REF = "refs/aitask-relations/observed"
SCHEMA_PATH = "schema_version"
MAX_ATTEMPTS = 8
DEFAULT_TIMEOUT = 20.0
UNREADABLE = "UNREADABLE"
QUERY_FILES = os.path.join(os.path.dirname(_LIB), "aitask_query_files.sh")

_PARENT_RE = re.compile(r"^t(\d+)_(?!\d+_)")
_CHILD_RE = re.compile(r"^t(\d+)_(\d+)_")


class ProjectUnresolved(RuntimeError):
    """The local project's logical name is missing or not a valid name."""


def local_project_name(root) -> str:
    """``project.name`` of the project at ``root`` (honours ``TASK_DIR``).

    Its absence is an install defect (``ait setup`` seeds it), reported as
    ``ProjectUnresolved``; there is no fallback name, because records written
    under a guessed name would never match the other clones' records.
    """
    import config_utils
    path = Path(root, os.environ.get("TASK_DIR", "aitasks"), "metadata", "project_config.yaml")
    try:
        cfg = config_utils.load_yaml_config(path)
    except Exception as exc:  # unreadable or malformed YAML
        raise ProjectUnresolved(f"cannot read {path}: {exc.__class__.__name__}") from exc
    project = cfg.get("project") if isinstance(cfg, dict) else None
    name = project.get("name") if isinstance(project, dict) else None
    if not isinstance(name, str) or not rs.valid_project(name.strip()):
        raise ProjectUnresolved(f"{path}: missing or invalid project.name")
    return name.strip()


def _test_hook(point: str, **ctx) -> None:
    """No-op seam: tests replace it with a barrier at a named point.

    Points: after_snapshot, after_resolve_local, after_pin, after_push,
    before_bookkeeping, gc_after_select, before_removal.
    """


def job_state(task_id):
    """Spool state of a task's analysis job: ``pending(..)`` / ``failed(..)``.

    Returns None here; t1981_3 (worker and spool) replaces it.
    """
    return None


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dumps(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _loads(data):
    if data is None:
        return None
    obj = json.loads(data.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("not a JSON object")
    return obj


def _atomic_write(path: str, data: bytes) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp-{os.getpid()}-{random.getrandbits(32):08x}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        try:
            view = memoryview(data)
            while view:
                # os.write may write fewer bytes than asked: loop until done, and
                # never publish a short temp file (a 0 return is a failure).
                n = os.write(fd, view)
                if n <= 0:
                    raise OSError(f"short write to {tmp}")
                view = view[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    os.replace(tmp, path)
    dfd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _id_of_task_name(name: str):
    base = os.path.basename(name)
    m = _CHILD_RE.match(base)
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    m = _PARENT_RE.match(base)
    if m:
        return m.group(1)
    return None


# ================================================================ task index

@dataclasses.dataclass
class TaskEntry:
    tid: str
    created_at: str | None
    status: str | None
    folded_into: str | None
    folded_tasks: list
    text: str | None
    location: str


class TaskIndex:
    """Live task identity, folds and digest baselines (active + archived).

    Per-id lookups are lazy (active files, then ``find_archived_markdown_by_id``
    which follows the shell resolver's loose -> numbered -> legacy order); a
    full scan (active + ``iter_all_archived_markdown`` + ``iter_legacy_archive``)
    runs only when completeness matters (an id found nowhere, the fold map,
    ``gc``). Every reader passes ``errors=``; a lookup that saw errors is
    "unknown", never "missing".
    """

    def __init__(self, root: str):
        self.root = root
        self.task_dir = Path(root, os.environ.get("TASK_DIR", "aitasks"))
        self.archived_dir = Path(root, os.environ.get("ARCHIVED_DIR", "aitasks/archived"))
        self.plan_dir = Path(root, os.environ.get("PLAN_DIR", "aiplans"))
        self.plan_archived_dir = Path(root, os.environ.get("ARCHIVED_PLAN_DIR", "aiplans/archived"))
        self._entries: dict = {}
        self._unknown: set = set()
        self._missing: set = set()
        self._plans: dict = {}
        self._active_loaded = False
        self.full = False
        self.errors: list = []
        self.duplicates: list = []
        self._fold_of: dict = {}

    # -- loading
    def _add(self, tid, text, location):
        # Metadata that cannot be read is an INCOMPLETE scan, never empty
        # metadata: a primary whose frontmatter is gone may still own folded
        # ids, and treating it as "no folds" would let gc delete their records.
        meta = {}
        if text is None:
            self.errors.append(f"{location}:t{tid}: unreadable task file")
        else:
            try:
                parsed = parse_frontmatter(text)
            except Exception as exc:  # malformed YAML
                parsed = None
                self.errors.append(f"{location}:t{tid}: malformed frontmatter ({exc.__class__.__name__})")
            else:
                if parsed is None:
                    self.errors.append(f"{location}:t{tid}: no frontmatter")
            if parsed is not None:
                if isinstance(parsed[0], dict):
                    meta = parsed[0]
                else:
                    self.errors.append(f"{location}:t{tid}: frontmatter is not a mapping")
        # task_yaml passes a non-list `folded_tasks` through UNCHANGED (by
        # design): iterating it would read "22" as ["2", "2"]. The container
        # must be a list and every member a task id, or the scan is incomplete.
        raw_folded = meta.get("folded_tasks")
        folded_list = []
        if raw_folded not in (None, "", []):
            if not isinstance(raw_folded, list):
                self.errors.append(f"{location}:t{tid}: folded_tasks is not a list")
            else:
                for item in raw_folded:
                    try:
                        if not isinstance(item, (str, int)) or isinstance(item, bool):
                            raise rs.SchemaError(repr(item))
                        folded_list.append(rs.norm_id(item))
                    except rs.SchemaError:
                        self.errors.append(f"{location}:t{tid}: bad folded_tasks member")
        created = meta.get("created_at")
        folded_into = meta.get("folded_into")
        try:
            if folded_into not in (None, "") and (not isinstance(folded_into, (str, int))
                                                   or isinstance(folded_into, bool)):
                raise rs.SchemaError(repr(folded_into))
            folded_into = rs.norm_id(folded_into) if folded_into not in (None, "") else None
        except rs.SchemaError:
            folded_into = None
            self.errors.append(f"{location}:t{tid}: unreadable folded_into")
        entry = TaskEntry(
            tid=tid,
            created_at=str(created) if created is not None else None,
            status=str(meta.get("status")) if meta.get("status") is not None else None,
            folded_into=folded_into,
            folded_tasks=folded_list,
            text=text, location=location)
        prev = self._entries.get(tid)
        if prev is not None:
            if prev.created_at != entry.created_at:
                self.duplicates.append(f"INDEX_DUPLICATE:t{tid}|{prev.location}|{location}")
            return prev
        self._entries[tid] = entry
        for folded in entry.folded_tasks:
            self._fold_of.setdefault(folded, tid)
        return entry

    def _read(self, path: Path, errs):
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            errs.append(f"{path}: {exc}")
            return None

    def load_active(self):
        if self._active_loaded:
            return
        self._active_loaded = True
        files = archive_iter.checked_glob(self.task_dir, "t*_*.md", self.errors)
        files += archive_iter.checked_glob(self.task_dir, "t*/t*_*_*.md", self.errors)
        for path in files:
            tid = _id_of_task_name(path.name)
            if tid is None:
                continue
            if "_" in tid and path.parent == self.task_dir:
                continue  # a child-shaped name at the top level is not a child
            text = self._read(path, self.errors)
            self._add(tid, text, "active")

    def full_scan(self):
        if self.full:
            return
        self.load_active()
        archived = list(archive_iter.iter_all_archived_markdown(self.archived_dir, errors=self.errors))
        archived += [("legacy", n, t) for n, t in archive_iter.iter_legacy_archive(self.archived_dir, errors=self.errors)]
        for item in archived:
            location = "archived"
            if len(item) == 3:
                location, name, text = item
            else:
                name, text = item
            tid = _id_of_task_name(name)
            if tid is None:
                continue
            self._add(tid, text, location)
        self.full = True
        self._unknown.clear()
        self._missing = set()

    def lookup(self, tid):
        tid = rs.norm_id(tid)
        self.load_active()
        if tid in self._entries:
            return self._entries[tid]
        if self.full or tid in self._missing or tid in self._unknown:
            return None
        errs: list = []
        found = archive_iter.find_archived_markdown_by_id(tid, self.archived_dir, errors=errs)
        if found:
            return self._add(tid, found[1], "archived")
        if errs:
            self._unknown.add(tid)
            self.errors.extend(errs)
        else:
            self._missing.add(tid)
        return None

    def refresh(self, ids):
        """Re-resolve these ids from disk (gc's per-attempt revalidation)."""
        for tid in ids:
            tid = rs.norm_id(tid)
            self._entries.pop(tid, None)
            self._missing.discard(tid)
            self._unknown.discard(tid)
            self._plans.pop(tid, None)
        saved_full, self.full = self.full, False
        try:
            for tid in ids:
                tid = rs.norm_id(tid)
                path = self._active_path(tid)
                if path is not None:
                    self._add(tid, self._read(path, self.errors), "active")
                else:
                    self.lookup(tid)
        finally:
            self.full = saved_full

    def _active_path(self, tid):
        """The active task file of one id, read from disk now (not the cache)."""
        if "_" in tid:
            parent = tid.split("_", 1)[0]
            matches = archive_iter.checked_glob(self.task_dir / f"t{parent}", f"t{tid}_*.md", self.errors)
        else:
            matches = [p for p in archive_iter.checked_glob(self.task_dir, f"t{tid}_*.md", self.errors)
                       if _id_of_task_name(p.name) == tid]
        return matches[0] if matches else None

    # -- queries
    def live_created_at(self, tid):
        entry = self.lookup(tid)
        return entry.created_at if entry else None

    def canonical(self, tid):
        """Follow ``folded_into`` (and archived primaries' ``folded_tasks``)."""
        tid = rs.norm_id(tid)
        seen = set()
        while tid not in seen:
            seen.add(tid)
            entry = self.lookup(tid)
            nxt = entry.folded_into if entry else None
            if nxt is None and entry is None:
                self.full_scan()
                nxt = self._fold_of.get(tid)
            if nxt is None:
                return tid
            tid = nxt
        return tid

    def exists(self, tid):
        """True / False / None (unknown: a reader saw errors)."""
        tid = rs.norm_id(tid)
        if self.lookup(tid) is not None:
            return True
        self.full_scan()
        if tid in self._entries or tid in self._fold_of:
            return True
        return None if self.errors else False

    def body_digest(self, tid):
        entry = self.lookup(tid)
        if entry is None or entry.text is None:
            return UNREADABLE
        return sha256_text(normalize_body(entry.text))

    def plan_digest(self, tid):
        """sha256 / None (no plan) / UNREADABLE."""
        tid = rs.norm_id(tid)
        if tid not in self._plans:
            self._plans[tid] = self._find_plan(tid)
        text = self._plans[tid]
        if text is UNREADABLE or text is None:
            return text
        return sha256_text(normalize_plan(text))

    def _find_plan(self, tid):
        errs: list = []
        if "_" in tid:
            parent, child = tid.split("_", 1)
            pats = [(self.plan_dir / f"p{parent}", f"p{tid}_*.md"),
                    (self.plan_archived_dir / f"p{parent}", f"p{tid}_*.md")]
            name_re = re.compile(rf"^p{parent}_{child}_")
        else:
            parent = tid
            pats = [(self.plan_dir, f"p{tid}_*.md"), (self.plan_archived_dir, f"p{tid}_*.md")]
            name_re = re.compile(rf"^p{tid}_(?!\d+_)")
        for directory, pattern in pats:
            for path in archive_iter.checked_glob(directory, pattern, errs):
                if name_re.match(path.name):
                    text = self._read(path, errs)
                    if text is not None:
                        return text
        bundles = []
        zst = archive_iter.archive_path_for_id(int(parent), self.plan_archived_dir)
        bundles += [zst, zst.with_suffix("").with_suffix(".tar.gz")]
        for bundle in bundles:
            if bundle.exists():
                for name, text in archive_iter.iter_archive_file(bundle, errors=errs):
                    if name_re.match(name):
                        return text
        for name, text in archive_iter.iter_legacy_archive(self.plan_archived_dir, errors=errs):
            if name_re.match(name):
                return text
        return UNREADABLE if errs else None


# ================================================================== snapshot

@dataclasses.dataclass
class Snapshot:
    state: str
    base: str | None
    files: dict
    pending: set
    corrupt: list


@dataclasses.dataclass
class Rel:
    from_: str
    to: str
    other: str  # the endpoint that is NOT the queried task (canonical ref)
    type: str
    description: str
    basis: list
    evidence: list
    record_task: str
    direction: str
    freshness: str
    pending_push: bool

    def as_dict(self):
        d = dataclasses.asdict(self)
        d["from"] = d.pop("from_")
        return d


# ===================================================================== store

class Store:
    def __init__(self, repo=None, *, remote="origin", timeout=None, project=None):
        repo = repo or os.getcwd()
        self.root = ors.toplevel(repo)
        self.remote = remote
        # The LOCAL project's logical name qualifies every bare id. It comes
        # from project_config.yaml `project.name` (seeded by `ait setup`), the
        # same source as the trails; it is never assumed.
        self.project = project if project is not None else local_project_name(self.root)
        if not rs.valid_project(self.project):
            raise ProjectUnresolved(f"invalid project name {self.project!r}")
        self.timeout = float(timeout if timeout is not None
                             else os.environ.get("AIT_RELATIONS_FETCH_TIMEOUT", DEFAULT_TIMEOUT))
        self.state_dir = os.path.join(ors.git_common_dir(self.root), "aitask-relations")
        self.outbox_dir = os.path.join(self.state_dir, "outbox")
        self.lock_path = os.path.join(self.state_dir, "outbox.lock")
        self.fetched_at_path = os.path.join(self.state_dir, "fetched_at")
        self._index = None
        self._refresh_outcome = None
        self._exists_cache: dict = {}

    # ------------------------------------------------------------ basics
    @property
    def index(self) -> TaskIndex:
        if self._index is None:
            self._index = TaskIndex(self.root)
        return self._index

    def mode(self) -> str:
        return "remote" if ors.remote_url(self.root, self.remote) else "local_only"

    def ref(self, task_id) -> str:
        return rs.canon_ref(task_id, self.project)

    @contextlib.contextmanager
    def _lock(self):
        os.makedirs(self.state_dir, exist_ok=True)
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _outbox_file(self, path: str) -> str:
        return os.path.join(self.outbox_dir, path)

    def _outbox_paths(self):
        result = []
        for kind in rs.KINDS:
            for f in sorted(glob.glob(os.path.join(self.outbox_dir, kind, "t*.json"))):
                result.append(f"{kind}/{os.path.basename(f)}")
        return result

    def _outbox_snapshot(self) -> dict:
        """``{path: (bytes, sha256)}`` read under the lock."""
        snap = {}
        with self._lock():
            for path in self._outbox_paths():
                try:
                    with open(self._outbox_file(path), "rb") as fh:
                        data = fh.read()
                except FileNotFoundError:
                    continue
                snap[path] = (data, _sha(data))
        return snap

    def _clear(self, entries: dict) -> int:
        """Remove each entry only if its bytes still equal the snapshot's."""
        removed = 0
        _test_hook("before_removal", paths=sorted(entries))
        with self._lock():
            for path, (_data, digest) in entries.items():
                target = self._outbox_file(path)
                try:
                    with open(target, "rb") as fh:
                        current = fh.read()
                except FileNotFoundError:
                    continue
                if _sha(current) != digest:
                    continue  # rewritten meanwhile: it survives
                os.unlink(target)
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(target + ".err")
                removed += 1
        return removed

    def _retain(self, entries: dict, reason: str) -> list:
        reason = reason.replace("\n", " ").replace("|", "/")
        with self._lock():
            for path, (_data, digest) in entries.items():
                target = self._outbox_file(path)
                try:
                    with open(target, "rb") as fh:
                        if _sha(fh.read()) != digest:
                            continue
                except FileNotFoundError:
                    continue
                _atomic_write(target + ".err",
                              _dumps({"at": _now(), "reason": reason}))
        return [f"RETAINED:{len(entries)}|{reason}"]

    def _files(self, commit) -> dict:
        return ors.read_files(self.root, commit) if commit else {}

    # ------------------------------------------------------- record logic
    def _kind_id(self, path):
        return rs.parse_store_path(path)

    def _live(self, path):
        parsed = self._kind_id(path)
        return self.index.live_created_at(parsed[1]) if parsed else None

    def _exists_nowhere(self, tid) -> bool:
        """Two independent negatives: the complete index AND aitask_query_files."""
        tid = rs.norm_id(tid)
        if tid in self._exists_cache:
            return self._exists_cache[tid]
        verdict = False
        if self.index.exists(tid) is False:
            verdict = self._query_files_not_found(tid)
        self._exists_cache[tid] = verdict
        return verdict

    def _query_files_not_found(self, tid) -> bool:
        lookups = [["archived-task", tid]]
        if "_" in tid:
            lookups.insert(0, ["child-file", *tid.split("_", 1)])
        else:
            lookups.insert(0, ["task-file", tid])
        for args in lookups:
            try:
                proc = subprocess.run(["bash", QUERY_FILES, *args], cwd=self.root,
                                      capture_output=True, text=True, timeout=120)
            except (OSError, subprocess.TimeoutExpired):
                return False
            out = proc.stdout.strip()
            if proc.returncode != 0 or out != "NOT_FOUND":
                return False
        return True

    def deletion_eligible(self, path, data) -> "str | None":
        """The gc reason a record at ``path`` may be deleted, or None."""
        parsed = self._kind_id(path)
        obj, _why = self._decode(path, data)
        if obj is None:
            return None  # never delete what cannot be validated
        entry = self.index.lookup(parsed[1])
        if entry is not None:
            if entry.created_at is not None and obj.get("task_created_at") != entry.created_at:
                return "identity_mismatch"
            return None
        if self._exists_nowhere(parsed[1]):
            return "task_gone"
        return None

    def _matches_live(self, path, data) -> bool:
        live = self._live(path)
        obj, _why = self._decode(path, data)
        return obj is not None and live is not None and obj.get("task_created_at") == live

    def merge_path(self, path, bases: list, l, r):
        """The total three-way rule for one path (bytes or None per side)."""
        if not bases:
            raise ValueError("merge_path needs at least one base (zero bases -> [None])")
        if l == r:
            return l
        if all(b == l for b in bases):
            return r
        if all(b == r for b in bases):
            if l is not None:
                return l
            return None if self.deletion_eligible(path, r) else r
        if l is not None and r is not None:
            return l if self._replaces(path, l, r) else r
        if r is None:
            return l if self._matches_live(path, l) else None
        return None if self.deletion_eligible(path, r) else r

    def three_way(self, local, remote) -> dict:
        base_commits = ors.merge_bases(self.root, local, remote)
        base_files = [self._files(b) for b in base_commits] or [{}]
        lf, rf = self._files(local), self._files(remote)
        paths = set(lf) | set(rf)
        for bf in base_files:
            paths |= set(bf)
        merged = {}
        for path in sorted(paths):
            value = self.merge_path(path, [bf.get(path) for bf in base_files],
                                    lf.get(path), rf.get(path))
            if value is not None:
                merged[path] = value
        return merged

    def integrate(self, commit) -> bool:
        """Make L contain ``commit`` (fast-forward or absorb merge)."""
        for _ in range(MAX_ATTEMPTS):
            cur = ors.resolve(self.root, L_REF)
            if cur is not None and ors.is_ancestor(self.root, commit, cur):
                return True
            if cur is None or ors.is_ancestor(self.root, cur, commit):
                if ors.cas_local(self.root, L_REF, commit, cur) == "OK":
                    return True
                continue
            merged = self.three_way(cur, commit)
            absorb = ors.commit_tree_from_files(
                self.root, merged, "ait: Absorb aitask-relations remote state",
                parents=(commit, cur))
            if ors.cas_local(self.root, L_REF, absorb, cur) == "OK":
                return True
        return False

    def _observe(self, commit):
        if ors.advance_ref(self.root, O_REF, commit) == "DIVERGED":
            ors.reset_ref(self.root, O_REF, commit)
            return [f"OBSERVED_DIVERGED:{commit[:12]}"]
        return []

    def _apply_outbox(self, base_files: dict, outbox: dict, reports: list):
        """Overlay outbox entries on ``base_files``; return (files, published, superseded)."""
        files = dict(base_files)
        published, superseded = {}, {}
        for path, (data, digest) in outbox.items():
            cur = files.get(path)
            if cur == data:
                superseded[path] = (data, digest)  # already there: nothing to publish
                continue
            if self._decode(path, data)[0] is None:
                # a damaged outbox entry is never published nor cleared
                reports.append(f"CORRUPT:outbox/{path}")
                continue
            if cur is not None and not self._replaces(path, data, cur):
                superseded[path] = (data, digest)
                reports.append(f"SUPERSEDED:{path}")
                continue
            files[path] = data
            published[path] = (data, digest)
        if files and SCHEMA_PATH not in files:
            files[SCHEMA_PATH] = (rs.LAYOUT_VERSION + "\n").encode()
        return files, published, superseded

    # -------------------------------------------------------------- write
    def visible(self) -> dict:
        """L plus the outbox (no fetch): ``{path: bytes}``."""
        files = self._files(ors.resolve(self.root, L_REF))
        for path, (data, _d) in self._outbox_snapshot().items():
            if self._decode(path, data)[0] is None:
                continue
            cur = files.get(path)
            if cur is None or self._replaces(path, data, cur):
                files[path] = data
        return files

    def write(self, path, record, *, flush=True) -> list:
        kind = path.split("/", 1)[0]
        rs.validate(kind, path, record)
        if self.local_id(record["task"]) is None:
            return [f"PROJECT_MISMATCH:{path}|{record['task']}"]
        tid = rs.parse_store_path(path)[1]
        entry = self.index.lookup(tid)
        if entry is not None and entry.created_at is not None \
                and record["task_created_at"] != entry.created_at:
            return [f"IDENTITY_MISMATCH:{path}"]
        if entry is None and self.index.exists(tid) is False:
            return [f"IDENTITY_MISMATCH:{path}|task_not_found"]
        data = _dumps(record)
        with self._lock():
            current = self.visible_no_lock(path)
            if current is not None and current != data and not self._replaces(path, data, current):
                return [f"STALE_RUN:{path}"]
            _atomic_write(self._outbox_file(path), data)
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self._outbox_file(path) + ".err")
        reports = [f"OUTBOX:{path}"]
        if flush:
            reports += self.flush()
        return reports

    def visible_no_lock(self, path):
        """The visible bytes at one path (caller holds the outbox lock)."""
        target = self._outbox_file(path)
        local = ors.resolve(self.root, L_REF)
        # One blob only: the lock is held, so the work must not grow with the store.
        lval = ors.read_file(self.root, local, path) if local else None
        try:
            with open(target, "rb") as fh:
                oval = fh.read()
        except FileNotFoundError:
            return lval
        if self._decode(path, oval)[0] is None:
            return lval
        if lval is None or self._replaces(path, oval, lval):
            return oval
        return lval

    # -------------------------------------------------------------- flush
    def flush(self) -> list:
        reports: list = []
        last_reason = "retries_exhausted"
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                time.sleep(random.uniform(0.05, 0.4) * attempt)
            outbox = self._outbox_snapshot()
            _test_hook("after_snapshot", attempt=attempt)
            local = ors.resolve(self.root, L_REF)
            _test_hook("after_resolve_local", attempt=attempt, local=local)
            if self.mode() == "local_only":
                result = self._flush_local(outbox, local, reports)
            else:
                result = self._flush_remote(outbox, local, reports)
            status, payload = result
            if status == "done":
                return reports + payload
            if status == "retain":
                return reports + self._retain(outbox, payload)
            last_reason = payload or last_reason
        return reports + self._retain(self._outbox_snapshot(), last_reason)

    def _flush_local(self, outbox, local, reports):
        base_files = self._files(local)
        files, published, superseded = self._apply_outbox(base_files, outbox, reports)
        if not published:
            self._clear(superseded)
            return "done", ["NOTHING_TO_FLUSH"] if not outbox else []
        changes = {p: d for p, d in files.items() if base_files.get(p) != d}
        commit = ors.build_commit(self.root, local, changes, "ait: Update aitask-relations (local)")
        if ors.cas_local(self.root, L_REF, commit, local) != "OK":
            return "retry", "local_conflict"
        self._clear({**published, **superseded})
        return "done", [f"PUBLISHED:{len(published)}"]

    def _flush_remote(self, outbox, local, reports):
        probe = ors.probe_remote_branch(self.root, BRANCH, self.timeout, self.remote)
        if probe.startswith("ERROR:"):
            return "retain", probe[len("ERROR:"):]
        remote = None
        if probe == "PRESENT":
            remote, err = ors.fetch_pinned(self.root, BRANCH, self.timeout, self.remote)
            if err:
                return "retain", err
        _test_hook("after_pin", remote=remote, local=local)
        extra = []
        if remote is not None:
            extra += self._observe(remote)
            if not self.integrate(remote):
                return "retain", "integrate_failed"
            self._write_fetched_at()
        local = ors.resolve(self.root, L_REF)  # now contains remote
        local_work = local is not None and local != remote
        delta = 0
        if local_work:
            rfiles = self._files(remote)
            lfiles = self._files(local)
            delta = sum(1 for p in set(lfiles) | set(rfiles)
                        if lfiles.get(p) != rfiles.get(p) and p != SCHEMA_PATH)
        base_files = self._files(local)
        files, published, superseded = self._apply_outbox(base_files, outbox, reports)
        changes = {p: d for p, d in files.items() if base_files.get(p) != d}
        if not changes and not local_work:
            self._clear(superseded)
            return "done", extra + (["NOTHING_TO_FLUSH"] if not outbox else [])
        commit = local
        if changes:
            commit = ors.build_commit(self.root, local, changes, "ait: Update aitask-relations")
        status = ors.cas_push(self.root, commit, BRANCH, remote, self.timeout, self.remote)
        _test_hook("after_push", status=status, commit=commit)
        if status == "CONFLICT":
            return "retry", "push_conflict"
        if status != "OK":
            return "retain", status[len("ERROR:"):] if status.startswith("ERROR:") else status
        _test_hook("before_bookkeeping", commit=commit)
        extra += self._observe(commit)
        if not self.integrate(commit):
            return "done", extra + self._retain({**published, **superseded}, "integrate_failed")
        self._write_fetched_at()
        self._clear({**published, **superseded})
        out = extra + [f"PUBLISHED:{len(published)}"]
        if local_work:
            out.append(f"UPGRADED:{delta}")
        return "done", out

    def _write_fetched_at(self):
        _atomic_write(self.fetched_at_path, (_now() + "\n").encode())

    def _fetched_at(self):
        try:
            with open(self.fetched_at_path, encoding="utf-8") as fh:
                return fh.read().strip() or None
        except FileNotFoundError:
            return None

    # --------------------------------------------------------------- read
    def _refresh(self, no_fetch):
        """The network half of ``read()``: at most ONE probe + fetch per Store.

        Only the outcome of a real refresh is cached. The local branch and
        outbox view is recomputed on every ``read()``, so writes made through
        this Store (or anyone else) are always observed without a new fetch.
        """
        if self._refresh_outcome is not None:
            return self._refresh_outcome
        if self.mode() == "local_only":
            return ("local_only", None)
        if no_fetch:
            return ("no_fetch", None)  # not cached: a later read may still fetch once
        probe = ors.probe_remote_branch(self.root, BRANCH, self.timeout, self.remote)
        if probe.startswith("ERROR:"):
            outcome = ("failed", probe[len("ERROR:"):])
        elif probe == "ABSENT":
            self._write_fetched_at()
            outcome = ("absent", None)
        else:
            remote, err = ors.fetch_pinned(self.root, BRANCH, self.timeout, self.remote)
            if err:
                outcome = ("failed", err)
            else:
                self._observe(remote)
                if self.integrate(remote):
                    self._write_fetched_at()
                    outcome = ("fetched", None)
                else:
                    outcome = ("integrate_failed", None)
        self._refresh_outcome = outcome
        return outcome

    def read(self, no_fetch=False) -> Snapshot:
        kind, reason = self._refresh(no_fetch)
        local = ors.resolve(self.root, L_REF)
        outbox = self._outbox_snapshot()
        mode = self.mode()
        no_data = False
        if kind == "local_only":
            state = "local_only"
        elif kind == "no_fetch":
            state = (f"stale:no_fetch@{self._fetched_at() or 'never'}" if local
                     else "unreachable:no_fetch")
            no_data = local is None
        elif kind == "failed":
            state, no_data = self._failed_state(reason, local)
        elif kind == "absent":
            state = "empty" if (local is None and not outbox) else f"fresh@{self._fetched_at()}"
        elif kind == "fetched":
            state = f"fresh@{self._fetched_at()}"
        else:
            state = f"stale:integrate_failed@{self._fetched_at() or 'never'}"
        raw = {} if no_data else self._files(local)
        pending = set()
        if mode == "remote" and local is not None and not no_data:
            observed = ors.resolve(self.root, O_REF)
            if observed is None:
                pending |= {p for p in raw if p != SCHEMA_PATH}
            elif not ors.is_ancestor(self.root, local, observed):
                bases = ors.merge_bases(self.root, local, observed)
                bfiles = self._files(bases[0]) if bases else {}
                pending |= {p for p in raw if raw.get(p) != bfiles.get(p) and p != SCHEMA_PATH}
        corrupt = []
        for path, (data, _d) in outbox.items():
            obj, why = self._decode(path, data)
            if obj is None:
                corrupt.append(f"outbox/{path}|{why}")
                continue
            cur = raw.get(path)
            if cur is None or self._replaces(path, data, cur):
                raw[path] = data
                pending.add(path)
        files = {}
        for path, data in raw.items():
            if path == SCHEMA_PATH:
                continue
            obj, why = self._decode(path, data)
            if obj is None:
                corrupt.append(f"{path}|{why}")  # reported, never consumed
                pending.discard(path)
                continue
            files[path] = obj
        return Snapshot(state, local, files, pending, corrupt)

    # ------------------------------------------------------- decoding
    def _decode(self, path, data):
        """``(record, None)`` for a valid store file, else ``(None, reason)``.

        Every consumer reads records only through here (or ``_replaces``), so a
        malformed blob is reported and skipped, never compared or rendered.
        """
        parsed = rs.parse_store_path(path)
        if parsed is None:
            return None, "unknown_path"
        if data is None:
            return None, "absent"
        try:
            obj = _loads(data)
        except (ValueError, UnicodeDecodeError):
            return None, "invalid_json"
        try:
            rs.validate(parsed[0], path, obj)
        except (rs.SchemaError, KeyError, TypeError) as exc:
            text = str(exc).replace("|", "/").replace("\n", " ")
            return None, f"schema:{text}"[:200]
        if self.local_id(obj["task"]) is None:
            return None, "foreign_task_project"
        return obj, None

    def _replaces(self, path, new, cur) -> bool:
        """Should bytes ``new`` replace bytes ``cur`` at ``path`` (both present)?

        A valid record always beats an invalid one; of two invalid blobs the
        current one is kept. Two valid records go through ``wins()``.
        """
        n, _ = self._decode(path, new)
        c, _ = self._decode(path, cur)
        if n is None:
            return False
        if c is None:
            return True
        return wins(path.split("/", 1)[0], n, c, self._live(path))

    def _failed_state(self, reason, local):
        reason = reason.replace("|", "/")
        if local is not None:
            return f"stale:{reason}@{self._fetched_at() or 'never'}", False
        return f"unreachable:{reason}", True

    # ---------------------------------------------------------- relations
    # Every end is handled as a QUALIFIED ref (<project>#<id>). Only refs of
    # the local project go through the task index and the fold map; a ref of
    # another project keeps its qualification verbatim (D12: cross-project
    # relations are deferred, but never silently rewritten as local).

    def local_id(self, ref):
        """The bare id when ``ref`` names a task of THIS project, else None."""
        project, tid = rs.parse_ref(ref) if "#" in str(ref) else (self.project, rs.norm_id(ref))
        return tid if project == self.project else None

    def canonical_ref(self, value) -> str:
        """Qualified ref, folded ids of the local project canonicalized."""
        ref = self.ref(value)
        tid = self.local_id(ref)
        return self.ref(self.index.canonical(tid)) if tid is not None else ref

    def label(self, ref) -> str:
        tid = self.local_id(ref)
        return f"t{tid}" if tid is not None else ref

    def _record_identity_ok(self, rec) -> bool:
        tid = self.local_id(rec["task"])
        if tid is None:
            return False  # a record in this store always describes a local task
        entry = self.index.lookup(tid)
        if entry is None:
            return self.index.exists(tid) is not False
        return entry.created_at is None or rec.get("task_created_at") == entry.created_at

    def _candidate(self, rec, ref):
        want = rs.qref(ref)
        return next((c for c in rec["inputs"]["candidates"] if rs.qref(c["ref"]) == want), None)

    def _end_identity_ok(self, ref, rec) -> bool:
        cand = self._candidate(rec, ref)
        if cand is None:
            return False
        tid = self.local_id(ref)
        if tid is None:
            return True  # another project's task: not checkable here
        entry = self.index.lookup(tid)
        if entry is None:
            return self.index.exists(tid) is not False
        return entry.created_at is None or cand["created_at"] == entry.created_at

    def _baseline_plan(self, tid, snap):
        stamp = snap.files.get(rs.store_path("approvals", tid))
        live = self.index.live_created_at(tid)
        if stamp is not None and live is not None and stamp.get("task_created_at") == live:
            return stamp.get("plan_sha256")
        return self.index.plan_digest(tid)

    def _end_freshness(self, tid, recorded, snap):
        if tid is None:
            return "unverified"  # another project's baseline is not readable here
        body = self.index.body_digest(tid)
        plan = self._baseline_plan(tid, snap)
        if body is UNREADABLE or plan is UNREADABLE:
            return "unverified"
        if recorded.get("body_sha256") != body or recorded.get("plan_sha256") != plan:
            return "stale"
        return "fresh"

    def freshness(self, rel_raw, rec, snap) -> str:
        src = self._end_freshness(self.local_id(rec["task"]), rec["inputs"]["source"], snap)
        if src == "stale":
            return "stale:source_changed"
        if src == "unverified":
            return "unverified:source_baseline"
        own_ref = rs.qref(rec["task"])
        other = rel_raw["to"] if rs.qref(rel_raw["from"]) == own_ref else rel_raw["from"]
        cand = self._candidate(rec, other)
        if cand is None:
            return "unverified:target_baseline"
        tgt = self._end_freshness(self.local_id(other), cand, snap)
        if tgt == "stale":
            return "stale:target_changed"
        if tgt == "unverified":
            return "unverified:target_baseline"
        return "fresh"

    def _records(self, snap):
        for path, rec in snap.files.items():
            parsed = rs.parse_store_path(path)
            if parsed and parsed[0] == "records" and isinstance(rec, dict) \
                    and rec.get("analysed", True) and "relations" in rec:
                yield path, rec

    def relations(self, task_id, snap=None) -> list:
        snap = snap or self.read()
        x = self.canonical_ref(task_id)
        result, seen = [], set()
        for path, rec in self._records(snap):
            try:
                if not self._record_identity_ok(rec):
                    continue
                own = rs.qref(rec["task"])
                for raw in rec["relations"]:
                    f_ref, t_ref = rs.qref(raw["from"]), rs.qref(raw["to"])
                    fc, tc = self.canonical_ref(f_ref), self.canonical_ref(t_ref)
                    if fc == tc or x not in (fc, tc):
                        continue
                    other = t_ref if f_ref == own else f_ref
                    if not self._end_identity_ok(other, rec):
                        continue
                    other_id = self.local_id(other)
                    if other_id is not None and self.index.exists(other_id) is False:
                        continue
                    key = (fc, tc, raw["type"], own)
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append(Rel(
                        from_=fc, to=tc, other=tc if fc == x else fc, type=raw["type"],
                        description=raw["description"], basis=raw["basis"],
                        evidence=raw.get("evidence", []), record_task=own,
                        direction=self._direction(x, fc, tc, raw["type"]),
                        freshness=self.freshness(raw, rec, snap),
                        pending_push=path in snap.pending))
            except (KeyError, TypeError, rs.SchemaError):
                continue
        return result

    def _direction(self, x, fc, tc, rtype):
        verb = rtype.replace("_", " ")
        if rs.TYPES.get(rtype) == "symmetric":
            return f"this task {verb} {self.label(tc if fc == x else fc)}"
        if fc == x:
            return f"this task {verb} {self.label(tc)}"
        return f"{self.label(fc)} {verb} this task"

    def analysis_line(self, task_id, snap=None, relations_state=None) -> str:
        snap = snap or self.read()
        if snap.state.startswith("unreachable"):
            return "unknown(store_unreachable)"
        tid = self.local_id(self.canonical_ref(task_id))
        if tid is None:
            return "unknown(other_project)"  # its record lives in that project's store
        rec = snap.files.get(rs.store_path("records", tid))
        if isinstance(rec, dict) and rec.get("analysed") and self._record_identity_ok(rec):
            try:
                flags = [f"stage={rec['run']['stage']}"]
                if self._end_freshness(tid, rec["inputs"]["source"], snap) != "fresh":
                    flags.append("stale")
                if rec.get("coverage", {}).get("missing_sources"):
                    flags.append("partial")
                return f"analysed:{len(rec['relations'])}({','.join(flags)})"
            except (KeyError, TypeError):
                pass
        job = job_state(tid)
        if job:
            return job
        state = relations_state or self.relations_state()
        return "disabled" if state == "disabled" else "never"

    def relations_state(self) -> str:
        import config_utils
        try:  # read-only; honours TASK_DIR like the task index does
            cfg = config_utils.load_yaml_config(
                self.index.task_dir / "metadata" / "project_config.yaml")
        except Exception:  # an unreadable config is not "enabled"
            cfg = {}
        rel = cfg.get("relations") if isinstance(cfg, dict) else None
        enabled = isinstance(rel, dict) and rel.get("enabled") is True
        if not enabled:
            return "disabled"
        return "host_off" if os.environ.get("AIT_RELATIONS") == "0" else "enabled"

    # -------------------------------------------------------------- status
    def status(self) -> list:
        lines = []
        now = time.time()
        for path in self._outbox_paths():
            target = self._outbox_file(path)
            try:
                age = int(now - os.path.getmtime(target))
            except FileNotFoundError:
                continue
            err = "-"
            with contextlib.suppress(FileNotFoundError, ValueError):
                with open(target + ".err", "rb") as fh:
                    err = _loads(fh.read()).get("reason", "-")
            lines.append(f"OUTBOX:{path}|age={age}|err={err}")
        return lines or ["OUTBOX:none"]

    # ------------------------------------------------------------------ gc
    def gc(self, dry_run=False) -> list:
        self.index.full_scan()
        if self.index.errors:
            return [f"GC_REFUSED:scan_incomplete|{len(self.index.errors)}"]
        first_selection = None
        for attempt in range(MAX_ATTEMPTS):
            if attempt:
                time.sleep(random.uniform(0.05, 0.4) * attempt)
            local = ors.resolve(self.root, L_REF)
            remote = None
            remote_mode = self.mode() == "remote"
            if remote_mode:
                probe = ors.probe_remote_branch(self.root, BRANCH, self.timeout, self.remote)
                if probe.startswith("ERROR:"):
                    return [f"GC_REFUSED:{probe[6:]}"]
                if probe == "PRESENT":
                    remote, err = ors.fetch_pinned(self.root, BRANCH, self.timeout, self.remote)
                    if err:
                        return [f"GC_REFUSED:{err}"]
                    self._observe(remote)
                    if not self.integrate(remote):
                        return ["GC_REFUSED:integrate_failed"]
                local = ors.resolve(self.root, L_REF)
            outbox = self._outbox_snapshot()
            local_files = self._files(local)
            remote_files = self._files(remote)
            # E: exactly the tree the deletion commit is built from (plus the
            # outbox overlay). Eligibility is decided on E's blob only.
            effective, _pub, _sup = self._apply_outbox(local_files, outbox, [])
            # Pre-selection looks at every source blob (remote, local, outbox),
            # so a path whose E blob turns out valid is reported as kept.
            preselect = set()
            for source in (remote_files, local_files, {p: d for p, (d, _s) in outbox.items()}):
                for path, data in source.items():
                    if self.deletion_eligible(path, data):
                        preselect.add(path)
            ids = {rs.parse_store_path(p)[1] for p in preselect | set(first_selection or ())}
            self.index.refresh(ids)
            self._exists_cache.clear()
            selected = {}
            for path in sorted(preselect | set(first_selection or ())):
                reason = self.deletion_eligible(path, effective.get(path))
                if reason:
                    selected[path] = reason
            if first_selection is None:
                first_selection = {p: "preselected" for p in preselect}
            _test_hook("gc_after_select", attempt=attempt, selected=sorted(selected))
            kept = [f"GC_KEPT:{p}|revalidated" for p in sorted(first_selection) if p not in selected]
            if dry_run:
                return kept + [f"GC_WOULD_REMOVE:{p}|{r}" for p, r in sorted(selected.items())] \
                    or ["GC_NONE"]
            if not selected:
                return kept + ["GC_NONE"]
            base_files = local_files
            deletions = {p: None for p in selected if p in base_files}
            outbox_hits = {p: v for p, v in outbox.items()
                           if p in selected and self.deletion_eligible(p, v[0])}
            if deletions:
                commit = ors.build_commit(self.root, local, deletions, "ait: gc aitask-relations")
                if remote_mode:
                    status = ors.cas_push(self.root, commit, BRANCH, remote, self.timeout, self.remote)
                    if status == "CONFLICT":
                        continue
                    if status != "OK":
                        return [f"GC_REFUSED:{status}"]
                    self._observe(commit)
                    if not self.integrate(commit):
                        return kept + ["GC_REFUSED:integrate_failed"]
                elif ors.cas_local(self.root, L_REF, commit, local) != "OK":
                    continue
            self._clear(outbox_hits)
            return kept + [f"GC_REMOVED:{p}|{r}" for p, r in sorted(selected.items())]
        return ["GC_REFUSED:retries_exhausted"]


def hostname() -> str:
    return socket.gethostname()
