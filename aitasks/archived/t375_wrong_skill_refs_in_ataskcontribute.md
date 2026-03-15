---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
issue: https://github.com/beyondeye/aitasks/issues/6
contributor: beyondeye
contributor_email: 5619462+beyondeye@users.noreply.github.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-12 11:13
updated_at: 2026-03-15 15:23
completed_at: 2026-03-15 15:23
boardcol: in_the_works
boardidx: 30
---

when running the aitask-contribute skill at the end of the skill workflow when everything is done, the following message is shown:

When this issue is imported via /aitask-pr-import or /aitask-contribution-review, your

why the aitask-pr-import skill is referenced? this does not seem correct to me

## Contribution from beyondeye (Issue #6)

**Areas:** claude-skills
**Files:** .claude/skills/aitask-contribute/SKILL.md
**Change type:** bug_fix

The summary message after contribution references /aitask-pr-import and /aitask-issue-import which don't exist for this purpose — the correct skill is /aitask-contribution-review. Users following the suggested skill names would get errors or confusion.

### Proposed fix

```diff
--- c/.claude/skills/aitask-contribute/SKILL.md
+++ w/.claude/skills/aitask-contribute/SKILL.md
@@ -281,7 +281,7 @@ Present the issue body preview to the user.
 - Issue #X: <title> — <url>
 - Issue #Y: <title> — <url>

-When these issues are imported via /aitask-pr-import or /aitask-issue-import,
+When these issues are imported via /aitask-contribution-review,
 your Co-authored-by attribution will be preserved in implementation commits.
 ```
