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
    MEMBER:<ref>|<status>|<priority>|<effort>|<boardcol>|<labels csv>|<followup_kind>|<path>
    MEMBER_EXT:<ref>|<created_at>|<anchor>|<verifies csv>|<risk_code_health>|<risk_goal_achievement>
    INPUT:task_file|<exists>|<status>|<depends csv>|<gates csv>|<ref>
    INPUT:plan_file|<exists>|<content_hash or ->|<ref>
    DIGEST:<hex>
    CURRENT | STALE
    DRIFT:<code>|<task_ref or ->|<detail>
    ERROR:<kind>:<id>            (staged -- emitted alone, exit 0)

  Only under --with-inflight (t1569_1) -- VOLATILE, see the determinism note:
    INFLIGHT_SOURCE:<gate|lock|tracked>|<ok|degraded|unavailable|not_consulted>|<age_seconds|->|<reason|->
    INFLIGHT:<ref>|<gate|lock|both>|<PLAN|IMPLEMENT|POSTIMPL|->|<archive_status>
    INFLIGHT_PATH:<ref>|<tracked|planned_new|phantom|malformed|no_tokens|unreadable|no_plan|unclassified>|<path|->
    INFLIGHT_SCAN:<n_tasks>|<corpus_status>|<source_status>

Deterministic ordering: INPUT lines in canonical (kind, ref) order (the
same order the digest hashes), MEMBER / MEMBER_EXT lines sorted by ref,
topics csv sorted, DRIFT lines deduplicated by (code, task_ref) --
lexicographically smallest sanitized detail survives -- and sorted by
(code, task_ref).

DETERMINISM, SCOPED. Two runs over unchanged state are byte-identical
ACROSS THE DIGEST-RELEVANT LINES -- everything above except the four
INFLIGHT* prefixes. Those four are volatile by nature (locks and
in-flight status change minute to minute), which is exactly why they are
opt-in and digest-excluded; stating the guarantee over the whole output,
as this docstring once did, would make the determinism test encode the
wrong property and keep passing while the real one rots. MEMBER_EXT: is
NOT volatile -- its fields change only when a task file changes -- so it
is emitted unconditionally and stays inside the guarantee.

The invariant existing trails depend on is DIGEST identity, not
whole-output identity: adding a non-volatile line changes the default
output while leaving every stored digest comparable.

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
                        qualified topic key matches scope.topics, or whose
                        depends or verifies intersects the persisted member
                        set (stored task inputs + entry tasks), or which a
                        member's own risk_mitigation_tasks names. That last
                        edge is member-side and INVERTED -- the follow-up
                        carries no back-reference and the member is usually
                        archived by then, so it is read from the member's
                        frontmatter (active tree or archive) and only live
                        active targets are reported
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
import signal
import subprocess
import sys
import time
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
# The vocabulary-clamped field builder; shared with work_report_gather so
# "neither sentinel means a real kind" holds by construction on both records.
from followup_kinds import followup_kind_field  # noqa: E402
import plan_paths  # noqa: E402
from record_protocol import (  # noqa: E402
    INVALID_ENUM, enum_field, has_record_breaking, sanitize_last_field,
    sanitize_middle_field,
)
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
#
# EXACTLY ONE ENTRY, always: the trail is single-version by design (load_schema
# reads one `const`), so a leftover key from an earlier bump would quietly
# re-admit documents this design means to reject as ERROR:invalid_trail.
#
# schema 1.1.0 pairs with normalization 1.0.0 (t1468_5): the bump added the
# OPTIONAL, display-only `entry.snapshot.followup_kind`, which never enters the
# normalized digest -- the digest hashes input records, and the snapshot
# reconstruction in _reconstruct_old_task_records reads only status + depends +
# gates_pending. The lock's contract runs one way: a *normalization* bump
# requires a schema bump, not the reverse. Should followup_kind ever enter the
# digest, NORMALIZATION_VERSION must bump too and every stored digest becomes
# incomparable.
SCHEMA_NORMALIZATION_LOCK = {"1.1.0": "1.0.0"}

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

# --- Delimiter safety -------------------------------------------------------
#
# The protocol has no escaping engine, so a value that can contain '|', CR or LF
# would make the record boundary undecidable. Refs, task metadata and drift
# details all come from user-editable task YAML, so none of them is pipe-free by
# construction -- each field class gets an explicit, tested policy instead of an
# assumption.
#
# That policy lives in lib/record_protocol.py (t1433), which this module used to
# carry a private copy of -- byte-identical to work_report_gather's. `_csv_entry`
# stays HERE because it adds a fourth reserved character (',') that only this
# module's csv-encoded list fields need. `_die` and the `trail_gather: ` prefix
# stay HERE too: a library path must not sys.exit, and the prefix is pinned (with
# a negative control) by the InfraExitCharacterizationTests section of
# tests/test_trail_gather.py.


def _csv_entry(value) -> str:
    """One member of a csv-encoded list field: ','/'|'/CR/LF -> `invalid`.
    Line transport only -- the digest always hashes the raw value."""
    text = str(value)
    if "," in text or has_record_breaking(text):
        return INVALID_ENUM
    return text


def _die(msg: str, code: int) -> None:
    print(f"trail_gather: {msg}", file=sys.stderr)
    sys.exit(code)


def emit_errors(out, errors: list[str]) -> None:
    for error in errors:
        print(f"ERROR:{sanitize_last_field(error)}", file=out)


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
    # `(?:^|.*/)`: `p<ID>` must START a path segment. The former `(?:.*/)?` made
    # the directory prefix optional, and `re.search` then matched mid-segment --
    # `aiplans/notp1159_root.md` was attributed to member 1159, shadowing its
    # real plan record (t1532).
    anchored = r"(?:^|.*/)"
    if "_" in own_id:
        parent, child = own_id.split("_", 1)
        pat = anchored + rf"p{parent}/p{parent}_{child}_[^/]*\.md"
    else:
        # `(?<!p<ID>/)`: a parent's plan lives DIRECTLY in the plan dir; the
        # `p<ID>/` subdir holds its children's plans. Without this guard the
        # prefix consumes `aiplans/p<ID>/` and the parent's pattern also matches
        # every child plan -- and because attribution takes the first match in
        # stored-input order, and the gatherer emits the child's ref first
        # ('/' < '_'), a faithfully-copied trail was reported STALE with an
        # un-clearable `plan_changed` (t1532). The lookbehind omits the leading
        # '/' so it also rejects a directory-less `p<ID>/p<ID>_<C>_*.md`.
        pat = anchored + rf"(?<!p{own_id}/)p{own_id}_[^/]*\.md"
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

def _canonical_refs(metadata: dict, project: str, key: str) -> list[str]:
    """Normalize a list-valued relation field to canonical refs in the OWNING
    project's namespace; unparseable entries stay verbatim (deterministic).
    Deduplicated: identical membership must never hash differently.

    Shared by every relation the module reads (`depends`, `verifies`,
    `risk_mitigation_tasks`) so owning-project semantics are defined once.
    """
    raw = metadata.get(key)
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


def _canonical_depends(metadata: dict, project: str) -> list[str]:
    """The digest-bearing relation (see task_record) -- kept under its own name
    because the digest contract is pinned to it."""
    return _canonical_refs(metadata, project, "depends")


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
    if has_record_breaking(ref):
        _die(f"ref {ref!r} contains '|', CR or LF and cannot round-trip "
             "through the protocol", EXIT_INFRA)
    return ref


def input_line(record: dict) -> str:
    exists = "true" if record["exists"] else "false"
    ref = _validated_ref_field(record["ref"])
    if record["kind"] == "task_file":
        depends = ",".join(_csv_entry(d) for d in record.get("depends", []))
        gates = ",".join(_csv_entry(g) for g in record.get("gates_pending", []))
        status = enum_field(record.get("status"))
        return f"INPUT:task_file|{exists}|{status}|{depends}|{gates}|{ref}"
    content_hash = record.get("content_hash") or "-"
    return f"INPUT:{record['kind']}|{exists}|{enum_field(content_hash)}|{ref}"


def member_line(row: TaskRow) -> str:
    ref = _validated_ref_field(row.ref)
    meta = row.metadata
    labels = meta.get("labels")
    labels_csv = ",".join(
        _csv_entry(l) for l in labels) if isinstance(labels, list) else ""
    return ("MEMBER:" + ref
            + f"|{enum_field(meta.get('status'))}"
            + f"|{enum_field(meta.get('priority'))}"
            + f"|{enum_field(meta.get('effort'))}"
            + f"|{enum_field(meta.get('boardcol'))}"
            + f"|{labels_csv}"
            + f"|{followup_kind_field(meta.get('followup_kind'))}"
            + f"|{sanitize_last_field(str(row.path))}")


def member_ext_line(row: TaskRow) -> str:
    """MEMBER_EXT: — per-member value/origin facts (t1569_1).

    A NEW line rather than extra fields on MEMBER:. That record's free-ish
    `path` field is last by contract, and DeterminismTests pins all eight of its
    positions specifically to make an insertion loud — so this goes beside it,
    never inside it.

    Emitted UNCONDITIONALLY (no --with-inflight): it needs no probe, no network
    and no git, the metadata is already read to build MEMBER:, and it is
    NON-VOLATILE — its fields change only when a task file changes. It is
    digest-excluded like every line here, structurally: these facts never enter
    an INPUT record, and trail_schema rejects unknown keys if one ever tried.

    Every field is sanitized and every field has a sentinel. t1569_3 parses this
    positionally, so a stray '|' would break the record and an empty field would
    be ambiguous. `created_at` and `anchor` are free-form hand-editable YAML at
    positions 2 and 3 — NOT last — so they take sanitize_middle_field().
    """
    ref = _validated_ref_field(row.ref)
    meta = row.metadata
    verifies = meta.get("verifies")
    verifies_csv = ",".join(
        _csv_entry(v) for v in verifies) if isinstance(verifies, list) else ""
    return ("MEMBER_EXT:" + ref
            + f"|{_middle_enum(meta.get('created_at'))}"
            + f"|{_middle_enum(meta.get('anchor'))}"
            + f"|{verifies_csv}"
            + f"|{enum_field(meta.get('risk_code_health'))}"
            + f"|{enum_field(meta.get('risk_goal_achievement'))}")


def _middle_enum(value) -> str:
    """enum_field()'s sentinel discipline, with middle-field delimiter safety.

    enum_field() alone would let a hand-typed '|' in `created_at:` split the
    record; sanitize_middle_field() alone would render an absent value as an
    empty field, which is indistinguishable from a present-but-empty one.
    """
    if value is None or value == "":
        return enum_field(None)
    return sanitize_middle_field(str(value))


# --- in-flight probe (--with-inflight; t1569_1) ------------------------------
#
# Everything below is OPT-IN. Without --with-inflight no INFLIGHT* line is
# emitted, no lock ref is read and no plan file is scanned -- that is what keeps
# every ordinary trail off the network and inside its latency budget.
#
# COMPATIBILITY BOUNDARY. The default snapshot is NOT byte-identical to the
# pre-change gatherer: MEMBER_EXT: is added unconditionally above. What IS
# guaranteed, and what existing trails actually depend on, is that the DIGEST:
# line is unchanged. Only the volatile INFLIGHT-prefixed lines are opt-in.
#
# DIGEST EXCLUSION is structural, not a convention: these facts never enter an
# INPUT record, and trail_schema._normalize_input_record() hard-errors on any
# unknown key, so a future attempt to smuggle one in fails loudly rather than
# invalidating every stored digest.

# Named budgets.
#
# The block budget must be able to BIND, which is a stronger requirement than
# exceeding the sum of the phases. It is consulted only through
# `min(block_deadline, now + _CLASSIFY_TIMEOUT_S)`, so it selects itself only
# when the work BEFORE classification has already consumed enough of it:
#
#   probes, worst case   gate 1 call + lock 3 calls = 4 x 5s  = 20s
#   git ls-files                                                5s   (bounded)
#   -------------------------------------------------------------------
#   elapsed before classify                                    25s
#   classify term                              25 + 10       = 35s  > 30s
#
# so the block deadline wins and the block branch is reachable. Bounding
# `git ls-files` is what makes that true: while it was unbounded the classify
# term was always <= 30s, the block could never be the smaller value, and the
# one call the budget was raised to cover could hang the snapshot forever.
_PROBE_TIMEOUT_S = 5
_CLASSIFY_TIMEOUT_S = 10
_INFLIGHT_TIMEOUT_S = 30

_LOCKS_REF = "origin/aitask-locks"
_LOCK_FILE_RE = re.compile(r"^t(\d+(?:_\d+)?)_lock\.yaml$")

# Kill-switch. Set to "1" to make --with-inflight a no-op regardless of argv.
# Tests need this in addition to the injectable seams below, because run_cli
# executes main() IN-PROCESS: without it, a probe that escaped the fixture would
# reach the developer's real repository.
_INFLIGHT_OFF_ENV = "AIT_TRAIL_NO_INFLIGHT"


def _run_bounded(cmd, timeout, cwd=None) -> "tuple[int, str]":
    """Run `cmd`, killing the whole PROCESS GROUP on timeout.

    subprocess.run(timeout=) kills only the direct child. The gate probe shells
    out to aitask_query_files.sh, which spawns its own git children, so a plain
    timeout would orphan the grandchildren. start_new_session puts the child in
    its own group; on timeout we signal the group.

    Raises subprocess.TimeoutExpired on expiry; returns (rc, stdout) otherwise.
    """
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        start_new_session=True, cwd=None if cwd is None else str(cwd))
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        proc.communicate()
        raise
    return proc.returncode, out.decode("utf-8", "replace")


@dataclass
class SourceResult:
    """One evidence source's outcome. `status` is PROBE HEALTH only."""
    name: str                       # gate | lock | tracked
    status: str = "ok"              # ok | degraded | unavailable | not_consulted
    age: "int | None" = None        # seconds; None renders as '-'
    reason: "str | None" = None
    ids: "dict[str, tuple[str, str]]" = field(default_factory=dict)

    def line(self) -> str:
        age = "-" if self.age is None else str(self.age)
        return (f"INFLIGHT_SOURCE:{self.name}|{self.status}|{age}|"
                f"{self.reason or '-'}")


def probe_gate_source(root: Path) -> SourceResult:
    """`aitask_query_files.sh inflight` -> {id: (resume_point, archive_status)}.

    The fourth field is the PRODUCER's `<archive_status>`
    (`aitask_query_files.sh:94`): NO_GATES | ALL_PASS | BLOCKED:<csv>. It is
    republished under that name rather than as "gate state", which it is not.
    A lock-only task contributes `unknown` -- the established absent-value
    sentinel -- so the published enum is that vocabulary plus `unknown`.

    Requires `Implementing` AND a `## Gate Runs` heading, so it is INCOMPLETE by
    construction -- measured live on this repo it surfaced 0 of 4 Implementing
    tasks. That is precisely why the union exists and why the scan status claims
    probe health rather than completeness.
    """
    result = SourceResult("gate")
    script = os.path.join(_SCRIPTS_DIR, "aitask_query_files.sh")
    try:
        rc, out = _run_bounded([script, "inflight"], _PROBE_TIMEOUT_S, cwd=root)
    except subprocess.TimeoutExpired:
        result.status, result.reason = "unavailable", "timeout"
        return result
    except OSError:
        result.status, result.reason = "unavailable", "scan_error"
        return result
    if rc != 0:
        result.status, result.reason = "unavailable", "scan_error"
        return result
    for line in out.split("\n"):
        if not line.startswith("INFLIGHT:"):
            continue
        parts = line[len("INFLIGHT:"):].split("|")
        if len(parts) >= 4:
            result.ids[parts[0]] = (parts[2], parts[3])
    return result


def probe_lock_source(root: Path) -> SourceResult:
    """Locked task ids from the LOCAL `origin/aitask-locks` tree. No fetch.

    Deliberately not `ait lock --list`: that performs a network `git fetch` and
    prints ANSI-coloured human text to stdout on its degenerate paths. Reading
    the cached ref keeps the shared gatherer off the network -- which is why the
    cache's AGE is load-bearing and reported here.
    """
    result = SourceResult("lock")

    def git(*a):
        return _run_bounded(["git", "-C", str(root), *a], _PROBE_TIMEOUT_S)

    try:
        rc, _ = git("rev-parse", "--verify", "--quiet", _LOCKS_REF + "^{tree}")
        if rc != 0:
            result.status, result.reason = "unavailable", "no_local_ref"
            return result
        rc, listing = git("ls-tree", "--name-only", _LOCKS_REF)
        if rc != 0:
            result.status, result.reason = "unavailable", "unreadable_tree"
            return result
    except subprocess.TimeoutExpired:
        result.status, result.reason = "unavailable", "timeout"
        return result
    except OSError:
        result.status, result.reason = "unavailable", "scan_error"
        return result

    for name in listing.split("\n"):
        match = _LOCK_FILE_RE.match(name.strip())
        if match:
            result.ids[match.group(1)] = ("-", "unknown")

    result.age, age_reason = _locks_cache_age(root)
    if result.age is None:
        result.status, result.reason = "degraded", age_reason
    return result


def _locks_cache_age(root: Path) -> "tuple[int | None, str | None]":
    """Seconds since THIS CLONE last updated the ref, from its reflog.

    NOT `git log -1 --format=%ct`: that is when the last lock was committed on
    whichever peer machine, while the consumer's question is how stale this
    cache is. The two diverge both ways -- a quiet branch fetched a second ago
    reports days, and a peer with a forward-skewed clock on a branch whose whole
    purpose is multi-host coordination yields a NEGATIVE age.

    A negative or unavailable age emits '-', never 0. Clamping to 0 would be
    fail-open: 0 reads as "updated this instant", the most plausible-and-wrong
    value this field can carry, over an arbitrarily stale cache.
    """
    try:
        rc, out = _run_bounded(
            ["git", "-C", str(root), "reflog", "show", "--date=raw",
             "-n", "1", _LOCKS_REF], _PROBE_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError):
        return None, "timeout"
    if rc != 0 or not out.strip():
        return None, "no_reflog"
    match = re.search(r"@\{(\d+)\s", out)
    if not match:
        return None, "no_reflog"
    age = int(time.time()) - int(match.group(1))
    if age < 0:
        return None, "clock_skew"
    return age, None


# Injectable seams. Tests replace these rather than the functions above, so a
# probe can be driven deterministically without a network, a locks branch, or a
# dependence on whatever repository happens to contain TMPDIR.
_GATE_PROBE = probe_gate_source
_LOCK_PROBE = probe_lock_source


def _classify_plan_paths(row, tree, tracked, tracked_dirs):
    """One task -> (class, path) records, or a single task sentinel.

    Each zero-path cause gets its OWN sentinel, because t1569_3 decides per
    task and a global field cannot answer a per-task question in a mixed repo:

        no plan file        -> no_plan
        plan yields nothing -> no_tokens
        plan unreadable     -> unreadable      (an I/O failure, not a corpus fact)

    Returns (records, has_plan, read_ok, yielded_tokens). `has_plan` is tracked
    separately from `read_ok` so the corpus axis can tell "no task has a plan"
    (durable, nothing to retry) from "plans exist but none could be read" (an
    I/O failure, retryable) -- the per-task sentinels already separate them, and
    a global field must not be less precise than the lines it summarizes.
    """
    plan = plan_path_for(row, tree) if row is not None else None
    if plan is None:
        return [("no_plan", "-")], False, False, False
    try:
        tokens = plan_paths.extract_file(plan)
    except (OSError, UnicodeDecodeError):
        return [("unreadable", "-")], True, False, False
    if not tokens:
        return [("no_tokens", "-")], True, True, False
    return ([(plan_paths.classify(t, tracked, tracked_dirs), t)
             for t in tokens], True, True, True)


def emit_inflight(out, tree, roots, local_name: str) -> None:
    """Emit the four INFLIGHT* records. Never raises; never fails the snapshot.

    Every degradation is a content state on stdout with exit 0.
    """
    root = tree.root
    deadline = time.monotonic() + _INFLIGHT_TIMEOUT_S

    gate = _GATE_PROBE(root)
    lock = _LOCK_PROBE(root)
    print(gate.line(), file=out)
    print(lock.line(), file=out)

    # SOURCES DEGRADE INDEPENDENTLY. The lock tree resolves through a different
    # command than the gated scan, so a clone with no cached ref must still
    # yield every gated record -- discarding them would manufacture exactly the
    # false no-conflict the parent task forbids.
    # Scoped to the two ENUMERATION probes -- the ones that answer "which tasks
    # are in flight". `tracked` is a third declared source but reports
    # CLASSIFICATION evidence, a different question, so folding it in here would
    # conflate two axes. The value names its own scope for exactly that reason:
    # "both_sources_ok" beside three declared sources invites a reader to assume
    # a clean bill of health for all three, which is the same trap as the
    # original "full" this vocabulary already replaced once.
    healthy = sum(1 for s in (gate, lock) if s.status != "unavailable")
    source_status = ("both_enumeration_ok" if healthy == 2
                     else "one_enumeration_ok" if healthy == 1
                     else "no_enumeration")

    merged: dict[str, list] = {}
    for src, tag in ((gate, "gate"), (lock, "lock")):
        for task_id, (resume, archive_status) in src.ids.items():
            if task_id in merged:
                merged[task_id][0] = "both"
                if merged[task_id][1] == "-":
                    merged[task_id][1] = resume
                    merged[task_id][2] = archive_status
            else:
                merged[task_id] = [tag, resume, archive_status]

    ordered = sorted(merged)
    for task_id in ordered:
        tag, resume, archive_status = merged[task_id]
        ref = _validated_ref_field(f"{local_name}#{task_id}")
        print(f"INFLIGHT:{ref}|{tag}|{resume}|{enum_field(archive_status)}",
              file=out)

    truncated = False
    # Declared unconditionally. With no in-flight task there is no
    # classification to have evidence about, but this contract is careful
    # everywhere else that absence is never the signal -- no_plan, no_tokens and
    # unclassified all exist for that reason -- so the state is NAMED rather
    # than represented by a missing line.
    tracked_src = SourceResult("tracked")
    if not ordered:
        tracked_src.status, tracked_src.reason = "not_consulted", "no_tasks"
        print(tracked_src.line(), file=out)
    if ordered:
        # `git ls-files` is the CLASSIFICATION evidence, and it is its own
        # evidence source -- reported on its own line, never swallowed.
        #
        # Substituting empty sets here (as an earlier revision did) would turn
        # an infrastructure failure into a measured result: every path would
        # classify `phantom`, they would still count as yielded, the corpus axis
        # would read `extractable` and both probe lines would read `ok`. A
        # consumer would receive a complete-looking, healthy-looking
        # classification derived from ZERO git evidence -- a false negative for
        # every `tracked` and `planned_new` collision t1569_3 exists to catch.
        # plan_paths.tracked_sets() documents that its callers must decide;
        # deciding means reporting, not defaulting.
        tracked = tracked_dirs = None
        try:
            tracked, tracked_dirs = plan_paths.tracked_sets(root)
        except subprocess.TimeoutExpired:
            tracked_src.status, tracked_src.reason = "unavailable", "timeout"
        except (subprocess.CalledProcessError, OSError):
            tracked_src.status, tracked_src.reason = "unavailable", "scan_error"
        print(tracked_src.line(), file=out)

        if tracked is None:
            # Classification did not run for ANY task. Each gets the sentinel
            # that says exactly that, so no task looks classified.
            for task_id in ordered:
                rref = _validated_ref_field(f"{local_name}#{task_id}")
                print(f"INFLIGHT_PATH:{rref}|unclassified|-", file=out)
            # `unclassifiable`, never `not_scanned`. Tasks WERE enumerated —
            # emitting a value glossed "nothing enumerated" beside a non-zero
            # n_tasks would make one value mean two opposite things: "there is
            # no in-flight work" and "there is in-flight work and we have no
            # idea what it touches". t1569_3 branches on this field.
            print(f"INFLIGHT_SCAN:{len(ordered)}|unclassifiable|"
                  f"{source_status}", file=out)
            return

        classify_deadline = min(deadline,
                                time.monotonic() + _CLASSIFY_TIMEOUT_S)
        n_plan = n_read = n_yield = 0
        for index, task_id in enumerate(ordered):
            if time.monotonic() > classify_deadline:
                # Budget expired. Every task not yet reached gets its OWN
                # sentinel -- without it, "ran out of clock" and "no plan file"
                # are the same observable, and t1569_3 would read the former as
                # the latter.
                truncated = True
                for remaining in ordered[index:]:
                    rref = _validated_ref_field(f"{local_name}#{remaining}")
                    print(f"INFLIGHT_PATH:{rref}|unclassified|-", file=out)
                break
            row = tree.by_own_id.get(task_id)
            records, has_plan, read_ok, yielded = _classify_plan_paths(
                row, tree, tracked, tracked_dirs)
            n_plan += 1 if has_plan else 0
            n_read += 1 if read_ok else 0
            n_yield += 1 if yielded else 0
            ref = _validated_ref_field(f"{local_name}#{task_id}")
            for cls, path in records:
                rendered = "-" if path == "-" else sanitize_last_field(path)
                print(f"INFLIGHT_PATH:{ref}|{cls}|{rendered}", file=out)
    else:
        n_plan = n_read = n_yield = 0

    print(f"INFLIGHT_SCAN:{len(ordered)}|"
          f"{_corpus_status(len(ordered), n_plan, n_read, n_yield, truncated)}|"
          f"{source_status}", file=out)


def _corpus_status(n_tasks: int, n_plan: int, n_read: int, n_yield: int,
                   truncated: bool) -> str:
    """The corpus axis, judged ONLY over plans actually read.

    Evaluated in a declared order, because several conditions can hold at once
    and an undeclared precedence is how a value ends up meaning two things.
    Unreadable and absent plans are EXCLUDED rather than counted as empty:
    counting them would let one permissions error file an I/O failure as a
    durable corpus fact.
    """
    if truncated:
        return "truncated"
    if n_tasks == 0:
        # Nothing was enumerated, so there is no corpus to judge. Distinct from
        # `unclassifiable`, which means tasks WERE enumerated but the
        # classification evidence (git ls-files) was unavailable.
        return "not_scanned"
    if n_plan == 0:
        # Tasks were enumerated and NONE has a plan. A durable corpus fact with
        # nothing to retry -- distinct from the I/O failure below.
        return "no_plans"
    if n_read == 0:
        # Plans exist but none could be read. Retryable, an operator problem.
        return "unread_io"
    if n_yield == 0:
        return "no_extractable_paths"
    if n_yield < n_read:
        return "partial_extractable"
    return "extractable"


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
    for ref in sorted(unique_rows):
        print(member_ext_line(unique_rows[ref]), file=out)
    ordered = sorted(records, key=lambda r: (r["kind"], r["ref"]))
    for record in ordered:
        print(input_line(record), file=out)
    print(f"DIGEST:{trail_schema.input_digest(records)}", file=out)
    # AFTER the digest, and gated: these lines are volatile and digest-excluded.
    # The env kill-switch is checked here as well as at the flag, so a test that
    # never reaches argv still cannot let a probe escape its fixture.
    if getattr(args, "with_inflight", False)             and os.environ.get(_INFLIGHT_OFF_ENV) != "1":
        local_tree = trees.get(local_name)
        if local_tree is not None:
            emit_inflight(out, local_tree, roots, local_name)
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


def _archived_metadata(bare_id: str, archived_dir: Path) -> dict | None:
    """Frontmatter of an archived task, or None when it is NOT in the archive.

    `{}` (archived but unparseable) is NOT the same as None: collapsing the two
    would reclassify every malformed archived task from `task_archived` to
    `task_deleted`. Callers MUST branch on `is not None`, never on truthiness.

    Deliberately does not apply _load_row's phantom-stub rule -- the archived
    path never had that guard, and adding it would flip archived stubs to
    `task_deleted` too.
    """
    archived = find_archived_markdown_by_id(bare_id, archived_dir)
    if archived is None:
        return None
    _, text = archived
    try:
        parsed = parse_frontmatter(text)
    except Exception:
        parsed = None
    return parsed[0] if parsed else {}


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
    meta = _archived_metadata(inp.bare_id, tree.archived_dir)
    if meta is not None:  # `{}` means archived-but-unparseable, NOT absent
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
        reasons.append((code, task, sanitize_last_field(detail)))

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
            verifies = set(_canonical_refs(row.metadata, proj, "verifies"))
            if qualified_topic in scope_topics:
                add("new_related_task", row.ref,
                    f"new task in topic {qualified_topic}")
            elif depends & member_refs:
                add("new_related_task", row.ref,
                    f"new task depends on {sorted(depends & member_refs)}")
            elif verifies & member_refs:
                # Manual-verification back-reference. Not always masked by a
                # depends edge: the archive carry-over and aggregate-sibling
                # producers both write `verifies` without a matching `depends`.
                add("new_related_task", row.ref,
                    f"new task verifies {sorted(verifies & member_refs)}")

    # Member-side edge (INVERTED): risk_mitigation_tasks is written on the
    # MEMBER at task-workflow Step 8d and names the follow-up. The follow-up
    # carries no back-reference, and the member is usually archived by the time
    # it matters (real case: archived aitasks#1293 -> live aitasks#1426), so
    # neither the live-row scan above nor a depends edge can ever reach it.
    #
    # Invariant: member_refs is a subset of (baseline | input_refs) -- entry_refs
    # feed baseline via _doc_task_refs, and task_inputs' canonicals are half of
    # input_refs. That containment alone makes self-reference, member-targets
    # and cycles structurally unreportable, so none needs its own guard.
    archived_meta: dict[tuple[str, str], dict | None] = {}
    for member_ref in sorted(member_refs):
        parsed = parse_ref(member_ref)
        if parsed is None:
            continue  # the schema tolerates a bare `1234` entry ref
        member_proj, member_bare = parsed
        member_tree = fresh.get(member_proj)
        if member_tree is None:
            continue
        member_row = member_tree.by_own_id.get(member_bare)
        if member_row is not None:
            member_meta = member_row.metadata
        else:
            cache_key = (member_proj, member_bare)
            if cache_key not in archived_meta:
                archived_meta[cache_key] = _archived_metadata(
                    member_bare, member_tree.archived_dir)
            member_meta = archived_meta[cache_key]
        if not member_meta:  # absent, or archived-but-unparseable
            continue
        for ref in _canonical_refs(member_meta, member_proj,
                                   "risk_mitigation_tasks"):
            target_parsed = parse_ref(ref)
            if target_parsed is None:
                continue
            # .get(): a cross-repo target's project may not be scanned at all.
            # Never widen the `projects` set for it -- that could stage an
            # unresolved_project error and turn a working drift run into an
            # ERROR-only one, and would widen the live-row scan to a new tree.
            target_tree = fresh.get(target_parsed[0])
            target = (target_tree.by_own_id.get(target_parsed[1])
                      if target_tree is not None else None)
            if target is None:
                continue  # archived / deleted / unscoped: not a candidate
            if target.ref in baseline or target.ref in input_refs:
                continue
            # This detail MUST keep sorting after every "new task ..." detail
            # ('n' < 'r'): dedup_reasons keeps the lexicographically smallest
            # detail per (code, task_ref), so a doubly-reachable target retains
            # its topic/depends wording byte-for-byte. Renaming this prefix
            # would silently rewrite existing drift output --
            # test_doubly_reachable_target_keeps_depends_detail pins it.
            add("new_related_task", target.ref,
                f"risk-mitigation follow-up of {member_ref}")

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
    snap.add_argument("--with-inflight", action="store_true",
                      help="probe in-flight tasks + their planned surfaces "
                           "(opt-in: reads the local locks ref and plan files)")
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
