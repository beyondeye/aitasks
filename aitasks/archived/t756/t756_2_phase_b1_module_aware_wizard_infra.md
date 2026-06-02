---
priority: high
effort: medium
depends: [t756_1, 898]
issue_type: feature
status: Done
labels: [ait_brainstorm, brainstom_modules, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 17:29
updated_at: 2026-06-02 10:11
completed_at: 2026-06-02 10:11
---

Phase B1 of the `ait brainstorm` **module decomposition** feature (parent t756).
The cross-cutting wizard plumbing that makes the brainstorm session module-aware,
**split out of the original Phase B** because it is the chunk that touches the most
existing code (design doc §4.5: "the chunk of work that touches the most existing
code"). **No new ops here** — this makes the *existing* ops subgraph-scoped and adds
the shared subgraph-selector the new ops (B2, t756_3) will build on. Depends on
Phase A (t756_1).

**Primary reference:** `aidocs/brainstorming/module_decomposition_design.md`
(§4.5 existing-ops-become-module-aware; §7 Phase A note placing the subgraph-selector
defaulting to `_umbrella`). **Binding conventions:** `aiplans/p756_brainstorm_modules.md`.

## Context
Phase A (t756_1) added per-subgraph HEADs (`current_heads`) and `module_label` on
nodes. For modules to be usable, the *existing* ops (`explore`, `compare`,
`synthesize`, `detail`, `patch`) must be scopeable to one subgraph, and the wizard
needs a subgraph-selector step. This is shared machinery the new ops (`module_decompose`
/`module_merge` in t756_3) reuse — extracting it here keeps B2 thin and resolves the
A/B boundary ambiguity flagged in t756_1's plan (the selector "lands in B if not cheap
in A" — it lands here).

## Scope
- `brainstorm_app.py`:
  - Insert a **subgraph-selector** wizard step before node-select. Default =
    most-recently-touched subgraph; fallback `_umbrella`. With a single subgraph the
    step is invisible/auto-selected so existing flows are unchanged.
  - `_NODE_SELECT_OPS` step 2 filters node candidates by
    `module_label == <selected subgraph>`.
  - Record the chosen `subgraph` in the op's `br_groups.yaml` group entry.
- `brainstorm_schemas.py`: add optional `subgraph` field on group entries (default
  `_umbrella` for back-compat with existing groups).
- `brainstorm_crew.py` + existing templates (`explorer.md`/`comparator.md`/
  `synthesizer.md`/`detailer.md`/`patcher.md`): add a small front-matter line
  "subgraph context: <module_label>" so the agent stays in scope; thread the module
  context through the `register_*()` input assembly.

## Reference Files for Patterns
- `brainstorm_app.py` existing wizard step machine (step1 op-picker → step2
  node-select → optional section-select → config → confirm) and `_execute_design_op`.
- t756_1's `get_head(module=...)` / `set_head(module=...)` and `current_heads` map.
- `aidocs/tui_conventions.md` (mandatory for Textual changes).

## Implementation Plan
1. Add the optional `subgraph` group field to the schema (default `_umbrella`).
2. Insert the subgraph-selector wizard step (auto-skip when only `_umbrella` exists).
3. Filter node-select candidates by `module_label`.
4. Record `subgraph` in group entries; add "subgraph context" template front-matter.

## Verification Steps
- With a single subgraph (`_umbrella` only), all existing ops behave exactly as
  before (back-compat — selector auto-selects, no visible change).
- On a constructed multi-module state (Phase A fixture), the subgraph selector lists
  subgraphs and node-select filters candidates by `module_label`.
- Group entries record `subgraph`; legacy groups without the field default to
  `_umbrella`.
- Existing brainstorm tests still pass; follow `aidocs/tui_conventions.md`.
