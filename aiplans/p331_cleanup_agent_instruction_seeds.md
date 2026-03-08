---
Task: t331_cleanup_agent_instruction_seeds.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Plan: t331 - Cleanup Agent Instruction Seeds

## Summary

Reduce the three agent-specific seed files so they act only as agent-identification overlays. Remove the shared preamble and skills-location guidance that already belongs in the shared Layer 1 instructions.

## Implementation Steps

1. Update `seed/geminicli_instructions.seed.md` to keep only the existing `## Agent Identification` section.
2. Update `seed/codex_instructions.seed.md` to keep only the existing `## Agent Identification` section.
3. Update `seed/opencode_instructions.seed.md` to keep only the existing `## Agent Identification` section.
4. Preserve the existing agent-identification wording; do not broaden the task into other seed-file cleanup.

## Verification

- Confirm each target file has exactly one `##` heading.
- Confirm that heading is `## Agent Identification`.
- Review the diff to ensure only the three target seed files changed for implementation.

## Post-Implementation

After implementation, update this plan with final notes, commit code and plan changes separately, then archive task `331`.

## Final Implementation Notes

- **Actual work done:** Removed the shared preamble and `## Skills` sections from the Gemini CLI, Codex CLI, and OpenCode agent seed files so each now contains only `## Agent Identification`.
- **Deviations from plan:** None. The implementation stayed within the exact task scope.
- **Issues encountered:** None during the file edits or verification.
- **Key decisions:** Preserved the existing agent-identification wording verbatim and limited edits to the three target seed files.
