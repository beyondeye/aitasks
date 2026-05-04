---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [brainstorm]
created_at: 2026-05-04 16:24
updated_at: 2026-05-04 16:24
boardidx: 40
---

Implement `apply_synthesizer_output()` in the brainstorm engine so that when a
synthesizer agent completes, its output is automatically parsed and integrated
as a new hybrid node in the session DAG.

## Background

The brainstorm engine has a complete end-to-end apply flow only for the
initializer agent (`apply_initializer_output` in
`.aitask-scripts/brainstorm/brainstorm_session.py` line 336, TUI auto-hook at
`brainstorm_app.py` line 2104). All other agent types write output but nothing
integrates them. See sibling tasks: apply-explorer (same delimiter format),
apply-detailer, apply-patcher.

## What to implement

### 1. `apply_synthesizer_output(task_num, agent_name)` in `brainstorm_session.py`

The synthesizer output uses the same four-delimiter format as the explorer
(`NODE_YAML_START/END` + `PROPOSAL_START/END`). If apply-explorer has already
introduced a shared `_apply_node_output()` helper (see sibling task), reuse it
here. Otherwise implement `apply_synthesizer_output` using the same logic:

- Read `<agent_name>_output.md` from the crew worktree
- Extract and validate `NODE_YAML_START/END` and `PROPOSAL_START/END` blocks
- Validate via `validate_node()` and `parse_sections()` / `validate_sections()`
- Call `create_node()`, write `br_nodes/<new_node_id>.yaml` and
  `br_proposals/<new_node_id>.md`
- Record the synthesizer's parent node IDs in the new node's `parents:` field
  (the synthesizer merges multiple nodes — all source node IDs must be listed)
- Call `set_head()` and `next_node_id()` to advance graph state

### 2. TUI auto-apply hook in `brainstorm_app.py`

After a synthesizer group completes, the TUI should auto-call
`apply_synthesizer_output`. Follow the initializer pattern:

- `_try_apply_synthesizer_if_needed(agent_name, force=False)` method
- Call from the timer tick when synthesizer status reaches `Completed`
- Show failure banner; provide manual retry

### 3. Error log

On failure write `<agent_name>_apply_error.log`.

## Files to touch

- `.aitask-scripts/brainstorm/brainstorm_session.py` — add `apply_synthesizer_output()`
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add TUI auto-hook
- `.aitask-scripts/brainstorm/templates/synthesizer.md` — verify delimiter format

## Reference: existing end-to-end flow

Study these before implementing:
- `brainstorm_session.py:apply_initializer_output` (line 336)
- `brainstorm_session.py:_extract_block` (line 253)
- `brainstorm_session.py:_tolerant_yaml_load` (line 308)
- `brainstorm_app.py:_try_apply_initializer_if_needed` (line 2104)
- `brainstorm_app.py` timer tick at line 3742
- `aitask_brainstorm_apply_initializer.sh`

## See also (sibling tasks)

- t739 apply-explorer (same four-delimiter format — implement shared helper there
  and reuse here; coordinate to avoid duplication)
- t741 apply-detailer (different format: plan markdown only)
- t743 apply-patcher (three-part output with impact analysis)
