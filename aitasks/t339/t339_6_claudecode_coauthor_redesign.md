---
priority: medium
effort: high
depends: [2, 3, 4, 5]
issue_type: feature
status: Implementing
labels: [codeagent, task_workflow, claudecode]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-08 18:36
updated_at: 2026-03-09 11:37
---

## Context

This child task is the final and highest-risk part of t339. It attempts to replace or suppress Claude Code’s native coauthor mechanism so Claude commits can use the same custom `<code agent> + <model>` trailer format as the other agents.

Unlike Codex, Gemini CLI, and OpenCode, Claude Code already injects its own coauthor trailer today. That means this task may fail if the native behavior cannot be disabled or if the custom mechanism would cause duplicate coauthor lines. A documented safe no-op is an acceptable outcome if replacement proves impossible without regressions.

## Key Files to Modify

- `.claude/skills/task-workflow/procedures.md` — document any Claude-specific branch or guard in the custom commit-attribution procedure
- `.claude/skills/task-workflow/SKILL.md` — clarify Claude-specific behavior in Step 8 if it differs from the non-Claude path
- `.aitask-scripts/aitask_codeagent.sh` or shared resolver helper — only if Claude-specific identity formatting needs explicit support in the shared resolver
- relevant Claude-facing documentation only if the behavior actually changes

## Reference Files for Patterns

- recent repository commits made by Claude Code — observe current native `Co-Authored-By` behavior
- `.claude/skills/task-workflow/procedures.md` — the shared mechanism introduced by earlier t339 children
- `aitasks/metadata/models_claudecode.json` — canonical Claude model identifiers

## Implementation Plan

### 1. Confirm how Claude currently injects attribution

Verify whether the existing Claude coauthor trailer is purely tool-native or can be influenced by the workflow’s commit-message shape.

### 2. Attempt safe replacement

If Claude supports a clean override path, route it through the same custom resolver so the trailer becomes `Claude Code + <model>` with the configured domain.

### 3. Guard against duplicate attribution

Do not ship a change that can produce both the native Claude trailer and the custom trailer on the same commit unless the duplication is intentionally filtered or suppressed.

### 4. Fall back safely if needed

If native Claude attribution cannot be replaced reliably, keep Claude on the current mechanism and document the limitation clearly.

## Verification Steps

- test for duplicate Claude coauthor trailers explicitly
- verify whether native Claude attribution can be suppressed or replaced in practice
- if replacement is unsafe, document the limitation and leave non-Claude support intact
