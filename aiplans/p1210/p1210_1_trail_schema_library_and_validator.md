---
Task: t1210_1_trail_schema_library_and_validator.md
Parent Task: aitasks/t1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md
Sibling Tasks: aitasks/t1210/t1210_2_*.md … t1210_7_*.md (all pending)
Archived Sibling Plans: (none yet — this is the first child implemented)
Worktree: (none — profile 'fast', current branch)
Branch: main (current branch)
Base branch: main
---

# Plan: t1210_1 — Trail schema library and validator

## Context

First implementation slice (T1 in RFC §14) of the Implementation Trails design
(`aidocs/implementation_trail_design.md`). t1210 produced a pinned v1 contract —
`aidocs/implementation_trail.schema.json` (Draft 2020-12 subset, root
`additionalProperties: false`, `schema_version` const `1.0.0`), three fixtures
under `aidocs/implementation_trail_examples/`, and a stdlib design-contract test
(`tests/test_implementation_trail_design.py`). This task turns that design-time
contract into the production schema library that T2 (gatherer/drift), T3
(skill), and T4 (board view) consume: load/validate/canonicalize trail JSON, and
own the versioned §8.1 input-snapshot normalization that `input_digest` hashes.

## Key design decisions

1. **Schema ships with the lib; aidocs stays the pinned design contract.**
   Runtime scripts must not read `aidocs/` (framework-repo-only; installed
   projects get `.aitask-scripts/` but not `aidocs/` — same reasoning that made
   `gates_reference.yaml` canonical under `.aitask-scripts/`, t1147). The lib
   reads a byte-identical copy at
   `.aitask-scripts/lib/implementation_trail.schema.json`; a drift-guard test
   pins it to the aidocs original. Any future schema edit must touch both files
   or the suite goes red.

2. **Validation is schema-driven, with pinned interpreter semantics.**
   `trail_schema.py` implements an interpreter for exactly the JSON-Schema
   subset the pinned schema uses. Patterns, enums, and required sets are read
   from the schema file at load time (same single-sourcing as the design test).
   The semantics of each supported keyword are pinned here, not left implicit:

   - **Types** (JSON-Schema-correct, bool is NOT an int/number):
     `string`→`str` · `integer`→`int` and not `bool` · `number`→`int|float` and
     not `bool` · `boolean`→`bool` only · `object`→`dict` · `array`→`list` ·
     `null`→`None`. A union (`"type": ["string","number","boolean"]`, used by
     `rendering_hints`) passes if any member matches.
   - **`additionalProperties`**: `false` → any key outside `properties` is an
     issue; **schema-valued** (used by `project_revision: {"type":"string"}`
     and `rendering_hints`) → each extra key's *value* is validated against
     that subschema; absent → extra keys permitted (JSON Schema default).
   - **`uniqueItems`** (used by `scope.topics`): duplicate detection by deep
     structural equality with the bool/number distinction above (`true` ≠ `1`).
   - Other supported keywords with standard semantics: `const`, `enum`,
     `pattern` (`re.search` on `str` values only), `minLength`/`maxLength`,
     `minimum`, `minItems`, `required`, `properties`, `items`, `$ref`→`$defs`.
   - **Tripwire:** any keyword outside this set raises `RuntimeError` (schema
     evolution must extend the interpreter, never silently under-validate).

3. **Robust two-phase validation; rich returns; never crashes on malformed
   input.** Phase 1 is the structural interpreter pass; phase 2 runs the
   semantic checks that JSON Schema cannot express:

   - wave `ordinal` strictly increasing; entry `position` strictly increasing
     per wave;
   - local-id uniqueness per category (`wave_id`, `entry_id`, `evidence_id`,
     `observation_id`);
   - every `evidence_refs` entry resolves to a declared `evidence_id`;
   - relation endpoints resolve to tasks referenced elsewhere (entry tasks ∪
     exclusion tasks ∪ observation `affects` ∪ snapshot `depends`);
   - `hard_depends` must have `provenance: fact` **and mirror the recorded
     DAG**: fixture edges run prerequisite→dependent (`from` lands before
     `to`), so when `to` resolves to a wave entry whose `snapshot` records a
     `depends` list, require `from ∈ to.snapshot.depends`. When `to` is not an
     entry or its snapshot has no `depends`, the claim is unverifiable and the
     check is skipped — this limitation is documented in the module docstring;
   - no `anchor` key anywhere (walk; covers `rendering_hints`, where the
     schema alone would allow it).

   Phase-2 checks are type-guarded at every traversal step: a node whose
   container type is wrong (`waves: {}`, `relations: [null]`, scalar
   `snapshot`) was already reported by phase 1 and is *skipped* — not
   re-reported, and never a `TypeError`/`KeyError` crash — while independent
   errors in well-formed branches are still collected. `validate_trail`
   returns all issues from both phases in one pass (`TrailIssue(path, rule,
   message)`); `load_trail` raises `TrailValidationError` carrying that list.
   No bare booleans.

4. **§8.1 normalization: versioned, per-kind closed contract.**
   `NORMALIZATION_VERSION = "1.0.0"` is hashed into the canonical bytes. Every
   input record has `ref` (non-empty str), `kind` (the schema's
   `generation.inputs` enum, read from the schema), `exists` (bool), plus
   state fields that are **required or forbidden — never optional — per
   (kind, exists)**:

   | kind | exists=true requires | exists=true forbids | exists=false |
   |---|---|---|---|
   | `task_file` | `status` (str), `depends` (list[str]), `gates_pending` (list[str]) | `content_hash` | all state fields forbidden |
   | `plan_file` | `content_hash` (non-empty str) | `status`, `depends`, `gates_pending` | all state fields forbidden |
   | `board_state`, `gate_ledger`, `other` | `content_hash` (non-empty str) | `status`, `depends`, `gates_pending` | all state fields forbidden |

   This kills the T1/T2 ambiguity: two gatherers observing the same live state
   cannot serialize it differently, because any deviation — unknown key
   (`boardidx`, timestamps are unrepresentable by construction), missing
   required field, forbidden field present (**even with value `null`**:
   presence is presence, absent-vs-null is not a degree of freedom), duplicate
   `(kind, ref)` pair, mistyped value — is a hard error naming the offending
   record and reason. A deleted input is representable (`exists: false`,
   state-free), which is what makes `input_missing` drift observable at
   refresh time.

   **Canonical form:** each record serialized with exactly `ref`, `kind`,
   `exists` + its required-per-(kind, exists) fields (no null padding — the
   shape is fully determined), `depends`/`gates_pending` sorted, records
   sorted by `(kind, ref)`, wrapped as
   `{"normalization_version": …, "inputs": […]}`, serialized
   `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True)`,
   UTF-8 encoded. `input_digest` = `sha256(...).hexdigest()[:16]` (matches the
   schema's `^[a-f0-9]{12,64}$`).

## Files

- **New:** `.aitask-scripts/lib/trail_schema.py` (stdlib-only; style per
  `.aitask-scripts/lib/artifact_manifest.py`)
- **New:** `.aitask-scripts/lib/implementation_trail.schema.json` (byte copy
  of the aidocs schema)
- **New:** `tests/test_trail_schema.py`
- **Unchanged:** `tests/test_implementation_trail_design.py` (kept as the
  aidocs-drift guard), `aidocs/implementation_trail.schema.json`, fixtures.

## Implementation steps

### 1. Schema copy

`cp aidocs/implementation_trail.schema.json .aitask-scripts/lib/` — exact bytes.

### 2. `.aitask-scripts/lib/trail_schema.py`

Public API (pinned):

```python
NORMALIZATION_VERSION = "1.0.0"   # versioned alongside schema_version (§8.1)
DIGEST_HEX_LEN = 16

TrailIssue = namedtuple("TrailIssue", ["path", "rule", "message"])

class TrailValidationError(ValueError):   # .issues: list[TrailIssue]

def load_schema(schema_path=None) -> dict
    # default: implementation_trail.schema.json next to __file__;
    # sanity-checks title + schema_version const; dies loudly on parse error.

def validate_trail(doc, schema=None) -> list[TrailIssue]
def load_trail(source, schema_path=None) -> dict
    # source: str/PathLike = file path; bytes = raw JSON payload.
    # Parse error → TrailValidationError(rule="json"); any issues → raise.

def canonical_input_snapshot(inputs) -> bytes   # per-kind contract, decision 4
def input_digest(inputs) -> str
```

The module docstring documents the input-record contract table and the
`hard_depends` verifiability limitation (decision 3).

**CLI (`__main__`)**: `python3 trail_schema.py validate <file>` →
`VALID:<trail_id>` exit 0, or one `INVALID:<path>|<rule>|<message>` line per
issue, exit 1. Small explicit scope addition over the task's step list: it
gives the "validator" in the task title a shell surface T2/T3 can call without
importing, following the artifact_manifest.py CLI-lib style.

### 3. `tests/test_trail_schema.py` — single test matrix

`unittest`, stdlib only. Mutations operate on deep copies (in-memory or
written under `tempfile.TemporaryDirectory()`) — never on the aidocs fixtures.

**A. Guards and happy path**
- lib schema copy byte-equal to `aidocs/implementation_trail.schema.json`;
- all three fixtures pass `load_trail` from a path AND from bytes;
  `validate_trail` returns `[]`.

**B. Interpreter semantics (decision 2)**
- `rendering_hints` with a `bool` value → valid; with an object/array value →
  invalid (schema-valued additionalProperties, union type);
- `project_revision` with a non-string value → invalid (nested dynamic
  properties);
- wave `ordinal: true` → invalid (boolean is not an integer);
- duplicate `scope.topics` entries → invalid (uniqueItems, deep equality);
- unknown keyword injected into a *test-local* schema → `RuntimeError`
  (tripwire proven to fire).

**C. Structural negative controls** (one mutation per rule; each asserts
`TrailValidationError` with the expected `rule` and, where meaningful, `path`)
- unknown root key · missing required root key · wrong `schema_version` · bad
  `trail_id` · bad task_ref (entry task) · bad timestamp · bad local_id · bad
  enum (`classification`) · empty `rationale` (minLength) · unknown nested key
  (entry level) · invalid JSON bytes · non-dict root.

**D. Semantic negative controls**
- duplicate / non-increasing wave ordinal · duplicate / non-increasing entry
  position · duplicate `entry_id` · unresolved `evidence_refs` · unresolved
  relation endpoint · `hard_depends` with `provenance: advisory` ·
  `hard_depends` whose `to` is an entry with recorded `depends` NOT containing
  `from` (mirror check) · `hard_depends` whose `to` lacks a snapshot `depends`
  → accepted (documented skip) · `anchor` key under `rendering_hints`.

**E. Robustness on malformed shapes (decision 3)**
- `waves: {}` → structural issue, no crash; `relations: [null]` → issue, no
  crash; scalar `snapshot` → issue, no crash;
- one malformed branch + one independent semantic error in another branch →
  BOTH reported in a single raise (rich-return + no-masking).

**F. Digest contract (decision 4)**
- determinism: permuted input order, permuted `depends` order, permuted dict
  key insertion → identical digest;
- known-answer test pinning the exact canonical bytes for a small mixed-kind
  input set (pins `NORMALIZATION_VERSION` + record shape);
- sensitivity: status flip, `gates_pending` change, `exists` flip,
  added/removed input → digest changes;
- per-kind fail-closed: unknown key (`boardidx`) · `task_file` with
  `content_hash` · `plan_file` with `status` · `plan_file` missing
  `content_hash` · `board_state` with `depends` · `exists: false` with any
  state field · forbidden field present as `null` · duplicate `(kind, ref)` ·
  mistyped `exists` — each a hard error naming the record;
- output matches the schema's `input_digest` pattern.

**G. CLI**
- subprocess the real entry point: valid fixture → exit 0 + `VALID:`; mutated
  tmp copy → exit 1 + `INVALID:` line (outermost surface; proves the suite
  fails on a genuinely bad input).

## Verification

- `python3 -m unittest tests.test_trail_schema -v` — green.
- `python3 -m unittest tests.test_implementation_trail_design -v` — still
  green (design test untouched).
- Commit as `feature: Add trail schema library and validator (t1210_1)`; then
  Step 9 (post-implementation): `./ait gates run 1210_1` (`risk_evaluated` is
  the active gate, recorded by the orchestrator), archival via
  `aitask_archive.sh 1210_1`.

## Out of scope (owned by siblings)

Scope/owner resolution, live-state gathering, and the `trail-drift` verb (T2);
skill flows (T3); board view (T4/T5); docs (T6). This lib defines *what the
canonical snapshot looks like and how it hashes*; T2 decides *what live state
feeds it*.

## Risk

### Code-health risk: low
- Duplicated schema file (lib copy vs aidocs pinned contract) could drift if the guard test were ever deleted along with a schema edit · severity: low · → mitigation: TBD
- Mini schema interpreter could mis-implement a keyword's semantics — bounded by the pinned semantics table (decision 2), the matrix-B tests, and the unknown-keyword `RuntimeError` tripwire · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The per-kind input-record contract is this task's reading of RFC §8.1; if T2's gatherer needs state the table can't carry, T2 must amend the lib — bounded, additive, and forced through a visible `NORMALIZATION_VERSION` bump by the known-answer digest test · severity: low · → mitigation: TBD
