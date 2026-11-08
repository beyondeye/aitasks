#!/usr/bin/env python3
"""relation_candidates_contract.py - the candidate-provider contract (t1981_3).

The worker (``relations_worker.py``) consumes, and t1981_2's generator
(``aitask_relation_candidates.sh``) produces, ONE result shape. This module owns
it, so neither side carries a private copy:

* ``validate(obj)`` - every required field and type, the closed tag vocabulary,
  coverage, and the snapshot digest echoes. A violation raises
  ``ContractError(reason)``; the worker turns it into a failed job, never into
  "zero candidates".
* ``parse_json_stdout(text)`` - ``--json`` stdout must be EXACTLY one JSON
  object (diagnostics go to stderr).
* ``to_json(result)`` / ``to_text(result)`` - the two renderings of one internal
  result. The text one is the agent-facing line protocol; ``parse_text`` reads
  it back so a contract test can prove both carry the same provider, evidence,
  coverage and truncation information. t1981_2 adds its ``UNCONFIRMED:``
  fallback rows to this renderer, not to a second one.

The screening snapshot (aidocs/framework/task_relations.md, "Worker API"): the
worker passes ``--snapshot <manifest>``; every body is the working tree, a task
listed in ``stamps`` contributes its plan as of the stamp's ``data_commit``, any
other task its working-tree plan. Cards and plan-derived evidence come only from
that content, and the result echoes the digests of what it screened
(``source_inputs``, per-candidate ``inputs``) so the worker can verify agreement.

Stdlib only.
"""
from __future__ import annotations

import json
import re

SCHEMA = "aitask-relation-candidates/1"
SNAPSHOT_SCHEMA = "aitask-relation-snapshot/1"

# D6 source tags. ``meta:<field>`` is open over a fixed field set.
TAGS = frozenset({
    "mention_out", "mention_in", "inbox_note", "family", "trail", "cites",
    "line_anchor", "inflight_overlap", "token", "label_rare",
})
META_FIELDS = frozenset({
    "depends", "anchor", "verifies", "children_to_implement",
    "risk_mitigation_tasks", "folded_tasks", "folded_into", "followup_origin",
})
# A failed or missing core source fails the job (D5 step 3).
CORE_SOURCES = ("mention_in", "mention_out", "cites")
# D6 ordering classes, used to group truncated ids.
TRUNCATION_CLASSES = frozenset({
    "meta", "mention", "inflight", "cites", "line_anchor", "token", "trail",
    "cites_hub", "label",
})
PROVIDER_PATHS_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_REF_RE = re.compile(r"^[a-z0-9_-]+#\d+(?:_\d+)?$")


class ContractError(ValueError):
    """The provider output violates the contract; ``str(exc)`` is the reason."""


def _req(cond, msg):
    if not cond:
        raise ContractError(msg)


def valid_tag(tag) -> bool:
    if not isinstance(tag, str):
        return False
    if tag in TAGS:
        return True
    if tag.startswith("meta:"):
        return tag[5:] in META_FIELDS
    return False


def _keys(obj, where, required, optional=()):
    _req(isinstance(obj, dict), f"{where}: expected an object")
    unknown = set(obj) - set(required) - set(optional)
    _req(not unknown, f"{where}: unknown key(s) {sorted(unknown)}")
    missing = [k for k in required if k not in obj]
    _req(not missing, f"{where}: missing key(s) {missing}")


def _sha(value, where, nullable=False):
    if nullable and value is None:
        return
    _req(isinstance(value, str) and bool(_SHA_RE.match(value)), f"{where}: expected a sha256")


def _ref(value, where):
    _req(isinstance(value, str) and bool(_REF_RE.match(value)),
         f"{where}: expected a qualified ref <project>#<id>, got {value!r}")


def _digest_pair(obj, where):
    _keys(obj, where, ("body_sha256", "plan_sha256"))
    _sha(obj["body_sha256"], f"{where}.body_sha256")
    _sha(obj["plan_sha256"], f"{where}.plan_sha256", nullable=True)


def _str_list(value, where):
    _req(isinstance(value, list) and all(isinstance(x, str) for x in value),
         f"{where}: expected a list of strings")


def validate(obj) -> dict:
    """Validate a decoded provider result; return it unchanged.

    Missing coverage, malformed fields or an unavailable core source raise:
    a provider that cannot vouch for its coverage has not answered.
    """
    _keys(obj, "candidates",
          ("schema", "source", "provider", "coverage", "cap", "source_inputs",
           "candidates", "truncated"))
    _req(obj["schema"] == SCHEMA, f"schema: expected {SCHEMA}, got {obj['schema']!r}")
    _ref(obj["source"], "source")
    _keys(obj["provider"], "provider", ("path", "detail"))
    _req(isinstance(obj["provider"]["path"], str)
         and bool(PROVIDER_PATHS_RE.match(obj["provider"]["path"])),
         "provider.path: expected a short lowercase name")
    _req(isinstance(obj["provider"]["detail"], str), "provider.detail: expected a string")
    cov = obj["coverage"]
    _keys(cov, "coverage", ("answered", "missing_sources"))
    _str_list(cov["answered"], "coverage.answered")
    _str_list(cov["missing_sources"], "coverage.missing_sources")
    for tag in cov["answered"] + cov["missing_sources"]:
        _req(valid_tag(tag), f"coverage: unknown source tag {tag!r}")
    _req(not set(cov["answered"]) & set(cov["missing_sources"]),
         "coverage: a source is both answered and missing")
    _req(isinstance(obj["cap"], int) and not isinstance(obj["cap"], bool) and obj["cap"] >= 0,
         "cap: expected a non-negative integer")
    _digest_pair(obj["source_inputs"], "source_inputs")
    _req(isinstance(obj["candidates"], list), "candidates: expected a list")
    _req(len(obj["candidates"]) <= obj["cap"], "candidates: more full candidates than the cap")
    seen = {obj["source"]}
    for i, cand in enumerate(obj["candidates"]):
        where = f"candidates[{i}]"
        _keys(cand, where, ("ref", "sources", "card", "evidence", "inputs"))
        _ref(cand["ref"], f"{where}.ref")
        _req(cand["ref"] not in seen, f"{where}.ref: duplicate or self ref {cand['ref']}")
        seen.add(cand["ref"])
        _str_list(cand["sources"], f"{where}.sources")
        _req(cand["sources"], f"{where}.sources: a candidate needs at least one source")
        for tag in cand["sources"]:
            _req(valid_tag(tag), f"{where}.sources: unknown source tag {tag!r}")
        _req(isinstance(cand["card"], str), f"{where}.card: expected a string")
        _req(isinstance(cand["evidence"], list), f"{where}.evidence: expected a list")
        for j, ev in enumerate(cand["evidence"]):
            ewhere = f"{where}.evidence[{j}]"
            _keys(ev, ewhere, ("source", "detail"), ("section", "line"))
            _req(valid_tag(ev["source"]), f"{ewhere}.source: unknown source tag {ev['source']!r}")
            _req(isinstance(ev["detail"], str), f"{ewhere}.detail: expected a string")
            if "section" in ev:
                _req(isinstance(ev["section"], str), f"{ewhere}.section: expected a string")
            if "line" in ev:
                _req(isinstance(ev["line"], int) and not isinstance(ev["line"], bool)
                     and ev["line"] > 0, f"{ewhere}.line: expected a positive integer")
        _digest_pair(cand["inputs"], f"{where}.inputs")
    trunc = obj["truncated"]
    _keys(trunc, "truncated", ("count", "by_class", "inputs"))
    _req(isinstance(trunc["count"], int) and not isinstance(trunc["count"], bool)
         and trunc["count"] >= 0, "truncated.count: expected a non-negative integer")
    _req(isinstance(trunc["by_class"], dict), "truncated.by_class: expected an object")
    total = 0
    for cls, refs in trunc["by_class"].items():
        _req(cls in TRUNCATION_CLASSES, f"truncated.by_class: unknown class {cls!r}")
        _req(isinstance(refs, list) and refs, f"truncated.by_class.{cls}: expected a non-empty list")
        for ref in refs:
            _ref(ref, f"truncated.by_class.{cls}")
            _req(ref not in seen, f"truncated.by_class.{cls}: duplicate or self ref {ref}")
            seen.add(ref)
        total += len(refs)
    _req(total == trunc["count"],
         f"truncated.count: {trunc['count']} but by_class lists {total} ref(s)")
    _req(isinstance(trunc["inputs"], dict), "truncated.inputs: expected an object")
    listed = {r for refs in trunc["by_class"].values() for r in refs}
    _req(set(trunc["inputs"]) == listed,
         "truncated.inputs: needs exactly one digest echo per truncated ref")
    for ref, pair in trunc["inputs"].items():
        _digest_pair(pair, f"truncated.inputs[{ref}]")
    missing_core = core_missing(obj)
    if missing_core:
        raise ContractError(f"core_missing:{','.join(missing_core)}")
    return obj


def core_missing(obj) -> list:
    """Core sources the provider did not answer (absent from ``answered``, or missing)."""
    cov = obj.get("coverage") or {}
    answered = set(cov.get("answered") or [])
    missing = set(cov.get("missing_sources") or [])
    return [s for s in CORE_SOURCES if s not in answered or s in missing]


def all_refs(obj) -> list:
    """Every candidate ref, full ones first, then truncated ones (by class order)."""
    refs = [c["ref"] for c in obj["candidates"]]
    for cls in sorted(obj["truncated"]["by_class"]):
        refs += obj["truncated"]["by_class"][cls]
    return refs


def input_echo(obj, ref):
    """The provider's digest echo for ``ref`` (source, full or truncated candidate)."""
    if ref == obj["source"]:
        return obj["source_inputs"]
    for cand in obj["candidates"]:
        if cand["ref"] == ref:
            return cand["inputs"]
    return obj["truncated"]["inputs"].get(ref)


def parse_json_stdout(text: str) -> dict:
    """Exactly one JSON object, optionally surrounded by whitespace."""
    _req(isinstance(text, str) and text.strip(), "malformed:empty stdout")
    decoder = json.JSONDecoder()
    stripped = text.strip()
    try:
        obj, end = decoder.raw_decode(stripped)
    except json.JSONDecodeError as exc:
        raise ContractError(f"malformed:invalid JSON ({exc.msg})") from None
    _req(not stripped[end:].strip(), "malformed:trailing data after the JSON object")
    _req(isinstance(obj, dict), "malformed:not a JSON object")
    return obj


def to_json(result: dict) -> str:
    return json.dumps(result, sort_keys=True, ensure_ascii=False)


# ------------------------------------------------------------- text protocol
# One record per line, separated by "\n" alone (a JSON string can hold raw
# U+0085 / U+2028 / U+2029, so readers must not split on Unicode line breaks).
# Every free-text field (cards, evidence details AND
# sections, the provider detail) is a JSON string literal, so a newline or a
# ``|`` inside it can never split a record, and an absent optional field is the
# bare ``-`` -- never a value, because a present one always starts with ``"``
# (sections) or is a digit run (lines). ``END:`` attests completeness: a
# truncated stream has no END line and does not parse.

def _q(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _dash(value):
    return "-" if value is None else str(value)


def to_text(result: dict) -> str:
    validate(result)
    out = [
        f"PROVIDER:{result['provider']['path']}|{_q(result['provider']['detail'])}",
        f"SOURCE:{result['source']}|body={result['source_inputs']['body_sha256']}"
        f"|plan={_dash(result['source_inputs']['plan_sha256'])}",
        f"COVERAGE:answered={','.join(result['coverage']['answered']) or '-'}"
        f"|missing={','.join(result['coverage']['missing_sources']) or '-'}",
        f"CAP:{result['cap']}",
    ]
    for cand in result["candidates"]:
        out.append(f"CANDIDATE:{cand['ref']}|sources={','.join(cand['sources'])}"
                   f"|body={cand['inputs']['body_sha256']}|plan={_dash(cand['inputs']['plan_sha256'])}")
        out.append(f"  CARD:{_q(cand['card'])}")
        for ev in cand["evidence"]:
            section = _q(ev["section"]) if "section" in ev else "-"
            out.append(f"  EVIDENCE:{ev['source']}|{section}|"
                       f"{_dash(ev.get('line'))}|{_q(ev['detail'])}")
    trunc = result["truncated"]
    out.append(f"TRUNCATED:{trunc['count']}")
    for cls in sorted(trunc["by_class"]):
        out.append(f"TRUNCATED_CLASS:{cls}:{','.join(trunc['by_class'][cls])}")
    for ref in sorted(trunc["inputs"]):
        pair = trunc["inputs"][ref]
        out.append(f"TRUNCATED_INPUTS:{ref}|body={pair['body_sha256']}|plan={_dash(pair['plan_sha256'])}")
    out.append(f"END:candidates={len(result['candidates'])}|truncated={trunc['count']}")
    return "\n".join(out) + "\n"


def _pair(fields):
    vals = dict(f.split("=", 1) for f in fields)
    plan = vals["plan"]
    return {"body_sha256": vals["body"], "plan_sha256": None if plan == "-" else plan}


_DECODER = json.JSONDecoder()


def _evidence(rest: str) -> dict:
    """``<source>|<"section" or ->|<line or ->|<"detail">``, JSON-aware."""
    source, sep, rest = rest.partition("|")
    _req(sep and valid_tag(source), f"text: bad evidence source {source!r}")
    ev = {"source": source}
    if rest.startswith('"'):
        section, end = _DECODER.raw_decode(rest)
        _req(isinstance(section, str), "text: evidence section is not a string")
        ev["section"] = section
        rest = rest[end:]
    elif rest.startswith("-"):
        rest = rest[1:]
    else:
        raise ContractError("text: malformed evidence section")
    _req(rest.startswith("|"), "text: malformed evidence record")
    line_no, sep, detail = rest[1:].partition("|")
    _req(sep, "text: malformed evidence record")
    if line_no != "-":
        _req(line_no.isdigit(), f"text: bad evidence line {line_no!r}")
        ev["line"] = int(line_no)
    value = json.loads(detail)
    _req(isinstance(value, str), "text: evidence detail is not a string")
    ev["detail"] = value
    return ev


def _csv(value):
    return [] if value == "-" else value.split(",")


def parse_text(text: str) -> dict:
    """Read ``to_text`` output back into a result (schema/source/cap restored)."""
    res = {"schema": SCHEMA, "candidates": [],
           "truncated": {"count": None, "by_class": {}, "inputs": {}}}
    cur = None
    ended = False
    try:
        # Records are separated by the protocol's literal "\n" ONLY: str.splitlines()
        # would also break inside a JSON string at U+0085 / U+2028 / U+2029 (or
        # \v, \f, \x1c-\x1e), which json.dumps(ensure_ascii=False) leaves raw.
        for line in text.split("\n"):
            line = line[:-1] if line.endswith("\r") else line
            if not line:
                continue
            _req(not ended, "text: data after END")
            body = line.lstrip(" ")  # the two-space indent of CARD / EVIDENCE only
            tag, _, rest = body.partition(":")
            if tag == "PROVIDER":
                path, _, detail = rest.partition("|")
                res["provider"] = {"path": path, "detail": json.loads(detail)}
            elif tag == "SOURCE":
                ref, *fields = rest.split("|")
                res["source"] = ref
                res["source_inputs"] = _pair(fields)
            elif tag == "COVERAGE":
                parts = dict(f.split("=", 1) for f in rest.split("|"))
                res["coverage"] = {"answered": _csv(parts["answered"]),
                                   "missing_sources": _csv(parts["missing"])}
            elif tag == "CAP":
                res["cap"] = int(rest)
            elif tag == "CANDIDATE":
                ref, sources, *fields = rest.split("|")
                cur = {"ref": ref, "sources": sources.split("=", 1)[1].split(","),
                       "card": None, "evidence": [], "inputs": _pair(fields)}
                res["candidates"].append(cur)
            elif tag == "CARD":
                _req(cur is not None, "text: CARD outside a candidate")
                cur["card"] = json.loads(rest)
            elif tag == "EVIDENCE":
                _req(cur is not None, "text: EVIDENCE outside a candidate")
                cur["evidence"].append(_evidence(rest))
            elif tag == "TRUNCATED":
                res["truncated"]["count"] = int(rest)
                cur = None
            elif tag == "TRUNCATED_CLASS":
                cls, _, refs = rest.partition(":")
                res["truncated"]["by_class"][cls] = refs.split(",")
            elif tag == "TRUNCATED_INPUTS":
                ref, *fields = rest.split("|")
                res["truncated"]["inputs"][ref] = _pair(fields)
            elif tag == "END":
                counts = dict(f.split("=", 1) for f in rest.split("|"))
                _req(int(counts["candidates"]) == len(res["candidates"]),
                     "text: END candidate count mismatch")
                ended = True
            else:
                raise ContractError(f"text: unknown record {tag!r}")
    except (ValueError, KeyError, IndexError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError(f"text: malformed line ({exc})") from None
    _req(ended, "text: no END line (truncated stream)")
    return validate(res)


# ----------------------------------------------------------- snapshot manifest

def snapshot_manifest(data_repo: str, source: str, stamps: dict) -> dict:
    return {"schema": SNAPSHOT_SCHEMA, "data_repo": data_repo, "source": source,
            "stamps": dict(sorted(stamps.items()))}


def validate_snapshot(obj) -> dict:
    _keys(obj, "snapshot", ("schema", "data_repo", "source", "stamps"))
    _req(obj["schema"] == SNAPSHOT_SCHEMA, f"snapshot.schema: expected {SNAPSHOT_SCHEMA}")
    _req(isinstance(obj["data_repo"], str) and obj["data_repo"], "snapshot.data_repo: expected a path")
    _ref(obj["source"], "snapshot.source")
    _req(isinstance(obj["stamps"], dict), "snapshot.stamps: expected an object")
    for ref, commit in obj["stamps"].items():
        _ref(ref, "snapshot.stamps")
        _req(isinstance(commit, str) and re.match(r"^[0-9a-f]{40,64}$", commit or ""),
             f"snapshot.stamps[{ref}]: expected a full commit id")
    return obj


def screening_digest(result: dict) -> str:
    """sha256 over the material screening inputs (the record's ``screening_sha256``)."""
    import hashlib
    material = {
        "provider": result["provider"]["path"],
        "coverage": {"answered": sorted(result["coverage"]["answered"]),
                     "missing_sources": sorted(result["coverage"]["missing_sources"])},
        "candidates": [{"ref": c["ref"], "sources": c["sources"], "card": c["card"],
                        "evidence": c["evidence"]} for c in result["candidates"]],
        "truncated": {k: v for k, v in sorted(result["truncated"]["by_class"].items())},
    }
    data = json.dumps(material, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
