---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [codeagent, ait_settings, task_workflow]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt-5
created_at: 2026-03-08 18:35
updated_at: 2026-03-09 09:52
completed_at: 2026-03-09 09:52
---

## Context

This child task adds project-scoped configuration for the custom code-agent commit coauthor email domain.

The new coauthor mechanism for t339 must not hardcode `aitasks.io`. The domain should live in shared project metadata so all task-workflow consumers derive the same `Co-authored-by` email format, and `ait setup` should initialize that metadata when a project is configured to use aitasks.

## Key Files to Modify

- `.aitask-scripts/aitask_setup.sh` — initialize or preserve the project coauthor domain during setup/reruns
- `seed/project_config.yaml` — document the new project-level config field and its default/example value
- `aitasks/metadata/project_config.yaml` — config surface that will store the new field in initialized projects
- `.aitask-scripts/aitask_codeagent.sh` or shared helper used by it — read the configured domain when building code-agent coauthor emails

## Reference Files for Patterns

- `seed/project_config.yaml` — existing project-scoped config file and documentation style
- `.aitask-scripts/aitask_setup.sh` — current setup flow that seeds `project_config.yaml`
- `.claude/skills/task-workflow/SKILL.md` — existing use of `project_config.yaml` via `verify_build`

## Implementation Plan

### 1. Extend project_config.yaml

Add a new shared field for the coauthor email domain in `project_config.yaml`. Keep it project-scoped and git-tracked.

### 2. Update ait setup

Teach `ait setup` to ensure the field exists when aitasks is configured in a project. Preserve an existing custom value on rerun instead of clobbering it.

### 3. Expose the config to commit-attribution code

Make the commit-attribution resolver read the configured domain from `aitasks/metadata/project_config.yaml`, with a documented default when the field is absent.

### 4. Document expected email format

Document that commit coauthor emails will be built as `<agent>_<model>@<configured-domain>`.

## Verification Steps

- `ait setup` on a fresh project creates `project_config.yaml` with the new field
- rerunning `ait setup` preserves an existing custom domain
- commit-attribution resolution uses the configured domain instead of a hardcoded one
