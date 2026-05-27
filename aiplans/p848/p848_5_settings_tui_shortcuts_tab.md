---
Task: t848_5_settings_tui_shortcuts_tab.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_1_*.md, aitasks/t848/t848_2_*.md, aitasks/t848/t848_3_*.md, aitasks/t848/t848_4_*.md, aitasks/t848/t848_6_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
---

# p848_5 — Settings TUI Shortcuts tab + export/import integration

## Goal

Add a cross-scope Shortcuts tab to `ait settings` that reuses the
existing export/import machinery (`export_all_configs` /
`import_all_configs` in `lib/config_utils.py`, surfaced via
`action_export_configs` / `action_import_configs` in `settings_app.py`).

## Files

**New:**

- `tests/test_settings_shortcuts_tab.sh`

**Modified:**

- `.aitask-scripts/lib/config_utils.py` (add optional `userconfig_keys` selector if needed)
- `.aitask-scripts/settings/settings_app.py`

## Step-by-step

### 1. `config_utils.py` selector check

Read `export_all_configs` / `import_all_configs` (lines 196 and 299
respectively). If `patterns=` already supports sub-key selection,
nothing to change. If not, add an optional kwarg:

```python
def export_all_configs(out_path, metadata_dir, patterns=None, userconfig_keys=None):
    # ... existing logic ...
    # When userconfig_keys is set, copy userconfig.yaml into the bundle
    # but containing only those top-level keys.
```

Plus a small unit test asserting the bundle round-trips an injected
`shortcuts:` section both in full-bundle and shortcuts-only modes.

### 2. Settings TUI tab pane

- Add `TabPane("Shortcuts", id="tab-shortcuts")` to the `TabbedContent`
  in `compose` (after Profiles).
- Add `"k"` -> `"tab-shortcuts"` to `_TAB_SHORTCUTS` (line ~143).
- Implement `_populate_shortcuts_tab(self)`:

  ```python
  def _populate_shortcuts_tab(self) -> None:
      pane = self.query_one("#tab-shortcuts", TabPane)
      pane.remove_children()
      table = DataTable(id="shortcuts-table")
      table.add_columns("Scope", "Action", "Current", "Default", "Label", "Origin")
      overrides = keybinding_registry.load_user_overrides()
      for (scope, action), (default_key, label) in sorted(keybinding_registry._DEFAULTS.items()):
          curr = overrides.get(scope, {}).get(action, default_key)
          origin = "user" if (scope, action) in overrides_seen else "default"
          table.add_row(scope, action, curr, default_key, label, origin)
      pane.mount(table)
      pane.mount(
          Horizontal(
              Button(self.label("reset_scope_shortcuts", "Reset scope"), id="btn-shortcuts-reset"),
              Button(self.label("export_shortcuts", "Export shortcuts"), id="btn-shortcuts-export"),
              Button(self.label("import_shortcuts", "Import shortcuts"), id="btn-shortcuts-import"),
              Button(self.label("lint_shortcuts", "Lint coherence"), id="btn-shortcuts-lint"),
          )
      )
  ```

- Wire `on_button_pressed` (or `@on(Button.Pressed, "#btn-shortcuts-*")`):
  - `reset` → confirm + `shortcut_persist.reset_scope(<selected_scope>)`; refresh table.
  - `export` → push `ExportScreen(default_patterns=("userconfig.yaml",), userconfig_keys=("shortcuts",))` and reuse `_handle_export`.
  - `import` → push `ImportScreen()`; reuse `_handle_import`; at the tail add `keybinding_registry.refresh_all(); self._populate_shortcuts_tab()`.
  - `lint` → run `keybinding_registry.coherence_lint()`; push a small results screen showing each warning.
- Wire `DataTable.RowSelected` → push `ShortcutEditorModal(scope=row["Scope"])`. On dismiss, refresh table.

### 3. `_handle_import` extension

Augment the existing `_handle_import` (`settings_app.py:2711-2728`) to
also call:

```python
keybinding_registry.refresh_all()
self._populate_shortcuts_tab()
```

after the other `_populate_*_tab()` calls.

### 4. Test

`tests/test_settings_shortcuts_tab.sh` uses Pilot:

1. Launch `SettingsApp`.
2. Press `k`; assert active tab is `tab-shortcuts` and table is populated.
3. Select a row; press Enter → modal pushes; capture key change; save; assert table redraw.
4. Press `Export shortcuts`; stub `ExportScreen` to return `{directory: <tmp>, patterns: [...]}`; assert bundle is created and contains only `userconfig.yaml` with only the `shortcuts:` key.
5. Press `Import shortcuts`; supply a forged bundle that changes a key; assert `userconfig.yaml` updated and table redrawn.
6. Drift two scopes' `quit` keys; press `Lint coherence`; assert results screen lists the warning.

## Verification

```bash
bash tests/test_settings_shortcuts_tab.sh
ait settings                    # navigate via k to Shortcuts; manual smoke
# verify focused export bundle
zstdcat <newest export.tar.zst> | tar -xOf - userconfig.yaml | head -20   # should contain only `shortcuts:`
# verify full export still includes shortcuts
# (just trigger Settings -> Export and inspect)
shellcheck tests/test_settings_shortcuts_tab.sh
```

## Verification (for the t848_7 manual-verification sibling)

- Settings → Shortcuts tab opens, shows all scopes.
- Editing a row updates the yaml AND the in-TUI button labels in the source TUI on relaunch.
- Export → Import round-trip preserves the change.
- Full Settings → Export also carries the change verbatim.
- Lint surfaces deliberate drift.

## Step 9 — Post-implementation

Standard archival.
