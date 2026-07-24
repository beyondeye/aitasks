#!/usr/bin/env python3
"""trail_gather - deterministic gatherer + drift checker for implementation
trails (t1210_2; RFC aidocs/implementation_trail_design.md par.7-8; T2).

Two verbs, both read-only:

  snapshot --scope task|topic|multi_topic [--owner <id>] <ids...>
      Resolve scope + owner, build the RFC par.8.1 normalized input records
      over the member tasks, and emit them with their input_digest.
  drift --trail <path>
      Recompute the digest of a stored trail document against live state and
      name the drift reasons. Handle (art:...) resolution lives in the bash
      wrapper aitask_trail_gather.sh -- this module only ever sees a path.

Invocation contract: cwd must be the project root (the `ait` dispatcher /
skill convention -- same as aitask_work_report_gather.sh and the artifact
CLI, whose config paths are cwd-relative). TASK_DIR / PLAN_DIR /
ARCHIVED_DIR env override the local directory layout (tests). Foreign
(cross-repo) projects resolved via aitask_project_resolve.sh are assumed to
use the default aitasks/ + aiplans/ layout.

LINE PROTOCOL (work_report_gather style: PREFIX + '|' fields, at most one
free-ish field per record and always LAST; exit 0 for every validation
outcome including ERROR lines, 2 usage, 3 infra):

    SCOPE:<kind>|<topics csv>
    OWNER:<ref | none>
    MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<path>
    INPUT:task_file|<exists>|<status>|<depends csv>|<gates csv>|<ref>
    INPUT:plan_file|<exists>|<content_hash or ->|<ref>
    DIGEST:<hex>
    CURRENT | STALE
    DRIFT:<code>|<task_ref or ->|<detail>
    ERROR:<kind>:<id>            (staged -- emitted alone, exit 0)

Deterministic ordering: INPUT lines in canonical (kind, ref) order (the
same order the digest hashes), MEMBER lines sorted by ref, topics csv
sorted, DRIFT lines deduplicated by (code, task_ref) -- lexicographically
smallest sanitized detail survives -- and sorted by (code, task_ref). Two
runs over unchanged state are byte-identical.

Error vocabulary (ERROR:<kind>:<id>): unknown_task, unresolved_project,
cross_repo_topic_unsupported, unstable_repository_state, undriftable_input,
ref_outside_project, invalid_trail, trail_unreadable, artifact_unresolved
(the last one is emitted by the wrapper). ERROR paths emit ONLY error
lines -- never a partial snapshot or a partial verdict.

GENERATION INVARIANT: snapshot records only inputs that exist
(exists=true always at generation); exists=false appears only in the drift
recomputation, which is exactly what makes a deleted input change the
digest. boardidx / timestamps are unrepresentable by the trail_schema
record contract (unknown key = hard error), so board repaints are never
drift.

DRIFT CONTRACT -- GATHERER_DRIFT_CODES is the complete emittable set;
premise_invalidated is authored by the refresh agent (T3), never by this
deterministic helper (RFC par.7.5 anti-fabrication). Trigger matrix
(existence-class rows mutually exclusive per input, first match wins;
snapshot-comparison rows fire only for active non-terminal inputs with a
matching entry; scans are digest-independent):

    task_folded         folded_into present or status Folded (active or
                        archived) -- checked first
    task_completed      else active with status Done, or archived Done
    task_archived       else found only in archive, status != Done
    task_deleted        else in neither tree
    status_changed      live status != entry snapshot.status
    dependency_changed  live depends set != snapshot.depends set
    gate_state_changed  live pending-gate set != snapshot.gates_pending set
    plan_changed        per-member plan-identity compare (appeared /
                        renamed), or sole candidate under residual
                        attribution
    input_missing       non-task stored input unreadable/absent
    new_related_task    unreferenced task in a scoped project whose
                        qualified topic key matches scope.topics or whose
                        depends intersects the persisted member set
                        (stored task inputs + entry tasks)
    other               residual attribution: substitution digest proves an
                        unattributed content change with >=2 candidates,
                        reconstruction is incomplete, or an attributed
                        content transition made the check undecidable and
                        unverified candidates remain

Residual attribution bound (declared approximation): the trail stores no
per-input hashes. Old task records are reconstructed from entry snapshots
and a substitution digest (old task records + live content records) is
compared to the stored digest -- but only when zero content transitions
were already attributed (a missing/renamed plan's old hash is
unreconstructible and poisons the check). When the check cannot run,
remaining candidates are flagged with one conservative `other` reason
(unverifiable -- refresh must reanalyze), never silently dropped.

Stable-read policy: record scans are accepted only when two consecutive
scans produce the same digest (max 3 scans), else
ERROR:unstable_repository_state. Detection of concurrent churn, not
isolation: two torn reads hashing identically are indistinguishable.

Version lock: a NORMALIZATION_VERSION bump MUST ship with a schema_version
bump (SCHEMA_NORMALIZATION_LOCK below; tripwire-tested). Under the lock,
every trail that passes validation was digested under the runtime's own
normalization; old-schema trails fail validation (ERROR:invalid_trail) --
never a false STALE.

Ownership: topic semantics live in lib/topic_semantics.py (board-owned
seam); the record/digest contract lives in lib/trail_schema.py (t1210_1).
This module composes them and never forks either.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Make lib/ importable however this module is invoked (via the .sh wrapper or
# directly from a test). Every module imported below now lives in lib/ —
# task_yaml moved there in t1217 — so this reaches into no sibling package.
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.dirname(_LIB_DIR)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import yaml  # noqa: E402

import trail_schema  # noqa: E402
from archive_iter import find_archived_markdown_by_id  # noqa: E402
from cross_repo_notation import parse_ref  # noqa: E402
from gate_ledger import archive_status_from_text  # noqa: E402
from task_yaml import BOARD_KEYS, parse_frontmatter  # noqa: E402
from topic_semantics import topic_key  # noqa: E402

EXIT_USAGE = 2
EXIT_INFRA = 3

STABLE_READ_MAX_SCANS = 3

# Version lock (tripwire-tested): bumping NORMALIZATION_VERSION without a
# schema_version bump would make stored digests silently incomparable -- the
# schema stores no normalization provenance, so comparability is guaranteed
# by pairing the two versions. Keep this mapping in lockstep with
# trail_schema; tests/test_trail_gather.py goes red on a one-sided bump.
SCHEMA_NORMALIZATION_LOCK = {"1.0.0": "1.0.0"}

# The complete set of drift codes this deterministic helper can emit -- a
# strict subset of the schema's freshness.drift_reasons enum.
# premise_invalidated is deliberately absent: refresh-agent-authored (T3).
GATHERER_DRIFT_CODES = frozenset({
    "task_completed", "task_archived", "task_deleted", "task_folded",
    "status_changed", "dependency_changed", "gate_state_changed",
    "plan_changed", "new_related_task", "input_missing", "other",
})

TASK_FILE_RE = re.compile(r"^t(\d+(?:_\d+)?)_")
PLAN_REF_RE = re.compile(r"^([a-z0-9_-]+):([^:].*)$")

_RECORD_BREAKING = ("|", "\r", "\n")
INVALID_ENUM = "invalid"
UNKNOWN_ENUM = "unknown"


# --- Delimiter safety (parity with work_report_gather's pinned policy) ------

def _has_record_breaking(value: str) -> bool:
    return any(ch in value for ch in _RECORD_BREAKING)


def _free_text(value: str) -> str:
    """Sanitize a free-text LAST field: '|' survives (maxsplit), CR/LF cannot."""
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def _enum_field(value) -> str:
    """A fixed-position enum-ish field: absent -> `unknown`, unsafe -> `invalid`."""
    if value is None or value == "":
        return UNKNOWN_ENUM
    text = str(value)
    return INVALID_ENUM if _has_record_breaking(text) else text


def _csv_entry(value) -> str:
    """One member of a csv-encoded list field: ','/'|'/CR/LF -> `invalid`.
    Line transport only -- the digest always hashes the raw value."""
    text = str(value)
    if "," in text or _has_record_breaking(text):
        return INVALID_ENUM
    return text


def _die(msg: str, code: int) -> None:
    print(f"trail_gather: {msg}", file=sys.stderr)
    sys.exit(code)


def emit_errors(out, errors: list[str]) -> None:
    for error in errors:
        print(f"ERROR:{_free_text(error)}", file=out)


# --- Ref layer --------------------------------------------------------------

def _local_dirs() -> tuple[Path, Path, Path]:
    """(task_dir, plan_dir, archived_dir) for the local project (env-aware)."""
    task_dir = Path(os.environ.get("TASK_DIR", "aitasks"))
    plan_dir = Path(os.environ.get("PLAN_DIR", "aiplans"))
    archived = Path(os.environ.get("ARCHIVED_DIR", str(task_dir / "archived")))
    return task_dir, plan_dir, archived


def local_project_name() -> str:
    """`project.name` from the local project_config.yaml. Its absence is an
    install defect (ait setup seeds it), not a validation outcome."""
    task_dir, _, _ = _local_dirs()
    config_path = task_dir / "metadata" / "project_config.yaml"
    try:
        with open(config_path, encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except OSError as exc:
        _die(f"cannot read {config_path}: {exc}", EXIT_INFRA)
    name = ((config.get("project") or {}).get("name") or "").strip()
    if not name:
        _die(f"{config_path}: missing project.name", EXIT_INFRA)
    return name


def canonical_id(raw: str, local_name: str) -> tuple[str, str] | None:
    """Canonicalize one id argument to (project, bare_id). Accepts local bare
    ids (`1208`, `t1208_3`) and cross-repo refs (`proj#12`, `proj#t12_3`).
    Returns None when the value parses as neither."""
    text = (raw or "").strip()
    if not text:
        return None
    m = re.fullmatch(r"t?(\d+(?:_\d+)?)", text)
    if m:
        return (local_name, m.group(1))
    return parse_ref(text)


class ProjectRoots:
    """Resolve logical project names to roots via aitask_project_resolve.sh,
    cached per name. The local project resolves to cwd without a subprocess."""

    def __init__(self, local_name: str):
        self.local_name = local_name
        self._cache: dict[str, Path | None] = {local_name: Path(".")}
        self._resolver = os.path.join(_SCRIPTS_DIR, "aitask_project_resolve.sh")

    def resolve(self, name: str) -> Path | None:
        if name in self._cache:
            return self._cache[name]
        root: Path | None = None
        try:
            out = subprocess.run(
                [self._resolver, name], capture_output=True, text=True,
                timeout=30, check=False,
            ).stdout.strip()
            if out.startswith("RESOLVED:"):
                root = Path(out.split(":", 1)[1])
        except (OSError, subprocess.TimeoutExpired):
            root = None
        self._cache[name] = root
        return root


# --- Task tree loading ------------------------------------------------------

@dataclass
class TaskRow:
    """One active task. `.filename`/`.metadata` satisfy the topic_semantics
    duck-type contract."""
    filename: str
    metadata: dict
    text: str
    path: Path
    own_id: str
    project: str

    @property
    def ref(self) -> str:
        return f"{self.project}#{self.own_id}"


@dataclass
class ProjectTree:
    name: str
    root: Path
    task_dir: Path
    plan_dir: Path
    archived_dir: Path
    rows: list[TaskRow] = field(default_factory=list)
    by_own_id: dict[str, TaskRow] = field(default_factory=dict)


def _load_row(path: Path, project: str) -> TaskRow | None:
    match = TASK_FILE_RE.match(path.name)
    if not match:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        parsed = parse_frontmatter(raw)
    except Exception:
        # Board parity: a malformed file is simply absent from the universe.
        parsed = None
    metadata = parsed[0] if parsed else {}
    if not metadata or set(metadata.keys()) <= set(BOARD_KEYS):
        return None  # phantom stub or unparseable -- invisible on the board too
    return TaskRow(filename=path.name, metadata=metadata, text=raw,
                   path=path, own_id=match.group(1), project=project)


def load_tree(name: str, root: Path, is_local: bool) -> ProjectTree:
    """The pinned universe: active parents (t*.md) + children (t*/t*_*.md),
    phantom stubs dropped -- identical to the board's By-Topic universe."""
    if is_local:
        task_dir, plan_dir, archived_dir = _local_dirs()
    else:
        task_dir = root / "aitasks"
        plan_dir = root / "aiplans"
        archived_dir = root / "aitasks" / "archived"
    tree = ProjectTree(name=name, root=root, task_dir=task_dir,
                       plan_dir=plan_dir, archived_dir=archived_dir)
    candidates = sorted(task_dir.glob("*.md")) + sorted(task_dir.glob("t*/t*_*.md"))
    for path in candidates:
        row = _load_row(path, name)
        if row is None:
            continue
        tree.rows.append(row)
        tree.by_own_id.setdefault(row.own_id, row)
    return tree


# --- Plan resolution (mirrors aitask_query_files.sh cmd_plan_file) ----------

def plan_path_for(row: TaskRow, tree: ProjectTree) -> Path | None:
    """Canonical plan lookup: parent -> $PLAN_DIR/p<N>_*.md, child ->
    $PLAN_DIR/p<P>/p<P>_<C>_*.md; sorted glob, first match wins."""
    if "_" in row.own_id:
        parent, child = row.own_id.split("_", 1)
        pattern = f"p{parent}/p{parent}_{child}_*.md"
    else:
        pattern = f"p{row.own_id}_*.md"
    matches = sorted(tree.plan_dir.glob(pattern))
    if not matches:
        return None
    if len(matches) > 1:
        print(f"trail_gather: {row.ref}: multiple plan files match "
              f"{pattern}; using {matches[0]}", file=sys.stderr)
    return matches[0]


def plan_glob_regex(own_id: str) -> re.Pattern:
    """Regex over a plan ref's *relpath* deciding whether it belongs to the
    member `own_id` (the identity-by-member rule for plan_changed)."""
    if "_" in own_id:
        parent, child = own_id.split("_", 1)
        pat = rf"(?:.*/)?p{parent}/p{parent}_{child}_[^/]*\.md"
    else:
        pat = rf"(?:.*/)?p{own_id}_[^/]*\.md"
    return re.compile(pat + r"$")


def _content_hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[
            :trail_schema.DIGEST_HEX_LEN]
    except OSError:
        return None


def _plan_ref(tree: ProjectTree, plan_path: Path) -> str:
    rel = os.path.relpath(plan_path, tree.root)
    return f"{tree.name}:{Path(rel).as_posix()}"


# --- Record building --------------------------------------------------------

def _canonical_depends(metadata: dict, project: str) -> list[str]:
    """Normalize a task's depends entries to canonical refs in the OWNING
    project's namespace; unparseable entries stay verbatim (deterministic).
    Deduplicated: identical membership must never hash differently."""
    raw = metadata.get("depends")
    if not isinstance(raw, list):
        return []
    out = set()
    for entry in raw:
        parsed = canonical_id(str(entry), project)
        if parsed is not None:
            out.add(f"{parsed[0]}#{parsed[1]}")
        else:
            out.add(str(entry))
    return sorted(out)


def _gates_pending(text: str) -> list[str]:
    verdict, pending = archive_status_from_text(text)
    return sorted(set(pending)) if verdict == "BLOCKED" else []


def task_record(row: TaskRow) -> dict:
    return {
        "ref": row.ref,
        "kind": "task_file",
        "exists": True,
        "status": str(row.metadata.get("status") or ""),
        "depends": _canonical_depends(row.metadata, row.project),
        "gates_pending": _gates_pending(row.text),
    }


def build_input_records(
        members: list[tuple[TaskRow, ProjectTree]],
) -> tuple[list[dict], dict[str, Path]]:
    """RFC par.8.1 records for the member set (generation invariant:
    exists=true only). Returns (records, {plan_ref: plan_path})."""
    records: list[dict] = []
    plan_paths: dict[str, Path] = {}
    seen_refs = set()
    for row, tree in members:
        if row.ref in seen_refs:
            continue
        seen_refs.add(row.ref)
        records.append(task_record(row))
        plan_path = plan_path_for(row, tree)
        if plan_path is not None:
            digest = _content_hash(plan_path)
            if digest is None:
                continue
            ref = _plan_ref(tree, plan_path)
            records.append({"ref": ref, "kind": "plan_file", "exists": True,
                            "content_hash": digest})
            plan_paths[ref] = plan_path
    return records, plan_paths


# --- Stable read ------------------------------------------------------------

def stable_records(scan_fn, max_scans: int = STABLE_READ_MAX_SCANS):
    """Accept a scan only when two consecutive scans digest identically.

    scan_fn() -> (records, payload). Returns (records, payload) of the last
    scan, or None after max_scans without two consecutive stable digests
    (churn detection, not isolation -- see module docstring).
    """
    prev_digest = None
    prev_result = None
    for _ in range(max_scans):
        records, payload = scan_fn()
        digest = trail_schema.input_digest(records)
        if prev_digest is not None and digest == prev_digest:
            return prev_result
        prev_digest, prev_result = digest, (records, payload)
    return None


# --- Line emission ----------------------------------------------------------

def _validated_ref_field(ref: str) -> str:
    if _has_record_breaking(ref):
        _die(f"ref {ref!r} contains '|', CR or LF and cannot round-trip "
             "through the protocol", EXIT_INFRA)
    return ref


def input_line(record: dict) -> str:
    exists = "true" if record["exists"] else "false"
    ref = _validated_ref_field(record["ref"])
    if record["kind"] == "task_file":
        depends = ",".join(_csv_entry(d) for d in record.get("depends", []))
        gates = ",".join(_csv_entry(g) for g in record.get("gates_pending", []))
        status = _enum_field(record.get("status"))
        return f"INPUT:task_file|{exists}|{status}|{depends}|{gates}|{ref}"
    content_hash = record.get("content_hash") or "-"
    return f"INPUT:{record['kind']}|{exists}|{_enum_field(content_hash)}|{ref}"


def member_line(row: TaskRow) -> str:
    ref = _validated_ref_field(row.ref)
    meta = row.metadata
    labels = meta.get("labels")
    labels_csv = ",".join(
        _csv_entry(l) for l in labels) if isinstance(labels, list) else ""
    return ("MEMBER:" + ref
            + f"|{_enum_field(meta.get('status'))}"
            + f"|{_enum_field(meta.get('priority'))}"
            + f"|{_enum_field(meta.get('effort'))}"
            + f"|{_enum_field(meta.get('boardcol'))}"
            + f"|{labels_csv}"
            + f"|{_free_text(str(row.path))}")


# --- snapshot verb ----------------------------------------------------------

def _resolve_scope_ids(raw_ids: list[str], scope: str, local_name: str,
                       errors: list[str]) -> list[tuple[str, str]]:
    """Canonicalize + dedup (first occurrence) the argv ids; staged errors."""
    ids: list[tuple[str, str]] = []
    for raw in raw_ids:
        parsed = canonical_id(raw, local_name)
        if parsed is None:
            errors.append(f"unknown_task:{raw}")
            continue
        if scope in ("topic", "multi_topic") and parsed[0] != local_name:
            errors.append(f"cross_repo_topic_unsupported:{parsed[0]}#{parsed[1]}")
            continue
        if parsed not in ids:
            ids.append(parsed)
    return ids


def cmd_snapshot(args, out=None) -> int:
    out = out if out is not None else sys.stdout
    local_name = local_project_name()
    roots = ProjectRoots(local_name)
    errors: list[str] = []
    ids = _resolve_scope_ids(args.ids, args.scope, local_name, errors)

    owner_parsed = None
    if args.owner:
        owner_parsed = canonical_id(args.owner, local_name)
        if owner_parsed is None:
            errors.append(f"unknown_task:{args.owner}")
    if errors:
        emit_errors(out, errors)
        return 0

    # Resolve every involved project root up front (staged, fail-closed).
    projects = {proj for proj, _ in ids}
    if owner_parsed:
        projects.add(owner_parsed[0])
    trees: dict[str, ProjectTree] = {}
    for proj in sorted(projects):
        root = roots.resolve(proj)
        if root is None:
            errors.append(f"unresolved_project:{proj}")
            continue
        trees[proj] = load_tree(proj, root, proj == local_name)
    if errors:
        emit_errors(out, errors)
        return 0

    def scan():
        # Rebuild trees + records from disk on every scan (stable read).
        fresh = {proj: load_tree(proj, tree.root, proj == local_name)
                 for proj, tree in trees.items()}
        scan_errors: list[str] = []
        members: list[tuple[TaskRow, ProjectTree]] = []
        if args.scope == "task":
            for proj, bare in ids:
                tree = fresh[proj]
                row = tree.by_own_id.get(bare)
                if row is None:
                    scan_errors.append(f"unknown_task:{proj}#{bare}")
                    continue
                members.append((row, tree))
                if "_" not in bare:
                    prefix = f"{bare}_"
                    for child in tree.rows:
                        if child.own_id.startswith(prefix):
                            members.append((child, tree))
        else:  # topic / multi_topic (local-only, validated above)
            tree = fresh[local_name]
            for _, bare in ids:
                found = [r for r in tree.rows
                         if topic_key(r, tree.by_own_id) == bare]
                if not found:
                    scan_errors.append(f"unknown_task:{local_name}#{bare}")
                    continue
                members.extend((r, tree) for r in found)

        # Validate --owner against the fresh universe.
        if owner_parsed is not None:
            owner_tree = fresh[owner_parsed[0]]
            if owner_tree.by_own_id.get(owner_parsed[1]) is None:
                scan_errors.append(
                    f"unknown_task:{owner_parsed[0]}#{owner_parsed[1]}")
        if scan_errors:
            return [], (scan_errors, [], {})
        records, _plan_paths = build_input_records(members)
        return records, ([], members, fresh)

    result = stable_records(scan)
    if result is None:
        emit_errors(out, ["unstable_repository_state:snapshot"])
        return 0
    records, (scan_errors, members, fresh) = result
    if scan_errors:
        emit_errors(out, sorted(set(scan_errors)))
        return 0

    # Owner: --owner override, else the single scope id, else none.
    if owner_parsed is not None:
        owner = f"{owner_parsed[0]}#{owner_parsed[1]}"
    elif len(ids) == 1:
        owner = f"{ids[0][0]}#{ids[0][1]}"
    else:
        owner = "none"

    # Topics: the roots for topic scopes; the members' own topic keys for
    # task scope (qualified per member project).
    if args.scope == "task":
        topics = sorted({
            f"{row.project}#{topic_key(row, fresh[row.project].by_own_id)}"
            for row, _ in members})
    else:
        topics = sorted({f"{local_name}#{bare}" for _, bare in ids})

    print(f"SCOPE:{args.scope}|{','.join(_csv_entry(t) for t in topics)}",
          file=out)
    print(f"OWNER:{_validated_ref_field(owner)}", file=out)
    unique_rows = {row.ref: row for row, _ in members}
    for ref in sorted(unique_rows):
        print(member_line(unique_rows[ref]), file=out)
    ordered = sorted(records, key=lambda r: (r["kind"], r["ref"]))
    for record in ordered:
        print(input_line(record), file=out)
    print(f"DIGEST:{trail_schema.input_digest(records)}", file=out)
    return 0


# --- drift verb -------------------------------------------------------------

@dataclass
class StoredInput:
    """One stored generation input.

    ``ref`` keeps the trail's EXACT stored spelling: the stored digest was
    hashed over these bytes, so digest reconstruction must reproduce them
    (re-spelling a tolerated ``proj#t100`` ref would fabricate STALE
    forever). ``canonical`` is the normalized ``proj#100`` form used for
    every lookup/comparison and for consumer-facing reason refs.
    """
    ref: str
    kind: str
    project: str
    canonical: str = ""        # task_file only
    bare_id: str = ""          # task_file only
    relpath: str = ""          # plan_file only


def _canonical_task_ref(ref: str) -> str:
    """Canonical `<project>#<bare-id>` spelling of a task ref (tolerated `t`
    form normalized); non-refs pass through unchanged."""
    parsed = parse_ref(ref)
    return f"{parsed[0]}#{parsed[1]}" if parsed else ref


def _classify_stored_inputs(doc: dict, errors: list[str]) -> list[StoredInput]:
    """Apply the driftable-input rule: every accepted kind has a defined live
    resolver, or the verdict is refused (staged errors)."""
    out: list[StoredInput] = []
    for record in doc["generation"]["inputs"]:
        ref, kind = record["ref"], record["kind"]
        if kind == "task_file":
            parsed = parse_ref(ref)
            if parsed is None:
                errors.append(f"undriftable_input:{ref}")
                continue
            out.append(StoredInput(ref=ref, kind=kind, project=parsed[0],
                                   canonical=f"{parsed[0]}#{parsed[1]}",
                                   bare_id=parsed[1]))
        elif kind == "plan_file":
            m = PLAN_REF_RE.fullmatch(ref)
            if m is None:
                errors.append(f"undriftable_input:{ref}")
                continue
            out.append(StoredInput(ref=ref, kind=kind, project=m.group(1),
                                   relpath=m.group(2)))
        else:  # board_state / gate_ledger / other: no canonical live resolver
            errors.append(f"undriftable_input:{ref}")
    return out


def _contained_plan_path(tree: ProjectTree, relpath: str) -> Path | None:
    """Resolve a plan relpath under its project root, realpath-confined."""
    root_real = os.path.realpath(tree.root)
    target = os.path.realpath(os.path.join(root_real, relpath))
    try:
        if os.path.commonpath([root_real, target]) != root_real:
            return None
    except ValueError:
        return None
    return Path(target)


def _doc_task_refs(doc: dict) -> tuple[set[str], set[str], dict[str, dict]]:
    """(baseline referenced set, entry task refs, entry task -> snapshot).
    All refs canonicalized (see _canonical_task_ref) so they compare against
    the gatherer's canonical spellings."""
    entry_refs: set[str] = set()
    snapshots: dict[str, dict] = {}
    for wave in doc.get("waves", []):
        for entry in wave.get("entries", []):
            task = entry.get("task")
            if isinstance(task, str):
                task = _canonical_task_ref(task)
                entry_refs.add(task)
                snapshot = entry.get("snapshot")
                if isinstance(snapshot, dict):
                    snapshots.setdefault(task, snapshot)
    baseline = set(entry_refs)
    for exclusion in doc.get("exclusions", []):
        task = exclusion.get("task")
        if isinstance(task, str):
            baseline.add(_canonical_task_ref(task))
    for obs in doc.get("observations", []):
        for task in obs.get("affects", []) or []:
            if isinstance(task, str):
                baseline.add(_canonical_task_ref(task))
    return baseline, entry_refs, snapshots


def _existence_reason(inp: StoredInput, tree: ProjectTree) -> tuple[str, str] | None:
    """Existence-class code for a task input, or None when active+non-terminal.
    Mutually exclusive, first match in the pinned matrix order wins."""
    row = tree.by_own_id.get(inp.bare_id)
    ref = inp.canonical
    if row is not None:
        meta = row.metadata
        if meta.get("folded_into") is not None or meta.get("status") == "Folded":
            return ("task_folded", f"{ref} is folded")
        if meta.get("status") == "Done":
            return ("task_completed", f"{ref} is Done (still active)")
        return None
    archived = find_archived_markdown_by_id(inp.bare_id, tree.archived_dir)
    if archived is not None:
        _, text = archived
        try:
            parsed = parse_frontmatter(text)
        except Exception:
            parsed = None
        meta = parsed[0] if parsed else {}
        if meta.get("folded_into") is not None or meta.get("status") == "Folded":
            return ("task_folded", f"{ref} was folded and archived")
        if meta.get("status") == "Done":
            return ("task_completed", f"{ref} completed and archived")
        return ("task_archived", f"{ref} archived with status "
                                 f"{meta.get('status')!r}")
    return ("task_deleted", f"{ref} not found in active or archived tree")


def _reconstruct_old_task_records(task_inputs: list[StoredInput],
                                  snapshots: dict[str, dict]) -> list[dict] | None:
    """Old task records from entry snapshots; None when any input lacks a
    complete snapshot (status + depends + gates_pending)."""
    records = []
    for inp in task_inputs:
        snap = snapshots.get(inp.canonical)
        if (not isinstance(snap, dict)
                or not isinstance(snap.get("status"), str)
                or not isinstance(snap.get("depends"), list)
                or not isinstance(snap.get("gates_pending"), list)):
            return None
        try:
            records.append({
                "ref": inp.ref,  # stored spelling: the digest hashed it
                "kind": "task_file", "exists": True,
                "status": snap["status"],
                "depends": sorted(set(snap["depends"])),
                "gates_pending": sorted(set(snap["gates_pending"])),
            })
        except TypeError:
            return None  # unhashable members -- phase-1 validation covered it
    return records


def dedup_reasons(
        reasons: list[tuple[str, str, str]]) -> list[tuple[tuple[str, str], str]]:
    """Canonical drift-reason dedup + ordering: one reason per
    (code, task_ref), lexicographically smallest sanitized detail surviving
    (pinned tie-break -- discovery order can never select the output text),
    sorted by (code, task_ref)."""
    best: dict[tuple[str, str], str] = {}
    for code, task, detail in reasons:
        key = (code, task)
        if key not in best or detail < best[key]:
            best[key] = detail
    return sorted(best.items())


def cmd_drift(args, out=None) -> int:
    out = out if out is not None else sys.stdout
    local_name = local_project_name()
    roots = ProjectRoots(local_name)

    # -- Load + validate the trail (verdicts only for schema-valid trails).
    if not os.path.isfile(args.trail):
        emit_errors(out, [f"trail_unreadable:{args.trail}"])
        return 0
    try:
        doc = trail_schema.load_trail(args.trail)
    except trail_schema.TrailValidationError as exc:
        if any(i.rule == "io" for i in exc.issues):
            emit_errors(out, [f"trail_unreadable:{args.trail}"])
            return 0
        for issue in exc.issues:
            print(f"INVALID:{issue.path}|{issue.rule}|{issue.message}",
                  file=sys.stderr)
        emit_errors(out, [f"invalid_trail:{len(exc.issues)}"])
        return 0

    # -- Version lock (defensive: a violated lock is a build defect).
    schema_version = doc["schema_version"]
    locked = SCHEMA_NORMALIZATION_LOCK.get(schema_version)
    if locked != trail_schema.NORMALIZATION_VERSION:
        _die(f"version lock violated: schema {schema_version} pairs with "
             f"normalization {locked!r} but runtime is "
             f"{trail_schema.NORMALIZATION_VERSION} -- bump both together",
             EXIT_INFRA)

    errors: list[str] = []
    stored_inputs = _classify_stored_inputs(doc, errors)
    baseline, entry_refs, snapshots = _doc_task_refs(doc)
    task_inputs = [i for i in stored_inputs if i.kind == "task_file"]
    plan_inputs = [i for i in stored_inputs if i.kind == "plan_file"]

    # -- Scanned projects: scope.topics ∪ entry refs ∪ stored task inputs.
    scope_topics = {_canonical_task_ref(t)
                    for t in doc.get("scope", {}).get("topics", [])
                    if isinstance(t, str)}
    projects: set[str] = {i.project for i in stored_inputs}
    for ref in entry_refs | scope_topics:
        parsed = parse_ref(ref)
        if parsed is not None:
            projects.add(parsed[0])
    trees: dict[str, ProjectTree] = {}
    for proj in sorted(projects):
        root = roots.resolve(proj)
        if root is None:
            errors.append(f"unresolved_project:{proj}")
            continue
        trees[proj] = load_tree(proj, root, proj == local_name)

    # -- Containment for plan refs (the one untrusted-ref file-read sink).
    plan_paths: dict[str, Path] = {}
    for inp in plan_inputs:
        if inp.project not in trees:
            continue  # unresolved_project already staged
        contained = _contained_plan_path(trees[inp.project], inp.relpath)
        if contained is None:
            errors.append(f"ref_outside_project:{inp.ref}")
            continue
        plan_paths[inp.ref] = contained

    if errors:
        emit_errors(out, sorted(set(errors)))
        return 0

    # -- Live record recomputation over the stored refs (stable read).
    def scan():
        fresh = {proj: load_tree(proj, tree.root, proj == local_name)
                 for proj, tree in trees.items()}
        records: list[dict] = []
        for inp in task_inputs:
            row = fresh[inp.project].by_own_id.get(inp.bare_id)
            if row is None:
                records.append({"ref": inp.ref, "kind": "task_file",
                                "exists": False})
            else:
                # Stored spelling, not row.ref: the stored digest was hashed
                # over these exact ref bytes (see StoredInput).
                record = task_record(row)
                record["ref"] = inp.ref
                records.append(record)
        for inp in plan_inputs:
            digest = _content_hash(plan_paths[inp.ref])
            if digest is None:
                records.append({"ref": inp.ref, "kind": "plan_file",
                                "exists": False})
            else:
                records.append({"ref": inp.ref, "kind": "plan_file",
                                "exists": True, "content_hash": digest})
        return records, fresh

    result = stable_records(scan)
    if result is None:
        emit_errors(out, ["unstable_repository_state:drift"])
        return 0
    live_records, fresh = result
    live_by_ref = {r["ref"]: r for r in live_records}
    live_digest = trail_schema.input_digest(live_records)
    stored_digest = doc["generation"]["input_digest"]
    digest_differs = live_digest != stored_digest

    reasons: list[tuple[str, str, str]] = []  # (code, task_ref-or-'-', detail)

    def add(code: str, task: str, detail: str) -> None:
        assert code in GATHERER_DRIFT_CODES
        reasons.append((code, task, _free_text(detail)))

    # -- Per-input reasons: only meaningful when the digest moved (an equal
    #    digest proves the recomputed records are identical to generation).
    attributed_content: set[str] = set()
    if digest_differs:
        for inp in task_inputs:
            reason = _existence_reason(inp, fresh[inp.project])
            if reason is not None:
                add(reason[0], inp.canonical, reason[1])
                continue
            snap = snapshots.get(inp.canonical)
            row = fresh[inp.project].by_own_id.get(inp.bare_id)
            if snap is None or row is None:
                continue
            live = live_by_ref[inp.ref]
            if (isinstance(snap.get("status"), str)
                    and live.get("status") != snap["status"]):
                add("status_changed", inp.canonical,
                    f"status {snap['status']!r} -> {live.get('status')!r}")
            if (isinstance(snap.get("depends"), list)
                    and set(live.get("depends", [])) != set(snap["depends"])):
                add("dependency_changed", inp.canonical,
                    f"depends now {live.get('depends', [])}")
            if (isinstance(snap.get("gates_pending"), list)
                    and set(live.get("gates_pending", []))
                    != set(snap["gates_pending"])):
                add("gate_state_changed", inp.canonical,
                    f"pending gates now {live.get('gates_pending', [])}")
        for inp in plan_inputs:
            if not live_by_ref[inp.ref]["exists"]:
                add("input_missing", "-", f"{inp.ref} no longer readable")
                attributed_content.add(inp.ref)

    # -- Digest-independent scans -------------------------------------------
    member_refs = {i.canonical for i in task_inputs} | entry_refs
    input_refs = ({i.canonical for i in task_inputs}
                  | {i.ref for i in plan_inputs})
    for proj, tree in fresh.items():
        for row in tree.rows:
            if row.ref in baseline or row.ref in input_refs:
                continue
            qualified_topic = f"{proj}#{topic_key(row, tree.by_own_id)}"
            depends = set(_canonical_depends(row.metadata, proj))
            if qualified_topic in scope_topics:
                add("new_related_task", row.ref,
                    f"new task in topic {qualified_topic}")
            elif depends & member_refs:
                add("new_related_task", row.ref,
                    f"new task depends on {sorted(depends & member_refs)}")

    # Plan identity by member: appeared / renamed (path change).
    for inp in task_inputs:
        if inp.project not in fresh:
            continue
        tree = fresh[inp.project]
        row = tree.by_own_id.get(inp.bare_id)
        if row is None:
            continue
        belongs = plan_glob_regex(inp.bare_id)
        stored_for_member = next(
            (p for p in plan_inputs
             if p.project == inp.project and belongs.search(p.relpath)), None)
        current = plan_path_for(row, tree)
        if current is None:
            continue  # some->none is input_missing territory (existence rule)
        current_ref = _plan_ref(tree, current)
        if stored_for_member is None:
            add("plan_changed", inp.canonical, f"plan appeared: {current_ref}")
        elif current_ref != stored_for_member.ref:
            add("plan_changed", inp.canonical,
                f"plan moved: {stored_for_member.ref} -> {current_ref}")
            attributed_content.add(stored_for_member.ref)

    # -- Residual attribution (content changes; see module docstring bound).
    if digest_differs:
        candidates = [i.ref for i in plan_inputs
                      if i.ref not in attributed_content
                      and live_by_ref[i.ref]["exists"]]
        if attributed_content:
            if candidates:
                add("other", "-",
                    "unverifiable content inputs (attributed transition made "
                    "residual attribution undecidable; refresh must "
                    f"reanalyze): {', '.join(sorted(candidates))}")
        else:
            old_task_records = _reconstruct_old_task_records(
                task_inputs, snapshots)
            if old_task_records is None:
                if candidates:
                    add("other", "-",
                        "unattributable content inputs (incomplete entry "
                        f"snapshots): {', '.join(sorted(candidates))}")
            else:
                live_content = [live_by_ref[i.ref] for i in plan_inputs]
                substitution = trail_schema.input_digest(
                    old_task_records + live_content)
                if substitution != stored_digest:
                    if len(candidates) == 1:
                        add("plan_changed", "-",
                            f"plan content changed: {candidates[0]}")
                    elif candidates:
                        add("other", "-",
                            "content changed in one of: "
                            + ", ".join(sorted(candidates)))
                    else:
                        add("other", "-",
                            "digest mismatch not attributable to any input "
                            "(lossy snapshot reconstruction)")

    ordered = dedup_reasons(reasons)

    print("STALE" if (digest_differs or ordered) else "CURRENT", file=out)
    for (code, task), detail in ordered:
        print(f"DRIFT:{code}|{_validated_ref_field(task)}|{detail}", file=out)
    print(f"DIGEST:{live_digest}", file=out)
    return 0


# --- CLI --------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aitask_trail_gather.sh",
        description="Deterministic gatherer + drift checker for "
                    "implementation trails.",
    )
    sub = parser.add_subparsers(dest="verb", required=True)
    snap = sub.add_parser("snapshot", help="gather scope input records + digest")
    snap.add_argument("--scope", required=True,
                      choices=("task", "topic", "multi_topic"))
    snap.add_argument("--owner", help="explicit owner task id (RFC J4)")
    snap.add_argument("ids", nargs="+", help="task ids or topic root ids")
    drift = sub.add_parser("drift", help="recompute a stored trail's freshness")
    drift.add_argument("--trail", required=True,
                       help="path to a trail JSON document")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code not in (0, None) else 0
    if args.verb == "snapshot":
        return cmd_snapshot(args)
    return cmd_drift(args)


if __name__ == "__main__":
    sys.exit(main())
