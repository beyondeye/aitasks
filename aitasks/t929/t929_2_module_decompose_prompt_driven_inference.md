---
priority: medium
effort: high
depends: [t929_1]
issue_type: enhancement
status: Ready
labels: [ait_brainstorm]
created_at: 2026-06-03 15:53
updated_at: 2026-06-03 15:53
---

## Context

Child of t929. Today `module_decompose` requires the user to **type module names up front** (`brainstorm_app.py` ~6937 parses comma/newline names); the agent only *assigns content* to those given names. Design doc `aidocs/brainstorming/module_decomposition_design.md` §4.2 states module names "can be supplied manually **OR identified by an agent**" (agent-driven is even the doc's default mode) — this inference path is **unimplemented**. This child lets the agent **propose** the module set/names from a free-text prompt when names are omitted.

Depends on **t929_1** (iterate-before-apply preview gate): agent-proposed names must be reviewable/editable before they commit, which is exactly what the t929_1 gate provides.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `_config_module_decompose()` (~6698) — make the names field optional; relabel; validation allows empty names when a Decomposition Plan/prompt is present.
  - Name parsing (~6937) — branch into "infer mode" when names are empty.
- `.aitask-scripts/brainstorm/brainstorm_crew.py`
  - `_assemble_input_module_decomposer()` (~510) — emit infer-mode instructions when no names supplied.
  - `register_module_decomposer()` (~849) — currently pre-generates node IDs from given names; defer node-ID assignment to apply time when inferring.
- `.aitask-scripts/brainstorm/templates/module_decomposer.md` — add the inference instruction path + a "proposed module names" output contract.
- `.aitask-scripts/brainstorm/brainstorm_session.py` — parse path (built in t929_1's `parse_module_decomposer_output`) handles agent-named modules + late node-ID assignment.
- Tests: `tests/test_brainstorm_apply_module_ops.py`, `tests/test_brainstorm_module_ops_integration.py`.

## Reference Files for Patterns

- Design doc §4.2 (`aidocs/brainstorming/module_decomposition_design.md`) — agent-driven name identification using `<!-- section: -->` markers and `component_*` dims as candidate boundaries; the `--from-sections` deterministic alternative.
- t929_1 plan (`aiplans/p929/p929_1_*.md`) — the preview gate and `parse_module_decomposer_output` helper this child consumes.
- Existing `module_decomposer.md` template — output block format (`MODULE_NODE`, NODE_YAML, PROPOSAL delimiters) to extend.

## Implementation Plan

1. **Optional names.** In `_config_module_decompose()`, relabel the names field "(optional — leave blank to let the agent propose)"; allow empty when a Decomposition Plan/prompt is present. Determine `infer_mode = (no names) and (plan present)`.
2. **Template inference path.** In `module_decomposer.md`, add a conditional section: in infer mode, instruct the agent to identify module boundaries from section markers / `component_*` dims / the free-text prompt and to **emit the proposed module name** in each `MODULE_NODE` block (extend the output contract so names come back from the agent, not just content).
3. **Input assembly.** `_assemble_input_module_decomposer()` switches between "names given" (today) and "infer" (omit the assigned names/IDs, include the prompt + inference directive).
4. **Node-ID deferral.** When inferring, do not pre-generate node IDs in `register_module_decomposer()` (the names aren't known yet). Assign IDs at parse/apply time from the agent's returned names (reuse the `n{num:03d}_{agent}_{safe_module}` scheme). Keep the pre-assigned path for the names-given case.
5. **Review integration.** Proposed names flow into the t929_1 `ModulePreviewScreen` so the user can review/edit/re-run before apply.

## Verification Steps

- Unit: infer-mode input assembly omits names + includes prompt; agent-named-module parsing produces correct nodes; node-ID deferral yields unique non-colliding IDs; names-given path unchanged (regression).
- Integration: empty-names decompose with a prompt → agent proposes a module set → preview shows proposed names → accept commits them.
- Manual: `ait brainstorm <task>`, Module Decompose, leave names blank + write a Decomposition Plan → agent proposes modules → review in preview → accept.
- Run the brainstorm test suite.
