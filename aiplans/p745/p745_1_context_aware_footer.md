---
Task: t745_1_context_aware_footer.md
Parent Task: aitasks/t745_improve_node_comparator.md
Sibling Tasks: aitasks/t745/t745_2_compare_regenerate_shortcut.md, aitasks/t745/t745_3_compact_equal_and_inline_diff.md, aitasks/t745/t745_4_diffviewer_screen_integration.md
Archived Sibling Plans: aiplans/archived/p745/p745_*_*.md
Worktree: aiwork/t745_1_context_aware_footer
Branch: aitask/t745_1_context_aware_footer
Base branch: main
---

# Plan — t745_1: Context-aware footer + tab-label embedded shortcuts

## Context

Foundational child of t745. The brainstorm Footer currently shows tab-switching shortcuts (`d`/`g`/`c`/`a`/`s`) at all times and never shows per-tab actions. This task hides those tab keys from the footer, surfaces them inside each tab's visible label using the parentheses convention (`(D)ashboard`, `(G)raph`, `(C)ompare`, `(A)ctions`, `(S)tatus`), and adds the `check_action` + `_TAB_SCOPED_ACTIONS` registry that subsequent siblings (t745_2, t745_4) will populate to make their bindings tab-scoped.

This task introduces no functional behavior change for existing actions — only footer visibility plumbing — and unblocks the rest of t745.

## Critical files

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `compose()` (lines 1586–1614) — TabPane label edits.
  - `BINDINGS` (lines 1512–1523) — `show=False` on tab bindings.
  - New: class-level `_TAB_SCOPED_ACTIONS` dict (initially empty; siblings populate).
  - New: `check_action()` method.

## Reference (do not modify)

- `.aitask-scripts/board/aitask_board.py:3333-3380` — canonical `check_action` style (return `True` show / `None` hide).

## Implementation steps

1. **Embed shortcut letter in tab labels** in `compose()`:
   - `TabPane("Dashboard", id="tab_dashboard")` → `TabPane("(D)ashboard", id="tab_dashboard")`
   - `TabPane("Graph", id="tab_dag")` → `TabPane("(G)raph", id="tab_dag")`
   - `TabPane("Compare", id="tab_compare")` → `TabPane("(C)ompare", id="tab_compare")`
   - `TabPane("Actions", id="tab_actions")` → `TabPane("(A)ctions", id="tab_actions")`
   - `TabPane("Status", id="tab_status")` → `TabPane("(S)tatus", id="tab_status")`

2. **Hide tab keys from footer** by adding `show=False` to each:
   ```python
   Binding("d", "tab_dashboard", "Dashboard", show=False),
   Binding("g", "tab_graph",     "Graph",     show=False),
   Binding("c", "tab_compare",   "Compare",   show=False),
   Binding("a", "tab_actions",   "Actions",   show=False),
   Binding("s", "tab_status",    "Status",    show=False),
   ```
   `q` (Quit), `ctrl+r`, and `ctrl+shift+r` are unchanged. The TUI switcher binding from `TuiSwitcherMixin.SWITCHER_BINDINGS` is already `show=False`.

3. **Add registry** as a class attribute near the top of `BrainstormApp`:
   ```python
   # Maps action_name -> required tab id; check_action hides the binding
   # from the footer when the active tab does not match.
   _TAB_SCOPED_ACTIONS: dict[str, str] = {}
   ```

4. **Add `check_action`**:
   ```python
   def check_action(self, action: str, parameters) -> bool | None:
       required_tab = self._TAB_SCOPED_ACTIONS.get(action)
       if required_tab is None:
           return True
       try:
           tabbed = self.query_one(TabbedContent)
       except Exception:
           return None
       if tabbed.active != required_tab:
           return None
       return True
   ```
   Default `True` keeps every non-registered action visible (same as today). Only registered actions get gated.

## Verification

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635` (an existing brainstorm session).
- Verify the five tabs at top read `(D)ashboard | (G)raph | (C)ompare | (A)ctions | (S)tatus`.
- Verify the footer no longer shows entries for `d g c a s`. `q Quit` remains; `j` (TUI switcher) was already hidden.
- Press each shortcut letter — tabs still switch.
- No tests are mandatory here; behavior is verified visually. The aggregate manual verification (t745_5) covers this.

## Final Implementation Notes

(to be filled in at Step 8)
