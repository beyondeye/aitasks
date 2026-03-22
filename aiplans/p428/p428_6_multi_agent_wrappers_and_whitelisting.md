---
Task: t428_6_multi_agent_wrappers_and_whitelisting.md
Parent Task: aitasks/t428_new_skill_aitask_qa.md
Sibling Tasks: aitasks/t428/t428_1_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Multi-agent Wrappers and Whitelisting

## Overview

Create wrapper files for Gemini CLI, Codex CLI, and OpenCode so the aitask-qa skill works across all supported agents.

## Steps

### 1. Create `.gemini/commands/aitask-qa.toml`

Follow `.gemini/commands/aitask-review.toml` pattern:
```toml
description = "Run QA analysis on any task: discover tests, run them, identify gaps, and create follow-up test tasks."
prompt = """
@.gemini/skills/geminicli_tool_mapping.md
@.gemini/skills/geminicli_planmode_prereqs.md

Execute the following Claude Code skill workflow.

Arguments: {{args}}

@.claude/skills/aitask-qa/SKILL.md
"""
```

### 2. Create `.agents/skills/aitask-qa/SKILL.md`

Follow `.agents/skills/aitask-review/SKILL.md` pattern with frontmatter + "Source of Truth" section.

### 3. Create `.opencode/skills/aitask-qa/SKILL.md`

Follow `.opencode/skills/aitask-review/SKILL.md` pattern with frontmatter + planmode prereqs + source reference.

## Verification

1. File format matches established patterns
2. References to source of truth are correct
3. No conflicts with existing wrappers

## Post-Implementation

Step 9 of task-workflow for archival.
