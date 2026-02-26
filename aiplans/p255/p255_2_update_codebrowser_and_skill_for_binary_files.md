---
Task: t255_2_update_codebrowser_and_skill_for_binary_files.md
Parent Task: aitasks/t255_support_for_binary_files_in_aiexplains.md
Sibling Tasks: aitasks/t255/t255_1_fix_extraction_processing_pipeline_for_binary_files.md
Archived Sibling Plans: aiplans/archived/p255/p255_1_*.md
Worktree: (working on current branch)
Branch: (current branch)
Base branch: main
---

## Plan: Update codebrowser + skill for binary files

### Step 1: Add `is_binary` field to FileExplainData

**File:** `aiscripts/codebrowser/annotation_data.py`

Add to `FileExplainData` dataclass (after `generated_at`):
```python
is_binary: bool = False
```

### Step 2: Update parse_reference_yaml()

**File:** `aiscripts/codebrowser/explain_manager.py`

In `parse_reference_yaml()` (lines 150-185):
- Read: `is_binary = file_entry.get("binary", False)`
- Wrap annotation/enrichment loops in `if not is_binary:`
- Pass `is_binary=is_binary` to FileExplainData constructor

### Step 3: Update _update_code_annotations()

**File:** `aiscripts/codebrowser/codebrowser_app.py`

In `_update_code_annotations()` (lines 237-244), add binary handling before the existing annotation line:

```python
if file_data and file_data.is_binary:
    code_viewer.set_annotations([])
    n = len(file_data.commit_timeline)
    self._annotation_info += f" (binary, {n} commit{'s' if n != 1 else ''})"
    self._update_info_bar()
    return
```

### Step 4: Update SKILL.md

**File:** `.claude/skills/aitask-explain/SKILL.md`

Add binary file handling guidance:
- Step 1 "Proceed with files": note binary files are auto-detected and marked
- Functionality mode: describe file role from path/name, grep for references in code
- Code Evolution mode: present commit timeline only, no line_ranges
- Notes section: document binary detection and behavior

### Verification

1. Open codebrowser, navigate to `imgs/` directory
2. Click PNG → "Binary file — cannot display" + "Annotations: <ts> (binary, N commits)"
3. Click text file → normal annotations
4. Old reference.yaml without `binary` field → all files get `is_binary=False`

## Post-implementation

Refer to Step 9 of the task-workflow (archival, merge, cleanup).
