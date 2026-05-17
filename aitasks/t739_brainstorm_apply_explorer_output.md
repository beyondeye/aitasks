---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [brainstorm]
created_at: 2026-05-04 16:24
updated_at: 2026-05-04 16:24
boardidx: 120
---

Implement `apply_explorer_output()` in the brainstorm engine so that when an
explorer agent completes, its output is automatically parsed and integrated as
a new node in the session DAG.

## Background

The brainstorm engine has a complete end-to-end apply flow only for the
initializer agent (`apply_initializer_output` in
`.aitask-scripts/brainstorm/brainstorm_session.py` line 336, TUI auto-hook at
`brainstorm_app.py` line 2104 and timer tick at line 3742). All other agent
types (explorer, synthesizer, detailer, patcher) write output files but
nothing parses or integrates them. This task adds the missing apply layer for
the explorer.

## What to implement

### 1. `apply_explorer_output(task_num, agent_name)` in `brainstorm_session.py`

Mirror the structure of `apply_initializer_output`:

- Read `<agent_name>_output.md` from the crew worktree
- Extract `NODE_YAML_START/END` and `PROPOSAL_START/END` delimiter blocks
  (same format the explorer template already specifies)
- Validate the node YAML via `validate_node()` and the proposal via
  `parse_sections()` / `validate_sections()`
- Call `create_node()` from `brainstorm_dag.py` with the parsed data
- Write `br_nodes/<new_node_id>.yaml` and `br_proposals/<new_node_id>.md`
- Call `set_head()` to advance the graph head to the new node
- Call `next_node_id()` to increment the counter in `br_graph_state.yaml`
- Return the new node_id

Consider extracting a shared `_apply_node_output(task_num, agent_name, ...)`
helper reusable by synthesizer (see sibling task for apply-synthesizer), since
both use the same four-delimiter output format.

### 2. TUI auto-apply hook in `brainstorm_app.py`

After an explorer group completes, the TUI should auto-call
`apply_explorer_output`. Follow the initializer pattern:

- `_try_apply_explorer_if_needed(agent_name, force=False)` method
- Call from the runner status poll / timer tick when explorer status reaches
  `Completed`
- Show a banner on apply failure (same style as initializer banner at line
  2136)
- Provide a manual retry binding (ctrl+? or menu action)

### 3. Error log

On YAML parse failure write
`<agent_name>_apply_error.log` (parallel to `initializer_bootstrap_apply_error.log`).

## Files to touch

- `.aitask-scripts/brainstorm/brainstorm_session.py` — add `apply_explorer_output()`
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add TUI auto-hook
- `.aitask-scripts/brainstorm/templates/explorer.md` — verify delimiter format
  matches what the apply function expects

## Reference: existing end-to-end flow

Study these before implementing:
- `brainstorm_session.py:apply_initializer_output` (line 336) — full apply
- `brainstorm_session.py:n000_needs_apply` (line 275) — gate check pattern
- `brainstorm_session.py:_extract_block` (line 253) — delimiter parser
- `brainstorm_session.py:_tolerant_yaml_load` (line 308) — YAML fallback
- `brainstorm_app.py:_try_apply_initializer_if_needed` (line 2104) — TUI hook
- `brainstorm_app.py` timer tick at line 3742 — auto-apply trigger
- `aitask_brainstorm_apply_initializer.sh` — manual fallback CLI wrapper

## See also (sibling tasks — same gap, different agent types)

- t740 apply-synthesizer (same NODE_YAML+PROPOSAL format as explorer — coordinate
  to avoid duplicate code via shared helper)
- t741 apply-detailer (different format: plan markdown only, updates node's
  `plan_file` field)
- t743 apply-patcher (three-part output: plan + impact analysis + metadata)
