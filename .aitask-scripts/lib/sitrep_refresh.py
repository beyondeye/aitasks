#!/usr/bin/env python3
"""Deterministic refresh of the sitrep store's Part 1 (t2175_3).

The sitrep store (``.aitask-sitrep/todo.md``, written only by
``aitask_sitrep_todo.sh`` -- see ``lib/sitrep_todo.py``) holds what harvest
(t2175_2) and the sitrep agent (t2175_4) put there. Nothing in the store moves
by itself: "t2181 open" stays open after t2181 is archived. This module
re-checks every item it KNOWS HOW TO VERIFY against the real state and writes
the results back through ``set-state --batch``, so it changes item state,
``checked_at`` and the one-line outcome -- Part 1 only, never a context entry,
a title, a group or a dismissal.

TARGETS (exhaustive). Only items whose state is ``open`` or ``unknown``; a
``done`` or ``dismissed`` item is never re-checked or written.

* ``kind=task`` with ref ``t<N>[_<M>]`` -- the task in the canonical root;
* ``kind=task`` with ref ``<project>#<N>[_<M>]`` -- the same, in the root the
  project registry resolves (``aitask_projects.sh resolve``); unresolved ⇒
  ``unknown`` (cross-repo ids stay unverified unless the registry resolves
  them);
* ``kind=action`` with ref ``push:<branch>@<sha>`` -- git, in the canonical root;
* ``kind=watch`` with ``trail:`` context sources -- the trail artifact.

Everything else (``kind=question`` triage items, agent action/watch items with
none of these anchors, items without a ref) is NOT a target and is left
byte-identical. "Unverifiable ⇒ unknown" applies to a target whose check could
not complete -- never to an item refresh has no rule for.

EVIDENCE. An item flips to ``done`` only on POSITIVE evidence, and ``done`` is
irreversible (done items are not re-checked):

* task: active ``Done`` (not yet archived), archived ``Done``, or ``Folded`` --
  live, or found in another task's ``folded_tasks`` after the folded file was
  deleted. Ready / Editing / Implementing / Postponed stay ``open`` with the
  live status as the outcome. A lookup that cannot prove absence (an
  unlistable directory, an unreadable bundle) is ``unknown``, never "missing".
* push: done only when the commit is an ancestor of the remote-tracking ref of
  the branch's PUSH destination (``<branch>@{push}``), that ref belongs to the
  branch's configured push remote, and that remote's push URL is exactly its
  single fetch URL -- a remote-tracking ref is evidence only for the endpoint
  it is fetched from. NO FETCH, no network: a stale tracking ref keeps the item
  open (the outcome names the last fetch), it never makes it done.
* trail: an entry has LANDED only when its work is Done -- a Folded entry
  lands when the task it was merged into is Done (receiver chain, at most
  ``MAX_FOLD_HOPS`` hops, cycle-guarded), matching the board's By-Trail view.
  The trail item is done only when every entry landed. This is deliberately
  NOT the task-item rule: a folded task's own reminder closes on Folded, its
  trail entry does not.

CONCURRENCY. The worker reads one snapshot (``load_todo_for_read``, no lock --
the writer's atomic rename gives a whole generation) and every batch line
carries the rev the worker OBSERVED in that snapshot. The writer applies a line
only if the item still has that rev (``STALE:`` otherwise) and never touches a
dismissed item (``KEPT:``). Every change to an item OR its context entry gives
the item a fresh store-wide rev, so a verdict computed from an older kind, ref,
state or ``trail:`` source can never be applied. Stale lines are counted, never
retried; the next run re-reads. Two concurrent refreshes are safe by the same
rule. There is no refresh mutex.

DEADLINE. One budget (``--budget``, default 60 s) covers the whole run. The
PARENT (``run``) does no scan, git or helper call itself: it spawns the
WORKER (``worker``) in its own session, reads its line stream, and at the check
deadline (``budget - reserve``, ``reserve = min(15, budget/4)``) kills the
worker's whole PROCESS GROUP -- so reused helpers with their own fixed or
unbounded waits (``archive_iter``'s zstd pipe, ``canonical_root``'s git calls,
the project resolver, the artifact CLI) can never overrun. The writer then
gets what is left of the budget. A caller's hard timeout must be at least
``budget + CALLER_MARGIN`` (interpreter start and exit). If the parent itself
is killed from outside (the monitor's runner kills only its direct child), the
worker's parent watchdog notices the re-parenting and kills its own group --
an orphaned worker never keeps running a stalled helper. Only the parent
writes, so a killed run writes nothing.

PROGRESS. Targets are checked oldest ``checked_at`` first (``never`` first,
ties by id). Every reached target -- finished, or interrupted by the deadline
(written ``unknown``: its check could not complete) -- gets the run's stamp, so
the next run starts with the targets this one did not reach and an expensive
item rotates to the back instead of starving the others.

WORKER LINE PROTOCOL (one record per line, flushed; free text always LAST):
    ROOT:<canonical root>                     (the whole remainder)
    NONE:no_store | NONE:no_targets
    TARGETS:<n>
    START:c<N>|<snapshot rev>|<kind>|<old state>|<old outcome>
    VERDICT:c<N>|<new state>|<outcome>        (only for the open START)
    FAILED:<reason>

START carries the CAS token, so a target interrupted before its VERDICT is
written with the rev the worker observed -- never a re-read one.

The refresh never creates a store: a root without an established store is
``REFRESH_NONE:no_store`` and nothing is written (the writer's first-mutation
init must never run from here). The wire contract of the entry point is in
``aitask_sitrep_refresh.sh``.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import os
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sitrep_todo as st  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITER = os.path.join(SCRIPTS_DIR, "aitask_sitrep_todo.sh")
TRAIL_GATHER_SH = os.path.join(SCRIPTS_DIR, "aitask_trail_gather.sh")
STORE_NAME = ".aitask-sitrep"

DEFAULT_BUDGET = 60.0
# Upper bound on --budget: one day. Beyond it a deadline is meaningless, and a
# huge or infinite value would overflow the selector's timeout.
MAX_BUDGET = 86400.0
MAX_RESERVE = 15.0
CALLER_MARGIN = 15.0
GIT_CAP = 20.0
DRIFT_CAP = 15.0
MAX_FOLD_HOPS = 5
MAX_WAVE_TITLE = 60

OPEN_STATUSES = ("Ready", "Editing", "Implementing", "Postponed", "Blocked")

_CHILD_FILE_RE = re.compile(r"t\d+_\d+_")
_TASK_NAME_RE = re.compile(r"^t(\d+(?:_\d+)?)_")
_TRAIL_HANDLE_RE = re.compile(r"^art:trail-[A-Za-z0-9._-]+\Z")
_ENTRY_REF_RE = re.compile(r"^([a-z0-9_-]+)#t?(\d+(?:_\d+)?)\Z")


class WorkerFailure(Exception):
    """A worker-side failure that ends the run (reported as FAILED:<reason>)."""


# --- the shared deadline ------------------------------------------------------

class Deadline:
    """One budget for checks plus write. ``reserve`` is kept for the writer."""

    def __init__(self, budget: float, now=time.monotonic):
        self.budget = max(0.0, float(budget))
        self.reserve = min(MAX_RESERVE, self.budget / 4)
        self._now = now
        self.start = now()

    def check_left(self) -> float:
        return self.start + self.budget - self.reserve - self._now()

    def run_left(self) -> float:
        return self.start + self.budget - self._now()


# --- outcome hygiene ----------------------------------------------------------

_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(s: str) -> str:
    """One line, no `|` (the writer refuses it outside titles), no controls."""
    s = _CTRL_RE.sub(" ", str(s)).replace("|", "/")
    return re.sub(r"\s+", " ", s).strip()


def fit_outcome(segments: list) -> str:
    """Join cleaned segments with " · " and fit MAX_OUTCOME: whole trailing
    segments are dropped first, then the text is cut with a trailing "…"."""
    segs = [clean_text(x) for x in segments if clean_text(x)]
    limit = st.MAX_OUTCOME
    while segs:
        text = " · ".join(segs)
        if len(text) <= limit:
            return text
        if len(segs) == 1:
            return text[:limit - 1].rstrip() + "…"
        segs.pop()
    return ""


def fit_with_members(head: str, members: list, tail: list) -> str:
    """`head (m1, m2, …)` + tail segments, shortening the member list first
    (`…+k` names how many were dropped) before fit_outcome drops tail parts."""
    members = [clean_text(m) for m in members]
    for keep in range(len(members), 0, -1):
        shown = ", ".join(members[:keep])
        if keep < len(members):
            shown += f", …+{len(members) - keep}"
        first = f"{head} ({shown})"
        text = " · ".join([clean_text(first)] + [clean_text(t) for t in tail if clean_text(t)])
        if len(text) <= st.MAX_OUTCOME:
            return text
    return fit_outcome([f"{head} (+{len(members)})" if members else head] + list(tail))


# --- targets ------------------------------------------------------------------

@dataclasses.dataclass
class Target:
    num: int
    rev: int
    kind: str
    state: str
    outcome: str
    checked_at: str
    check: str            # task | push | trail
    ref: str = ""
    trails: tuple = ()


def select_targets(store: st.TodoStore) -> list:
    out = []
    for num in sorted(store.items):
        it = store.items[num]
        if it.state not in ("open", "unknown"):
            continue
        base = dict(num=num, rev=it.rev, kind=it.kind, state=it.state,
                    outcome=it.outcome, checked_at=it.checked_at, ref=it.ref)
        if it.kind == "task" and it.ref and not it.ref.startswith("push:"):
            out.append(Target(check="task", **base))
        elif it.kind == "action" and st.parse_push_ref(it.ref):
            out.append(Target(check="push", **base))
        elif it.kind == "watch":
            ctx = store.contexts.get(num)
            trails = tuple(p for t, p in (ctx.sources if ctx else []) if t == "trail")
            if trails:
                out.append(Target(check="trail", trails=trails, **base))
    return out


def order_targets(targets: list) -> list:
    """Oldest check first: `never`, then ascending ISO stamp; ties by id."""
    return sorted(targets, key=lambda t: (t.checked_at != "never", t.checked_at, t.num))


# --- task lookup --------------------------------------------------------------

@dataclasses.dataclass
class TaskFacts:
    found: str            # active | archived | fold_scan | missing | error
    status: str = ""
    folded_into: str = ""
    receiver: str = ""    # fold_scan: the task whose folded_tasks lists this id
    completed_at: str = ""
    detail: str = ""


def _bare(value) -> str:
    return str(value).strip().lstrip("t")


def _meta_of(text: str):
    import task_yaml
    parsed = task_yaml.parse_frontmatter(text)
    meta = parsed[0] if parsed else None
    return meta if isinstance(meta, dict) else None


def _facts(found: str, meta: dict) -> TaskFacts:
    fi = meta.get("folded_into")
    return TaskFacts(found=found, status=str(meta.get("status") or "").strip(),
                     folded_into=_bare(fi) if fi not in (None, "") else "",
                     completed_at=str(meta.get("completed_at") or "").strip())


class TaskIndex:
    """Fail-closed task lookups for ONE root (the shape of
    ``trail_links.lookup_task_meta``, rooted explicitly), with the per-run
    fold-scan cache."""

    def __init__(self, root: str):
        self.root = root
        self.base = Path(root) / "aitasks"
        self._cache = {}
        self._folds = None        # folded id -> [receiver ids]
        self._fold_errors = []

    def lookup(self, tid: str) -> TaskFacts:
        tid = _bare(tid)
        if tid not in self._cache:
            self._cache[tid] = self._lookup(tid)
        return self._cache[tid]

    def _lookup(self, tid: str) -> TaskFacts:
        from archive_iter import checked_glob, find_archived_markdown_by_id
        errors: list = []
        if "_" in tid:
            active = checked_glob(self.base / f"t{tid.split('_', 1)[0]}",
                                  f"t{tid}_*.md", errors)
        else:
            active = [p for p in checked_glob(self.base, f"t{tid}_*.md", errors)
                      if not _CHILD_FILE_RE.match(p.name)]
        if active:
            path = sorted(active)[0]
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                meta = _meta_of(text)
            except Exception as exc:  # noqa: BLE001 - unreadable is not absent
                return TaskFacts("error", detail=f"{path.name}: {exc}")
            if meta is None:
                return TaskFacts("error", detail=f"{path.name}: unparseable frontmatter")
            return _facts("active", meta)
        if errors:
            # The active location could not be listed: an archived copy is not
            # the answer, and absence is not proven.
            return TaskFacts("error", detail=errors[0])
        found = find_archived_markdown_by_id(tid, self.base / "archived", errors=errors)
        if errors:
            return TaskFacts("error", detail=errors[0])
        if found is not None:
            try:
                meta = _meta_of(found[1])
            except Exception as exc:  # noqa: BLE001
                return TaskFacts("error", detail=f"{found[0]}: {exc}")
            if meta is None:
                return TaskFacts("error", detail=f"{found[0]}: unparseable frontmatter")
            return _facts("archived", meta)
        return self._fold_lookup(tid)

    def _fold_lookup(self, tid: str) -> TaskFacts:
        if self._folds is None:
            self._build_folds()
        if self._fold_errors:
            return TaskFacts("error", detail=f"fold scan: {self._fold_errors[0]}")
        receivers = sorted(set(self._folds.get(tid, [])))
        if len(receivers) == 1:
            return TaskFacts("fold_scan", status="Folded", receiver=receivers[0])
        if len(receivers) > 1:
            return TaskFacts("error", detail="listed in the folded_tasks of "
                             + ", ".join("t" + r for r in receivers))
        return TaskFacts("missing")

    def _build_folds(self) -> None:
        """One scan per run: the folded_tasks of every task's AUTHORITATIVE
        record -- the one `_lookup` would read. Precedence per task id, the
        same as `find_archived_markdown_by_id` behind the active file: active,
        then a loose archived file, then the id's OWN numbered ``.tar.zst``,
        then its own ``.tar.gz`` (also when a zst counterpart exists -- direct
        lookup falls back to it per id), then the legacy ``old.tar.*``. A stale archived copy of an active task, or a copy
        in some other bundle, is never read as a fold relationship.

        Any read or parse failure of a task-named record is a scan error --
        malformed YAML, a missing closing delimiter, and a record with no
        frontmatter at all, active or archived alike: an incomplete scan cannot
        prove where a task went, so the lookup answers unknown."""
        from archive_iter import (archive_path_for_id, archived_markdown_sources,
                                  checked_glob, iter_archive_file,
                                  iter_legacy_archive, read_loose_markdown)
        errors: list = []
        best: dict = {}           # task id -> (rank, meta)
        archived = self.base / "archived"

        def take(name: str, text, rank: int, where) -> None:
            m = _TASK_NAME_RE.match(os.path.basename(name))
            if not m or text is None:
                return
            tid = m.group(1)
            if tid in best and best[tid][0] <= rank:
                return
            try:
                meta = _meta_of(text)
            except Exception as exc:  # noqa: BLE001 - malformed YAML
                errors.append(f"{where}: {name}: {exc}")
                return
            if meta is None:
                errors.append(f"{where}: {name}: unparseable frontmatter")
                return
            best[tid] = (rank, meta)

        # rank 0: active files (parents at the top, children in t<N>/).
        paths = [p for p in checked_glob(self.base, "t*.md", errors)
                 if not _CHILD_FILE_RE.match(p.name)]
        for d in checked_glob(self.base, "t*", errors):
            if re.match(r"^t\d+$", d.name) and d.is_dir():
                paths.extend(checked_glob(d, "t*_*.md", errors))
        for p in paths:
            try:
                take(p.name, p.read_text(encoding="utf-8", errors="replace"), 0, p)
            except OSError as exc:
                errors.append(f"{p}: {exc}")

        def bundle(path: Path) -> None:
            # rank 2: the id's own .tar.zst; rank 3: its own .tar.gz -- the
            # per-id fallback find_archived_markdown_by_id reads when the record
            # is absent from the zst (so a zst copy always wins).
            rank = 2 if path.name.endswith(".tar.zst") else 3
            for name, text in iter_archive_file(path, errors=errors):
                m = _TASK_NAME_RE.match(name)
                if not m:
                    continue
                own = archive_path_for_id(int(m.group(1).split("_")[0]), archived)
                if path not in (own, own.with_suffix("").with_suffix(".tar.gz")):
                    continue      # find_archived_markdown_by_id never reads it
                take(name, text, rank, path)

        # rank 1: loose archived files; then the numbered bundles.
        for kind, path in archived_markdown_sources(archived, errors=errors):
            if kind == "loose":
                take(path.name, read_loose_markdown(path, errors), 1, path)
            else:
                bundle(path)
        # The .tar.gz bundles archived_markdown_sources leaves out because a
        # .tar.zst counterpart exists: direct lookup still falls back to them.
        for gz in checked_glob(archived, "_b*/old*.tar.gz", errors):
            if gz.with_suffix("").with_suffix(".tar.zst").exists():
                bundle(gz)
        # rank 4: the legacy old.tar.zst / old.tar.gz.
        for name, text in iter_legacy_archive(archived, errors=errors):
            take(name, text, 4, archived / "old.tar.*")

        folds: dict = {}
        for tid, (_rank, meta) in best.items():
            listed = meta.get("folded_tasks") or []
            if not isinstance(listed, list):
                listed = [listed]
            for f in listed:
                folds.setdefault(_bare(f), []).append(tid)
        self._folds = folds
        self._fold_errors = errors


@dataclasses.dataclass
class Verdict:
    state: str
    outcome: str


def describe(facts: TaskFacts) -> str:
    """Short live-state label of a task, for receiver/owner mentions."""
    if facts.found == "active":
        return facts.status or "no status"
    if facts.found == "archived":
        return "archived" if facts.status == "Done" else f"archived {facts.status}"
    if facts.found == "fold_scan":
        return f"folded into t{facts.receiver}"
    return "not found" if facts.found == "missing" else "unreadable"


def reminder_verdict(facts: TaskFacts, receiver=None) -> Verdict:
    """A task ITEM (a reminder). `receiver` is the receiving task's facts, used
    only to say where a folded task went."""
    def folded(into: str) -> Verdict:
        if not into:
            return Verdict("done", "folded")
        where = f"folded into t{into}"
        if receiver is not None and receiver.found in ("active", "archived"):
            where += f" (t{into}: {describe(receiver)})"
        return Verdict("done", where)

    if facts.found == "error":
        return Verdict("unknown", f"lookup failed: {facts.detail}")
    if facts.found == "missing":
        return Verdict("unknown", "task file not found")
    if facts.found == "fold_scan":
        return folded(facts.receiver)
    if facts.status == "Folded":
        return folded(facts.folded_into)
    if facts.found == "archived":
        if facts.status == "Done":
            date = facts.completed_at[:10]
            return Verdict("done", f"archived (completed {date})" if date else "archived")
        return Verdict("unknown", f"archived with status {facts.status or '(none)'}")
    if facts.status == "Done":
        return Verdict("done", "status: Done (not yet archived)")
    if not facts.status:
        return Verdict("unknown", "task file has no status")
    return Verdict("open", f"status: {facts.status}")


def landed_state(tid: str, lookup) -> tuple:
    """(landed | open | unverifiable, chain of bare ids) for a trail entry.
    Landed ⇔ the work is Done: a Folded entry follows its receiver."""
    chain = [_bare(tid)]
    for _hop in range(MAX_FOLD_HOPS + 1):
        facts = lookup(chain[-1])
        if facts.found in ("error", "missing"):
            return "unverifiable", chain
        if facts.status == "Done" and facts.found in ("active", "archived"):
            return "landed", chain
        nxt = facts.receiver if facts.found == "fold_scan" else (
            facts.folded_into if facts.status == "Folded" else None)
        if nxt is None:
            if facts.found == "archived":
                return "unverifiable", chain
            return ("open" if facts.status else "unverifiable"), chain
        if not nxt or nxt in chain:
            return "unverifiable", chain
        chain.append(nxt)
    return "unverifiable", chain


# --- project resolution -------------------------------------------------------

class Projects:
    def __init__(self, root: str):
        self.root = root
        self._cache = {}
        self._local = None

    def resolve(self, name: str) -> str:
        if name not in self._cache:
            import sitrep_harvest
            path = sitrep_harvest.resolve_project(name)
            self._cache[name] = path if path and os.path.isdir(path) else ""
        return self._cache[name]

    def local_name(self) -> str:
        if self._local is None:
            try:
                import trail_gather
                self._local = trail_gather.local_project_name()
            except (SystemExit, Exception):  # noqa: BLE001 - absent name ⇒ ""
                self._local = ""
        return self._local


# --- push ---------------------------------------------------------------------

def _git(root: str, *args: str, cap: float = GIT_CAP):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    try:
        p = subprocess.run(["git", "-C", root, *args], capture_output=True,
                           text=True, timeout=cap, env=env)
    except subprocess.TimeoutExpired:
        raise
    except OSError:
        return 127, ""
    return p.returncode, p.stdout


def _fetched(root: str) -> str:
    rc, out = _git(root, "rev-parse", "--git-common-dir")
    if rc != 0 or not out.strip():
        return "never"
    common = out.strip()
    if not os.path.isabs(common):
        common = os.path.join(root, common)
    try:
        mtime = os.stat(os.path.join(common, "FETCH_HEAD")).st_mtime
    except OSError:
        return "never"
    return time.strftime("%Y-%m-%d %H:%MZ", time.gmtime(mtime))


def push_verdict(root: str, branch: str, sha: str) -> Verdict:
    rc, out = _git(root, "rev-parse", "--is-inside-work-tree")
    if rc != 0 or out.strip() != "true":
        return Verdict("unknown", "not a git repository")
    if _git(root, "check-ref-format", "--branch", branch)[0] != 0:
        return Verdict("unknown", f"invalid branch name {branch}")
    if _git(root, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")[0] != 0:
        return Verdict("unknown", f"commit {sha[:7]} not in this repository")
    if _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")[0] != 0:
        return Verdict("unknown", f"no local branch {branch}")
    no_dest = Verdict("unknown", f"no remote push destination for {branch}")
    rc, out = _git(root, "rev-parse", "--symbolic-full-name", f"{branch}@{{push}}")
    dest = out.strip()
    if rc != 0 or not dest.startswith("refs/remotes/"):
        return no_dest
    # The push remote, from config (the same precedence git uses for @{push}).
    remote = ""
    for key in (f"branch.{branch}.pushRemote", "remote.pushDefault", f"branch.{branch}.remote"):
        rc, val = _git(root, "config", "--get", key)
        if rc == 0 and val.strip():
            remote = val.strip()
            break
    rc, out = _git(root, "remote")
    remotes = out.split() if rc == 0 else []
    if not remote or remote == "." or remote not in remotes \
            or not dest.startswith(f"refs/remotes/{remote}/"):
        return no_dest
    # A remote with no configured URL is NOT "no URL" to `get-url`: git then
    # reports the remote's NAME as its URL. So the raw config must name one.
    rc, raw = _git(root, "config", "--get-all", f"remote.{remote}.url")
    if rc != 0 or not [u for u in raw.splitlines() if u.strip()]:
        return no_dest
    rc_f, fetch = _git(root, "remote", "get-url", "--all", remote)
    rc_p, push = _git(root, "remote", "get-url", "--push", "--all", remote)
    fetch_urls = [u for u in fetch.splitlines() if u.strip()]
    push_urls = [u for u in push.splitlines() if u.strip()]
    if rc_f != 0 or rc_p != 0 or not fetch_urls:
        return no_dest
    if len(fetch_urls) != 1 or push_urls != fetch_urls:
        return Verdict("unknown", f"push URL differs from fetch URL ({remote}); "
                       "not verifiable without network")
    short = dest[len("refs/remotes/"):]
    rc, _ = _git(root, "merge-base", "--is-ancestor", sha, dest)
    if rc == 0:
        return Verdict("done", f"pushed: {sha[:7]} is on {short}")
    if rc != 1:
        return Verdict("unknown", f"cannot compare {sha[:7]} with {short}")
    rc, out = _git(root, "rev-list", "--left-right", "--count",
                   f"refs/heads/{branch}...{dest}")
    counts = out.split()
    if rc != 0 or len(counts) != 2:
        return Verdict("open", f"not pushed: {sha[:7]} is not on {short} "
                       f"(fetched {_fetched(root)})")
    return Verdict("open", f"not pushed: {branch} {counts[0]} ahead / {counts[1]} "
                   f"behind {short} (fetched {_fetched(root)})")


# --- trail --------------------------------------------------------------------

def run_drift(root: str, handle: str) -> str:
    try:
        p = subprocess.run([TRAIL_GATHER_SH, "drift", "--trail", handle],
                           capture_output=True, text=True, timeout=DRIFT_CAP, cwd=root)
    except (subprocess.TimeoutExpired, OSError):
        return "drift unavailable"
    lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    if p.returncode != 0 or not lines:
        return "drift unavailable"
    if lines[0] == "CURRENT":
        return "drift CURRENT"
    if lines[0] == "STALE":
        return f"drift STALE ({sum(1 for ln in lines[1:] if ln.startswith('DRIFT:'))})"
    return "drift error"


def entry_label(project: str, tid: str, local: str) -> str:
    return f"t{tid}" if project == local else f"{project}#{tid}"


def trail_verdict(doc: dict, entry_state, drift: str, owner: str = "") -> Verdict:
    """`entry_state(task_ref) -> (state, label)` with state landed / open /
    unverifiable. Pure: the lookups are injected."""
    waves = sorted(doc.get("waves") or [], key=lambda w: w.get("ordinal", 0))
    total = len(waves)
    any_open = False
    nxt = None
    for k, wave in enumerate(waves, start=1):
        pending = []
        for entry in wave.get("entries") or []:
            state, label = entry_state(entry.get("task", ""))
            if state == "open":
                any_open = True
                pending.append(label)
            elif state == "unverifiable":
                pending.append(label + "?")
        if pending and nxt is None:
            nxt = (k, wave, pending)
    gen = str(((doc.get("generation") or {}).get("generated_at")) or "")[:10]
    tail = [drift]
    if gen:
        tail.append(f"generated {gen}")
    if owner:
        tail.append(owner)
    if nxt is None:
        return Verdict("done", fit_outcome([f"all {total} waves landed"] + tail))
    k, wave, pending = nxt
    title = clean_text(wave.get("title") or wave.get("wave_id") or "")
    if len(title) > MAX_WAVE_TITLE:   # a long title must not crowd out the facts
        title = title[:MAX_WAVE_TITLE - 1].rstrip() + "…"
    head = f"next wave {k}/{total} {title}".strip()
    outcome = fit_with_members(f"{head}: {len(pending)} pending", pending, tail)
    return Verdict("open" if any_open else "unknown", outcome)


# --- the worker ---------------------------------------------------------------

class Checker:
    def __init__(self, root: str):
        self.root = root
        self.projects = Projects(root)
        self._indexes = {root: TaskIndex(root)}

    def index(self, root: str) -> TaskIndex:
        if root not in self._indexes:
            self._indexes[root] = TaskIndex(root)
        return self._indexes[root]

    def check(self, t: Target) -> Verdict:
        if t.check == "task":
            return self.check_task(t.ref)
        if t.check == "push":
            branch, sha = st.parse_push_ref(t.ref)
            return push_verdict(self.root, branch, sha)
        return self.check_trail(t.trails)

    def check_task(self, ref: str) -> Verdict:
        m = st.XREF_RE.match(ref)
        if m:
            proj, tid = m.group(1), m.group(2)
            root = self.projects.resolve(proj)
            if not root:
                return Verdict("unknown", f"cross-repo: project {proj} not resolved")
            v = self._reminder(self.index(root), tid)
            return Verdict(v.state, fit_outcome([f"{proj}: {v.outcome}"]))
        m = st.LOCAL_REF_RE.match(ref)
        if not m:
            return Verdict("unknown", f"unsupported ref {ref}")
        return self._reminder(self.index(self.root), m.group(1))

    @staticmethod
    def _reminder(idx: TaskIndex, tid: str) -> Verdict:
        facts = idx.lookup(tid)
        into = facts.receiver if facts.found == "fold_scan" else (
            facts.folded_into if facts.status == "Folded" else "")
        receiver = idx.lookup(into) if into else None
        v = reminder_verdict(facts, receiver)
        return Verdict(v.state, fit_outcome([v.outcome]))

    def entry_state(self, ref: str) -> tuple:
        local = self.projects.local_name()
        m = _ENTRY_REF_RE.match(ref or "")
        if not m:
            return "unverifiable", clean_text(ref or "?")
        proj, tid = m.group(1), m.group(2)
        root = self.root if proj == local and local else self.projects.resolve(proj)
        if not root:
            return "unverifiable", entry_label(proj, tid, local)
        state, chain = landed_state(tid, self.index(root).lookup)
        label = "→".join(entry_label(proj, c, local) for c in chain)
        return state, label

    def owner_text(self, ref: str) -> str:
        local = self.projects.local_name()
        m = _ENTRY_REF_RE.match(ref or "")
        if not m:
            return ""
        proj, tid = m.group(1), m.group(2)
        if not local or proj != local:
            return f"owner {proj}#{tid}"
        return f"owner t{tid} {describe(self.index(self.root).lookup(tid))}"

    def check_trail(self, trails: tuple) -> Verdict:
        if len(trails) > 1:
            return Verdict("unknown", "several trail sources")
        handle = trails[0]
        if not _TRAIL_HANDLE_RE.match(handle):
            return Verdict("unknown", f"unsupported trail pointer {clean_text(handle)}")
        import trail_discovery
        seam = os.environ.get("AITASK_SITREP_REFRESH_ARTIFACT_SH", "")
        if seam:
            trail_discovery.ARTIFACT_SCRIPT = Path(seam)
        loaded = trail_discovery.load_trail_blob(handle)
        doc, error = loaded[0], loaded[1]
        if doc is None:
            return Verdict("unknown", fit_outcome([f"trail unreadable: {error or handle}"]))
        drift = run_drift(self.root, handle)
        return trail_verdict(doc, self.entry_state, drift, self.owner_text(doc.get("owner", "")))


def _emit(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _watch_parent(ppid: int, interval: float = 0.25) -> None:
    """The worker's own backstop: if its parent dies (a caller killed the run
    from outside -- the monitor's runner kills only the direct child), kill the
    worker's whole process group, which includes any helper it is blocked in.
    A daemon thread, so it runs while the main thread waits on a subprocess."""
    import threading

    def loop():
        while True:
            time.sleep(interval)
            if os.getppid() != ppid:
                try:
                    os.killpg(os.getpgrp(), signal.SIGKILL)
                finally:
                    os._exit(1)

    threading.Thread(target=loop, name="parent-watch", daemon=True).start()


def cmd_worker(args) -> int:
    import sitrep_harvest
    _watch_parent(args.parent if args.parent else os.getppid())
    try:
        root, _is_git = sitrep_harvest.canonical_root(os.path.abspath(args.root))
    except sitrep_harvest.HarvestFailure as e:
        _emit(f"FAILED:root:{e}")
        return 0
    _emit(f"ROOT:{root}")
    store_dir = os.path.join(root, STORE_NAME)
    if not os.path.isdir(store_dir) or "ESTABLISHED=0" in st.store_state(store_dir):
        _emit("NONE:no_store")
        return 0
    try:
        snapshot = st.load_todo_for_read(store_dir)
    except st.FormatError as e:
        _emit(f"FAILED:store_unusable:{clean_text(e)}")
        return 0
    targets = order_targets(select_targets(snapshot))
    if not targets:
        _emit("NONE:no_targets")
        return 0
    _emit(f"TARGETS:{len(targets)}")
    os.chdir(root)  # the artifact CLI and trail libs are cwd-relative
    checker = Checker(root)
    for t in targets:
        _emit(f"START:c{t.num}|{t.rev}|{t.kind}|{t.state}|{t.outcome}")
        try:
            v = checker.check(t)
        except subprocess.TimeoutExpired:
            v = Verdict("unknown", "timed out")
        except Exception as exc:  # noqa: BLE001 - one target never ends the run
            v = Verdict("unknown", f"check error: {type(exc).__name__}")
        _emit(f"VERDICT:c{t.num}|{v.state}|{fit_outcome([v.outcome])}")
    return 0


# --- the parent ---------------------------------------------------------------

class ProtocolError(Exception):
    pass


@dataclasses.dataclass
class Line:
    num: int
    rev: int
    kind: str
    old_state: str
    old_outcome: str
    state: str = ""
    outcome: str = ""
    interrupted: bool = False


class Stream:
    """The parent's view of the worker's line stream (pure, unit-tested)."""

    def __init__(self):
        self.root = ""
        self.none = ""
        self.failed = ""
        self.targets = 0
        self.lines = []          # finished Line records
        self.open = None         # the START without a VERDICT yet

    def feed(self, raw: str) -> None:
        tag, _, rest = raw.partition(":")
        if tag == "ROOT" and not self.root:
            self.root = rest
        elif tag == "NONE" and self.root:
            self.none = rest
        elif tag == "FAILED":
            self.failed = rest
        elif tag == "TARGETS" and self.root and re.match(r"^\d+\Z", rest):
            self.targets = int(rest)
        elif tag == "START" and self.root:
            if self.open is not None:
                raise ProtocolError(f"START while c{self.open.num} is open")
            parts = rest.split("|", 4)
            m = re.match(r"^c([1-9][0-9]*)\Z", parts[0])
            if len(parts) != 5 or not m or not re.match(r"^[1-9][0-9]*\Z", parts[1]):
                raise ProtocolError(f"bad START {raw!r}")
            self.open = Line(int(m.group(1)), int(parts[1]), parts[2], parts[3], parts[4])
        elif tag == "VERDICT" and self.root:
            parts = rest.split("|", 2)
            if self.open is None or len(parts) != 3 or parts[0] != f"c{self.open.num}":
                raise ProtocolError(f"VERDICT without its START: {raw!r}")
            if parts[1] not in ("open", "done", "unknown"):
                raise ProtocolError(f"bad VERDICT state {raw!r}")
            self.open.state, self.open.outcome = parts[1], parts[2]
            self.lines.append(self.open)
            self.open = None
        else:
            raise ProtocolError(f"unexpected worker line {raw!r}")

    def close(self, interrupted: bool, budget: float) -> list:
        """The batch lines: finished verdicts, plus the target the deadline
        interrupted (written unknown, with ITS snapshot rev)."""
        out = list(self.lines)
        if self.open is not None:
            if not interrupted:
                raise ProtocolError(f"worker ended with c{self.open.num} open")
            self.open.state = "unknown"
            self.open.outcome = f"check did not finish within the {budget:g}s budget"
            self.open.interrupted = True
            out.append(self.open)
            self.open = None
        return out


def _kill_group(proc) -> None:
    """SIGKILL the child's whole process group. Only ever called while the
    group leader is still UNREAPED (alive or a zombie): until it is reaped its
    pid -- and so the pgid -- cannot be reused, so this can never hit an
    unrelated group."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass


def _exited_unreaped(pid: int, timeout: float) -> bool:
    """Wait up to `timeout` for `pid` to exit WITHOUT reaping it (WNOWAIT)."""
    end = time.monotonic() + max(0.0, timeout)
    while True:
        try:
            if os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
                return True
        except ChildProcessError:
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.02)


def supervise(cmd: list, deadline: Deadline, env=None):
    """Run the worker in its own session; return (Stream, interrupted, rc, err).
    At the check deadline the whole process group is killed."""
    stream = Stream()
    errf = tempfile.TemporaryFile()
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=errf, start_new_session=True, env=env)
    except OSError as e:
        errf.close()
        raise WorkerFailure(f"worker_spawn:{e.strerror or e}") from None
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    buf = b""
    interrupted = False
    proto = None
    try:
        while True:
            left = deadline.check_left()
            if left <= 0:
                interrupted = True
                break
            if not sel.select(timeout=left):
                continue
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                try:
                    stream.feed(raw.decode("utf-8", "replace"))
                except ProtocolError as e:
                    proto = str(e)
                    interrupted = True
                    break
            if proto:
                break
    finally:
        sel.close()
        if not interrupted and not _exited_unreaped(proc.pid, deadline.check_left()):
            interrupted = True
        # Kill the group on EVERY path -- a grandchild must not outlive the
        # run -- and always BEFORE reaping the leader (see _kill_group).
        _kill_group(proc)
        rc = proc.wait()
        proc.stdout.close()
        errf.seek(0)
        err = errf.read().decode("utf-8", "replace")
        errf.close()
    if proto:
        raise WorkerFailure(f"worker_protocol:{clean_text(proto)}")
    return stream, interrupted, rc, err


def _pause(point: str) -> None:
    fifo = os.environ.get("AITASK_SITREP_REFRESH_PAUSE_FIFO", "")
    if not fifo:
        return
    with open(fifo + ".reached", "w", encoding="utf-8") as fh:
        fh.write(point + "\n")
    with open(fifo, encoding="utf-8") as fh:
        fh.readline()


def run_writer(root: str, batch: str, deadline: Deadline, restart: bool):
    """`set-state --batch` from what is left of the budget; returns its lines.
    `restart`: the pause seam held the run, so the write gets a fresh reserve."""
    left = deadline.reserve if restart else deadline.run_left()
    if left <= 0:
        raise WorkerFailure("deadline")
    env = dict(os.environ, AITASK_SITREP_DIR=os.path.join(root, STORE_NAME),
               AITASK_SITREP_LOCK_TIMEOUT=str(int(max(1, min(10, left - 3)))))
    try:
        proc = subprocess.Popen([WRITER, "set-state", "--batch"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=root, env=env, start_new_session=True)
    except OSError as e:
        raise WorkerFailure(f"writer:spawn:{e.strerror or e}") from None
    try:
        out, err = proc.communicate(batch.encode("utf-8"), timeout=max(1.0, left))
    except subprocess.TimeoutExpired:
        _kill_group(proc)   # communicate() did not reap it: the pgid is safe
        proc.communicate()
        raise WorkerFailure("writer_timeout") from None
    if proc.returncode == 3:
        raise WorkerFailure("lock_busy")
    if proc.returncode == 4:
        raise WorkerFailure("store_unusable")
    if proc.returncode != 0:
        detail = (err.decode("utf-8", "replace").strip().splitlines() or [""])[-1]
        raise WorkerFailure(f"writer:exit{proc.returncode}:{clean_text(detail)}")
    return out.decode("utf-8", "replace").splitlines()


def _results(writer_lines: list) -> dict:
    res = {}
    for ln in writer_lines:
        for tag, word in (("STATE:c", "applied"), ("STALE:c", "stale"),
                          ("KEPT:c", "kept"), ("NOT_FOUND:c", "not_found")):
            if ln.startswith(tag):
                num = re.match(r"^([0-9]+)", ln[len(tag):])
                if num:
                    res[int(num.group(1))] = word
    return res


def cmd_run(args) -> int:
    budget = args.budget
    deadline = Deadline(budget)
    try:
        ts = st.now_ts()
    except st.RequestError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    cmd = [sys.executable, os.path.abspath(__file__), "worker", "--root", args.root,
           "--parent", str(os.getpid())]
    try:
        stream, interrupted, rc, err = supervise(cmd, deadline)
    except WorkerFailure as e:
        print(f"REFRESH_FAILED:{e}")
        return 1
    if stream.failed:
        print(f"REFRESH_FAILED:{stream.failed}")
        return 1
    if not stream.root:
        if err.strip():
            sys.stderr.write(err)
        print("REFRESH_FAILED:deadline" if interrupted else f"REFRESH_FAILED:worker:{rc}")
        return 1
    if stream.none:
        print(f"REFRESH_NONE:{stream.none}")
        return 0
    if not interrupted and rc != 0:
        if err.strip():
            sys.stderr.write(err)
        print(f"REFRESH_FAILED:worker:{rc}")
        return 1
    try:
        lines = stream.close(interrupted, budget)
    except ProtocolError as e:
        print(f"REFRESH_FAILED:worker_protocol:{clean_text(e)}")
        return 1
    not_reached = stream.targets - len(lines)
    if not_reached > 0:
        print(f"REFRESH_WARN:budget_exhausted|{not_reached} not reached")
    if not lines:
        print("REFRESH_FAILED:deadline")
        return 1
    batch = "".join(f"c{ln.num}|{ln.rev}|{ln.state}|{ts}|{ln.outcome}\n" for ln in lines)
    log = os.environ.get("AITASK_SITREP_REFRESH_BATCH_LOG", "")
    if log:
        with open(log, "w", encoding="utf-8") as fh:
            fh.write(batch)
    if args.dry_run:
        results = {ln.num: "dry_run" for ln in lines}
    else:
        paused = bool(os.environ.get("AITASK_SITREP_REFRESH_PAUSE_FIFO"))
        _pause("refresh:before_write")
        try:
            results = _results(run_writer(stream.root, batch, deadline, paused))
        except WorkerFailure as e:
            print(f"REFRESH_FAILED:{e}")
            return 1
    counts = dict(checked=len(lines), changed=0, stale=0, kept=0, unknown=0)
    for ln in lines:
        res = results.get(ln.num, "not_found")
        print(f"REFRESH_ITEM:c{ln.num}|{ln.kind}|{ln.old_state}->{ln.state}|{res}|{ln.outcome}")
        if res in ("applied", "dry_run"):
            if (ln.state, ln.outcome) != (ln.old_state, ln.old_outcome):
                counts["changed"] += 1
            if ln.state == "unknown":
                counts["unknown"] += 1
        elif res in ("stale", "kept"):
            counts[res] += 1
    print("REFRESHED:" + "|".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sitrep_refresh.py")
    sub = p.add_subparsers(dest="op", required=True)
    r = sub.add_parser("run")
    r.add_argument("--root", default=".")
    r.add_argument("--budget", type=float, default=None)
    r.add_argument("--dry-run", action="store_true")
    w = sub.add_parser("worker")
    w.add_argument("--root", required=True)
    w.add_argument("--parent", type=int, default=0)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if args.op == "worker":
        return cmd_worker(args)
    if args.budget is None:
        raw = os.environ.get("AITASK_SITREP_REFRESH_BUDGET", "")
        try:
            args.budget = float(raw) if raw else DEFAULT_BUDGET
        except ValueError:
            print(f"Error: AITASK_SITREP_REFRESH_BUDGET={raw!r} is not a number",
                  file=sys.stderr)
            return 2
    if not math.isfinite(args.budget) or not 0 <= args.budget <= MAX_BUDGET:
        print(f"Error: the budget must be a number of seconds between 0 and {MAX_BUDGET:g} "
              f"(got {args.budget!r})", file=sys.stderr)
        return 2
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
