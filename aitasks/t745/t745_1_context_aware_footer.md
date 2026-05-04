---
priority: high
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-04 22:20
updated_at: 2026-05-04 22:27
---

## Context

Foundational child of t745. The brainstorm Footer currently advertises tab-switching shortcuts (`d` Dashboard / `g` Graph / `c` Compare / `a` Actions / `s` Status) but never the per-tab actions. This task hides tab-switching keys from the footer, communicates them inline in tab labels using the parentheses convention (`(D)ashboard`, `(G)raph`, `(C)ompare`, `(A)ctions`, `(S)tatus`), and adds a context-aware footer infrastructure (`check_action` + `_TAB_SCOPED_ACTIONS` registry) so subsequent siblings (t745_2, t745_4) can declare bindings that auto-show only when their tab is active.

This task is foundational — no functional behavior change for existing actions, just the footer visibility plumbing — and unblocks the rest of the t745 work.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `BrainstormApp.compose()` (lines 1586–1614) — change each `TabPane(...)` first-arg label to embed the shortcut letter in parentheses.
  - `BrainstormApp.BINDINGS` (lines 1512–1523) — add `show=False` to the five tab bindings (`d`, `g`, `c`, `a`, `s`). `q` (Quit), `ctrl+r`, and switcher bindings are unchanged.
  - Add a new method `check_action(self, action: str, parameters) -> bool | None` modelled on `aitask_board.py:3333`. It uses `self.query_one(TabbedContent).active` to decide visibility.
  - Add a class-level dict `_TAB_SCOPED_ACTIONS` (initially empty — siblings populate it).

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py` lines 3333–3380 — canonical `check_action` style. Use the same return-value contract: `True` (show), `False` (gray), `None` (hide). Match this style verbatim.
- `.aitask-scripts/brainstorm/brainstorm_app.py:1512` — existing `BINDINGS` shape and use of `show=False` (e.g. line 1522 for `ctrl+shift+r`).

## Implementation Plan

1. Update `compose()` TabPane labels:
   - `TabPane("Dashboard", id="tab_dashboard")` → `TabPane("(D)ashboard", ...)`
   - `TabPane("Graph", id="tab_dag")` → `TabPane("(G)raph", ...)`
   - `TabPane("Compare", id="tab_compare")` → `TabPane("(C)ompare", ...)`
   - `TabPane("Actions", id="tab_actions")` → `TabPane("(A)ctions", ...)`
   - `TabPane("Status", id="tab_status")` → `TabPane("(S)tatus", ...)`
2. Update `BINDINGS`: add `show=False` to `Binding("d", "tab_dashboard", "Dashboard")` and the four other tab bindings. Keep their action behavior intact.
3. Add a class-level constant `_TAB_SCOPED_ACTIONS: dict[str, str] = {}` near the top of the class. Document in a one-line comment that this maps action_name -> required_tab_id.
4. Add `check_action`:
   ```python
   def check_action(self, action: str, parameters) -> bool | None:
       required_tab = self._TAB_SCOPED_ACTIONS.get(action)
       if required_tab is None:
           return True  # not tab-scoped — let the default behavior win
       try:
           tabbed = self.query_one(TabbedContent)
       except Exception:
           return None
       if tabbed.active != required_tab:
           return None  # hide from footer when wrong tab is active
       return True
   ```
5. Do NOT touch any per-tab functionality in this task. Subsequent siblings will register their own actions in `_TAB_SCOPED_ACTIONS`.

## Verification Steps

- Launch the brainstorm TUI on an existing session: `./.aitask-scripts/aitask_brainstorm.sh 635`
  - The five tabs at the top now read `(D)ashboard | (G)raph | (C)ompare | (A)ctions | (S)tatus`.
  - The footer no longer shows `d g c a s` entries.
  - Pressing each shortcut key still switches tabs as before (binding behavior unchanged).
  - `q` (Quit) and `j` (TUI switcher) entries remain in the footer across all tabs.
- Run the existing brainstorm test suite (if any): `bash tests/test_brainstorm_*.sh` (skip if absent — TUI work is verified via t745_5).
- Run shellcheck if any `.sh` files were changed (this task should not change any).

## Notes for sibling tasks

- The `_TAB_SCOPED_ACTIONS` registry is the integration point. To add a tab-scoped binding from a sibling task: add `Binding("X", "my_action", "Label")` to `BINDINGS`, then add `"my_action": "tab_<id>"` to `_TAB_SCOPED_ACTIONS`. No further changes to `check_action` are required.
- `check_action`'s default-return is `True` so all existing actions remain visible; only registered ones get the gating.
