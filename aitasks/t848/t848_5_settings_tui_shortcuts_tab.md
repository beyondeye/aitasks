---
priority: medium
effort: medium
depends: [t848_4]
issue_type: feature
status: Implementing
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-27 17:29
updated_at: 2026-05-31 11:34
---

## Context

Fifth child of t848. Adds a Shortcuts tab to the Settings TUI that exposes every scope at once and reuses the **existing** export/import flow (`action_export_configs` / `action_import_configs` in `settings_app.py:2689-2728`, backed by `export_all_configs` / `import_all_configs` in `lib/config_utils.py:196,299`).

Depends on t848_1…t848_4.

Key constraint (from user feedback at planning time): export/import of keybindings must mirror the existing settings export/import, not be a parallel flow. The cleanest way is to keep overrides inside `userconfig.yaml` under `shortcuts:` — the existing bundle then carries them for free. The Shortcuts tab adds a focused "export shortcuts only" / "import shortcuts" pair that reuses the same screens with a preset pattern selector.

## Key Files to Modify

- `.aitask-scripts/lib/config_utils.py`:
  - **No behavior change required** for the bundle — `userconfig.yaml` is already included by `export_all_configs`. Add a small unit test verifying the bundle round-trips an injected `shortcuts:` section.
  - If the existing `export_all_configs(... patterns=...)` selector cannot scope a single yaml's *subkey*, add an optional `userconfig_keys=("shortcuts",)` filter that, when set, copies only those sub-keys into the bundle's `userconfig.yaml`. Keep the default behavior unchanged.

- `.aitask-scripts/settings/settings_app.py`:
  - Add `TabPane("Shortcuts", id="tab-shortcuts")` to the tabs list (after Profiles).
  - Update `_TAB_SHORTCUTS` (line ~143) to map `"k"` → `"tab-shortcuts"` (currently unused).
  - Update the hand-composed footer string at line ~1214 to include the new tab letter (this should already be registry-derived after t848_3).
  - Implement `_populate_shortcuts_tab(self)`:
    - Iterates `keybinding_registry._DEFAULTS` keys grouped by scope.
    - Mounts a `DataTable` per scope (or one big table with a Scope column — pick the latter; matches how Profiles tab presents one table).
    - Columns: Scope, Action, Current key, Default key, Label, Origin.
  - Add buttons inside the tab:
    - `Button(self.app.label("reset_scope", "Reset scope to defaults"), id="btn-shortcuts-reset")` — opens an `AskUserQuestion` equivalent (a small confirm modal — pattern exists in `EditConfigScreen` reuse) then calls `shortcut_persist.reset_scope(<currently-selected-scope>)`.
    - `Button(self.app.label("export_shortcuts", "Export shortcuts"), id="btn-shortcuts-export")` — pushes `ExportScreen()` (existing class) with `default_patterns=["userconfig"]` and `userconfig_keys=("shortcuts",)`. The new param flows through to `export_all_configs`.
    - `Button(self.app.label("import_shortcuts", "Import shortcuts"), id="btn-shortcuts-import")` — pushes `ImportScreen()` and the existing `_handle_import` callback already reloads everything; add a hook in `_handle_import` to also call `keybinding_registry.refresh_all()` and `_populate_shortcuts_tab()`.
    - `Button(self.app.label("lint_shortcuts", "Lint coherence"), id="btn-shortcuts-lint")` — calls `keybinding_registry.coherence_lint()`, pops a results modal listing warnings.
  - Editing a row reuses `ShortcutEditorModal` from t848_4 with the row's scope.

- **NEW** `tests/test_settings_shortcuts_tab.sh`:
  - Pilot-launches `SettingsApp`, switches to Shortcuts tab via `k`, asserts table populated.
  - Triggers edit of a row, asserts yaml + table redraw.
  - Triggers "Export shortcuts" via the button (using a mock `ExportScreen` dismiss returning a temp directory), asserts the resulting bundle contains the `shortcuts:` section verbatim and no other keys from `userconfig.yaml`.
  - Triggers "Import shortcuts" on a forged bundle, asserts table redraws to new state.
  - Triggers "Lint" with a forged drift override, asserts the results modal lists it.

## Reference Files for Patterns

- `.aitask-scripts/settings/settings_app.py` lines 1121-1166 (BINDINGS + tabs structure), 1214 (footer), 2689-2728 (export/import handlers), 352-396 (`ConfigManager`).
- `.aitask-scripts/lib/config_utils.py` lines 196-310 (`export_all_configs` / `import_all_configs`).
- t848_4 `ShortcutEditorModal` — the row-editor modal is unchanged here.

## Implementation Plan

1. Confirm by reading whether `export_all_configs` already accepts a `patterns` selector fine-grained enough; if it operates on whole files, extend it with `userconfig_keys` as described above. Single targeted change in `config_utils.py`.
2. Add the new tab pane and `_populate_shortcuts_tab` method. Add tab letter `k`.
3. Wire the four buttons. Reuse existing `ExportScreen` / `ImportScreen`; add the optional `default_patterns` / `userconfig_keys` constructor args.
4. Hook `_handle_import` to refresh the registry + shortcuts tab.
5. Write Pilot test.
6. Manually verify: edit a key, full Settings → Export → Import round-trip carries the change; Settings → "Export shortcuts" produces a bundle containing only the `shortcuts:` portion.

## Verification Steps

```bash
bash tests/test_settings_shortcuts_tab.sh
bash tests/test_keybinding_registry.sh
bash tests/test_shortcut_editor_modal.sh
ait settings                    # navigate to Shortcuts tab via k
                                # edit a row, export, import; observe persistence
# inspect the produced bundle
ls -1 /tmp | grep aitasks_config_export_   # newest export
zstdcat <bundle> | tar -tvf -              # verify only userconfig.yaml present in "shortcuts-only" export
shellcheck tests/test_settings_shortcuts_tab.sh
```

## Notes for sibling tasks

- Record the exact selector-API decision (`patterns=`, `userconfig_keys=`, or a new combination) — t848_6 docs must describe what "Export shortcuts only" actually produces.
- If `ExportScreen` / `ImportScreen` ended up needing extra constructor params, document the back-compat path (default args).
