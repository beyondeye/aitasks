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

## Step 9 Reference

Post-implementation: archive child task via `./aiscripts/aitask_archive.sh 260_7`
