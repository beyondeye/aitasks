---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t1468_5]
issue_type: feature
status: Implementing
labels: [artifacts, trails, skills, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/opus5
created_at: 2026-08-13 12:27
updated_at: 2026-08-16 10:25
---

## Context

Parent: **t1505**. Read the parent plan
`aiplans/p1505_lite_trail_mode_and_trail_summary_pane.md`.

This child adds one optional schema field: **`narrative.overview`**, the
free-form, non-binding prose summary that t1505_4's lite flow writes and t1505_1's
pane displays.

## Dependency: t1468_5 must land first (hard)

**`depends: [1468_5]`** — not a sequencing preference, a file conflict.
`t1468_5` (`followup_kind remaining read surfaces`) is currently `Implementing`
and is editing the exact two files this child edits:

- it **bumps `schema_version` `const` from `"1.0.0"` to `"1.1.0"`** and sets
  `SCHEMA_NORMALIZATION_LOCK = {"1.1.0": "1.0.0"}` (with `NORMALIZATION_VERSION`
  deliberately left at `"1.0.0"`);
- it adds an optional `followup_kind` to `entry.snapshot`;
- it edits **both** schema copies.

**Do not fight that decision.** The trail is single-version by design:
`trail_schema.py:143-145` reads exactly one `schema_version` `const` and dies if
it is missing; `trail_gather.py:107-109` states the intent outright — *old-schema
trails fail validation (`ERROR:invalid_trail`), never a false `STALE`*. t1468_5
considered dual-accept and rejected it.

## Rebase check — the FIRST step, before any edit

The description below was written against the pre-t1468_5 tree. Re-derive the
current state before touching anything:

1. Read both schema copies and confirm the `const` (expected `"1.1.0"`).
2. `diff aidocs/implementation_trail.schema.json .aitask-scripts/lib/implementation_trail.schema.json`
   — must be empty.
3. Read `tests/test_trail_schema.py`'s `test_wrong_schema_version` (it pins
   const-ness by asserting a *specific* other version is rejected; t1468_5
   updates which one).

Then apply the change on top of **that** state, not the state described here.

## Key files to modify

- `aidocs/implementation_trail.schema.json` — the canonical contract.
- `.aitask-scripts/lib/implementation_trail.schema.json` — the shipped runtime
  copy (`aidocs/` does not ship to installed projects).
- `tests/test_trail_schema.py` — new cases.
- `aidocs/implementation_trail_design.md` §6 (schema walkthrough).

## Implementation plan

### 1. Add the property

To `properties.narrative.properties` (which is `additionalProperties: false`,
currently `problem_statement`, `recommendation_summary`, `method_note`,
`caveats`):

```json
"overview": {
  "description": "Free-form prose summary of the findings and the motivation for the proposed wave/task order. Advisory and NON-BINDING: renderers display it verbatim; no consumer derives membership, ordering or classification from it.",
  "type": "string",
  "minLength": 1
}
```

- **NOT** added to `narrative.required` — every existing document must stay
  valid, which is the whole point of doing this additively.
- **Do NOT bump `schema_version`.** t1468_5's bump to `1.1.0` already invalidated
  every stored 1.0.0 trail; a second bump would invalidate them again for a purely
  additive property. Leave the const exactly as t1468_5 set it.

### 2. Keep the two copies byte-identical

`tests/test_trail_schema.py:63`
(`test_lib_schema_byte_identical_to_aidocs_contract`) pins them to byte equality.
Copy the file rather than hand-editing twice, and re-run `diff` after.

### 3. Validator

**Expected: no change to `trail_schema.py`.** `type` and `minLength` are already
in `SUPPORTED_KEYWORDS` (`:114`). Verify this rather than assume it — the
interpreter raises `RuntimeError` on any keyword it does not know, deliberately,
so that "schema evolution must extend the interpreter, never silently
under-validate". If a `RuntimeError` appears, that tripwire is doing its job and
the interpreter needs extending.

### 4. Tests (`tests/test_trail_schema.py`)

- A document **with** `overview` validates.
- A document **without** `overview` validates — the load-bearing back-compat
  case, since nothing existing carries the field.
- `overview: ""` fails, and the assertion names the expected `minLength` rule and
  the `$.narrative.overview` path — not merely "invalid".
- `overview: 123` fails on `type`, likewise path-and-rule specific.

Follow the file's existing style: the `aidocs/implementation_trail_examples/`
corpus is the valid baseline and every mutation operates on a deep copy.

### 5. Docs

`aidocs/implementation_trail_design.md` §6 documents the field **and its advisory
status** — that renderers display it verbatim and no consumer may derive
membership, ordering or classification from it. That constraint is the reason the
field is safe to add to a document whose other fields are binding, so it belongs
in the contract, not only in a task file.

## Verification steps

- `bash tests/test_trail_schema.py`
- `bash tests/test_implementation_trail_design.py` — it reads the same schema file
  and guards aidocs drift. It pins no narrative property set today, so an additive
  property needs no relaxation there; confirm that still holds.
- `diff` between the two schema copies is empty.
- Real entry point: `./.aitask-scripts/aitask_trail_gather.sh drift --trail <handle>`
  returns a `CURRENT`/`STALE` verdict, never `ERROR:invalid_trail`, for a trail at
  the current schema version.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the LAST line.

**Expected non-failure:** a trail still stored at `1.0.0` *is* rejected after
t1468_5's bump. That rejection belongs to t1468_5 (t1468_7 owns refreshing the two
live artifacts) and must not be read as a regression from this child.

`aidocs/implementation_trail_examples/*.json` need no change for this field;
t1468_5 separately regenerates `cross_topic_multiple_trails.json` for its bump.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-16T07:25:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-16T07:59:15Z status=pass attempt=1 type=human
