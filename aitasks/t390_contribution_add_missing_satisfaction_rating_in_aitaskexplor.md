---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [contribution]
folded_tasks: [379]
issue: https://github.com/beyondeye/aitasks/issues/7
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
created_at: 2026-03-15 15:20
updated_at: 2026-03-15 15:21
---

Issue created: 2026-03-12 16:39:34, last updated: 2026-03-12 16:39:54

## [Contribution] Add missing satisfaction rating in aitask-explore 'Save for later' path

## Contribution: Add missing satisfaction rating in aitask-explore 'Save for later' path

### Scope
bug_fix

### Motivation
The Satisfaction Feedback Procedure only runs via task-workflow Step 9b, which is only reached when continuing to implementation. When a user selects 'Save for later' after exploration, no rating is collected, losing valuable feedback data for model selection.

### Proposed Merge Approach
Clean merge — single line addition, no conflicts expected

### Framework Version
0.10.0

### Changed Files

| File | Status |
|------|--------|
| `.claude/skills/aitask-explore/SKILL.md` | Modified |

### Code Changes

#### `.claude/skills/aitask-explore/SKILL.md`

```diff
--- c/.claude/skills/aitask-explore/SKILL.md
+++ w/.claude/skills/aitask-explore/SKILL.md
@@ -239,6 +239,7 @@ Otherwise, use `AskUserQuestion`:
 
 **If "Save for later":**
 - Inform user: "Task t\<N\>_\<name\>.md is ready. Run `/aitask-pick <N>` when you want to implement it."
+- Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/procedures.md`) with `skill_name` = `"explore"`.
 - End the workflow.
 
 **If "Continue to implementation":**
```


<!-- aitask-contribute-metadata
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
based_on_version: 0.10.0
fingerprint_version: 1
areas: claude-skills
file_paths: .claude/skills/aitask-explore/SKILL.md
file_dirs: .claude/skills/aitask-explore
change_type: bug_fix
auto_labels: area:claude-skills,scope:bug_fix
-->
## Comments

**github-actions** (2026-03-12 16:39:49)

## Contribution Overlap Analysis

| Issue | Score | Overlap | Detail |
|-------|-------|---------|--------|
| [#6](https://github.com/beyondeye/aitasks/issues/6) | 3 (low) | [Contribution] Fix incorrect skill name in contribute workflow output | areas- claude-skills (+2); change_type- bug_fix (+1) |

<!-- overlap-results top_overlaps: 6:3 overlap_check_version: 1 -->

-------

**github-actions** (2026-03-12 16:39:53)

## Contribution Overlap Analysis

| Issue | Score | Overlap | Detail |
|-------|-------|---------|--------|
| [#6](https://github.com/beyondeye/aitasks/issues/6) | 3 (low) | [Contribution] Fix incorrect skill name in contribute workflow output | areas- claude-skills (+2); change_type- bug_fix (+1) |

<!-- overlap-results top_overlaps: 6:3 overlap_check_version: 1 -->

## Merged from t379: add missing rating in explore

currently when running aitask-explore skill and not continuing to task implementation after task creation there is no question to the user to rate the perfomance of the cli/model. (after the question continue to implementaiton is answered with no). ask me questions if you need clarification

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t379** (`t379_add_missing_rating_in_explore.md`)
