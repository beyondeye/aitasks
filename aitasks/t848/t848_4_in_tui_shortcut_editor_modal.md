---
priority: medium
effort: high
depends: [t848_3]
issue_type: feature
status: Implementing
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-27 17:29
updated_at: 2026-05-30 22:44
---

## Context

Fourth child of t848. Implements the `?`-triggered modal that rebinding any TUI's shortcuts from inside that TUI. After this child, the customization loop is end-to-end without hand-editing yaml.

Depends on t848_1 (registry/persist) and t848_2 (mixin + render API). t848_3 should have already migrated brainstorm's `?` → `H`.

## Key Files to Modify

- **NEW** `.aitask-scripts/lib/shortcut_editor_modal.py`:
  - `class ShortcutEditorModal(ModalScreen)`.
  - Constructor takes `scope: str` (e.g. `"board"`).
  - Composes:
    - Header: `"Shortcuts — <scope>"` plus a help line `"Enter: rebind • r: reset • d: clear override • s: save & close • Esc: cancel"`.
    - `DataTable` columns: Action, Current key, Default key, Label, Origin (`default` / `user`).
    - Footer auto-rendered from modal's own BINDINGS.
  - BINDINGS:
    - `Binding("escape", "cancel", "Cancel")`
    - `Binding("enter", "rebind_row", "Rebind")`
    - `Binding("r", "reset_row", "Reset row")`
    - `Binding("d", "clear_row", "Clear override")`
    - `Binding("s", "save", "Save")`
  - Key capture: on `action_rebind_row`, push a tiny child screen `KeyCaptureScreen` that swallows the next single key event and returns it. Validate against modal's own collision set (other rows in the same scope), highlight collision in red, ask confirm before saving.
  - On `action_save`:
    1. For each pending change, call `shortcut_persist.save_override(scope, action_id, new_key)` or `clear_override(...)` if reset to default.
    2. Call `keybinding_registry.refresh(scope)`.
    3. Call `self.app.refresh_bindings()` (Textual API) — if not available in the installed Textual version, fall back to dismissing the modal with a notification: `"Restart this TUI to apply changes."`.
    4. Dismiss.
  - **Carry its own `DEFAULT_CSS`** (per memory note `feedback_modal_self_contained_css`).

- **NEW** `.aitask-scripts/lib/key_capture_screen.py` (or inline in `shortcut_editor_modal.py`):
  - `class KeyCaptureScreen(ModalScreen[str])` — overrides `on_key`, returns the pressed key combo (`event.key` for single keys; `f"{mod}+{event.key}"` for modifiers). Excludes `escape` (treated as cancel).

- `.aitask-scripts/lib/shortcuts_mixin.py`:
  - Implement `action_open_shortcuts_editor(self)`:
    ```python
    def action_open_shortcuts_editor(self) -> None:
        from .shortcut_editor_modal import ShortcutEditorModal
        self.push_screen(ShortcutEditorModal(scope=self._shortcuts_scope))
    ```
  - Remove the `NotImplementedError` stub from t848_2.

- `.aitask-scripts/brainstorm/brainstorm_app.py`:
  - Verify the `?` → `H` migration from t848_3 is in place. If t848_3 deferred it, perform it here.

- **NEW** `tests/test_shortcut_editor_modal.sh`:
  - Uses Textual's `Pilot` to drive the modal:
    1. Launch a minimal test App with `ShortcutsMixin` and a couple of `Binding`s.
    2. Press `?` → modal appears, table populated.
    3. Move cursor to row, press `Enter`, simulate a key event for a new key, press `s`.
    4. Assert `userconfig.yaml` now contains the override.
    5. Re-open modal, confirm the row's Current key reflects the new value.
    6. Press `d` on the row, press `s`; assert the override disappears from yaml.
    7. Set up an in-scope collision; assert the highlight + confirm flow.

## Reference Files for Patterns

- `.aitask-scripts/lib/tui_switcher.py:TuiSwitcherOverlay` — a modal pushed by a mixin from every TUI. Mirror its CSS-self-containment and key capture style.
- `.aitask-scripts/settings/settings_app.py` `EditConfigScreen` — pattern for a modal that captures user input and writes via a config helper. Reuse the notification idiom (`self.notify("…")`).
- Textual's `DataTable` usage already present in `.aitask-scripts/stats/stats_app.py`.

## Implementation Plan

1. Implement `KeyCaptureScreen` (or inline it).
2. Implement `ShortcutEditorModal` with table populated from `keybinding_registry._DEFAULTS` filtered to scope, plus current overrides.
3. Wire `action_open_shortcuts_editor` in `ShortcutsMixin`.
4. Confirm `app.refresh_bindings()` exists in the project's Textual version (`pip show textual` from `.aitask-scripts/.venv` or whatever the project uses). If not, document the restart-required fallback.
5. Write Pilot-based test.
6. Manually exercise in board, monitor, codebrowser, brainstorm, settings; rebind a visible shortcut and confirm the `(X)` label updates.

## Verification Steps

```bash
bash tests/test_shortcut_editor_modal.sh
bash tests/test_keybinding_registry.sh
bash tests/test_shortcuts_registry_coverage.sh
# manual smoke (defer aggregated checks to manual-verification sibling)
ait board                       # press `?` → modal opens, table filled
# rebind a row, save, exit → ? again to confirm
```

## Notes for sibling tasks

- Record whether `self.app.refresh_bindings()` was sufficient or restart-fallback was required — Settings → Shortcuts tab (t848_5) needs the same answer.
- If `KeyCaptureScreen` rejects certain key combos (e.g. `ctrl+c`), document the list so t848_5 can apply the same allow-list in its row editor.
