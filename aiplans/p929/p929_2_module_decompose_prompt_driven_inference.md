---
Task: t929_2_module_decompose_prompt_driven_inference.md
Parent Task: aitasks/t929_brainstorm_decompose_prompt_iterate_carveout_and_docs.md
Sibling Tasks: aitasks/t929/t929_1_module_decompose_iterate_before_apply.md, aitasks/t929/t929_3_brainstorm_tui_code_verified_docs.md
Archived Sibling Plans: aiplans/archived/p929/p929_*_*.md
Worktree: aiwork/t929_2_module_decompose_prompt_driven_inference
Branch: aitask/t929_2_module_decompose_prompt_driven_inference
Base branch: main
---

# t929_2 — Prompt-driven module-set inference

## Goal

When module names are omitted, let the decomposer agent **propose** the module
set/names from a free-text prompt — realizing design §4.2's agent-driven mode
(today unimplemented; the user must type names up front).

## Depends on t929_1

Agent-proposed names must be reviewable/editable before they commit — provided
by the t929_1 preview gate (`ModulePreviewScreen` +
`parse_module_decomposer_output()`). Read `aiplans/archived/p929/p929_1_*.md`
(once t929_1 lands) for the exact surfaces.

## Current state (verified)

- `_config_module_decompose()` (`brainstorm_app.py` ~6698) collects names in a
  TextArea; parsing splits on `[,\n]+` (~6937). The agent only assigns content
  to given names.
- `_assemble_input_module_decomposer()` (`brainstorm_crew.py` ~510) lists the
  module names + pre-assigned node IDs in `_input.md`.
- `register_module_decomposer()` (~849) pre-generates node IDs
  (`n{num:03d}_{agent}_{safe_module}`) from the given names.
- `templates/module_decomposer.md` input section says "Module names to create".

## Implementation steps

1. **Optional names** — `_config_module_decompose()`: relabel the names field
   "(optional — leave blank to let the agent propose)"; allow empty when a
   Decomposition Plan/prompt is present. Compute
   `infer_mode = (no names) and (plan present)`.
2. **Template inference path** — `templates/module_decomposer.md`: add a
   conditional section. In infer mode, instruct the agent to identify module
   boundaries from `<!-- section: -->` markers, `component_*` dims, and the
   prompt, and to **emit the proposed MODULE_NAME** in each `MODULE_NODE` block
   (extend the output contract so names come back from the agent).
3. **Input assembly** — `_assemble_input_module_decomposer()` switches between
   "names given" (today) and "infer" (omit assigned names/IDs; include the
   prompt + inference directive).
4. **Node-ID deferral** — when inferring, skip ID pre-generation in
   `register_module_decomposer()`; assign IDs at parse/apply time from the
   agent's returned names (reuse the existing scheme, dedupe vs the graph).
   Keep the pre-assigned path for names-given.
5. **Review integration** — proposed names flow into the t929_1
   `ModulePreviewScreen` for review/edit/re-run before apply.

## Verification

- Unit: infer-mode input assembly omits names + includes prompt; agent-named
  parsing creates correct nodes; deferred IDs are unique/non-colliding;
  names-given path unchanged (regression).
- Integration: empty-names + prompt → agent proposes set → preview shows names →
  accept commits.
- Manual: `ait brainstorm <task>` → Module Decompose, names blank + write a
  Decomposition Plan → agent proposes modules → review → accept.

See parent task **Step 9 (Post-Implementation)** for cleanup, archival, merge.

## Notes for sibling tasks

- The docs child (t929_3) documents this inference path; record any residual
  design-vs-implementation gaps surfaced here.
