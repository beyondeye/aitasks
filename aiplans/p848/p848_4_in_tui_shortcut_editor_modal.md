---
Task: t848_4_in_tui_shortcut_editor_modal.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_1_*.md, aitasks/t848/t848_2_*.md, aitasks/t848/t848_3_*.md, aitasks/t848/t848_5_*.md, aitasks/t848/t848_6_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
---

# p848_4 — `?` shortcut editor modal (in-TUI)

## Goal

Implement the `ShortcutEditorModal` pushed by `ShortcutsMixin` when the
user presses `?`. After this child, end-to-end rebinding works from
inside any TUI without hand-editing yaml.

## Files

**New:**

- `.aitask-scripts/lib/shortcut_editor_modal.py`
- `.aitask-scripts/lib/key_capture_screen.py`
- `tests/test_shortcut_editor_modal.sh`

**Modified:**

- `.aitask-scripts/lib/shortcuts_mixin.py` (replace stub `action_open_shortcuts_editor`)

## Step-by-step

### 1. `key_capture_screen.py`

```python
class KeyCaptureScreen(ModalScreen[str | None]):
    """One-shot key capture. Returns the key combo or None on Esc."""
    BINDINGS = []  # we override on_key directly
    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
            return
        # Build combo string like Textual: "ctrl+r", "shift+down", etc.
        self.dismiss(event.key)
```

Carries its own `DEFAULT_CSS` for the centered prompt overlay.

### 2. `shortcut_editor_modal.py`

```python
class ShortcutEditorModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "rebind_row", "Rebind"),
        Binding("r", "reset_row", "Reset row"),
        Binding("d", "clear_row", "Clear override"),
        Binding("s", "save", "Save"),
    ]
    DEFAULT_CSS = "..."

    def __init__(self, scope: str): ...
    def compose(self): ...  # Header label, DataTable, Footer
    def _populate_table(self): ...  # rows from registry filtered to scope
    def _pending: dict[action_id, new_key]  # accumulated edits before save
    def action_rebind_row(self): await self.app.push_screen(KeyCaptureScreen(), self._on_key_captured)
    def _on_key_captured(self, key): ...  # update pending + redraw row, color red on collision
    def action_reset_row(self): ...  # mark row "reset to default" in pending
    def action_clear_row(self): ...   # remove override in pending
    def action_save(self):
        for action_id, key in self._pending.items():
            shortcut_persist.save_override(self._scope, action_id, key)
        keybinding_registry.refresh(self._scope)
        try:
            self.app.refresh_bindings()
            self.notify("Shortcuts updated")
        except Exception:
            self.notify("Restart the TUI to fully apply changes", severity="warning")
        self.dismiss()
```

Collision detection inside the modal: maintain `effective_key_map: dict[key, action_id]`; flag duplicates with `add_class("collision")` on the row's key cell.

### 3. Mixin

```python
def action_open_shortcuts_editor(self) -> None:
    from .shortcut_editor_modal import ShortcutEditorModal
    self.push_screen(ShortcutEditorModal(scope=self._shortcuts_scope))
```

### 4. Confirm `app.refresh_bindings()` availability

Run from the project's Textual:

```bash
python3 -c "from textual.app import App; print(hasattr(App, 'refresh_bindings'))"
```

If `False`, fall back to the notify-restart path documented above.

### 5. `tests/test_shortcut_editor_modal.sh`

Use `Pilot` to drive a minimal test App:
1. Compose a tiny App with `ShortcutsMixin` and two `Binding`s.
2. Press `?` → modal mounts; assert table rows match registered bindings.
3. Move to row 1, press Enter → `KeyCaptureScreen` pushes.
4. Simulate `o` keystroke; capture screen dismisses with `"o"`; row redraws.
5. Press `s` → modal dismisses; assert `userconfig.yaml` now has `{shortcuts: {<scope>: {<action>: "o"}}}`.
6. Re-open modal; assert Current key is `o`.
7. Press `d` on the row, then `s`; assert override cleared from yaml.
8. Manufacture a collision (override two actions to `o`); assert collision class applied; pressing `s` shows a confirm modal — capture and accept; assert save proceeds.

## Verification

```bash
bash tests/test_shortcut_editor_modal.sh
bash tests/test_keybinding_registry.sh
bash tests/test_shortcuts_registry_coverage.sh
# Manual: ait board → ? → edit a row → save → label updates immediately (or after restart per fallback path)
shellcheck tests/test_shortcut_editor_modal.sh
```

## Verification (for the t848_7 manual-verification sibling)

- `?` opens the editor in every TUI; table only shows that TUI's actions.
- Rebind a visible action (e.g. board → Pick); confirm `(P)ick` label updates.
- Reset and Clear flows work.
- Save under a collision triggers the confirm prompt and saves only on accept.

## Step 9 — Post-implementation

Standard archival.
