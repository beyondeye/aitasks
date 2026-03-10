---
Task: t357_2_document_opencode_plan_mode_caveats.md
Parent Task: aitasks/t357_planning_phase_in_codex_opencode.md
Sibling Tasks: aitasks/t357/t357_1_fix_opencode_planning_detail.md
Archived Sibling Plans: (check aiplans/archived/p357/ when starting)
Worktree: (none — working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Document OpenCode Plan Mode Caveats (Website)

## Context

After child 1 fixes the root cause in the skill files, this task adds documentation to the website about OpenCode plan mode limitations. Scope may adjust based on child 1 results.

## Implementation Steps

### Step 1: Add OpenCode section to `website/content/docs/installation/known-issues.md`

**1a. Update intro text (line 8)**

Change:
```
This page tracks current workflow issues by code agent. At the moment, known issues are limited to Claude Code and Codex CLI.
```
To:
```
This page tracks current workflow issues by code agent.
```

**1b. Add OpenCode section** between Codex CLI and References sections:

```markdown
## OpenCode

#### Plan mode may skip task locking

When OpenCode runs in plan mode, interactive skills (`aitask-pick`, `aitask-explore`, `aitask-review`, `aitask-fold`) may skip the task locking step because plan mode restricts the agent to read-only tools.

**Recommendation:** Use OpenCode in regular mode (not plan mode) for interactive skills that acquire task locks. These skills have their own internal planning phases.

#### Plan mode produces shallow implementation plans

OpenCode's plan mode may produce high-level overviews instead of detailed step-by-step implementation plans during the task-workflow planning phase. The `opencode_planmode_prereqs.md` file contains explicit instructions to mitigate this, but results may vary by model.
```

**1c. Add reference link** in References section:

```markdown
- OpenCode plan mode prereqs: [`.opencode/skills/opencode_planmode_prereqs.md`](https://github.com/beyondeye/aitasks/blob/main/.opencode/skills/opencode_planmode_prereqs.md)
```

### Step 2: Add locking caveat to skills documentation page on website

Find the skills documentation page on the website and add a note about OpenCode plan mode caveat for task locking. (Exact page TBD — explore `website/content/docs/` for the skills page when starting this task.)

### Step 3: Commit

```
documentation: Add OpenCode plan mode caveats to website (t357_2)
```

## Key Files
- `website/content/docs/installation/known-issues.md`
- Skills documentation page on website (TBD)

## Verification
- Build website: `cd website && hugo build --gc --minify`
- Verify known-issues page renders correctly

## Post-Implementation
- Step 9: Archive task, push
