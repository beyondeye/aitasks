---
Task: t848_5_settings_tui_shortcuts_tab.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_1_*.md, aitasks/t848/t848_2_*.md, aitasks/t848/t848_3_*.md, aitasks/t848/t848_4_*.md, aitasks/t848/t848_6_*.md
Archived Sibling Plans: aiplans/archived/p848/p848_*_*.md
Worktree: (current directory — fast profile)
Branch: main
Base branch: main
---

# p848_5 — Settings TUI: Shortcuts tab + export/import integration

> ## ⚠️ RE-RUN GUIDANCE — read first (aborted run, 2026-05-31)
>
> A first implementation run completed the code and all tests passed, **but it
> was aborted before commit** because the agent's tool channel degraded badly
> (file reads returned fabricated content; a batch of historical tool calls
> replayed/cancelled). All working-tree changes from that run were **discarded**;
> nothing was committed to `main`. Task ownership/lock and any plan bookkeeping
> from that run should be treated as suspect — re-verify on resume.
>
> **What that run learned (carry into the re-run):**
> 1. **The export bundle is JSON, not tar/zst.** `config_utils.EXPORT_EXTENSION
>    = ".aitcfg.json"` and `config_utils.py` contains **no `tarfile` usage**.
>    Earlier drafts (and a sub-agent report) wrongly described a `.tar.zst`
>    tarball with `tarfile.TarInfo` members — that was a hallucination. Integrate
>    shortcuts into the **JSON bundle structure** that `export_all_configs`
>    builds/returns (a dict written as JSON), and have `import_all_configs`
>    merge it back. Read those two functions first and match their actual member
>    representation.
> 2. **Do NOT use `zstdcat … | tar` to inspect a bundle** — it's a `.aitcfg.json`
>    file; inspect it as JSON.
> 3. The settings tab letter `s` is free; `_TAB_SHORTCUTS` letters a/b/c/m/p/t
>    are taken; tab switching is via a raw-key handler (not registered Bindings).
> 4. The rest of the architecture below was validated by passing tests in the
>    aborted run (8 settings-tab Pilot tests + 4 config_utils tests + 14 editor
>    regression tests) — the approach is sound; only the bundle-format details
>    above needed correcting.
> 5. Run in a **healthy session**; verify each edit with `python3 -c "import ast"`
>    + `grep -c` (these stayed reliable even while file reads were corrupted).

## Context

`t848` makes every TUI shortcut customizable. Children t848_1–t848_4 built the
plumbing (registry + override persistence + the `(X)`-label renderer + the
in-TUI `?` editor modal). **t848_5** surfaces a cross-scope **Shortcuts tab** in
`ait settings` so a user can browse/edit *every* TUI's bindings in one place
(not just the current TUI's, as the `?` editor does), reset a scope to
defaults, lint cross-TUI coherence, and **export/import** their keybindings —
sharing a customized layout between machines.

**Corrected premise:** shortcut overrides live in `aitasks/metadata/userconfig.yaml`
under `shortcuts:`, alongside per-user `email:` / `last_used_labels:`. That file
is NOT in the settings export bundle by default. The user's decision is to
**integrate shortcuts as a first-class export/import category**, exporting
**only** the `shortcuts:` subtree (never the whole userconfig — no email leak)
and **merging** it on import (never clobbering local `email`/`last_used_labels`).

User decisions (settled): (1) export/import = integrate as a category now;
(2) list widget = a single `DataTable`. Single cohesive feature, effort medium —
**no child split**.

## Files to modify

### 1. `.aitask-scripts/lib/keybinding_registry.py` — public all-scopes getter
The editor's `iter_scope_bindings(prefix)` is prefix-filtered; the settings tab
needs *every* binding. Add a sibling (mirrors its shape; avoids reaching into
private `_DEFAULTS`):
```python
def iter_all_bindings() -> list[tuple[str, str, str, str]]:
    """Every recorded (scope, action_id, default_key, label), sorted."""
    return sorted(
        ((s, a, dk, lbl) for (s, a), (dk, lbl) in _DEFAULTS.items()),
        key=lambda r: (r[0], r[1]),
    )
```

### 2. `.aitask-scripts/lib/config_utils.py` — shortcuts-only export + merge import
**Read the real functions first.** `EXPORT_EXTENSION = ".aitcfg.json"` — the
bundle is a **JSON document**, not a tar. `export_all_configs(output_path,
metadata_dir, patterns=None) -> dict` assembles a `bundle` dict (with an
`_export_meta`) and writes it as JSON. `import_all_configs(input_path,
metadata_dir, overwrite=False, selected_files=None) -> list[str]` reads that
JSON and writes the files back out. `load_yaml_config(path)->dict` (returns {}
if missing) and `save_yaml_config(path, data)` are the yaml helpers to reuse.

- **Export** — add `include_shortcuts: bool = False`. When set, read
  `userconfig.yaml` via `load_yaml_config`, extract ONLY the `{"shortcuts": …}`
  subtree, and add it to the JSON bundle as its own member (match how other
  members are keyed in the bundle dict — e.g. a `shortcuts.yaml` / `shortcuts`
  entry). Never put the raw `userconfig.yaml` in the bundle. Bump the
  `_export_meta` file count.
- **Import** — when the bundle carries that shortcuts member (and it's selected,
  or no selection given), **deep-merge** the subtree (`scope → action_id → key`)
  into the local `userconfig.yaml` via `load_yaml_config`/`save_yaml_config`,
  preserving every other local top-level key. Always merge; never overwrite
  siblings.
- Add a `tests/test_config_utils*` case (match the existing convention — there
  is a `tests/test_config_utils.py`): assert `include_shortcuts=True` round-trips
  the subtree and that import merges while preserving `email`/`last_used_labels`.

### 3. `.aitask-scripts/settings/settings_app.py` — the tab, buttons, wiring
- **Tab pane** — in `compose()` add `TabPane("Shortcuts", id="tab_shortcuts")`
  holding a `VerticalScroll(id="shortcuts_content")`.
- **Tab letter** — add `"s": "tab_shortcuts"` to `_TAB_SHORTCUTS` (`s` free).
- **Export category** — add a `"Shortcuts"` entry to `EXPORT_CATEGORIES`
  (use a sentinel like `["__shortcuts__"]`); in `_handle_export`, detect the
  sentinel in the selected patterns, remove it, and pass `include_shortcuts=True`
  to `export_all_configs`. The main Export screen (`e`) then gains a "Shortcuts"
  checkbox — same flow, no parallel path.
- **`_populate_shortcuts_tab(self)`** — query `#shortcuts_content`,
  `remove_children()`, then mount: a hint `Label` ("Enter: edit • r: reset scope
  • l: lint • restart the TUI to apply"); a `Horizontal` of Buttons
  (`#btn_sc_reset`, `#btn_sc_export`, `#btn_sc_import`, `#btn_sc_lint`); and a
  `DataTable(id="shortcuts_table", cursor_type="row")` with columns
  **Scope·Action·Current·Default·Label·Origin**, one row per
  `keybinding_registry.iter_all_bindings()` (Current = `resolve_key`; Origin =
  `user` if the override is in `load_user_overrides()` else `default`). Encode
  scope+action in the DataTable row key.
- **`on_mount()`** — call `self._populate_shortcuts_tab()` alongside the other
  `_populate_*_tab()` calls.
- **Edit a row** — `on_data_table_row_selected` for the shortcuts table →
  `push_screen(ShortcutEditorModal(scope=<row scope>), callback=…)`; on dismiss
  → `keybinding_registry.refresh_all()` + repopulate. (Reuses t848_4 unchanged.)
- **Buttons** (`on_button_pressed`): reset → a new `ResetShortcutsConfirmScreen`
  (mirror `SaveProfileConfirmScreen`, self-contained CSS) → `shortcut_persist.reset_scope(scope)`
  + repopulate; export → `ExportScreen` pre-selecting only the Shortcuts category
  (add an additive `preset_categories` arg), reuse `_handle_export`; import →
  `ImportScreen`, reuse `_handle_import`; lint → `coherence_lint()` → a small
  read-only `LintResultsScreen` (new, self-contained CSS) or `notify("No
  coherence issues")` when empty.
- **`_handle_import`** — after the existing reloads add
  `keybinding_registry.refresh_all()` + `self._populate_shortcuts_tab()` (and the
  currently-missing `self._populate_tmux_tab()` — a real pre-existing omission).
- **Live-apply caveat** — per t848_4, `refresh_bindings()` does NOT rebuild the
  keymap in Textual 8.2.7; edits persist but apply on next launch. The hint
  label + editor toast already say "restart to apply"; do not attempt live re-key.

### 4. Tests
- `tests/test_settings_shortcuts_tab.py` — Pilot-driven (mirror
  `tests/test_shortcut_editor_modal.py` setup). Cases: tab populated from
  `iter_all_bindings`; row edit persists + redraws; Reset-scope confirm clears
  the override; Lint with forced drift lists a warning; "Export shortcuts"
  (stub the screen dismiss) yields a bundle whose shortcuts member is **only**
  the subtree (no `email`); "Import shortcuts" of a forged bundle merges and
  PRESERVES the local `email`.
- config_utils unit test (see §2).

## Reuse (do not reinvent)
- `keybinding_registry`: `iter_all_bindings` (new), `resolve_key`,
  `load_user_overrides`, `refresh_all`, `coherence_lint`.
- `shortcut_persist`: `reset_scope`, `save_override`, `clear_override`.
- `shortcut_editor_modal.ShortcutEditorModal(scope)` — unchanged.
- `config_utils`: `export_all_configs` / `import_all_configs` (extended),
  `load_yaml_config` / `save_yaml_config`.
- settings_app: `ExportScreen` / `ImportScreen` / `_handle_export` /
  `_handle_import`; `SaveProfileConfirmScreen` as the confirm-modal template.

## Verification
```bash
python3 tests/test_settings_shortcuts_tab.py
python3 tests/test_config_utils_shortcuts.py      # (or your config_utils test name)
python3 tests/test_shortcut_editor_modal.py        # regression
bash tests/test_keybinding_registry.sh
bash tests/test_shortcuts_registry_coverage.sh
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['.aitask-scripts/lib/keybinding_registry.py','.aitask-scripts/lib/config_utils.py','.aitask-scripts/settings/settings_app.py']]; print('PARSE_OK')"
ait settings        # press s → Shortcuts tab; Enter a row → edit → "restart to apply"; Reset/Lint/Export/Import
# inspect a focused export bundle (it is JSON, not tar):
python3 -c "import json,glob,os; p=sorted(glob.glob('*.aitcfg.json'),key=os.path.getmtime)[-1]; b=json.load(open(p)); print([k for k in b]);"
grep -c 'email:' aitasks/metadata/userconfig.yaml   # still 1 after an import
```

## Found issues from the aborted run (2026-05-31)
- **Tooling/env (not a code defect):** the agent's file-read channel returned
  fabricated source content mid-run; this seeded a false "uncompressed-tar-
  despite-.tar.zst" defect and tar-based export wording. Corrected above. No
  follow-up bug task was filed (verified the defect does not exist: export is
  `.aitcfg.json` JSON, zero `tarfile` usage).
- **Real, in-scope:** `_handle_import` previously repopulated agent/board/project/
  models/profiles but **omitted tmux** — fix it while wiring the shortcuts repaint.
- No genuine upstream/pre-existing defects identified in unrelated code.

## Post-implementation (workflow)
Step 8 user review (non-skippable) → Step 9 child archival of t848_5
(`./.aitask-scripts/aitask_archive.sh 848_5`). On the verify path, append a
`plan_verified` entry to this plan before commit (this file intentionally carries
no `plan_verified` entry so a resume re-verifies against the corrected plan).
Note for **t848_6 (docs)**: the export contract — a "Shortcuts" category exports
a derived shortcuts member (subtree only) into the `.aitcfg.json` bundle, and
import **merges** it, never overwriting `email`/`last_used_labels`.
