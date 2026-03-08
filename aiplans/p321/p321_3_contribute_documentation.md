---
Task: t321_3_contribute_documentation.md
Parent Task: aitasks/t321_removeautoupdatefromdocsorimplement.md
Sibling Tasks: aitasks/t321/t321_1_*.md, aitasks/t321/t321_2_*.md, aitasks/t321/t321_4_*.md, aitasks/t321/t321_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t321_3 — Documentation

## Overview

Create website documentation for `/aitask-contribute` skill, a new workflow page for open-source contributions, update overview.md, and link from README.md.

## Steps

### 1. Create skill documentation page — DONE

Created `website/content/docs/skills/aitask-contribute.md` (weight: 23) following `aitask-pr-import.md` format. Covers overview, usage, 7-step workflow, and key capabilities (two modes, areas, AI analysis, grouping, attribution).

### 2. Update overview.md — DONE

Updated line 49 to: "modify them for your needs and contribute back with ease your enhancements to the project with the included AI-based /aitask-contribute skill" with relref link.

### 3. Create workflow page — DONE

Created `website/content/docs/workflows/contribute-and-manage.md` (weight: 36). Covers three complementary features: Issue to Task, PR to Task, and Contribute Without Forking. Includes end-to-end lifecycle diagram, contributor attribution flow, and comparison table.

### 4. Update README.md — DONE

Updated line 65 with matching wording and link to the new workflow page.

## Key Files

- **Created:** `website/content/docs/skills/aitask-contribute.md`
- **Created:** `website/content/docs/workflows/contribute-and-manage.md`
- **Modified:** `website/content/docs/overview.md` (line 49)
- **Modified:** `README.md` (line 65)

## Verification

- `cd website && hugo build --gc --minify` — PASSED (no errors, 102 pages)

## Final Implementation Notes
- **Actual work done:** Created skill doc, workflow page (covering all 3 contribution paths with lifecycle diagram and comparison table), updated overview.md and README.md. Scope expanded beyond original plan to include workflow page and README update.
- **Deviations from plan:** Original plan only had 2 steps (skill doc + overview.md). User requested adding: workflow page for "Contribute and Manage Contributions" covering issue-to-task, PR-to-task, and contribute-without-forking; and README.md update with link to the workflow.
- **Issues encountered:** None. Hugo build passed on first try.
- **Key decisions:** Weight 23 for skill doc (after pr-import at 22), weight 36 for workflow page (after pr-workflow at 35). Workflow page structured around three complementary features with an end-to-end lifecycle diagram.
- **Notes for sibling tasks:** The aitask-contribute skill and script were developed with the aitasks GitHub repo in mind. A follow-up task should verify multi-platform support (GitLab, Bitbucket) for the underlying `aitask_contribute.sh` script, since the documentation now implies general platform support. The `gh` CLI dependency in the skill's prerequisites check is GitHub-specific.

## Step 9 Reference
Post-implementation: archive task via task-workflow Step 9.
