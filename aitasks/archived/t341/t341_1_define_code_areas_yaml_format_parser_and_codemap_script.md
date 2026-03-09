---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-09 13:06
updated_at: 2026-03-09 16:11
completed_at: 2026-03-09 16:11
---

Define the code_areas.yaml metadata format for hierarchical project code areas. Create a bash YAML parser (parse_code_areas) in aitask_contribute.sh. Create aitask_codemap.sh for structural scanning. Add seed template and setup integration.

## Context

The `/aitask-contribute` skill currently has 6 hardcoded code areas in `.aitask-scripts/aitask_contribute.sh` (lines 43-50), all specific to the aitasks framework. Task t341 generalizes the skill to also support contributing to the project where the framework is installed. This child task creates the foundational metadata format and tooling that t341_2 and t341_3 build upon.

## Key Files to Modify

- **Create** `seed/code_areas.yaml` — Seed template with format docs and commented examples (follow pattern of `seed/project_config.yaml`)
- **Create** `.aitask-scripts/aitask_codemap.sh` — Internal-only script for structural scanning (NOT an `ait` subcommand)
- **Modify** `.aitask-scripts/aitask_contribute.sh` — Add `parse_code_areas()` function after the existing AREAS array (~line 50)
- **Modify** `.aitask-scripts/aitask_setup.sh` — Add copy of `code_areas.yaml` during setup (follow pattern at line ~1008 for `project_config.yaml`)
- **Extend** `tests/test_contribute.sh` — Add tests for YAML parsing and codemap scanning

## Reference Files for Patterns

- `seed/project_config.yaml` — Seed template pattern with extensive commented documentation
- `.aitask-scripts/aitask_contribute.sh:43-50` — Existing AREAS array showing current format
- `.aitask-scripts/aitask_contribute.sh:229-248` — `list_areas()` function showing AREA output format
- `.aitask-scripts/aitask_setup.sh:1008` — Seed file copy pattern during setup
- `.aitask-scripts/aitask_setup.sh:1142-1182` — `ensure_project_config_defaults()` pattern
- `tests/test_contribute.sh` — Existing test helpers and patterns

## Implementation Plan

### Step 1: Define code_areas.yaml format

Create `seed/code_areas.yaml`:
```yaml
# Code areas map — hierarchical project structure for /aitask-contribute (project mode)
#
# This file maps your project's code areas for the contribute workflow.
# When contributing to the project itself (not the aitasks framework),
# this file defines which areas of your codebase are available for selection.
#
# Generated with: ./.aitask-scripts/aitask_codemap.sh --scan
# AI-enhanced descriptions are added by the /aitask-contribute skill.
#
# Format:
#   version: 1
#   areas:
#     - name: <area-name>           # Short identifier (no spaces, lowercase)
#       path: <relative-path>/      # Relative to repo root, trailing /
#       description: <text>         # Human-readable description
#       children:                   # Optional sub-areas
#         - name: <child-name>
#           path: <child-path>/
#           description: <text>
#
# Rules:
#   - 2-space YAML indent
#   - One path per entry (relative to repo root, trailing /)
#   - children: is optional (omit for leaf areas)
#   - version: 1 is required
#
# Example:
#   areas:
#     - name: backend
#       path: src/backend/
#       description: REST API and business logic
#       children:
#         - name: auth
#           path: src/backend/auth/
#           description: Authentication and JWT handling
#         - name: models
#           path: src/backend/models/
#           description: Database models and migrations
#     - name: frontend
#       path: src/web/
#       description: React frontend application
#     - name: tests
#       path: tests/
#       description: Test suites

version: 1

areas: []
```

### Step 2: Create parse_code_areas() in aitask_contribute.sh

Add after the AREAS array (~line 50). The function:
- Reads `aitasks/metadata/code_areas.yaml` (path resolved via `$TASK_DIR/metadata/code_areas.yaml`)
- Uses `awk` to parse the simple nested YAML (track indentation level for parent/child)
- Outputs `AREA|<name>|<path>|<description>|<parent>` lines
- `<parent>` is empty for top-level areas, parent name for children
- Supports optional `--parent <name>` argument to filter children only
- Returns exit code 1 if file not found (with error to stderr)

Parsing approach: Lines matching `- name:` at 4-space indent are top-level; at 8-space indent they're children. Following `path:` and `description:` lines belong to the current entry.

### Step 3: Create aitask_codemap.sh

New internal script with standard shebang and set -euo pipefail:
- `--scan` flag: Uses `git ls-files` to discover directories, filters out framework dirs, outputs skeleton YAML
- `--scan --existing <path>` flag: Reads existing code_areas.yaml, outputs only unmapped areas
- `--write` flag: Writes skeleton to `aitasks/metadata/code_areas.yaml` (refuses if file exists)
- Filters: `.aitask-scripts/`, `aitasks/`, `aiplans/`, `.claude/`, `.gemini/`, `.agents/`, `.opencode/`, `seed/`, `node_modules/`, `__pycache__/`, `.git/`
- For dirs with >2 immediate subdirs: generates one level of children
- Description defaults to cleaned-up directory name (replace hyphens/underscores with spaces)

### Step 4: Update aitask_setup.sh

Add `code_areas.yaml` copy to setup flow (near line 1008):
```bash
cp "$project_dir/seed/code_areas.yaml" "$project_dir/.aitask-data/aitasks/metadata/" 2>/dev/null || true
```

### Step 5: Add tests

Extend `tests/test_contribute.sh`:
- Test `parse_code_areas()` with a known YAML file → verify output format
- Test `--parent` filter returns only children
- Test missing file → verify error exit code
- Test `aitask_codemap.sh --scan` in a temp git repo → verify valid YAML output
- Test `--scan --existing` → verify only unmapped areas returned

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_codemap.sh` passes
2. `bash tests/test_contribute.sh` — all new and existing tests pass
3. `./.aitask-scripts/aitask_codemap.sh --scan` in the aitasks repo itself produces valid YAML listing non-framework dirs (e.g., `tests/`)
4. Create a temp `code_areas.yaml` and verify `parse_code_areas` output
