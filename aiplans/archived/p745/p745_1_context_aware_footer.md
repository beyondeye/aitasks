---
Task: t745_1_context_aware_footer.md
Parent Task: aitasks/t745_improve_node_comparator.md
Sibling Tasks: aitasks/t745/t745_2_compare_regenerate_shortcut.md, aitasks/t745/t745_3_compact_equal_and_inline_diff.md, aitasks/t745/t745_4_diffviewer_screen_integration.md, aitasks/t745/t745_5_manual_verification_improve_node_comparator.md
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-05-04 22:43
---

# Plan — t745_1: Context-aware footer + tab-label embedded shortcuts (verified)

## Context

Foundational child of t745. The brainstorm Footer currently shows tab-switching shortcuts (`d`/`g`/`c`/`a`/`s`) at all times and never shows per-tab actions. This task hides those tab keys from the footer, surfaces them inside each tab's visible label using the parentheses convention (`(D)ashboard`, `(G)raph`, `(C)ompare`, `(A)ctions`, `(S)tatus`), and adds the `check_action` + `_TAB_SCOPED_ACTIONS` registry that subsequent siblings (t745_2, t745_4) will populate to make their bindings tab-scoped.

This task introduces no functional behavior change for existing actions — only footer visibility plumbing — and unblocks the rest of t745.

## Verification of plan against current code (re-confirmed)

- `BINDINGS` block at lines 1512–1523 contains the five tab bindings (`d` Dashboard, `g` Graph, `c` Compare, `a` Actions, `s` Status), `q` Quit, `ctrl+r`, `ctrl+shift+r`. None has `show=False` yet for the tab keys.
- `compose()` at lines 1586–1614 contains five `TabPane(...)` calls with IDs `tab_dashboard`, `tab_dag`, `tab_compare`, `tab_actions`, `tab_status`. (Note: action `tab_graph` maps to TabPane id `tab_dag` — not a typo, just the existing naming.)
- Action handlers `action_tab_dashboard / _graph / _compare / _actions / _status` exist at lines 1916–1948.
- `aitask_board.py` `check_action` reference still at lines 3333–3380 — return contract: `True` show / `False` gray / `None` hide.
- `query_one(TabbedContent).active` is already used at lines 1620 and 1781 — the pattern is confirmed valid for this app.

No deviations from the original plan are required. Proceeding with the implementation as-is.

## Critical files

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `compose()` (lines 1586–1614) — TabPane label edits.
  - `BINDINGS` (lines 1512–1523) — `show=False` on tab bindings.
  - New: class-level `_TAB_SCOPED_ACTIONS` dict (initially empty; siblings populate).
  - New: `check_action()` method.

## Reference (do not modify)

- `.aitask-scripts/board/aitask_board.py:3333-3380` — canonical `check_action` style.

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
   Default `True` keeps every non-registered action visible. Only registered actions get gated.

## Verification

- Launch `./.aitask-scripts/aitask_brainstorm.sh 635` (an existing brainstorm session).
- Verify the five tabs at top read `(D)ashboard | (G)raph | (C)ompare | (A)ctions | (S)tatus`.
- Verify the footer no longer shows entries for `d g c a s`. `q Quit` remains; `j` (TUI switcher) was already hidden.
- Press each shortcut letter — tabs still switch.
- Aggregate manual verification (t745_5) covers this.

## Final Implementation Notes

- **Actual work done:** Three localized edits to `.aitask-scripts/brainstorm/brainstorm_app.py`: (1) added `show=False` to the five tab `Binding`s in `BINDINGS`; (2) added a class-level `_TAB_SCOPED_ACTIONS: dict[str, str] = {}` registry directly below `BINDINGS`, with a leading docstring-comment explaining its purpose; (3) added a `check_action(self, action, parameters)` method right after `__init__` that returns `True` for non-registered actions, `None` (hide from footer) when the active TabbedContent tab does not match the registry value, and `True` when it does; (4) wrapped the five `TabPane(...)` first-arg labels with the parentheses convention `(D)ashboard`, `(G)raph`, `(C)ompare`, `(A)ctions`, `(S)tatus`.
- **Deviations from plan:** None. The plan was followed verbatim. The internal `_TAB_SCOPED_ACTIONS` registry ships empty as planned — t745_2 and t745_4 will populate it.
- **Issues encountered:** None. `python3 -c "import ast; ast.parse(...)"` confirmed syntactic correctness. No tests changed (no brainstorm-app unit tests exist for this surface). Visual TUI verification is deferred to t745_5 (aggregate manual verification sibling).
- **Key decisions:** Placed `check_action` immediately after `__init__` (above all other helpers) because it is a Textual lifecycle hook and benefits from being visually grouped with the bindings and registry it gates. Used a bare-`Exception` catch on the `query_one(TabbedContent)` call so the footer never crashes during early `compose()` lifecycle if the widget isn't mounted yet — at that point we hide the binding (`return None`), matching the safest fallback.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** Sibling tasks t745_2 and t745_4 add their bindings to `BINDINGS` and a one-line entry to `_TAB_SCOPED_ACTIONS` keyed on action name (e.g., `"compare_regenerate": "tab_compare"`, `"compare_diff": "tab_compare"`). The `check_action` method needs no changes for new tab-scoped actions. Note: the `Binding`'s `show=` attribute should remain the default `True` so that `check_action` controls visibility — passing `show=False` would render the binding permanently invisible regardless of tab. The registry entry only needs the bare action name (no `action_` prefix). Empirical observation during implementation: the existing `Binding("g", "tab_graph", ...)` action name does NOT match its TabPane id `tab_dag`. We did not normalize this in t745_1 (out of scope), but note that any future code that maps action_name → tab_id must use the action name (`tab_graph`), not the tab id (`tab_dag`).
