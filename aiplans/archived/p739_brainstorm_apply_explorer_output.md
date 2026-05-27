---
Task: t739_brainstorm_apply_explorer_output.md
Base branch: main
plan_verified: []
---

# t739 — Implement `apply_explorer_output()` for the brainstorm engine

## Context

The brainstorm engine has a complete end-to-end apply flow only for the **initializer** and **patcher** agents. Explorer agents (`register_explorer` in
`.aitask-scripts/brainstorm/brainstorm_crew.py:468`) currently write
`<agent_name>_output.md` containing `NODE_YAML` / `PROPOSAL` / optional
`NEW_DIMENSIONS` blocks (see `templates/explorer.md:170-184`), but **nothing
parses or integrates them**. The user has to manually create the node.

This task closes that gap by:

1. Adding an engine-side apply function that parses an explorer's output and
   creates a new node parented on the baseline.
2. Wiring the brainstorm TUI to auto-call the apply hook when an explorer
   agent reaches `Completed` (mirroring the patcher polling pattern).
3. Providing a CLI fallback `ait brainstorm apply-explorer <task> <agent>` for
   manual recovery.
4. Extracting a shared `_apply_node_output()` helper that synthesizer
   (sibling task **t740**) can reuse — both share the
   `NODE_YAML + PROPOSAL` output format.
5. Parsing the optional `NEW_DIMENSIONS` block and merging entries into
   `br_graph_state.yaml`'s `active_dimensions` list.

## Reference: existing pattern

- Initializer apply (overwrites fixed `n000_init`): `brainstorm_session.py:426`
- Patcher apply (creates a new node, three-block output):
  `brainstorm_session.py:586`
- TUI initializer hook: `brainstorm_app.py:3170` (`_try_apply_initializer_if_needed`)
- TUI patcher polling: `brainstorm_app.py:3237` (`_ensure_patcher_poll_timer`),
  `:3252` (`_scan_existing_patchers`), `:3291` (`_poll_patchers`),
  `:3324` (`_try_apply_patcher_if_needed`), `:3382` (`action_retry_patcher_apply`)
- Patcher CLI fallback: `.aitask-scripts/aitask_brainstorm_apply_patcher.sh`
- Patcher tests: `tests/test_brainstorm_apply_patcher.py`

## Implementation plan

### 1. `brainstorm_session.py` — engine logic

Add (after `apply_initializer_output` ends, before the patcher block):

```python
_EXPLORER_DELIMITERS = (
    "NODE_YAML_START",
    "NODE_YAML_END",
    "PROPOSAL_START",
    "PROPOSAL_END",
)

def _explorer_needs_apply(task_num, agent_name) -> bool:
    """True iff <agent_name>_output.md has all 4 delimiters AND its node_id
    does NOT already exist in br_nodes/. Mirrors _patcher_needs_apply."""
    # parallel to _patcher_needs_apply; parses NODE_YAML block (not METADATA)
    # for node_id.
```

Add the shared helper (reusable by `apply_synthesizer_output` in t740):

```python
def _apply_node_output(
    task_num: int | str,
    agent_name: str,
    *,
    group_name_default: str,  # e.g. "explore_001"
    expected_role: str,        # "explorer" or "synthesizer" — for error log naming
) -> tuple[str, list[str]]:
    """Parse <agent_name>_output.md with NODE_YAML + PROPOSAL delimiters,
    validate, call create_node(), set_head(), next_node_id(), and parse
    optional NEW_DIMENSIONS. Returns (new_node_id, new_dimensions_added).

    Writes <agent_name>_apply_error.log on failure.
    """
```

Behavior:

- Read `<agent_name>_output.md` from `crew_worktree(task_num)`. Raise
  `FileNotFoundError` if missing.
- `_extract_block` NODE_YAML_START/END and PROPOSAL_START/END.
- `_tolerant_yaml_load` NODE_YAML. On YAMLError, write
  `<agent_name>_apply_error.log` with the original error + first 2000 chars of
  the YAML block, then re-raise.
- Validate dict shape; auto-fill `created_at` (now) and `created_by_group`
  (derive from `agent_name` via existing `_agent_to_group_name` →
  `explorer_001a` becomes `explore_001`).
- Override `proposal_file = f"{PROPOSALS_DIR}/{new_node_id}.md"` (same
  invariant fix used by the patcher).
- `validate_node(node_data)` — raise `ValueError` if errors.
- `parse_sections` / `validate_sections` on PROPOSAL — raise `ValueError` if
  errors.
- Refuse to overwrite an existing node:
  `if (wt / NODES_DIR / f"{new_node_id}.yaml").exists(): raise ValueError`.
- Build `dimensions` dict by filtering `node_data` against
  `_PATCHER_NON_DIMENSION_FIELDS` (same set — both share the same structural
  field list; rename the constant to `_NODE_NON_DIMENSION_FIELDS` so it reads
  generic).
- `create_node(...)` with parsed parents, description, dimensions, proposal
  text, group_name, reference_files.
- `set_head(wt, new_node_id)`.
- `next_node_id(wt)` to advance the counter.
- Parse optional NEW_DIMENSIONS block (tag is `--- NEW_DIMENSIONS ---`
  WITHOUT a matching `_END` — see `templates/explorer.md:179-184`). The
  template emits a single delimiter followed by free text up to EOF. Use a
  simple split on `--- NEW_DIMENSIONS ---`; take the tail, strip, split on
  commas, drop entries equal to `"none"` (case-insensitive), drop empties.
  Read `br_graph_state.yaml`, append unique new dim keys to
  `active_dimensions`, write back.
- `update_operation(task_num, derived_group, agents_append=agent_name,
  nodes_created=new_node_id, status="Completed")`.
- Return `(new_node_id, new_dimensions_added)`.

Catch-all error-log wrapper at the bottom of `_apply_node_output` mirrors the
patcher's pattern: write `<agent_name>_apply_error.log` on any exception not
already logged (so the TUI banner hint can point at the log file).

Add the explorer entry point:

```python
def apply_explorer_output(task_num, agent_name) -> str:
    """Parse <agent_name>_output.md and integrate it as a new node.
    Returns the new node_id.
    """
    new_id, _new_dims = _apply_node_output(
        task_num, agent_name,
        group_name_default="explore",
        expected_role="explorer",
    )
    return new_id
```

(The `group_name_default` / `expected_role` parameters are stubs for t740 to
plug into; for explorer they only affect the catch-all error-log filename and
are passed through. Keep the signature stable so t740 can add
`apply_synthesizer_output` as a one-liner wrapper.)

**Rename / share constant:** rename `_PATCHER_NON_DIMENSION_FIELDS` →
`_NODE_NON_DIMENSION_FIELDS` (set is already generic — patcher and
explorer/synthesizer all emit the same structural fields). Keep the old name
as an alias `_PATCHER_NON_DIMENSION_FIELDS = _NODE_NON_DIMENSION_FIELDS` for
zero-risk migration (one external reference in tests; remove the alias once
verified unused).

### 2. `brainstorm_app.py` — TUI auto-apply hook

Mirror the patcher pattern (lines 3237-3406):

- Add class-level state initialized in `__init__` / `on_mount`:
  - `self._explorer_groups: dict[str, list[str]] = {}`   # group_name → agent_names
  - `self._explorer_poll_timer = None`
  - `self._applying_explorer: set[str] = set()`
  - `self._explorer_apply_errors: dict[str, str] = {}`
- Add `_register_explorer_group(group_name, agent_names)` called from
  `_run_design_op` after `register_explorer` returns. Replace the existing
  `if op == "explore":` block (lines 4871-4883) so each registered agent is
  added to the tracking dict and the poll timer is ensured. Use
  `self.call_from_thread(...)` since `_run_design_op` runs in a worker thread.
- Add `_ensure_explorer_poll_timer()` / `_stop_explorer_poll_timer()`
  (5 s interval, same as patcher).
- Add `_scan_existing_explorers()` — on session load
  (`_load_existing_session`), walk `explorer_*_status.yaml` files in the
  worktree; for each Completed agent whose output passes
  `_explorer_needs_apply`, track it. Call after `_scan_existing_patchers()`
  at line 3168.
- Add `_poll_explorers()` — for each tracked agent, if its
  `_status.yaml` shows `Completed` and `_explorer_needs_apply` returns True,
  call `_try_apply_explorer_if_needed(agent_name)`. Drop already-applied
  entries. Stop the timer when empty.
- Add `_try_apply_explorer_if_needed(agent_name, force=False)`:
  - Guard against re-entry via `self._applying_explorer`.
  - Import `apply_explorer_output` from `brainstorm.brainstorm_session`.
  - On exception: store in `_explorer_apply_errors`, surface via
    `_set_apply_banner` (reuse the initializer banner widget, OR add a new
    one). Hint text: `run `ait brainstorm apply-explorer <task> <agent>` to
    retry`.
  - On success: `_clear_apply_banner`, drop from tracking, notify
    `Explorer {agent} applied → {new_id}.`, then `_load_existing_session()`
    to refresh the DAG.
- Add manual retry binding `ctrl+shift+x` →
  `action_retry_explorer_apply()` (picks the most-recently-status'd tracked
  explorer, like the patcher's `action_retry_patcher_apply`). Register the
  binding in the `BINDINGS` list near the `ctrl+shift+r` patcher entry.

**Banner reuse decision:** reuse the existing `#initializer_apply_banner`
Static widget — `_set_apply_banner` / `_clear_apply_banner` are already
generic. The initializer-vs-explorer message is in the banner text itself.
(The patcher uses a separate `#patcher_impact_banner` because it also has to
display IMPACT_FLAG details — explorer has no such concept.)

### 3. CLI fallback wrapper

New file: `.aitask-scripts/aitask_brainstorm_apply_explorer.sh`. Copy
`aitask_brainstorm_apply_patcher.sh` and adapt:

- Usage line: `ait brainstorm apply-explorer <task_num> <agent_name>`.
- Args: `NUM`, `AGENT` (no source_node_id — explorer parents come from the
  agent's NODE_YAML).
- Python heredoc calls
  `apply_explorer_output(num, agent)` and prints `APPLIED:<new_id>` on
  success, `APPLY_FAILED:<error>` on failure (exit 1).

Wire into the dispatcher in `ait` between lines 269-270:

```bash
apply-explorer)    exec "$SCRIPTS_DIR/aitask_brainstorm_apply_explorer.sh" "$@" ;;
```

Update the help block (line 282-284) to list it, and the error message on
line 290 (`Available: ...`).

### 4. Tests

New file: `tests/test_brainstorm_apply_explorer.py`. Adapt
`tests/test_brainstorm_apply_patcher.py` with these cases:

1. `test_creates_node_and_advances_head` — happy path, NODE_YAML with
   dimensions, no NEW_DIMENSIONS. Assert: node yaml written with correct
   `proposal_file`, proposal markdown written, head set to new id,
   `next_node_id` incremented, dimensions preserved.
2. `test_new_dimensions_merged_into_graph_state` — NEW_DIMENSIONS block lists
   `component_cache, assumption_pool`. Assert active_dimensions list contains
   both, and pre-existing entries are not duplicated.
3. `test_new_dimensions_none_is_noop` — NEW_DIMENSIONS block contains `none`.
   Assert active_dimensions unchanged.
4. `test_new_dimensions_absent_is_noop` — output has only NODE_YAML +
   PROPOSAL, no NEW_DIMENSIONS tag. Assert no error, active_dimensions
   unchanged.
5. `test_reference_files_preserved` — node yaml includes
   `reference_files: [...]`; assert preserved on the new node.
6. `test_missing_created_at_is_auto_filled`.
7. `test_missing_created_by_group_derived_from_agent_name` — `explorer_001a`
   → `explore_001`.
8. `test_missing_output_raises_filenotfound`.
9. `test_missing_delimiter_raises_valueerror` — drop NODE_YAML_END.
10. `test_existing_node_refuses_overwrite` — pre-seed `n001_explored.yaml`,
    agent output specifies `node_id: n001_explored`. Assert `ValueError`.
11. `test_invalid_yaml_writes_error_log` — malformed NODE_YAML triggers
    `<agent>_apply_error.log` write.
12. `test_invalid_node_data_writes_error_log` — node fails `validate_node`
    (e.g. missing `description`); assert `<agent>_apply_error.log` exists.
13. `_explorer_needs_apply` cases mirroring `_patcher_needs_apply` tests
    (missing output, partial delimiters, full output + non-existing node,
    full output + existing node).

Use the same `_seed_session` / `_apply` helpers pattern. Patch
`brainstorm.brainstorm_session.crew_worktree` to return the tempdir.

### 5. Template verification

Read `.aitask-scripts/brainstorm/templates/explorer.md` and confirm the
delimiters exactly match the parser:

- `--- NODE_YAML_START ---` / `--- NODE_YAML_END ---` ✓
- `--- PROPOSAL_START ---` / `--- PROPOSAL_END ---` ✓
- `--- NEW_DIMENSIONS ---` (single, no `_END`) ✓ — parser handles this
  asymmetry explicitly.

No template changes expected. If the parser tests reveal a mismatch, fix the
template (not the parser) so all agents converge on the same format.

## Files to touch

- `.aitask-scripts/brainstorm/brainstorm_session.py` — add
  `_EXPLORER_DELIMITERS`, `_explorer_needs_apply`, `_apply_node_output`,
  `apply_explorer_output`. Rename `_PATCHER_NON_DIMENSION_FIELDS` →
  `_NODE_NON_DIMENSION_FIELDS` (keep alias).
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add explorer
  tracking/polling/apply methods, register binding `ctrl+shift+x`, call
  `_scan_existing_explorers()` from `_load_existing_session()`, register each
  explorer in `_run_design_op` after `register_explorer` returns.
- `.aitask-scripts/aitask_brainstorm_apply_explorer.sh` — NEW (copy/adapt
  patcher wrapper).
- `ait` — add `apply-explorer` dispatch case + help text + error message.
- `tests/test_brainstorm_apply_explorer.py` — NEW.

## Verification

```bash
# Unit tests
python -m unittest tests.test_brainstorm_apply_explorer -v

# Lint the new shell wrapper
shellcheck .aitask-scripts/aitask_brainstorm_apply_explorer.sh

# CLI smoke test
ait brainstorm apply-explorer --help   # should exit 2 with usage line

# Manual end-to-end (requires existing brainstorm session):
#   1. ait brainstorm <task>            # open TUI
#   2. Trigger an explore operation with 2 parallel explorers.
#   3. Wait for both agents to reach Completed.
#   4. Confirm: TUI auto-applies both, DAG refreshes with new nodes,
#      no error banner.
#   5. Inspect br_graph_state.yaml: head moved, next_node_id incremented,
#      active_dimensions extended (if explorer emitted NEW_DIMENSIONS).
#   6. Force a failure (corrupt one _output.md), press ctrl+shift+x, confirm
#      banner appears with the apply-explorer CLI hint, then run the hint
#      command and confirm it surfaces the same error.
```

End-to-end TUI verification is manual — flag as a candidate for an
`issue_type: manual_verification` follow-up sibling at Step 8c.

## Sibling-task handoff (t740 apply-synthesizer)

The shared `_apply_node_output()` helper means t740 reduces to:

```python
def apply_synthesizer_output(task_num, agent_name) -> str:
    new_id, _ = _apply_node_output(
        task_num, agent_name,
        group_name_default="hybridize",
        expected_role="synthesizer",
    )
    return new_id
```

Plus the synthesizer TUI hook (same pattern as explorer's). Make sure the
helper does not hard-code any explorer-specific text (e.g. error log
messages, group prefix derivation) — derive everything from
`agent_name`/`expected_role` so t740 inherits a working helper.

## Step 9 — Post-Implementation

Standard merge / archive flow per `task-workflow/SKILL.md` Step 9. Run
`ait skill verify` is NOT required (no skill/template touched). Run
`shellcheck .aitask-scripts/aitask_brainstorm_apply_explorer.sh` before
committing. Build verification is the unit-test suite for the affected
module:

```bash
python -m unittest tests.test_brainstorm_apply_explorer tests.test_brainstorm_apply_patcher tests.test_brainstorm_session -v
```

## Final Implementation Notes

- **Actual work done:** Implemented `apply_explorer_output()` and the shared
  `_apply_node_output()` helper in `brainstorm_session.py`. Added a TUI
  auto-apply loop (track / scan / poll / try / retry-binding) in
  `brainstorm_app.py`, wired into `_run_design_op` and
  `_load_existing_session`. Created CLI fallback
  `aitask_brainstorm_apply_explorer.sh` and added the `apply-explorer`
  subcommand to the `ait` dispatcher. Tests: 16 new cases in
  `tests/test_brainstorm_apply_explorer.py` covering happy path,
  NEW_DIMENSIONS handling (merge, none, absent), error cases (missing
  output, missing delimiter, existing node, invalid YAML, invalid node
  data), and `_explorer_needs_apply` matrix.
- **Deviations from plan:** None to the public-API surface. One in-scope
  refinement: `_agent_to_group_name` was updated to strip the trailing
  parallel-explorer suffix (`explorer_001a` → `explore_001` instead of
  `explore_001a`), so that `update_operation` actually finds the right
  group for parallel explorers. The patcher path (no parallel suffix) is
  unaffected.
- **Issues encountered:** Initial test for
  `test_missing_created_by_group_derived_from_agent_name` exposed the
  parallel-suffix bug above. Fixed in `_agent_to_group_name`; patcher
  tests stayed green.
- **Key decisions:**
  - Made the helper signature minimal — `expected_role` only — so t740's
    `apply_synthesizer_output` is a one-line wrapper. The
    `group_name_default` parameter from the original draft turned out to
    be unused and was dropped.
  - Reused the existing `#initializer_apply_banner` widget for explorer
    failure messages (per plan); explorer has no IMPACT_FLAG so the
    patcher's dedicated impact banner is not needed.
  - Tracked explorer agents as a flat `set` instead of `dict[group →
    list]`, since each agent's NODE_YAML carries its own parents and the
    poll loop only needs the agent name.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** t740 (`apply-synthesizer`) can call
  `_apply_node_output(task_num, agent_name, expected_role="synthesizer")`
  directly. The synthesizer TUI hook follows the explorer pattern
  verbatim (track set, scan, poll, try, retry binding). For agent-name →
  group-name resolution, note that `_agent_to_group_name` maps
  `synthesizer_001` → `hybridize_001` (no parallel suffix expected for
  synthesizers, so the new strip-suffix branch is a no-op for that role).
- **Manual-verification failure:** item "Corrupt one explorer's `_output.md` (e.g. truncate the NODE_YAML block), press `ctrl+shift+x`, verify the apply banner shows the `apply-explorer` CLI hint." failed; follow-up task t837.
