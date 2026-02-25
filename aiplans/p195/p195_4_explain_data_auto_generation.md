---
Task: t195_4_explain_data_auto_generation.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_1_*.md, aitasks/t195/t195_5_*.md
Branch: main
Base branch: main
---

# Plan: t195_4 — Explain Data Auto-Generation Infrastructure

## Steps

### 1. Modify `aitask_explain_extract_raw_data.sh` (line 17)
```bash
# FROM:
AIEXPLAINS_DIR="aiexplains"
# TO:
AIEXPLAINS_DIR="${AIEXPLAINS_DIR:-aiexplains}"
```
This is backward-compatible — existing callers get the same default.

### 2. Create `aiscripts/codebrowser/explain_manager.py`

**`ExplainManager.__init__(project_root: Path)`**:
- Store root, create `aiexplain/codebrowser/` if needed via `os.makedirs(exist_ok=True)`

**`_dir_to_key(directory: Path) -> str`**:
- `str(directory).replace("/", "__")` or `"_root_"` for project root

**`get_cached_data(file_path: Path) -> FileExplainData | None`**:
- Compute dir_key from file's parent directory
- Glob `aiexplain/codebrowser/{dir_key}__*/reference.yaml`
- Sort by name (timestamp suffix), take most recent
- Parse and return, or None

**`generate_explain_data(directory: Path) -> FileExplainData`**:
- List direct children: `git ls-files <dir>/` → filter `os.path.dirname(f) == str(dir)`
- Set env: `AIEXPLAINS_DIR=aiexplain/codebrowser`
- Run: `subprocess.run([script, "--gather"] + files, env=env, check=True, capture_output=True)`
- Find newest dir in `aiexplain/codebrowser/` (timestamp-only name)
- Rename to `{dir_key}__{timestamp}`
- Parse reference.yaml

**`parse_reference_yaml(yaml_path: Path) -> dict[str, FileExplainData]`**:
- Load YAML
- For each file entry: build `AnnotationRange` from `line_ranges`
- Return dict keyed by file path

**`refresh_data(directory: Path)` / `get_run_info(file_path: Path)`**

### 3. Update `codebrowser_app.py`
- Import `ExplainManager` and `work` from textual
- Instantiate `ExplainManager` in `__init__`
- Add `@work(exclusive=True)` async method `_load_explain_data(file_path)` (board pattern uses `exclusive=True`, not `thread=True`)
  - Check cache via `explain_manager.get_cached_data()`
  - If miss, run `explain_manager.generate_explain_data()` in thread via `asyncio.to_thread()`
  - Update info bar via `call_from_thread()` or direct update after await
- Wire to file selection handler (`on_directory_tree_file_selected`)
- Info bar: show explain data timestamp or "(generating...)" status
- Add `Binding("r", "refresh_explain", "Refresh annotations")` and `action_refresh_explain()` method
- Store current explain data as `self._current_explain_data` for use by t195_5 (annotation overlay)

## Verification
- Select file → "(generating...)" → timestamp appears
- Same directory → cached (instant)
- New directory → new generation
- `r` → regenerates
- `aiexplains/codebrowser/` has proper naming
- AIEXPLAINS_DIR change is backward-compatible

## Final Implementation Notes
- **Actual work done:** All 3 steps implemented as planned. Modified `aitask_explain_extract_raw_data.sh` line 17 for env var override. Created `explain_manager.py` with full `ExplainManager` class (cache lookup, generation, YAML parsing, refresh, run info). Updated `codebrowser_app.py` with `ExplainManager` integration, `@work(exclusive=True)` async background generation, info bar status updates, and `r` keybinding for refresh.
- **Deviations from plan:** Changed output directory from `aiexplain/codebrowser/` to `aiexplains/codebrowser/` (per user feedback — reuses the existing gitignored `aiexplains/` directory instead of creating a separate `aiexplain/` directory). No `.gitignore` changes needed. The `work` decorator import was initially from `textual.worker` (wrong) — corrected to `from textual import work` matching the board TUI pattern. `ExplainManager` is instantiated in `compose()` rather than `on_mount()` since `_project_root` is set there.
- **Issues encountered:** `from textual.worker import work` raised ImportError — the `work` decorator is re-exported from the top-level `textual` package (`from textual import work`), same as how `aitask_board.py` imports it.
- **Key decisions:** Used `asyncio.to_thread()` for subprocess calls inside `@work(exclusive=True)` async methods — this prevents blocking the event loop while the extract script runs. Timestamp is parsed from the run directory name suffix (last 15 chars, `YYYYMMDD_HHMMSS` format). `_current_explain_data` is stored as instance variable for use by t195_5 (annotation overlay).
- **Notes for sibling tasks:** `ExplainManager` is accessed via `self.explain_manager` on the app. `self._current_explain_data` holds the parsed `dict[str, FileExplainData]` for the current directory — t195_5 should read this to render annotation gutters. The `_load_explain_data` worker uses `exclusive=True` so only one generation runs at a time. The `work` decorator must be imported as `from textual import work` (not from `textual.worker`). Use direct imports (not relative) for all codebrowser modules. The extract script now supports `AIEXPLAINS_DIR` env var override — t195_11 should ensure the `--no-recurse` flag also works with this override.
