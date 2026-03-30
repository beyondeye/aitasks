---
priority: medium
effort: medium
depends: [t475_2]
issue_type: feature
status: Implementing
labels: [aitask_monitor, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-29 10:41
updated_at: 2026-03-30 09:52
---

## Integrate TUI Switcher into Existing TUIs

Add the `TuiSwitcherMixin` and `j` keybinding to all existing TUI applications for cross-TUI quick-switching.

### Context

The TUI Switcher widget (t475_2) provides a reusable mixin. This task integrates it into all 5 existing TUI apps. After this, pressing `j` in any TUI opens the switcher overlay for jumping between TUIs in the tmux session.

### Key Files to Modify

- `.aitask-scripts/board/aitask_board.py` — `KanbanApp` class (~line 2547)
- `.aitask-scripts/codebrowser/codebrowser_app.py` — `CodeBrowserApp` class
- `.aitask-scripts/settings/settings_app.py` — `SettingsApp` class
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `BrainstormApp` class
- `.aitask-scripts/diffviewer/diffviewer_app.py` — `DiffViewerApp` class

### Key Files to Reference

- `.aitask-scripts/lib/tui_switcher.py` — the TUI Switcher module (t475_2)
- `.aitask-scripts/lib/agent_launch_utils.py` — tmux utilities

### Implementation Plan

For each TUI app, the changes are minimal and follow the same pattern:

#### 1. Import the mixin

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
from tui_switcher import TuiSwitcherMixin
```

(Or adjust the import path based on how each TUI currently handles lib imports.)

#### 2. Add mixin to class inheritance

```python
# Before:
class KanbanApp(App):

# After:
class KanbanApp(App, TuiSwitcherMixin):
```

#### 3. Add switcher bindings

```python
# Before:
BINDINGS = [Binding("q", "quit", "Quit"), ...]

# After:
BINDINGS = [
    *TuiSwitcherMixin.SWITCHER_BINDINGS,
    Binding("q", "quit", "Quit"), ...
]
```

#### 4. Set current TUI name in __init__

```python
def __init__(self):
    super().__init__()
    self.current_tui_name = "board"  # unique per TUI
```

TUI name values: `"board"`, `"codebrowser"`, `"settings"`, `"brainstorm"`, `"diffviewer"`

#### 5. Keybinding compatibility verification

The `j` key is confirmed unused across all TUIs:
- Board: uses q, tab, escape, arrows, shift+arrows, ctrl+arrows, enter, r, s, c, C, n, p, x, X, O, a, g, i
- Codebrowser: uses q, escape, tab, r, t, g, e, d, D, h, H
- Settings: uses q, e, i, r
- Brainstorm: uses q, d, g, c, a, s
- Diffviewer: uses q, n, p, m, u, v, s, e

No conflicts with `j`.

### Verification

For each TUI:
1. Launch TUI
2. Press `j` — verify overlay appears
3. Select another TUI — verify it switches/spawns correctly
4. Press `j` again — verify overlay closes (toggle behavior)
5. Verify `Escape` also closes the overlay
6. Verify all existing keybindings still work (no regressions)
7. Test outside tmux: `j` should show warning notification
