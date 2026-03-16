---
priority: medium
effort: low
depends: [t401_1]
issue_type: test
status: Ready
labels: [task_workflow]
created_at: 2026-03-16 11:21
updated_at: 2026-03-16 11:36
---

## Context

Child task 1 (`t401_1`) created `.aitask-scripts/aitask_parse_detected_agent.sh` and updated `.gemini/skills/geminicli_tool_mapping.md` to use it. This task verifies the new procedure works end-to-end when running from Gemini CLI.

Parent task: `aitasks/t401_more_robust_self_detection_for_claude_code.md`

## Verification Steps

1. Launch Gemini CLI in this repository
2. Run a workflow that triggers model-self-detection (e.g., `/aitask-pick` on a test task, or manually invoke the Agent Attribution Procedure)
3. Confirm the script is called correctly: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent geminicli --cli-id <model_id>`
4. Verify the output is a valid `AGENT_STRING:geminicli/<name>` matching an entry in `aitasks/metadata/models_geminicli.json`
5. Check that `implemented_with` is written correctly to the task frontmatter

## Key Files

- `.aitask-scripts/aitask_parse_detected_agent.sh` — The script being verified
- `.gemini/skills/geminicli_tool_mapping.md` — Updated Agent String section
- `aitasks/metadata/models_geminicli.json` — Gemini CLI models (5 entries)

## Special Considerations

Gemini CLI identifies its model from system context or from `~/.gemini/settings.json`. Verify that the model ID passed to the script matches a `cli_id` in the models file.
