---
priority: medium
effort: medium
depends: [1]
issue_type: feature
status: Done
labels: [codeagent, task_workflow, codexcli]
implemented_with: codex/gpt5
created_at: 2026-03-08 18:35
updated_at: 2026-03-09 10:49
completed_at: 2026-03-09 10:49
---

## Context

This child task establishes the shared commit-attribution mechanism for t339 and proves it end to end with Codex.

The task-workflow currently records `implemented_with` metadata but does not define a matching custom `Co-authored-by` trailer for non-Claude agents. This task should introduce the reusable resolver/procedure and wire it into the shared commit flow, using Codex as the first concrete supported agent.

## Key Files to Modify

- `.aitask-scripts/aitask_codeagent.sh` or a shared helper used by it — expose machine-readable commit-attribution data from an agent string
- `.claude/skills/task-workflow/procedures.md` — add the code-agent commit attribution procedure
- `.claude/skills/task-workflow/SKILL.md` — update Step 8 commit instructions to compose contributor and agent trailers
- `.claude/skills/aitask-pickrem/SKILL.md` — keep direct commit instructions aligned with the new procedure
- `.claude/skills/aitask-pickweb/SKILL.md` — keep direct commit instructions aligned with the new procedure
- `.claude/skills/aitask-wrap/SKILL.md` — keep direct commit instructions aligned with the new procedure
- `tests/test_codeagent.sh` — add resolver coverage for Codex coauthor output

## Reference Files for Patterns

- `.claude/skills/task-workflow/procedures.md` — current Contributor Attribution and Agent Attribution procedures
- `.aitask-scripts/aitask_codeagent.sh` — existing agent/model resolution logic
- `aitasks/metadata/models_codex.json` — canonical Codex model identifiers
- recent repository commits that include Claude-generated coauthor trailers — formatting reference only, not a requirement to match provider branding

## Implementation Plan

### 1. Add a reusable commit-attribution resolver

Expose a helper/subcommand that returns structured coauthor data from the standardized agent string and configured domain.

### 2. Add a task-workflow procedure for code-agent commit attribution

Document how Step 8 should resolve and append the agent trailer for non-Claude workflows.

### 3. Compose trailers safely

Define the final code commit shape so imported contributor attribution and code-agent attribution can coexist in the same commit message without losing either trailer.

### 4. Prove the path with Codex

Add tests and examples using a Codex agent string such as `codex/gpt5_3codex`.

## Verification Steps

- the resolver emits a Codex display name, email, and `Co-authored-by:` trailer
- Step 8 docs describe contributor + agent trailer composition clearly
- Codex-specific test coverage passes
