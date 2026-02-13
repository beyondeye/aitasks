---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [aitasks, documentation]
created_at: 2026-02-13 02:40
updated_at: 2026-02-13 02:40
---

## Summary

Document the workflow of asking Claude Code to create follow-up tasks during or after implementing a task. This should be added to a new **Workflows** section in README.md (create the section if it doesn't exist yet).

## What to Document

### Context-Aware Follow-Up Task Creation

When working on a task via `/aitask-pick`, Claude Code already has full context about:
- The current task and its implementation details
- Issues discovered during implementation
- Related improvements or refactors identified
- Missing features noticed while coding

This makes creating follow-up tasks much easier than doing it separately with `ait create`, because Claude can auto-generate a detailed, well-structured task definition with all the relevant context already included.

### Workflow to Document

1. **During implementation** (while working on a task via `/aitask-pick`):
   - User notices something that needs a follow-up task
   - User asks Claude: "create a follow-up task for X" or "add a task to fix Y that I noticed"
   - Claude invokes `/aitask-create` skill with context already loaded
   - Claude pre-fills the task definition with implementation details, relevant file paths, and code references from the current session

2. **After implementation** (before or after archival):
   - User completes the task and during review realizes follow-up work is needed
   - User asks Claude to create follow-up tasks
   - Claude leverages the full implementation context to write detailed task descriptions

3. **Key advantages over standalone `ait create`:**
   - No need to re-explain context — Claude already knows the codebase state
   - Task definitions are richer: include specific file paths, line numbers, code patterns
   - Dependencies are obvious from context (e.g., "depends on t108 which we just implemented")
   - Related tasks can be batch-created in one conversation

### Where in README.md

Add to a **Workflows** section (create if not present). This section should collect practical usage patterns and tips. The follow-up task workflow should be one subsection, e.g.:

```markdown
## Workflows

### Creating Follow-Up Tasks During Implementation

When working on a task with `/aitask-pick`, you can ask Claude to create follow-up tasks...
```

## Reference Files

- README.md
- .claude/skills/aitask-create/SKILL.md
- .claude/skills/aitask-pick/SKILL.md
