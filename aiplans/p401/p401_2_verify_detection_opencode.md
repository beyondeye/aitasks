---
Task: t401_2_verify_detection_opencode.md
Parent Task: aitasks/t401_more_robust_self_detection_for_claude_code.md
Sibling Tasks: aitasks/t401/t401_1_*.md, aitasks/t401/t401_3_*.md, aitasks/t401/t401_4_*.md
Archived Sibling Plans: aiplans/archived/p401/p401_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Verification Plan: Detection on OpenCode

## Steps

1. Launch OpenCode in this repository
2. Pick a test task or trigger model-self-detection manually
3. Verify `./.aitask-scripts/aitask_parse_detected_agent.sh --agent opencode --cli-id <model_id>` is called
4. Confirm output matches `AGENT_STRING:opencode/<name>` from `models_opencode.json`
5. Verify `implemented_with` metadata is set correctly

## Special: OpenCode suffix matching

Test with provider-qualified and bare model IDs to verify suffix match fallback works.

## Step 9: Post-Implementation

Archive per standard workflow.
