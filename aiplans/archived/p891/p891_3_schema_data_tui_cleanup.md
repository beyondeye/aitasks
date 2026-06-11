---
Task: t891_3_schema_data_tui_cleanup.md
Parent Task: aitasks/t891_brainstorm_proposal_only_retire_plans.md
Sibling Tasks: aitasks/t891/t891_1_decision_docs_v2_architecture.md, aitasks/t891/t891_2_ops_agents_removal.md, aitasks/t891/t891_4_finalize_proposal_export.md
Worktree: (current branch — profile 'fast')
Branch: main (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-11 11:37
---

# Plan — t891_3: remove plan_file / br_plans data + plan TUI surfaces

## Context

`ait brainstorm` is being simplified to a **proposal-only** design engine (parent
t891). t891_2 already removed the `detail`/`patch` ops and detailer/patcher agents
(~3000 lines, archived). This third child removes the plan **data model** and the
plan **TUI surfaces**: the `plan_file` node field, the `br_plans/` store +
`read_plan`/`PLANS_DIR`, the node-detail **Plan tab**, the DAG plan **badge** (●/○)
and `l`/`view_plan` binding, the node-action/node-select plan markers, and the
plan half of the **node-detail export modal**. `ait brainstorm` is unshipped →
remove outright, no migration for existing `plan_file`-bearing sessions.

**Re-verification done (verify path).** All anchors below were re-checked against
the as-landed (post-t891_2) code on 2026-06-11. The surface is **materially larger
than the 2026-06-01 snapshot** — three areas the snapshot missed are flagged
`[NEW]` below.

## Sibling boundary (do NOT touch — belongs to t891_4)

`brainstorm_session.py` `finalize_session` (L337-367) still reads
`node_data.get("plan_file")` and copies the plan to `aiplans/`. **t891_4** owns
its replacement. Leave the function body alone. (After this task no node ever
gets a `plan_file`, so `finalize_session` will raise `ValueError` on every call —
acceptable: t891_4 is the next child and `ait brainstorm` is unshipped.)

## Removal inventory (locate by symbol; line numbers are as-landed 2026-06-11)

### `brainstorm_schemas.py`
- `NODE_OPTIONAL_FIELDS` (L20): drop `"plan_file"` → `["reference_files", "module_label"]`.
  (Note: this constant has **no consumers** anywhere — dead config — so the edit is
  trivially safe; keep the other two entries, out of scope.)

### `brainstorm_dag.py`
- `PLANS_DIR = "br_plans"` (L24) — remove.
- `read_plan` (L520-525) — remove (its only consumers are in `brainstorm_app.py`,
  all removed below; the crew consumer was already dropped by t891_2).
- Node-deletion closure cleanup (L305-314 snapshot block + L360-363): remove the
  `plan_files` snapshot loop and the `PLANS_DIR` unlink + custom-`pf` unlink; keep
  the `NODES_DIR` / `PROPOSALS_DIR` unlinks.
- Module docstring (L5): drop the `br_plans/` mention.

### `brainstorm_op_refs.py`
- Import `PLANS_DIR` (L13) — remove.
- `_VALID_KINDS` (L27-31): remove `"node_plan"` (no `OpDataRef("node_plan", …)`
  constructor exists anywhere — verified).
- `file_for_ref` `node_plan` branch (L54-55) — remove.

### `brainstorm_crew.py`  *(t891_2 "left for you")*
- Import `PLANS_DIR` (L32) — remove.
- `_assemble_input_explorer` plan-display block (L238-240): remove the
  `plan_file = session_path / PLANS_DIR / …` / `if plan_file.is_file(): lines.append("- Plan: …")`
  three lines.

### `brainstorm_session.py`
- Import `PLANS_DIR` (L29) — remove.
- Session dir creation (L100): drop `PLANS_DIR` from
  `for subdir in (NODES_DIR, PROPOSALS_DIR, PLANS_DIR):` → stop creating `br_plans/`.
- `_NODE_NON_DIMENSION_FIELDS` (L545-): drop `"plan_file"` (L547).
- Module docstrings (L7, L68): drop `br_plans/` mentions.
- **Leave `finalize_session` (L337-367) — t891_4.**

### `brainstorm_dag_display.py`
- `NO_PLAN_STYLE` (L54) — remove (only used by the badge, below).
- `_build_graph` (L91-133): drop `node_has_plan_map` (build + return); change the
  return annotation (L93) from 6-tuple to 5-tuple; update docstring (L96-102).
- `_render_node_box` (L220-306): drop the `has_plan` param (L227) and the ●/○ block
  (L268-271). `NODE_ROWS` stays 5 (the marker is inline in the title row).
- `_render_layer` (L309-): drop the `node_has_plan_map` param (L317), `plan_map`
  (L321), and the `has_plan=` kwarg to `_render_node_box` (L335).
- `Binding("l", "view_plan", "Plan", …)` (L473) — remove.
- `PlanRequested` message class (L513-518) — remove.
- `_node_has_plan_map` instance state (L545); its assignment in `load_dag`
  (L558 unpack + L565); and the `node_has_plan_map=` kwarg in the `_render_layer`
  call (L621) — remove (update the L558 unpacking to 5 names).
- `action_view_plan` (L840-845) — remove.

### `brainstorm_app.py`
- Import `read_plan` (L64) — remove.
- `reads_from_parent` help text **[NEW]** (L267): remove the
  `"Plan markdown of the base node (if one exists)."` line from the `explore` op help.
- **`NodeDetailModal`** (L1049-1278):
  - Drop `_plan_parsed` / `_plan_text` init (L1064-1065).
  - Drop the `TabPane("Plan", …)` block (L1085-1090) — modal docstring/comment
    (L1049, L1098) updated to "Metadata, Proposal".
  - Drop the `# --- Plan tab ---` population block (L1152-1167).
  - `on_section_minimap_section_selected` (L1181-1182): drop the `plan_minimap`
    branch.
  - `action_focus_minimap` (L1204-1205): drop the `tab_plan` branch.
  - `action_fullscreen_view` (L1227-1229): drop the `tab_plan` branch (keep
    proposal; the warning text becomes "only works on Proposal tab").
  - `action_export` (L1250, L1257-1259): drop `default_plan` + the `plan_text` /
    `default_plan` args passed to `ExportNodeDetailModal`.
- **Export modal subsystem [NEW]** (plan half):
  - `_export_filename` (L1305-1307): kind is now only `'proposal'` (drop the docstring
    `'or plan'`).
  - `_write_node_exports` (L1310-1332): drop `plan_text` / `do_plan` params and the
    `if do_plan:` write branch.
  - `ExportNodeDetailModal` (L1335-1421): drop `plan_text` / `default_plan` params,
    `_plan_text` / `_default_plan` state, the Plan `Checkbox` (L1379-1384), the
    `do_plan` read + "at least one" guard wording (L1400-1402), and the `do_plan`
    arg to `_write_node_exports` (L1409-1417). Modal subtitle/labels → proposal-only.
- **`NodeRow`** (L2138-): drop `has_plan` param (L2153, L2158) and the `plan_marker`
  in `render` (L2163-2167).
- **`NodeActionSelectModal`**: drop `has_plan` param + `self.has_plan` (L2334, L2337)
  — verified the value is **never read** (t891_2 left it dangling).
- `action_node_action` (L4070-4073): drop `has_plan = self._node_has_plan(node_id)`
  and the `has_plan` positional arg to `NodeActionSelectModal(node_id, has_plan, op_states)`.
- Dashboard node-row build (L5825-5829): drop `has_plan = bool(node_data.get("plan_file"))`
  and the `has_plan=` kwarg to `NodeRow`.
- `PlanRequested` handler `on_dag_display_plan_requested` (L6047-6064) — remove.
- Wizard node-select badge (L6502-6516): drop the `has_plan` read + the
  `● has plan` / `○ no plan` `lbl_parts` branch; keep `nid` + `HEAD`.
- `_node_sections` (L7094-7110) **[NEW]**: drop the `read_plan` "plan preferred"
  branch (L7096-7103) → proposal-only. Docstring → "proposal sections". (Callers
  L6546/L6556/L6863 feed the t873 section-select wizard — behavior preserved via the
  proposal fallback.)
- `_node_has_plan` (L7116-7122) — remove (only caller was L4070, removed above; the
  patch-wizard gate the snapshot named is already gone — t891_2).

## Must preserve
- Node metadata + proposal model, dimensions, **t873 section markers / dimension
  links**, the surviving node-detail tabs (Metadata, Proposal) + their minimap, the
  proposal export path, and the `explore`/`compare`/`synthesize`/module bindings.
- The shared `_node_sections`/`_node_has_sections` section machinery (now
  proposal-only) — used by the section-select wizard step.

## Implementation order
1. Data sources first: `schemas.py` field, `dag.py` (`PLANS_DIR`/`read_plan`/delete
   cleanup), `op_refs.py` (`node_plan`/import), `crew.py` (import + explorer line),
   `session.py` (import + L100 dir-create + `_NODE_NON_DIMENSION_FIELDS` + docstrings).
2. `dag_display.py`: `_build_graph` map → `_render_node_box`/`_render_layer` params →
   badge + `NO_PLAN_STYLE` → `l`/`view_plan` binding + `PlanRequested` + `action_view_plan`
   → `_node_has_plan_map` state/wiring.
3. `brainstorm_app.py`: `read_plan` import → NodeDetailModal Plan tab + minimap +
   fullscreen/focus/export branches → export-modal plan half → NodeRow/NodeActionSelectModal
   → `action_node_action`/dashboard/wizard badges → `PlanRequested` handler →
   `_node_sections` plan branch → `_node_has_plan`.
4. Tests (next section).
5. grep sweep + AST-parse; clean dead imports.

## Tests (inspect & update — keep proposal assertions, drop plan ones)
All are **mixed** proposal+plan tests → **update in place** (no whole-file deletions;
no test is plan-only):
- `test_brainstorm_op_refs.py` — drop `node_plan` kind assertions.
- `test_brainstorm_dag.py` — drop `read_plan`/`PLANS_DIR`/`br_plans` cases.
- `test_brainstorm_node_delete.py` — drop `br_plans` from the deleted-dirs fixture/asserts.
- `test_brainstorm_crew.py` — drop the explorer `- Plan:` line assertion.
- `test_brainstorm_dag_op_badge.py` — drop the `br_plans` fixture mkdir; the
  five-rows / blank-badge tests stay (NODE_ROWS unchanged).
- `test_brainstorm_dag_op_keybinding.py` — drop any `view_plan`/`l` case (the file's
  visible tests are `o`-key; confirm during edit).
- `test_brainstorm_node_detail_minimap.py` — drop `plan` from `_make_session`, the
  `br_plans` write, and the `#plan_content`/`#plan_pane` assertions; keep proposal.
- `test_brainstorm_node_action_modal.py` / `test_brainstorm_node_action_relevance.py`
  — drop `has_plan` constructor arg + plan-marker assertions.
- `test_brainstorm_node_export.py` — drop plan checkbox / `do_plan` / plan-file
  assertions; keep proposal export.
- `test_brainstorm_wizard_sections.py` — `_node_sections` now proposal-only; drop the
  plan-preferred case, keep proposal-section coverage.
- `test_brainstorm_groups_persist.py` — single `has_plan` hit; confirm incidental
  (likely a NodeRow construction) and update if needed.
- `test_brainstorm_cli.sh` / `test_brainstorm_cli_python.py` — confirm `plan` hits are
  not finalize-export (t891_4) before touching; otherwise leave.

## Verification
- `grep -rn "plan_file\|read_plan\|PLANS_DIR\|br_plans\|node_has_plan\|view_plan\|PlanRequested\|has_plan\|node_plan" .aitask-scripts/brainstorm/`
  returns only the intentionally-retained `finalize_session` `plan_file` reads
  (t891_4) — nothing else live.
- AST-parse: `python -c "import ast,glob;[ast.parse(open(f).read()) for f in glob.glob('.aitask-scripts/brainstorm/*.py')]"` clean.
- Run the updated/kept brainstorm tests (the list above + `test_brainstorm_node_export.py`,
  `test_brainstorm_node_detail_minimap.py`) — all pass.
- Manual `ait brainstorm <n>`: node-detail modal has only Metadata + Proposal tabs;
  no ●/○ plan badges in the DAG; `l` unbound; node-action / node-select rows show no
  plan marker; export modal offers Proposal only; opening a previously-`plan_file`
  node does not error.

## Risk

### Code-health risk: medium
- Wide multi-site deletion across the brainstorm subsystem (7 `.py` files + ~11 test
  files). A naive grep-and-delete would (a) strip the shared proposal/section
  (`_node_sections`) or t873 machinery caught as a `plan`/`has_plan` false-positive,
  or (b) break the `_render_node_box` row count, or (c) touch `finalize_session`
  (t891_4's boundary). · severity: medium · → mitigation: in-task (per-symbol KEEP
  markers above; proposal-fallback preserved in `_node_sections`; AST-parse + targeted
  grep sweep before done; run kept brainstorm tests).
- Removing a symbol while leaving a dangling reference (e.g. the `_build_graph`
  5-tuple unpack, an import, or a `PLanRequested` `@on` handler) yields an
  ImportError / unpacking error only hit at runtime. · severity: low · → mitigation:
  in-task (AST-parse all brainstorm `.py`; grep each removed symbol for residual refs;
  launch `ait brainstorm` manually).

### Goal-achievement risk: low
- None identified. Scope is a bounded, well-mapped removal confined to `brainstorm/`
  + its tests (no external importers of `PLANS_DIR`/`read_plan`); the sibling boundary
  with t891_4 is explicit.

See **Step 9 (Post-Implementation)** of the shared workflow for archival
(`./.aitask-scripts/aitask_archive.sh 891_3`).

## Final Implementation Notes

- **Actual work done:** Removed the plan data model + plan TUI surfaces end-to-end
  (net ~308 lines across 7 source + 16 test files). Source: `brainstorm_schemas.py`
  (`plan_file` out of `NODE_OPTIONAL_FIELDS`), `brainstorm_dag.py` (`PLANS_DIR`,
  `read_plan`, the node-delete closure plan snapshot + `br_plans` unlink, docstring),
  `brainstorm_op_refs.py` (`node_plan` kind + branch + `PLANS_DIR` import),
  `brainstorm_crew.py` (`PLANS_DIR` import + explorer `- Plan:` line),
  `brainstorm_session.py` (`PLANS_DIR` import, `br_plans/` dir creation at the
  subdir-create loop, `plan_file` from `_NODE_NON_DIMENSION_FIELDS`, two docstrings),
  `brainstorm_dag_display.py` (`NO_PLAN_STYLE`, `node_has_plan_map` build/return → 5-tuple,
  `_render_node_box` `has_plan` param + ●/○ block, `_render_layer` param, `l`/`view_plan`
  binding, `PlanRequested` message, `_node_has_plan_map` state + wiring, `action_view_plan`),
  `brainstorm_app.py` (`read_plan` import; NodeDetail **Plan tab** + minimap + the
  fullscreen/focus/section-selected/export plan branches; the **ExportNodeDetailModal**
  plan half incl. `_write_node_exports`/`_export_filename`/`action_export`; `NodeRow`
  plan marker; `NodeActionSelectModal` dead `has_plan`; `action_node_action` /
  dashboard / wizard node-select badges; `PlanRequested` `@on` handler; `_node_sections`
  → proposal-only; `_node_has_plan` removed; the explorer `reads_from_parent` /
  `_OPERATION_HELP` plan help text).
- **Deviations from plan:** The as-landed surface was materially larger than the
  2026-06-01 snapshot. Areas the snapshot missed and that were handled here:
  (1) the entire **ExportNodeDetailModal** plan-export path (`Shift+E` export) —
  params, checkbox, `do_plan`/`plan_text` plumbing, `_write_node_exports` branch,
  `_export_filename` 'plan' kind; (2) `_node_sections` "plan preferred, else proposal"
  → proposal-only (feeds the t873 section-select wizard, behavior preserved via the
  proposal fallback); (3) the explorer `reads_from_parent` help text + the
  `_OPERATION_HELP` source comment. Also cleaned two vestigial `br_plans` mkdirs in
  tests the symbol-grep flagged (`test_brainstorm_dag_click_focus.py`,
  `test_brainstorm_apply_created_by_group.sh`). Two test-side `_build_graph` 6-tuple
  unpacks and two extra `_make_session(plan=...)` callers were missed on the first
  pass and fixed after the suite flagged them.
- **Issues encountered:** None blocking. The `_build_graph` arity change (6→5 tuple)
  rippled into `test_brainstorm_dag_op_badge.py`'s unpacks; the suite caught it
  immediately. Verified `_render_node_box` still emits NODE_ROWS=5 (the ●/○ was inline
  in the title row, not its own row).
- **Key decisions:** Left `finalize_session` (`brainstorm_session.py`) and its
  `plan_file` reads **untouched** — that is t891_4's boundary. Consequently the two
  finalize-dependent tests (`test_brainstorm_dag.py::test_finalize_copies_plan`,
  `test_brainstorm_cli_python.py::test_archive_sets_crew_status`) were kept passing by
  inlining the `"br_plans"` literal (since the store is no longer auto-created) and
  explicitly `mkdir`-ing it — both carry a NOTE that t891_4 owns their rewrite. All
  other plan tests were updated in place to proposal-only; none were deleted wholesale
  (no test was plan-only).
- **Upstream defects identified:** None.
- **Notes for sibling tasks (t891_4 — finalize replacement / proposal export):**
  - `finalize_session` (`brainstorm_session.py` ~L337-367) is the **only** remaining
    live `plan_file` consumer in `.aitask-scripts/brainstorm/`. After t891_3, no node
    is ever written with a `plan_file`, so `finalize_session` now raises
    `ValueError("HEAD node '<head>' has no plan_file.")` on **every** call — replace it
    per your plan (proposal export or fast-track-ownership).
    `PLANS_DIR`/`read_plan`/`br_plans` are gone, so finalize must not reference them.
  - Two tests still scaffold a `br_plans/` dir + `plan_file` purely to exercise the
    legacy finalize copy: `test_brainstorm_dag.py::test_finalize_copies_plan` and
    `test_brainstorm_cli_python.py::TestArchiveCommand::test_archive_sets_crew_status`
    (both use the inlined `"br_plans"` literal + a NOTE). Rewrite/retire them when you
    change finalize. `test_brainstorm_cli.sh` Test 11 ("archive handles no-plan HEAD
    gracefully", asserts `NO_PLAN` + `ARCHIVED`) still passes and may need updating
    depending on the new finalize semantics.
  - The kept `_node_sections`/`_node_has_sections` (now proposal-only) and the t873
    section machinery are not yours to touch.
