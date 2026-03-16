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

Child task 1 (`t401_1`) created `.aitask-scripts/aitask_parse_detected_agent.sh` and updated `.codex/instructions.md` and `.agents/skills/codex_tool_mapping.md` to use it. This task verifies the new procedure works end-to-end when running from Codex CLI.

Parent task: `aitasks/t401_more_robust_self_detection_for_claude_code.md`

## Verification Steps

1. Launch Codex CLI in this repository
2. Run a workflow that triggers model-self-detection (e.g., `$aitask-pick` on a test task, or manually invoke the Agent Attribution Procedure)
3. Confirm the script is called correctly: `./.aitask-scripts/aitask_parse_detected_agent.sh --agent codex --cli-id <model_id>`
4. Verify the output is a valid `AGENT_STRING:codex/<name>` matching an entry in `aitasks/metadata/models_codex.json`
5. Check that `implemented_with` is written correctly to the task frontmatter

## Key Files

- `.aitask-scripts/aitask_parse_detected_agent.sh` — The script being verified
- `.codex/instructions.md` — Updated Agent Identification section
- `.agents/skills/codex_tool_mapping.md` — Updated Agent String section
- `aitasks/metadata/models_codex.json` — Codex CLI models (6 entries)

## Special Considerations

Codex models cannot reliably self-identify from system context. The model ID is read from `~/.codex/config.toml` via: `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'`. Verify this command produces the correct cli_id for the configured model.
