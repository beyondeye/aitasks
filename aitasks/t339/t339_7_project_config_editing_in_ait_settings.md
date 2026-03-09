---
priority: medium
effort: medium
depends: [1]
issue_type: feature
status: Ready
labels: [codeagent, ait_settings, web_site]
created_at: 2026-03-09 00:00
updated_at: 2026-03-09 09:51
---

## Context

This child task extends t339 by making the shared `project_config.yaml` settings editable from the `ait settings` TUI.

The coauthor-domain work from `t339_1` introduces a new shared project setting that users should not have to edit manually in YAML. The Settings TUI already edits project and user JSON configs plus execution profiles, so this task should add a first-class editing surface for `aitasks/metadata/project_config.yaml` and document it in the Settings docs.

**Note:** During `t339_1`, part of this child's intended scope was already implemented: the Settings TUI gained a Project Config tab, YAML helper support, and the initial Settings docs updates. Use this child as follow-up tracking for any remaining cleanup, refinement, or scope reconciliation rather than reimplementing that work from scratch.

## Key Files to Modify

- `.aitask-scripts/settings/settings_app.py` — load/save `project_config.yaml` and expose editable project-config fields in the TUI
- `.aitask-scripts/lib/config_utils.py` or adjacent helper used by settings_app — add any YAML config helpers needed by the TUI
- `website/content/docs/tuis/settings/_index.md` — document the new Project Config tab/section
- `website/content/docs/tuis/settings/how-to.md` — add a how-to for editing project config values
- `website/content/docs/tuis/settings/reference.md` — update shortcuts, tabs, config-file reference, and project-config key reference

## Reference Files for Patterns

- `.aitask-scripts/settings/settings_app.py` — existing editable tabs for Board and Profiles
- `aitasks/metadata/project_config.yaml` — current project-scoped settings file edited by this task
- `website/content/docs/tuis/settings/` — existing docs structure for the Settings TUI

## Implementation Plan

### 1. Reconcile the existing project-config support

Start by reviewing what `t339_1` already landed in the Settings TUI and docs, then narrow this child to any remaining gaps or cleanup.

### 2. Expose the initial editable keys

Support at least:

- `codeagent_coauthor_domain`
- `verify_build`

Save changes back to YAML while preserving unrelated keys.

### 3. Update the Settings docs if gaps remain

Document the new project-config editing surface only in the Settings docs. Do not fold this into the broader coauthor workflow docs from `t339_5`.

### 4. Add verification coverage

Add tests for YAML project-config helpers and for the new coauthor-domain setup/helper path where relevant.

## Verification Steps

- the Settings TUI shows a project-config editing surface
- editing `codeagent_coauthor_domain` persists to `aitasks/metadata/project_config.yaml`
- editing `verify_build` persists valid YAML
- the Settings docs match the implemented tab names, shortcuts, and file paths
