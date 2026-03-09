---
Task: t341_2_add_target_project_dual_mode_to_contribute_script.md
Parent Task: aitasks/t341_generalize_contribute_code_area_sel_in_contribute.md
Sibling Tasks: aitasks/t341/t341_1_define_code_areas_yaml_format_parser_and_codemap_script.md, aitasks/t341/t341_3_update_skill_md_target_selection_codemap_drilldown.md
Archived Sibling Plans: aiplans/archived/p341/p341_1_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t341_2 — --target project dual-mode in aitask_contribute.sh

## Overview

Add `--target <framework|project>` and `--parent <area-name>` flags to `aitask_contribute.sh`. When `--target project`, the script reads areas from `code_areas.yaml` (via `parse_code_areas()` from t341_1), diffs against local branches, and creates issues on the project's own repo.

## Steps

### 1. Add ARG_TARGET and ARG_PARENT variables

Add to batch mode variables section (~line 22):
```bash
ARG_TARGET=""
ARG_PARENT=""
```

### 2. Extend parse_args()

Add cases (~line 548):
```bash
--target) ARG_TARGET="$2"; shift 2 ;;
--parent) ARG_PARENT="$2"; shift 2 ;;
```

Add validation for --target (framework|project).

### 3. Add list_project_areas() function

After `list_areas()` (~line 248):
- Outputs `MODE:project` + `TARGET:project` + AREA lines from `parse_code_areas()`
- Passes `--parent` filter if ARG_PARENT is set

### 4. Modify list_areas() to branch on target

If `ARG_TARGET == "project"` → call `list_project_areas()`. Otherwise existing code.

### 5. Extend resolve_area_dirs() for project mode

When `ARG_TARGET == "project"`, look up area path from `parse_code_areas()` output instead of AREAS array.

### 6. Extend list_changed_files() for project mode

When `ARG_TARGET == "project"`, use `git diff --name-only main -- <dirs>` (same as clone mode). No upstream fetching.

### 7. Extend generate_diff() for project mode

When `ARG_TARGET == "project"`, use `git diff main -- <files>`.

### 8. Extend detect_contribute_mode() for project mode

When `ARG_TARGET == "project"`, return `"project"`.

### 9. Update main() for project mode

When `ARG_TARGET == "project"` and `ARG_REPO` is empty, auto-detect from `git remote get-url origin`.

### 10. Add tests

- Backward compatibility: `--list-areas` without --target is unchanged
- `--list-areas --target project` reads code_areas.yaml
- `--list-areas --target project --parent <area>` returns children
- `--list-changes --target project --area <area>` finds files
- Dry-run with `--target project`

## Post-Implementation

- Reference Step 9 of task-workflow for archival
- Run shellcheck and tests
- Verify zero regressions in existing framework mode
