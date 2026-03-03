---
Task: t292_finalize_ait_settings_export_import.md
Worktree: (none — working on current branch)
Branch: (current branch)
Base branch: main
---

## Context

The `ait settings` TUI has export/import features that are functional but lack polish and hardening. Before documenting the settings TUI (task t291), these features need to be finalized:

1. **Export** dumps all configs to CWD with no user control over destination or subset
2. **Import** uses a raw text input for file path — no file discovery, no format identification
3. **Import validation** is minimal — no schema checking, no preview of what will be imported
4. **"Raw" operation** in Agent defaults tab has no documentation/description in the TUI

## Plan

### 1. Change export file extension to `.aitcfg.json`

**Files:** `aiscripts/lib/config_utils.py`, `aiscripts/settings/settings_app.py`

- In `settings_app.py:1864`, change the filename pattern from `aitasks_config_export_{timestamp}.json` to `aitasks_config_export_{timestamp}.aitcfg.json`
- Add a constant `EXPORT_EXTENSION = ".aitcfg.json"` in `config_utils.py` for reuse

### 2. Add ExportScreen modal with destination and subset options

**File:** `aiscripts/settings/settings_app.py`

Create a new `ExportScreen(ModalScreen)` class (similar to `ImportScreen`) with:
- **Directory field**: `Input` pre-filled with `"."` (current directory), user can change
- **Subset checkboxes** using `CycleField` (yes/no) for each category:
  - "Agent defaults" (patterns: `*_config.json`, `*_config.local.json`)
  - "Model configs" (patterns: `models_*.json`, `models_*.local.json`)
  - All default to "yes"
- **Export button** + **Cancel button**

Update `action_export_configs()` to push `ExportScreen` instead of exporting directly. Add a `_handle_export()` callback that:
- Builds the pattern list based on selected subsets
- Constructs the output path from directory + timestamped filename
- Calls `export_all_configs()` with the filtered patterns

Update `export_all_configs()` in `config_utils.py` to accept patterns parameter (already does — no change needed).

### 3. Improve ImportScreen with file discovery and selective import

**File:** `aiscripts/settings/settings_app.py`

Replace the current `ImportScreen` with a multi-step flow:

**Step 1 — File selection:**
- **Discovered files list**: On mount, scan CWD and project root for `*.aitcfg.json` files (also legacy `aitasks_config_export_*.json`). Show them as selectable items.
- **Manual path input**: Keep an `Input` field as fallback for typing a custom path
- **Proceed button** to move to step 2

**Step 2 — File selection (which configs to import):**
After a valid bundle file is selected, parse it and show:
- Bundle metadata: version, export date, total file count
- **Per-file toggle** (CycleField yes/no) for each config file in the bundle, with:
  - File name
  - Description of what the file contains (from a `CONFIG_FILE_DESCRIPTIONS` dict)
  - Status indicator: "new" if doesn't exist locally, "exists (will overwrite)" if it does
- **Global overwrite toggle**: yes/no (same as current)
- **Import button** + **Cancel button**

Add a `CONFIG_FILE_DESCRIPTIONS` dict:
```python
CONFIG_FILE_DESCRIPTIONS = {
    "board_config.json": "Board columns and display settings (shared/project)",
    "board_config.local.json": "Board user preferences (auto-refresh, sync)",
    "codeagent_config.json": "Default AI models per operation (shared/project)",
    "codeagent_config.local.json": "User-specific AI model overrides",
    "models_claudecode.json": "Claude Code model list and verification scores",
    "models_codex.json": "Codex CLI model list and verification scores",
    "models_geminicli.json": "Gemini CLI model list and verification scores",
    "models_opencode.json": "OpenCode model list and verification scores",
}
```

Implementation:
- Add `_scan_export_files()` method using `Path.cwd().glob("*.aitcfg.json")` + legacy pattern
- Replace single-screen modal with a two-step flow (show/hide containers within same screen)
- The callback result includes: `path`, `overwrite`, and `selected_files` (list of filenames to import)

Update `import_all_configs()` in `config_utils.py` to accept an optional `selected_files: list[str] | None` parameter. When provided, only import files in that list (skip others).

### 4. Harden import validation

**File:** `aiscripts/lib/config_utils.py`

Add a `validate_export_bundle(bundle: dict) -> list[str]` function that returns a list of warnings/errors:
- Check `_export_meta` exists and is a dict
- Check `version` field exists and is a supported version (currently only `1`)
- Check `files` key exists and is a dict
- For each file in `files`:
  - Check value is a dict (not string, list, etc.)
  - Check filename matches one of `DEFAULT_EXPORT_PATTERNS` (warn if unexpected filename)
  - Skip `_error` entries (existing behavior)
- Return warnings list (empty = valid)

Call `validate_export_bundle()` in `import_all_configs()` before writing files. Raise `ValueError` for critical errors (missing `files` key — already done), log warnings for non-critical issues.

Also call it in `ImportScreen` preview to show validation status.

### 5. Add operation descriptions in Agent defaults tab

**File:** `aiscripts/settings/settings_app.py`

Add a dict of operation descriptions:
```python
OPERATION_DESCRIPTIONS = {
    "task-pick": "Model used for picking and implementing tasks",
    "explain": "Model used for explaining/documenting code",
    "batch-review": "Model used for batch code review operations",
    "raw": "Model used for direct/ad-hoc code agent invocations (passthrough mode)",
}
```

In `_populate_agent_tab()`, after each operation's project+user rows, add a dim description label:
```python
desc = OPERATION_DESCRIPTIONS.get(key, "")
if desc:
    container.mount(Label(f"[dim italic]{desc}[/dim italic]", classes="op-desc"))
```

Also update the section hint at the top of the Agent tab to mention that each operation has a description.

### 6. Update seed config

**File:** `seed/codeagent_config.json`

No structural changes needed — the "raw" operation is already present. The documentation will come from the TUI itself.

### 7. Update tests

**File:** `tests/test_config_utils.py`

- Add test for `validate_export_bundle()` — valid bundle, missing meta, bad version, non-dict file entries
- Add test for `.aitcfg.json` extension in export filename
- Add test for pattern filtering in export (subset selection)

## Files to Modify

| File | Changes |
|------|---------|
| `aiscripts/lib/config_utils.py` | Add `EXPORT_EXTENSION`, `validate_export_bundle()`, `selected_files` param to `import_all_configs()` |
| `aiscripts/settings/settings_app.py` | New `ExportScreen`, improved `ImportScreen`, operation descriptions, updated `action_export_configs()` |
| `tests/test_config_utils.py` | New tests for validation, extension, and selective import |

## Verification

1. Run existing tests: `python3 -m pytest tests/test_config_utils.py -v`
2. Run new validation tests
3. Manual TUI testing:
   - `./ait settings` → press `e` → verify ExportScreen shows with directory + subset options
   - Export with defaults → verify `.aitcfg.json` file created
   - Export with subset deselected → verify fewer files in bundle
   - Press `i` → verify discovered `.aitcfg.json` files shown, also legacy `.json` files
   - Select a bundle → verify step 2 shows per-file toggles with descriptions and exists/new status
   - Deselect some files → verify only selected files are imported
   - Import the exported file → verify success notification
   - Check Agent defaults tab → verify operation descriptions shown
   - Try importing a malformed JSON file → verify error handling
   - Try importing a file missing `_export_meta` → verify warning

## Final Implementation Notes
- **Actual work done:** All 7 plan items implemented as designed. Export uses new `.aitcfg.json` extension, ExportScreen allows directory and category selection, ImportScreen has two-step flow with file discovery and per-file toggles with descriptions, bundle validation added, operation descriptions in Agent defaults tab, 16 new tests added (62 total).
- **Deviations from plan:** None significant. validation is called in ImportScreen step 2 (during preview) rather than inside `import_all_configs()` itself, to keep the core function simple and let the UI handle warnings display.
- **Issues encountered:** None.
- **Key decisions:** Used CycleField (existing widget) for all toggles rather than checkboxes for consistency with existing UI patterns. Used show/hide containers for two-step import flow rather than separate screens for simpler state management.
