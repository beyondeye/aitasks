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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1782** id=2026-09-10T13:11:33Z.a6d0a59098e761ca0f805ec6 from=t1782 from_verified=yes at=2026-09-10T13:11:33Z base=da20ffd80bd9eba6658ed29e7ddbf2ff2146c494 base_branch=main dirty=no host=omg16
>
> | t1782 (code commit da20ffd80) rewrote docs/README.md as a section index: one row
> | per top-level docs page and section (Overview, Getting Started, Installation,
> | Concepts, TUI Applications, Workflow Guides, Code Agent Skills, Command
> | Reference, Development Guide). It no longer lists individual pages.
> | 
> | So your step 6 ("Update docs/README.md so the docs inventory includes the new
> | skill page and workflow page") and the "docs/README.md - docs inventory mapping"
> | entry in your files list no longer apply: a new page under skills/ or
> | workflows/ needs no README row.
> | 
> | The new guard, tests/test_docs_readme_links.sh, fails only when a link in that
> | file is dead, or when a new top-level page or section
> | (website/content/docs/*.md or website/content/docs/*/_index.md) is not linked.
> | Advisory; this describes the tree at da20ffd80, so re-check docs/README.md when
> | you pick this up.
