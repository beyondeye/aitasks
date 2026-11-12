---
title: "Follow-Up Tasks and Task Discovery"
linkTitle: "Follow-Up Tasks"
weight: 60
description: "Creating follow-up tasks, querying existing tasks, and updating them with new findings — all during implementation"
depth: [intermediate]
---

While working on a task via [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}), your code agent session has full context about the current implementation: the codebase, the task definition, the plan, and all changes made so far. That makes it a good moment to create follow-up tasks, and also to find and update existing tasks, because none of that context has to be explained again.

## During Implementation

When you notice something that needs a follow-up task while the agent is working, ask:

- "Create a follow-up task for refactoring the auth middleware"
- "Add a task to fix the edge case I noticed in the validation logic"
- "Create a task for adding tests to the module we just modified"

The agent invokes [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) with the current session context already loaded. The resulting task definition includes specific file paths, line numbers, code patterns, and references to the current implementation, details you would otherwise have to explain again in a separate task creation session.

Because the agent knows which task it just implemented, it can also set the new task's `depends` field itself, for example `depends: [t108]`. You can ask for several related follow-up tasks in one conversation, and the agent can cross-reference them with each other.

## After Implementation (During Review)

During the review step of `/aitask-pick`, you may realize additional work is needed that falls outside the current task's scope. Before committing or after selecting "Need more changes", ask the agent to create follow-up tasks. The full implementation context, including the diff and plan file, is still available, so the generated task definitions are as detailed and accurate as ones created during implementation.

## Querying Existing Tasks

Instead of always creating new tasks, you can ask whether a relevant task already exists. This is especially useful when you notice an issue or opportunity during implementation but aren't sure if it's already tracked.

Ask naturally:

- "Are there any existing tasks about improving the search performance?"
- "Check if we already have a task for fixing the date parsing edge case"
- "Do any pending tasks cover accessibility in the settings page?"

The agent reads the task files in `aitasks/`, compares descriptions, labels, and scope against your question, and reports back with one of three outcomes:

1. An existing task already covers it. The agent tells you which task addresses the issue and shows a summary. Nothing needs to be done, and no duplicate is created.
2. An existing task partially covers it. The agent identifies the related task and offers to update its description to incorporate the new finding (see [Updating Existing Tasks](#updating-existing-tasks) below).
3. No matching task exists. The agent suggests creating a new follow-up task, pre-filled with the context from the current session.

## Updating Existing Tasks

When the agent finds a task that partially matches your concern, it can update the task description with concrete details from the current session, such as file paths, line numbers and code patterns, instead of creating a duplicate.

For example, you are working on task t195, adding keyboard navigation to the frontend's file viewer, and notice that long files lag when you scroll. You ask "Are there any tasks about performance in the file viewer?" The agent finds t210, "Optimize file viewer rendering for large files", and shows its summary: it mentions virtual scrolling and reducing DOM nodes, but not the lag you saw. You ask the agent to add the scroll lag to that task. It adds a section to t210's description: the scroll handler re-renders the visible lines on every scroll event instead of debouncing, the lag appears with files over 500 lines, and the code path is the scroll event handler in `FileViewer.tsx`. The section also names t195 as the task during which the lag was found, so whoever picks up t210 later can trace it back.

## Automatic Upstream-Defect Follow-up

In the flows above, you ask the agent to create or update a task. `/aitask-pick` also offers one on its own: after you approve "Commit changes" at the review step, when the just-committed plan file documents an *upstream defect* (a separate, pre-existing bug surfaced during diagnosis in a different script, helper, or module), the skill offers to spawn a fresh `bug` aitask for it with the diagnostic chain of reasoning pre-loaded into the body. See [Upstream Defect Follow-up]({{< relref "/docs/workflows/upstream-defect-followup" >}}) for the plan-file contract, the parsing modes, and the seeded task structure.

## Automatic Manual-Verification Follow-up

After you approve "Commit changes" at the review step, and after the upstream-defect offer, `/aitask-pick` offers to queue a standalone manual-verification task that is picked once the current task archives. It covers behavior only a human can check and automated tests cannot, such as TUI flows, live agent launches and inspecting files on disk. See [Manual Verification → Post-Implementation Follow-up]({{< relref "/docs/workflows/manual-verification#post-implementation-follow-up-step-8c" >}}) for the candidate discovery and seeded checklist.

## Automatic Risk-Mitigation Follow-up

When [risk evaluation]({{< relref "/docs/workflows/risk-evaluation" >}}) is enabled, the planning step can propose mitigation tasks for the risks it identifies. A **before** mitigation becomes a blocking dependency of the original task (implement it first, then re-pick the original); an **after** mitigation is a post-implementation follow-up that blocks nothing. Small, separable mitigations can instead be inlined as pre- or post-phases of the plan itself; then no task is created and the mitigation lands with the original work. Each is proposed and confirmed during planning. See [Risk Evaluation]({{< relref "/docs/workflows/risk-evaluation" >}}) for the two risk dimensions, the `## Risk` plan section, and the force re-verification behavior.
