---
priority: low
effort: medium
depends: [t129_4]
issue_type: documentation
status: Implementing
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-15 17:15
updated_at: 2026-02-19 23:40
---

## Context
This task adds comprehensive documentation for the `/aitask-review` skill to README.md. The skill (created in t129_4) enables Claude-driven code review using configurable review guides (from t129_3). Documentation should explain the motivation, the review guides system, workflow, and include a sample usage scenario.

## Key Files to Modify

1. **Modify** `README.md` — add aitask-review documentation

## Reference Files for Patterns

- `README.md` — existing documentation style, especially the `/aitask-pick` section and "Typical Workflows" section
- `.claude/skills/aitask-review/SKILL.md` — the actual skill implementation to document
- `aireviewguides/*.md` — review guide files to document
- `seed/reviewguides/` — seed templates to list

## Implementation Plan

### Step 1: Update Table of Contents
Add `/aitask-review` entry under "Claude Code Integration" section in the TOC, after `/aitask-explore`.

### Step 2: Update Claude Code Integration table
Add row: `| /aitask-review | AI-driven code review using configurable review guides, creates tasks from findings |`

### Step 3: Add /aitask-review section
Insert after the `/aitask-explore` section, following the existing documentation pattern:

- **Usage block**: `/aitask-review`
- **Motivation paragraph**: Explain the value of automated code review for finding conventions violations, duplication, refactoring opportunities, and security issues; turning findings into actionable tasks
- **Workflow overview**: Numbered steps
- **Review guides system**: Document the file format (YAML frontmatter with name, description, environment), the `aireviewguides/` directory, how to create custom review guides
- **Seed review guides**: Table listing all provided seed templates with names, environments, and focus areas
- **Key capabilities**: Bullet list

### Step 4: Add "Code Review Workflow" typical workflow
Add a new subsection under "Typical Workflows" with a concrete example of reviewing a module using specific review guides, selecting findings, creating tasks, and continuing to implementation. Also describe how to create a project-specific review guide.

## Verification Steps

1. Verify markdown headings are correctly nested
2. Verify TOC links match the actual heading anchors
3. Cross-reference with actual SKILL.md and review guide files
4. Verify the seed review guides table matches actual files in seed/reviewguides/
5. Check that no existing content was accidentally removed or modified
