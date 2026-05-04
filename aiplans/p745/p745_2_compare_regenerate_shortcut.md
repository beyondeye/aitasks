---
Task: t745_2_compare_regenerate_shortcut.md
Parent Task: aitasks/t745_improve_node_comparator.md
Sibling Tasks: aitasks/t745/t745_3_compact_equal_and_inline_diff.md, aitasks/t745/t745_4_diffviewer_screen_integration.md, aitasks/t745/t745_5_manual_verification_improve_node_comparator.md
Archived Sibling Plans: aiplans/archived/p745/p745_1_context_aware_footer.md
Worktree: aiwork/t745_2_compare_regenerate_shortcut
Branch: aitask/t745_2_compare_regenerate_shortcut
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-04 23:24
---

# Plan — t745_2: Compare tab regenerate shortcut (verified)

## Context

Issue 1 from the parent t745: once a comparison is shown, users have no visible
way to regenerate it with different nodes. With t745_1's context-aware footer in
place, this task adds an `r` key visible only on the Compare tab that re-opens
`CompareNodeSelectModal` to pick fresh nodes.

User-confirmed design decision: regenerate **always re-opens the modal** (not
"refresh same nodes").

## Verification of plan against current code (re-confirmed)

The original plan's line numbers drifted because t745_1 added the
`_TAB_SCOPED_ACTIONS` registry, the `check_action` method, and the parenthesized
tab labels. The substance and approach remain valid. Updated anchors:

- `BINDINGS` block at lines **1566–1577** (was 1512–1523). Tab bindings already
  carry `show=False`; `Binding("r", "compare_regenerate", "Regenerate")` is the
  new addition.
- `_TAB_SCOPED_ACTIONS: dict[str, str] = {}` at line **1582** — empty dict
  ready for the new `"compare_regenerate": "tab_compare"` entry.
- `check_action` at lines **1616–1626** — already in place; no change needed.
  Returns `None` (hide) when active tab does not match the registered tab id,
  `True` otherwise.
- Compare hint Label at line **1673** — currently
  `"Press 'c' to select nodes for comparison, 'D' to diff"`.
- `action_tab_compare` at lines **1997–2012** — second-press branch
  (lines 2001–2011) constructs and pushes `CompareNodeSelectModal(nodes)` with
  `callback=self._on_compare_selected`. This is the body to extract into
  `_open_compare_select_modal()`.
- `CompareNodeSelectModal` defined at line **759** — unchanged. (Sibling task
  t746 just landed `on_key` arrow navigation inside the modal but did not
  change its constructor signature or the callback contract.)
- `_on_compare_selected` callback at line **2935** — unchanged; replaces
  `_compare_nodes` and rebuilds the matrix via `_build_compare_matrix`, which
  already calls `container.remove_children()`. No cache-invalidation work
  needed.

No deviations from the original plan's approach are required.

## Critical files

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `BINDINGS` (1566–1577) — append `Binding("r", "compare_regenerate", "Regenerate")`.
  - `_TAB_SCOPED_ACTIONS` (1582) — change to `{"compare_regenerate": "tab_compare"}`.
  - `compose()` Compare hint Label (1673) — update text.
  - `action_tab_compare` (1997–2012) — refactor second-press body into a shared helper.
  - New: `_open_compare_select_modal()` private helper, `action_compare_regenerate()`.

## Reference files for patterns

- `aiplans/archived/p745/p745_1_context_aware_footer.md` — wiring of
  `_TAB_SCOPED_ACTIONS` and `check_action` (the `Binding`'s `show=` attribute
  must remain default `True` for `check_action` to control visibility; the
  registry needs only the bare action name without the `action_` prefix).

## Implementation steps

1. **Extract modal-open into a helper.** Move the body of `action_tab_compare`'s
   second-press branch (the `len(nodes) < 2` check, the `notify`, and the
   `push_screen(CompareNodeSelectModal(...), callback=self._on_compare_selected)`)
   into a new private method on `BrainstormApp`:

   ```python
   def _open_compare_select_modal(self) -> None:
       nodes = list_nodes(self.session_path)
       if len(nodes) < 2:
           self.notify("Need at least 2 nodes to compare", severity="warning")
           return
       self.push_screen(
           CompareNodeSelectModal(nodes),
           callback=self._on_compare_selected,
       )
   ```

   Place it directly above `action_tab_compare` (in the same "Tab switching
   actions" block) so the helper sits next to its sole caller.

2. **Update `action_tab_compare`** to delegate to the helper instead of
   duplicating the modal-push logic:

   ```python
   def action_tab_compare(self) -> None:
       if isinstance(self.screen, ModalScreen):
           return
       tabbed = self.query_one(TabbedContent)
       if tabbed.active == "tab_compare":
           self._open_compare_select_modal()
           return
       tabbed.active = "tab_compare"
   ```

3. **Add the new action** below `action_tab_compare`:

   ```python
   def action_compare_regenerate(self) -> None:
       if isinstance(self.screen, ModalScreen):
           return
       self._open_compare_select_modal()
   ```

   The `ModalScreen` guard mirrors the existing tab-switch handlers — important
   so the `r` key does not accidentally re-open the modal while another modal
   is already on top.

4. **Add the binding** in `BINDINGS` (after the five tab bindings, before the
   `ctrl+r` retry binding):

   ```python
   Binding("r", "compare_regenerate", "Regenerate"),
   ```

   Leave `show=` at its default (`True`) — `check_action` controls footer
   visibility per the t745_1 contract.

5. **Register in the tab-scoped actions map**:

   ```python
   _TAB_SCOPED_ACTIONS: dict[str, str] = {
       "compare_regenerate": "tab_compare",
   }
   ```

6. **Update the Compare tab hint Label** at line 1673:

   ```python
   "Press 'r' to (re)select nodes, 'D' to open full diff",
   ```

   The `'D' to open full diff` half is forward-looking copy that t745_4 will
   wire up; the existing footer/global `Shift+D` handler (in the `on_key`
   path) keeps the diff open path working until then.

## Verification

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635` (an existing brainstorm
  session with ≥2 nodes).
- Switch to the Compare tab. Footer shows `r Regenerate` (and `q Quit`).
- Press `r` (or `c` twice) — `CompareNodeSelectModal` opens. Pick two nodes.
  Comparison renders.
- Press `r` again — modal re-opens. Pick different nodes — comparison replaces
  the previous one (no stale rows; `_build_compare_matrix` clears children).
- Switch back to Dashboard — `r Regenerate` no longer in footer (only `q`,
  `ctrl+r`, and any other globally-shown bindings).
- Verify the empty-state hint Label inside the Compare tab on first entry
  reads `"Press 'r' to (re)select nodes, 'D' to open full diff"`.
- Aggregate human verification covered by sibling t745_5.

## Out of scope

- Caching / refresh-without-modal behavior. Always opens the modal per user
  decision.
- Wiring `D` to a real diff view — that is sibling t745_4.

## Step 9 — Post-Implementation

Follow the standard task-workflow Step 9 archive flow:
`./.aitask-scripts/aitask_archive.sh 745_2`. Parent t745 stays Ready until all
remaining children (t745_3, t745_4, t745_5) complete.

## Post-Review Changes

### Change Request 1 (2026-05-04 23:35)
- **Requested by user:** In the `CompareNodeSelectModal`, (a) add a keyboard shortcut to confirm the comparison since Enter is already used by Checkbox to toggle selection (suggested using `c`), and (b) make the Compare button visibly disabled when fewer than 2 nodes are selected so users see at-a-glance when the action is available.
- **Changes made:**
  1. Added `Binding("c", "confirm", "Compare")` to `CompareNodeSelectModal.BINDINGS`. The binding shows in the modal's footer for discoverability.
  2. Renamed `confirm` to `action_confirm` (the Textual action-name convention so the binding can resolve it). The `@on(Button.Pressed, "#btn_compare")` handler is now a thin shim (`_on_compare_pressed`) that delegates to `action_confirm()` so the button click and the `c` shortcut share one validation path.
  3. Updated the modal hint Label from `"↑↓ Navigate  Space/Enter Toggle"` to `"↑↓ Navigate  Space/Enter Toggle  c Compare"`.
  4. Added `_update_compare_button()` helper that disables `#btn_compare` when the selection count is outside `2 <= count <= 4`.
  5. Added `on_mount()` to set the initial disabled state (no checkboxes ticked → button disabled on first paint).
  6. Added `@on(Checkbox.Changed) _on_checkbox_changed` to refresh the button state every time a checkbox toggles.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py` (`CompareNodeSelectModal` class only).

### Change Request 2 (2026-05-04 23:38)
- **Requested by user:** Change the Compare button label from `"Compare"` to `"(C)ompare"` so the keyboard shortcut is visible directly on the button (matching the parenthesized-letter convention used by the brainstorm tab labels).
- **Changes made:** Updated the `Button` first-arg from `"Compare"` to `"(C)ompare"`.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py` (`CompareNodeSelectModal.compose()`).

## Final Implementation Notes

- **Actual work done:** All six planned edits to `.aitask-scripts/brainstorm/brainstorm_app.py` landed verbatim:
  (1) appended `Binding("r", "compare_regenerate", "Regenerate")` to `BrainstormApp.BINDINGS` after the five tab bindings;
  (2) populated `_TAB_SCOPED_ACTIONS` with `{"compare_regenerate": "tab_compare"}`;
  (3) updated the Compare-tab hint Label text to `"Press 'r' to (re)select nodes, 'D' to open full diff"`;
  (4) extracted the modal-push logic from `action_tab_compare`'s second-press branch into a new private helper `_open_compare_select_modal()`;
  (5) `action_tab_compare` second-press branch now delegates to the helper;
  (6) added new `action_compare_regenerate()` that guards against `ModalScreen` and calls `_open_compare_select_modal()`.
  Two post-review change requests added a `c` keyboard shortcut on the `CompareNodeSelectModal`, an auto-disabled `(C)ompare` button, and shared validation between the button click and the keyboard shortcut. See **Post-Review Changes** above for the per-request breakdown.
- **Deviations from plan:** None on the original 6-step plan. Two additive changes during Step 8 review (CR1, CR2) extended the scope to the existing `CompareNodeSelectModal` widget — they were not anticipated in the verified plan but were directly motivated by user testing the new `r` flow and noticing that the modal itself lacked a confirm shortcut and a disabled-state signal.
- **Issues encountered:** None substantive. The modified test files (`tests/test_init_data.sh`, `tests/test_t167_integration.sh`, `tests/test_t644_branch_mode_upgrade.sh`) that appeared in the working tree during this session are pre-existing WIP unrelated to t745_2 (they reference `python_resolve.sh` and `packaging/` from t732_2/t623_5) and were deliberately left out of the t745_2 commit.
- **Key decisions:**
  - Placed the `_open_compare_select_modal` helper directly above its callers in the "Tab switching actions" block rather than near other helpers further up the class, so the helper sits next to its sole caller pair (`action_tab_compare`, `action_compare_regenerate`).
  - Mirrored the `isinstance(self.screen, ModalScreen)` guard from the existing tab-switch handlers into `action_compare_regenerate` so the `r` key is a no-op while another modal is on top — matches the precedent set by `action_tab_compare` etc. and avoids accidentally re-opening the modal over itself.
  - For CR1, renamed `confirm` to `action_confirm` (Textual action-name convention) so the new `c` binding can resolve directly. The button's `@on(Button.Pressed, "#btn_compare")` handler is now a one-line shim (`_on_compare_pressed`) that calls `action_confirm()`. This keeps a single source of truth for the validation (the `< 2` and `> 4` notifications) shared between the button and the shortcut.
  - For CR1's button-disable behavior, used Textual's standard `@on(Checkbox.Changed)` event subscription rather than polling — the `_update_compare_button` helper recomputes the disabled state from `_get_selected()` so there is no parallel state to keep in sync.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t745_4 (`compare_diff` action):** Add the binding to `BrainstormApp.BINDINGS` next to `Binding("r", "compare_regenerate", ...)`. Register `"compare_diff": "tab_compare"` in `_TAB_SCOPED_ACTIONS` (the dict is no longer empty after this task — append the new key). The `Binding`'s `show=` attribute should remain default `True`; `check_action` controls footer visibility.
  - **CompareNodeSelectModal contract:** The modal now exposes `action_confirm()` as the canonical confirm path (button click and `c` shortcut both route through it). Future callers (e.g., the diffviewer integration in t745_4) that need to open this modal can rely on the existing `_open_compare_select_modal()` helper on `BrainstormApp` and the same `_on_compare_selected` callback that calls `_build_compare_matrix`. The modal's button-disable invariant is `2 <= count <= 4` enforced by `_update_compare_button()` on every Checkbox.Changed event.
  - **Hint Label copy:** The `'D' to open full diff` half of the new hint is forward-looking copy that t745_4 will wire up; the existing `Shift+D` global handler in `on_key` keeps the diff-open path working until then. No change needed in t745_4 beyond actually implementing the action.
