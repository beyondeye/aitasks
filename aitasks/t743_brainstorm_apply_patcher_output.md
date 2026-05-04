---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [brainstorm]
created_at: 2026-05-04 16:24
updated_at: 2026-05-04 16:24
---

Implement `apply_patcher_output()` in the brainstorm engine so that when a
patcher agent completes, its three-part output is automatically parsed: the
patched plan is written to `br_plans/`, a new node is created with the updated
metadata, and IMPACT_FLAG cases surface a warning in the TUI.

## Background

The brainstorm engine has a complete end-to-end apply flow only for the
initializer agent (`apply_initializer_output` in
`.aitask-scripts/brainstorm/brainstorm_session.py` line 336, TUI auto-hook at
`brainstorm_app.py` line 2104). The patcher is the most complex missing case:
its output has three parts and two branches (NO_IMPACT vs IMPACT_FLAG). This
task was identified when patcher agent `patcher_001` for crew `brainstorm-635`
completed successfully but the runner stopped without materializing the output.
See sibling tasks: apply-explorer, apply-synthesizer, apply-detailer.

## Patcher output format (three-part)

```
--- PATCHED_PLAN_START ---
<modified plan markdown>
--- PATCHED_PLAN_END ---

--- IMPACT_START ---
**NO_IMPACT** <justification>
  — or —
**IMPACT_FLAG** <affected dimensions, old→new values, recommended action>
--- IMPACT_END ---

--- METADATA_START ---
<updated YAML with new node_id and parents>
--- METADATA_END ---
```

## What to implement

### 1. `apply_patcher_output(task_num, agent_name, source_node_id)` in `brainstorm_session.py`

- Read `<agent_name>_output.md` from the crew worktree
- Extract all three delimiter blocks using `_extract_block()`
- Parse the METADATA block via `_tolerant_yaml_load()`; validate via `validate_node()`
- Parse the IMPACT block: detect `**NO_IMPACT**` vs `**IMPACT_FLAG**`
- Write the patched plan to `br_plans/<new_node_id>_plan.md`
- Call `create_node()` with the parsed metadata and an empty proposal
  (patcher does not create a new proposal — it reuses the source node's
  proposal; pass `proposal_content = read_proposal(session_path, source_node_id)`)
- Set `plan_file: br_plans/<new_node_id>_plan.md` on the new node
- Call `set_head()` and `next_node_id()` to advance graph state
- Return `(new_node_id, impact_type, impact_details)` so the TUI can act on it

For NO_IMPACT: graph advances normally, no additional steps.
For IMPACT_FLAG: return the affected dimensions and recommended action so the
TUI can display the warning banner.

### 2. TUI auto-apply hook in `brainstorm_app.py`

After a patcher group completes, the TUI should auto-call
`apply_patcher_output` and branch on impact type:

- `_try_apply_patcher_if_needed(agent_name, source_node_id, force=False)`
- Call from the timer tick when patcher status reaches `Completed`
- On success + NO_IMPACT: clear any prior patcher banner, update node display
- On success + IMPACT_FLAG: show a persistent warning banner listing the
  affected dimensions and recommended action (e.g. "Explorer should
  regenerate proposal with component_cache changed from Redis to Memcached")
  — do NOT silently ignore IMPACT_FLAG
- On apply failure: show error banner; provide manual retry

### 3. Error log

On failure write `<agent_name>_apply_error.log`.

## Note on current state (brainstorm-635)

The output of `patcher_001` for brainstorm session 635 (task t635) is already
written to `.aitask-crews/crew-brainstorm-635/patcher_001_output.md` with all
three delimiter blocks present. Once this apply function is implemented, it
can be invoked manually to unblock that session:

```bash
ait brainstorm apply-patcher 635 patcher_001 n000_init
```

(add `aitask_brainstorm_apply_patcher.sh` wrapper script analogous to
`aitask_brainstorm_apply_initializer.sh`)

## Files to touch

- `.aitask-scripts/brainstorm/brainstorm_session.py` — add `apply_patcher_output()`
- `.aitask-scripts/brainstorm/brainstorm_app.py` — add TUI auto-hook + IMPACT_FLAG banner
- `.aitask-scripts/brainstorm/templates/patcher.md` — verify three-part delimiter format
- `.aitask-scripts/aitask_brainstorm_apply_patcher.sh` — new manual fallback wrapper

## Reference: existing end-to-end flow

Study these before implementing:
- `brainstorm_session.py:apply_initializer_output` (line 336)
- `brainstorm_session.py:_extract_block` (line 253)
- `brainstorm_session.py:_tolerant_yaml_load` (line 308)
- `brainstorm_app.py:_try_apply_initializer_if_needed` (line 2104)
- `brainstorm_app.py` timer tick at line 3742
- `aitask_brainstorm_apply_initializer.sh` — CLI wrapper pattern to replicate

## See also (sibling tasks)

- t739 apply-explorer (same general create-node pattern; NODE_YAML+PROPOSAL format)
- t740 apply-synthesizer (same four-delimiter format as explorer)
- t741 apply-detailer (enriches existing node like patcher does, but simpler
  single-part output with no impact analysis)
