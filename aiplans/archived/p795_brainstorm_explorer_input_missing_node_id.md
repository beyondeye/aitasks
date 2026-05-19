---
Task: t795_brainstorm_explorer_input_missing_node_id.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
---

# Plan: Assign node_id at registration for all node-creating agents

## Context

Surfaced during t792 diagnosis. The orchestrator's
`_assemble_input_explorer` / `_assemble_input_synthesizer` /
`_assemble_input_patcher` (`.aitask-scripts/brainstorm/brainstorm_crew.py`)
build the `<agent>_input.md` consumed by each agent, but never include
the `node_id` the agent should use. The explorer template
(`.aitask-scripts/brainstorm/templates/explorer.md:30`) tells the agent
"Use the ID assigned by the orchestrator (provided in input)" — but
the input does not contain one. Each agent must invent an ID.

The collision risk is general across **every** node-creating agent:

- **Explorer** — `max_parallel=2` per group → highest blast radius
  (concrete near-miss in `brainstorm-635`, t792).
- **Synthesizer** — `max_parallel=1` per group, but multiple
  synthesize_* groups can run in parallel.
- **Patcher** — `max_parallel=1` per group, but multiple patch_*
  groups can run in parallel, and a patcher in one group can collide
  with an explorer in another.

Initializer is **not** a node creator in the same sense: it overwrites
the fixed seed id `n000_init` and never allocates a fresh number.

The general fix: have the orchestrator consume the canonical
counter (`next_node_id()`, `brainstorm_dag.py:136-145`) at registration
time and bake the assigned id into `_input.md`. Each agent uses its
input's `node_id` verbatim.

## Approach

Single uniform pattern across `register_explorer`, `register_synthesizer`,
`register_patcher`:

1. Consume the counter at registration:
   `node_num = next_node_id(session_dir)` →
   `assigned_node_id = f"n{node_num:03d}_{agent_name}"`.
2. Pass `assigned_node_id` through to the `_assemble_input_*` helper.
3. Helper appends a `## Assigned Node ID` block to the input markdown
   with the value and a one-line "use verbatim" instruction.
4. Templates updated to require the agent to copy that value verbatim
   into the YAML `node_id` field.
5. The apply-side `next_node_id(wt)` consumer in both
   `_apply_node_output` (`brainstorm_session.py:950`) and
   `apply_patcher_output` (`brainstorm_session.py:735`) is removed —
   registration now owns the counter, so leaving the apply-side bump
   would double-count.

Counter gaps from failed/aborted agents are harmless — the counter is
monotonic; gaps just mean a few unused id numbers.

Assigned id format: `n{N:03d}_{agent_name}` (e.g.
`n002_explorer_001a`, `n003_synthesizer_001`, `n004_patcher_001`).
Deterministic, unique across parallel siblings (agent_name carries
the suffix letter for explorers), and immediately useful in logs.

The existing `f"node {new_node_id} already exists"` guards in both
apply paths (`brainstorm_session.py:930-931` and `:704-705`) stay
in place as belt-and-suspenders — they catch any agent that ignores
the assigned id.

## Critical files

- `.aitask-scripts/brainstorm/brainstorm_crew.py` — registration helpers
  (`register_explorer`, `register_synthesizer`, `register_patcher`)
  and input assembly (`_assemble_input_explorer`,
  `_assemble_input_synthesizer`, `_assemble_input_patcher`).
- `.aitask-scripts/brainstorm/brainstorm_session.py` — drop apply-side
  counter bumps in `_apply_node_output` (line 950) and
  `apply_patcher_output` (line 735).
- `.aitask-scripts/brainstorm/templates/explorer.md` — update
  Phase 3 node_id instruction.
- `.aitask-scripts/brainstorm/templates/synthesizer.md` — explicit
  verbatim contract in Phase 4 metadata bullets.
- `.aitask-scripts/brainstorm/templates/patcher.md` — explicit
  verbatim contract in Part 3 metadata instructions.
- `tests/test_brainstorm_crew.py` — adapt three existing
  `_assemble_input_explorer` calls + add collision test.
- `tests/test_brainstorm_apply_explorer.py:190` — adjust counter
  expectation (now `== 1`, was `== 2`).
- `tests/test_brainstorm_apply_patcher.py:179` — same adjustment.

Initializer is left untouched.

## Implementation steps

### 1. Add `assigned_node_id` to input assembly

`brainstorm_crew.py::_assemble_input_explorer` — new required
keyword parameter `assigned_node_id: str`. Append before the trailing
newline:

```
## Assigned Node ID
<assigned_node_id>

Use this exact value as the `node_id` field of your output YAML.
Do not invent a different id or modify it in any way.
```

`brainstorm_crew.py::_assemble_input_synthesizer` — same signature
change, same trailing block.

`brainstorm_crew.py::_assemble_input_patcher` — same signature change,
same trailing block (the patcher's input already references "Current
Node" — the assigned id is for the **new** patched-copy node it will
create).

### 2. Allocate at registration

Add `next_node_id` to the existing `from .brainstorm_dag import (...)`
block at the top of `brainstorm_crew.py` (it's already exported and in
use elsewhere in the package).

`register_explorer`:

```python
node_num = next_node_id(session_dir)
assigned_node_id = f"n{node_num:03d}_{agent_name}"

input_content = _assemble_input_explorer(
    session_dir, base_node_id, mandate, active_dimensions,
    assigned_node_id=assigned_node_id,
    target_sections=target_sections,
)
```

`register_synthesizer` — same pattern, `agent_name` already
`f"synthesizer_{seq}"`.

`register_patcher` — same pattern, `agent_name` already
`f"patcher_{seq}"`.

### 3. Drop apply-side counter bumps

`brainstorm_session.py::_apply_node_output`: remove the
`next_node_id(wt)` call (currently line 950). The on-disk
`f"node {new_node_id} already exists"` guard
(`brainstorm_session.py:930-931`) stays.

`brainstorm_session.py::apply_patcher_output`: remove the
`next_node_id(wt)` call (currently line 735). The
`f"node {new_node_id} already exists"` guard at
`brainstorm_session.py:704-705` stays.

### 4. Update templates

`templates/explorer.md` line 30 — replace:

```
- node_id: Use the ID assigned by the orchestrator (provided in input)
```

with:

```
- node_id: Copy the value from the `## Assigned Node ID` section of
  your `_input.md` **verbatim**. Do not invent a different id, and do
  not modify it in any way.
```

`templates/synthesizer.md` — the Input section already lists "The new
node ID assigned by the orchestrator" at line 13. Add a matching
bullet to the "File 1: Node Metadata (YAML)" requirements list
(currently lines 25-31): `- node_id: Copy the value from the
"## Assigned Node ID" section of your _input.md verbatim.`

`templates/patcher.md` — Part 3 (lines 50-57) currently says "Output a
copy of the parent's YAML with only node_id and parents updated (new
node ID, parent = current node)". Replace "new node ID" with: "use
the value from the `## Assigned Node ID` section of your `_input.md`
verbatim as the new node_id".

### 5. Update tests

`tests/test_brainstorm_crew.py`:

- Three existing `_assemble_input_explorer(...)` call sites (lines
  143, 167, 176) — pass `assigned_node_id="n001_explorer_001a"` (or
  similar test-stable value).
- New test `test_explorer_input_includes_assigned_node_id` — asserts
  the `## Assigned Node ID` heading and value appear in the output.
- New test `test_parallel_explorers_get_distinct_node_ids` — calls
  `register_explorer` twice with same `group_name` and different
  `agent_suffix` ("a" and "b"), then parses each emitted
  `<agent>_input.md` (via `_write_agent_input`'s on-disk artifact)
  and asserts the two `## Assigned Node ID` values differ. Mock
  `_run_addwork` (no real `ait crew addwork` shell call needed) using
  `unittest.mock.patch`.

`tests/test_brainstorm_apply_explorer.py:190`: change
`self.assertEqual(gs["next_node_id"], 2)` →
`self.assertEqual(gs["next_node_id"], 1)`. Counter no longer advances
at apply time.

`tests/test_brainstorm_apply_patcher.py:179`: same adjustment, `== 2`
→ `== 1`.

## Verification

1. `python tests/test_brainstorm_crew.py` — crew tests (existing +
   new collision test) pass.
2. `python tests/test_brainstorm_apply_explorer.py` — apply tests
   pass with the updated counter expectation.
3. `python tests/test_brainstorm_apply_patcher.py` — patcher apply
   tests pass with the updated counter expectation.
4. `python tests/test_brainstorm_dag.py` — `next_node_id` primitive
   unaffected.

## Acceptance check

- Two parallel explorers registered to the same group receive
  distinct `node_id` values in their `_input.md`, deterministically
  derived from `next_node_id()` × agent_name.
- Same guarantee for synthesizer / patcher across groups.
- The "already exists" guards in both apply paths remain as a
  defensive net.

## Step 9 (Post-Implementation)

Standard cleanup per `.claude/skills/task-workflown-fast-/SKILL.md`
Step 9: fast profile works on current branch, no merge step.
`aitask_archive.sh 795` handles the rest.

## Final Implementation Notes

- **Actual work done:** Implemented the plan as written. The
  orchestrator now consumes `next_node_id()` at registration time in
  `register_explorer`, `register_synthesizer`, and `register_patcher`,
  formatting the assigned id as `n{N:03d}_{agent_name}`. Each
  `_assemble_input_*` helper grew a required `assigned_node_id`
  parameter and appends a `## Assigned Node ID` block to the
  per-agent input markdown. Apply-side counter bumps were removed
  from both `_apply_node_output` and `apply_patcher_output`; the
  existing on-disk "already exists" guards remain as the
  belt-and-suspenders defensive net. Templates for explorer,
  synthesizer, and patcher were updated to require copying the
  assigned id verbatim. Three existing assembly tests in
  `test_brainstorm_crew.py` were updated to pass the new parameter;
  two new tests were added
  (`test_explorer_input_includes_assigned_node_id`,
  `test_distinct_node_ids_for_parallel_siblings`). Counter
  assertions in `test_brainstorm_apply_explorer.py` and
  `test_brainstorm_apply_patcher.py` were updated to reflect that
  apply no longer bumps the counter.
- **Deviations from plan:** Re-scoped the fix to cover the patcher
  in addition to explorer/synthesizer after user push-back that "if
  this is a general problem, it needs a general solution." Patcher's
  collision risk is structurally identical even though its
  `max_parallel=1` per group limits the practical likelihood — the
  uniform pattern is simpler than excluding one node-creator.
- **Issues encountered:** A first run of the new assembly test
  asserted the literal word "verbatim" in lowercase markdown, but
  the rendered prose phrases the requirement as "Do not invent a
  different id…". Tightened the assertion to match the actual prose.
- **Key decisions:**
  - Assigned id format `n{N:03d}_{agent_name}` (e.g.
    `n002_explorer_001a`). Deterministic, unique across parallel
    siblings via the agent suffix, descriptive enough for logs.
  - Skip the "defensive reject mismatched node_id" variant from the
    task suggestions; the on-disk "node already exists" check is
    structurally sufficient for the acceptance criteria and avoids
    re-parsing `_input.md` from the apply path.
  - Initializer is left untouched — it overwrites the fixed seed id
    `n000_init` and does not allocate a fresh counter value.
- **Upstream defects identified:** None.

