---
Task: t929_2_module_decompose_prompt_driven_inference.md
Parent Task: aitasks/t929_brainstorm_decompose_prompt_iterate_carveout_and_docs.md
Sibling Tasks: aitasks/t929/t929_3_brainstorm_tui_code_verified_docs.md
Archived Sibling Plans: aiplans/archived/p929/p929_1_module_decompose_iterate_before_apply.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-05 11:10
---

# t929_2 — Prompt-driven module-set inference (verified 2026-06-05)

## Context

`module_decompose` (brainstorm TUI) today forces the user to **type module
names up front**: `_config_module_decompose` collects a names TextArea,
`_actions_collect_config` rejects an empty list, and the agent only assigns
*content* to those names. Design doc §4.2 says module names can be "supplied
manually OR identified by an agent" — the agent-driven path is unimplemented.
This task lets the agent **propose** the module set from the free-text
Decomposition Plan when names are left blank. Sibling **t929_1** (landed) added
the review gate (`ModulePreviewScreen` + pure `parse_module_decomposer_output`)
and steering, so proposed names are reviewable before they commit.

## Verification of the existing plan against current code (post-t929_1)

The pre-t929_1 plan was directionally right but is **stale** and has **one real
gap**:

- **All line numbers shifted.** Current surfaces:
  - `brainstorm_app.py`: `_config_module_decompose()` @6954; names collected in
    `ta_module_decompose_modules` TextArea @6972-6973; parsed/validated in
    `_actions_collect_config` @7195-7224 (empty rejected @7203-7205, uniqueness
    @7206-7208); `operation_extra` persists `modules`/`from_sections`/
    `instructions` etc. @7660-7672; dispatch `register_module_decomposer` @7691;
    `from_sections` deterministic branch @7673-7689; `ModulePreviewScreen`
    @2298-2374 (shows `module_name`, `node_id`, `proposal_excerpt`);
    `_open_module_preview` @5041; `_try_apply_module_agent_if_needed` review gate
    @4977-5028; `_module_rerun_decomposer` @5090.
  - `brainstorm_crew.py`: `_assemble_input_module_decomposer()` @546 (emits
    `## Modules`, `## Options`, `## Assigned Module Node IDs` via
    `_module_node_id_lines` @498, optional `## Decomposition Plan`, optional
    `## Steering`); `register_module_decomposer()` @887 pre-generates IDs
    `n{num:03d}_{agent}_{safe_module}` @909-913.
  - `brainstorm_session.py`: `parse_module_decomposer_output()` @1465 (PURE);
    `apply_module_decomposer_output()` @1514; `_module_decomposer_needs_apply`
    @1176; `module_decomposer_review_enabled` @1219.
  - `templates/module_decomposer.md`: output already echoes `MODULE_NAME`; has
    Steering rules; says "Use the assigned node IDs verbatim".

- **THE GAP (correction to original task body).** The original task assumed
  t929_1's parser "handles agent-named modules + late node-ID assignment." It
  does **not**: `parse_module_decomposer_output` raises `ValueError` when
  `node_id` is missing (@1500-1502), `apply` reads `node_id` straight from the
  agent's NODE_YAML (@1543), and `_module_decomposer_needs_apply` treats a
  missing `node_id` as "still needs work" (@1209-1213). In infer mode the agent
  cannot know node IDs (the names aren't pre-generated). **So node-ID deferral
  needs a concrete mechanism — it is genuine new work, not a freebie.**

## UX: explicit 3-way mode selector (chosen with user)

Replace the implicit `chk_from_sections` checkbox with a **RadioSet** that makes
all three decompose modes explicit and discoverable:

```
Decompose mode:
( ) Manual — I type the names
(•) Agent-proposed — infer from the Plan      <-- NEW
( ) From section markers
```

This folds the existing `from_sections` flag into the same control (no more
silent "blank means infer"). Default = **Manual** (preserves today's behavior
and the fast-track preset). The Modules field is relabeled "(used by Manual /
From-sections)". RadioSet follows the existing pattern in
`diffviewer/plan_manager_screen.py` (RadioButton children, read via
`pressed_index`); it is mounted imperatively like the other config widgets.

The radio is **purely a config-collection UI change** — it still produces the
same downstream `cfg` keys. Mapping:
- Manual → `from_sections=False`, `modules` non-empty.
- Agent-proposed → `from_sections=False`, `modules=[]` (infer).
- From section markers → `from_sections=True`, `modules` non-empty.

So the crew/session side needs **no new mode field**: the infer signal stays
`modules == [] and not from_sections`, already recoverable from the persisted
`operation_extra` (re-runs replay it naturally).

## Core mechanism: normalize-before-parse (keeps the pure parser & apply untouched)

Defer node-ID assignment via a single idempotent **normalization** step that
runs *before* any parse, injecting deferred IDs into `_output.md`. After it
runs, the infer-mode output is shape-identical to a names-given output, so
`parse`, `_module_decomposer_needs_apply`, `apply`, and `ModulePreviewScreen`
all work **unchanged** (proposed names AND assigned IDs show in the preview for
free). Chosen over making the parser tolerate missing IDs because it keeps the
pure/strict parser contract intact and gives the preview real node IDs.

## Implementation steps

1. **Mode selector + optional names (config) — `brainstorm_app.py`.**
   - `_config_module_decompose` @6972-6974: relabel the Modules label
     `[bold]Modules (used by Manual / From-sections)[/]`; **replace** the
     `chk_from_sections` checkbox with a `RadioSet` (class
     `rs_decompose_mode`) holding three `RadioButton`s — `Manual` (value=True /
     default), `Agent-proposed (infer)`, `From section markers`. Import
     `RadioSet, RadioButton` from `textual.widgets`. Mount it imperatively
     (`RadioSet(RadioButton(...), ...)`) where the checkbox was.
   - `_actions_collect_config` @7203-7224: read the pressed mode via
     `query_one(".rs_decompose_mode", RadioSet).pressed_index` (0=manual,
     1=infer, 2=sections). Derive `config["from_sections"] = (mode == sections)`
     and treat `mode == infer` as the empty-names path. Validation by mode:
     - Manual / From-sections → require non-empty `modules`, keep the uniqueness
       check (notify "Enter module names" / "Module names must be unique").
     - Agent-proposed → require a non-empty Decomposition Plan; set
       `config["modules"] = []` (ignore any text in the names field). Notify
       "Agent-proposed mode needs a Decomposition Plan to infer from" when the
       plan is blank.
     - Keep `config["instructions"]`, `link_to_task`, `review_before_apply` as
       today.

2. **Crew input assembly branch — `brainstorm_crew.py` `_assemble_input_module_decomposer` @561-589.**
   - When `modules` is non-empty: today's behavior (unchanged → byte-identical).
   - When `modules == []` (infer): omit `## Modules` and the
     `_module_node_id_lines()` block; instead emit a `## Decomposition Mode`
     section: `infer` + a directive to identify module boundaries from
     `<!-- section: -->` markers, `component_*` dims, and the Decomposition Plan;
     choose concise module names; emit each as `MODULE_NAME`; and **omit
     `node_id`** from NODE_YAML (it will be assigned). Add a small
     `_module_infer_directive_lines()` helper mirroring `_module_node_id_lines`.
   - `register_module_decomposer` @909-913 already produces an empty
     `module_node_ids` dict when `modules == []` — no pre-generation. No change
     needed there beyond passing the empty list through (already does).

3. **Template infer path — `templates/module_decomposer.md`.**
   - `## Input`: note that names may be omitted; when a `## Decomposition Mode:
     infer` section is present, the agent proposes the module set itself.
   - `## Output` / `## Rules`: when inferring, MODULE_NAME = the agent's chosen
     name, and **leave `node_id` out of NODE_YAML** (orchestrator assigns it;
     it already overwrites `proposal_file`/`parents`/`created_by_group`). Keep
     the names-given rules ("use assigned IDs verbatim") for that mode.

4. **Node-ID deferral (normalization) — `brainstorm_session.py`.**
   - New `assign_inferred_module_node_ids(task_num, agent_name) -> None`: read
     `{agent}_output.md`; for each MODULE_NODE block whose NODE_YAML lacks
     `node_id`, assign `n{next_node_id(wt):03d}_{agent_name}_{safe_module}`
     (reuse the exact crew scheme; `safe_module` from MODULE_NAME), inject
     `node_id: <id>` into the NODE_YAML text, and rewrite the file. **Idempotent**
     (no-op when every block already has a `node_id` → names-given path
     untouched). Uniqueness is inherent (monotonic `next_node_id`); apply's
     existing `node {id} already exists` guard (@1544) remains the backstop.
   - Call it once before each parse: at the top of
     `apply_module_decomposer_output` (after read, before `parse`, covers
     review-off auto-apply) and in `_open_module_preview` before `parse`
     (covers review-on, so the preview shows the assigned IDs). Both idempotent;
     the poll-timer `_module_review_pending` guard ensures preview opens once.
   - **Parser and apply stay strict & unchanged** — by the time they parse, IDs
     are present.

5. **Review integration — no `ModulePreviewScreen` change.** Because
   normalization runs before the preview parse, the existing screen already
   renders proposed `module_name` + assigned `node_id` + `proposal_excerpt`.
   Re-run/steer and Cancel paths work as-is (Cancel renames the output via
   `discard_module_decomposer_output`; the consumed counter values are harmless).

## Verification

- **Unit (`tests/test_brainstorm_apply_module_ops.py`):**
  - Infer assembly: `_assemble_input_module_decomposer(..., modules=[])` omits
    `## Modules` / `## Assigned Module Node IDs`, includes the infer directive +
    the Decomposition Plan.
  - Names-given assembly is **byte-identical** to today (regression).
  - `assign_inferred_module_node_ids`: a no-node_id output gets unique
    `n{num:03d}_{agent}_{safe}` IDs injected; running it twice is a no-op; a
    names-given output is left byte-identical.
- **Integration (`tests/test_brainstorm_module_ops_integration.py`):**
  - Agent-proposed mode + plan → agent output without node_ids → normalize →
    preview shows proposed names+IDs → accept commits the nodes.
  - Manual/names-given path unchanged (existing parser/apply/review tests pass).
- **Config (mode mapping + validation):** Agent-proposed + Plan accepted
  (`modules` collected as `[]`, `from_sections=False`); Agent-proposed + blank
  Plan rejected; Manual + empty names rejected; From-sections selected →
  `from_sections=True` with names required.
- **Manual:** `ait brainstorm <task>` → `A` on a node → Module Decompose →
  select **Agent-proposed** mode + write a Decomposition Plan → agent proposes
  modules → review shows names → accept commits.
- Run the brainstorm test suite.

See parent task **Step 9 (Post-Implementation)** for cleanup, archival, merge.

## Notes for sibling tasks

- t929_3 (docs) documents this inference path; record any residual
  design-vs-implementation gaps surfaced here (notably: from_sections is the
  deterministic alternative; infer mode is the agent path; node IDs are assigned
  at normalization time, not by the agent).

## Risk

### Code-health risk: medium
- Adds a normalization call at the top of the load-bearing
  `apply_module_decomposer_output` and a second (infer) branch through decompose
  assembly · severity: medium · → mitigation: in-plan — normalization is
  idempotent and a strict no-op for names-given outputs (they already carry
  `node_id`); names-given assembly asserted byte-identical; the infer branch is
  guarded by `modules == []`, unreachable in Manual / From-sections modes.
- Replaces the `chk_from_sections` checkbox with a RadioSet · severity: low · →
  mitigation: the checkbox is referenced only at its two config sites
  (`brainstorm_app.py:6974` mount, `:7211` read) and by no test, so the swap is
  fully contained to `_config_module_decompose` / `_actions_collect_config`;
  downstream `cfg["from_sections"]` semantics are preserved.
- Normalization consumes `next_node_id` at preview time, so a Cancelled preview
  advances the node counter (non-colliding, never reused) · severity: low · →
  mitigation: documented; counter monotonicity already guarantees uniqueness.

### Goal-achievement risk: low
- Depends on the agent reliably omitting `node_id` and supplying MODULE_NAME in
  infer mode · severity: low · → mitigation: template-driven contract +
  integration test; if the agent emits a node_id anyway, normalization no-ops
  and apply uses it (still correct).
