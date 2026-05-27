---
Task: t848_2_label_renderer_and_board_pilot.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_1_*.md, aitasks/t848/t848_3_*.md, aitasks/t848/t848_4_*.md, aitasks/t848/t848_5_*.md, aitasks/t848/t848_6_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
---

# p848_2 — Label renderer + ShortcutsMixin + board pilot

## Goal

Build `(X)plore`-style label renderer + `ShortcutsMixin`, then migrate
the board TUI end-to-end as proof. After this child, picking the board
button labels reflect the active binding key from t848_1's registry,
including when the user has overridden the key.

## Files

**New:**

- `.aitask-scripts/lib/shortcut_labels.py`
- `.aitask-scripts/lib/shortcuts_mixin.py`
- `tests/test_shortcut_labels.sh`
- `tests/test_shortcut_labels_golden/*` (one expected-output file per case)

**Modified:**

- `.aitask-scripts/board/aitask_board.py`

## Step-by-step

### 1. `shortcut_labels.py`

```python
def render_label(text: str, key: str) -> str:
    """
    Wrap the first case-insensitive occurrence of `key` (single char) in
    `text` with parentheses, capitalizing the wrapped char. Fallback if
    no match: append ` (K)`. Multi-key combos (anything containing `+`
    or with len(key) > 1) always use the fallback form, rendered as
    ` (Display)` (e.g. `ctrl+r` -> ` (Ctrl+R)`).
    """

def display_form(key: str) -> str:
    """`ctrl+r` -> `Ctrl+R`, `a` -> `A`."""
```

Edge cases (documented in module docstring):
- Empty `key` -> return `text` unchanged.
- `key` not in `text`, single char -> ``text + " (" + key.upper() + ")"``.
- First-match rule: first occurrence anywhere (including mid-word).

### 2. `shortcuts_mixin.py`

```python
from textual.binding import Binding
from .keybinding_registry import register_app_bindings, resolve_key
from .shortcut_labels import render_label

class ShortcutsMixin:
    _shortcuts_scope: str = ""  # subclasses MUST override

    SHORTCUTS_MIXIN_BINDINGS = [
        Binding("?", "open_shortcuts_editor", "Keys"),
    ]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if not self._shortcuts_scope:
            raise RuntimeError("ShortcutsMixin subclass must set _shortcuts_scope")
        # Mutate in place so Textual's class-attribute scan sees the rewrite.
        self.BINDINGS = register_app_bindings(self._shortcuts_scope, self.BINDINGS)

    def label(self, action_id: str, text: str) -> str:
        key = resolve_key(self._shortcuts_scope, action_id) or ""
        return render_label(text, key)

    def action_open_shortcuts_editor(self) -> None:
        raise NotImplementedError("Implemented in t848_4")
```

### 3. Board pilot — `aitask_board.py`

- Class declaration:
  ```python
  class KanbanApp(TuiSwitcherMixin, ShortcutsMixin, App):
      _shortcuts_scope = "board"
      BINDINGS = [
          *TuiSwitcherMixin.SWITCHER_BINDINGS,
          *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
          Binding("q", "quit", "Quit"),
          ...  # unchanged
          # Newly-added bindings for previously-button-only actions:
          Binding("l", "lock", "Lock", show=False),
          Binding("u", "unlock", "Unlock", show=False),
          Binding("v", "view_plan", "View Plan", show=False),
          # save/revert/edit/rename/delete have existing or n/a bindings — audit case-by-case.
      ]
  ```

- Button label replacements at `aitask_board.py:2262-2282`:
  ```python
  yield Button(self.app.label("pick_task", "Pick"), variant="warning", id="btn_pick", ...)
  yield Button(self.app.label("brainstorm_task", "Brainstorm"), variant="primary", id="btn_brainstorm", ...)
  yield Button("\U0001f512 " + self.app.label("lock", "Lock"), variant="primary", id="btn_lock", ...)
  yield Button("\U0001f513 " + self.app.label("unlock", "Unlock"), variant="warning", id="btn_unlock", ...)
  yield Button(self.app.label("close_detail", "Close"), variant="default", id="btn_close", ...)
  yield Button(self.app.label("view_plan", "View Plan"), variant="primary", id="btn_view", ...)
  yield Button(self.app.label("save_changes", "Save Changes"), variant="success", id="btn_save", ...)
  yield Button(self.app.label("revert", "Revert"), variant="error", id="btn_revert", ...)
  yield Button(self.app.label("edit", "Edit"), variant="primary", id="btn_edit", ...)
  yield Button(self.app.label("rename", "Name"), variant="primary", id="btn_rename", ...)
  yield Button(self.app.label("delete_archive", "Delete/Archive"), variant="error", id="btn_delete", ...)
  ```

- Audit the rest of `aitask_board.py` for `Button(` literals with
  `\([A-Za-z]\)` and migrate them too.

### 4. Tests

`tests/test_shortcut_labels.sh`:
- For each case, run a Python one-liner that imports `render_label` and
  compares output to a committed golden file under
  `tests/test_shortcut_labels_golden/<case>.txt`.

Golden cases:
- `pick_p.txt` -> `(P)ick`
- `pick_P.txt` -> `(P)ick`
- `pick_o.txt` -> `Pick (O)`
- `toggle_children_x.txt` -> `Toggle Children` with first-match wrap (record exact output to lock the rule)
- `move_right_ctrl_r.txt` -> `Move Right (Ctrl+R)`
- `empty_key.txt` -> `Foo`

## Verification

```bash
bash tests/test_shortcut_labels.sh
ait board                       # buttons render with default keys
echo "shortcuts:" >> aitasks/metadata/userconfig.yaml
echo "  board:" >> aitasks/metadata/userconfig.yaml
echo "    pick_task: o" >> aitasks/metadata/userconfig.yaml
ait board                       # (P)ick now reads Pick (O)
# clean up
yq -i 'del(.shortcuts)' aitasks/metadata/userconfig.yaml
```

## Verification (for the t848_7 manual-verification sibling)

- `ait board` shows `(P)ick`-style labels driven by current bindings.
- Editing `userconfig.yaml` updates the labels on relaunch.
- All other board behavior unchanged (no regression in detail screen).

## Step 9 — Post-implementation

Standard archival.
