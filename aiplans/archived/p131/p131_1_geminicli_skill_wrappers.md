---
Task: t131_1_geminicli_skill_wrappers.md
Parent Task: aitasks/t131_geminicli_support.md
Sibling Tasks: aitasks/t131/t131_2_*.md, aitasks/t131/t131_3_*.md, aitasks/t131/t131_4_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

# Plan: Gemini CLI Skill Wrappers (t131_1)

## Overview

Create 19 files in `.gemini/skills/`:
- 1 tool mapping file
- 1 plan mode prerequisites file
- 17 skill wrapper directories

## Step 1: Create `.gemini/skills/geminicli_tool_mapping.md`

Follow `.opencode/skills/opencode_tool_mapping.md` pattern. Include:

1. Tool mapping table (Claude Code → Gemini CLI)
2. AskUserQuestion adaptation section — Gemini CLI has a good equivalent, no constraints
3. Plan mode section — no toggle, plan inline
4. Sub-skill references — use `activate_skill(name)` or read skill file directly
5. Agent string section — `geminicli/<model_name>` from `models_geminicli.json`
6. Task-workflow adaptations — same content as OpenCode's (plan file creation, post-implementation finalization)

## Step 2: Create `.gemini/skills/geminicli_planmode_prereqs.md`

Follow `.opencode/skills/opencode_planmode_prereqs.md` pattern:
- Gemini CLI has no EnterPlanMode/ExitPlanMode
- Plan inline: announce planning phase, use read-only tools, present plan, ask approval
- Checkpoints: ask questions naturally
- Abort handling: follow abort procedure from source skill

## Step 3: Create 17 skill wrappers

For each skill, read the Claude Code skill's frontmatter to get the `description` and argument info. Create `.gemini/skills/aitask-<name>/SKILL.md` with:

```markdown
---
name: aitask-<name>
description: <from Claude Code skill>
---

## Plan Mode Prerequisites

**BEFORE executing the workflow**, read **`.gemini/skills/geminicli_planmode_prereqs.md`**
and follow its guidance for plan mode phases.

## Source of Truth

This is a Gemini CLI wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-<name>/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Gemini CLI adaptations, read **`.gemini/skills/geminicli_tool_mapping.md`**.

## Arguments

<skill-specific argument description>
```

### Skills list with descriptions and arguments:

1. **aitask-changelog** — Generate changelog from commits and archived plans. No arguments.
2. **aitask-create** — Create a new AI task file. No arguments (interactive).
3. **aitask-explain** — Explain files: functionality, usage, code history. Accepts file path argument.
4. **aitask-explore** — Explore codebase interactively, then create a task. No arguments.
5. **aitask-fold** — Identify and merge related tasks. No arguments.
6. **aitask-pick** — Select next task for implementation. Optional task ID: `/aitask-pick 16` or `/aitask-pick 16_2`.
7. **aitask-pickrem** — Pick and implement task in remote/non-interactive mode. Optional task ID.
8. **aitask-pickweb** — Pick and implement task on Claude Code Web. Optional task ID.
9. **aitask-pr-import** — Create aitask from a pull request. Accepts PR URL or number.
10. **aitask-refresh-code-models** — Research latest AI models and update config. No arguments.
11. **aitask-review** — Review code using configurable review guides. No arguments.
12. **aitask-reviewguide-classify** — Classify a review guide file. Accepts file path.
13. **aitask-reviewguide-import** — Import external content as reviewguide. Accepts file/URL/directory.
14. **aitask-reviewguide-merge** — Compare and merge two review guides. Accepts two file paths.
15. **aitask-stats** — Display task completion statistics. No arguments.
16. **aitask-web-merge** — Merge completed Claude Web branches. No arguments.
17. **aitask-wrap** — Wrap uncommitted changes into an aitask. No arguments.

## Post-Implementation

- Refer to Step 9 (Post-Implementation) in `.claude/skills/task-workflow/SKILL.md`

## Final Implementation Notes

- **Actual work done:** Created all 19 files as planned — 1 tool mapping file (`geminicli_tool_mapping.md`), 1 plan mode prereqs file (`geminicli_planmode_prereqs.md`), and 17 skill wrappers in `.gemini/skills/aitask-*/SKILL.md`. Followed the OpenCode wrapper pattern exactly, adapting references from OpenCode to Gemini CLI.
- **Deviations from plan:** None. Implementation matched the plan precisely.
- **Issues encountered:** None.
- **Key decisions:** Used the same plan mode prereqs structure as OpenCode (8 skills with planning phases get the prereqs section). Tool mapping covers Gemini CLI-specific tools like `run_shell_command`, `replace`, `activate_skill`, `codebase_investigator`/`generalist` for sub-agents, and `google_web_search`/`web_fetch` for external info.
- **Notes for sibling tasks:** The `.gemini/skills/` directory is now established. t131_2 (command wrappers) should create `.gemini/commands/` following the same pattern used by `.opencode/commands/`. The tool mapping and planmode prereqs files are shared across both skills and commands. The `geminicli_tool_mapping.md` includes the agent string convention (`geminicli/<model_name>` from `models_geminicli.json`) which will be needed for proper agent attribution.
