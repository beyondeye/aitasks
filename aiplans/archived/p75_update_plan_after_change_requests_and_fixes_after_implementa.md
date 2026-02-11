---
Task: t75_update_plan_after_change_requests_and_fixes_after_implementa.md
Branch: main (no separate branch)
Base branch: main
---

# Plan: Add Plan Update Step After User Review (t75)

## Context

The aitask-pick skill currently has a gap: when a user reviews implementation (Step 7) and requests changes ("Need more changes"), those changes get implemented and the loop returns to Step 7. However, the plan file in `aiplans/` is never updated to reflect these post-review changes. The task asks that the plan serve as a **log of what was actually implemented**, including user-requested changes and fixes made after the initial implementation.

Currently Step 6 says "Update the external plan file as you progress" but there's no instruction to update it after the Step 7 review loop. The plan file should capture the complete story: original plan + deviations during implementation + changes requested by user after review.

## Approach

Add plan-update logic **within the existing Step 7 flow** rather than creating a whole new numbered step:

### Changes to SKILL.md

**File:** `.claude/skills/aitask-pick/SKILL.md`

1. **Modify the "Need more changes" branch in Step 7**: After making requested changes, before returning to Step 7 loop, log the change request and what was done in the plan file.

2. **Modify the "If Commit changes" branch in Step 7**: Before committing, add a plan consolidation sub-step that reviews the plan against actual changes and adds a final summary section.

### Plan file format additions

```markdown
## Post-Review Changes

### Change Request 1 (YYYY-MM-DD HH:MM)
- **Requested by user:** <description>
- **Changes made:** <description>
- **Files affected:** <list>

## Final Implementation Notes
- <notes about what was actually implemented vs original plan>
```

## Verification

1. Read the modified SKILL.md and verify new instructions are in the right position
2. Walk through Step 7 flow to confirm plan update happens at right moments

## Final Implementation Notes
- Implementation matched the plan exactly — no deviations
- Two edits made to `.claude/skills/aitask-pick/SKILL.md` Step 7:
  1. "Commit changes" branch: Added plan consolidation sub-step (read plan, review diff, add "Final Implementation Notes" section)
  2. "Need more changes" branch: Added plan update logging (append "Post-Review Changes" section with numbered change request entries)
- No post-review changes were requested; implementation was approved on first review
