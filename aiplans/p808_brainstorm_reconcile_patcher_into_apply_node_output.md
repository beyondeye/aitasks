---
Task: t808_brainstorm_reconcile_patcher_into_apply_node_output.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Reconcile patcher apply path into shared `_apply_node_output()`

## Goal

The patcher apply path (`apply_patcher_output`) predated the shared
`_apply_node_output()` helper used by explorer (t739) and synthesizer
(t740). All three flows duplicated: node-id validation, `create_node`
invocation, head advancement, `update_operation`, error-log writing, and
the `_NODE_NON_DIMENSION_FIELDS` dimension extraction. This task unifies
the patcher onto the shared core via a parser-strategy abstraction.

## Approach

Extend `_apply_node_output` with three injection points so the
flow-specific differences are parameterised rather than duplicated:

1. **`parser` callable** — `(text, err_log, expected_role) -> (node_data,
   proposal_text, extras)`. Each flow parses its own output format and is
   responsible for writing its flow-specific YAML error log.
   - `_parse_two_block_output` — explorer/synthesizer (NODE_YAML +
     PROPOSAL), also validates proposal sections.
   - `_parse_patcher_output` — patcher (PATCHED_PLAN + IMPACT + METADATA),
     reads the parent's proposal verbatim via `source_node_id`, classifies
     the IMPACT block.
2. **`finalize` hook** — runs between `create_node` and `set_head`. The
   patcher uses it (`_write_patcher_plan_file`) to persist the
   PATCHED_PLAN block as a plan file and record `plan_file` on the node.
   Explorer/synthesizer pass `None`.
3. **`extra_error_context`** — extra key/value lines for the catch-all
   error log (patcher passes `source_node_id`).
4. **`metadata_block_label`** — `"NODE_YAML"` vs `"METADATA"` for the
   `validate_node` failure message.

`_apply_node_output` now returns `(new_node_id, node_data, extras)` so the
wrappers can run their flow-specific tail (`update_operation`,
NEW_DIMENSIONS merge).

The shared core now owns: file-existence check, `created_at` default,
`created_by_group` canonicalisation, `proposal_file` override,
`validate_node`, node-collision check, `_NODE_NON_DIMENSION_FIELDS`
dimension extraction, `create_node`, `set_head`, and the catch-all error
log.

## Steps

1. Add `from typing import Callable` import. ✓
2. Add `_parse_patcher_output` (three-block parser) and
   `_write_patcher_plan_file` (finalize hook). ✓
3. Rewrite `apply_patcher_output` to call `_apply_node_output` with the
   patcher parser closure + finalize hook; keep `update_operation` (no
   `agents_append`) in the wrapper tail. Public signature and
   `(new_node_id, impact_type, impact_details)` return preserved. ✓
4. Add `_parse_two_block_output` (extracted from the old inline parsing)
   and `_merge_new_dimensions` (extracted NEW_DIMENSIONS merge). ✓
5. Rewrite `_apply_node_output` as the injectable shared core. ✓
6. Update `apply_explorer_output` / `apply_synthesizer_output` to use the
   new return shape and run `_merge_new_dimensions` + `update_operation`
   (with `agents_append`) in the wrapper tail. ✓

## Constraints honoured

- No public-API breakage: `apply_patcher_output`, `apply_explorer_output`,
  `apply_synthesizer_output` keep their signatures and return types.
- Patcher-specific behaviour preserved: `source_node_id` lookup, IMPACT
  payload in the return tuple, `<agent>_apply_error.log` filename and
  message format (including the `source_node_id:` line), `update_node`
  plan_file recording.
- Out of scope: t741 (detailer) — untouched.

## Verification

- `tests/test_brainstorm_apply_patcher.py` — 18/18 pass.
- `tests/test_brainstorm_apply_patcher_cli.sh` — 6/7 (see Final Notes).
- `tests/test_brainstorm_apply_created_by_group.sh` — 2/2 pass.
- `tests/test_brainstorm_apply_explorer.py` — 16/16 pass.
- `tests/test_brainstorm_apply_synthesizer.py` — 14/14 pass.
- TUI patcher polling/apply/retry verified by inspection:
  `brainstorm_app.py:_try_apply_patcher_if_needed` unpacks
  `new_id, impact, details` — return shape unchanged; `_patcher_needs_apply`
  and the `ctrl+shift+r` retry binding untouched.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. `_apply_node_output`
  is now a parser-strategy core shared by all three single-node apply flows
  (explorer, synthesizer, patcher).
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Chose the "extend `_apply_node_output` with a parser
  callable" option from the task (option 1) over a thin composition layer —
  it keeps a single try/except + error-log site and a single `validate_node`
  /`create_node`/`set_head` sequence. The `finalize` hook (rather than
  folding the plan-file write into the parser) keeps the patcher's
  create_node → plan_file → set_head ordering identical to the original.
- **Upstream defects identified:** tests/test_brainstorm_apply_patcher_cli.sh:101-108
  — the "graph state advanced" assertion expects `next_node_id: 2` after a
  patcher apply, but `apply_patcher_output` (by design, per the
  "next_node_id is consumed at registration time" comment) never increments
  `next_node_id`. This test FAILS identically on the pre-change baseline
  (verified via `git stash`), so it is a pre-existing defect in the test (or
  the CLI script) — not a regression from this task. It is out of scope here.
- **Build verification:** `python -m py_compile` passes; module imports
  cleanly.
