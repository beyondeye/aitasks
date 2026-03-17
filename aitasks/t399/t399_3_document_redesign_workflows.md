---
priority: medium
effort: medium
depends: [t399_2]
issue_type: documentation
status: Ready
labels: [aitask-redesign, workflows, web_site]
created_at: 2026-03-17 18:51
updated_at: 2026-03-17 18:51
---

## Document Redesign Skill And Workflows

### Context

Once the new `/aitask-redesign` behavior is implemented, the docs must explain
how it fits with the existing task lifecycle. The public documentation should
make the distinction between `/aitask-revert` and `/aitask-redesign` obvious,
and should cover both redesign-after-revert and brainstorm-alternatives use
cases.

### Key Files To Modify

- `website/content/docs/skills/aitask-redesign.md` - skill reference page
- `website/content/docs/workflows/task-redesign.md` - workflow guide page
- `website/content/docs/skills/_index.md` - skills overview table
- `docs/README.md` - docs inventory mapping
- `website/content/docs/skills/verified-scores.md` - only if the implemented
  skill collects feedback

### Reference Files For Patterns

- `website/content/docs/skills/aitask-revert.md` - skill page structure
- `website/content/docs/skills/aitask-explore.md` - guided workflow phrasing
- `website/content/docs/workflows/revert-changes.md` - workflow-guide style
- `website/content/docs/skills/_index.md` - skills overview table format

### Implementation Plan

1. Read the final implemented workflow from child `t399_2` so the docs reflect
   actual behavior rather than the earlier draft.
2. Create `website/content/docs/skills/aitask-redesign.md` with:
   - usage examples
   - step-by-step flow
   - the two supported v1 modes
   - capability summary
   - relation to `/aitask-revert`
3. Create `website/content/docs/workflows/task-redesign.md` with two end-to-end
   walkthroughs:
   - redesign after revert or changed implementation direction
   - brainstorm alternative designs before implementation
4. Add explicit cross-links to `/aitask-revert` and explain the handoff from the
   redesign artifact to `/aitask-pick <newid>`.
5. Update `website/content/docs/skills/_index.md` so the skill appears in the
   public overview.
6. Update `docs/README.md` so the docs inventory includes the new skill page and
   workflow page.
7. If child `t399_2` adds satisfaction feedback, update
   `website/content/docs/skills/verified-scores.md` to list
   `/aitask-redesign` there as well.
8. Run `hugo build --gc --minify` inside `website/` and fix any broken links or
   frontmatter issues.

### Verification Steps

- the skill page documents both redesign and brainstorm usage
- the workflow page explains how `/aitask-redesign` complements
  `/aitask-revert`
- the docs clearly tell the user what artifacts are created and how to continue
- the website builds successfully with Hugo
