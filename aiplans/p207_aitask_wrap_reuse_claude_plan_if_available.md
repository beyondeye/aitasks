---
Task: t207_aitask_wrap_reuse_claude_plan_if_available.md
Branch: main (current branch)
Worktree: (none — working on current branch)
---

# Plan: Add Claude plan reuse to aitask-wrap (t207)

## Context

The `aitask-wrap` skill creates retroactive task documentation for uncommitted changes. Currently, it analyzes the diff from scratch and generates a new plan. However, if the user just executed a Claude Code plan (stored at `~/.claude/plans/`), that plan already contains detailed context about _why_ the changes were made. Reusing it would produce better task documentation and save the user from re-explaining intent.

## Changes

**File: `.claude/skills/aitask-wrap/SKILL.md`**

Add a new **Step 1b: Check for Recent Claude Plans** between Step 1 (Analyze Changes) and Step 2 (Present Analysis).

### Step 1b Logic

1. **Scan for recent plans** — list the 5 most recently modified `.md` files in `~/.claude/plans/`:
   ```bash
   ls -t ~/.claude/plans/*.md 2>/dev/null | head -5
   ```

2. **Extract preview info** for each plan:
   - Read the first ~20 lines to get the YAML frontmatter and title/heading
   - Extract the `Task:` field from frontmatter if present (shows which task it was for)
   - Extract the first `# ` heading as the plan title
   - Get the file modification time for display

3. **Filter out aitask-wrap plans** — skip plans that have `Created by: aitask-wrap` in frontmatter (these are retroactive plans created by previous wrap operations, not useful as source context)

4. **If no candidate plans found** — skip silently, proceed to Step 2

5. **If candidates found** — use `AskUserQuestion` with `multiSelect: true`:
   - Question: "Found recent Claude Code plans. Select any that are relevant to the current changes (or skip):"
   - Header: "Plans"
   - Options (up to 3 most recent candidates + 1 skip):
     - Each plan: label = plan title or first heading (truncated to fit), description = `Task: <task_field>` if present, otherwise file modification timestamp
     - "None — skip" (description: "Don't use any existing plan, analyze from scratch")

6. **If user selects one or more plans:**
   - Read the full content of each selected plan
   - Store them as `selected_plans` (list) for use in subsequent steps
   - Display: "Plans loaded: <title1>, <title2>, ..."

7. **If only "None — skip" selected (or no plans selected):** proceed normally (no plan context)

### Integrate selected plans into existing steps

**Step 1 (Analyze Changes)** — add a note: When `selected_plans` is available, use the plan content(s) to enhance the analysis. The plans likely explain the intent and approach, so use them to improve the "Probable user intent" and ensure the factual summary aligns with the plans' descriptions.

**Step 2 (Present Analysis)** — add a new field to the display:
```
**Source plans:** <plan title 1> (from ~/.claude/plans/<filename1>), <plan title 2> (from ~/.claude/plans/<filename2>), ...
```
Only shown when one or more plans were selected.

**Step 4b (Create Plan File)** — when `selected_plans` is available:
- Change the frontmatter to reference the sources:
  ```yaml
  Created by: aitask-wrap (retroactive documentation, based on Claude plan(s))
  Source plans: ~/.claude/plans/<filename1>, ~/.claude/plans/<filename2>
  ```
- Replace the generic "Probable User Intent" section with a "Plan Context" section that incorporates the original plan content(s) (condensed/reformatted as needed)
- Keep the "Final Implementation Notes" section as-is

## Verification

1. Run `/aitask-wrap` with uncommitted changes when recent plans exist in `~/.claude/plans/` — verify the plan selection prompt appears
2. Select a plan and verify it gets incorporated into the wrap analysis and final plan file
3. Select "None — skip" and verify the workflow proceeds normally (same as current behavior)
4. Run `/aitask-wrap` when `~/.claude/plans/` is empty or missing — verify no errors and workflow proceeds normally
5. Verify plans with `Created by: aitask-wrap` frontmatter are filtered out

## Final Implementation Notes

- **Actual work done:** Added Step 1b to `.claude/skills/aitask-wrap/SKILL.md` — a new section between Step 1 (Analyze Changes) and Step 2 (Present Analysis) that scans `~/.claude/plans/` for recent Claude Code plan files, filters out aitask-wrap-generated plans, and presents candidates to the user via multiSelect AskUserQuestion. Integration notes for Steps 1, 2, and 4b are included inline within Step 1b.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Integration instructions for Steps 1, 2, and 4b were consolidated into a single "Integration with other steps" subsection within Step 1b rather than duplicating content across multiple steps, keeping the skill file DRY and easier to maintain.
