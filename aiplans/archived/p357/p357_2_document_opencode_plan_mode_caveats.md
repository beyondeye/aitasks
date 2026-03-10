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

## Final Implementation Notes
- **Actual work done:** Added OpenCode section to known-issues.md with two subsections (plan mode locking skip, shallow plans with workaround). Added reference link. Added OpenCode plan mode caveat to skills _index.md blockquote.
- **Deviations from plan:** Step 1a (update intro text) was skipped — the intro had already been updated by a prior change. Step 1b was enhanced with a user-requested workaround for shallow plans: prompting the agent directly to expand the plan. The shallow plans issue was corrected to be a general OpenCode limitation (not plan-mode-specific). The `relref` shortcode in skills/_index.md required an absolute path (`/docs/installation/known-issues`) instead of relative.
- **Issues encountered:** Hugo build failed with `REF_NOT_FOUND` when using `relref "installation/known-issues"` from skills/_index.md — fixed by using absolute path `/docs/installation/known-issues`.
- **Key decisions:** Placed OpenCode section after Codex CLI (alphabetical order among non-Claude agents).
- **Notes for sibling tasks:** No further siblings expected. The known-issues page now has sections for all four supported agents (Claude Code, Gemini CLI, Codex CLI, OpenCode).

## Post-Review Changes

### Change Request 1 (2026-03-10)
- **Requested by user:** The shallow implementation plans issue is not specific to OpenCode plan mode — it's a general OpenCode limitation.
- **Changes made:** Changed heading from "Plan mode produces shallow implementation plans" to "Shallow implementation plans". Updated description to clarify this is a general limitation, not plan-mode-specific.
- **Files affected:** `website/content/docs/installation/known-issues.md`

## Post-Implementation
- Step 9: Archive task, push
