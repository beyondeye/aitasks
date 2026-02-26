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

## Post-Review Changes

### Change Request 1 (2026-02-26 12:30)
- **Requested by user:** Three issues reported during review: (1) binary files show no annotation pane, (2) child task IDs like t202_2 display as t2022, (3) annotation colors collide for different tasks
- **Changes made:**
  - Issue 1: Confirmed working as designed — binary files can't display code, so no gutter. Info bar shows "(binary, N commits)" correctly.
  - Issue 2: Fixed `yaml_escape()` in `aiscripts/aitask_explain_process_raw_data.py` to quote strings containing underscores (YAML interprets `228_2` as integer `2282`). Added `_` and space to the special-char check.
  - Issue 3: Replaced `hash()` modulo color assignment in `aiscripts/codebrowser/code_viewer.py` with a deterministic lookup table based on sorted unique task IDs, guaranteeing unique colors for up to 8 tasks.
- **Files affected:** `aiscripts/aitask_explain_process_raw_data.py`, `aiscripts/codebrowser/code_viewer.py`

## Final Implementation Notes

- **Actual work done:** Implemented all 4 planned steps (is_binary field, parse_reference_yaml update, _update_code_annotations binary handling, SKILL.md updates). Additionally fixed two pre-existing bugs discovered during review: yaml_escape not quoting child task IDs with underscores, and hash-based annotation color assignment causing collisions.
- **Deviations from plan:** Two additional fixes beyond the original 4 steps: (1) `yaml_escape()` in `aitask_explain_process_raw_data.py` now quotes strings with underscores to prevent YAML interpreting `228_2` as `2282`; (2) `_build_annotation_gutter()` in `code_viewer.py` now uses a sorted lookup table instead of `hash()` for deterministic unique color assignment.
- **Issues encountered:** User reported 3 issues during review. Issue 1 (binary file annotation pane) was working as designed — binary files can't display code lines, so no gutter is shown, but the info bar correctly shows "(binary, N commits)". Issues 2 and 3 were real bugs fixed.
- **Key decisions:** Binary files show commit count in the info bar rather than attempting any gutter visualization. The yaml_escape fix adds underscore and space to the quoting trigger characters. Color assignment sorts task IDs alphabetically for deterministic mapping.
- **Notes for sibling tasks:** The `yaml_escape()` fix affects all reference.yaml output, not just binary files. Old reference.yaml files with unquoted child task IDs will still display incorrectly until regenerated.

## Post-implementation

Refer to Step 9 of the task-workflow (archival, merge, cleanup).
