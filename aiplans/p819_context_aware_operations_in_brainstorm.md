---
Task: t819_context_aware_operations_in_brainstorm.md
Base branch: main
plan_verified: []
---

# t819 — Context-aware single-node operations in brainstorm TUI

## Context

The `ait brainstorm` Textual TUI has five tabs: **Dashboard** and **Graph**
(browse DAG nodes), **Compare** and **Actions** (dispatch operations), and
**Status**. The Compare operation is already reachable contextually from the
Graph tab (`x` on a focused node → switch to Compare tab pre-loaded with that
node). The Actions tab's operation wizard has no such shortcut: to run an
operation on a node the user must switch to Actions, pick the operation, then
re-pick the node they were already looking at.

This task adds the same context-aware shortcut for the wizard's **single-node
operations** — Explore, Detail, Patch. From the Graph or Dashboard tab, with a
node focused, the user opens a small modal dialog, picks one of those three
operations, and is dropped into the Actions-tab wizard with the operation and
node pre-selected — landing directly on the config / section-select / confirm
step so only the operation definition remains.

**Decisions (from user):** the picker offers all three single-node ops
(Explore, Detail, Patch; Patch disabled when the node has no plan). The `a`
key stays bound to "switch to Actions tab"; the new picker uses **`A`
(shift+a)** — free, mnemonic, and consistent with the existing `D` (`shift+d`,
compare-diff) app-level binding.

All production code lands in one file:
`.aitask-scripts/brainstorm/brainstorm_app.py`. The TUI runs on PyPy 3.11 —
**no Python 3.12+ syntax** (no `match`, no PEP 695; keep `X | None`).

## Pattern being mirrored

`on_dag_display_compare_requested()` (`brainstorm_app.py:4847-4877`) — the
Compare-from-Graph handler. Its critical detail: **defocus the source widget
before switching tabs** (`tabbed.query_one(Tabs).focus()` then
`tabbed.active = ...`), otherwise Textual auto-reverts the active tab to keep
the focused widget visible. The new callback must do the same.

Modal template: `CompareNodeSelectModal` (`brainstorm_app.py:1481-1576`).

## Implementation

### 1. New modal class `NodeActionSelectModal`

Insert after `CompareNodeSelectModal` (after line 1576). A `ModalScreen`
subclass; single-select picker reusing the existing `OperationRow` widget
(lines 1756-1786) for visual parity with the Actions wizard's step 1.

- `__init__(self, node_id: str, has_plan: bool)`.
- `compose()`: `Container(id="node_action_dialog")` holding a title label
  (`Operate on node <id>`), a hint label, a `VerticalScroll(id="node_action_list")`
  with one `OperationRow` per op — `explore`, `detail`, `patch` — and a Cancel
  button. The `patch` row is disabled (`disabled=True` → `can_focus=False`)
  when `has_plan` is false.
- `BINDINGS`: `escape` → `cancel`.
- `on_key`: `up`/`down` navigate enabled `OperationRow`s (wrap-around over
  focusable rows only, mirroring `CompareNodeSelectModal._navigate_checkboxes`);
  `enter` dismisses with the focused row's `op_key`.
- `@on(OperationRow.Activated)`: mouse click on an enabled row → `event.stop()`
  then `dismiss(op_key)` (`event.stop()` keeps the message off the app's
  `on_operation_row_activated`).
- `on_mount` → `call_after_refresh` to focus + `selected`-mark the first
  enabled row.
- Returns the chosen `op_key` string via `dismiss()`, or `None` on cancel.

### 2. CSS

Add a `#node_action_dialog` / `#node_action_title` / `#node_action_hint` /
`#node_action_list` / `#node_action_buttons` block to the app's `CSS`,
adjacent to and modelled on the existing `#compare_select_dialog` rules
(fixed width ~64, `border: thick $primary`, centered title, scrollable list).

### 3. App binding + `action_node_action()`

- Add `Binding("A", "node_action", "Node op")` to `BrainstormApp.BINDINGS`
  (lines 2605-2626), grouped next to the `D` binding.
- New `action_node_action()` near `action_tab_graph` (after line 3161). Guards,
  in order: not under a `ModalScreen`; active tab ∈ {`tab_dashboard`,
  `tab_dag`}; `_current_focused_node_id` is set (else `notify` "Focus a node
  first"); `self.read_only` false (else warn); session `status` ∈ {`init`,
  `active`} (else warn — design ops unavailable); node still in
  `list_nodes(self.session_path)` (else clear `_current_focused_node_id`,
  error). Then `push_screen(NodeActionSelectModal(node_id, has_plan), callback)`
  where `has_plan = self._node_has_plan(node_id)` (helper at line 5420).

### 4. `check_action()` footer scoping

`_TAB_SCOPED_ACTIONS` maps one action → one tab and cannot express two tabs.
Add an explicit `node_action` branch in `check_action()` after the `op_help`
branch (after line 2711), mirroring its style: return `True` only when the
active tab is `tab_dashboard`/`tab_dag` **and** `_current_focused_node_id` is
set; otherwise `None` (hides the binding from the footer, keeps it live).

### 5. Modal callback `_on_node_action_result(node_id, op_key)`

Add next to `action_node_action`. On `op_key` falsy → return. Re-validate the
node still exists (`list_nodes`) — background poll timers can mutate the DAG
while the modal is open. Then:

1. Defocus source widget: `tabbed.query_one(Tabs).focus()` (in `try`).
2. `tabbed.active = "tab_actions"`.
3. Seed wizard state as if step 1 just completed: `_wizard_op = op_key`,
   `_set_total_steps()` (line 5120), reset `_wizard_has_sections` /
   `_cmp_section_checks`.
4. Call `_actions_show_node_select()` (renders step 2; note it clears
   `_wizard_config`), **then** set `_wizard_config["_selected_node"] = node_id`,
   mark the matching `OperationRow.selected` and enable `.btn_actions_next`
   (mirrors `on_operation_row_activated` lines 5729-5739) so a later wizard
   `Back` lands on a correct step 2.
5. Call `_actions_advance_from_node_select(node_id)` to render the real next
   step (config / section-select / confirm).

### 6. Extract `_actions_advance_from_node_select(node)` helper

Consolidate the node-select advance logic currently duplicated in three
places. Insert the new method before `_actions_show_section_select`
(before line 5196). Body = verbatim lift of the canonical block at
`_on_actions_next` lines 5640-5659: empty-node guard; patch-needs-plan guard
(`_node_has_plan`, notify error); `_node_has_sections(node)` →
`_actions_show_section_select()`; else `detail` → set `_wizard_config["node"]`
+ `_actions_show_confirm()`; else `_actions_show_config()`.

Update the call sites:
- **`_on_actions_next`** (lines 5637-5659): the `_wizard_step == 2` /
  `_NODE_SELECT_OPS` branch calls the helper.
- **Keyboard `Enter`** handler (`on_key`, lines 2942-2954): the step-2 branch
  calls the helper. **This fixes a pre-existing bug** — the old keyboard path
  jumped `detail` straight to `_actions_show_confirm()`, skipping
  `_actions_show_section_select()` for nodes that have sections. Routing
  through the helper applies the section check uniformly. Record this as an
  upstream-defect fix in the commit message / Final Implementation Notes.
- **New modal callback** (§5) — third caller.

### 7. Edge cases

Empty session / no focused node → warn, no modal. Node deleted before keypress
→ caught in `action_node_action`. Node deleted while modal open → re-checked in
`_on_node_action_result`. Read-only or non-`init`/`active` status → warn, no
modal. Patch on a planless node → disabled in the modal; the helper's
patch/no-plan guard is the safety net. `A` under a pushed/modal screen →
blocked by the `ModalScreen` guard and the `screen_stack > 1` guard already at
the top of `check_action`.

## Critical files

- `.aitask-scripts/brainstorm/brainstorm_app.py` — all production code
  (modal class, CSS, binding, `action_node_action`, `_on_node_action_result`,
  `_actions_advance_from_node_select` extraction, two existing call-site edits).
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `list_nodes`, `read_node`
  (already imported; read-only reference).
- `tests/test_brainstorm_node_action_modal.py` — new test file.
- `tests/test_brainstorm_dag_op_keybinding.py` /
  `tests/test_brainstorm_compare_modal.py` — Pilot and unit-test patterns to
  mirror.

## Testing / verification

New file `tests/test_brainstorm_node_action_modal.py`, PyPy 3.11 syntax:

**Unit tests** (mirror `test_brainstorm_compare_modal.py`): modal composes 3
`OperationRow`s; `has_plan=False` → `patch` row `op_disabled` /
`can_focus=False`, others enabled; title contains the node id; navigation
wraps over enabled rows only.

**Pilot integration tests** (mirror `test_brainstorm_dag_op_keybinding.py`,
temp session with a planned and a planless node):
- `A` on Dashboard / on Graph with a node focused → `NodeActionSelectModal`
  on the screen stack.
- Pick `explore` → modal dismissed, `tabbed.active == "tab_actions"`,
  `_wizard_op == "explore"`, `_wizard_config["_selected_node"]` set, wizard on
  the config step (not node-select).
- Pick `detail` on a node **with** sections → lands on
  `_actions_show_section_select` (`_wizard_has_sections is True`) — regression
  guard for the keyboard-Enter bug fix.
- Pick `detail` on a node **without** sections → lands on
  `_actions_show_confirm`, `_wizard_config["node"]` set.
- `A` with no node focused / on Compare or Status tab / while a modal is open
  / on a read-only session → no modal pushed, appropriate notify.
- `check_action("node_action", None)` → `True` on a node tab with a focused
  node, `None` otherwise.

Run the new test plus the existing brainstorm wizard/DAG tests to confirm the
helper extraction is behavior-preserving. Manual smoke test: `ait brainstorm`
on a session, focus a node on Graph and Dashboard, press `A`, run each of the
three operations end-to-end.

Then Step 8 (user review), Step 9 (post-implementation: merge, archive).

## Follow-ups for other agent trees

Per CLAUDE.md, this is a Claude Code skill-source-of-truth repo, but this
change is to the brainstorm TUI (Python), not a skill — no Codex/Gemini/
OpenCode port needed.

## Post-Review Changes

### Change Request 1 (2026-05-20 14:34)

- **Requested by user:** Manual testing showed the picker dialog opened
  fine, but selecting an operation often did nothing — the wizard only
  started after several attempts on the same node, non-deterministically.
  Restarting the TUI reproduced it. Symptom of "hidden state" gating the
  selection.
- **Root cause:** `Screen.dismiss()` (Textual 8.1.1, `screen.py:1908`)
  invokes the result callback *before* `pop_screen()`. `pop_screen()`
  (`app.py:3061`) posts a `ScreenResume` event that restores focus to the
  pre-modal widget — the `DAGDisplay` / `NodeRow` on the Graph/Dashboard
  tab. The original `_on_node_action_result` switched to the Actions tab,
  but the later `ScreenResume` re-focused the source widget and
  `TabbedContent` reverted the active tab to keep it visible. The tab
  switch was silently undone; the "works after N tries" was the resulting
  focus race.
- **Changes made:** Reworked the flow to be timing-independent. The Actions
  tab is now switched in `action_node_action` *before* the picker modal is
  pushed (focus moved off the source widget onto the `Tabs` bar first, so
  `ScreenResume` restores focus to `Tabs` and the Actions tab sticks).
  `_on_node_action_result` no longer switches tabs on the success path; it
  gained an `origin_tab` parameter and restores it on cancel / missing-node.
  Added `OnNodeActionResultTests` (3 tests) covering the callback contract
  (cancel restores origin tab, missing node restores origin tab, a valid
  pick seeds the wizard and keeps the Actions tab).
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`,
  `tests/test_brainstorm_node_action_modal.py`.

### Change Request 2 (2026-05-20 14:49)

- **Requested by user:** The Change Request 1 fix made it worse — picking
  an operation now did nothing at all (on the Graph tab).
- **Root cause (the real one):** `widget.focus()` in Textual is
  **asynchronous** — it does not update `screen.focused` until a
  message-pump turn later. Change Request 1's `action_node_action` did
  `tabbed.query_one(Tabs).focus()` then immediately `push_screen(...)`, so
  at push time the `DAGDisplay` was *still* the focused widget. The modal
  screen saved `DAGDisplay` as the focus to restore; on dismiss the pop's
  `ScreenResume` restored it, and `TabbedContent` reverted to the Graph tab
  to keep the focused widget visible. (Confirmed by booting the app under
  the Textual pilot: after `Tabs.focus()`, `app.focused` was unchanged
  until a `pause()`.) The Dashboard happened to work by timing luck.
- **Changes made:** `action_node_action` no longer touches tabs or focus —
  it just opens the picker. The dismiss callback `_on_node_action_result`
  seeds the wizard and then defers the tab switch via `call_after_refresh`
  to `_enter_actions_tab`, which runs *after* the modal pop and its
  `ScreenResume` have fully settled (`call_after_refresh` drains pending
  messages first). `_enter_actions_tab` sets `tabbed.active` and focuses a
  widget inside `#actions_content` — being the last focus change, the
  Actions tab sticks. On cancel nothing happened, so the user naturally
  stays on the originating tab (no explicit restore needed). Removed the
  now-unused `_focus_first_in_actions_content`.
- **Verification added:** New `tests/test_brainstorm_node_action_integration.py`
  — boots a real `BrainstormApp` over a temp session (`init_session`) and
  drives it with the Textual pilot: `A` on the Graph and Dashboard tabs,
  pick an op, assert the Actions tab activates and the wizard is seeded;
  a repeated-attempts test guards the "works only after retries" symptom;
  a cancel test. Confirmed deterministic across multiple runs. The
  `OnNodeActionResultTests` unit tests were updated for the new
  `_on_node_action_result(node_id, op_key)` signature.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`,
  `tests/test_brainstorm_node_action_modal.py`,
  `tests/test_brainstorm_node_action_integration.py`.

## Final Implementation Notes

- **Actual work done:** Added the `A` keybinding on the Graph/Dashboard
  tabs, the `NodeActionSelectModal` picker (Explore/Detail/Patch; Patch
  disabled when the node has no plan), and the wizard-entry flow that seeds
  the Actions wizard pre-loaded with the chosen op + node. Extracted
  `_actions_advance_from_node_select` as the shared node-select advance
  helper (Next button, keyboard Enter, picker callback). Added CSS, the
  `check_action` footer-scoping branch, and `_enter_actions_tab`.
- **Deviations from plan:** Plan §5 had the dismiss callback switch tabs
  directly; the shipped design defers the tab switch via
  `call_after_refresh` to `_enter_actions_tab` after the modal pop settles
  (necessary — see Post-Review Changes CR1/CR2). The plan deferred the
  end-to-end in-TUI flow to manual verification; a full-app pilot
  integration test was added instead (`test_brainstorm_node_action_integration.py`).
- **Issues encountered:** Two review iterations on a focus/timing bug —
  the modal pop's `ScreenResume` reverted the Actions-tab switch. Root
  cause was `widget.focus()` being asynchronous in Textual. Resolved by
  not touching tabs/focus in `action_node_action` and deferring the switch
  to after the pop settles. Full detail in Post-Review Changes.
- **Key decisions:** Use `call_after_refresh` + the `TabbedContent`
  focus-auto-reveal mechanism (focus a widget in `#actions_content`) rather
  than fighting it; `action_node_action` opens the picker only, so cancel
  is a natural no-op.
- **Upstream defects identified:** None. (Diagnosis surfaced a pre-existing
  bug — keyboard `Enter` on the wizard node-select step skipped section
  selection for `detail` — but it lives in the same file and was fixed
  in-scope by routing all three call sites through
  `_actions_advance_from_node_select`.)
