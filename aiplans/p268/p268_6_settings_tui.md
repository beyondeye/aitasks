---
Task: t268_6_settings_tui.md
Parent Task: aitasks/t268_wrapper_for_claude_code.md
Sibling Tasks: aitasks/t268/t268_7_implemented_with_metadata.md, aitasks/t268/t268_8_documentation.md
Archived Sibling Plans: aiplans/archived/p268/p268_1_core_wrapper_script.md, p268_2_config_infrastructure.md, p268_3_common_config_library.md, p268_4_board_config_split.md, p268_5_tui_integration.md, p268_9_refresh_code_models_skill.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The aitasks project has multiple config files scattered across `aitasks/metadata/` — codeagent defaults, board config, model lists, execution profiles — with a per-project/per-user layered override system (via `config_utils.py`). Currently there is no centralized way to view or edit these configs; users must manually edit JSON/YAML files. This task creates `ait settings`, a Textual TUI for browsing and editing all configuration in one place.

## Implementation Plan

### Step 1: Create shell launcher `aiscripts/aitask_settings.sh`

Copy the `aiscripts/aitask_codebrowser.sh` pattern exactly:
- venv check (`~/.aitask/venv/bin/python`), fallback to system python
- Check for `textual` and `pyyaml` packages (no `linkify-it-py` needed)
- `ait_warn_if_incapable_terminal`
- `exec "$PYTHON" "$SCRIPT_DIR/settings/settings_app.py" "$@"`

### Step 2: Add dispatcher entry in `ait`

- Add `settings) shift; exec "$SCRIPTS_DIR/aitask_settings.sh" "$@" ;;` at line ~125 (after `codebrowser`)
- Add `settings` to `show_usage()` under TUI section
- Add `settings` to the update-check skip list (line 114) alongside other TUI commands

### Step 3: Create `aiscripts/settings/settings_app.py` (~700 LOC)

#### 3a: Imports, constants, path setup (~30 LOC)

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from config_utils import (load_layered_config, split_config, save_project_config,
                          save_local_config, local_path_for, export_all_configs,
                          import_all_configs)
```

Constants:
- `METADATA_DIR = Path("aitasks") / "metadata"`
- `CODEAGENT_CONFIG = METADATA_DIR / "codeagent_config.json"`
- `BOARD_CONFIG = METADATA_DIR / "board_config.json"`
- `MODEL_FILES = {"claude": ..., "codex": ..., "gemini": ..., "opencode": ...}`
- `PROFILES_DIR = METADATA_DIR / "profiles"`
- Board key split: `_BOARD_PROJECT_KEYS = {"columns", "column_order"}`, `_BOARD_USER_KEYS = {"settings"}`

#### 3b: ConfigManager class (~80 LOC)

Centralizes all config loading/saving:
- `load_all()` — loads each config via `load_layered_config()`, also loads raw project/local layers separately to determine value sources
- `save_codeagent(project_data, local_data)` — saves via `save_project_config`/`save_local_config`
- `save_board(merged)` — uses `split_config()` then saves both layers
- Loads model files as read-only dicts
- `load_profiles()` — reads all `*.yaml` files from `PROFILES_DIR`, parses with `yaml.safe_load()`
- `save_profile(filename, data)` — writes profile dict back to YAML with `yaml.dump()`

#### 3c: CycleField widget (~60 LOC)

Copy from `aiscripts/board/aitask_board.py` lines 710-769. Self-contained widget with no external deps. Used for enumerated settings (auto_refresh_minutes, layer selection).

#### 3d: ConfigRow widget (~30 LOC)

Simple focusable `Static` subclass displaying a config key-value with layer badge:
- `[PROJECT]` badge in green for project-layer values
- `[USER]` badge in amber for local-override values
- Focus highlighting via CSS class

#### 3e: EditValueScreen modal (~50 LOC)

`ModalScreen` for editing a single codeagent default value:
- Input field with current value
- CycleField for target layer (project / user)
- Save/Cancel buttons
- Dismisses with `{"key", "value", "layer"}` dict

#### 3f: ImportScreen modal (~40 LOC)

`ModalScreen` for entering import file path:
- Input field for file path
- Overwrite toggle (CycleField: Yes/No)
- Import/Cancel buttons

#### 3g: SettingsApp main class (~100 LOC)

```python
class SettingsApp(App):
    TITLE = "aitasks settings"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("e", "export_configs", "Export"),
        Binding("i", "import_configs", "Import"),
        Binding("r", "reload_configs", "Reload"),
    ]
```

Uses `TabbedContent` with 4 tabs:

**Tab 1: "Agent Defaults"** (~60 LOC)
- Shows each key in `codeagent_config["defaults"]` as a `ConfigRow`
- Determines value source by comparing project vs local layer
- Press Enter on a row to open `EditValueScreen`
- After edit, saves to chosen layer and refreshes display

**Tab 2: "Board"** (~50 LOC)
- Read-only section: columns list (id, title, color) — editing columns is the board's job
- Editable section: user settings — `auto_refresh_minutes` via CycleField (options: 1, 2, 5, 10, 15, 30, 0=off)
- Save button writes via `ConfigManager.save_board()`

**Tab 3: "Models"** (~60 LOC read-only)
- Sub-section per provider (Claude, Codex, Gemini, OpenCode)
- Each model displayed as: `name | cli_id | notes | verified scores`
- Footer hint: "Managed by 'ait codeagent refresh'. Edit files directly for manual changes."

**Tab 4: "Profiles"** (~80 LOC editable)
- Lists each `*.yaml` file from `PROFILES_DIR` as expandable sections
- Each profile shows its key-value pairs as editable fields:
  - Boolean keys (`skip_task_confirmation`, `create_worktree`, `force_unlock_stale`): CycleField with `true`/`false`/`(unset)` options
  - Enum keys (`plan_preference`, `plan_preference_child`): CycleField with `use_current`/`verify`/`create_new`/`(unset)` options
  - Enum keys (`post_plan_action`): CycleField with `start_implementation`/`(unset)` options
  - Enum keys (`default_email`): CycleField with `userconfig`/`first`/`(unset)` + free-text option
  - Enum keys (`done_task_action`, `review_action`, `issue_action`, etc.): CycleField with their known values
  - String keys (`name`, `description`, `base_branch`): ConfigRow, press Enter to edit in-place via Input
- `(unset)` option removes the key from the profile (= ask interactively at runtime)
- Save button per profile writes back to YAML file
- Known profile keys from schema in `profiles.md`: `name`, `description`, `skip_task_confirmation`, `default_email`, `create_worktree`, `base_branch`, `plan_preference`, `plan_preference_child`, `post_plan_action`, `explore_auto_continue`, plus remote-specific: `force_unlock_stale`, `done_task_action`, `orphan_parent_action`, `complexity_action`, `review_action`, `issue_action`, `abort_plan_action`, `abort_revert_status`

**Actions:**
- `action_export_configs()` — calls `export_all_configs()`, writes timestamped file, shows notification
- `action_import_configs()` — opens `ImportScreen`, on confirm calls `import_all_configs()`, reloads, rebuilds
- `action_reload_configs()` — re-reads all files, rebuilds tab contents

#### 3h: CSS (~80 LOC inline)

Follows board pattern with `App.CSS` string. Key rules for:
- Tab content padding
- ConfigRow focus highlighting
- Layer badges (green/amber)
- Section headers
- Model table formatting
- Modal dialog sizing/positioning

### Step 4: Create `aiscripts/settings/__init__.py`

Empty file to make the directory a Python package.

## Files to Create

| File | Description |
|------|-------------|
| `aiscripts/settings/__init__.py` | Empty package init |
| `aiscripts/settings/settings_app.py` | Main Settings TUI app (~700 LOC) |
| `aiscripts/aitask_settings.sh` | Shell launcher |

## Files to Modify

| File | Change |
|------|--------|
| `ait` | Add `settings` dispatcher entry + usage text |

## Design Decisions

1. **TabbedContent over sidebar** — Built-in Textual widget, handles keyboard nav and visual indicators automatically. Far less code than a custom sidebar.
2. **Copy CycleField instead of extracting to shared lib** — Avoids refactoring dependency on board TUI. Only ~60 lines.
3. **No codebrowser settings tab** — `codebrowser_config.json` doesn't exist. Can add later when it does.
4. **Models read-only, profiles editable** — Models managed by `ait codeagent refresh` (read-only display). Profiles are editable with typed widgets per schema key — CycleField for bools/enums, Input for strings. `(unset)` option removes a key so the question is asked interactively at runtime.
5. **No tests** — TUI apps are difficult to unit test. ConfigManager delegates entirely to `config_utils.py` which already has 46 tests. Manual testing is the primary verification approach.

## Verification Steps

1. `./ait settings` launches the TUI and displays all 4 tabs
2. Tab navigation works with keyboard (Tab key or clicking tab headers)
3. Agent Defaults tab shows correct values with layer badges
4. Editing a codeagent default and saving writes to the correct file
5. Board tab shows columns (read-only) and user settings (editable)
6. Models tab shows all 4 providers with their model lists
7. Profiles tab shows all profiles with editable fields
8. Editing a profile value (bool/enum/string) and saving writes back to YAML
9. Setting a profile key to `(unset)` removes it from the YAML
10. `E` key exports configs to a timestamped JSON file
9. `I` key opens import modal, importing restores configs
10. `R` key reloads all configs from disk
11. `Q` exits cleanly
12. Missing config files are handled gracefully (empty display, not crash)

## Final Implementation Notes

- **Actual work done:** Created `aiscripts/settings/settings_app.py` (~700 LOC) with ConfigManager, CycleField, ConfigRow, EditValueScreen, EditStringScreen, ImportScreen widgets, and SettingsApp with 4 TabbedContent tabs (Agent Defaults, Board, Models, Profiles). Created `aiscripts/aitask_settings.sh` launcher and `aiscripts/settings/__init__.py`. Added `settings` command to `ait` dispatcher with usage text and update-check skip.
- **Deviations from plan:**
  - Added `EditStringScreen` modal (not originally planned) for editing profile string values via Enter key on ConfigRow
  - Used `_safe_id()` helper to sanitize filenames with dots (e.g., `default.yaml`) for Textual widget IDs — Textual doesn't allow dots in IDs
  - Used `config_layer` instead of `layer` for ConfigRow attribute — Textual's Widget class reserves `layer` as a property
  - Simplified button mounting — `mount()` returns AwaitMount not a context manager, so buttons are mounted directly on the container rather than inside a Horizontal wrapper
- **Issues encountered:**
  - Textual's `Widget.layer` property conflicts with naming `self.layer` on ConfigRow — fixed by renaming to `config_layer`
  - Textual's `check_identifiers` rejects dots in widget IDs — fixed with `_safe_id()` helper that replaces dots/spaces with underscores
  - `container.mount(Horizontal(...))` returns `AwaitMount` which isn't a context manager — simplified to mount buttons directly
- **Key decisions:**
  - 18 profile schema keys defined in `PROFILE_SCHEMA` dict with type info (bool/enum/string and options) — drives automatic widget generation per profile
  - `_profile_id_map` dict maps safe widget IDs back to actual filenames for save operations
  - ConfigManager loads both merged and raw (project/local) layers separately to determine value source for layer badges
  - `save_codeagent()` removes local file entirely when local overrides become empty
- **Notes for sibling tasks:**
  - t268_7 (implemented_with metadata) — no impact on settings TUI; the new frontmatter field is task-level, not config-level
  - t268_8 (documentation) — should document `ait settings` command under TUI section, describe the 4 tabs, and explain per-project vs per-user config editing. Reference the profile schema from `profiles.md`.
  - The `_safe_id()` pattern could be extracted to a shared utility if other TUIs need it

## Post-Implementation

Step 9: archive t268_6, update parent task's `children_to_implement`, push.
