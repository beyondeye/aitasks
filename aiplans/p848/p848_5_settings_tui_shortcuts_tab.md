---
Task: t848_5_settings_tui_shortcuts_tab.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_6_documentation_for_customizable_shortcuts.md, aitasks/t848/t848_7_manual_verification_customizable_shortcuts.md, aitasks/t848/t848_8_cascade_reset_to_default.md, aitasks/t848/t848_9_eager_subscope_registration.md
Archived Sibling Plans: aiplans/archived/p848/p848_1_shortcut_registry_and_overrides.md, aiplans/archived/p848/p848_2_label_renderer_and_board_pilot.md, aiplans/archived/p848/p848_3_sweep_remaining_tuis.md, aiplans/archived/p848/p848_4_in_tui_shortcut_editor_modal.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-31 11:33
---

# p848_5 — Settings TUI: Shortcuts tab + export/import integration (verified)

## Context

`t848` makes every TUI shortcut customizable. Children t848_1–t848_4 built the
plumbing: a scope/action→key registry with override resolution
(`keybinding_registry.py`), atomic override persistence into
`userconfig.yaml` (`shortcut_persist.py`), the `(X)`-label renderer, and the
in-TUI `?` editor modal (`ShortcutEditorModal`, edits the *current* TUI's
scope only).

**t848_5** surfaces a cross-scope **Shortcuts tab** in `ait settings` so a user
can browse/edit *every* TUI's bindings in one place, reset a scope to defaults,
lint cross-TUI coherence, and **export/import** their keybindings to share a
layout between machines.

**Settled design decisions (from planning + user feedback):**
- Shortcut overrides live in `aitasks/metadata/userconfig.yaml` under
  `shortcuts:`. That file is NOT in the settings export bundle by default.
- Export/import integrates as a **first-class category in the existing
  settings export/import flow** — NOT a parallel flow. Export emits **only**
  the `shortcuts:` subtree (never the whole `userconfig.yaml` — no email leak);
  import **deep-merges** it (never clobbering local `email`/`last_used_labels`).
- The list widget is a single `DataTable`. Single cohesive feature, effort
  medium — **no child split**.

**Lazy-registration gap (must solve here — confirmed not covered by t848_9):**
`_DEFAULTS` is populated by `register_app_bindings(scope, BINDINGS)`, which runs
only when a class is *instantiated* (`ShortcutsMixin.__init__`,
`shortcuts_mixin.py:41`) or at a class-body/module-level eager call (the `shared`
`j` in `tui_switcher.py:1065`; `brainstorm.dag` in
`brainstorm_dag_display.py:450`). In a standalone `ait settings` process only
`SettingsApp` is constructed, so `_DEFAULTS` holds essentially just `settings` +
`shared`. Every other TUI's scope (board, brainstorm, monitor, codebrowser,
applink, syncer, stats, diffviewer, minimonitor) and their modal sub-scopes are
**absent** → `iter_all_bindings()` would return a near-empty list and the tab
would be useless. t848_9 only makes each App register *its own* sub-scopes for
*its own* `?` editor and is declared "not a dependency of t848_5"; it does NOT
give a settings-only process cross-TUI visibility. **This task builds the global
registration sweep** (decision: build here; t848_9 reuses it).

**Verified facts about the current codebase (2026-05-31):**
- The export bundle is **JSON**, not tar/zst: `config_utils.EXPORT_EXTENSION =
  ".aitcfg.json"`, no `tarfile` usage. `export_all_configs(output_path,
  metadata_dir, patterns=None) -> dict` builds `bundle = {"_export_meta":
  {version, exported_at, file_count}, "files": {<filename>: <json-content>}}`
  and writes it with `json.dump`. `import_all_configs(input_path, metadata_dir,
  overwrite=False, selected_files=None) -> list[str]` iterates
  **`bundle["files"].items()`** and writes each member out as a JSON file under
  `metadata_dir/<name>` (with a path-traversal guard rejecting names containing
  separators). → **Shortcuts must be a top-level bundle key (`bundle["shortcuts"]`),
  a sibling of `_export_meta`/`files` — NOT inside `files`** (a `files` member
  would be written as a file and would fail/!merge).
- Settings tab letter **`s` is free**; `a/b/c/m/p/t` are taken in
  `_TAB_SHORTCUTS`. Tab switching is a raw `on_key` handler (not registered
  Bindings) that does `tabbed.active = _TAB_SHORTCUTS[event.key]`. The footer is
  Textual's registry-derived `Footer()` widget — **no hand-composed footer
  string to edit** (the original task note about "line ~1214 footer" is stale).
- `_handle_import` repopulates agent/board/project/models/profiles but **omits
  `_populate_tmux_tab()`** (a real pre-existing bug to fix while wiring the
  shortcuts repaint).
- Live re-key caveat (from t848_4): `App.refresh_bindings()` does NOT rebuild the
  active keymap in Textual 8.2.7 — saved rebinds apply on next launch. Set the
  same "restart to apply" expectation here; do not attempt live re-key.

## Files to modify

### 0. NEW `.aitask-scripts/lib/shortcut_scopes.py` — global scope manifest + sweep
The foundation that makes the cross-TUI tab possible. A **declared manifest**
of every binding source + a fail-soft sweep that registers them **without
instantiating** any App/Screen (decision: import modules, read class attrs).

- `KNOWN_BINDING_SOURCES` — declared list of **module files only** (NOT
  per-class entries), to minimize the hand-maintained surface and drift:

  | module file | scopes it contributes |
  |---|---|
  | `board/aitask_board.py` | board, board.detail |
  | `lib/agent_command_screen.py` | board.agent_cmd |
  | `brainstorm/brainstorm_app.py` | brainstorm, brainstorm.compare_select |
  | `brainstorm/brainstorm_dag_display.py` | brainstorm.dag (class-body register at line 450) |
  | `codebrowser/codebrowser_app.py` | codebrowser, codebrowser.copypath |
  | `applink/applink_app.py` | applink, applink.pairing, applink.status |
  | `monitor/monitor_app.py` | monitor |
  | `monitor/minimonitor_app.py` | minimonitor |
  | `syncer/syncer_app.py` | syncer |
  | `diffviewer/diffviewer_app.py` | diffviewer |
  | `stats/stats_app.py` | stats |
  | `lib/stale_entry_modal.py` | shared.stale_entry |
  | `lib/tui_switcher.py` | shared (module-level register at line 1065) |

  (`settings` self-registers because `SettingsApp` is the running app.)

- `register_all_known_bindings()` — mirror the **proven import recipe** from
  `tests/test_shortcuts_registry_coverage.sh`: ensure `.aitask-scripts/lib`,
  `.aitask-scripts`, and `.aitask-scripts/codebrowser` are on `sys.path`, then
  for each manifest module `importlib.util.spec_from_file_location(name, path)` +
  `exec_module` (loads by path → no sys.path name-collision). Importing covers
  class-body/module-level registrations (`brainstorm.dag`, `shared`). Then
  **introspect the module's own classes** (`inspect.getmembers(mod,
  inspect.isclass)` filtered to `cls.__module__ == name`) and for any class with
  a truthy `_shortcuts_scope` + a `BINDINGS` list, call
  `keybinding_registry.register_app_bindings(cls._shortcuts_scope, cls.BINDINGS)`
  — **no instantiation**. Introspection (not a hardcoded class list) means a new
  dialog added *inside an existing TUI module* is registered automatically — only
  a brand-new TUI *file* needs a manifest line. Wrap **each module in
  try/except**: one that fails to import (missing optional dep) logs to stderr and
  is skipped, never breaking the tab. `register_app_bindings` is idempotent.
- This lives in its own `lib/` module (NOT in `keybinding_registry.py`) to avoid
  a circular dependency — the TUI modules import `keybinding_registry`, so the
  registry must not import them. The sweep is called lazily at runtime, after
  modules are loadable.

### 1. `.aitask-scripts/lib/keybinding_registry.py` — public all-scopes getter
The editor's `iter_scope_bindings(prefix)` is prefix-filtered; the settings tab
needs *every* binding. Add a sibling that mirrors its shape (avoids reaching into
private `_DEFAULTS` from settings_app):
```python
def iter_all_bindings() -> list[tuple[str, str, str, str]]:
    """Every recorded (scope, action_id, default_key, label), sorted."""
    return sorted(
        ((s, a, dk, lbl) for (s, a), (dk, lbl) in _DEFAULTS.items()),
        key=lambda r: (r[0], r[1]),
    )
```

### 2. `.aitask-scripts/lib/config_utils.py` — shortcuts-only export + merge import
Reuse `load_yaml_config(path)` / `save_yaml_config(path, data)` (both exist).

- **Export** — add `include_shortcuts: bool = False` to `export_all_configs`.
  When set, read `userconfig.yaml` (under `metadata_dir`) via `load_yaml_config`,
  extract ONLY the `shortcuts` subtree, and if non-empty add it as a **top-level
  bundle key**: `bundle["shortcuts"] = <subtree>`. Bump
  `bundle["_export_meta"]["file_count"]`. Never put raw `userconfig.yaml` in the
  bundle.
- **Import** — in `import_all_configs`, after the existing `bundle["files"]`
  loop, handle `bundle.get("shortcuts")`: if present AND
  (`selected_files is None` OR `"shortcuts" in selected_files`), load local
  `userconfig.yaml`, **deep-merge** the subtree (`scope → action_id → key`) into
  its `shortcuts` key, preserving every other local top-level key, and
  `save_yaml_config`. Append `"shortcuts"` to the returned `written` list.
- **Test** — new `tests/test_config_utils_shortcuts.py` (Python unittest, mirror
  `tests/test_config_utils.py`): assert `include_shortcuts=True` round-trips the
  subtree as a top-level bundle key; assert import deep-merges while preserving
  `email`/`last_used_labels`; assert export with no `shortcuts:` present yields no
  `shortcuts` bundle key.

### 3. `.aitask-scripts/settings/settings_app.py` — tab, export category, buttons, wiring
- **Tab pane** — in `compose()` mirror the existing `TabbedContent(...)` pattern:
  add `"Shortcuts"` to the positional title list (after `"Profiles"`) **and** add
  `with TabPane("Shortcuts", id="tab_shortcuts"): yield VerticalScroll(id="shortcuts_content")`
  after the Profiles `TabPane`.
- **Tab letter** — add `"s": "tab_shortcuts"` to `_TAB_SHORTCUTS`. The existing
  `on_key` handler picks it up automatically.
- **Export category** — add `"Shortcuts": ["__shortcuts__"]` (sentinel) to
  `EXPORT_CATEGORIES`. The Export screen auto-generates a checkbox per category,
  so the main Export (`e`) gains a "Shortcuts" checkbox. In `_handle_export`,
  detect the `"__shortcuts__"` sentinel in the selected patterns, strip it, and
  pass `include_shortcuts=True` to `export_all_configs(...)`. (An empty residual
  pattern list → `patterns=[]` → exports zero files + the shortcuts member, i.e.
  a "shortcuts-only" bundle.)
- **`ExportScreen` preset** — add an additive `preset_categories: list[str] |
  None = None` constructor arg; when set, pre-check those category checkboxes in
  its compose (default `None` → unchanged behavior). Used by the tab's "Export
  shortcuts" button to pre-select only "Shortcuts".
- **`ImportScreen` shortcuts entry** — when the loaded bundle has a non-empty
  top-level `bundle["shortcuts"]`, add a selection checkbox (label e.g.
  "shortcuts (keybindings)", value `"shortcuts"`) alongside the per-file
  checkboxes, so the unified Import screen can include/exclude it. Its selection
  flows through `selected_files` into the merge in §2 (no parallel import flow).
- **`_populate_shortcuts_tab(self)`** — first call
  `shortcut_scopes.register_all_known_bindings()` (the global sweep — idempotent,
  safe to call on every repopulate) so `_DEFAULTS` holds every TUI's scopes;
  then query `#shortcuts_content`, `remove_children()`, and mount: a hint `Label`
  ("Enter: edit • r: reset scope • l: lint • restart the TUI to apply"); a
  `Horizontal` of `Button`s (`#btn_sc_reset`, `#btn_sc_export`, `#btn_sc_import`,
  `#btn_sc_lint`); and a `DataTable(id="shortcuts_table", cursor_type="row")`
  with columns **Scope · Action · Current · Default · Label · Origin**, one row
  per `keybinding_registry.iter_all_bindings()` (Current = `resolve_key`;
  Origin = `user` if the override is in `load_user_overrides()` else `default`).
  Encode `scope`+`action_id` in the DataTable row key.
- **`on_mount()`** — add `self._populate_shortcuts_tab()` alongside the other
  `_populate_*_tab()` calls (the sweep runs inside it, before
  `iter_all_bindings()`).
- **Edit a row** — `on_data_table_row_selected` for the shortcuts table →
  `push_screen(ShortcutEditorModal(scope=<row scope>), callback=…)`; on dismiss →
  `keybinding_registry.refresh_all()` + `self._populate_shortcuts_tab()`. (Reuses
  the t848_4 modal unchanged.)
- **Buttons** (`on_button_pressed`):
  - reset → push a new `ResetShortcutsConfirmScreen` (mirror
    `SaveProfileConfirmScreen`; reuse the app-level `#edit_dialog` CSS — these
    screens live in `settings_app.py` and are used only by `SettingsApp`, so
    they need no self-contained CSS) → on confirm
    `shortcut_persist.reset_scope(<selected scope>)` + repopulate. Scope = the
    scope of the currently-selected DataTable row.
  - export → `push_screen(ExportScreen(preset_categories=["Shortcuts"]),
    callback=self._handle_export)` (reuses `_handle_export`).
  - import → `push_screen(ImportScreen(), callback=self._handle_import)`.
  - lint → `keybinding_registry.coherence_lint()` → if warnings, push a small
    read-only `LintResultsScreen` (new; needs a scrollable list, so give it
    minimal self-contained `DEFAULT_CSS`); if empty, `notify("No coherence
    issues")`.
- **`_handle_import`** — after the existing reloads add the currently-missing
  `self._populate_tmux_tab()` (pre-existing omission) **and**
  `keybinding_registry.refresh_all()` + `self._populate_shortcuts_tab()`.
- **Live-apply** — saved rebinds apply on next launch (Textual 8.2.7). The hint
  label + editor toast already say "restart to apply"; do not attempt live re-key.

### 4. Tests
- `tests/test_shortcut_scopes.py` (NEW) — **machine-checked drift guard.** This
  is the answer to "how do we ensure a new dialog gets into the global registry":
  1. **Discover ground-truth scopes from source** — scan `.aitask-scripts/**/*.py`
     for `_shortcuts_scope = "<scope>"` assignments **and** any registration call's
     first string literal via a tolerant pattern like
     `register[_a-z]*bindings\(\s*["']([^"']+)["']` (this catches both
     `register_app_bindings("brainstorm.dag", …)` and the **aliased**
     `_register_shared_bindings("shared", …)` at `tui_switcher.py:1065` — a naive
     `register_app_bindings\(` regex would miss `shared`). This is the
     authoritative set of scopes, derived independently of the manifest.
  2. **Run the sweep** — `keybinding_registry._reset_for_tests()` then
     `register_all_known_bindings()` (fresh process, **no App instantiated**).
  3. **Assert** `discovered_scopes ⊆ registered_scopes`. Any scope declared in
     source but not registered by the sweep FAILS with a message naming the
     missing scope(s) and instructing the dev to add the declaring module file to
     `KNOWN_BINDING_SOURCES` in `lib/shortcut_scopes.py`.
  This catches a new TUI *file* the manifest doesn't list, and (because the sweep
  introspects module classes) a new in-module dialog is covered automatically —
  the guard confirms it. `settings` is excluded from the source-derived set or
  pre-registered in the test (it self-registers via the running App, not the
  sweep).
- `tests/test_settings_shortcuts_tab.py` — Pilot-driven (mirror
  `tests/test_shortcut_editor_modal.py` setup: `sys.path.insert` for
  `.aitask-scripts` + `.aitask-scripts/lib`; chdir into a tempdir with
  `aitasks/metadata/userconfig.yaml`; `keybinding_registry._reset_for_tests()` in
  setUp/tearDown). Cases:
  - tab populated from `iter_all_bindings` including **cross-TUI** scopes
    (assert e.g. a `board` row and a `monitor` row are present even though only
    `SettingsApp` was launched — proves the sweep ran);
  - row edit persists + table redraws (via the editor modal, or direct
    `shortcut_persist` + repopulate);
  - Reset-scope confirm clears that scope's overrides;
  - Lint with a forced drift override returns/lists a warning;
  - "Export shortcuts" (stub the `ExportScreen` dismiss to a temp dir) yields a
    bundle whose top-level `shortcuts` member is **only** the subtree (no
    `email`);
  - "Import shortcuts" of a forged bundle deep-merges and PRESERVES local
    `email`.
- `tests/test_config_utils_shortcuts.py` — see §2.

### 5. `aidocs/tui_conventions.md` — document the registration rule
Add a new `## ` section (near "TUI footer must surface every operation on the
affected tab/screen", a sibling don't-forget-to-wire-it rule) stating: any new
Textual TUI App, or any new modal/sub-screen that sets `_shortcuts_scope` (or
registers a scope via a class-body `register_app_bindings("<scope>", …)`), is
surfaced in **Settings → Shortcuts** via the global sweep in
`.aitask-scripts/lib/shortcut_scopes.py`. A new dialog **inside an existing TUI
module** is picked up automatically (the sweep introspects the module's classes);
a **brand-new TUI module file** MUST be added to `KNOWN_BINDING_SOURCES`. The
`tests/test_shortcut_scopes.py` drift guard fails until it is. (Per CLAUDE.md,
`aidocs/tui_conventions.md` is the read-on-demand doc for "adding keybindings to
an existing TUI" — this rule belongs there.)

## Reuse (do not reinvent)
- `keybinding_registry`: `iter_all_bindings` (new), `resolve_key`,
  `load_user_overrides`, `refresh_all`, `coherence_lint`, `register_app_bindings`.
- the import recipe in `tests/test_shortcuts_registry_coverage.sh`
  (`spec_from_file_location` + `register_class_only`) — the canonical, already-
  passing way to load every TUI module in one process; the new
  `register_all_known_bindings()` reuses that recipe.
- `shortcut_persist`: `reset_scope`, `save_override`, `clear_override`.
- `shortcut_editor_modal.ShortcutEditorModal(scope)` — unchanged.
- `config_utils`: `export_all_configs` / `import_all_configs` (extended),
  `load_yaml_config` / `save_yaml_config`.
- `settings_app`: `ExportScreen` / `ImportScreen` / `_handle_export` /
  `_handle_import`; `SaveProfileConfirmScreen` as the confirm-modal template;
  `EXPORT_CATEGORIES`; the `on_key` tab-switch handler.

## Verification
```bash
python3 tests/test_shortcut_scopes.py                  # global sweep populates all scopes (no instantiation)
python3 tests/test_settings_shortcuts_tab.py
python3 tests/test_config_utils_shortcuts.py
python3 tests/test_shortcut_editor_modal.py            # regression
bash tests/test_keybinding_registry.sh
bash tests/test_shortcuts_registry_coverage.sh
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['.aitask-scripts/lib/keybinding_registry.py','.aitask-scripts/lib/shortcut_scopes.py','.aitask-scripts/lib/config_utils.py','.aitask-scripts/settings/settings_app.py']]; print('PARSE_OK')"
ait settings    # press s → Shortcuts tab shows EVERY TUI's scopes (board, monitor,
                # brainstorm, …) not just settings; Enter a row → edit → "restart
                # to apply"; Reset / Lint / Export / Import buttons
# inspect a focused export bundle (it is JSON, not tar):
python3 -c "import json,glob,os; p=sorted(glob.glob('*.aitcfg.json'),key=os.path.getmtime)[-1]; b=json.load(open(p)); print(list(b.keys()), 'shortcuts' in b)"
grep -c 'email:' aitasks/metadata/userconfig.yaml      # still 1 after an import
```

## Notes for sibling task t848_6 (docs)
Document the export contract precisely: a "Shortcuts" category in the **general**
settings Export (`e`) / Import (`i`) flow emits a derived top-level `shortcuts`
member (the `shortcuts:` subtree only) into the `.aitcfg.json` bundle; import
**deep-merges** it into `userconfig.yaml`, never overwriting
`email`/`last_used_labels`. There is no separate shortcuts-only export/import
action — it is one checkbox category in the existing Export/Import screens, and
`ImportScreen` surfaces a `shortcuts` selection entry when the bundle carries one.

## Notes for sibling task t848_9 (eager sub-scope registration + `?`-as-shared)
This task introduces `lib/shortcut_scopes.py` (`KNOWN_BINDING_SOURCES` +
`register_all_known_bindings()`) — the canonical global scope manifest. t848_9
should **reuse this manifest** rather than building a parallel per-App mechanism:
its eager per-TUI sub-scope goal becomes "ensure the active TUI's own sub-scopes
are registered up front" (a filtered call against the same manifest), and its
required `?`-as-`shared` deliverable is unchanged. t848_9's original framing
("not a dependency of t848_5", favoring per-App approach #2) is superseded by
this shared manifest — flag this in the Final Implementation Notes so the t848_9
task description can be adjusted. Once `?` is registered under `shared` (t848_9),
it will appear once under `shared` in the Settings tab automatically (the
shared-action de-dup in `register_app_bindings` already handles it).

## Post-Review Changes

### Change Request 1 (2026-05-31 — UX fixes on the Shortcuts tab)
- **Requested by user:** Three UX issues: (1) redundant scrollbars — the tab had
  an outer `VerticalScroll` plus the scrollable `DataTable`; (2) the tab did not
  follow the settings nav convention (↑/↓ between options incl. the tab title;
  ←/→ switches tabs when the title is focused) — ↓ from the tab title didn't land
  on the first table row and ↑ at the top didn't return to the tab title;
  (3) buttons should sit at the bottom and have keyboard shortcuts.
- **Changes made:**
  1. The Shortcuts tab content is now a non-scrolling `Vertical(id="shortcuts_content")`
     (was `VerticalScroll`); the `DataTable` is `height: 1fr` and scrolls itself.
     Removed the redundant outer scrollbar.
  2. `_nav_vertical` now treats a focused `DataTable` as the "options" list: ↑/↓
     move the row cursor internally and **hand off at the boundaries** — ↑ at row 0
     focuses the tab title (`Tabs`), ↓ past the last row moves to the buttons.
     Removed the `on_key` early-return guard that previously let the DataTable
     swallow arrows. Entering the tab (via `s` / ↓ from the title) focuses the
     table at row 0.
  3. Buttons moved to the **bottom** (mounted after the table). Each gained a
     footer-visible, shortcut-tab-contextual key: **d** Reset scope, **x** Export
     shortcuts, **o** Import shortcuts, **l** Lint. Gated to the Shortcuts tab via
     a new `SettingsApp.check_action` (hidden from the footer / inert on other
     tabs). Button labels show the key; the hint line lists them.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`,
  `tests/test_settings_shortcuts_tab.py` (added `NavigationTests`: arrow nav
  title↔table, `check_action` gating, `l`→lint, `d`→reset-confirm).

### Change Request 2 (2026-05-31 — button keys: off-footer + inline-rendered labels)
- **Requested by user:** The `d/x/o/l` keys showed in the footer on every tab
  while also having dedicated buttons on the Shortcuts tab — redundant. Keep
  only the buttons (no footer entries), and render each button's label with the
  existing `(X)`-style helper (e.g. `E(x)port shortcuts`), not a trailing `(x)`.
- **Changes made:**
  1. The four `sc_*` `Binding`s are now `show=False` — the keys still work
     (gated to the Shortcuts tab by `check_action`) but never appear in the
     footer. (`check_action`-based hiding alone was insufficient in this Textual
     version; `show=False` is authoritative.)
  2. Button labels now use `shortcut_labels.render_label(text, key)`:
     `(D) Reset scope`, `E(X)port shortcuts`, `Imp(O)rt shortcuts`,
     `(L)int coherence`. Hint line reworded to point at the buttons + their
     parenthesized keys.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`,
  `tests/test_settings_shortcuts_tab.py` (added
  `test_buttons_render_shortcut_key_in_label`, asserting the rendered labels and
  `show=False`).

### Change Request 3 (2026-05-31 — drop redundant Export/Import shortcut buttons)
- **Requested by user:** The tab's dedicated "Export shortcuts" / "Import
  shortcuts" buttons are redundant — the general Export (`e`) / Import (`i`)
  already include the "Shortcuts" bundle category. (User also asked why the
  `(X)` label letter is uppercased: that is the pre-existing t848_2 `(X)plore`
  convention in `shortcut_labels.render_label`, shared by every TUI's button
  labels — left unchanged here; any change is a cross-cutting follow-up.)
- **Changes made:**
  - Removed the `btn_sc_export` / `btn_sc_import` buttons, the `x`/`o`
    (`sc_export`/`sc_import`) bindings, `action_sc_export`/`action_sc_import`,
    their `on_button_pressed` branches, and the `_SHORTCUT_TAB_ACTIONS` entries.
    The tab now has only **Reset scope (d)** and **Lint coherence (l)** buttons.
  - Reverted the `ExportScreen` `preset_categories` constructor arg (now unused)
    — `ExportScreen` is back to its original no-arg form. The "Shortcuts"
    `EXPORT_CATEGORIES` entry + `_handle_export` sentinel handling + the
    `ImportScreen` shortcuts entry all remain (the general e/i flow).
- **Files affected:** `.aitask-scripts/settings/settings_app.py`,
  `tests/test_settings_shortcuts_tab.py` (replaced the preset test with
  `test_general_export_screen_has_shortcuts_category`; trimmed the button-label
  test to the two remaining buttons).

## Final Implementation Notes
- **Actual work done:**
  - **NEW `.aitask-scripts/lib/shortcut_scopes.py`** — `KNOWN_BINDING_SOURCES`
    (declared list of TUI *module files*) + `register_all_known_bindings()`: a
    fail-soft, run-once sweep that imports each module by file path
    (`spec_from_file_location`, mirroring the coverage test's recipe) and
    introspects its classes for `_shortcuts_scope`+`BINDINGS`, registering them
    **without instantiating** any App/Screen. Module import also covers
    class-body/module-level registrations (`brainstorm.dag`, `shared`).
  - `keybinding_registry.iter_all_bindings()` — complete cross-TUI binding list.
  - `config_utils.export_all_configs(include_shortcuts=…)` adds only the
    `shortcuts:` subtree as a top-level bundle member; `import_all_configs`
    deep-merges it into `userconfig.yaml`, preserving `email`/`last_used_labels`.
  - `settings_app.py` — Shortcuts tab (`s`): single `DataTable` of every TUI's
    bindings (sweep runs once in `_populate_shortcuts_tab`, then row-clear/refill
    on repaint), Enter→`ShortcutEditorModal`, bottom buttons **(D) Reset scope**
    / **(L)int coherence** (keys `show=False`, gated by `check_action`,
    labels via `render_label`), arrow-nav integrated with the tab-title↔table
    convention, "Shortcuts" export category (sentinel→`include_shortcuts`),
    `ImportScreen` shortcuts entry, and the pre-existing `_populate_tmux_tab()`
    omission in `_handle_import`/`action_reload_configs` fixed.
  - `aidocs/tui_conventions.md` — "New TUIs / dialogs must register in the
    global shortcut manifest" rule + drift-guard reference.
  - Tests: `test_shortcut_scopes.py` (source-scan drift guard),
    `test_config_utils_shortcuts.py` (6), `test_settings_shortcuts_tab.py` (15).
- **Deviations from plan:** (1) `_populate_shortcuts_tab` builds chrome once and
  clears/refills rows instead of re-mounting (a fixed-id DataTable races the
  deferred `remove_children`). (2) The sweep runs once per app (guard flag) — it
  re-executes module bodies, and `_DEFAULTS` persists for the process. (3)
  `KNOWN_BINDING_SOURCES` lists module files (not per-class entries) + class
  introspection, so in-module dialogs are auto-covered. (4) The dedicated tab
  Export/Import buttons + `ExportScreen.preset_categories` were dropped (CR3) —
  the general `e`/`i` flow's "Shortcuts" category covers it.
- **Issues encountered:** `aitask_board` needs `.aitask-scripts/board` on
  `sys.path` (`task_yaml` sibling) — the sweep adds each manifest module's dir
  (no basename collisions across TUI dirs). Heavy multi-tab repopulate makes
  `pilot.pause()` time out in tests (not a runtime bug — the merge is
  synchronous; tests assert the file directly).
- **Key decisions:** global manifest lives in its own `lib/` module (registry
  must not import TUIs → circular); drift guard scans source so a new
  scope/module fails CI until added; button mnemonics rendered with the existing
  `(X)plore` helper (uppercase letter is that shared t848_2 convention, left
  unchanged).
- **Upstream defects identified:** None. (The `_handle_import` missing
  `_populate_tmux_tab()` repaint was a pre-existing omission in the same file,
  fixed inline here — not a separate follow-up.)
- **Notes for sibling tasks:**
  - **t848_6 (docs):** see "Notes for sibling task t848_6" above — shortcuts
    export/import is the general Export(`e`)/Import(`i`) flow's "Shortcuts"
    category; import deep-merges, never clobbering `email`/`last_used_labels`.
  - **t848_9 (eager sub-scope + `?`-as-shared):** reuse
    `lib/shortcut_scopes.py` (`KNOWN_BINDING_SOURCES` + sweep) instead of a
    parallel per-App mechanism; once `?` registers under `shared`, it appears
    once under `shared` in this tab automatically. t848_9's "not a dependency of
    t848_5" framing is superseded by this shared manifest.

## Post-implementation (workflow)
Step 8 user review (non-skippable) → Step 8b/8c follow-ups → Step 9 child
archival of t848_5 (`./.aitask-scripts/aitask_archive.sh 848_5`). On the verify
path, a `plan_verified` entry is appended to this plan before commit.
