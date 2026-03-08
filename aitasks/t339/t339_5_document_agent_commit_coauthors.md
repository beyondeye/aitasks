---
priority: medium
effort: low
depends: [1, 2, 3, 4]
issue_type: documentation
status: Ready
labels: [codeagent, task_workflow, web_site]
created_at: 2026-03-08 18:36
updated_at: 2026-03-08 18:36
---

## Context

This child task documents the configurable code-agent commit coauthor mechanism introduced by t339.

The website docs should explain the new project-level email-domain setting, which workflows use the custom coauthor trailer, how imported contributor attribution composes with code-agent attribution, and what caveats remain for Claude Code if the native coauthor behavior cannot be replaced safely.

## Key Files to Modify

- `website/content/docs/skills/aitask-pick/` pages or nearby workflow docs — describe the new commit-attribution behavior where Step 8 is documented
- `website/content/docs/commands/setup-install.md` — document the new setup-time project config field
- `website/content/docs/tuis/settings/reference.md` or other config reference pages — add the new `project_config.yaml` field if settings/config reference coverage belongs there
- any overview/installation page that should mention the project-scoped coauthor domain setting

## Reference Files for Patterns

- `website/content/docs/skills/aitask-pick/build-verification.md` — existing documentation pattern for `project_config.yaml`
- `website/content/docs/commands/codeagent.md` — terminology for agent strings and model identifiers
- `.claude/skills/task-workflow/SKILL.md` and `procedures.md` — source of truth for workflow behavior to be documented

## Implementation Plan

### 1. Document the new project config field

Explain where the coauthor email domain lives, its default behavior, and how `ait setup` initializes it.

### 2. Document workflow commit behavior

Describe how code commits can now include both imported contributor attribution and code-agent attribution.

### 3. Document Claude caveat explicitly

If the Claude redesign remains risky or partial, document that limitation instead of implying parity.

## Verification Steps

- website docs build successfully
- the new config field is documented in the correct config/setup pages
- commit-attribution docs match actual workflow behavior and caveats
