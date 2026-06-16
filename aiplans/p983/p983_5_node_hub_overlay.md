---
Task: t983_5_node_hub_overlay.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_5_node_hub_overlay
Branch: aitask/t983_5_node_hub_overlay
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-16 12:37
---

# p983_5 — Node Hub overlay (Enter)

Child of t983 (brainstorm-TUI IA redesign). `Enter` on the cursor node opens a
**Node Hub**: the shared Detail surface (`NodeDetailPanel` from t983_1, plus the
Proposal tab + minimap) **and** an **Operations** entry that opens the t983_4
Operations dialog contextual to the current selection. This unifies the
node-detail entry points and gives the wizard re-host (t983_6) and Compare
overlay (t983_7) a second launch surface besides `A`.

## Context

The target IA (parent t983) routes node detail through ONE overlay reachable by
`Enter`, and folds the two op entry points behind the contextual **Operations**
dialog. Today (verified against the current 8275-line
`.aitask-scripts/brainstorm/brainstorm_app.py`):

- `Enter` opens `NodeDetailModal` from **two** sites: the list-view binding
  `action_open_node_detail` (`:4279`, `self.push_screen(NodeDetailModal(...))` at
  `:4290`) and the graph-view handler `on_dag_display_node_selected`
  (`:6308`, push at `:6311`).
- `NodeDetailModal` (`:1050`) is already the shared Detail surface: a Metadata
  tab hosting `NodeDetailPanel` (t983_1) + a Proposal tab with the section
  minimap, plus `v` fullscreen / `e` export / `tab` minimap bindings. Its only
  button is **Close** (`#btn_close_detail`, `:1090`), dismissing `None`
  (`close_detail` `:1219`, `action_close` `:1223`).
- `A` (`Binding("A", "node_action", ...)` `:3738`) → `action_node_action`
  (`:4405`) opens the **Operations** dialog `NodeActionSelectModal` (the t983_4
  cardinality-driven dialog). It runs guards (modal-active, `tab_browse`,
  focused node, read-only, session status, node-exists), then computes
  `cardinality` / `op_states` / `targets` and pushes the modal with the
  `_on_node_action_result` callback (`:4492`).

**Stale refs corrected from the task stub:** the stub cited `:3914`
(`action_open_node_detail`), `:5942` (graph `NodeDetailModal` path), `:1047`
(`NodeDetailModal`). t983_4 shifted these to `:4279`, `:6308/:6311`, `:1050`
respectively. The approach is unchanged; only line numbers moved.

## Goal

Unify the node-detail entry points behind one **Node Hub** overlay opened by
`Enter`, with an Operations entry that launches the existing t983_4 Operations
dialog seeded from the current selection. No auto-open on cursor movement.

**Why a Hub rather than making `Enter` open Operations directly (intended
two-trigger design, not a regression):** the parent t983 "Confirmed design
decisions" set `Enter → Node Hub (Detail)` and `A → Operations dialog` as
**two distinct triggers**. `A` stays the one-keystroke path to Operations for
power users; the Hub's Operations entry is a *second* launch surface (and the
discoverable one for new users who reach Operations via the Detail overlay).
This child also lays the surface that t983_6 (wizard re-host) and t983_7
(Compare overlay) plug into besides `A`. So the Hub adding a step to Operations
is by design — `A` is unchanged.

## Design decisions (with trade-offs)

1. **`NodeHub(NodeDetailModal)` subclass — reuse the whole Detail surface.**
   `NodeDetailModal` already *is* the Detail tab the parent migration map calls
   for ("`NodeDetailModal` (Enter) → Node Hub ▸ Detail"). Subclassing inherits
   the Metadata `NodeDetailPanel`, Proposal tab, minimap, fullscreen, and export
   verbatim — the Hub adds only an **Operations entry**. `NodeDetailModal` stays
   defined (its three existing test files —
   `test_brainstorm_node_detail_minimap.py`, `test_brainstorm_node_export.py`,
   `test_brainstorm_node_detail_panel.py` — all construct it **directly** on a
   bare host, none via the app `Enter` binding, so they stay green).
   *Rejected — rename `NodeDetailModal` → `NodeHub`:* matches the migration map
   literally but churns 3 test files + internal comments and risks the t983_1
   modal-fold guard; no benefit over subclassing.
   *Rejected — standalone `NodeHub` wrapping `NodeDetailModal`:* nested
   ModalScreens are awkward in Textual and would force extracting the whole
   Detail compose/on_mount into shared helpers — more churn than a subclass.

2. **Inject the Operations entry via two tiny overridable hooks on
   `NodeDetailModal`,** keeping its rendered output byte-identical:
   - `_dialog_title_text()` → returns `f"Node Detail: {self.node_id}"` today;
     `NodeHub` overrides it to `f"Node Hub: {self.node_id}"`.
   - `_dialog_buttons()` → a generator yielding the Close `Button`; `NodeHub`
     overrides it to yield an **Operations** `Button` (`#btn_node_hub_ops`,
     `variant="primary"`) followed by Close.
   `NodeDetailModal.compose` is refactored to call these hooks instead of inlining
   the title string and the button. This avoids duplicating the ~25-line
   compose body in the subclass. *Trade-off:* two small indirections in the base
   class; both return the current literals so base behavior is unchanged.

3. **Typed Hub→app dismiss protocol (not a bare string convention).** The Hub
   dismisses with `None` (closed) **or** a small typed result so the contract is
   visible and extensible — t983_6/t983_7 will add launch verbs here. Define,
   beside `NodeHub`:
   ```python
   NODE_HUB_OPERATIONS = "operations"   # add NODE_HUB_* verbs as launch surfaces grow

   class NodeHubResult(NamedTuple):
       """Result a NodeHub dismisses with. `action` is one of the NODE_HUB_*
       verbs; `node_id` is the Hub's node. Extending the Hub as a launch
       surface (t983_6 wizard re-host, t983_7 Compare overlay) = add a verb +
       a branch in BrainstormApp._on_node_hub_result."""
       action: str
       node_id: str
   ```
   (`NamedTuple` is already imported via `from typing import ...`; verified
   below.) This addresses the "untyped `result[0]`" fragility directly.

4. **In-modal `a` binding + button both launch Operations.** `NodeHub` adds
   `Binding("a", "operations", "Operations")`. **Verified no collision:** the
   only `a` binding anywhere is app-level (`Binding("a", "tab_actions",
   show=False)` `:3733`), which a focused `ModalScreen` shadows — exactly as the
   existing modal-local `v`/`e`/`tab` already shadow their app-level namesakes
   (proven pattern, no new mechanism); no widget composed inside the Hub
   (`NodeDetailPanel`/`DimensionRow`/`SectionMinimap`/`Button`) binds `a`.
   `action_operations` and the `#btn_node_hub_ops` `Button.Pressed` handler both
   `self.dismiss(NodeHubResult(NODE_HUB_OPERATIONS, self.node_id))`. The
   app-level `A` (`action_node_action`) is already a no-op while a `ModalScreen`
   is active (`if isinstance(self.screen, ModalScreen): return`, `:4412`), so
   there is no double-trigger.

5. **Extract `_open_operations_dialog(node_id)` from `action_node_action`** so the
   `A` keybinding and the Hub callback share one launch path (derive-don't-
   duplicate). The helper holds the post-tab guards (read-only, session status,
   node-exists) + `cardinality`/`op_states`/`targets` computation + the
   `push_screen(NodeActionSelectModal(...), _on_node_action_result)` call.
   `action_node_action` keeps the keybinding-context guards (modal-active,
   `tab_browse`, resolve `node_id = self._current_focused_node_id` + the
   **preserved "Focus a node first" warning** for an empty cursor) then
   delegates. The Hub's own `Enter`-open path never passes a `None` node
   (`action_open_node_detail` pushes the Hub only for a focused `NodeRow`;
   graph `NodeSelected` carries a concrete `focused_id`).
   **Cursor-anchor invariant (closes the selection-sync window):** the helper
   begins by anchoring the cursor to its argument —
   `self._current_focused_node_id = node_id; self._selection.set_primary(node_id)`
   — so the dialog's single-node target (`effective()` falls back to
   `{primary}` when nothing is marked) is unambiguously `node_id` regardless of
   message-ordering. It is a no-op on the `A` path (primary already equals
   node_id) and does not disturb a marked set (`effective()` returns the marked
   set when non-empty — the t983_4 multi-target semantics are unchanged).

6. **Repoint both `Enter` sites to `NodeHub` with a result callback.** Add
   `_on_node_hub_result(result)`: when `isinstance(result, NodeHubResult)` and
   `result.action == NODE_HUB_OPERATIONS` it calls
   `self._open_operations_dialog(result.node_id)`; a plain `None` (Escape/Close)
   is a no-op. The push-callback fires only after the Hub is dismissed, so
   Operations opens cleanly on a closed Hub — no nested modal.

7. **No auto-open on cursor movement (preserved).** Already the case: focus
   changes only refresh the shared `#browse_node_panel`
   (`_show_browse_node_detail` `:6230`); `Enter` is the sole opener. No change
   needed beyond not adding any focus-triggered open.

8. **"Remove the now-redundant direct `NodeDetailModal` opens" = repoint, not
   delete the class.** After step 6, no site opens `NodeDetailModal` directly;
   the class remains as the Hub's base + the tests' fixture. This is the
   scope-honest reading of the stub's "remove redundant opens".

## Implementation steps (all in `.aitask-scripts/brainstorm/brainstorm_app.py` unless noted)

1. **Hooks on `NodeDetailModal`.** In `compose` (`:1067`), replace the inline
   title with `Label(self._dialog_title_text(), id="node_detail_title")` and the
   inline button row with `with Horizontal(id="node_detail_buttons"): yield from
   self._dialog_buttons()`. Add:
   ```python
   def _dialog_title_text(self) -> str:
       return f"Node Detail: {self.node_id}"

   def _dialog_buttons(self):
       yield Button("Close", variant="default", id="btn_close_detail")
   ```

2. **Typed result protocol + `NodeHub` subclass** (define right after
   `NodeDetailModal`, before `_open_node_detail_visible` `:1227`;
   `NamedTuple` is already imported at `:10`):
   ```python
   NODE_HUB_OPERATIONS = "operations"   # add NODE_HUB_* verbs as launch surfaces grow

   class NodeHubResult(NamedTuple):
       """What a NodeHub dismisses with: `action` ∈ NODE_HUB_* verbs, `node_id`
       the Hub's node. Extend the Hub (t983_6/t983_7) = add a verb + a branch
       in BrainstormApp._on_node_hub_result."""
       action: str
       node_id: str

   class NodeHub(NodeDetailModal):
       """Node Hub overlay (Enter): the shared Detail surface (Metadata
       NodeDetailPanel + Proposal/minimap, inherited from NodeDetailModal) plus
       an Operations entry that launches the contextual Operations dialog
       (t983_4) seeded from the current selection."""

       BINDINGS = [Binding("a", "operations", "Operations")]

       def _dialog_title_text(self) -> str:
           return f"Node Hub: {self.node_id}"

       def _dialog_buttons(self):
           yield Button("Operations", variant="primary", id="btn_node_hub_ops")
           yield Button("Close", variant="default", id="btn_close_detail")

       def action_operations(self) -> None:
           self.dismiss(NodeHubResult(NODE_HUB_OPERATIONS, self.node_id))

       @on(Button.Pressed, "#btn_node_hub_ops")
       def _open_operations(self) -> None:
           self.dismiss(NodeHubResult(NODE_HUB_OPERATIONS, self.node_id))
   ```
   (Textual merges `BINDINGS` across the MRO, so the inherited `escape`/`tab`/
   `v`/`e` bindings remain.)

3. **Extract `_open_operations_dialog`.** Refactor `action_node_action` (`:4405`):
   keep the modal-active + `tab_browse` checks and the `node_id =
   self._current_focused_node_id` / "Focus a node first" guard, then
   `self._open_operations_dialog(node_id)`. Move the read-only / status /
   node-exists guards and the `cardinality`/`op_states`/`targets` + `push_screen`
   block (`:4421-4453`) into the new method, prefaced by the cursor-anchor
   invariant:
   ```python
   def _open_operations_dialog(self, node_id: str) -> None:
       """Open the contextual Operations dialog for node_id (shared by the `A`
       keybinding and the Node Hub's Operations entry)."""
       # Anchor the cursor to node_id so the dialog's single-node target is
       # unambiguous regardless of event ordering (no-op on the `A` path; does
       # not disturb a marked set — effective() returns marks when non-empty).
       self._current_focused_node_id = node_id
       self._selection.set_primary(node_id)
       # read_only / status / node-exists guards (verbatim from action_node_action)
       # ... cardinality = self._selection.cardinality
       # ... op_states = self._node_action_op_states(node_id, cardinality)
       # ... targets = sorted(self._selection.effective()) or [node_id]
       # ... self.push_screen(NodeActionSelectModal(node_id, op_states, targets=targets),
       #         lambda result, nid=node_id: self._on_node_action_result(nid, result))
   ```

4. **Repoint the two `Enter` sites + add the callback.**
   - `action_open_node_detail` (`:4290`):
     `self.push_screen(NodeHub(focused.node_id, self.session_path), self._on_node_hub_result)`
   - `on_dag_display_node_selected` (`:6311`):
     `self.push_screen(NodeHub(event.node_id, self.session_path), self._on_node_hub_result)`
   - Add:
     ```python
     def _on_node_hub_result(self, result) -> None:
         """Hub dismissed: NodeHubResult(action, node_id) dispatches the action;
         None (Escape/Close) → no-op. New launch verbs (t983_6/7) add a branch."""
         if isinstance(result, NodeHubResult) and result.action == NODE_HUB_OPERATIONS:
             self._open_operations_dialog(result.node_id)
     ```
   - Update the two `action_open_node_detail` / `on_dag_display_node_selected`
     docstrings (and the `:6977` comment) from "NodeDetailModal" → "NodeHub".

5. **New test `tests/test_brainstorm_node_hub.py`** (pure `.py`, run via
   `tests/run_all_python_tests.sh`; mirror the harness in
   `test_brainstorm_node_detail_panel.py` — `_make_session`, a bare `_HostApp`
   that pushes `NodeHub` on mount, and the `_SmokeApp(BrainstormApp)` that skips
   the session-loading `on_mount`).

## Verification

- **Pilot — `tests/test_brainstorm_node_hub.py`** (new):
  - `assert issubclass(NodeHub, NodeDetailModal)` and the binding table contains
    `a → operations` (guards concern 7 — the final merged BINDINGS).
  - Push `NodeHub(node_id, session)` on a bare host → after `pilot.pause()` the
    Detail content renders the cursor node (title `Node Hub: <id>`, the Metadata
    `NodeDetailPanel`, the Proposal tab) **and** the `#btn_node_hub_ops`
    Operations button is present.
  - Hub dismiss contract: drive `a` (and separately press `#btn_node_hub_ops`) →
    assert the Hub dismisses with `NodeHubResult(NODE_HUB_OPERATIONS, node_id)`
    (typed, not a bare string).
  - **Non-vacuous Operations launch:** the `_SmokeApp(BrainstormApp)` fixture
    MUST write a session whose status is `active` and whose node exists in the
    graph (`list_nodes`), so `_open_operations_dialog`'s read-only/status/
    node-exists guards **pass** rather than short-circuit. Then drive the Hub's
    `a` (or button) and `pilot.pause()` → **positively assert
    `isinstance(app.screen, NodeActionSelectModal)`** (the dialog actually
    pushed). Add a companion negative case: a read-only session → the guard
    fires, `notify` is called, and **no** `NodeActionSelectModal` is pushed
    (so the positive test cannot pass vacuously).
  - `Enter` opens the Hub, **both views**: in the `_SmokeApp`, focus a `NodeRow`
    and press `enter` → `isinstance(app.screen, NodeHub)`; drive the graph path
    via `on_dag_display_node_selected` (`DAGDisplay.NodeSelected`) → a `NodeHub`
    is pushed. End-to-end from the graph path: dismiss that Hub with the
    Operations result → assert `NodeActionSelectModal` opens (covers the
    graph-view chain, not just that the Hub mounts).
- **Regression:** `test_brainstorm_node_detail_minimap.py`,
  `test_brainstorm_node_export.py`, `test_brainstorm_node_detail_panel.py`
  (construct `NodeDetailModal` directly — unaffected),
  `test_brainstorm_node_action_modal.py` / `…_relevance.py` (the Operations
  dialog path is byte-preserved by the extract-helper refactor).
- **Suite:** `bash tests/run_all_python_tests.sh` (`tests/test_brainstorm*.py`)
  green.
- **Manual:** `ait brainstorm <session>` → Browse, `Enter` on a node in **list**
  view opens the Hub (Detail renders, Proposal/minimap intact); `a` (or the
  Operations button) opens the Operations dialog for that node; Escape/Close
  returns without opening anything. Repeat in **graph** view (`Enter` on a DAG
  node). `space`-mark a second node, `Enter` → Hub → Operations shows the marked
  `Targets (2): …` with single-node ops greyed (t983_4 behavior, now reachable
  from the Hub).

## Risk

### Code-health risk: low
- Two new overridable hooks (`_dialog_title_text` / `_dialog_buttons`) on
  `NodeDetailModal`; both return the current literals, so base behavior is
  byte-identical. · severity: low · → mitigation: covered by the unchanged
  minimap/export/panel regression tests
- The Operations-launch logic is extracted into `_open_operations_dialog`;
  `action_node_action` becomes a thin guard+delegate. **Verified single
  extraction** — the moved block is the contiguous `:4421-4453` body with one
  caller today. · severity: low · → mitigation: the existing
  `test_brainstorm_node_action_modal.py` / `OnNodeActionResultTests` exercise the
  preserved path; the new Hub test exercises the second caller
- Hub→app launch contract: an untyped tuple would be fragile as t983_6/t983_7
  add launch verbs. · severity: low (mitigated in design) · → mitigation: typed
  `NodeHubResult` NamedTuple + `NODE_HUB_*` constants + a dispatch docstring
  naming the future extenders (Design §3)
- Graph-view `Enter` → Operations could target a stale cursor in a narrow
  message-ordering window. · severity: low (mitigated in design) · → mitigation:
  the cursor-anchor invariant at the top of `_open_operations_dialog` (Design §5)
  pins the dialog's single-node target to the Hub's node; the marked-set path is
  untouched; a graph-path end-to-end test asserts the chain

### Goal-achievement risk: low
- Approach is the parent-mandated one (Hub overlay on `Enter` + Operations entry
  reusing the t983_4 dialog), and every prerequisite (`NodeDetailModal` Detail
  surface, `NodeActionSelectModal`, `self._selection`) is verified present. ·
  severity: low · → mitigation: n/a

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_5`.
