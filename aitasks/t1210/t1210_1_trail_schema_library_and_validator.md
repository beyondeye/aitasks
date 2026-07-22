---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [python, task-planning]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/fable5
created_at: 2026-07-22 16:15
updated_at: 2026-07-22 16:55
---

## Context

First implementation slice of the Implementation Trails design (parent t1210).
The approved design is `aidocs/implementation_trail_design.md` (RFC); this child
is **T1** in RFC §14. It turns the design-time contract into the production
schema library every later slice (gatherer, skill, board view) consumes.

## Key files to create/modify

- `.aitask-scripts/lib/trail_schema.py` (new) — load / validate / canonicalize
  trail JSON documents.
- `tests/test_trail_schema.py` (new) — unit tests; adopt the fixtures in
  `aidocs/implementation_trail_examples/` as test data.
- `tests/test_implementation_trail_design.py` (existing, keep) — the design-time
  contract test stays as the aidocs-drift guard; the new library test is the
  production check. Extend rather than delete.

## Reference files for patterns

- `aidocs/implementation_trail.schema.json` — the PINNED v1 contract
  (`schema_version` const `1.0.0`, root `additionalProperties: false`).
- `aidocs/implementation_trail_design.md` §6 (schema walkthrough), §8.1 (the
  canonical normalization the digest hashes — this library owns and versions
  that normalization).
- `.aitask-scripts/lib/artifact_manifest.py` — style reference for a
  validated, stdlib-only, atomic-write lib under `.aitask-scripts/lib/`.

## Implementation plan

1. `trail_schema.py`: `load_trail(path_or_bytes) -> dict` (fail-closed:
   unknown root keys, missing required keys, bad task-ref/timestamp/local-id
   patterns, non-increasing wave ordinals / entry positions, unresolved
   evidence/relation refs are all hard errors with which-item/reason detail —
   rich returns, not bare booleans).
2. `canonical_input_snapshot(inputs) -> bytes` + `input_digest(inputs) -> str`
   implementing RFC §8.1 (per-task: existence, status, sorted depends, pending
   gate set, plan-file content hash; boardidx and timestamps excluded).
   Version the normalization alongside `schema_version`.
3. Mirror the structural checks of `tests/test_implementation_trail_design.py`
   as library validation so the two cannot drift (single-source the patterns
   by reading the schema file, as the design test already does).
4. Unit tests: valid fixtures pass; one mutation per validation rule fails
   with the expected reason (negative controls per rule).

## Verification

- `python3 -m unittest tests.test_trail_schema -v` green.
- `python3 -m unittest tests.test_implementation_trail_design -v` still green.
- Negative control: each guarded rule demonstrably fails (exit 1) on a
  mutated fixture copy (mutate copies under the test tmpdir, never the
  aidocs fixtures).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-22T13:55:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-22T15:50:21Z status=pass attempt=1 type=human
