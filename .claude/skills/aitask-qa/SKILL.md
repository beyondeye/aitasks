---
name: aitask-qa
description: Run QA analysis on any task — analyze changes, discover test gaps, run tests, and create follow-up test tasks
user-invocable: true
---

## Workflow

### Step 0 (pre-parse): Extract `--profile` argument

If the skill arguments contain `--profile <name>`:
- Extract the `<name>` value (the word following `--profile`)
- Store it as `profile_override`
- Remove `--profile <name>` from the argument string before passing to Step 1
- If `--profile` appears but no name follows, warn: "Missing profile name after --profile" and set `profile_override` to null

If no `--profile` in arguments, set `profile_override` to null.

### Step 0a: Select Execution Profile

Execute the **Execution Profile Selection Procedure** (see `.claude/skills/task-workflow/execution-profile-selection.md`) with:
- `skill_name`: `"qa"`
- `profile_override`: the value parsed from `--profile` argument (or null)

Store the selected profile as `active_profile`. Initialize `feedback_collected` to `false`.

### Step 1: Task Selection

Accept optional task ID argument: `/aitask-qa 42` or `/aitask-qa 16_2`

> **Full procedure:** Read `task-selection.md` for the complete Step 1 details including direct selection (1a), interactive selection (1b), and task context determination.

Store: `task_file`, `task_id`, `is_child`, `parent_id`, `is_archived`.

### Step 1c: Select QA Tier

**Profile check:** If `qa_tier` is set in the active profile, use it directly.
Display: "Profile '<name>': qa_tier=<value>"

Otherwise, use `AskUserQuestion`:
- Question: "Select QA analysis depth:"
- Header: "QA Tier"
- Options:
  - "Quick" (description: "Run existing tests + lint only. No analysis or plan generation.")
  - "Standard" (description: "Full analysis: change detection, test discovery, gap analysis, test plan")
  - "Exhaustive" (description: "Full analysis + edge cases + verification gate + regression hints")

**Set the `tier` context variable** based on the selection:
- Quick → `tier = q`
- Standard → `tier = s`
- Exhaustive → `tier = e`

This variable controls which steps and sub-steps execute. Each step and sub-step in the procedure files is annotated with a **`[Tier: ...]`** tag specifying which tier values activate it. The rules:
- `[Tier: q, s, e]` — runs for all tiers
- `[Tier: s, e]` — runs for Standard and Exhaustive only (skip when `tier = q`)
- `[Tier: e]` — runs for Exhaustive only (skip when `tier = q` or `tier = s`)

### Step 2: Change Analysis `[Tier: s, e]`

**Skip this step when `tier = q`.** Proceed to Step 4.

> **Full procedure:** Read `change-analysis.md` for the complete Step 2 details including context gathering (2a), commit detection (2b), and change categorization (2c).

### Step 3: Test Discovery `[Tier: s, e]`

**Skip this step when `tier = q`.** Proceed to Step 4.

> **Full procedure:** Read `test-discovery.md` for the complete Step 3 details including test scanning (3a), source-to-test mapping (3b), and gap identification (3c).

### Step 4: Test Execution `[Tier: q, s, e]`

> **Full procedure:** Read `test-execution.md` for the complete Step 4 details. Sub-steps are tier-annotated: 4a-4c `[Tier: q, s, e]`, 4d Health Score `[Tier: s, e]`, 4e Verification Gate `[Tier: e]`.

### Step 5: Test Plan Proposal `[Tier: s, e]`

**Skip this step when `tier = q`.** Proceed to Step 7.

> **Full procedure:** Read `test-plan-proposal.md` for the complete Step 5 details. Sub-steps are tier-annotated: 5a core proposals `[Tier: s, e]`, regression hints `[Tier: s, e]` (bug tasks only), edge case brainstorming `[Tier: e]`, 5b action `[Tier: s, e]`.

- If "Skip" → proceed to Step 7
- If "Export test plan only" → write plan, proceed to Step 7
- If "Implement tests now" → implement, commit, proceed to Step 7
- If "Create follow-up test task" → proceed to Step 6

### Step 6: Follow-up Task Creation

> **Full procedure:** Read `follow-up-task-creation.md` for the complete Step 6 details.

Proceed to Step 7.

### Step 7: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/satisfaction-feedback.md`) with `skill_name: "qa"`.

---

## Procedures

The following procedures are in individual files — read on demand when referenced:

- **Task Selection Procedure** (`task-selection.md`) — Interactive and direct task selection with confirmation
- **Change Analysis Procedure** (`change-analysis.md`) — Gather context, detect commits, categorize changes
- **Test Discovery Procedure** (`test-discovery.md`) — Scan for existing tests, map to source, identify gaps
- **Test Execution Procedure** (`test-execution.md`) — Run tests, present results, health score, verification gate
- **Test Plan Proposal Procedure** (`test-plan-proposal.md`) — Generate test ideas, regression hints, determine action
- **Follow-up Task Creation Procedure** (`follow-up-task-creation.md`) — Create sibling or standalone test task
- **Satisfaction Feedback Procedure** (`.claude/skills/task-workflow/satisfaction-feedback.md`) — Collect user feedback
- **Execution Profile Selection** (`.claude/skills/task-workflow/execution-profile-selection.md`) — Profile scan and selection

## Notes

- This skill works with both active and archived tasks
- For archived tasks, plan files in `aiplans/archived/` contain the richest implementation context
- The commit detection pattern `(t<N>)` uses parentheses as delimiters to avoid partial matches
- Profile keys: `qa_mode`, `qa_run_tests`, `qa_tier` control automation level and analysis depth
- When no commits are found, the skill falls back to plan-file analysis
- This skill does NOT modify task status or claim ownership — it is read-only analysis
- The skill replaces the tightly-coupled test-followup-task procedure (formerly Step 8b in task-workflow, now deprecated)
