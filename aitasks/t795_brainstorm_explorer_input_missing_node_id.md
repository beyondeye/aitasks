---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_brainstorm, brainstorm_explore]
created_at: 2026-05-19 09:45
updated_at: 2026-05-19 09:45
---

Upstream defect surfaced during t792 diagnosis.

## Problem

`.aitask-scripts/brainstorm/brainstorm_crew.py::_assemble_input_explorer`
(lines 191-264) builds the `_input.md` consumed by each explorer agent
but **never writes the assigned `node_id`** into it. The explorer
work2do template (`.aitask-scripts/brainstorm/templates/explorer.md:30`)
instructs the agent:

> "node_id: Use the ID assigned by the orchestrator (provided in input)"

…but the input does not contain one. Each explorer must invent an ID.

### Why this matters

Parallel explorers in the same group (e.g. `explorer_001a` and
`explorer_001b` in `explore_001`) both invent `node_id` values
independently. In `brainstorm-635` they happened to pick different
slugs (`n002_template_resolved_gates`, `n002_profile_templated_gates`),
so no collision. But if both pick the same slug, the second apply
fails at the `node_id already exists` check
(`.aitask-scripts/brainstorm/brainstorm_session.py:885`) — the user
loses one explorer's output.

### Same gap in synthesizer

`_assemble_input_synthesizer` (lines 295-...) has the same omission.
Lower blast radius because synthesizer groups typically have a single
agent, but the input/template contract is still wrong.

## Suggested fix

1. In `_assemble_input_explorer`, before writing the input, derive
   the next free `node_id` for each agent via `next_node_id()` in
   `brainstorm_session.py` (already exists at line 905). Increment
   per-agent so parallel explorers get distinct IDs. Write into the
   `_input.md` a new section like:
   ```
   ## Assigned Node ID
   n00X_<slug-placeholder>
   ```
   The agent uses this verbatim instead of inventing one.
2. Mirror the change in `_assemble_input_synthesizer`.
3. Update `_apply_node_output` to defensively reject any agent-emitted
   `node_id` that doesn't match the assigned one (or just keep the
   existing "already exists" check; this is now belt-and-suspenders).
4. Optional follow-on: drop the "invent the slug suffix" instruction
   from the explorer template too, replaced by "use the assigned
   node_id verbatim".

## Acceptance

- Two parallel explorers in the same group never produce conflicting
  `node_id` values, even under adversarial inputs.
- Regression test: scaffold a fake crew worktree with two explorer
  agents whose outputs both nominate the same slug → confirm the
  orchestrator assignment overrides them, and both apply paths
  succeed with distinct IDs.

## Origin

Surfaced by t792 ("Force canonical created_by_group and add
group-level progress aggregate"). See
`aiplans/archived/p792_brainstorm_explore_progress.md` "Upstream
defects identified".
