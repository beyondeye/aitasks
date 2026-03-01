---
Task: t268_3_common_config_library.md
Parent Task: aitasks/t268_wrapper_for_claude_code.md
Sibling Tasks: aitasks/t268/t268_4_board_config_split.md, aitasks/t268/t268_5_tui_integration.md
Archived Sibling Plans: aiplans/archived/p268/p268_1_core_wrapper_script.md, aiplans/archived/p268/p268_2_config_infrastructure.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The aitasks project has multiple Python TUIs (board, codebrowser, future settings TUI) that each handle JSON config loading inline. A per-project / per-user layered override pattern exists in bash (`codeagent_config.json` + `codeagent_config.local.json`) but has no Python equivalent. This task creates `aiscripts/lib/config_utils.py` — a shared module providing reusable config loading/saving with deep-merge logic, plus `tests/test_config_utils.py`.

## Files Created/Modified

| Action | File |
|--------|------|
| Create | `aiscripts/lib/config_utils.py` |
| Create | `tests/test_config_utils.py` |
| Modify | `tests/run_all_python_tests.sh` — add `aiscripts/lib` to PYTHONPATH |

## Implementation Steps

### Step 1: Create `aiscripts/lib/config_utils.py` (~195 LOC) [DONE]

Module with stdlib-only dependencies (`json`, `copy`, `pathlib`, `datetime`).

Functions:
1. `local_path_for(project_path) -> Path` — Derive `.local.json` path
2. `deep_merge(base, override) -> dict` — Recursive merge (dict=merge, list=replace, scalar=replace)
3. `load_layered_config(project_path, local_path=None, defaults=None) -> dict` — 3-layer merge
4. `save_project_config(path, data) -> None` — Write JSON with indent=2
5. `save_local_config(path, data) -> None` — Same as save_project_config
6. `split_config(merged, project_keys=None, user_keys=None) -> tuple[dict, dict]` — Partition by top-level keys
7. `export_all_configs(output_path, metadata_dir, patterns=None) -> dict` — Bundle configs
8. `import_all_configs(input_path, metadata_dir, overwrite=False) -> list[str]` — Restore from bundle

### Step 2: Create `tests/test_config_utils.py` (46 tests) [DONE]

Using `unittest`, tests cover all 8 functions including edge cases (missing files, invalid JSON, path traversal, no mutation, round-trip).

### Step 3: Update `tests/run_all_python_tests.sh` [DONE]

Added `aiscripts/lib` to PYTHONPATH.

### Step 4: Verification [DONE]

- 46/46 config_utils tests pass
- 71/71 total Python tests pass (including existing merge tests)

## Final Implementation Notes

- **Actual work done:** Created `aiscripts/lib/config_utils.py` (195 LOC) with 8 functions implementing layered JSON config loading with deep-merge, save, split, export/import. Created `tests/test_config_utils.py` with 46 unit tests. Updated `tests/run_all_python_tests.sh` to include `aiscripts/lib` in PYTHONPATH.
- **Deviations from plan:** None. Implementation matches the task spec exactly.
- **Issues encountered:** None. pytest not installed on system but unittest fallback works perfectly.
- **Key decisions:**
  - Used `copy.deepcopy` for all merge operations to guarantee no mutation of inputs
  - `_load_json` helper silently returns `{}` for missing files but propagates `json.JSONDecodeError` for corrupt files (fail-silent on absence, fail-loud on corruption)
  - Export format includes `_export_meta` with version, timestamp, and file count for forward compatibility
  - Path traversal protection in `import_all_configs` checks for `/`, `\`, and `os.sep`
  - `local_path_for` uses simple string replacement (`".json"` → `".local.json"`) matching the established naming convention
- **Notes for sibling tasks:**
  - t268_4 (board config split) should use `load_layered_config("aitasks/metadata/board_config.json", defaults=DEFAULT_CONFIG)` to replace inline `load_metadata()` in `aitask_board.py`
  - t268_5 (TUI integration) can use `split_config(merged, user_keys={"settings"})` to separate board settings into project/user layers
  - The module is at `aiscripts/lib/config_utils.py` — import with `sys.path.insert(0, "aiscripts/lib")` or use PYTHONPATH (already configured in test runner)
  - `export_all_configs` / `import_all_configs` provide config backup/restore for t268_8 (documentation) to reference
