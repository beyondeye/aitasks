---
priority: high
effort: high
depends: [195_1]
issue_type: feature
status: Ready
labels: [codebrowser]
created_at: 2026-02-25 12:18
updated_at: 2026-02-25 12:18
---

## Context

This is child task 4 of t195 (Python Code Browser TUI). It implements the `ExplainManager` — the data layer that generates, caches, and parses explain data for the codebrowser. When a user browses a file, the manager automatically checks for cached explain data and generates it if missing.

The existing explain pipeline (`aitask_explain_extract_raw_data.sh` + `aitask_explain_process_raw_data.py`) does the heavy lifting. The manager orchestrates it from Python via subprocess, directing output to `aiexplain/codebrowser/` with a directory-based naming scheme.

## Key Files to Modify

- **`aiscripts/codebrowser/explain_manager.py`** (NEW): `ExplainManager` class with:
  - `__init__(project_root: Path)`: stores root, creates `aiexplain/codebrowser/` if needed
  - `get_cached_data(file_path: Path) -> FileExplainData | None`: finds most recent explain run covering the file's directory
  - `generate_explain_data(directory: Path) -> FileExplainData`: runs extract script for non-recursive directory files, stores with directory key naming
  - `parse_reference_yaml(yaml_path: Path) -> dict[str, FileExplainData]`: parses reference.yaml into per-file data
  - `refresh_data(directory: Path) -> FileExplainData`: deletes old run, regenerates
  - `get_run_info(file_path: Path) -> ExplainRunInfo | None`: returns run metadata
- **`aiscripts/aitask_explain_extract_raw_data.sh`** (MODIFY line 17): Change `AIEXPLAINS_DIR="aiexplains"` to `AIEXPLAINS_DIR="${AIEXPLAINS_DIR:-aiexplains}"` to allow environment variable override
- **`aiscripts/codebrowser/codebrowser_app.py`** (MODIFY):
  - Instantiate `ExplainManager` in app `__init__`
  - Add `@work(thread=True)` method for background explain generation
  - Update file info bar to show explain data timestamp and "(generating...)" status
  - Add `r` keybinding for refresh explain data

## Reference Files for Patterns

- `aiscripts/aitask_explain_extract_raw_data.sh` (full file): Extract script — line 17 for AIEXPLAINS_DIR, lines 23-42 for `expand_path()` (recurses into subdirs via `git ls-files`), output structure in `$AIEXPLAINS_DIR/<timestamp>/`
- `aiscripts/aitask_explain_process_raw_data.py` (full file): Processes raw data into `reference.yaml` — understand the YAML output format (files[].commits[], files[].line_ranges[])
- `aiscripts/board/aitask_board.py` (lines 2590-2640): `@work(thread=True)` pattern for background subprocess execution
- `aiscripts/codebrowser/annotation_data.py` (from t195_1): `AnnotationRange`, `FileExplainData`, `ExplainRunInfo` dataclasses

## Implementation Plan

1. Modify `aitask_explain_extract_raw_data.sh` line 17:
   - FROM: `AIEXPLAINS_DIR="aiexplains"`
   - TO: `AIEXPLAINS_DIR="${AIEXPLAINS_DIR:-aiexplains}"`
   - This allows the codebrowser to redirect output via environment variable

2. Create `explain_manager.py`:
   - **Directory key computation**: `_dir_to_key(directory: Path) -> str`:
     - Convert relative path to string, replace `/` with `__`
     - Example: `aiscripts/lib/` → `aiscripts__lib`
     - Root directory: use `_root_` as key

   - **`get_cached_data(file_path: Path) -> FileExplainData | None`**:
     - Compute directory = file_path.parent (relative to project root)
     - Compute dir_key = `_dir_to_key(directory)`
     - Glob: `aiexplain/codebrowser/{dir_key}__*/reference.yaml`
     - Sort by timestamp suffix (descending), use most recent
     - If found: parse and return data for the specific file_path
     - If not found: return None

   - **`generate_explain_data(directory: Path) -> FileExplainData`**:
     - List direct-child files: `git ls-files <directory>/` → filter to depth=1 (exclude files in subdirectories by checking `os.path.dirname(f) == str(directory)`)
     - Skip if no files in directory
     - Run subprocess:
       ```python
       env = os.environ.copy()
       env["AIEXPLAINS_DIR"] = "aiexplain/codebrowser"
       subprocess.run(["./aiscripts/aitask_explain_extract_raw_data.sh", "--gather"] + file_list, env=env, check=True)
       ```
     - The script creates `aiexplain/codebrowser/<timestamp>/` — find the newest directory
     - Rename to `aiexplain/codebrowser/{dir_key}__{timestamp}/`
     - Parse reference.yaml and return FileExplainData

   - **`parse_reference_yaml(yaml_path: Path) -> dict[str, FileExplainData]`**:
     - Load YAML file
     - For each file entry: build list of `AnnotationRange` from `line_ranges`
     - Map `commits` timeline numbers to task_ids
     - Return dict keyed by file path

   - **`refresh_data(directory: Path) -> FileExplainData`**:
     - Find existing run for this directory key
     - Delete it (`shutil.rmtree`)
     - Call `generate_explain_data(directory)`

   - **`get_run_info(file_path: Path) -> ExplainRunInfo | None`**:
     - Find cached run directory
     - Parse timestamp from directory name suffix
     - Count files from `files.txt`
     - Return `ExplainRunInfo`

3. Update `codebrowser_app.py`:
   - In `__init__`: `self.explain_manager = ExplainManager(project_root)`
   - Add `_load_explain_data(file_path: Path)` as `@work(thread=True)`:
     - Check cache → generate if miss → update UI on completion via `call_from_thread`
   - Update `on_directory_tree_file_selected()` to call `_load_explain_data()`
   - Update file info bar: show timestamp when data available, "(generating...)" when in progress
   - Add binding: `Binding("r", "refresh_explain", "Refresh annotations")`
   - `action_refresh_explain()`: call `explain_manager.refresh_data()` in background

## Verification Steps

1. Run `./ait codebrowser`, select a file — file info bar should show "(generating...)" then update with timestamp
2. Navigate to another file in the same directory — should use cached data (no regeneration)
3. Navigate to a file in a different directory — should trigger new generation
4. Press `r` — should regenerate and show updated timestamp
5. Check `aiexplain/codebrowser/` directory — should contain properly named run directories (e.g., `aiscripts__lib__20260225_143052/`)
6. Verify `reference.yaml` exists in each run directory and contains valid data
7. Verify the `AIEXPLAINS_DIR` change is backward-compatible: running `./aiscripts/aitask_explain_extract_raw_data.sh --gather <file>` without the env var should still write to `aiexplains/`
