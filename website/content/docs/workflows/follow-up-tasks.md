---
title: "Follow-Up Tasks and Task Discovery"
linkTitle: "Follow-Up Tasks"
weight: 60
description: "Creating follow-up tasks, querying existing tasks, and updating them with new findings — all during implementation"
---

While working on a task via [`/aitask-pick`](../../skills/aitask-pick/), Claude Code has full context about the current implementation: the codebase, the task definition, the plan, and all changes made so far. This makes it an ideal moment to create follow-up tasks, but also to **discover and update existing tasks** — far more effective than doing either separately.

## During Implementation

When you notice something that needs a follow-up task while Claude is working, simply ask:

- "Create a follow-up task for refactoring the auth middleware"
- "Add a task to fix the edge case I noticed in the validation logic"
- "Create a task for adding tests to the module we just modified"

Claude invokes [`/aitask-create`](../../skills/aitask-create/) with the current session context already loaded. The resulting task definition automatically includes specific file paths, line numbers, code patterns, and references to the current implementation — details that would be tedious to re-explain in a standalone task creation session.

## After Implementation (During Review)

During the review step of `/aitask-pick`, you may realize additional work is needed that falls outside the current task's scope. Before committing or after selecting "Need more changes", ask Claude to create follow-up tasks. The full implementation context — including the diff and plan file — is still available, so the generated task definitions are detailed and accurate.

## Querying Existing Tasks

Instead of always creating new tasks, you can ask Claude whether a relevant task already exists. This is especially useful when you notice an issue or opportunity during implementation but aren't sure if it's already tracked.

Ask naturally:

- "Are there any existing tasks about improving the search performance?"
- "Check if we already have a task for fixing the date parsing edge case"
- "Do any pending tasks cover accessibility in the settings page?"

Claude reads the task files in `aitasks/`, compares descriptions, labels, and scope against your question, and reports back with one of three outcomes:

1. **An existing task already covers it** — Claude tells you which task addresses the issue and shows a summary. No action needed, no duplicate created.
2. **An existing task partially covers it** — Claude identifies the related task and offers to update its description to incorporate the new finding (see [Updating Existing Tasks](#updating-existing-tasks) below).
3. **No matching task exists** — Claude suggests creating a new follow-up task, pre-filled with the context from the current session.

This works because Claude already has the full codebase and implementation context loaded. It can make meaningful comparisons between what you've discovered and what's already defined in the task backlog.

## Updating Existing Tasks

When Claude finds a task that partially matches your concern, it can update the task description to incorporate specific details from the current session. This enriches the existing task with concrete information — file paths, line numbers, code patterns — that would otherwise be lost.

For example, while implementing a UI component you might notice that a utility function has a subtle edge case. Claude finds an existing task about hardening that utility module. Rather than creating a duplicate, Claude updates the existing task to mention the specific edge case, the affected call site, and the input that triggers it.

This keeps the backlog clean and ensures that when someone eventually picks up that task, they have actionable details from the session where the issue was first observed.

## Example: Discovering Related Tasks During Implementation

You're working on task t195 — adding keyboard navigation to the code browser. While testing, you notice that long files cause noticeable rendering lag when scrolling.

**You ask:** "Are there any tasks about performance in the code browser?"

**Claude searches** the pending tasks and finds t210 — "Optimize code browser rendering for large files." It shows you the task summary: the task mentions virtual scrolling and reducing DOM nodes, but doesn't mention the specific scroll-triggered re-render you observed.

**You ask:** "Update that task to mention the scroll lag I just found — it seems to re-render visible lines on every scroll event instead of debouncing."

**Claude updates** t210's description, adding a section with the specific observation: the scroll handler triggers a full re-render of visible lines, the lag appears with files over 500 lines, and the affected code path is in `codebrowser.py` around the scroll event handler. The update also references t195 as the session where this was discovered.

**Result:** No duplicate task, the existing task is enriched with specific diagnostic information, and the link between the two tasks creates a paper trail.

## Advantages Over Standalone Task Creation

- **No context re-entry** — Claude already knows the codebase state, what was changed, and why
- **Richer task definitions** — Includes specific file paths, function names, line numbers, and code patterns from the current session
- **Obvious dependencies** — Claude can auto-set `depends: [t108]` because it knows which task was just implemented
- **Batch creation** — Multiple related follow-up tasks can be created in one conversation, with cross-references between them
- **No duplicates** — Querying existing tasks before creating new ones keeps the backlog clean
- **Enriched existing tasks** — Partial matches get updated with concrete details from the current session, making them more actionable when someone picks them up later
