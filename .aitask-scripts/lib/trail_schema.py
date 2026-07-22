#!/usr/bin/env python3
"""trail_schema.py - implementation-trail schema library and validator (t1210_1).

Production loader/validator/canonicalizer for Implementation Trail JSON
documents (design: aidocs/implementation_trail_design.md; T1 in RFC par.14).
The pinned v1 contract lives in aidocs/implementation_trail.schema.json; the
byte-identical runtime copy ships next to this file as
implementation_trail.schema.json (aidocs/ does not ship to installed projects
-- same reasoning that made gates_reference.yaml canonical under
.aitask-scripts/, t1147). tests/test_trail_schema.py pins the two copies to
byte equality.

VALIDATION MODEL (two phases, rich returns, never crashes on untrusted JSON):

Parsing is fail-closed JSON: the non-JSON literals NaN/Infinity/-Infinity are
rejected at load (and "number" additionally rejects non-finite floats for
documents built in memory).

Phase 1 -- structural: a small interpreter over exactly the JSON-Schema subset
the pinned schema uses, with patterns/enums/required sets read from the schema
file itself (single-sourced; the design-contract test reads the same file).
Pinned semantics: bool is NOT an integer/number ("integer" rejects True);
"additionalProperties": false flags unknown keys, schema-valued
additionalProperties (project_revision, rendering_hints) validates the extra
values; uniqueItems compares by deep structural equality with the bool/number
distinction (true != 1). Any schema keyword outside SUPPORTED_KEYWORDS raises
RuntimeError -- schema evolution must extend the interpreter, never silently
under-validate.

Phase 2 -- semantic (what JSON Schema cannot express): strictly increasing
wave ordinals / per-wave entry positions; per-category local-id uniqueness;
evidence_refs resolution; relation-endpoint resolution; hard_depends must be
provenance=fact AND mirror the recorded DAG (edges run prerequisite ->
dependent: when `to` is a wave entry whose snapshot records `depends`, `from`
must be a member; when `to` is not an entry or has no recorded depends the
claim is unverifiable and the check is SKIPPED -- known limitation); no
"anchor" key anywhere (covers rendering_hints, where the schema alone would
allow one). Phase-2 traversal is type-guarded: nodes phase 1 already flagged
as mis-typed are skipped, not re-reported and never a crash.

validate_trail() returns every issue from both phases as
TrailIssue(path, rule, message); load_trail() raises TrailValidationError
carrying that list. No bare booleans.

INPUT-SNAPSHOT NORMALIZATION (RFC par.8.1; the digest T2's gatherer compares):

canonical_input_snapshot(inputs) / input_digest(inputs) implement the
versioned normalization (NORMALIZATION_VERSION, hashed into the bytes).
Each input record carries ref (non-empty str), kind (the schema's
generation.inputs enum), exists (bool), plus state fields that are REQUIRED
or FORBIDDEN -- never optional -- per (kind, exists):

    kind                            exists=true requires        forbids
    task_file                       status, depends,            content_hash
                                    gates_pending
    plan_file                       content_hash                status, depends,
                                                                gates_pending
    board_state/gate_ledger/other   content_hash                status, depends,
                                                                gates_pending
    (any kind) exists=false         --                          all state fields

Unknown keys (boardidx, timestamps are unrepresentable by construction),
missing required fields, forbidden fields present (even as null -- presence is
presence), duplicate (kind, ref) pairs, and mistyped values are all hard
errors naming the offending record. depends and gates_pending are semantically
SETS: a duplicate member is a hard error (fail-closed, not silent dedup --
identical membership must never hash differently, and a duplicate indicates
an upstream gatherer bug). Canonical bytes: records carry exactly
ref/kind/exists + the required fields, depends/gates_pending sorted, records
sorted by (kind, ref), wrapped with normalization_version, json.dumps with
sort_keys, compact separators, ensure_ascii, UTF-8. Digests are comparable
only within a NORMALIZATION_VERSION.

CLI: python3 trail_schema.py validate <file>
  -> "VALID:<trail_id>" exit 0, or one "INVALID:<path>|<rule>|<message>" line
     per issue, exit 1.
"""

import hashlib
import json
import math
import os
import re
import sys
from collections import namedtuple

NORMALIZATION_VERSION = "1.0.0"  # versioned alongside schema_version (RFC par.8.1)
DIGEST_HEX_LEN = 16              # sha256 truncation; matches ^[a-f0-9]{12,64}$

SCHEMA_BASENAME = "implementation_trail.schema.json"
DEFAULT_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   SCHEMA_BASENAME)

TrailIssue = namedtuple("TrailIssue", ["path", "rule", "message"])


class TrailValidationError(ValueError):
    """Raised by load_trail / canonical_input_snapshot; carries .issues."""

    def __init__(self, issues):
        self.issues = list(issues)
        super().__init__("; ".join(
            "%s [%s]: %s" % (i.path, i.rule, i.message) for i in self.issues))


# --- Phase 1: schema-driven structural interpreter -------------------------

# The complete keyword set the interpreter understands. Anything else in the
# schema is a RuntimeError tripwire, so a future schema edit cannot silently
# go unvalidated. Annotation keywords carry no constraints and are ignored.
SUPPORTED_KEYWORDS = {
    "type", "const", "enum", "pattern", "minLength", "maxLength", "minimum",
    "minItems", "uniqueItems", "required", "properties",
    "additionalProperties", "items", "$ref",
}
ANNOTATION_KEYWORDS = {"$schema", "$id", "$defs", "title", "description"}

_TYPE_CHECKS = {
    # bool subclasses int in Python; JSON Schema keeps them distinct.
    # NaN/Infinity are not JSON: the loader rejects the literals at parse
    # time, and "number" additionally rejects non-finite floats so documents
    # built in memory cannot smuggle them past validate_trail either.
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: (isinstance(v, (int, float))
                         and not isinstance(v, bool)
                         and (not isinstance(v, float) or math.isfinite(v))),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def load_schema(schema_path=None):
    """Load + sanity-check the trail schema. Dies loudly on a broken schema
    (a broken schema is an install defect, not a document issue)."""
    path = schema_path or DEFAULT_SCHEMA_PATH
    with open(path, encoding="utf-8") as fh:
        schema = json.load(fh)
    if schema.get("title") != "Implementation Trail":
        raise RuntimeError("%s: not the Implementation Trail schema" % path)
    const = schema.get("properties", {}).get("schema_version", {}).get("const")
    if not isinstance(const, str):
        raise RuntimeError("%s: missing schema_version const" % path)
    return schema


def _canonical_key(value):
    """Hashable structural identity preserving the bool/number distinction
    (true != 1) while following JSON semantics for 1 == 1.0."""
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("num", float(value))
    if isinstance(value, str):
        return ("str", value)
    if value is None:
        return ("null",)
    if isinstance(value, list):
        return ("list", tuple(_canonical_key(v) for v in value))
    if isinstance(value, dict):
        return ("dict", tuple(sorted(
            (k, _canonical_key(v)) for k, v in value.items())))
    raise RuntimeError("unhashable JSON value of type %s" % type(value).__name__)


def _type_matches(value, type_spec):
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    for name in types:
        check = _TYPE_CHECKS.get(name)
        if check is None:
            raise RuntimeError("unsupported schema type: %r" % (name,))
        if check(value):
            return True
    return False


def _type_names(type_spec):
    return "|".join(type_spec) if isinstance(type_spec, list) else type_spec


def _check_node(value, subschema, path, defs, issues):
    """Validate value against subschema; append TrailIssues. Returns True when
    the node's *container type* matched (semantic checks may traverse it)."""
    unsupported = (set(subschema) - SUPPORTED_KEYWORDS - ANNOTATION_KEYWORDS)
    if unsupported:
        raise RuntimeError(
            "unsupported schema keyword(s) %s at %s -- extend the "
            "trail_schema.py interpreter" % (sorted(unsupported), path))

    if "$ref" in subschema:
        ref = subschema["$ref"]
        prefix = "#/$defs/"
        if not ref.startswith(prefix) or ref[len(prefix):] not in defs:
            raise RuntimeError("unresolvable $ref %r at %s" % (ref, path))
        return _check_node(value, defs[ref[len(prefix):]], path, defs, issues)

    if "type" in subschema and not _type_matches(value, subschema["type"]):
        issues.append(TrailIssue(
            path, "type", "expected %s, got %s"
            % (_type_names(subschema["type"]), type(value).__name__)))
        return False  # further keyword checks would be meaningless / crash

    if "const" in subschema and value != subschema["const"]:
        issues.append(TrailIssue(
            path, "const", "expected %r, got %r" % (subschema["const"], value)))
    if "enum" in subschema and value not in subschema["enum"]:
        issues.append(TrailIssue(
            path, "enum", "%r not in %s" % (value, subschema["enum"])))

    if isinstance(value, str):
        if "pattern" in subschema and not re.search(subschema["pattern"], value):
            issues.append(TrailIssue(
                path, "pattern",
                "%r does not match %s" % (value, subschema["pattern"])))
        if "minLength" in subschema and len(value) < subschema["minLength"]:
            issues.append(TrailIssue(
                path, "minLength",
                "length %d < %d" % (len(value), subschema["minLength"])))
        if "maxLength" in subschema and len(value) > subschema["maxLength"]:
            issues.append(TrailIssue(
                path, "maxLength",
                "length %d > %d" % (len(value), subschema["maxLength"])))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in subschema and value < subschema["minimum"]:
            issues.append(TrailIssue(
                path, "minimum", "%r < %r" % (value, subschema["minimum"])))

    if isinstance(value, dict):
        for key in subschema.get("required", ()):
            if key not in value:
                issues.append(TrailIssue(
                    path, "required", "missing required key %r" % key))
        props = subschema.get("properties", {})
        additional = subschema.get("additionalProperties", True)
        for key, item in value.items():
            child_path = "%s.%s" % (path, key)
            if key in props:
                _check_node(item, props[key], child_path, defs, issues)
            elif additional is False:
                issues.append(TrailIssue(
                    path, "additionalProperties", "unknown key %r" % key))
            elif isinstance(additional, dict):
                _check_node(item, additional, child_path, defs, issues)
            # additional is True/absent: extra keys permitted unvalidated.

    if isinstance(value, list):
        if "minItems" in subschema and len(value) < subschema["minItems"]:
            issues.append(TrailIssue(
                path, "minItems",
                "%d item(s) < %d" % (len(value), subschema["minItems"])))
        if subschema.get("uniqueItems"):
            seen = {}
            for idx, item in enumerate(value):
                key = _canonical_key(item)
                if key in seen:
                    issues.append(TrailIssue(
                        "%s[%d]" % (path, idx), "uniqueItems",
                        "duplicate of item %d" % seen[key]))
                else:
                    seen[key] = idx
        if "items" in subschema:
            for idx, item in enumerate(value):
                _check_node(item, subschema["items"],
                            "%s[%d]" % (path, idx), defs, issues)

    return True


# --- Phase 2: semantic checks (type-guarded; skip what phase 1 flagged) ----

def _dicts(seq):
    """Well-formed (dict) members of a possibly mis-typed list value."""
    if not isinstance(seq, list):
        return []
    return [item for item in seq if isinstance(item, dict)]


def _check_strictly_increasing(items, field, path, rule, issues):
    values = [it[field] for it in items
              if isinstance(it.get(field), int)
              and not isinstance(it.get(field), bool)]
    for prev, cur in zip(values, values[1:]):
        if cur <= prev:
            issues.append(TrailIssue(
                path, rule,
                "%s values must be strictly increasing (%r then %r)"
                % (field, prev, cur)))
            return


def _check_no_anchor(node, path, issues):
    if isinstance(node, dict):
        if "anchor" in node:
            issues.append(TrailIssue(
                path, "no_anchor",
                "trail documents must not carry 'anchor' keys -- canonical "
                "topic membership lives in task frontmatter only"))
        for key, value in node.items():
            _check_no_anchor(value, "%s.%s" % (path, key), issues)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            _check_no_anchor(value, "%s[%d]" % (path, idx), issues)


def _semantic_checks(doc, issues):
    waves = _dicts(doc.get("waves"))
    entries = []  # (wave, entry)
    for wave in waves:
        for entry in _dicts(wave.get("entries")):
            entries.append((wave, entry))

    # Strictly increasing ordinals / per-wave positions.
    _check_strictly_increasing(waves, "ordinal", "$.waves",
                               "wave_ordinal", issues)
    for wave in waves:
        wave_id = wave.get("wave_id", "?")
        _check_strictly_increasing(
            _dicts(wave.get("entries")), "position",
            "$.waves[%s]" % wave_id, "entry_position", issues)

    # Per-category local-id uniqueness.
    id_sets = (
        ("wave_id", "$.waves",
         [w.get("wave_id") for w in waves]),
        ("entry_id", "$.waves[*].entries",
         [e.get("entry_id") for _, e in entries]),
        ("evidence_id", "$.evidence",
         [ev.get("evidence_id") for ev in _dicts(doc.get("evidence"))]),
        ("observation_id", "$.observations",
         [o.get("observation_id") for o in _dicts(doc.get("observations"))]),
    )
    for label, path, ids in id_sets:
        seen = set()
        for value in ids:
            if not isinstance(value, str):
                continue  # phase 1 already reported the type/required issue
            if value in seen:
                issues.append(TrailIssue(
                    path, "duplicate_local_id",
                    "duplicate %s %r" % (label, value)))
            seen.add(value)

    # evidence_refs resolution.
    evidence_ids = {ev.get("evidence_id")
                    for ev in _dicts(doc.get("evidence"))
                    if isinstance(ev.get("evidence_id"), str)}
    referrers = (
        [("$.waves[*].entries[%s]" % e.get("entry_id", "?"),
          e.get("evidence_refs")) for _, e in entries]
        + [("$.observations[%s]" % o.get("observation_id", "?"),
            o.get("evidence_refs"))
           for o in _dicts(doc.get("observations"))])
    for path, refs in referrers:
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if isinstance(ref, str) and ref not in evidence_ids:
                issues.append(TrailIssue(
                    path, "evidence_ref",
                    "references unknown evidence %r" % ref))

    # Relation endpoints must be referenced elsewhere in the document.
    known = {e.get("task") for _, e in entries}
    known |= {x.get("task") for x in _dicts(doc.get("exclusions"))}
    for obs in _dicts(doc.get("observations")):
        affects = obs.get("affects")
        if isinstance(affects, list):
            known |= {a for a in affects if isinstance(a, str)}
    entry_depends = {}  # task ref -> recorded snapshot depends (when a list)
    for _, entry in entries:
        snapshot = entry.get("snapshot")
        if not isinstance(snapshot, dict):
            continue
        depends = snapshot.get("depends")
        if isinstance(depends, list):
            known |= {d for d in depends if isinstance(d, str)}
            if isinstance(entry.get("task"), str):
                entry_depends[entry["task"]] = depends
    known.discard(None)

    for idx, rel in enumerate(_dicts(doc.get("relations"))):
        path = "$.relations[%d]" % idx
        for end in (rel.get("from"), rel.get("to")):
            if isinstance(end, str) and end not in known:
                issues.append(TrailIssue(
                    path, "relation_endpoint",
                    "endpoint %r not referenced anywhere else "
                    "in the document" % end))
        if rel.get("type") == "hard_depends":
            if rel.get("provenance") != "fact":
                issues.append(TrailIssue(
                    path, "hard_depends_fact",
                    "hard_depends must mirror recorded DAG facts "
                    "(provenance %r)" % rel.get("provenance")))
            # Mirror check (prerequisite -> dependent edges): when `to` is an
            # entry with a recorded depends snapshot, `from` must be in it.
            # `to` not an entry / no recorded depends -> unverifiable, skipped.
            src, dst = rel.get("from"), rel.get("to")
            if (isinstance(src, str) and isinstance(dst, str)
                    and dst in entry_depends
                    and src not in entry_depends[dst]):
                issues.append(TrailIssue(
                    path, "hard_depends_mirror",
                    "hard_depends %s -> %s but %s is not in %s's recorded "
                    "snapshot.depends" % (src, dst, src, dst)))

    _check_no_anchor(doc, "$", issues)


# --- Public validation API -------------------------------------------------

def validate_trail(doc, schema=None):
    """Both validation phases over an in-memory document. Returns every issue
    as a list of TrailIssue (empty = valid); raises only RuntimeError, and
    only for a defective schema/interpreter (never for a bad document)."""
    if schema is None:
        schema = load_schema()
    issues = []
    root_ok = _check_node(doc, schema, "$", schema.get("$defs", {}), issues)
    if root_ok and isinstance(doc, dict):
        _semantic_checks(doc, issues)
    return issues


def _reject_json_constant(literal):
    raise ValueError(
        "non-finite JSON constant %r is not valid JSON" % (literal,))


def load_trail(source, schema_path=None):
    """Load + validate a trail document, fail-closed.

    source: str/os.PathLike = path to a JSON file; bytes = raw JSON payload.
    Returns the parsed document; raises TrailValidationError (with .issues)
    on parse failure or any validation issue.
    """
    if isinstance(source, bytes):
        raw, origin = source, "<bytes>"
    elif isinstance(source, (str, os.PathLike)):
        origin = os.fspath(source)
        try:
            with open(source, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            raise TrailValidationError(
                [TrailIssue("$", "io", "cannot read %s: %s" % (origin, exc))])
    else:
        raise TypeError("source must be a path or bytes, got %s"
                        % type(source).__name__)
    try:
        # Fail-closed JSON: Python's default loader accepts the non-JSON
        # literals NaN/Infinity/-Infinity, and NaN would then pass the
        # schema's "number" union in rendering_hints -- reject them at parse.
        doc = json.loads(raw, parse_constant=_reject_json_constant)
    except ValueError as exc:
        raise TrailValidationError(
            [TrailIssue("$", "json", "invalid JSON (%s): %s" % (origin, exc))])
    issues = validate_trail(doc, load_schema(schema_path))
    if issues:
        raise TrailValidationError(issues)
    return doc


# --- Input-snapshot normalization + digest (RFC par.8.1) -------------------

_TASK_STATE_FIELDS = ("status", "depends", "gates_pending")
_ALL_STATE_FIELDS = _TASK_STATE_FIELDS + ("content_hash",)
_RECORD_BASE_FIELDS = ("ref", "kind", "exists")


def _input_kinds(schema):
    kinds = (schema["properties"]["generation"]["properties"]["inputs"]
             ["items"]["properties"]["kind"]["enum"])
    if not kinds:
        raise RuntimeError("schema declares no input kinds")
    return kinds


def _str_list(value):
    return (isinstance(value, list)
            and all(isinstance(v, str) for v in value))


def _normalize_input_record(record, index, kinds, issues):
    """Validate one input record against the per-(kind, exists) contract;
    return its canonical dict (None when any issue was appended)."""
    path = "inputs[%d]" % index

    def bad(rule, message):
        issues.append(TrailIssue(path, rule, message))

    if not isinstance(record, dict):
        bad("type", "input record must be an object, got %s"
            % type(record).__name__)
        return None

    unknown = set(record) - set(_RECORD_BASE_FIELDS) - set(_ALL_STATE_FIELDS)
    if unknown:
        bad("unknown_key",
            "unknown key(s) %s (boardidx / timestamps are deliberately "
            "unrepresentable)" % sorted(unknown))
        return None

    ref, kind, exists = (record.get("ref"), record.get("kind"),
                         record.get("exists"))
    if not isinstance(ref, str) or not ref:
        bad("ref", "ref must be a non-empty string, got %r" % (ref,))
        return None
    if kind not in kinds:
        bad("kind", "kind %r not in %s" % (kind, kinds))
        return None
    if not isinstance(exists, bool):
        bad("exists", "exists must be a boolean, got %r" % (exists,))
        return None

    if not exists:
        required, forbidden = (), _ALL_STATE_FIELDS
    elif kind == "task_file":
        required, forbidden = _TASK_STATE_FIELDS, ("content_hash",)
    else:  # plan_file, board_state, gate_ledger, other
        required, forbidden = ("content_hash",), _TASK_STATE_FIELDS

    # Presence is presence: a forbidden field present as null is still an
    # error -- absent-vs-null is not a degree of freedom two gatherers could
    # exercise differently.
    present_forbidden = [f for f in forbidden if f in record]
    if present_forbidden:
        bad("forbidden_field",
            "%r (kind=%s, exists=%s) forbids field(s) %s"
            % (ref, kind, exists, present_forbidden))
        return None
    missing = [f for f in required if f not in record]
    if missing:
        bad("missing_field",
            "%r (kind=%s, exists=%s) requires field(s) %s"
            % (ref, kind, exists, missing))
        return None

    canonical = {"ref": ref, "kind": kind, "exists": exists}
    if "status" in required:
        if not isinstance(record["status"], str):
            bad("status", "%r: status must be a string" % ref)
            return None
        canonical["status"] = record["status"]
    for field in ("depends", "gates_pending"):
        if field in required:
            if not _str_list(record[field]):
                bad(field, "%r: %s must be a list of strings" % (ref, field))
                return None
            # Both fields are semantically SETS (RFC par.8.1: sorted depends,
            # pending gate SET). A duplicate member is a hard error, not a
            # silent dedup: ["g"] and ["g","g"] describe the same membership
            # and must not hash differently, and a duplicate indicates an
            # upstream gatherer bug that deduping would mask.
            members = record[field]
            if len(set(members)) != len(members):
                dupes = sorted({m for m in members if members.count(m) > 1})
                bad("duplicate_member",
                    "%r: %s has duplicate member(s) %s -- the field is a "
                    "set" % (ref, field, dupes))
                return None
            canonical[field] = sorted(members)
    if "content_hash" in required:
        if not isinstance(record["content_hash"], str) \
                or not record["content_hash"]:
            bad("content_hash",
                "%r: content_hash must be a non-empty string" % ref)
            return None
        canonical["content_hash"] = record["content_hash"]
    return canonical


def canonical_input_snapshot(inputs, schema=None):
    """Canonical bytes over the gatherer's input records (module docstring
    pins the per-kind contract). Raises TrailValidationError on any
    contract deviation, naming each offending record and reason."""
    if schema is None:
        schema = load_schema()
    kinds = _input_kinds(schema)
    if not isinstance(inputs, list):
        raise TrailValidationError([TrailIssue(
            "inputs", "type",
            "inputs must be a list, got %s" % type(inputs).__name__)])
    issues, canonical, seen = [], [], {}
    for index, record in enumerate(inputs):
        normalized = _normalize_input_record(record, index, kinds, issues)
        if normalized is None:
            continue
        key = (normalized["kind"], normalized["ref"])
        if key in seen:
            issues.append(TrailIssue(
                "inputs[%d]" % index, "duplicate_input",
                "duplicate (kind, ref) %r -- first at inputs[%d]"
                % (key, seen[key])))
            continue
        seen[key] = index
        canonical.append(normalized)
    if issues:
        raise TrailValidationError(issues)
    canonical.sort(key=lambda rec: (rec["kind"], rec["ref"]))
    payload = {"normalization_version": NORMALIZATION_VERSION,
               "inputs": canonical}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def input_digest(inputs, schema=None):
    """Truncated sha256 hex over canonical_input_snapshot (RFC par.8.1)."""
    snapshot = canonical_input_snapshot(inputs, schema)
    return hashlib.sha256(snapshot).hexdigest()[:DIGEST_HEX_LEN]


# --- CLI -------------------------------------------------------------------

def main(argv):
    if len(argv) != 2 or argv[0] != "validate":
        sys.stderr.write("usage: trail_schema.py validate <file>\n")
        return 2
    try:
        doc = load_trail(argv[1])
    except TrailValidationError as exc:
        for issue in exc.issues:
            print("INVALID:%s|%s|%s" % (issue.path, issue.rule, issue.message))
        return 1
    print("VALID:%s" % doc["trail_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
