---
Task: t475_4_integrate_tui_switcher_existing_tuis.md
Parent Task: aitasks/t475_monitor_tui.md
Sibling Tasks: aitasks/t475/t475_2_*.md
Archived Sibling Plans: aiplans/archived/p475/p475_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: Integrate TUI Switcher into Existing TUIs

## Step 1: Board TUI (aitask_board.py)

File: `.aitask-scripts/board/aitask_board.py`

1. Add import at top (adjust path for board's location):
   ```python
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
   from tui_switcher import TuiSwitcherMixin
   ```
2. Change `class KanbanApp(App):` → `class KanbanApp(App, TuiSwitcherMixin):`
3. Add `*TuiSwitcherMixin.SWITCHER_BINDINGS,` at start of BINDINGS list
4. Add `self.current_tui_name = "board"` in `__init__`

## Step 2: CodeBrowser TUI (codebrowser_app.py)

File: `.aitask-scripts/codebrowser/codebrowser_app.py`

Same pattern. Set `self.current_tui_name = "codebrowser"`.

## Step 3: Settings TUI (settings_app.py)

File: `.aitask-scripts/settings/settings_app.py`

Same pattern. Set `self.current_tui_name = "settings"`.

## Step 4: Brainstorm TUI (brainstorm_app.py)

File: `.aitask-scripts/brainstorm/brainstorm_app.py`

Same pattern. Set `self.current_tui_name = "brainstorm"`.

## Step 5: DiffViewer TUI (diffviewer_app.py)

File: `.aitask-scripts/diffviewer/diffviewer_app.py`

Same pattern. Set `self.current_tui_name = "diffviewer"`.

## Verification

For each TUI:
1. Launch and press `j` — overlay appears
2. Select another TUI — switches/spawns correctly
3. Press `j` again — overlay closes
4. `Escape` also closes
5. All existing keybindings still work
6. Outside tmux: `j` shows warning notification

## Final Implementation Notes

- **Actual work done:** Integrated TuiSwitcherMixin into 4 of 5 TUI apps (board, codebrowser, settings, brainstorm). DiffViewer was skipped per user request. Also fixed two issues in the shared tui_switcher module.
- **Deviations from plan:**
  - DiffViewer integration deferred (user requested skip)
  - MRO order corrected from original plan: uses `TuiSwitcherMixin, App` (mixin first), matching the monitor app pattern from t475_3
  - Additional fix in `tui_switcher.py`: overlay now auto-highlights first selectable item on mount, skipping the disabled current TUI
  - Additional fix in board's `check_action`: returns `False` for nav actions when TuiSwitcherOverlay is active, preventing priority arrow key bindings from intercepting ListView navigation
- **Issues encountered:**
  - Board's `priority=True` arrow key bindings captured up/down keys before the TuiSwitcherOverlay's ListView could handle them. Fixed via `check_action` guard that returns `False` for nav actions when TuiSwitcherOverlay is the active screen.
  - ListView initially highlighted the disabled current TUI item. Fixed by setting `list_view.index` to the first non-disabled item after populating.
- **Key decisions:**
  - Used `*TuiSwitcherMixin.SWITCHER_BINDINGS` unpacking pattern (consistent and reusable) rather than manually adding `Binding("j", ...)` as done in monitor_app.py
  - Imported `TuiSwitcherOverlay` in board to enable isinstance check in check_action
  - Brainstorm needed `lib/` added to sys.path (previously only had parent dir)
- **Notes for sibling tasks:** DiffViewer integration (t475_5 or separate task) still needs: lib/ added to sys.path, `__init__` method created, same mixin pattern applied. The `check_action` fix is board-specific and shouldn't be needed for other TUIs unless they also use priority arrow key bindings.

## Step 9 Reference

Commit, archive, push per task-workflow Step 9.
