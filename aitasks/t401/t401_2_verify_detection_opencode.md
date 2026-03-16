---
priority: medium
effort: low
depends: [t401_1]
issue_type: test
status: Ready
labels: [task_workflow]
created_at: 2026-03-16 11:21
updated_at: 2026-03-16 11:21
---

## Context

Child task 1 (`t401_1`) created `.aitask-scripts/aitask_parse_detected_agent.sh` and updated `.opencode/instructions.md` and `.opencode/skills/opencode_tool_mapping.md` to use it. This task verifies the new procedure works end-to-end when running from OpenCode.

Parent task: `aitasks/t401_more_robust_self_detection_for_claude_code.md`

## Verification Steps

1. Launch OpenCode in this repository
2. Run a workflow that triggers model-self-detection (e.g., `/aitask-pick` on a test task, or manually invoke the Agent Attribution Procedure)
3. Confirm the script is called correctly: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent opencode --cli-id <model_id>`
4. Verify the output is a valid `AGENT_STRING:opencode/<name>` matching an entry in `aitasks/metadata/models_opencode.json`
5. Check that `implemented_with` is written correctly to the task frontmatter

## Key Files

- `.aitask-scripts/aitask_parse_detected_agent.sh` — The script being verified
- `.opencode/instructions.md` — Updated Agent Identification section
- `.opencode/skills/opencode_tool_mapping.md` — Updated Agent String section
- `aitasks/metadata/models_opencode.json` — OpenCode models (51 entries, provider-qualified cli_ids like `opencode/gpt-5.4`)

## Special Considerations

OpenCode models use provider-qualified `cli_id` values (e.g., `openai/gpt-5.4`, `opencode/claude-opus-4-6`). The script has a suffix match fallback for when OpenCode reports just the base model name without provider prefix. Verify both exact and suffix match scenarios work.
