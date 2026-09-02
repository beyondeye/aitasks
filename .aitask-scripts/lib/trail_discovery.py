#!/usr/bin/env python3
"""trail_discovery - frontmatter-driven discovery of implementation trails
(promoted out of the board in t1647_1; RFC aidocs/implementation_trail_design.md
par.5, par.9, par.12).

Pure, import-testable core shared by the board's By-Trail view and the
trail-merge surfaces (the t1647_3 preflight helper and, through it, the
/aitask-merge-trails skill). Discovery, dedup, overlap computation and blob
loading live here; rendering (lanes, glyphs, summary text, drift display) stays
in the board.

Invocation contract: cwd must be the project root (the `ait` dispatcher / skill
convention -- same as lib/trail_gather.py and the artifact CLI, whose config
paths are cwd-relative). TASK_DIR overrides the task directory and is read
**per call** via `_tasks_dir()`, never cached at import: the board test fixture
loads a fresh board module per synthetic tree but this module is imported once
for the whole single-process suite, so a module-level constant would freeze to
whichever tree happened to load first and silently scan the wrong one.

READ-ONLY contract: the only subprocesses ever spawned are the `artifact get`
and `artifact versions` read verbs. Every trail WRITE happens in the launched
skill after its own confirmation (RFC par.9.3, par.12).

NOTE FOR TESTS: these functions call each other through THIS module's namespace.
A test that stubs one of them (or ARTIFACT_SCRIPT) for a caller that also lives
here must patch it on `trail_discovery`, not on the board -- the board's names
are re-export bindings and rebinding them does not affect resolution here.
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from archive_iter import iter_archived_frontmatter
from config_utils import task_dir
from task_yaml import parse_frontmatter
from topic_semantics import parse_task_filename, _task_id_sort_key
import trail_schema


TRAIL_ARTIFACT_KIND = "implementation_trail"

ARTIFACT_SCRIPT = Path(".aitask-scripts") / "aitask_artifact.sh"


def _tasks_dir() -> Path:
    """Task directory, resolved **per call** from the environment.

    Deliberately not a module-level constant: see the module docstring. Mirrors
    `trail_gather._local_dirs()`, which resolves the same way for the same
    reason."""
    return task_dir()


@dataclass
class TrailInfo:
    """One discovered trail (selection-modal row). ``load_error`` non-empty ⇒
    the blob failed to resolve or validate — fail-closed error card (§9.2),
    with ``versions`` as the read-only fallback listing."""
    handle: str
    owner_id: str            # bare local id of the winning owner ("635", "635_2")
    owner_archived: bool
    owner_folded: bool
    name: str = ""           # advisory frontmatter name
    doc: dict | None = None
    load_error: str = ""
    versions: list = field(default_factory=list)


def trail_entry_refs(doc) -> set:
    """All entry task refs of a trail document (overlap computation)."""
    refs = set()
    for wave in doc.get("waves") or []:
        for entry in wave.get("entries") or []:
            ref = entry.get("task")
            if ref:
                refs.add(str(ref))
    return refs


def compute_trail_overlaps(infos):
    """Per-handle "also in" notes (§9.2): ``{handle: [(task_ref, other_title)]}``
    for every entry ref shared with another discovered trail."""
    members = {}
    titles = {}
    for info in infos:
        if not info.doc:
            continue
        members[info.handle] = trail_entry_refs(info.doc)
        titles[info.handle] = str(info.doc.get("title") or info.handle)
    overlaps = {}
    for handle, refs in members.items():
        notes = []
        for other, other_refs in members.items():
            if other == handle:
                continue
            for ref in sorted(refs & other_refs):
                notes.append((ref, titles[other]))
        overlaps[handle] = notes
    return overlaps


def _trail_owner_rank(info: TrailInfo):
    """Dedup precedence for one handle listed by several owners (a fold copies
    the handle to the primary without stripping the folded task's entry):
    active non-folded > active folded > archived; tie → lowest owner id."""
    if info.owner_archived:
        state = 2
    elif info.owner_folded:
        state = 1
    else:
        state = 0
    return (state, _task_id_sort_key(info.owner_id or "999999999"))


def dedupe_trail_records(records):
    """Collapse discovery records to one ``TrailInfo`` per handle using
    ``_trail_owner_rank`` (first-seen order preserved for equal handles)."""
    best = {}
    order = []
    for rec in records:
        cur = best.get(rec.handle)
        if cur is None:
            best[rec.handle] = rec
            order.append(rec.handle)
        elif _trail_owner_rank(rec) < _trail_owner_rank(cur):
            best[rec.handle] = rec
    return [best[h] for h in order]


def _iter_active_task_frontmatter(unreadable=None):
    """Yield ``(filename, metadata)`` for every live task file, read from disk.

    The two glob patterns mirror ``TaskManager.load_tasks`` /
    ``load_child_tasks``, but the files are re-read rather than taken from the
    manager on purpose: its dicts are a board-STARTUP snapshot, so a trail whose
    owning task gained its ``artifacts:`` frontmatter after launch stayed
    invisible until a restart (t1365).

    Any file that does not yield a frontmatter mapping is skipped, and — when it
    is **task-named** — its name is appended to ``unreadable`` (if a list is
    supplied). Skipping is mandatory rather than defensive: the only consumer is
    a ``@work(thread=True)`` worker and Textual's ``exit_on_error=True`` default
    turns an escaped exception into board exit, yet ``parse_frontmatter`` RAISES
    on malformed YAML. Reporting is what stops a torn read from masquerading as
    "there are no trails".

    Both failure shapes matter, and they do not look alike: a file cut mid-YAML
    makes ``parse_frontmatter`` RAISE, while an empty / delimiter-truncated one
    makes it return ``None``. Treating only the raise as a failure would leave
    the *more likely* window silent.

    **No in-tree writer produces either shape any more.** t1371 converted
    ``frontmatter_patch``; t1379 converted the rest — ``Task.save`` above and
    ``aitask_merge`` through ``lib/atomic_write.py``, and every shell writer of a
    task or plan file (``aitask_update.sh``'s ``write_task_file``,
    ``aitask_create.sh``, ``aitask_issue_import.sh``, ``aitask_plan_verified.sh``,
    ``aitask_plan_externalize.sh``) through ``lib/atomic_write.sh``. All of them
    now render into a temp staged beside the target and rename it into place, so
    a scan racing any of them sees the whole old file or the whole new one.

    The guard nevertheless stays, for what atomicity does not cover: a file
    hand-edited into malformed YAML, one written by tooling outside this repo, a
    truncated checkout, and any writer added later that forgets the helper.
    ``parse_frontmatter`` RAISES on malformed YAML whatever produced it, and this
    is a ``@work(thread=True)`` worker under ``exit_on_error=True`` — so the
    guard is load-bearing regardless of how the bad bytes got there. What changed
    is the *likelihood*, not the necessity: a report here used to mean "you raced
    a writer" and now means "this file is genuinely broken".

    The task-named qualifier is what keeps that honest without crying wolf: a
    ``.md`` file under the task dir whose name is not ``t<N>_…`` is a document,
    not a task, and reporting it would warn on every scan forever."""
    for pattern in ("*.md", "t*/t*_*.md"):
        for path in sorted(_tasks_dir().glob(pattern)):
            try:
                parsed = parse_frontmatter(
                    path.read_text(encoding="utf-8", errors="replace"))
                meta = parsed[0] if parsed else None
            except Exception:
                meta = None
            if isinstance(meta, dict):
                yield path.name, meta
            elif unreadable is not None and parse_task_filename(path.name)[0]:
                unreadable.append(path.name)


def _iter_trail_frontmatter_records(unreadable=None):
    """Yield raw ``TrailInfo`` records from active + archived task frontmatter
    (`artifacts:` entries with kind == implementation_trail). Discovery is
    frontmatter-driven — the artifact manifest stores no kind (RFC §5) — and
    BOTH halves are read from disk, never from the manager's startup snapshot
    (t1365).

    ``unreadable`` collects skipped **active** task files only: the archived
    half goes through ``iter_archived_frontmatter``, which swallows read and
    parse failures internally."""
    def _records(filename, meta, archived):
        task_num, _name = parse_task_filename(filename)
        folded = bool(meta.get("folded_into")) or meta.get("status") == "Folded"
        for rec in meta.get("artifacts") or []:
            if (isinstance(rec, dict) and rec.get("handle")
                    and rec.get("kind") == TRAIL_ARTIFACT_KIND):
                yield TrailInfo(
                    handle=str(rec["handle"]),
                    owner_id=(task_num or "").lstrip("t"),
                    owner_archived=archived,
                    owner_folded=folded,
                    name=str(rec.get("name") or ""),
                )

    for filename, meta in _iter_active_task_frontmatter(unreadable):
        yield from _records(filename, meta, False)

    def _parse_meta(text):
        result = parse_frontmatter(text)
        return result[0] if result else None

    for filename, meta in iter_archived_frontmatter(
            _tasks_dir() / "archived", _parse_meta):
        if isinstance(meta, dict):
            yield from _records(filename, meta, True)


def _trail_versions(handle: str) -> list:
    """Read-only ``ait artifact versions`` listing (§9.2 fallback). Best-effort."""
    try:
        result = subprocess.run(
            [str(ARTIFACT_SCRIPT), "versions", handle],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return [ln.rstrip() for ln in result.stdout.splitlines()
                    if ln.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return []


def load_trail_blob(handle: str):
    """Fetch + validate a trail blob. Returns ``(doc, error, versions)``.

    Fail-closed (RFC §12): a get failure or schema-invalid document yields
    ``doc=None`` with a non-empty ``error`` and the versions fallback — never
    a partial document. Read-only: only ``get``/``versions`` are spawned."""
    import tempfile
    doc = None
    error = ""
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="ait_trail_", suffix=".json")
        os.close(fd)
        result = subprocess.run(
            [str(ARTIFACT_SCRIPT), "get", handle, "--out", tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            diag = (result.stderr or result.stdout).strip().splitlines()
            error = f"artifact unresolved: {diag[-1] if diag else handle}"
        else:
            try:
                doc = trail_schema.load_trail(tmp_path)
            except trail_schema.TrailValidationError as exc:
                error = f"invalid trail document: {len(exc.issues)} issue(s)"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        error = f"artifact unresolved: {exc}"
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    versions = _trail_versions(handle) if error else []
    return doc, error, versions


def discover_trails():
    """Frontmatter-driven trail discovery, deduped by handle, blobs loaded and
    validated (fail-closed into ``load_error``). Subprocess-heavy — call from
    a thread worker, never the UI thread.

    Returns ``(infos, unreadable)``. ``unreadable`` names the active task files
    the scan could not read, so a caller can tell "there are no trails" apart
    from "part of the scan failed" — the two must not look alike, because the
    second is a retryable race (t1365)."""
    unreadable = []
    infos = dedupe_trail_records(_iter_trail_frontmatter_records(unreadable))
    for info in infos:
        info.doc, info.load_error, info.versions = load_trail_blob(info.handle)
    return infos, unreadable
