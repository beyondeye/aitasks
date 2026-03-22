---
Task: t428_6_multi_agent_wrappers_and_whitelisting.md
Parent Task: aitasks/t428_new_skill_aitask_qa.md
Sibling Tasks: aitasks/t428/t428_3_*.md, aitasks/t428/t428_5_*.md, aitasks/t428/t428_7_*.md
Archived Sibling Plans: aiplans/archived/p428/p428_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Multi-agent Wrappers and Whitelisting (t428_6)

## Context

The `/aitask-qa` skill (created in t428_1) currently only works in Claude Code. This task creates wrapper files for Gemini CLI, Codex CLI, and OpenCode so the skill is accessible from all supported agents.

## Steps

### 1. Create `.gemini/commands/aitask-qa.toml`

Follow pattern from `.gemini/commands/aitask-review.toml`:

```toml
description = "Run QA analysis on any task — analyze changes, discover test gaps, run tests, and create follow-up test tasks."
prompt = """

@.gemini/skills/geminicli_tool_mapping.md

@.gemini/skills/geminicli_planmode_prereqs.md

Execute the following Claude Code skill workflow.

Arguments: {{args}}

@.claude/skills/aitask-qa/SKILL.md
"""
```

### 2. Create `.agents/skills/aitask-qa/SKILL.md`

Follow pattern from `.agents/skills/aitask-review/SKILL.md` — includes frontmatter, Prerequisites, Source of Truth, and Arguments sections:

```markdown
---
name: aitask-qa
description: Run QA analysis on any task — analyze changes, discover test gaps, run tests, and create follow-up test tasks.
---

## Prerequisites

**If you are Codex CLI:** Read **`.agents/skills/codex_interactive_prereqs.md`** BEFORE proceeding.

**If you are Gemini CLI:** Read **`.agents/skills/geminicli_planmode_prereqs.md`** BEFORE proceeding.

## Source of Truth

This is a unified skill wrapper for Codex CLI and Gemini CLI. The authoritative skill definition is:

**`.claude/skills/aitask-qa/SKILL.md`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

**If you are Gemini CLI:** For tool mapping and adaptations, read **`.agents/skills/geminicli_tool_mapping.md`**.

## Arguments

Optional `--profile <name>` to override execution profile selection. Example: `/aitask-qa --profile fast`.
```

### 3. Create `.opencode/skills/aitask-qa/SKILL.md`

Follow pattern from `.opencode/skills/aitask-review/SKILL.md`:

```markdown
---
name: aitask-qa
description: Run QA analysis on any task — analyze changes, discover test gaps, run tests, and create follow-up test tasks.
---

## Plan Mode Prerequisites

**BEFORE executing the workflow**, read **`.opencode/skills/opencode_planmode_prereqs.md`**
and follow its guidance for plan mode phases.

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-qa/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
OpenCode adaptations, read **`.opencode/skills/opencode_tool_mapping.md`**.

## Arguments

Optional `--profile <name>` to override execution profile selection. Example: `/aitask-qa --profile fast`.
```

## Verification

1. Diff each new file against its aitask-review counterpart to ensure pattern consistency
2. Verify `.claude/skills/aitask-qa/SKILL.md` exists (source of truth reference)
3. No duplicate skill registration conflicts

## Final Implementation Notes

- **Actual work done:** Created all three wrapper files exactly as planned, following the aitask-review wrapper patterns.
- **Deviations from plan:** Added `## Arguments` section to Codex and OpenCode wrappers (missing from original plan but present in reference patterns).
- **Issues encountered:** None — straightforward file creation.
- **Key decisions:** Used em-dash in description to match the source skill's frontmatter exactly.
- **Notes for sibling tasks:** All wrappers reference `.claude/skills/aitask-qa/SKILL.md` as source of truth. If the source skill description changes, these wrappers should be updated to match.

## Post-Implementation

Step 9 of task-workflow for archival.
