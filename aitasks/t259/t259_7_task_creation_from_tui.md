---
priority: medium
effort: medium
depends: [t259_6]
issue_type: feature
status: Ready
labels: [aitask_review, ui]
created_at: 2026-02-26 18:44
updated_at: 2026-02-26 18:44
---

## Context

This task adds the ability to create aitasks directly from review findings in the reviewbrowser TUI (t259). Users can create tasks from individual findings or bulk-create from multiple findings with grouping options.

Depends on: t259_5 (TUI app shell), t259_6 (findings viewer must exist for finding selection)

## Key Files to Modify

- aiscripts/reviewbrowser/task_creator.py (new) — task creation integration

## Reference Files for Patterns

- .claude/skills/aitask-review/SKILL.md — Step 4: task creation from findings (single, grouped by guide, per finding)
- aiscripts/aitask_create.sh — invoked with --batch --commit for task creation

## Implementation Plan

### Step 1: Single finding task creation

- t key when a finding is highlighted
- Build task description from finding: file, line, guide, description, code_snippet, suggested_fix
- Map severity to priority: high -> high, medium -> medium, low -> low
- Call: aitask_create.sh --batch --commit --name "<file>_<category>_review" --priority <p> --effort low --type <issue_type from guide> --labels "review,<category>" --desc "<description>"
- Update finding's task_created field in .findings.yaml
- Show confirmation in TUI

### Step 2: Multi-finding task creation

- T key on file or directory level
- Show grouping options dialog:
  - Single task: all findings in one task
  - Group by guide: one task per review guide
  - Group by file: one task per file
- For multi-task: create parent task + children using aitask_create.sh --parent
- Update task_created fields for all included findings

### Step 3: Keybinding integration

- Register t and T bindings in main app
- Show available bindings in footer
- Disable t when no finding is highlighted
- Disable T when no file/directory is selected

### Step 4: Task creation feedback

- After creation: show task ID in TUI notification
- Findings with task_created show a tag/badge in the viewer
- Prevent duplicate task creation (warn if finding already has task_created)

## Verification Steps

- Create a task from a single finding, verify task file content
- Create grouped tasks from directory, verify parent+children structure
- Verify task_created field is updated in findings YAML
- Verify duplicate prevention works
