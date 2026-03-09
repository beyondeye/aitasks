---
Task: t339_7_project_config_editing_in_ait_settings.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_1_*.md, aitasks/t339/t339_2_*.md, aitasks/t339/t339_3_*.md, aitasks/t339/t339_4_*.md, aitasks/t339/t339_5_*.md, aitasks/t339/t339_6_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_7 — Project Config Editing in Settings

## Overview

Add a first-class editable surface in `ait settings` for shared values from `aitasks/metadata/project_config.yaml`, then update the Settings TUI docs to match.

## Status Note

Part of this plan was already implemented during `t339_1`. Before working on this child, verify what remains unfinished and trim the scope to cleanup, refinement, or any missing cases that `t339_1` did not complete.

## Steps

### 1. Load and save project config YAML

Add reusable YAML config helpers for the Settings app and use them to load/save `project_config.yaml`.

### 2. Add a Project Config tab

Expose editable project-scoped settings in the Settings TUI with an initial focus on:

- `codeagent_coauthor_domain`
- `verify_build`

### 3. Update Settings docs

Document the new tab/shortcut and the editable `project_config.yaml` keys in the Settings docs only.

### 4. Add regression coverage

Cover YAML helper round-trips and the coauthor-domain setup/helper behavior touched by this sibling's supporting changes.

## Verification

- project-config YAML helpers round-trip cleanly
- `ait settings` exposes the Project Config tab
- Settings docs reflect the new tab, shortcut, and config file

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.


## Final Implementation Notes
- **Actual work done:** Confirmed that t339_1 already implemented the Settings TUI Project Config tab and YAML helpers. Added missing regression tests in tests/test_config_utils.py for save_yaml_config and load_yaml_config to complete the scope.
- **Deviations from plan:** None, just skipped redundant work already done in t339_1.
- **Issues encountered:** None.
- **Key decisions:** Avoided reimplementing TUI features, focused on regression test coverage.
- **Notes for sibling tasks:** The YAML helpers are now fully tested for edge cases.
