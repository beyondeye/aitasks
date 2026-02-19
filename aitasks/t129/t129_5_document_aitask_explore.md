---
priority: low
effort: medium
depends: [t129_2]
issue_type: documentation
status: Implementing
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-15 17:15
updated_at: 2026-02-19 23:02
---

## Context
This task adds comprehensive documentation for the `/aitask-explore` skill to README.md. The skill (created in t129_2) enables user-driven codebase exploration that culminates in task creation. Documentation should explain the motivation, workflow, and include a sample usage scenario.

## Key Files to Modify

1. **Modify** `README.md` — add aitask-explore documentation

## Reference Files for Patterns

- `README.md` — existing documentation style, especially the `/aitask-pick` section (lines 658-738) and "Typical Workflows" section (lines 857-996)
- `.claude/skills/aitask-explore/SKILL.md` — the actual skill implementation to document

## Implementation Plan

### Step 1: Update Table of Contents
Add `/aitask-explore` entry under "Claude Code Integration" section in the TOC, after `/aitask-pick`.

### Step 2: Update Claude Code Integration table
Add row: `| /aitask-explore | Start with codebase exploration, create a task when ready, optionally continue to implementation |`

### Step 3: Add /aitask-explore section
Insert after the `/aitask-pick` section (after the Execution Profiles subsection), following the existing documentation pattern:

- **Usage block**: `/aitask-explore`
- **Motivation paragraph**: Explain the friction of defining tasks upfront when you don't yet know what the task should be. Situations like investigating a bug, exploring unfamiliar code, or looking for improvement opportunities benefit from exploration-first workflow.
- **Workflow overview**: Numbered steps matching the skill's actual flow
- **Key capabilities**: Bullet list of features

### Step 4: Add "Exploration-Driven Development" workflow
Add a new subsection under "Typical Workflows" describing the scenario where a developer doesn't know exactly what to build. Include a concrete walkthrough example.

## Verification Steps

1. Verify markdown headings are correctly nested
2. Verify TOC links match the actual heading anchors
3. Cross-reference workflow steps with actual SKILL.md content
4. Check that no existing content was accidentally removed or modified
