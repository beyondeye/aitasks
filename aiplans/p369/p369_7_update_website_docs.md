---
Task: t369_7_update_website_docs.md
Parent Task: aitasks/t369_aitask_explain_for_aitask_pick.md
Sibling Tasks: aitasks/t369/t369_*_*.md
Archived Sibling Plans: aiplans/archived/p369/p369_*_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Update Website Documentation (t369_7)

## Overview

Document the new `gather_explain_context` profile field and the historical context gathering feature in the Hugo/Docsy website. Two pages need updating: the settings reference (profile schema table) and the aitask-pick skill page (workflow description).

**Dependency:** Requires t369_3 (profile changes) and t369_6 (settings TUI) to be completed.

## Files to Modify

| File | Change |
|------|--------|
| `website/content/docs/tuis/settings/reference.md` | Add row to Planning table |
| `website/content/docs/skills/aitask-pick/_index.md` | Add historical context mentions |

## Detailed Implementation Steps

### Step 1: Update Profile Schema in settings reference

**File:** `website/content/docs/tuis/settings/reference.md`

**Location:** The "Planning" section of the Profile Schema (around lines 95-99).

Current table:
```markdown
### Planning

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `plan_preference` | enum | `use_current`, `verify`, `create_new` | What to do when an existing plan is found |
| `plan_preference_child` | enum | `use_current`, `verify`, `create_new` | Same as above, but specifically for child tasks (takes priority) |
| `post_plan_action` | enum | `start_implementation` | What to do after plan is saved |
```

Add a new row after `post_plan_action`:
```markdown
| `gather_explain_context` | int or enum | `ask`, `0`, `1`, `2`, `3`, `5` | Number of historical plans to extract during planning. `ask` = prompt user, `0` = disabled, positive integer = max plans via greedy selection by code contribution |
```

### Step 2: Update aitask-pick skill page -- Step-by-Step section

**File:** `website/content/docs/skills/aitask-pick/_index.md`

**Location:** The numbered step-by-step list (around line 29).

Find step 7:
```markdown
7. **Planning** -- Enters the agent planning flow to explore the codebase and create an implementation plan. If a plan already exists, offers three options: use as-is, verify against current code, or create from scratch. Complex tasks can be decomposed into child subtasks during this phase
```

Update to:
```markdown
7. **Planning** -- Enters the agent planning flow to explore the codebase and create an implementation plan. Optionally gathers historical architectural context from aitask-explain data, showing why existing code was designed the way it is (controlled by `gather_explain_context` profile key). If a plan already exists, offers three options: use as-is, verify against current code, or create from scratch. Complex tasks can be decomposed into child subtasks during this phase
```

### Step 3: Update aitask-pick skill page -- Key Capabilities section

**Location:** The Key Capabilities bullet list (around lines 36-42).

Add a new bullet after the "Plan mode integration" bullet:

```markdown
- **Historical context** -- During planning, optionally extracts historical plan content from the aitask-explain data to show why existing code was designed a certain way. Controlled by the `gather_explain_context` profile key: `0` disables it, a positive integer sets the max number of plans to extract (greedy selection by git blame line count), and `ask` prompts the user. Plans are selected per-file and deduplicated across all target files
```

### Step 4: Check execution profiles sub-page

Check if `website/content/docs/skills/aitask-pick/execution-profiles/` exists and has its own profile schema listing:

```bash
ls website/content/docs/skills/aitask-pick/execution-profiles/
```

If it has a schema table, add the same row as Step 1.

### Step 5: Check settings overview page

Read `website/content/docs/tuis/settings/_index.md` to see if it lists specific profile fields. If it only gives a general overview (likely), no changes needed. If it lists specific fields, add `gather_explain_context`.

### Step 6: Build verification

```bash
cd website && hugo build --gc --minify 2>&1 | head -20
```

Verify no build errors. Hugo will catch broken links and invalid markdown.

## Verification

1. **Build test:** `cd website && hugo build --gc --minify` completes without errors
2. **Visual check:** Run `cd website && ./serve.sh` and:
   - Navigate to Settings Reference page -- verify new row in Planning table
   - Navigate to aitask-pick skill page -- verify historical context mentioned in Step 7 and Key Capabilities
3. **Link check:** Verify any internal references resolve (the `gather_explain_context` references in the pick page should match the settings reference page)

## Step 9: Post-Implementation

Follow `.claude/skills/task-workflow/SKILL.md` Step 9 for cleanup, archival, and merge.
