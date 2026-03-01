---
Task: t260_4_create_pr_review_skill.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_1_*.md through t260_7_*.md
Archived Sibling Plans: aiplans/archived/p260/p260_1_*.md through p260_3_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Create /aitask-pr-review Skill (t260_4)

## Overview

Create a new Claude Code skill that reads intermediate PR data from `aitask_pr_import.sh`, analyzes the PR with AI assistance, and creates a structured aitask + implementation plan. Follows the `aitask-explore` skill pattern.

## Steps

### 1. Create skill directory and file

Create `.claude/skills/aitask-pr-review/SKILL.md`

### 2. Write YAML header

```yaml
---
name: aitask-pr-review
description: Create an aitask from a pull request by analyzing PR data and generating a structured task with implementation plan.
user-invocable: true
---
```

### 3. Write Step 0a: Profile Selection

Identical to aitask-explore Step 0a:
- Run `./aiscripts/aitask_scan_profiles.sh`
- Parse output, handle NO_PROFILES / single / multiple
- Load selected profile YAML file

### 4. Write Step 0c: Sync with Remote

`./aiscripts/aitask_pick_own.sh --sync` — non-blocking

### 5. Write Step 1: PR Selection

AskUserQuestion with options:
- "Enter PR number" → ask for number, run `./aiscripts/aitask_pr_import.sh --batch --pr <num> --data-only`
- "Browse open PRs" → run `./aiscripts/aitask_pr_import.sh --batch --list`, present results, run `--data-only` for selected PR
- "Use existing PR data" → glob `.aitask-pr-data/*.md`, present via AskUserQuestion

Read the intermediate data file.

### 6. Write Step 2: PR Analysis

Present structured summary:
- PR metadata (title, author, state, branches, diff stats, URL)
- Description excerpt
- Changed files list

AI analysis covering:
- Purpose/intent behind the PR
- Proposed solution approach evaluation
- Quality assessment (code quality, tests, edge cases)
- Concerns and potential issues
- Alignment with codebase conventions

### 7. Write Step 3: Interactive Q&A Loop

Same pattern as explore Step 2:
- AskUserQuestion: "Continue analyzing" / "Create task from this PR" / "Abort"
- If continuing: allow user to ask questions, explore codebase for comparison
- If abort: end without creating task

### 8. Write Step 4: Related Task Discovery

Same as explore Step 2b:
- `./aiscripts/aitask_ls.sh -v --status all --all-levels 99`
- Filter to Ready/Editing, no children
- Present related tasks for folding

### 9. Write Step 5: Task Creation

Create task with all PR metadata:
```bash
./aiscripts/aitask_create.sh --batch --commit \
    --name "<title>" --desc-file - \
    --priority "<p>" --effort "<e>" --type "<type>" \
    --labels "<labels>" \
    --pull-request "<url>" \
    --contributor "<username>" \
    --contributor-email "<email>"
```

Task description includes: PR context, AI analysis, recommended approach, files to modify, testing requirements.

### 10. Write Step 6: Decision Point

Default to "Save for later" (first option) — PR-originated tasks typically need more review.
Profile check for `explore_auto_continue`.

### 11. Write Step 7: Hand-off

Set context variables and hand off to `task-workflow/SKILL.md` Step 3.

### 12. Register skill

Add to `.claude/settings.local.json` if needed for skill discovery.

## Key Design Decisions

- Default action is "Save for later" (not continue to implementation) — different from explore
- AI analysis focuses on evaluating the PR approach and suggesting improvements, not just summarizing
- The skill does NOT modify the PR or interact with the platform — it only reads data
- Task description should capture enough context that a fresh session can implement without needing the intermediate data file

## Verification

1. End-to-end test with a real PR
2. Test "Use existing PR data" path
3. Test abort flow — no task created
4. Test folding related tasks
5. Test profile-based auto-continue

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_4`
