---
priority: low
effort: low
depends: [428_1]
issue_type: feature
status: Ready
labels: [testing, qa]
created_at: 2026-03-22 11:28
updated_at: 2026-03-22 11:28
---

## Context

Create wrapper skill files for Gemini CLI, Codex CLI, and OpenCode so that the new `/aitask-qa` skill is accessible from all supported code agents. Follow established wrapper patterns.

## Key Files to Create

- **`.gemini/commands/aitask-qa.toml`** — Gemini CLI command wrapper
- **`.agents/skills/aitask-qa/SKILL.md`** — Codex CLI skill wrapper
- **`.opencode/skills/aitask-qa/SKILL.md`** — OpenCode skill wrapper

## Implementation Steps

### 1. Gemini CLI: `.gemini/commands/aitask-qa.toml`

Follow the pattern from `.gemini/commands/aitask-review.toml`:

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

### 2. Codex CLI: `.agents/skills/aitask-qa/SKILL.md`

Follow the pattern from `.agents/skills/aitask-review/SKILL.md`:

```markdown
---
name: aitask-qa
description: Run QA analysis on any task: discover tests, run them, identify gaps, and create follow-up test tasks.
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
```

### 3. OpenCode: `.opencode/skills/aitask-qa/SKILL.md`

Follow the pattern from `.opencode/skills/aitask-review/SKILL.md`:

```markdown
---
name: aitask-qa
description: Run QA analysis on any task: discover tests, run them, identify gaps, and create follow-up test tasks.
---

## Plan Mode Prerequisites

**BEFORE executing the workflow**, read **`.opencode/skills/opencode_planmode_prereqs.md`**
and follow its guidance for plan mode phases.

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-qa/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
OpenCode adaptations, read **`.opencode/skills/opencode_tool_mapping.md`**.
```

## Reference Files

- `.gemini/commands/aitask-review.toml` — Gemini wrapper pattern
- `.agents/skills/aitask-review/SKILL.md` — Codex wrapper pattern
- `.opencode/skills/aitask-review/SKILL.md` — OpenCode wrapper pattern
- `.claude/skills/aitask-qa/SKILL.md` — Source of truth (created in t428_1)

## Verification Steps

1. Verify `.gemini/commands/aitask-qa.toml` matches the established TOML format
2. Verify `.agents/skills/aitask-qa/SKILL.md` has correct frontmatter and "Source of Truth" reference
3. Verify `.opencode/skills/aitask-qa/SKILL.md` follows OpenCode wrapper convention
4. Check no duplicate skill registration conflicts exist
