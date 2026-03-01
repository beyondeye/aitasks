---
Task: t268_4_board_config_split.md
Parent Task: aitasks/t268_config_layer_support.md
Sibling Tasks: aitasks/t268/t268_5_tui_integration.md, aitasks/t268/t268_6_settings_tui.md
Archived Sibling Plans: aiplans/archived/p268/p268_1_core_wrapper_script.md, aiplans/archived/p268/p268_2_config_infrastructure.md, aiplans/archived/p268/p268_3_common_config_library.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The board TUI (`aiscripts/board/aitask_board.py`) currently loads/saves `board_config.json` using plain `json` I/O. This mixes project-level settings (columns, column_order) with user preferences (auto_refresh_minutes, collapsed_columns) in a single git-tracked file. Task t268_3 created `aiscripts/lib/config_utils.py` with layered config loading — this task integrates it into the board TUI to split config into project (git-tracked) and user (gitignored) layers.

## Key Categorization

**Per-project** (`board_config.json`, git-tracked):
- `columns` — column definitions (id, title, color)
- `column_order` — column display order

**Per-user** (`board_config.local.json`, gitignored):
- `settings` — contains `auto_refresh_minutes`, `collapsed_columns`, future user prefs

## Files to Modify

| File | Change |
|------|--------|
| `aiscripts/board/aitask_board.py` | Refactor `load_metadata()` and `save_metadata()` to use `config_utils` |

## Files to Create

| File | Change |
|------|--------|
| `tests/test_board_config_split.py` | Automated tests for the layered config integration |

## Implementation Steps

### Step 1: Add config_utils import to aitask_board.py [DONE]
### Step 2: Define user/project key constants [DONE]
### Step 3: Refactor `load_metadata()` (~line 201) [DONE]
### Step 4: Refactor `save_metadata()` (~line 215) [DONE]
### Step 5: Verify gitignore coverage [DONE]

`aitasks/metadata/*.local.json` already in data branch `.gitignore` (from t268_2).

### Step 6: Create `tests/test_board_config_split.py` [DONE]

12 test cases across 9 test classes covering load, save, roundtrip, migration, and deep merge.

## Final Implementation Notes

- **Actual work done:** Refactored `load_metadata()` and `save_metadata()` in `aitask_board.py` to use `config_utils.py` functions. Added `_PROJECT_KEYS`/`_USER_KEYS` constants. Created `tests/test_board_config_split.py` with 12 tests.
- **Deviations from plan:** None. Implementation matches the task spec exactly.
- **Issues encountered:** None. Gitignore was already in place from t268_2. All 83 Python tests pass (12 new + 71 existing).
- **Key decisions:**
  - Split at top-level key: `columns`+`column_order` → project, `settings` → user. The `settings` dict contains all user preferences (`auto_refresh_minutes`, `collapsed_columns`).
  - `save_metadata()` only writes local file if `user_data` is non-empty (defensive, though `settings` is always present in practice).
  - Migration is seamless: existing single-file `board_config.json` loads fine, and on first save the settings are split to `board_config.local.json`.
  - Import uses `sys.path.insert(0, ...)` relative to `__file__` for robustness regardless of working directory.
- **Notes for sibling tasks:**
  - t268_5 (TUI integration) can build on this pattern — the board now demonstrates the canonical way to use `config_utils` for layered config.
  - t268_6 (settings TUI) should use the same `_USER_KEYS` set to know which settings are user-configurable vs project-level.
  - The `deep_merge` in `config_utils` means local files only need to contain the keys they override — partial overrides work correctly.
