---
priority: medium
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [ait_brainstorm]
children_to_implement: [t929_3]
folded_tasks: [776]
created_at: 2026-06-03 14:06
updated_at: 2026-06-05 11:22
boardcol: now
boardidx: 20
---

## Context

Surfaced while working in an `ait brainstorm` session, trying to extract/subdivide a full proposal into modules. This is a **parent** task to be **split into children during planning**: an *enhancement track* (module-decompose usability) and a *documentation track* (code-verified brainstorm usage docs). It extends the existing module feature (`t756` family) and its design doc `aidocs/brainstorming/module_decomposition_design.md` — it does **not** add a new operation (per design §4.9, UC-3 is a parameterisation of `decompose`).

## Findings (current state of `module_decompose`)

Today's `module_decompose` (TUI: press `A` on a node → "Module Decompose"; `_config_module_decompose()` ~ `.aitask-scripts/brainstorm/brainstorm_app.py:6698`; agent `register_module_decomposer()` `.aitask-scripts/brainstorm/brainstorm_crew.py:849`; input assembly `_assemble_input_module_decomposer()` `brainstorm_crew.py:510`; template `.aitask-scripts/brainstorm/templates/module_decomposer.md`):

- The user must **type the module names up front** (`brainstorm_app.py:6937` parses comma/newline names). The agent only *assigns content* to those given names, guided by `<!-- section: -->` markers, `component_*` dims, and an optional free-text "Decomposition Plan" (`ta_module_decompose_plan`, passed as `instructions`). There is **no name/module-set inference** by the agent — design §4.2's "names can be supplied manually OR identified by an agent" is unimplemented.
- The decomposer runs **one-shot**; on completion its `MODULE_NODE` output is **auto-applied** to the graph by a poll timer (`brainstorm_app.py:4872` → `_try_apply_module_agent_if_needed` → `apply_module_decomposer_output` `brainstorm_session.py:1413`). There is **no review/steer/accept gate** — only an error+retry path. Changing boundaries means cascade-delete + full redo.
- `decompose` **forks, never prunes**: it copies a module-scoped slice into a new independently-evolvable subgraph but leaves the umbrella whole (template rule 5: "Do not update the umbrella proposal"; design §4.2 side-effect). For "fast-track one module, the rest waits" (UC-3), the correct op is the existing **"Fast-track this module" preset** (single-module decompose + link-to-task; `brainstorm_app.py:3879-3890`), and **"the rest" = the untouched umbrella**, not a disjoint complement. A true carve-out (reduce umbrella to the complement) does not exist.

## Enhancement track (children to plan)

1. **Prompt-driven module-set inference** — let the agent *propose* the module set/names from a free-text prompt when names are omitted (realize design §4.2 intent). Reuses existing `module_decomposer` machinery (reads whole proposal, emits N `MODULE_NODE` blocks).
2. **Iterate-before-apply** — a preview/steer/accept loop on the *proposed* decomposition before it commits to the graph (today it auto-applies). Model after how explore/patch surface output before apply.
3. **Optional disjoint carve-out mode** — reduce the umbrella to the complement of the carved-out module (vs. today's fork-only), with the disjoint split shown in the preview.

All three land as an extended mode of `decompose`/fast-track, not a new op.

## Documentation track (child to plan) — incorporates folded t776

4. **Code-verified `ait brainstorm` usage guide** → base for website docs at `website/content/docs/tuis/brainstorm/{_index,how-to,reference}.md` (mirroring board/codebrowser/settings/monitor/syncer/stats). `aidocs/brainstorming/` is **design/architecture only**; there is **no website brainstorm page** despite CLAUDE.md listing brainstorm as a documented TUI. The guide must be **verified against actual code behavior** (real keybindings, wizard flows, ops as implemented) and explicitly **record design-vs-implementation divergences** found here (e.g. mandatory module names, fork-not-prune). t776 (folded below) is the prior, broader "document the whole brainstorm TUI" task; its scope is incorporated here.

## References

- Design doc: `aidocs/brainstorming/module_decomposition_design.md` (UC-1/2/3, §4.2 decompose, §4.8 fast-track, §4.9 why-3-ops).
- Related (not folded): `t756` family (module feature parent + children, has children), `t569` (different op: child-split for impl ordering), `t535` (status-tab agent actions), `t925` (node ops surfacing).

## Verification

- Enhancement: manual brainstorm session — prompt with no names → agent proposes module set; preview → edit/accept before apply; carve-out reduces umbrella. Plus unit/integration tests mirroring `test_brainstorm_apply_module_ops.py` / `test_brainstorm_module_ops_integration.py`.
- Docs: `cd website && ./serve.sh`, browse `/docs/tuis/brainstorm/`, confirm the page renders and the `tuis/_index.md` bullet links it (drop "Dedicated documentation is pending"); cross-check documented behavior against the code.

## Merged from t776: brainstorm tui user facing docs


## Context

The `ait brainstorm` TUI currently has no dedicated documentation page. The TUI overview at `website/content/docs/tuis/_index.md` lists it with the note "Dedicated documentation is pending". This follow-up was carved out of t749_7 (retrospective evaluation for the operation-provenance feature) because:

- The original t749_7 plan called for adding a small docs section covering only the new operation-provenance bits (DAG badge, dashboard "Generated by" block, `o` keybinding, `OperationDetailScreen`, `OpDataRef`).
- Writing a partial doc for one feature when the umbrella TUI is undocumented is awkward and produces a doc that goes stale quickly.
- The new operation-provenance feature must first be user-verified via the manual-verification sibling `t749_8` before docs are stable enough to write.

## Goal

Write a dedicated brainstorm TUI doc page modelled on the existing per-TUI doc pages (board, codebrowser, settings, monitor, syncer, stats).

## Key Files to Modify

- `website/content/docs/tuis/brainstorm/_index.md` (NEW) — overview page for the brainstorm TUI.
- (Optional follow-ups) `website/content/docs/tuis/brainstorm/how-to.md` and `reference.md`, mirroring the pattern from `board/`, `codebrowser/`, etc.
- `website/content/docs/tuis/_index.md` — update the brainstorm bullet to link to the new page and drop the "Dedicated documentation is pending" suffix.

## Reference Patterns to Follow

- `website/content/docs/tuis/board/_index.md` and `how-to.md` — pattern for overview + how-to split.
- `website/content/docs/tuis/codebrowser/_index.md` — concise feature-rich overview model.
- `website/content/docs/tuis/syncer/_index.md` — recent example added in t693 family.

## Suggested Section Coverage

- Launch flow: `ait brainstorm <task>` and `--proposal-file` variants.
- Session layout: dashboard left/right panes, status tab, compare tab, DAG view.
- DAG view: 5-row node box (introduced in t749_3), operation-color legend (cyan=explore, yellow=compare, magenta=hybridize, blue=detail, red=patch, dim=bootstrap).
- Operations: explore / compare / hybridize / detail / patch / bootstrap — what each does and which agents it spawns.
- Operation provenance UI:
  - Dashboard right-pane "Generated by" block (t749_4).
  - `o` keybinding on focused DAG node or dashboard NodeRow (t749_6).
  - `OperationDetailScreen` modal: Overview tab + per-agent Input/Output/Log tabs (t749_5).
- Contributor primitive: `OpDataRef` (t749_2) — pointer-to-on-disk-data pattern.
- Footer keys: `j Next  k Prev  enter Open  h Set HEAD  o Operation` on the DAG view.

## Dependencies

Depends on t749_8 (manual verification of the operation-provenance feature). Writing docs before manual verification risks documenting behaviour that does not match the intended spec.

## Verification

1. `cd website && ./serve.sh` — locally browse to `/docs/tuis/brainstorm/` and confirm the new page renders.
2. Confirm the brainstorm bullet in `/docs/tuis/` no longer says "Dedicated documentation is pending" and links to the new page.
3. Cross-check with the manual-verification checklist for t749 to make sure documented behaviour matches what was verified.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t776** (`t776_brainstorm_tui_user_facing_docs.md`)
