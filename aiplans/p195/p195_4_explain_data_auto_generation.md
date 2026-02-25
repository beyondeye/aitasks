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
- Instantiate `ExplainManager` in `__init__`
- Add `@work(thread=True)` method `_load_explain_data(file_path)`
- Wire to file selection handler
- Info bar: show timestamp or "(generating...)"
- Add `r` binding for refresh

## Verification
- Select file → "(generating...)" → timestamp appears
- Same directory → cached (instant)
- New directory → new generation
- `r` → regenerates
- `aiexplain/codebrowser/` has proper naming
- AIEXPLAINS_DIR change is backward-compatible
