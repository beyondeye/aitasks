---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [task_workflow]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-17 18:52
updated_at: 2026-03-17 21:21
---

## Goal

Refactor `aitask_verified_update.sh` and `satisfaction-feedback.md` to reduce the number of steps an agent needs to record a satisfaction score.

## Changes

### 1. Add --agent/--cli-id to aitask_verified_update.sh

Add two new optional flags as an alternative to `--agent-string`:
- `--agent <agent>` — agent name (claudecode, geminicli, codex, opencode)
- `--cli-id <model_id>` — raw model ID from the agent's runtime (e.g., claude-opus-4-6)

When `--agent` and `--cli-id` are provided (instead of `--agent-string`), the script internally calls:
```bash
./.aitask-scripts/aitask_resolve_detected_agent.sh --agent <agent> --cli-id <cli_id>
```
and uses the resolved agent string. The existing `--agent-string` flag continues to work for backward compatibility.

Validation:
- If `--agent-string` is provided, `--agent`/`--cli-id` must NOT be provided (and vice versa)
- If `--agent`/`--cli-id` are used, both must be provided

### 2. Simplify satisfaction-feedback.md

Replace the current step 2 ("Execute the Model Self-Detection Sub-Procedure (see model-self-detection.md)") with inlined instructions:

1. Identify which code agent you are: `claudecode`, `geminicli`, `codex`, or `opencode`
2. Obtain your current model ID (agent-specific methods — keep the brief per-agent instructions from model-self-detection.md)
3. Call the script directly:
```bash
./.aitask-scripts/aitask_verified_update.sh --agent <agent> --cli-id <model_id> --skill "<skill_name>" --score <rating> --silent
```

This eliminates the need to read model-self-detection.md and call aitask_resolve_detected_agent.sh separately.

**Important:** Do NOT remove or modify `model-self-detection.md` itself — it is still referenced by `agent-attribution.md` for a different purpose.

### 3. Update test

Add test cases to `tests/test_resolve_detected_agent.sh` (or create a new test file) to verify the new `--agent`/`--cli-id` flags on `aitask_verified_update.sh` work correctly.

## Key Files

- `.aitask-scripts/aitask_verified_update.sh` — add --agent/--cli-id flags
- `.claude/skills/task-workflow/satisfaction-feedback.md` — simplify procedure
- `.aitask-scripts/aitask_resolve_detected_agent.sh` — reference (called internally, not modified)
- `.claude/skills/task-workflow/model-self-detection.md` — reference (not modified, still used by agent-attribution)

## Verification

1. `bash .aitask-scripts/aitask_verified_update.sh --agent claudecode --cli-id claude-opus-4-6 --skill test --score 5 --silent` → should resolve and update
2. `bash .aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill test --score 5 --silent` → backward compat still works
3. Providing both `--agent-string` and `--agent` should error
4. `shellcheck .aitask-scripts/aitask_verified_update.sh` — no warnings
