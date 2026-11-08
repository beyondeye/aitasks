#!/usr/bin/env python3
"""relations_schema.py - schema, vocabulary and digests of the relations store.

The record shapes of aidocs/framework/task_relations.md D2: the relations record
(``records/``), the obsolescence assessment (``obsolescence/``), the human
dismissal (``dismissals/``) and the plan-approval stamp (``approvals/``).

Writers fail closed: an unknown key, type, relation type or basis kind raises
``SchemaError`` and nothing is written. Every kind carries ``task_created_at``,
the live task's ``created_at`` when the record was made, so a record of a
deleted task whose (child) id was reused is told apart from the current one
(D2 identity, D11).

This module also owns the ONE digest normalization (D2 "Digests"), used by every
writer and every reader:

* ``normalize_body`` -- the task description without its frontmatter and its
  framework sections (``## Inbox``, ``## Gate Runs``, folded history), through
  ``plan_paths.task_body_text``;
* ``normalize_plan`` -- the plan without its YAML header and without the
  sections the workflow appends after approval (``## Final Implementation
  Notes``, ``## Post-Review Changes``).

and the ONE comparison, ``wins()``: identity first, then ``(stage, at)``.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cross_repo_notation  # noqa: E402
import plan_paths  # noqa: E402

SCHEMA = "aitask-relations/1"
LAYOUT_VERSION = "1"
KINDS = ("records", "obsolescence", "dismissals", "approvals")

TYPES = {
    "affects": "directed",
    "advisory_precedes": "directed",
    "coordinates_with": "symmetric",
    "duplicates": "symmetric",
    "supersedes": "directed",
    "informs": "directed",
}
IMPACT_BASES = frozenset({"path", "symbol", "token"})
CONNECTIVITY_BASES = frozenset({"task_ref"})
BASIS_KINDS = IMPACT_BASES | CONNECTIVITY_BASES
NEEDS_IMPACT = frozenset({"affects", "coordinates_with", "supersedes"})
TRIGGERS = frozenset({"created", "plan_approved", "fold", "sweep", "manual",
                      "landed"})
OUTCOMES = frozenset({"related", "unrelated", "unreadable"})
BANDS = frozenset({"none", "low", "medium", "high"})
DISPOSITIONS = frozenset({"keep", "refresh", "fold_into", "drop"})
MAX_DESCRIPTION = 600

_ID_RE = re.compile(r"^t?(\d+(?:_\d+)?)$")
_PROJECT_RE = re.compile(r"^[a-z0-9_-]+$")  # cross_repo_references.md project-name grammar
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PATH_RE = re.compile(r"^(records|obsolescence|dismissals|approvals)/t(\d+(?:_\d+)?)\.json$")
_FINAL_SECTIONS = ("## Final Implementation Notes", "## Post-Review Changes")


class SchemaError(ValueError):
    """A record failed validation; nothing may be written."""


# --------------------------------------------------------------------- refs

def norm_id(value) -> str:
    """``'1981_1'`` from ``1981_1`` / ``'t1981_1'`` / ``'aitasks#1981_1'``."""
    text = str(value).strip()
    if "#" in text:
        return parse_ref(text)[1]
    m = _ID_RE.match(text)
    if not m:
        raise SchemaError(f"bad task id: {value!r}")
    return m.group(1)


def parse_ref(ref) -> "tuple[str, str]":
    """``(project, id)`` of a canonical ``<project>#<id>`` ref.

    Delegates to the shared ``cross_repo_notation.parse_ref`` so the store
    accepts exactly the notation ``ait note`` and the trails accept
    (aidocs/framework/cross_repo_references.md); a non-match is a SchemaError.
    """
    parsed = cross_repo_notation.parse_ref(str(ref)) if isinstance(ref, (str, int)) else None
    if parsed is None:
        raise SchemaError(f"bad task ref: {ref!r}")
    return parsed


def qref(ref) -> str:
    """Normalized form of an already-qualified ref (``t`` prefix stripped)."""
    project, tid = parse_ref(ref)
    return f"{project}#{tid}"


def valid_project(name) -> bool:
    return isinstance(name, str) and bool(_PROJECT_RE.match(name))


def canon_ref(value, project) -> str:
    """The canonical ref of an id or ref.

    A qualified ref keeps its own project (never rewritten); a bare id is
    qualified with ``project``, the LOCAL project's name.
    """
    text = str(value).strip()
    if "#" in text:
        proj, tid = parse_ref(text)
        return f"{proj}#{tid}"
    return f"{project}#{norm_id(text)}"


def store_path(kind: str, task_id) -> str:
    if kind not in KINDS:
        raise SchemaError(f"unknown kind: {kind!r}")
    return f"{kind}/t{norm_id(task_id)}.json"


def parse_store_path(path: str):
    """``(kind, id)`` of a store path, or None for a non-record path."""
    m = _PATH_RE.match(path)
    if not m:
        return None
    return m.group(1), m.group(2)


# ------------------------------------------------------------------ digests

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def normalize_body(raw_task_text: str) -> str:
    # Edge blank lines are dropped: cutting a framework section leaves the
    # blank line that separated it, which is not a change to the description.
    body = plan_paths.task_body_text(raw_task_text.replace("\r\n", "\n"))
    return body.strip("\n") + "\n"


def normalize_plan(raw_plan_text: str) -> str:
    text = raw_plan_text.replace("\r\n", "\n")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 4)
            text = "" if nl == -1 else text[nl + 1:]
    out, skipping = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            skipping = any(line.rstrip() == h or line.startswith(h + " ")
                           for h in _FINAL_SECTIONS)
        if not skipping:
            out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def digests(task_text, plan_text=None) -> dict:
    """``{body_sha256, plan_sha256}``; ``plan_sha256`` is None with no plan."""
    return {
        "body_sha256": sha256_text(normalize_body(task_text)) if task_text is not None else None,
        "plan_sha256": sha256_text(normalize_plan(plan_text)) if plan_text is not None else None,
    }


# --------------------------------------------------------------- validation

def _require(cond, msg):
    if not cond:
        raise SchemaError(msg)


def _keys(obj, where, required, optional=()):
    _require(isinstance(obj, dict), f"{where}: expected an object")
    unknown = set(obj) - set(required) - set(optional)
    _require(not unknown, f"{where}: unknown key(s) {sorted(unknown)}")
    missing = [k for k in required if k not in obj]
    _require(not missing, f"{where}: missing key(s) {missing}")


def _str(value, where, allow_empty=False):
    _require(isinstance(value, str) and (allow_empty or value), f"{where}: expected a string")


def _sha(value, where, nullable=False):
    if nullable and value is None:
        return
    _require(isinstance(value, str) and _SHA256_RE.match(value), f"{where}: expected a sha256")


def _ref(value, where):
    _str(value, where)
    parse_ref(value)


def _repo_path(value, where):
    _str(value, where)
    _require(not value.startswith("/"), f"{where}: absolute path {value!r}")
    _require("/../" not in f"/{value}/" and not value.startswith("../"),
             f"{where}: '..' segment in {value!r}")
    _require("/" in value.strip("/"), f"{where}: bare basename {value!r} (store a full repository path)")


def _validate_run(run, where):
    _keys(run, where, ("id", "trigger", "stage", "at"),
          ("host", "agent_string", "code_base", "data_base", "candidate_provider"))
    _str(run["id"], f"{where}.id")
    _require(run["trigger"] in TRIGGERS, f"{where}.trigger: unknown {run['trigger']!r}")
    _require(run["stage"] in (1, 2), f"{where}.stage: expected 1 or 2")
    _str(run["at"], f"{where}.at")
    for key in ("host", "agent_string", "code_base", "data_base", "candidate_provider"):
        if key in run:
            _str(run[key], f"{where}.{key}", allow_empty=True)


def _validate_digest_pair(obj, where):
    _keys(obj, where, ("body_sha256", "plan_sha256"))
    _sha(obj["body_sha256"], f"{where}.body_sha256")
    _sha(obj["plan_sha256"], f"{where}.plan_sha256", nullable=True)


def validate_relations_record(rec):
    _keys(rec, "record",
          ("schema", "task", "task_created_at", "analysed", "run", "inputs", "relations"),
          ("considered", "usage", "coverage"))
    _require(rec["schema"] == SCHEMA, f"record.schema: expected {SCHEMA}")
    _ref(rec["task"], "record.task")
    _str(rec["task_created_at"], "record.task_created_at")
    _require(isinstance(rec["analysed"], bool), "record.analysed: expected a boolean")
    _validate_run(rec["run"], "record.run")
    inputs = rec["inputs"]
    # screening_sha256 (t1981_3): digest of the provider's screening inputs
    # (cards, evidence, coverage, truncation), so UP_TO_DATE also sees evidence
    # changes. Optional, and part of aitask-relations/1 from its first release
    # (D2 "Schema compatibility").
    _keys(inputs, "record.inputs", ("source", "candidates"), ("screening_sha256",))
    _validate_digest_pair(inputs["source"], "record.inputs.source")
    if "screening_sha256" in inputs:
        _sha(inputs["screening_sha256"], "record.inputs.screening_sha256")
    _require(isinstance(inputs["candidates"], list), "record.inputs.candidates: expected a list")
    cand_refs = set()
    for i, cand in enumerate(inputs["candidates"]):
        where = f"record.inputs.candidates[{i}]"
        _keys(cand, where, ("ref", "created_at", "body_sha256", "plan_sha256"))
        _ref(cand["ref"], f"{where}.ref")
        _str(cand["created_at"], f"{where}.created_at")
        _sha(cand["body_sha256"], f"{where}.body_sha256", nullable=True)
        _sha(cand["plan_sha256"], f"{where}.plan_sha256", nullable=True)
        cand_refs.add(qref(cand["ref"]))
    for i, item in enumerate(rec.get("considered", [])):
        where = f"record.considered[{i}]"
        _keys(item, where, ("ref", "outcome"), ("sources",))
        _ref(item["ref"], f"{where}.ref")
        _require(item["outcome"] in OUTCOMES, f"{where}.outcome: unknown {item['outcome']!r}")
        if "sources" in item:
            _require(isinstance(item["sources"], list)
                     and all(isinstance(s, str) for s in item["sources"]),
                     f"{where}.sources: expected a list of strings")
    _require(isinstance(rec["relations"], list), "record.relations: expected a list")
    own = qref(rec["task"])
    for i, rel in enumerate(rec["relations"]):
        where = f"record.relations[{i}]"
        _keys(rel, where, ("from", "to", "type", "description", "basis"), ("evidence",))
        _ref(rel["from"], f"{where}.from")
        _ref(rel["to"], f"{where}.to")
        _require(rel["type"] in TYPES, f"{where}.type: unknown relation type {rel['type']!r}")
        _str(rel["description"], f"{where}.description")
        _require(len(rel["description"]) <= MAX_DESCRIPTION,
                 f"{where}.description: over {MAX_DESCRIPTION} characters")
        ends = {qref(rel["from"]), qref(rel["to"])}
        _require(len(ends) == 2, f"{where}: a relation needs two distinct tasks")
        _require(own in ends, f"{where}: neither end is the record's task {own}")
        (other,) = ends - {own}
        _require(other in cand_refs,
                 f"{where}: end {other} has no inputs.candidates[] entry")
        _require(isinstance(rel["basis"], list), f"{where}.basis: expected a list")
        kinds = set()
        for j, basis in enumerate(rel["basis"]):
            bwhere = f"{where}.basis[{j}]"
            _keys(basis, bwhere, ("kind", "value"))
            _require(basis["kind"] in BASIS_KINDS, f"{bwhere}.kind: unknown basis kind {basis['kind']!r}")
            if basis["kind"] == "path":
                _repo_path(basis["value"], f"{bwhere}.value")
            else:
                _str(basis["value"], f"{bwhere}.value")
            kinds.add(basis["kind"])
        if rel["type"] in NEEDS_IMPACT:
            _require(kinds & IMPACT_BASES,
                     f"{where}: type {rel['type']} needs at least one impact basis (path/symbol/token)")
        for j, ev in enumerate(rel.get("evidence", [])):
            _keys(ev, f"{where}.evidence[{j}]", ("source", "detail"))
            _str(ev["source"], f"{where}.evidence[{j}].source")
            _str(ev["detail"], f"{where}.evidence[{j}].detail", allow_empty=True)
    if "usage" in rec:
        _keys(rec["usage"], "record.usage", (), ("input_tokens", "output_tokens", "cost_usd", "wall_s"))
    if "coverage" in rec:
        _keys(rec["coverage"], "record.coverage", ("missing_sources",))
        _require(isinstance(rec["coverage"]["missing_sources"], list),
                 "record.coverage.missing_sources: expected a list")


def validate_obsolescence(rec):
    _keys(rec, "obsolescence",
          ("schema", "task", "task_created_at", "run", "inputs", "evidence", "band",
           "reasons", "disposition"), ("fold_target", "usage"))
    _require(rec["schema"] == SCHEMA, f"obsolescence.schema: expected {SCHEMA}")
    _ref(rec["task"], "obsolescence.task")
    _str(rec["task_created_at"], "obsolescence.task_created_at")
    _validate_run(rec["run"], "obsolescence.run")
    _keys(rec["inputs"], "obsolescence.inputs", ("body_sha256", "plan_sha256", "evidence_digest"))
    _sha(rec["inputs"]["body_sha256"], "obsolescence.inputs.body_sha256")
    _sha(rec["inputs"]["plan_sha256"], "obsolescence.inputs.plan_sha256", nullable=True)
    _sha(rec["inputs"]["evidence_digest"], "obsolescence.inputs.evidence_digest")
    ids = set()
    _require(isinstance(rec["evidence"], list), "obsolescence.evidence: expected a list")
    for i, ev in enumerate(rec["evidence"]):
        _keys(ev, f"obsolescence.evidence[{i}]", ("id", "kind", "detail", "source"))
        ids.add(ev["id"])
    _require(rec["band"] in BANDS, f"obsolescence.band: unknown {rec['band']!r}")
    _require(isinstance(rec["reasons"], list), "obsolescence.reasons: expected a list")
    for i, reason in enumerate(rec["reasons"]):
        _keys(reason, f"obsolescence.reasons[{i}]", ("text", "evidence_ids"))
        _require(set(reason["evidence_ids"]) <= ids,
                 f"obsolescence.reasons[{i}]: unknown evidence id")
    _require(rec["disposition"] in DISPOSITIONS,
             f"obsolescence.disposition: unknown {rec['disposition']!r}")
    if rec["disposition"] == "fold_into":
        _ref(rec.get("fold_target"), "obsolescence.fold_target")


def validate_dismissal(rec):
    _keys(rec, "dismissal", ("task", "task_created_at", "at", "by", "evidence_digest"), ("note",))
    _ref(rec["task"], "dismissal.task")
    _str(rec["task_created_at"], "dismissal.task_created_at")
    _str(rec["at"], "dismissal.at")
    _str(rec["by"], "dismissal.by")
    _sha(rec["evidence_digest"], "dismissal.evidence_digest")
    if "note" in rec:
        _str(rec["note"], "dismissal.note", allow_empty=True)


def validate_approval(rec):
    _keys(rec, "approval",
          ("task", "task_created_at", "approved_at", "data_commit", "body_sha256", "plan_sha256"))
    _ref(rec["task"], "approval.task")
    _str(rec["task_created_at"], "approval.task_created_at")
    _str(rec["approved_at"], "approval.approved_at")
    _str(rec["data_commit"], "approval.data_commit")
    _sha(rec["body_sha256"], "approval.body_sha256")
    _sha(rec["plan_sha256"], "approval.plan_sha256")


_VALIDATORS = {
    "records": validate_relations_record,
    "obsolescence": validate_obsolescence,
    "dismissals": validate_dismissal,
    "approvals": validate_approval,
}


def validate(kind: str, path: str, obj) -> None:
    """Validate ``obj`` as a ``kind`` record stored at ``path``."""
    parsed = parse_store_path(path)
    _require(parsed is not None, f"bad store path: {path!r}")
    _require(parsed[0] == kind, f"path {path!r} is not a {kind} path")
    _VALIDATORS[kind](obj)
    _require(norm_id(obj["task"]) == parsed[1],
             f"path {path!r} does not match the record's task {obj['task']}")


# --------------------------------------------------------------- comparison

def order_key(kind: str, obj) -> tuple:
    if kind in ("records", "obsolescence"):
        return (obj["run"]["stage"], obj["run"]["at"])
    if kind == "approvals":
        return (0, obj["approved_at"])
    return (0, obj["at"])


def wins(kind: str, new, old, live_created_at) -> bool:
    """True when ``new`` should replace ``old`` (neither may be None).

    Identity first: when the live task's ``created_at`` is known and exactly
    one side belongs to that incarnation, that side wins whatever its stage or
    time. Otherwise newest-wins, ``order_key(new) >= order_key(old)``.
    """
    if new is None or old is None:
        raise ValueError("wins() compares two records; a deletion is merge_path's job")
    if live_created_at is not None:
        new_live = new.get("task_created_at") == live_created_at
        old_live = old.get("task_created_at") == live_created_at
        if new_live != old_live:
            return new_live
    return order_key(kind, new) >= order_key(kind, old)
