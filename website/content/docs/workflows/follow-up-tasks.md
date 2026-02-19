---
title: "Creating Follow-Up Tasks"
linkTitle: "Follow-Up Tasks"
weight: 60
description: "Creating rich follow-up tasks during implementation with full context"
---

While working on a task via [`/aitask-pick`](../../skills/aitask-pick/), Claude Code has full context about the current implementation: the codebase, the task definition, the plan, and all changes made so far. This makes it an ideal moment to create follow-up tasks — far richer than creating them separately with [`ait create`](../../commands/task-management/#ait-create) or [`/aitask-create`](../../skills/aitask-create/).

## During Implementation

When you notice something that needs a follow-up task while Claude is working, simply ask:

- "Create a follow-up task for refactoring the auth middleware"
- "Add a task to fix the edge case I noticed in the validation logic"
- "Create a task for adding tests to the module we just modified"

Claude invokes [`/aitask-create`](../../skills/aitask-create/) with the current session context already loaded. The resulting task definition automatically includes specific file paths, line numbers, code patterns, and references to the current implementation — details that would be tedious to re-explain in a standalone task creation session.

## After Implementation (During Review)

During the review step of `/aitask-pick`, you may realize additional work is needed that falls outside the current task's scope. Before committing or after selecting "Need more changes", ask Claude to create follow-up tasks. The full implementation context — including the diff and plan file — is still available, so the generated task definitions are detailed and accurate.

## Advantages Over Standalone Task Creation

- **No context re-entry** — Claude already knows the codebase state, what was changed, and why
- **Richer task definitions** — Includes specific file paths, function names, line numbers, and code patterns from the current session
- **Obvious dependencies** — Claude can auto-set `depends: [t108]` because it knows which task was just implemented
- **Batch creation** — Multiple related follow-up tasks can be created in one conversation, with cross-references between them
