---
priority: medium
effort: medium
depends: [2]
issue_type: feature
status: Implementing
labels: [codeagent, task_workflow, opencode]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-08 18:36
updated_at: 2026-03-09 12:32
---

## Context

This child task extends the shared t339 commit-attribution mechanism to OpenCode.

OpenCode uses its own model catalog and can expose provider-prefixed model IDs, so this task must verify that the shared coauthor resolver behaves predictably for OpenCode model strings while still producing the standardized `<agent>_<model>@<domain>` email shape.

## Key Files to Modify

- `.aitask-scripts/aitask_codeagent.sh` or shared resolver helper — ensure OpenCode model identifiers are transformed consistently for coauthor output
- `aitasks/metadata/models_opencode.json` usage sites — confirm display-name resolution uses the intended OpenCode model metadata
- `.claude/skills/task-workflow/procedures.md` — add OpenCode notes only if the shared logic needs agent-specific caveats
- `tests/test_codeagent.sh` — add OpenCode resolver coverage

## Reference Files for Patterns

- `aitasks/metadata/models_opencode.json` — canonical OpenCode model identifiers
- `.aitask-scripts/aitask_opencode_models.sh` — reference for how OpenCode model IDs are currently treated in the repo
- shared resolver/procedure changes introduced in earlier t339 children

## Implementation Plan

### 1. Validate OpenCode model handling

Ensure provider-prefixed or nonstandard OpenCode model IDs still produce a stable display name and email local-part for coauthor output.

### 2. Add OpenCode test coverage

Cover at least one current OpenCode model entry from `models_opencode.json`.

### 3. Update shared documentation only if needed

Keep the shared procedure generic unless OpenCode truly needs an explicit caveat.

## Verification Steps

- OpenCode resolver output uses the configured domain
- OpenCode test coverage passes
- any OpenCode-specific caveat is documented only if required by actual model-id behavior
