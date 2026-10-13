#!/usr/bin/env python3
"""trail_links - cross-repo linked-trail discovery (t1957_3).

Finds, for one trail of this repository, the **linked** trails stored in other
registered repositories. Trail B (repo Y) is linked to trail A (repo X) when:

- ``fwd-xdeps``  a member of A has ``xdeprepo: Y`` and an ``xdeps`` id that is a
  member of B;
- ``fwd-member`` A has a cross-repo member ``Y#id`` that is a member of B;
- ``rev-xdeps``  a member of B has ``xdeprepo: X`` and an ``xdeps`` id that is a
  member of A;
- ``rev-member`` B has a cross-repo member ``X#id`` that is a member of A.

Identity is ``(realpath(project root), task_id)``. A project name is always
resolved to a root (through ``aitask_project_resolve.sh``, the registry
resolver) and never compared as a string, because a registry name, a tmux
session name and ``project.name`` may all differ. Ownership is root-based on
**both** sides: a member is "of B" when its name resolves to B's root, whatever
spelling the trail used — ``project.name``, a registry alias, or (in a repo with
no ``project.name``) any name the resolver maps there. That is why the export
never decides ownership: it emits the metadata of every member id, and the
scanner, which knows every root, picks the own ones.

Three layers:

- ``export`` (``python3 trail_links.py export``) runs with cwd = another repo's
  root and ``TASK_DIR=aitasks``. It is this checkout's code reading that repo's
  files and calling that repo's (cwd-relative) artifact CLI, so it works against
  a repo on an older framework.
- ``find_linked_trails`` is pure: exported data plus a resolver in, links out.
- ``scan_linked_trails`` (thread-worker use only — it spawns one export per
  candidate project) never skips a project silently: a candidate that could not
  be searched, or was searched only in part, becomes a ``ProjectScanError``, and
  ``complete`` is ``not errors``. An incomplete scan must never be shown as a
  definitive "no linked trails".

Invocation contract: cwd is the project root and ``TASK_DIR`` is read per call
(``config_utils.task_dir``), as in ``trail_discovery``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import yaml

from archive_iter import checked_glob, find_archived_markdown_by_id
from config_utils import task_dir
from cross_repo_deps import xdep_ref_pairs
from cross_repo_notation import parse_ref
from task_yaml import parse_frontmatter
from trail_discovery import discover_trails, trail_entry_refs

#: Absolute path of this file, captured at import: the export re-execs it with
#: cwd set to another repository, where a relative path would not resolve.
_THIS_FILE = os.path.abspath(__file__)
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(_THIS_FILE))
_RESOLVER = os.path.join(_SCRIPTS_DIR, "aitask_project_resolve.sh")

EXPORT_FORMAT = 1
#: The export prints its result as ONE line with this prefix and the scanner
#: reads only that line. stdout is not otherwise clean: under PyPy (the
#: board's fast path, whose ``sys.executable`` the scan re-uses) importing
#: PyYAML's C extension prints cpyext type diagnostics to stdout.
EXPORT_PREFIX = "TRAIL_LINKS_EXPORT:"
EXPORT_TIMEOUT = 30
RESOLVE_TIMEOUT = 30

#: The file whose presence makes a registered path an aitasks project root
#: (the same marker ``agent_launch_utils._read_registry_index`` checks).
_PROJECT_MARKER = Path("aitasks") / "metadata" / "project_config.yaml"
_PROJECT_NAME_RE = re.compile(r"[a-z0-9_-]+")
_CHILD_FILE_RE = re.compile(r"t\d+_\d+_")

#: ``ProjectScanError.kind`` values.
STALE = "stale"                        # registered path moved or missing
NOT_FOUND = "not_found"                # name does not resolve
EXPORT_FAILED = "export_failed"        # export crashed / printed no valid JSON
TIMEOUT = "timeout"                    # export exceeded EXPORT_TIMEOUT
PARTIAL = "partial"                    # searched, but some data was unreadable
REGISTRY_UNREADABLE = "registry_unreadable"   # project = registry path
LOCAL_UNREADABLE = "local_unreadable"  # a member of the local trail unreadable


@dataclass(frozen=True)
class LinkedTrail:
    project: str             # the name the project was searched under
    root: str                # realpath of its root
    handle: str
    name: str
    reasons: tuple           # sorted "fwd-xdeps: …" / "rev-member: …" strings


@dataclass(frozen=True)
class ProjectScanError:
    project: str
    kind: str
    detail: str


@dataclass(frozen=True)
class LinkScan:
    links: list
    errors: list
    complete: bool


@dataclass(frozen=True)
class ProjectExport:
    project: str
    root: str
    data: dict


# --- Readers (cwd-relative) --------------------------------------------------

def _local_project_name() -> str:
    """``project.name`` of the cwd project, or ``""`` when absent/unreadable.

    Never fatal: most registered repos predate the field, and a repo without it
    is still searchable — its members are then owned through the resolver.
    "Unreadable" includes invalid UTF-8 (``UnicodeDecodeError`` is a
    ``ValueError``, not an ``OSError``)."""
    path = task_dir() / "metadata" / "project_config.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError, yaml.YAMLError):
        return ""
    project = data.get("project") if isinstance(data, dict) else None
    if isinstance(project, dict) and project.get("name"):
        return str(project["name"]).strip()
    return ""


def _meta_state(meta) -> dict:
    """The ``ok`` record for one parsed frontmatter mapping."""
    xdeps = meta.get("xdeps") or []
    if not isinstance(xdeps, list):
        xdeps = [xdeps]
    pairs = xdep_ref_pairs(meta.get("xdeprepo"), xdeps)
    return {"state": "ok",
            "xdeprepo": pairs[0][0] if pairs else "",
            "xdeps": [xid for _repo, xid in pairs]}


def _parsed_meta(name: str, text: str) -> dict:
    try:
        parsed = parse_frontmatter(text)
        meta = parsed[0] if parsed else None
    except Exception as exc:
        return {"state": "unreadable", "detail": f"{name}: {exc}"}
    if not isinstance(meta, dict):
        return {"state": "unreadable", "detail": f"{name}: unparseable frontmatter"}
    return _meta_state(meta)


def lookup_task_meta(task_id: str) -> dict:
    """Cross-repo dependency metadata of one task of the cwd project.

    ``{"state": "ok", "xdeprepo", "xdeps"}`` (xdeps normalized, both empty
    unless both fields are set), ``{"state": "missing"}`` when no active or
    archived file exists, or ``{"state": "unreadable", "detail"}`` when a file
    exists but cannot be read — or a directory listing or archive lookup
    failed, so absence cannot be proven. Active files win over archived ones."""
    tid = str(task_id).lstrip("t")
    base = task_dir()
    errors: list = []
    if "_" in tid:
        active = checked_glob(base / f"t{tid.split('_', 1)[0]}",
                              f"t{tid}_*.md", errors)
    else:
        active = [p for p in checked_glob(base, f"t{tid}_*.md", errors)
                  if not _CHILD_FILE_RE.match(p.name)]
    if active:
        path = active[0]
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"state": "unreadable", "detail": f"{path.name}: {exc}"}
        return _parsed_meta(path.name, text)
    if errors:
        # Active files take precedence, so when the active location could not
        # be listed an archived copy is not the answer: the active file it
        # hides may carry the xdeps.
        return {"state": "unreadable", "detail": "; ".join(errors)}
    found = find_archived_markdown_by_id(tid, base / "archived", errors=errors)
    if errors:
        # The archive lookup stops at its first hit, so every failure it
        # recorded lies at a location that precedes the hit (loose before
        # bundle) — a hit after a failure is not authoritative either.
        return {"state": "unreadable", "detail": "; ".join(errors)}
    if found is None:
        return {"state": "missing"}
    return _parsed_meta(*found)


# --- Export side -------------------------------------------------------------

def build_export() -> dict:
    """The cwd project's trails, members and member metadata, as one dict.

    ``tasks`` covers every id named by any member ref, whatever project name
    the ref uses: ownership is decided by the scanner, by root."""
    scan_errors: list = []
    infos, unreadable = discover_trails(scan_errors=scan_errors)
    trails = []
    ids = set()
    for info in infos:
        members = sorted(trail_entry_refs(info.doc)) if info.doc else []
        for ref in members:
            parsed = parse_ref(ref)
            if parsed:
                ids.add(parsed[1])
        title = str((info.doc or {}).get("title") or "")
        trails.append({
            "handle": info.handle,
            "name": info.name or title or info.handle,
            "title": title,
            "owner_id": info.owner_id,
            "load_error": info.load_error,
            "members": members,
        })
    return {
        "format": EXPORT_FORMAT,
        "local_project": _local_project_name(),
        "unreadable": sorted(unreadable),
        "scan_errors": scan_errors,
        "trails": trails,
        "tasks": {tid: lookup_task_meta(tid) for tid in sorted(ids)},
    }


# --- Pure relation -----------------------------------------------------------

@dataclass
class _Side:
    own: dict          # identity -> raw member ref
    foreign: dict      # identity -> raw member ref
    xdeps: dict        # target identity -> {"<ref> xdeps <repo>#<id>", …}
    unreadable: dict   # task id -> detail (own members whose meta is unknown)


def _project_root(name, own_project, own_root, resolve):
    if own_project and name == own_project:
        return own_root
    return resolve(name) if name else None


def _side(members, tasks, own_project, own_root, resolve) -> _Side:
    """Classify one trail's members by root and collect its xdep targets."""
    side = _Side({}, {}, {}, {})
    for ref in members:
        parsed = parse_ref(str(ref or ""))
        if not parsed:
            continue
        root = _project_root(parsed[0], own_project, own_root, resolve)
        if not root:
            continue
        bucket = side.own if root == own_root else side.foreign
        bucket.setdefault((root, parsed[1]), str(ref))
    for (_root, tid), ref in side.own.items():
        meta = tasks.get(tid)
        state = meta.get("state") if isinstance(meta, dict) else None
        if state == "missing":
            continue
        if state != "ok":
            side.unreadable[tid] = (meta or {}).get("detail") or "not exported"
            continue
        repo = meta.get("xdeprepo") or ""
        target_root = _project_root(repo, own_project, own_root, resolve)
        if not target_root:
            continue
        for xid in meta.get("xdeps") or []:
            side.xdeps.setdefault((target_root, str(xid)), set()).add(
                f"{ref} xdeps {repo}#{xid}")
    return side


def _unreadable_detail(unreadable: dict) -> str:
    return "; ".join(f"t{tid}: {detail}"
                     for tid, detail in sorted(unreadable.items()))


def find_linked_trails(local_doc, local_tasks, local_project, local_root,
                       exports, resolve):
    """``(links, errors)`` for the local trail against exported trails.

    Pure given a pure ``resolve(name) -> realpath | None``. ``local_tasks`` and
    each export's ``tasks`` map a bare task id to a ``lookup_task_meta``
    record. An own member whose record is unreadable (or absent) cannot
    contribute xdeps: it is reported — ``local_unreadable`` for this trail,
    ``partial`` for an exported one — and every other link is still returned."""
    local_root = str(local_root)
    local = _side(sorted(trail_entry_refs(local_doc or {})), local_tasks or {},
                  local_project, local_root, resolve)
    errors = []
    if local.unreadable:
        errors.append(ProjectScanError(local_project or "(this project)",
                                       LOCAL_UNREADABLE,
                                       _unreadable_detail(local.unreadable)))
    links = []
    for exp in exports:
        data = exp.data
        tasks = data.get("tasks") or {}
        own_project = str(data.get("local_project") or "")
        unreadable: dict = {}
        for trail in data.get("trails") or []:
            if trail.get("load_error"):
                continue
            other = _side(trail.get("members") or [], tasks, own_project,
                          exp.root, resolve)
            unreadable.update(other.unreadable)
            reasons = set()
            for ident, details in local.xdeps.items():
                if ident in other.own:
                    reasons.update(f"fwd-xdeps: {d}" for d in details)
            for ident, ref in local.foreign.items():
                if ident in other.own:
                    reasons.add(f"fwd-member: {ref}")
            for ident, details in other.xdeps.items():
                if ident in local.own:
                    reasons.update(f"rev-xdeps: {d}" for d in details)
            for ident, ref in other.foreign.items():
                if ident in local.own:
                    reasons.add(f"rev-member: {ref}")
            if reasons:
                links.append(LinkedTrail(
                    project=exp.project, root=exp.root,
                    handle=str(trail.get("handle")),
                    name=str(trail.get("name") or trail.get("handle")),
                    reasons=tuple(sorted(reasons))))
        if unreadable:
            errors.append(ProjectScanError(
                exp.project, PARTIAL,
                f"unreadable task(s): {_unreadable_detail(unreadable)}"))
    links.sort(key=lambda link: (link.project, link.handle))
    return links, _merge_errors(errors)


def _merge_errors(errors) -> list:
    """One error per (project, kind); distinct details are joined."""
    merged: dict = {}
    for err in errors:
        details = merged.setdefault((err.project, err.kind), [])
        if err.detail and err.detail not in details:
            details.append(err.detail)
    return [ProjectScanError(project, kind, "; ".join(details))
            for (project, kind), details in merged.items()]


# --- Scan (thread-worker use only) -------------------------------------------

def _registry_path() -> str:
    return (os.environ.get("AITASKS_PROJECTS_INDEX")
            or os.path.expanduser("~/.config/aitasks/projects.yaml"))


def _read_registry() -> list:
    """``[(name, path)]`` of the per-user registry. RAISES when a registry that
    exists cannot be read (a missing file is an empty registry): the plain
    ``aitask_project_resolve.sh list`` folds that failure into empty output,
    which would make an unsearched registry look searched."""
    from agent_launch_utils import _parse_registry_records_strict
    return [(rec.name, rec.path) for rec in _parse_registry_records_strict()]


def _resolve_name(name: str) -> tuple:
    """``(status, path_or_detail)`` from ``aitask_project_resolve.sh <name>``;
    status is ``RESOLVED``, ``STALE`` or ``NOT_FOUND`` (any failure)."""
    if not _PROJECT_NAME_RE.fullmatch(name or ""):
        return ("NOT_FOUND", "not a project name")
    try:
        out = subprocess.run(
            [_RESOLVER, name], capture_output=True, text=True,
            errors="replace", timeout=RESOLVE_TIMEOUT, check=False).stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ("NOT_FOUND", f"resolver failed: {exc}")
    for line in out.splitlines():
        if line.startswith("RESOLVED:"):
            return ("RESOLVED", line[len("RESOLVED:"):])
        if line.startswith(f"STALE:{name}:"):
            return ("STALE", line[len(f"STALE:{name}:"):])
        if line.startswith("NOT_FOUND:"):
            return ("NOT_FOUND", "not registered")
    return ("NOT_FOUND", "resolver gave no answer")


class _Resolver:
    """Per-scan cache over ``_resolve_name``. Used from the scanning thread
    only — the export pool never resolves."""

    def __init__(self):
        self._cache: dict = {}

    def lookup(self, name: str) -> tuple:
        if name not in self._cache:
            self._cache[name] = _resolve_name(name)
        return self._cache[name]

    def root(self, name: str):
        status, path = self.lookup(name)
        return os.path.realpath(path) if status == "RESOLVED" and path else None


def _run_export(root: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, _THIS_FILE, "export"], cwd=root,
        env={**os.environ, "TASK_DIR": "aitasks"},
        # errors="replace": undecodable bytes from another repo's run (a
        # traceback, interpreter noise) must become an error row, never a
        # UnicodeDecodeError escaping the scan's worker thread.
        capture_output=True, text=True, errors="replace",
        timeout=EXPORT_TIMEOUT)


def _valid_export(data) -> bool:
    if not isinstance(data, dict) or data.get("format") != EXPORT_FORMAT:
        return False
    trails = data.get("trails")
    if not isinstance(trails, list) or not isinstance(data.get("tasks"), dict):
        return False
    return all(isinstance(t, dict) and isinstance(t.get("handle"), str)
               and isinstance(t.get("members"), list) for t in trails)


def _collect_export(name: str, root: str):
    """``(ProjectExport | None, [ProjectScanError])`` for one candidate."""
    try:
        proc = _run_export(root)
    except subprocess.TimeoutExpired:
        return None, [ProjectScanError(name, TIMEOUT,
                                       f"export exceeded {EXPORT_TIMEOUT}s")]
    except OSError as exc:
        return None, [ProjectScanError(name, EXPORT_FAILED, str(exc))]
    lines = (proc.stderr or "").strip().splitlines()
    if proc.returncode != 0:
        detail = lines[-1] if lines else f"exit {proc.returncode}"
        return None, [ProjectScanError(name, EXPORT_FAILED, detail)]
    records = [line[len(EXPORT_PREFIX):]
               for line in (proc.stdout or "").splitlines()
               if line.startswith(EXPORT_PREFIX)]
    try:
        data = json.loads(records[-1]) if records else None
    except ValueError:
        data = None
    if not _valid_export(data):
        return None, [ProjectScanError(name, EXPORT_FAILED,
                                       "export printed no valid result")]
    parts = []
    if data.get("unreadable"):
        parts.append("unreadable task file(s): "
                     + ", ".join(map(str, data["unreadable"])))
    if data.get("scan_errors"):
        parts.append("read failure(s): "
                     + "; ".join(map(str, data["scan_errors"])))
    failed = [t["handle"] for t in data["trails"] if t.get("load_error")]
    if failed:
        parts.append("unloadable trail(s): " + ", ".join(failed))
    errors = [ProjectScanError(name, PARTIAL, "; ".join(parts))] if parts else []
    return ProjectExport(name, root, data), errors


def scan_linked_trails(local_doc, *, local_root=".", local_project=None,
                       local_tasks=None, max_workers=4) -> LinkScan:
    """Search every candidate project for trails linked to ``local_doc``.

    Candidates are the registry entries plus every project the trail points at
    directly (its members' ``xdeprepo`` and its cross-repo members), so a
    project missing from the registry is still searched or reported. Blocking
    and subprocess-heavy: call from a thread worker, never the UI thread."""
    local_root = os.path.realpath(local_root)
    if local_project is None:
        local_project = _local_project_name()
    resolver = _Resolver()
    members = sorted(trail_entry_refs(local_doc or {}))
    own_ids = []
    for ref in members:
        parsed = parse_ref(ref)
        if parsed and (_project_root(parsed[0], local_project, local_root,
                                     resolver.root) == local_root):
            own_ids.append(parsed[1])
    if local_tasks is None:
        local_tasks = {tid: lookup_task_meta(tid) for tid in own_ids}

    errors = []
    candidates: dict = {}            # realpath -> name, in discovery order
    try:
        records = _read_registry()
    except (OSError, ValueError) as exc:
        errors.append(ProjectScanError(_registry_path(), REGISTRY_UNREADABLE,
                                       str(exc)))
        records = []
    for name, path in records:
        if not name:
            continue
        if not path:
            # The strict reader keeps name-only rows; `ait projects list`
            # shows them as stale. Still a project that was not searched.
            errors.append(ProjectScanError(name, STALE, "no path registered"))
            continue
        if not (Path(path) / _PROJECT_MARKER).is_file():
            errors.append(ProjectScanError(name, STALE, path))
            continue
        root = os.path.realpath(path)
        if root != local_root:
            candidates.setdefault(root, name)

    direct = []
    for ref in members:
        parsed = parse_ref(ref)
        if parsed and parsed[0] != local_project:
            direct.append(parsed[0])
    for tid in own_ids:
        meta = local_tasks.get(tid) or {}
        if meta.get("state") == "ok" and meta.get("xdeprepo"):
            direct.append(meta["xdeprepo"])
    for name in dict.fromkeys(direct):
        status, path = resolver.lookup(name)
        if status == "RESOLVED":
            root = os.path.realpath(path)
            if root != local_root:
                candidates.setdefault(root, name)
        elif status == "STALE":
            errors.append(ProjectScanError(name, STALE, path))
        else:
            errors.append(ProjectScanError(name, NOT_FOUND, path))

    exports = []
    if candidates:
        items = list(candidates.items())
        workers = max(1, min(max_workers, len(items)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda item: _collect_export(item[1], item[0]),
                                    items))
        for export, export_errors in results:
            errors.extend(export_errors)
            if export is not None:
                exports.append(export)

    links, relation_errors = find_linked_trails(
        local_doc, local_tasks, local_project, local_root, exports,
        resolver.root)
    errors = _merge_errors(errors + relation_errors)
    return LinkScan(links=links, errors=errors, complete=not errors)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="trail_links.py",
        description="Cross-repo linked-trail discovery. `export` prints this "
                    "project's trails and member metadata as one "
                    f"`{EXPORT_PREFIX}<json>` line (run with cwd = the "
                    "project root).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export", help="print this project's trail export as JSON")
    args = parser.parse_args(argv)
    if args.cmd == "export":
        sys.stdout.write(EXPORT_PREFIX
                         + json.dumps(build_export(), sort_keys=True) + "\n")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
