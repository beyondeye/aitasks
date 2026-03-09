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

### 1. Create `seed/code_areas.yaml`

Seed template with extensive comments documenting the format (follow `seed/project_config.yaml` pattern). Contains `version: 1` and `areas: []` as default.

### 2. Add `parse_code_areas()` to `aitask_contribute.sh`

Add after the AREAS array (~line 50). Parser uses `awk` to:
- Track current entry context (name, path, description, parent)
- Detect indentation level: 4-space = top-level area, 8-space = child
- Output `AREA|<name>|<path>|<description>|<parent>` per entry
- Support `--parent <name>` filter argument
- Exit 1 with stderr message if file not found

Key: The code_areas.yaml path should be `$SCRIPT_DIR/../aitasks/metadata/code_areas.yaml` (or use the `$TASK_DIR` convention from `task_utils.sh`).

### 3. Create `.aitask-scripts/aitask_codemap.sh`

New internal-only script:
- Shebang: `#!/usr/bin/env bash`, `set -euo pipefail`
- Source `terminal_compat.sh` for `die()`/`info()`
- Flags: `--scan`, `--scan --existing <path>`, `--write`
- Logic:
  1. `git ls-files` → extract unique top-level dirs
  2. Filter framework dirs
  3. For each dir: count immediate subdirs. If >2, generate children
  4. Output YAML with `version: 1` header
  5. `--existing`: Parse given code_areas.yaml, only output areas not already present
  6. `--write`: Write to `aitasks/metadata/code_areas.yaml` (refuse if exists)

### 4. Update `aitask_setup.sh`

Add copy of `code_areas.yaml` seed template during setup (~line 1008, alongside project_config.yaml copy).

### 5. Add tests to `tests/test_contribute.sh`

- Test parse_code_areas with a temp YAML file
- Test --parent filter
- Test missing file error
- Test aitask_codemap.sh --scan in a temp git repo
- Test --scan --existing with partial file

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

## Post-Implementation

- Reference Step 9 of task-workflow for archival
- Run `shellcheck .aitask-scripts/aitask_codemap.sh`
- Run `bash tests/test_contribute.sh`
