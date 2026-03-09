---
Task: t341_1_define_code_areas_yaml_format_parser_and_codemap_script.md
Parent Task: aitasks/t341_generalize_contribute_code_area_sel_in_contribute.md
Sibling Tasks: aitasks/t341/t341_2_add_target_project_dual_mode_to_contribute_script.md, aitasks/t341/t341_3_update_skill_md_target_selection_codemap_drilldown.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t341_1 — code_areas.yaml format, parser, and codemap script

## Overview

Create the foundational metadata format (`code_areas.yaml`), a bash YAML parser (`parse_code_areas()`) in `aitask_contribute.sh`, and a structural scanning script (`aitask_codemap.sh`). This is the base that t341_2 and t341_3 build upon.

## Steps

### 1. Create `seed/code_areas.yaml` [DONE]

Seed template with extensive comments documenting the format (follow `seed/project_config.yaml` pattern). Contains `version: 1` and `areas: []` as default.

### 2. Add `parse_code_areas()` to `aitask_contribute.sh` [DONE]

Added after the AREAS array (~line 51). Parser uses `awk` to:
- Track current entry context (name, path, description, parent)
- Detect indentation level: 2-space = top-level area, 6-space = child (standard YAML 2-space indent)
- Output `AREA|<name>|<path>|<description>|<parent>` per entry
- Support `--parent <name>` filter argument
- Exit 1 with `NO_CODE_AREAS` stderr message if file not found

Uses `$TASK_DIR/metadata/code_areas.yaml` path convention from `task_utils.sh`.

Also added source guard (`[[ "${BASH_SOURCE[0]}" == "${0}" ]] && main "$@"`) to enable sourcing for testing.

### 3. Create `.aitask-scripts/aitask_codemap.sh` [DONE]

New internal-only script:
- Shebang: `#!/usr/bin/env bash`, `set -euo pipefail`
- Source `terminal_compat.sh` for `die()`/`info()`, `task_utils.sh` for `$TASK_DIR`
- Flags: `--scan`, `--scan --existing <path>`, `--write`, `--help`
- Excludes framework dirs: `.aitask-scripts`, `aitasks`, `aiplans`, `.claude`, `.gemini`, etc.
- For dirs with >2 immediate subdirs: generates one level of children
- `--existing`: outputs only areas not already present in the given file
- `--write`: writes to `$TASK_DIR/metadata/code_areas.yaml` (refuses if exists)

### 4. Update `aitask_setup.sh` [DONE]

Added `cp "$project_dir/seed/code_areas.yaml" ...` at line 1009 (alongside project_config.yaml copy).

### 5. Add tests to `tests/test_contribute.sh` [DONE]

9 new tests (17-25), all passing:
- Test 17: parse_code_areas with valid YAML (5 assertions)
- Test 18: parse_code_areas --parent filter (4 assertions)
- Test 19: parse_code_areas with missing file
- Test 20: parse_code_areas with empty areas
- Test 21: aitask_codemap.sh --scan in temp git repo
- Test 22: aitask_codemap.sh --scan with children generation
- Test 23: aitask_codemap.sh --scan --existing filters mapped areas
- Test 24: aitask_codemap.sh --write refuses if exists
- Test 25: aitask_codemap.sh --write creates file

## Verification Notes (2026-03-09)

All reference points confirmed against codebase:
- AREAS array at `aitask_contribute.sh:43-50` — 6 hardcoded entries, pipe-delimited `name|dirs|desc`
- `list_areas()` at `aitask_contribute.sh:229-248` — outputs `AREA|name|dirs|desc` (3 fields)
- `parse_code_areas()` will output `AREA|name|path|desc|parent` (4 fields, adds parent tracking)
- `seed/project_config.yaml` — 71 lines, extensive commented YAML template pattern
- `aitask_setup.sh:1005-1016` — seed copy block, uses `cp ... 2>/dev/null || true` pattern
- `tests/test_contribute.sh` — 382 lines, uses `assert_eq`/`assert_contains` helpers
- `terminal_compat.sh` — `die()`, `warn()`, `info()`, `success()` available
- `task_utils.sh:14-18` — `TASK_DIR` defaults to `aitasks`
- `code_areas.yaml` does NOT exist yet in either `seed/` or `aitasks/metadata/`

Plan is sound and ready for implementation.

## Final Implementation Notes

- **Actual work done:** All 5 planned steps completed as designed — seed template, awk parser, codemap script, setup integration, and tests
- **Deviations from plan:** YAML indent levels corrected from 4/8-space to 2/6-space (standard YAML 2-space indent). Added source guard to `aitask_contribute.sh` to enable function-level testing. Initial plan mentioned indent levels of 4/8 but the actual YAML structure uses 2-space base indent
- **Issues encountered:** First test run failed because awk patterns assumed 4-space indent for top-level YAML list items; standard YAML uses 2-space. Also, `source aitask_contribute.sh` was not testable because `main "$@"` ran unconditionally — added `BASH_SOURCE` guard
- **Key decisions:** Used `NO_CODE_AREAS` sentinel on stderr (not just exit code) for missing file detection. Codemap script filters 12 framework directories. Children threshold is >2 subdirs
- **Notes for sibling tasks:** `parse_code_areas()` outputs `AREA|name|path|desc|parent` — t341_2 should use this function for project-mode area listing. The source guard in contribute.sh means `main` only runs when executed directly. Codemap can be called from the skill to generate initial code areas

## Post-Implementation

- Reference Step 9 of task-workflow for archival
- Run `shellcheck .aitask-scripts/aitask_codemap.sh`
- Run `bash tests/test_contribute.sh`
