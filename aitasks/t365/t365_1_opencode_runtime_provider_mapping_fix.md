---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [opencode, verifiedstats]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-11 15:50
updated_at: 2026-03-11 16:47
---

## Context

This is child task 1 of t365 (verified stats for same model across different providers). It fixes the OpenCode model identity mismatch so runtime self-detection, `implemented_with`, and verified-score updates refer to the correct provider/model entry.

The investigation found that OpenCode runtime identification can produce provider-qualified model ids such as `openai/gpt-5.4`, while the current OpenCode catalog/discovery flow stores GPT-family entries under names derived from `opencode/*` ids such as `zen_gpt_5_4`. That mismatch can cause the task workflow to attribute runs to the wrong model/provider and update the wrong verified score entry.

## Key Files to Modify

- `.aitask-scripts/aitask_opencode_models.sh`
- `aitasks/metadata/models_opencode.json`
- `seed/models_opencode.json`
- `.claude/skills/task-workflow/procedures.md`
- `tests/test_codeagent.sh`

## Reference Files for Patterns

- `.aitask-scripts/aitask_codeagent.sh` - model resolution and agent-string handling
- `tests/test_codeagent.sh` - OpenCode coauthor and resolution coverage
- `.claude/skills/task-workflow/procedures.md` - Model Self-Detection Sub-Procedure

## Implementation Plan

### 1. Audit OpenCode provider/model identity rules

- Confirm exactly which ids are emitted by `opencode models --verbose` for GPT-family entries and how those ids differ from the runtime ids seen by OpenCode skills.
- Document the supported matching rule in code comments and in the task-workflow procedure so the fallback behavior is explicit.

### 2. Fix OpenCode model discovery naming

- Rework `.aitask-scripts/aitask_opencode_models.sh` so provider identity is not collapsed into `zen_*` names when doing so prevents correct attribution.
- Keep existing verified data preserved when entries are renamed or normalized.
- Ensure GPT-family entries can represent the correct provider/model identity needed by self-detection.

### 3. Harden runtime self-detection

- Update `.claude/skills/task-workflow/procedures.md` so OpenCode matching is:
  1. exact `cli_id` match
  2. explicit alias/normalized match only when unambiguous
  3. raw fallback when no safe mapping exists
- Prevent silent remapping of OpenAI GPT runtime ids to `zen_*` entries when the provider does not actually match.

### 4. Add regression coverage

- Extend `tests/test_codeagent.sh` with cases covering:
  - `gpt-5.4` provider mismatch regression
  - same base LLM available from multiple providers
  - unknown provider/runtime ids still falling back safely

## Verification Steps

- `bash tests/test_codeagent.sh`
- `ait codeagent coauthor opencode/<model>` returns the correct provider-aware display name
- OpenCode self-detection no longer attributes OpenAI GPT runs to `zen_gpt_5_4`
