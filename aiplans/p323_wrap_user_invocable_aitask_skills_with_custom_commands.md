---
Task: t323_wrap_user_invocable_aitask_skills_with_custom_commands.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t323 — Custom Command Wrappers + Skill Enhancements for OpenCode

## Context

OpenCode supports skills (`.opencode/skills/`) and commands (`.opencode/commands/`).
Skills existed as minimal wrappers. Commands didn't exist. Complex skills lacked
plan-mode guidance that Codex CLI provides via prerequisites.

## Implementation

### Part A: Shared Files

1. **Cleaned up `.opencode/skills/opencode_tool_mapping.md`** — removed trivial 1:1 rows
   (Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch). Kept only non-trivial
   differences: AskUserQuestion->ask, Agent->task, Skill->skill, EnterPlanMode/ExitPlanMode.

2. **Created `.opencode/skills/opencode_planmode_prereqs.md`** — shared plan-mode guidance
   analogous to Codex's `codex_interactive_prereqs.md`. Covers plan mode handling,
   checkpoints, and abort handling.

### Part B: Command Files (17 total)

Created `.opencode/commands/` with 17 command files:

**Simple template (9 skills)** — no task-workflow:
- aitask-changelog, aitask-create, aitask-explain, aitask-refresh-code-models,
  aitask-reviewguide-classify, aitask-reviewguide-import, aitask-reviewguide-merge,
  aitask-stats, aitask-web-merge

**Extended template (8 skills)** — include planmode prereqs:
- aitask-pick, aitask-pickrem, aitask-pickweb, aitask-explore, aitask-fold,
  aitask-pr-import, aitask-review, aitask-wrap

Commands use `@` includes to inline tool mapping and source skill content.

### Part C: Skill Wrapper Enhancements

Updated 8 complex skill wrappers in `.opencode/skills/` to reference
`opencode_planmode_prereqs.md` BEFORE the "Source of Truth" section (so prerequisites
are read before the Claude skill is loaded).

### Skipped (non-invocable)

No commands created for: aitask-create2, ait-git, task-workflow, user-file-select.

## Verification

- [x] 17 command files in `.opencode/commands/`
- [x] No commands for non-invocable skills
- [x] 8 extended commands include planmode prereqs
- [x] 8 skill wrappers reference planmode prereqs
- [x] Tool mapping has no trivial 1:1 rows

## Follow-up Tasks

1. **t324**: Update release packaging pipeline (`.github/workflows/release.yml`, `install.sh`,
   `aitask_setup.sh`) to package/install `.opencode/commands/` and `opencode_planmode_prereqs.md`
2. **t325**: Add Codex CLI and Gemini CLI command wrappers

## Final Implementation Notes

- **Actual work done:** Created 17 OpenCode command wrappers, planmode prereqs file,
  cleaned up tool mapping, enhanced 8 skill wrappers with prereqs references
- **Deviations from plan:** Prereqs section was initially placed after "Source of Truth"
  in skill wrappers; moved to before "Source of Truth" during review for logical ordering
- **Key decisions:** Shared files kept in `.opencode/skills/` (no new `.opencode/shared/`
  directory) to reuse existing install pipeline. Single tool mapping file serves both
  commands (via `@` include) and skills (via read reference).
