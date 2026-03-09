---
Task: t341_3_update_skill_md_target_selection_codemap_drilldown.md
Parent Task: aitasks/t341_generalize_contribute_code_area_sel_in_contribute.md
Sibling Tasks: aitasks/t341/t341_1_define_code_areas_yaml_format_parser_and_codemap_script.md, aitasks/t341/t341_2_add_target_project_dual_mode_to_contribute_script.md
Archived Sibling Plans: aiplans/archived/p341/p341_1_*.md, aiplans/archived/p341/p341_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t341_3 — SKILL.md target selection, codemap sub-workflow, and drill-down

## Overview

Update `.claude/skills/aitask-contribute/SKILL.md` to add a framework-vs-project target selection (Step 0), an incremental codemap generation sub-workflow when `code_areas.yaml` is missing, hierarchical drill-down for project areas, and dynamic area updates for unlisted areas.

## Steps

### 1. Add Step 0: Target Selection

Insert before current Step 1. AskUserQuestion: "aitasks framework" vs "This project". If framework → existing flow with `--target framework`. If project → Step 0a.

### 2. Add Step 0a: Code Areas Check

Run `--list-areas --target project`. If fails → codemap generation sub-workflow. If succeeds → Step 2.

### 3. Add Codemap Generation Sub-workflow

Incremental multi-pass:
1. Run `aitask_codemap.sh --scan` (or `--scan --existing <path>` for partial files)
2. For each unmapped area: read representative files, generate AI description
3. Save progress periodically to `code_areas.yaml`
4. Commit via `./ait git`
5. Post-scan checkpoint: "Continue" or "Abort" (to free context)

### 4. Restructure Step 2 for project mode

Hierarchical drill-down with `--parent` flag. Include "Other (unlisted area)" at every level. If Other: ask path+description, use `--area-path`, update code_areas.yaml after contribution.

### 5. Update Steps 3-7 for project mode

All script calls include `--target project`. Issue target is project's repo (auto-detected). Update confirm dialog text.

### 6. Update Notes section

Document new flags, target selection, codemap sub-workflow, multi-pass behavior, dynamic area updates.

## Post-Implementation

- Reference Step 9 of task-workflow for archival
- Read through SKILL.md end-to-end for consistency
- Verify framework flow is completely unchanged
