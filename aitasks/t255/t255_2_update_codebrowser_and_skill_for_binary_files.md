---
priority: high
effort: medium
depends: [t255_1]
issue_type: feature
status: Ready
labels: [ui, aitask_explain]
created_at: 2026-02-26 11:15
updated_at: 2026-02-26 11:15
---

Update codebrowser and aitask-explain skill to handle binary file entries in reference.yaml (consumer side).

## Context

After t255_1 fixes the extraction pipeline, binary files will be marked with `binary: true` in reference.yaml and have empty line_ranges but populated commit timelines. The consumers of this data (codebrowser TUI and aitask-explain skill) need to handle these entries gracefully — showing commit history info for binary files without attempting line-level annotations or code explanations.

## Key Files to Modify

1. **`aiscripts/codebrowser/annotation_data.py`** (lines 14-18)
   - Add `is_binary: bool = False` to `FileExplainData` dataclass

2. **`aiscripts/codebrowser/explain_manager.py`** — `parse_reference_yaml()` (lines 129-187)
   - Read `binary` field from YAML: `is_binary = file_entry.get("binary", False)`
   - Skip annotation building loop when `is_binary` is True
   - Pass `is_binary=is_binary` to `FileExplainData` constructor

3. **`aiscripts/codebrowser/codebrowser_app.py`** — `_update_code_annotations()` (lines 237-244)
   - Handle `file_data.is_binary`: set empty annotations, show binary commit count in info bar
   - Display: `"Annotations: <ts> (binary, N commits)"`

4. **`.claude/skills/aitask-explain/SKILL.md`**
   - Document binary file handling in each analysis mode

## Reference Files for Patterns

- `aiscripts/codebrowser/annotation_data.py` — Existing dataclass pattern with default fields
- `aiscripts/codebrowser/explain_manager.py:150-185` — How reference.yaml is parsed into FileExplainData
- `aiscripts/codebrowser/codebrowser_app.py:237-244` — Current `_update_code_annotations()` method
- `aiscripts/codebrowser/code_viewer.py:96-108` — Existing binary detection (shows "Binary file — cannot display")

## Implementation Plan

### Step 1: Add `is_binary` to FileExplainData

In `annotation_data.py`, add field to the dataclass:
```python
is_binary: bool = False
```

### Step 2: Update explain_manager.py parser

In `parse_reference_yaml()`, read the `binary` field and conditionally skip annotation building:
- `is_binary = file_entry.get("binary", False)`
- Wrap the annotation/enrichment loops in `if not is_binary:`
- Pass `is_binary=is_binary` to FileExplainData constructor

### Step 3: Update codebrowser_app.py

In `_update_code_annotations()`:
```python
if file_data and file_data.is_binary:
    code_viewer.set_annotations([])
    n = len(file_data.commit_timeline)
    self._annotation_info += f" (binary, {n} commit{'s' if n != 1 else ''})"
    self._update_info_bar()
    return
```

### Step 4: Update SKILL.md

Add binary file handling guidance to:
- Step 1 "Proceed with files": note that binary files are auto-detected
- Functionality mode: describe file role from path/name, grep for references
- Code Evolution mode: present commit timeline only, no line_ranges
- Notes section: document binary detection behavior

## Verification Steps

1. Open codebrowser, navigate to directory with binary files (e.g., `imgs/`)
2. Click a PNG file — should show "Binary file — cannot display" + "Annotations: <ts> (binary, N commits)" in info bar
3. Click a text file — normal annotations as before
4. Verify old reference.yaml (no binary field) still works — all files get `is_binary=False`
