---
Task: t983_4_operations_dialog_cardinality.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_4_operations_dialog_cardinality
Branch: aitask/t983_4_operations_dialog_cardinality
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-16 10:58
---

# p983_4 — Operations dialog (cardinality-driven)

Child of t983. Unify the two op entry points (Actions-tab wizard op list + the
`A` `NodeActionSelectModal`) into ONE contextual **Operations** dialog whose op
rows grey by **selection cardinality** (t983_2 `NodeSelection`). Lands before
the Node Hub (t983_5) so the Hub can open it; the seeded-wizard re-host is
t983_6 and the compare overlay / drop-Compare-tab is t983_7.

## Context

Verify-pass re-check of the pre-t983_3 plan against the current
`.aitask-scripts/brainstorm/brainstorm_app.py` (8095 lines). t983_1/2/3 have all
landed; the original line refs and one instruction are **stale**:

- `NodeActionSelectModal` is now `:2470` (was :2235); `_node_action_op_states`
  `:4214` (was :3939); `action_node_action` `:4246`; `_on_node_action_result`
  `:4329`; `action_op_help` `:4574`; `OperationHelpModal` `:1697`;
  `_OP_LABELS`/`_DESIGN_OPS`/`_OPERATION_HELP` at `:239`/`:219`/`:251`.
- **`NodeSelection` is already wired in** by t983_3: `self._selection`
  (`:3684`), driven by the `space`-mark path (`action_browse_mark` `:4202`),
  cursor sync in `_show_browse_node_detail`, and `remove()` on node deletion.
  So `self._selection.cardinality` / `.effective()` / `.primary` are available
  to this task — no new selection plumbing needed.
- **`action_node_action` already gates on `tab_browse`** (`:4256`), not
  `tab_actions`. The plan's "repoint the `tab_actions` gate" instruction is
  **wrong for this task**: the Actions, Compare, and Status tabs *still exist*
  (their removal is t983_6 wizard re-host / t983_7 compare overlay / t983_8
  Session split). The `action_op_help` `tab_actions` gate (`:4582`) correctly
  still serves the **wizard**, which is untouched here.
- **compare/synthesize do not use the wizard node-select step**
  (`_NODE_SELECT_OPS = {"explore"}`, `:158`); `compare` launches via its own
  `CompareNodeSelectModal` + `tab_compare` (`_open_compare_select_modal`
  `:4515`, `action_tab_compare` `:4525`).

The current `NodeActionSelectModal` (`:2470`) already implements exactly the
pattern this task extends: an `_OPS` list, an `op_states[op_key] =
(disabled, reason)` map computed by the caller, and `OperationRow`
disabled-with-reason rendering. `_node_action_op_states` (`:4214`) is an
instance method doing session I/O inline — this task makes its decision logic
**pure**.

## Goal

Extend `NodeActionSelectModal` → the contextual **Operations** dialog: list the
design ops **and** the multi-node ops (compare/synthesize), greyed by selection
cardinality, with the op-list descriptions and `_OPERATION_HELP` discoverability
preserved. Make the enable/disable decision a **pure, headless function**
(testability-first, mirroring t983_2 `NodeSelection` and the wizard-step model).

**Scope decision (user-confirmed):** the cardinality-greying + op listing land
now; the **launch-seeding** of compare/synthesize from the dialog (pre-filling
the marked set into their flows) is **deferred to t983_6 (wizard re-host) /
t983_7 (compare overlay)** — the siblings that rewrite those flows. Choosing a
multi-node op from the dialog this task routes to its **existing entry point
unchanged**. This is the lowest-blast-radius path and avoids reworking flows
t983_6/7 will rewrite anyway. Recorded here so the AC narrowing is explicit.

## Design decisions (with trade-offs)

1. **Pure module-level `op_states_for_selection(node_ctx, cardinality)`** —
   placed beside the other I/O-free models (wizard-step helpers / `NodeSelection`,
   ~`:1800-1955`). Signature: `node_ctx` is a plain dict of the per-node facts
   the module-op preconditions need — `{"is_umbrella": bool, "has_ancestor":
   bool, "has_linked_task": bool}` — and `cardinality` is the effective
   selection size. Returns `{op_key: (disabled, reason)}` for **every op in the
   dialog**. No Textual, no session I/O — exhaustively unit-testable like
   `NodeSelection`. Greying rules:
   - **single-node ops** (`explore`, `fast_track`, `delete`): disabled when
     `cardinality > 1`, reason `"select a single node"`.
   - **module ops** (`module_decompose`/`merge`/`sync`): disabled when
     `cardinality > 1` (reason `"select a single node"`) **or** their existing
     precondition is unmet (umbrella / no-ancestor / no-linked-task) — the
     cardinality reason takes precedence when both apply.
   - **multi-node ops** (`compare`, `synthesize`): disabled when
     `cardinality < 2`, reason `"mark 2+ nodes"`.
   *Rejected:* keeping the logic inside the App method — it is the exact thing
   the task asks to make pure and is the testability centerpiece.

2. **`_node_action_op_states(self, node_id, cardinality)` becomes a thin I/O
   wrapper.** It does only the session reads it does today (`_node_module`,
   `_read_graph_state`, `_ancestor_subgraphs` → the three `node_ctx` booleans
   for the **primary** node) and delegates the decision to
   `op_states_for_selection(node_ctx, cardinality)`. Module preconditions are
   computed from the primary node; when `cardinality > 1` the module ops are
   greyed by cardinality regardless, so the primary's `node_ctx` is the correct
   single source. *Trade-off:* the wrapper gains a `cardinality` param.
   **Verified single caller** — `grep -n _node_action_op_states` returns exactly
   the def (`:4214`) and one call in `action_node_action` (`:4284`); no event
   binding or second consumer inherits the new behavior unawares.

3. **Operations dialog = the extended `NodeActionSelectModal`.** Add `compare`
   and `synthesize` to `_OPS` (`:2491`) so the dialog lists the full op set;
   labels/descriptions come from the existing `_OP_LABELS` (compare/synthesize
   are in `_DESIGN_OPS`, `:221-222`) via the existing `_LOCAL_LABELS`/`_OP_LABELS`
   lookup in `compose` — no new rendering. Relabel the dialog title from
   "Operate on node X" toward "Operations" while still naming the contextual
   target (primary node id, or "N nodes" when a marked set drives it). This is
   the "fold in the Actions-tab op list with descriptions": the dialog now shows
   the same `_DESIGN_OPS` rows the wizard's `op_select` step shows. *Note:* the
   wizard's physical `op_select` step is NOT removed here (that is the t983_6
   re-host) — the dialog supersedes it as the **entry point** only.

4. **`action_node_action` drives cardinality** (`:4246`). Compute `cardinality =
   self._selection.cardinality` and pass it to
   `_node_action_op_states(node_id, cardinality)`; `node_id` stays the primary
   cursor node (`self._current_focused_node_id`, kept in sync with
   `self._selection.primary` by t983_3). Pass the selection context the modal
   needs to render its title. No change to the `tab_browse` gate or the
   read-only / status guards.

5. **Preserve `_OPERATION_HELP` discoverability from the dialog via an in-modal
   `H` binding.** Add `Binding("H", "op_help", "Help")` (or lowercase per the
   wizard's binding) to `NodeActionSelectModal.BINDINGS` (`:2482`) plus an
   `action_op_help` on the modal that pushes `OperationHelpModal(focused.op_key)`
   for the focused `OperationRow`. **No-help fallback (closes the UX hole):**
   `fast_track` and `delete` have no `_OPERATION_HELP` entry; rather than a
   silent SkipAction, the modal's `action_op_help` calls
   `self.app.notify("No help available for this operation.", severity="information")`
   so `H` always gives feedback. *This is the scope-honest replacement for the
   stale "repoint the tab_actions gate":* the wizard's app-level `action_op_help`
   stays gated to `tab_actions` (the wizard still lives there), so the dialog
   gets its **own** parallel help path rather than repointing the wizard's.
   *Trade-off:* two op-help entry points coexist until t983_6 re-hosts the wizard
   and unifies them — recorded as a sibling note, not a new task (t983_6 already
   owns that reconciliation).

6. **Launch routing (`_on_node_action_result`, `:4329`) — selection wired
   through, no re-host. (Verified-safe routing — corrects a plan bug.)**
   **Verified:** compare/synthesize do NOT use the wizard node-select step
   (`_NODE_SELECT_OPS = {"explore"}`); they pick their source nodes *inside the
   config step* via a `FuzzyCheckList` — `syn_nodes` (`:4786`) / `cmp_nodes`
   (`:4795`) — so a "seedless" launch is their **normal** state, not an error.
   Therefore route them through the **same branch the module ops already use**
   (`:4366`): `self._wizard_op = op_key; self._set_total_steps();
   self._actions_show_config(); self.call_after_refresh(self._enter_actions_tab)`.
   `_actions_show_config` renders the (empty) node checklist; the user picks
   there. **Do NOT** route them through the generic `:4378` branch — it calls
   `_actions_show_node_select()`, which is explore-only and would mis-drive these
   ops. The dialog op `compare` maps to the **comparator agent op** (its
   `_OPERATION_HELP` "Compare — Tradeoff Analyst", the `cmp_nodes` config /
   `register_comparator` path) — **not** the `tab_compare` dimension matrix
   (`_open_compare_select_modal`, `:4515`), which is a separate tool t983_7
   reconciles. Stated explicitly so the choice is not silent. No pre-checking of
   the marked set — that seeding is t983_6/t983_7. *Rejected:* pre-seeding
   `self._selection.effective()` into the config checklist now — more wiring into
   flows t983_6/7 rewrite anyway.

7. **Explicit marked-node listing in BOTH the dialog and the Browse screen
   (user-requested).** Today marks are shown only as a per-row yellow `●` glyph
   in *list* view (`NodeRow.marked`, `:2202` / `_refresh_node_marks`, `:4169`);
   *graph* view shows nothing (t1004) and no view prints the marked node **names**.
   Add an explicit textual list in two places, both fed by the single source
   `self._selection`:
   - **Operations dialog:** a selection-summary `Label` under the title listing
     the **effective target set** — `self._selection.effective()` — e.g.
     `Targets (3): n012, n034, n056` (or the lone primary when nothing is
     marked). Makes the cardinality greying concrete (this is what
     compare/synthesize will act on). The modal already receives the data it
     needs once step 5 threads the selection in. **Overflow-safe render
     (closes the modal-height hole):** the summary sits *outside* the inner
     `VerticalScroll#node_action_list` and the dialog is `height: auto;
     max-height: 90%` (`#node_action_dialog`, `:3125`), so an unbounded
     comma-line could push the op list. Cap the displayed names (first ~5) with a
     `(+K more)` suffix — e.g. `Targets (12): n001, n002, n003, n004, n005 (+7
     more)` — bounding the label to ≤2 lines regardless of set size.
   - **Browse screen:** a `#browse_marked_info` `Label` in the shared
     `#browse_detail_pane` `VerticalScroll` (alongside `#session_status_info` /
     `#module_status_info`, above `#browse_node_panel`) listing the marked node
     names. **Verified:** `#browse_detail_pane` is a **persistent sibling of the
     `#browse_switcher` ContentSwitcher** (`:3783-3795`, commented "survives `v`
     toggles"), so the label shows in **both** list and graph views — covering
     the graph-view glyph gap until t1004. It is itself a `VerticalScroll`, so
     this label may wrap freely (the pane scrolls); empty/`None` when nothing is
     marked. Use the same `(+K more)` cap for visual consistency with the dialog.
   - **Single-effect-per-method (closes the hidden-second-effect concern):** do
     NOT overload `_refresh_node_marks` (`:4169`, which sets per-row glyphs).
     Extract the summary update into a dedicated `_refresh_marked_summary()` that
     renders `#browse_marked_info` from `self._selection.marked`, and call it from
     `_refresh_node_marks` with an inline comment ("glyphs + textual summary").
     Future glyph edits see one clearly-named companion call, not a buried side
     effect.
   *Trade-off:* one new label + one CSS rule + a small render helper; additive,
   no new state (derives entirely from `self._selection`, honoring the
   single-source rule).

## Implementation steps (all in `.aitask-scripts/brainstorm/brainstorm_app.py` unless noted)

1. **Pure function.** Add module-level `op_states_for_selection(node_ctx,
   cardinality)` near the wizard-step / `NodeSelection` models (~`:1955`,
   before the modal classes), implementing the three greying rules in Design §1.
2. **Wrapper.** Refactor `_node_action_op_states` (`:4214`) to build `node_ctx`
   from the existing I/O (`is_umbrella`, `has_ancestor` via `_ancestor_subgraphs`,
   `has_linked_task` via `_read_graph_state`/`module_tasks`) and `return
   op_states_for_selection(node_ctx, cardinality)`. Add the `cardinality` param.
3. **Modal op list.** Add `"compare"`, `"synthesize"` to `_OPS` (`:2491`) in the
   contextual order from the parent design (explore · compare · synthesize ·
   module_* · fast_track · delete). Relabel `#node_action_title` (`:2517`) to
   "Operations" naming the contextual target.
4. **`H` help in the modal.** Add the binding + `action_op_help` to
   `NodeActionSelectModal` pushing `OperationHelpModal(focused.op_key)`.
5. **Cardinality wiring.** In `action_node_action` (`:4246`) compute
   `cardinality = self._selection.cardinality` and pass it to the wrapper; thread
   the selection context into the modal title.
6. **Launch routing.** In `_on_node_action_result` (`:4329`) add a `compare` /
   `synthesize` branch using the **module-op pattern** (`_actions_show_config` +
   `_enter_actions_tab`), NOT the generic node-select branch (Design §6).
7. **Dialog target list.** Add the selection-summary `Label` to
   `NodeActionSelectModal.compose` (under `#node_action_title`, `:2516`)
   rendering the capped `(+K more)` form of `self._selection.effective()` passed
   in via step 5.
8. **Browse marked list.** Add `#browse_marked_info` `Label` to the
   `#browse_detail_pane` compose block (`:3783`), populate it from a new
   `_refresh_marked_summary()` helper called by `_refresh_node_marks` (`:4169`),
   and add a CSS rule mirroring the existing `#session_status_info` /
   `#module_status_info` style.

## Verification

- **Pure unit** (`tests/test_brainstorm_node_action_relevance.py`, extend):
  retarget the cardinality logic onto `op_states_for_selection(node_ctx,
  cardinality)` directly — exhaustive cases: cardinality 1 leaves single-node
  ops enabled and greys compare/synthesize ("mark 2+ nodes"); cardinality ≥ 2
  greys explore/fast_track/delete/module_* ("select a single node") and enables
  compare/synthesize; module-op preconditions (umbrella / no-ancestor /
  no-linked-task) still grey at cardinality 1 with their own reasons; the
  cardinality reason wins when both apply. Keep ≥1 wrapper test that the I/O
  `_node_action_op_states` maps a synthetic session → the right `node_ctx`
  (umbrella/ancestor/linked-task), now passing an explicit `cardinality`.
- **Pilot** (`tests/test_brainstorm_node_action_modal.py`, update): the
  `_OPS`-order assertion (`:88-92`) now includes compare/synthesize; a marked-set
  `op_states` greys compare/synthesize vs single-node ops; `H` on a focused
  help-bearing row pushes `OperationHelpModal`, and `H` on `fast_track`/`delete`
  fires the "No help available" notify (no crash, no silent no-op). Update
  `OnNodeActionResultTests` to assert the compare/synthesize branch calls
  `_actions_show_config` (NOT `_actions_show_node_select`) — guarding the
  seedless-launch safety directly.
- **Cardinality roundtrip** (pure + pilot): unit-assert that
  `op_states_for_selection` flips correctly across a mark→unmark cycle
  (cardinality 1 → 2 → 1) — single-node ops re-enable and compare/synthesize
  re-grey; pilot-assert the same dynamic transition through `action_browse_mark`
  toggling, exercising the reactive plumbing the static cases miss.
- **Marked-list rendering** (pilot, in the modal + Browse test files): the
  dialog summary lists `effective()` node ids and updates with the marked set;
  `_refresh_node_marks` populates `#browse_marked_info` with the marked names and
  clears it when the set empties (assert in both list and graph views, since the
  detail pane is shared).
- **Suite:** `bash tests/run_all_python_tests.sh` (`tests/test_brainstorm*.py`,
  36 files) green.
- **Manual:** `ait brainstorm <session>` → Browse → `A` opens **Operations**;
  with one node focused, compare/synthesize are greyed ("mark 2+ nodes") and
  single-node ops enabled; `space`-mark a second node → the Browse
  `#browse_marked_info` lists both names (verify in list AND graph view); `A`
  again → dialog shows `Targets (2): …`, single-node ops grey ("select a single
  node"), compare/synthesize enabled; **then unmark the second node and re-open
  `A`** → single-node ops re-enable and compare/synthesize re-grey (roundtrip);
  `H` on explore opens its help, `H` on delete shows "No help available";
  choosing compare/synthesize lands in the Actions config step with its node
  checklist (no crash).

## Risk

### Code-health risk: medium
- The dialog gains its own `H` op-help path while the wizard keeps its
  `action_op_help` (`:4582`, gated to `tab_actions`); two op-help entry points
  coexist until the wizard is re-hosted. · severity: low · → mitigation: t983_6
  (existing sibling — wizard re-host unifies the op-help path; no new task)
- Cardinality plumbing threads through `action_node_action` →
  `_node_action_op_states` → the pure fn; a future caller that forgets the new
  `cardinality` arg would mis-grey. Bounded: **verified single caller** (grep:
  def `:4214`, call `:4284`), and the pure fn is exhaustively unit-tested. ·
  severity: low · → mitigation: covered by the pure + pilot tests in-scope
- compare/synthesize launch routing is easy to get wrong (the explore-only
  generic branch vs the module-op config branch). · severity: low · →
  mitigation: routing **verified** against the `syn_nodes`/`cmp_nodes` config
  flow (Design §6) and asserted by an `OnNodeActionResultTests` case that the
  branch calls `_actions_show_config`, not `_actions_show_node_select`
- `_refresh_node_marks` acquiring a second effect (glyphs + summary) is hidden
  from future editors. · severity: low · → mitigation: summary extracted into a
  named `_refresh_marked_summary()` helper with an inline call-site comment
  (Design §7), so the second effect is explicit rather than buried

### Goal-achievement risk: low
- Approach is the parent-mandated one (pure op_states + extended modal,
  mirroring the proven `NodeSelection`/wizard-step models) and every
  prerequisite (`self._selection`, the `op_states`/`OperationRow` pattern,
  `_OPERATION_HELP`) is verified present. The one scope narrowing — deferring
  compare/synthesize launch-seeding to t983_6/t983_7 — is explicit and
  user-confirmed. · severity: low · → mitigation: n/a
- None other identified.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_4`.
