---
Task: t1505_3_trail_narrative_overview_field.md
Parent Task: aitasks/t1505_lite_trail_mode_and_trail_summary_pane.md
Sibling Tasks: aitasks/t1505/t1505_1_bytrail_summary_pane.md, aitasks/t1505/t1505_2_trail_detail_modal_entry_first.md, aitasks/t1505/t1505_4_trail_skill_lite_default.md
Archived Sibling Plans: aiplans/archived/p1505/p1505_*_*.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
---

# p1505_3 — `narrative.overview` schema field

Adds one optional schema property: the free-form, non-binding prose summary that
t1505_4 writes and t1505_1 displays.

**Blocked on t1468_5** (`depends: [t1468_5]`) — a file conflict, not a
preference. That task is currently `Implementing` and is editing both schema
copies: it bumps `schema_version` `const` from `"1.0.0"` to `"1.1.0"`, sets
`SCHEMA_NORMALIZATION_LOCK = {"1.1.0": "1.0.0"}` (leaving `NORMALIZATION_VERSION`
at `"1.0.0"`), and adds an optional `followup_kind` to `entry.snapshot`.

## Step 0 — Rebase check (FIRST, before any edit)

This plan was written against the pre-t1468_5 tree. Re-derive the current state:

1. Read both schema copies; confirm the `const` (expected `"1.1.0"`).
2. `diff aidocs/implementation_trail.schema.json .aitask-scripts/lib/implementation_trail.schema.json`
   — must be empty.
3. Read `tests/test_trail_schema.py`'s `test_wrong_schema_version` — it pins
   const-ness by asserting a *specific* other version is rejected, and t1468_5
   updates which one.

Apply the change on top of **that** state, not the state described below.

## Implementation steps

### 1. Add the property

To `properties.narrative.properties` (which is `additionalProperties: false`;
currently `problem_statement`, `recommendation_summary`, `method_note`,
`caveats`):

```json
"overview": {
  "description": "Free-form prose summary of the findings and the motivation for the proposed wave/task order. Advisory and NON-BINDING: renderers display it verbatim; no consumer derives membership, ordering or classification from it.",
  "type": "string",
  "minLength": 1
}
```

- **Not** added to `narrative.required` — every existing document must stay
  valid; that is the whole point of doing this additively.
- **Do not bump `schema_version`.** t1468_5's bump already invalidated every
  stored 1.0.0 trail; a second bump would invalidate them again for a purely
  additive property. Leave the const exactly as t1468_5 set it.

### 2. Keep the two copies byte-identical

`tests/test_trail_schema.py:63` (`test_lib_schema_byte_identical_to_aidocs_contract`)
pins byte equality — `aidocs/` does not ship to installed projects, so the runtime
copy under `.aitask-scripts/lib/` is what actually validates. Copy the file rather
than hand-editing twice, then re-run `diff`.

### 3. Validator

**Expected: no change to `trail_schema.py`.** `type` and `minLength` are already
in `SUPPORTED_KEYWORDS` (`:114`). Verify rather than assume — the interpreter
raises `RuntimeError` on any unknown keyword *by design*, so that "schema
evolution must extend the interpreter, never silently under-validate". A
`RuntimeError` here means the tripwire is working and the interpreter needs
extending.

### 4. Tests (`tests/test_trail_schema.py`)

- Document **with** `overview` validates.
- Document **without** `overview` validates — the load-bearing back-compat case.
- `overview: ""` fails; the assertion names the expected `minLength` rule and the
  `$.narrative.overview` path, not merely "invalid".
- `overview: 123` fails on `type`, likewise path-and-rule specific.

Follow the file's existing style: `aidocs/implementation_trail_examples/` is the
valid baseline corpus and every mutation operates on a deep copy.

### 5. Docs

`aidocs/implementation_trail_design.md` §6 documents the field **and its advisory
status** — renderers display it verbatim; no consumer derives membership, ordering
or classification from it. That constraint is what makes the field safe to add to
a document whose other fields are binding, so it belongs in the contract, not only
in a task file.

## Verification

- `bash tests/test_trail_schema.py`
- `bash tests/test_implementation_trail_design.py` — reads the same schema file and
  guards aidocs drift. It pins no narrative property set today, so an additive
  property needs no relaxation; confirm that still holds.
- `diff` between the two schema copies is empty.
- Real entry point: `./.aitask-scripts/aitask_trail_gather.sh drift --trail <handle>`
  returns `CURRENT`/`STALE`, never `ERROR:invalid_trail`, for a trail at the
  current schema version.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the **last**
  line.

**Expected non-failure:** a trail still stored at `1.0.0` *is* rejected after
t1468_5's bump. That rejection belongs to t1468_5 (t1468_7 owns refreshing the two
live artifacts) and must not be read as a regression from this child.

`aidocs/implementation_trail_examples/*.json` need no change for this field;
t1468_5 separately regenerates `cross_topic_multiple_trails.json` for its bump.

Post-implementation cleanup, archival and merge follow **Step 9** of the shared
task workflow.
