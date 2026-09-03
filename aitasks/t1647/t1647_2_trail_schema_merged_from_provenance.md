---
priority: medium
effort: low
depends: [t1647_1]
issue_type: feature
status: Implementing
labels: [trails, artifacts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1647
created_at: 2026-09-01 18:49
updated_at: 2026-09-03 12:47
---

## Context

Second child of t1647 (trail-to-trail merge). A merged trail must record where
it came from. Add an OPTIONAL root property `merged_from` to the
implementation-trail schema — optional-additive, **no `schema_version` bump**:
the root is `additionalProperties: false` with `schema_version` const
`"1.1.0"` and the loader rejects any other version, so a required field or
version bump would turn every stored trail into ERROR:invalid_trail. The
optional-additive `overview` precedent (t1505_3) applies.

## Schema change (BOTH copies, byte-identical)

Files: `aidocs/implementation_trail.schema.json` AND
`.aitask-scripts/lib/implementation_trail.schema.json` (they are identical
today — keep them identical).

Add to root `properties`:

```json
"merged_from": {
  "description": "Provenance of a trail-to-trail merge: the source trails whose content was re-authored into this document. Written by /aitask-merge-trails; absent on any trail that never absorbed another. The recorded version of the folded (retired) source is what makes an interrupted retirement deterministically resumable.",
  "type": "array", "minItems": 1,
  "items": {
    "type": "object", "additionalProperties": false,
    "required": ["handle", "version", "merged_at"],
    "properties": {
      "handle":    {"type": "string", "minLength": 1},
      "version":   {"type": "string", "minLength": 1},
      "title":     {"type": "string"},
      "merged_at": {"$ref": "#/$defs/timestamp"}
    }
  }
}
```

Convention (schema description + later RFC child t1647_6): the merged doc's
`generation.inputs` ALSO carries one `{"kind": "other", "ref":
"<handle>@<version>"}` entry per source trail (the `inputs` enum already has
`other` — no enum change).

## Depth note (pinned from parent — no validator change here)

Deep-wins depth reconciliation is PREFLIGHT policy (t1647_3), not a schema
rule. The existing `--expect-depth` machinery in `lib/trail_schema.py`
(`_check_depth_contract`, `_check_lite_shape`) already enforces
marker-matches-authoring and lite shape; do not touch it.

## Tests

- `tests/test_trail_schema.py`: merged_from accepted (valid doc + the new
  key validates); wrong shapes rejected (missing required key, extra key
  under items, empty array); document WITHOUT merged_from still valid
  (backward compat — the load-bearing case); if no test currently asserts
  the two schema copies are byte-identical, add one.
- `tests/test_implementation_trail_design.py`: add fixture
  `aidocs/implementation_trail_examples/merged_trail.json` (a small deep
  trail carrying `merged_from` + the two `kind: other` inputs), extend
  `FIXTURE_NAMES` (the `test_no_unexpected_fixture_files` pin REQUIRES this),
  and add a merged_from structural check mirroring the file's existing
  style (stdlib-only). Note `test_no_root_keys_outside_schema` will
  validate the fixture's keys against the updated schema automatically.
- Re-validate every existing fixture + the live trail shapes against the new
  schema (the suite does this; just run it).

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` green (at minimum
  test_trail_schema.py + test_implementation_trail_design.py).
- `diff aidocs/implementation_trail.schema.json .aitask-scripts/lib/implementation_trail.schema.json`
  → empty.
- `./.aitask-scripts/aitask_trail_depth.sh validate aidocs/implementation_trail_examples/merged_trail.json --expect-depth deep`
  → VALID.

Parent plan: `aiplans/p1647_merge_trails_skill_shared_helpers_board_command_docs.md`.
