---
priority: low
effort: medium
depends: [740]
issue_type: refactor
status: Ready
labels: [brainstorm, refactor]
created_at: 2026-05-19 23:33
updated_at: 2026-05-19 23:33
---

Reconcile the patcher apply path into the shared `_apply_node_output()`
helper introduced by t739 (`apply-explorer`).

## Background

`brainstorm_session.py:_apply_node_output()` is the shared engine core
for explorer (t739) and synthesizer (t740) apply flows. Both use the
two-block `NODE_YAML + PROPOSAL` output format and produce a single new
node parented as the agent specifies. The **patcher** apply path
(`apply_patcher_output`, `brainstorm_session.py:636`) predates the
shared helper. It uses a different three-block output format
(`PATCHED_PLAN_START/END`, `IMPACT_START/END`, `METADATA_START/END` —
see `_PATCHER_DELIMITERS` at `:497-501`) and the corresponding
`_patcher_needs_apply`. The two flows currently duplicate: node-id
validation, `create_node` invocation, head/next-id advancement,
`update_operation` call, error-log writing, and the
`_NODE_NON_DIMENSION_FIELDS` dimension extraction.

## What to do

1. **Extract a parser-strategy abstraction.** Either
   - extend `_apply_node_output` with a callable that parses the
     output text into a `(node_data_dict, proposal_text, extras_dict)`
     tuple — explorer/synthesizer pass the two-block parser,
     patcher passes a three-block parser that also extracts the
     `IMPACT` block; or
   - introduce a thin layer above `_apply_node_output` that both flows
     compose.
2. **Migrate `apply_patcher_output`** to use the unified path. Preserve
   the patcher-specific behavior:
   - Source node lookup (`source_node_id` argument).
   - `IMPACT` payload returned alongside `new_node_id` (the TUI uses it
     to populate the impact banner).
   - `_patcher_apply_error.log` filename / message format.
3. **Confirm all patcher tests still pass** unchanged
   (`tests/test_brainstorm_apply_patcher.py`,
   `tests/test_brainstorm_apply_patcher_cli.sh`,
   `tests/test_brainstorm_apply_created_by_group.sh`).
4. **Confirm TUI patcher polling/apply/retry still works**
   (`brainstorm_app.py:_try_apply_patcher_if_needed`, retry binding
   `ctrl+shift+r`).

## Files likely to touch

- `.aitask-scripts/brainstorm/brainstorm_session.py` (rework
  `_apply_node_output` / `apply_patcher_output`).
- Possibly `brainstorm_app.py` if the patcher apply return signature
  changes (impact payload).
- No new tests required if the abstraction is invisible to callers;
  add targeted parser-strategy tests if the abstraction is exposed
  publicly.

## Constraints

- **No public-API breakage.** `apply_patcher_output`,
  `apply_explorer_output`, `apply_synthesizer_output` keep the same
  signatures and return types.
- **Out of scope:** t741 (detailer — different output entirely;
  separate helper). Don't try to fold detailer into the same
  abstraction.
