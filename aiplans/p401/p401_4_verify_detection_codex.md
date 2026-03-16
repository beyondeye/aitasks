---
Task: t401_4_verify_detection_codex.md
Parent Task: aitasks/t401_more_robust_self_detection_for_claude_code.md
Sibling Tasks: aitasks/t401/t401_1_*.md, aitasks/t401/t401_2_*.md, aitasks/t401/t401_3_*.md
Archived Sibling Plans: aiplans/archived/p401/p401_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Verification Plan: Detection on Codex CLI

## Steps

1. Launch Codex CLI in this repository
2. Pick a test task or trigger model-self-detection manually
3. Verify `./.aitask-scripts/aitask_parse_detected_agent.sh --agent codex --cli-id <model_id>` is called
4. Confirm output matches `AGENT_STRING:codex/<name>` from `models_codex.json`
5. Verify `implemented_with` metadata is set correctly

## Special: Codex model ID

Codex cannot self-identify — model ID comes from `~/.codex/config.toml`. Verify the grep command produces the right value.

## Step 9: Post-Implementation

Archive per standard workflow.
