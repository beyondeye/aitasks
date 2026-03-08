---
priority: high
effort: medium
depends: [t131_1]
issue_type: feature
status: Implementing
labels: [geminicli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-07 23:21
updated_at: 2026-03-08 08:12
---

Create 17 command wrappers in `.gemini/commands/aitask-*.md` for all user-invocable skills.

## Context

Gemini CLI supports custom commands in `.gemini/commands/`. Command wrappers provide an alternative invocation path alongside skills. Each command file uses `@` syntax to include referenced files inline. This follows the same dual pattern used for OpenCode (`.opencode/commands/`).

Depends on t131_1 (skill wrappers) since commands reference the tool mapping and planmode prereqs files created there.

## Key Files to Create

All files are NEW in `.gemini/commands/`:
- `aitask-changelog.md`, `aitask-create.md`, `aitask-explain.md`, `aitask-explore.md`
- `aitask-fold.md`, `aitask-pick.md`, `aitask-pickrem.md`, `aitask-pickweb.md`
- `aitask-pr-import.md`, `aitask-refresh-code-models.md`, `aitask-review.md`
- `aitask-reviewguide-classify.md`, `aitask-reviewguide-import.md`, `aitask-reviewguide-merge.md`
- `aitask-stats.md`, `aitask-web-merge.md`, `aitask-wrap.md`

## Reference Files for Patterns

- `.opencode/commands/aitask-pick.md` — Pattern for command wrappers (use `@` file inclusion)
- `.opencode/commands/aitask-stats.md` — Simpler command without arguments

## Implementation Plan

For each of the 17 skills, create a command file following this template:
```markdown
---
description: <description from Claude Code skill>
---

@.gemini/skills/geminicli_tool_mapping.md

@.gemini/skills/geminicli_planmode_prereqs.md

Execute the following Claude Code skill workflow. <context about arguments if applicable>

Arguments: $ARGUMENTS

@.claude/skills/aitask-<name>/SKILL.md
```

Get the `description` for each command from the corresponding `.claude/skills/aitask-<name>/SKILL.md` frontmatter. Add context about arguments where applicable (e.g., "If a task number is provided, use it for direct selection" for aitask-pick).

## Verification Steps

```bash
# Count command files (expect 17)
ls .gemini/commands/aitask-*.md | wc -l

# Verify each references the correct Claude Code skill
for f in .gemini/commands/aitask-*.md; do
  name=$(basename "$f" .md)
  grep -l ".claude/skills/$name/SKILL.md" "$f" || echo "MISSING: $name"
done

# Verify @-includes for tool mapping
grep -l "geminicli_tool_mapping.md" .gemini/commands/aitask-*.md | wc -l
```
