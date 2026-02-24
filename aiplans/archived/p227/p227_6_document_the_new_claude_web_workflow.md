---
Task: t227_6_document_the_new_claude_web_workflow.md
Parent Task: aitasks/t227_aitask_own_failure_in_cluade_web.md
Sibling Tasks: aitasks/t227/t227_1_*.md, aitasks/t227/t227_2_*.md, aitasks/t227/t227_3_*.md, aitasks/t227/t227_4_*.md, aitasks/t227/t227_5_*.md
Archived Sibling Plans: aiplans/archived/p227/p227_*_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: t227_6 — Document the new Claude Web workflow

## Context

All five sibling tasks (t227_1 through t227_5) are completed. The Claude Web workflow is fully implemented across two skills (`aitask-pickweb`, `aitask-web-merge`), a helper script, board lock/unlock controls, lock-aware pick, and per-user config. Website docs already exist for individual skills (`aitask-pickweb.md`, `aitask-pickrem.md`). What's missing is:
- A consolidated end-to-end workflow guide in the website documentation
- A website skill reference page for `/aitask-web-merge`
- Parent task t227 summary of outcomes

## Implementation Steps

### Step 1: Create `website/content/docs/workflows/claude-web.md`

Website workflow page with Hugo frontmatter. Content: overview of Claude Web limitations, standard vs Claude Web workflow comparison, 3-step guide (lock → pickweb → web-merge), `.aitask-data-updated/` directory explanation, execution profile notes, troubleshooting, and cross-links.

### Step 2: Create `website/content/docs/skills/aitask-web-merge.md`

Website skill reference page for `/aitask-web-merge` (missing — pickweb page links to it). Content: overview, usage, workflow steps, merge details, cross-links.

### Step 3: Update t227 parent task description

Add summary section to parent task documenting child task outcomes, t220 verification findings, and key decisions.

## Key Files
- **Create:** `website/content/docs/workflows/claude-web.md`, `website/content/docs/skills/aitask-web-merge.md`
- **Modify:** `aitasks/t227_aitask_own_failure_in_cluade_web.md`

## Verification
- Review workflow page for accuracy against SKILL.md files
- Verify web-merge skill page matches the actual skill definition
- Check Hugo frontmatter follows existing page patterns
- Verify all cross-links between pages are correct

## Final Implementation Notes
- **Actual work done:** Created 2 website documentation pages and updated the parent task description. All 3 planned steps implemented as designed.
- **Deviations from original task:** The original task called for `aidocs/claude_web_workflow.md` (internal docs) and `aitasks/metadata/profiles/claude-web.yaml`. Per user feedback: documentation moved to `website/content/docs/workflows/` (end-user docs), and the claude-web.yaml profile was dropped since `remote.yaml` already serves pickweb.
- **Issues encountered:** None.
- **Key decisions:** Added `website/content/docs/skills/aitask-web-merge.md` (not in original task) because the pickweb page links to it but it didn't exist. CLAUDE.md update was dropped per user request.
- **Notes for sibling tasks:** This is the last child task — no remaining siblings.

## Post-Implementation (Step 9)
Archive child task t227_6. Since this is the last child, parent t227 will auto-archive.
