---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [brainstorm]
created_at: 2026-05-04 16:24
updated_at: 2026-05-04 16:24
boardidx: 100
---

Implement `apply_detailer_output()` in the brainstorm engine so that when a
detailer agent completes, its plan output is automatically written to
`br_plans/` and the target node's YAML is updated with the `plan_file` field.

## Background

The brainstorm engine has a complete end-to-end apply flow only for the
initializer agent (`apply_initializer_output` in
`.aitask-scripts/brainstorm/brainstorm_session.py` line 336, TUI auto-hook at
`brainstorm_app.py` line 2104). The detailer writes a plan file but nothing
parses or stores it. See sibling tasks: apply-explorer, apply-synthesizer
(both create new nodes), apply-patcher (three-part output).

## What to implement

### 1. `apply_detailer_output(task_num, agent_name, target_node_id)` in `brainstorm_session.py`

The detailer output format is different from explorer/synthesizer — it
produces a plan markdown document (not a new node). The apply function should:

- Read `<agent_name>_output.md` from the crew worktree
- Extract the plan content (the detailer template likely uses a single
  delimiter pair — check `.aitask-scripts/brainstorm/templates/detailer.md`
  for the exact format; add delimiters to the template if not yet present)
- Validate the plan has content
- Write the plan to `br_plans/<target_node_id>_plan.md`
  (use `brainstorm_dag.PLANS_DIR` constant)
- Update the target node's YAML to set `plan_file:
  br_plans/<target_node_id>_plan.md` — use `update_node()` from
  `brainstorm_dag.py`
- Does NOT create a new node, does NOT update `current_head` or `next_node_id`
  (detailer enriches an existing node, not creates a new one)

### 2. TUI auto-apply hook in `brainstorm_app.py`

After a detailer group completes, the TUI should auto-call
`apply_detailer_output`. The target node ID must be derivable from the agent's
group context or stored in the agent's `_status.yaml` at registration time.

- `_try_apply_detailer_if_needed(agent_name, force=False)` method
- Call from the timer tick when detailer status reaches `Completed`
- Show failure banner; provide manual retry

### 3. Error log

On failure write `<agent_name>_apply_error.log`.

## Files to touch

- `.aitask-scripts/brainstorm/brainstorm_session.py` — add `apply_detailer_output()`
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add TUI auto-hook
- `.aitask-scripts/brainstorm/templates/detailer.md` — verify/add plan
  delimiter markers so the apply function has a reliable extraction boundary
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — confirm `update_node()`
  can set `plan_file`; add if missing

## Reference: existing end-to-end flow

Study these before implementing:
- `brainstorm_session.py:apply_initializer_output` (line 336)
- `brainstorm_session.py:_extract_block` (line 253)
- `brainstorm_dag.py:create_node` and `update_node`
- `brainstorm_app.py:_try_apply_initializer_if_needed` (line 2104)
- `brainstorm_app.py` timer tick at line 3742
- `aitask_brainstorm_apply_initializer.sh`

## See also (sibling tasks)

- t739 apply-explorer (creates new nodes; different output format but same general
  apply pattern)
- t740 apply-synthesizer (creates new nodes; same four-delimiter format as explorer)
- t743 apply-patcher (enriches/forks existing node like detailer does, but
  three-part output with impact analysis)
