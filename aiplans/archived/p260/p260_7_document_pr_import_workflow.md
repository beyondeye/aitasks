---
Task: t260_7_document_pr_import_workflow.md
Parent Task: aitasks/t260_taskfrompullrequest.md
Sibling Tasks: aitasks/t260/t260_1_*.md through t260_6_*.md
Archived Sibling Plans: aiplans/archived/p260/p260_1_*.md through p260_6_*.md
Worktree: (none — current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Document PR Import Workflow (t260_7)

## Overview

Add documentation for the PR import feature: command reference page for `ait pr-import`, skill reference for `/aitask-pr-review`, workflow guide for creating tasks from PRs, and index updates. Note: `ait pr-close` is internal (automated by task-workflow during archival) and not documented as a user-facing command.

## Steps

### 1. Create `website/content/docs/commands/pr-import.md`
- [x] Single command page for `ait pr-import` only
- Follow `issue-integration.md` format
- Interactive mode (4-step fzf flow), batch mode examples, complete options table, key features, intermediate data format

### 2. Create `website/content/docs/skills/aitask-pr-review.md`
- [x] Follow `aitask-explore.md` pattern
- Use "Step-by-step" heading (not "Workflow")
- 6 steps: PR selection → analysis → Q&A → related task discovery → task creation → decision point

### 3. Create `website/content/docs/workflows/pr-workflow.md`
- [x] Motivation: why import PRs as tasks
- Two paths: fully automated (skill) vs partially automated (batch script)
- Automated lifecycle: contributor attribution + PR close via task-workflow
- End-to-end flow diagram, metadata fields, platform examples

### 4. Update `website/content/docs/commands/_index.md`
- [x] Add `ait pr-import` to Integration category

### 5. Update `website/content/docs/skills/_index.md`
- [x] Add `/aitask-pr-review` to skill table

## Verification

1. `cd website && hugo build --gc --minify` — no build errors
2. Verify sidebar navigation shows new entries
3. Compare docs against actual CLI flags

## Final Implementation Notes

- **Actual work done:** Created 3 new documentation pages (`pr-import.md`, `aitask-pr-review.md`, `pr-workflow.md`) and updated 2 index pages (`commands/_index.md`, `skills/_index.md`). All 5 steps completed as planned.
- **Deviations from plan:** Per user feedback during review: (1) `ait pr-close` was removed from documentation as it's not user-facing — it's automated internally by task-workflow during archival. The command page was renamed from `pr-integration.md` to `pr-import.md` since it only covers one command. (2) Skill page uses "Step-by-step" heading instead of "Workflow". (3) Workflow page expanded to document both interactive and batch modes of `ait pr-import`, and explains the automated lifecycle (contributor attribution + PR close) handled by task-workflow.
- **Key decisions:** PR import is documented as a single-command page rather than multi-command; the workflow page serves as the connective tissue explaining how the pieces (script, skill, task-workflow) fit together.
- **Notes for sibling tasks:** The workflow page (`pr-workflow.md`) cross-links to commands and skills using relative paths like `../../commands/pr-import/#ait-pr-import`. The t260_8 task (board integration) should update the board docs similarly. Hugo build verified at 87 pages, 658ms.

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_7`
