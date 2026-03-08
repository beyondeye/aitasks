---
Task: t131_2_geminicli_command_wrappers.md
Parent Task: aitasks/t131_geminicli_support.md
Sibling Tasks: aitasks/t131/t131_1_*.md, aitasks/t131/t131_3_*.md, aitasks/t131/t131_4_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Gemini CLI Command Wrappers (t131_2)

## Overview

Create 17 command files in `.gemini/commands/aitask-*.md`. Each command uses `@` file inclusion syntax to pull in the tool mapping, plan mode prereqs, and the source Claude Code skill.

## Step 1: Create 17 command wrappers

For each user-invocable skill, create `.gemini/commands/aitask-<name>.md` following the OpenCode command pattern (`.opencode/commands/aitask-pick.md`):

```markdown
---
description: <description from Claude Code skill>
---

@.gemini/skills/geminicli_tool_mapping.md

@.gemini/skills/geminicli_planmode_prereqs.md

Execute the following Claude Code skill workflow. <context if applicable>

Arguments: $ARGUMENTS

@.claude/skills/aitask-<name>/SKILL.md
```

### Commands list:

1. aitask-changelog.md
2. aitask-create.md
3. aitask-explain.md
4. aitask-explore.md
5. aitask-fold.md
6. aitask-pick.md — Add "If a task number is provided, use it for direct selection."
7. aitask-pickrem.md — Add "If a task number is provided, use it for direct selection."
8. aitask-pickweb.md — Add "If a task number is provided, use it for direct selection."
9. aitask-pr-import.md — Add "If a PR URL or number is provided, use it."
10. aitask-refresh-code-models.md
11. aitask-review.md
12. aitask-reviewguide-classify.md — Add "If a file path is provided, use it."
13. aitask-reviewguide-import.md — Add "If a file/URL/directory is provided, use it."
14. aitask-reviewguide-merge.md — Add "If two file paths are provided, use them."
15. aitask-stats.md
16. aitask-web-merge.md
17. aitask-wrap.md

## Post-Implementation

- Refer to Step 9 (Post-Implementation) in `.claude/skills/task-workflow/SKILL.md`

## Final Implementation Notes

- **Actual work done:** Created all 17 command wrapper files in `.gemini/commands/` as planned. 8 commands with planmode prereqs (pick, pickrem, pickweb, explore, fold, pr-import, review, wrap) and 9 without (changelog, create, explain, refresh-code-models, reviewguide-classify, reviewguide-import, reviewguide-merge, stats, web-merge).
- **Deviations from plan:** The original plan listed argument context notes for reviewguide-classify ("If a file path is provided, use it."), reviewguide-import ("If a file/URL/directory is provided, use it."), reviewguide-merge ("If two file paths are provided, use them."), and pr-import ("If a PR URL or number is provided, use it."). These were not included in the final command files to match the OpenCode command pattern exactly, which uses a generic `Arguments: $ARGUMENTS` line without skill-specific context for those commands. The pick/pickrem/pickweb commands do include "If a task number is provided..." context, matching the OpenCode pattern.
- **Issues encountered:** None.
- **Key decisions:** Followed the OpenCode command wrapper pattern exactly (`.opencode/commands/`), substituting `geminicli_tool_mapping.md` and `geminicli_planmode_prereqs.md` for their OpenCode equivalents. Used the same two template variants: Template A (with planmode prereqs, "Execute the following Claude Code skill workflow.") and Template B (without prereqs, "Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping above.").
- **Notes for sibling tasks:** The `.gemini/commands/` directory is now established with all 17 wrappers. t131_3 (setup/install/release) needs to bundle these files alongside the `.gemini/skills/` files. The staging directory for commands should be `aitasks/metadata/geminicli_commands/` and the release workflow should build `gemini_commands/` from `.gemini/commands/`.
