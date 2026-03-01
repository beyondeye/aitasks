---
priority: high
effort: medium
depends: [t268_2]
issue_type: feature
status: Done
labels: [modelwrapper]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-01 09:00
updated_at: 2026-03-01 14:45
completed_at: 2026-03-01 14:45
---

## Context

This is child task 3 of t268 (Code Agent Wrapper). It creates a shared Python module `config_utils.py` that provides reusable config loading/saving logic for all TUIs (board, codebrowser, settings). This ensures consistent merge logic for the per-project / per-user config layer pattern across all Python TUI components.

## Key Files

- **Create:** `aiscripts/lib/config_utils.py`
- **Create:** `tests/test_config_utils.py`

## Implementation Plan

### 1. Create `aiscripts/lib/config_utils.py`

Functions:
- `load_layered_config(project_path, local_path)` → deep-merge per-project + per-user JSON configs. Per-user values override per-project values. Handles missing files gracefully.
- `save_project_config(path, data)` → write project-level config JSON
- `save_local_config(path, data)` → write per-user config JSON (only overrides)
- `split_config(data, project_keys, user_keys)` → split merged config back into project/user layers for saving
- `export_all_configs(output_path)` → bundle all config files (board, codebrowser, codeagent, model files) into a single JSON export
- `import_all_configs(input_path)` → restore configs from an export bundle

Deep merge rules:
- Dict values: recursive merge (per-user overrides individual keys)
- List values: per-user replaces entire list
- Scalar values: per-user overrides per-project

### 2. Create `tests/test_config_utils.py`

Unit tests using `pytest`:
- Test deep merge with nested dicts
- Test missing file handling
- Test save/load round-trip
- Test split_config correctly separates project/user keys
- Test export/import round-trip

## Reference Files

- `aiscripts/board/aitask_board.py` (lines ~198-218): Current `load_metadata()` / `save_metadata()` pattern to understand existing config loading
- `aitasks/metadata/board_config.json`: Current board config format

## Verification Steps

1. `python3 -m pytest tests/test_config_utils.py` passes
2. Deep merge correctly overlays per-user on per-project config
3. Missing config files handled gracefully (returns defaults)
4. Export/import round-trips without data loss
