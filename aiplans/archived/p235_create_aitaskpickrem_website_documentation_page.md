---
Task: t235_create_aitaskpickrem_website_documentation_page.md
Branch: (current branch, remote mode)
---

# Plan: Create aitask-pickrem Website Documentation Page (t235)

## Context

The website documentation at `website/content/docs/skills/` has pages for most skills but is missing `aitask-pickrem`. The task description says to follow the pattern of existing skill pages like `aitask-pick/_index.md` and reference the shared Build Verification subpage.

## Approach

Create a single-page documentation file `website/content/docs/skills/aitask-pickrem.md` (not a directory with `_index.md`, since there are no subpages — Build Verification is already a shared subpage under `aitask-pick/`). Also update the skills index page to include the new skill.

## Steps

1. **Create** `website/content/docs/skills/aitask-pickrem.md`
   - Front matter: title `/aitask-pickrem`, weight 11 (right after aitask-pick at 10)
   - Structure following the aitask-pick page pattern:
     - Overview paragraph explaining what it is and key difference from aitask-pick
     - Usage section with code block
     - Project root note
     - Workflow Overview (10 numbered steps matching SKILL.md Steps 0-10)
     - Key Capabilities (bulleted list)
     - Execution Profiles section with explanation + comparison vs aitask-pick profiles
     - Extended Profile Schema table (remote-specific fields)
     - Build Verification link to `../aitask-pick/build-verification/`
   - Reference file: `.claude/skills/aitask-pickrem/SKILL.md` for content accuracy

2. **Modify** `website/content/docs/skills/_index.md`
   - Add `/aitask-pickrem` row to the Skill Overview table, after `/aitask-pick`

## Verification

- Run Hugo build to verify no errors
- Check the generated HTML exists at the expected path

## Post-Review Changes

### Change Request 1 (2026-02-24 21:30)
- **Requested by user:** Clarify that plan approval is still interactive; remove Claude Code Web references (use aitask-pickweb instead); add reference to aitask-pickweb
- **Changes made:** Updated intro paragraph, comparison table, workflow step 8, and profiles section to mention plan approval is interactive. Replaced Claude Web references with generic "non-interactive environments" and added a note directing users to /aitask-pickweb for Claude Web.
- **Files affected:** `website/content/docs/skills/aitask-pickrem.md`

## Final Implementation Notes
- **Actual work done:** Created `website/content/docs/skills/aitask-pickrem.md` with full documentation following the aitask-pick page pattern. Added row to skills index. Applied user feedback to clarify plan approval interactivity and remove Claude Web references.
- **Deviations from plan:** Added a "Key Differences from /aitask-pick" comparison table (not originally planned but improves clarity). Dropped the "Key Capabilities" bulleted list section — the workflow overview and comparison table already cover the key points without redundancy.
- **Issues encountered:** None
- **Key decisions:** Used single-page format (not directory with _index.md) since aitask-pickrem has no subpages. Referenced aitask-pick's Build Verification subpage via relative link.

## Post-Implementation

- Step 9: Archive task and plan files
