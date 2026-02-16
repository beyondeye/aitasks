# Typical Workflows

This section describes common usage patterns that combine the CLI tools and Claude Code skills into end-to-end development workflows.

## Table of Contents

- [Capturing Ideas Fast](#capturing-ideas-fast)
- [Complex Task Decomposition](#complex-task-decomposition)
- [GitHub Issue Development Workflow](#github-issue-development-workflow)
- [Parallel Development](#parallel-development)
- [Multi-Tab Terminal Workflow](#multi-tab-terminal-workflow)
- [Monitoring While Implementing](#monitoring-while-implementing)
- [Creating Follow-Up Tasks During Implementation](#creating-follow-up-tasks-during-implementation)

---

## Capturing Ideas Fast

The most important thing when a new task idea comes to mind is capturing it immediately, before the thought fades. The [`ait create`](commands.md#ait-create) script is designed for this: you can write a task description as a raw stream of consciousness without worrying about structure, grammar, or completeness.

**The philosophy: capture intent now, refine later.**

In interactive mode, `ait create` walks you through metadata selection (priority, effort, labels) via fast fzf menus, then lets you enter the description as consecutive text blocks. There is no need to open an external editor or craft a polished specification — Claude is perfectly capable of understanding rough, unstructured descriptions with missing details.

**Recommended setup:** Keep a terminal tab with `ait create` ready to launch at all times. When an idea strikes — even mid-implementation on another task — switch to that tab, type the idea, assign basic metadata, and get back to work. The task is saved as a local draft in `aitasks/new/` (gitignored, no network needed) and can be finalized later.

**The iterative refinement pipeline:**

1. **Capture** — Create the task with [`ait create`](commands.md#ait-create) or [`/aitask-create2`](skills.md#aitask-create2). Write whatever comes to mind, even multiple paragraphs of loosely connected ideas
2. **Organize** — Use [`ait board`](commands.md#ait-board) to visually triage: drag tasks between kanban columns, adjust priority and effort, add labels
3. **Refine** — When picked for implementation with [`/aitask-pick`](skills.md#aitask-pick-number), the planning phase explores the codebase and produces a structured implementation plan from your raw intent

This pipeline means you never need to spend time writing perfect task descriptions upfront. The framework handles progressive refinement at each stage.

---

## Complex Task Decomposition

For tasks that are too large or risky for a single implementation run, the aitasks framework supports decomposition into child subtasks. This gives you controlled, disciplined execution of complex features while maintaining full context across all subtasks.

**How it works:**

- During the planning phase of [`/aitask-pick`](skills.md#aitask-pick-number), if a task is assessed as high complexity, the skill automatically offers to break it into child subtasks
- You can also force decomposition by adding a line like "this is a complex task: please decompose in child tasks" in the task description
- Each child task is created with detailed context: key files to modify, reference patterns, step-by-step implementation instructions, and verification steps. This ensures each child can be executed independently in a fresh Claude Code context

**Context propagation between siblings:**

When implementing a child task, [`/aitask-pick`](skills.md#aitask-pick-number) automatically gathers context from previously completed siblings. The primary reference is the archived plan files in `aiplans/archived/p<parent>/`, which contain the full implementation record including a "Final Implementation Notes" section with patterns established, gotchas discovered, and shared code created. This means each successive child task benefits from the experience of earlier ones.

**Typical decomposition flow:**

1. Create a parent task describing the full feature
2. Run `/aitask-pick <parent_number>` — during planning, choose to decompose
3. Define child tasks with descriptions and dependencies
4. Implement children one at a time with `/aitask-pick <parent>_<child>` (e.g., `/aitask-pick 16_1`, `/aitask-pick 16_2`)
5. When all children are complete, the parent is automatically archived

---

## GitHub Issue Development Workflow

The framework fully supports GitHub issue-based development through the [`ait issue-import`](commands.md#ait-issue-import) and [`ait issue-update`](commands.md#ait-issue-update) commands, creating a seamless round-trip between GitHub and your local task management.

**The full cycle:**

1. **Import** — Run [`ait issue-import`](commands.md#ait-issue-import) to fetch open GitHub issues and create task files. In interactive mode, you can browse issues with fzf, preview their content, and select which ones to import. GitHub labels are mapped to aitask labels, and the issue type (bug, feature, refactor) is auto-detected from labels. A link to the original issue is stored in the task's `issue` metadata field

2. **Implement** — Pick the imported task with [`/aitask-pick`](skills.md#aitask-pick-number) and go through the normal implementation workflow (planning, coding, review)

3. **Close** — During post-implementation, the [`/aitask-pick`](skills.md#aitask-pick-number) workflow detects the linked `issue` field and offers to update the GitHub issue. Choose from: close with implementation notes, comment only, close silently, or skip. The [`ait issue-update`](commands.md#ait-issue-update) command automatically extracts implementation notes from the archived plan file and detects associated commits by searching git log for the `(t<task_id>)` pattern in commit messages

**Batch import** is also available for automation:

```bash
ait issue-import --batch --all --skip-duplicates    # Import all open issues
ait issue-import --batch --range 10-20 --parent 5   # Import as children of task 5
```

---

## Parallel Development

The aitasks framework supports multiple developers (or multiple AI agent instances) working on different tasks simultaneously.

**How concurrency is managed:**

- **Status tracking via git:** When [`/aitask-pick`](skills.md#aitask-pick-number) starts work on a task, it sets the status to "Implementing", records the developer's email in `assigned_to`, and commits + pushes the change. This makes the assignment visible to anyone who pulls the latest state
- **Atomic task locking:** The atomic lock system prevents two PCs from picking the same task simultaneously. Locks are stored on a separate `aitask-locks` git branch using compare-and-swap semantics
- **Atomic ID counter:** The atomic ID counter on the `aitask-ids` branch ensures globally unique task numbers even when multiple PCs create tasks against the same repo

**Git worktrees for isolation:**

When working on multiple tasks in parallel, use the git worktree option in [`/aitask-pick`](skills.md#aitask-pick-number). This creates an isolated working directory at `aiwork/<task_name>/` on a separate branch, so each task's changes don't interfere with each other. After implementation, the branch is merged back to main and the worktree is cleaned up.

**Best practices:**

- Run `git pull` before starting `/aitask-pick` to see the latest task status and assignments
- Use git worktrees when multiple developers work in parallel, or when running multiple Claude Code instances on tasks that touch overlapping files
- Working on the current branch (without worktrees) is safe when you are a single developer giving work to multiple Claude Code instances on tasks that don't touch the same files

**Parallel exploration:**

`/aitask-explore` is read-only — it searches and reads code but never modifies source files. This makes it safe to run in a separate terminal tab while another Claude Code instance implements a task. Use this pattern to stay productive: explore and create new tasks while waiting for builds, tests, or ongoing implementations to complete.

---

## Multi-Tab Terminal Workflow

The aitasks framework is built for terminal-centric development. Using a terminal emulator that supports multiple tabs or panes — switchable with keyboard shortcuts — makes the workflow significantly more efficient.

**Recommended terminal emulators:**

- [**Warp**](https://www.warp.dev/) — Modern terminal with built-in Claude Code integration, multi-tab support, and real-time diff viewing. Available for Linux, macOS, and Windows
- **tmux** — Terminal multiplexer with split panes and sessions. Works everywhere
- [**Ghostty**](https://ghostty.org/) — Fast GPU-accelerated terminal with tabs and splits

**Typical tab layout:**

| Tab | Purpose |
|-----|---------|
| Tab 1 | Main Claude Code session running [`/aitask-pick`](skills.md#aitask-pick-number) |
| Tab 2 | [`ait board`](commands.md#ait-board) for visual task management and triage |
| Tab 3 | [`ait create`](commands.md#ait-create) ready to launch for capturing new ideas |
| Tab 4 | Git status / diff viewer for monitoring implementation changes |

**IDE alternative:** You can also run a terminal inside your IDE (VS Code, IntelliJ, etc.) and use another pane to watch file changes in real time. However, dedicated terminal emulators with keyboard-driven tab switching tend to be faster for this workflow.

---

## Monitoring While Implementing

While [`/aitask-pick`](skills.md#aitask-pick-number) is running — especially during the exploration or implementation phases which can take several minutes — you can stay productive in other terminal tabs.

**What to do while waiting:**

- **Triage tasks** — Open [`ait board`](commands.md#ait-board) in another tab to review priorities, move tasks between kanban columns, update metadata (priority, effort, labels), and adjust dependencies
- **Capture new ideas** — As ideas come up during the implementation (which they often do while watching the agent work), quickly switch to a tab with [`ait create`](commands.md#ait-create) and write them down. The key shortcut `n` in [`ait board`](commands.md#ait-board) also launches task creation directly
- **Review progress** — Watch the current diff in another tab to understand what changes are being made. Warp's built-in diff viewer or a simple `git diff` in a separate tab works well for this

This parallel workflow means the human never becomes a bottleneck waiting for the AI agent to finish. You are always either reviewing the agent's output, managing your task backlog, or capturing the next set of ideas.

---

## Creating Follow-Up Tasks During Implementation

While working on a task via [`/aitask-pick`](skills.md#aitask-pick-number), Claude Code has full context about the current implementation: the codebase, the task definition, the plan, and all changes made so far. This makes it an ideal moment to create follow-up tasks — far richer than creating them separately with [`ait create`](commands.md#ait-create) or [`/aitask-create`](skills.md#aitask-create).

**During implementation:**

When you notice something that needs a follow-up task while Claude is working, simply ask:

- "Create a follow-up task for refactoring the auth middleware"
- "Add a task to fix the edge case I noticed in the validation logic"
- "Create a task for adding tests to the module we just modified"

Claude invokes [`/aitask-create`](skills.md#aitask-create) with the current session context already loaded. The resulting task definition automatically includes specific file paths, line numbers, code patterns, and references to the current implementation — details that would be tedious to re-explain in a standalone task creation session.

**After implementation (during review):**

During the review step of `/aitask-pick`, you may realize additional work is needed that falls outside the current task's scope. Before committing or after selecting "Need more changes", ask Claude to create follow-up tasks. The full implementation context — including the diff and plan file — is still available, so the generated task definitions are detailed and accurate.

**Advantages over standalone task creation:**

- **No context re-entry** — Claude already knows the codebase state, what was changed, and why
- **Richer task definitions** — Includes specific file paths, function names, line numbers, and code patterns from the current session
- **Obvious dependencies** — Claude can auto-set `depends: [t108]` because it knows which task was just implemented
- **Batch creation** — Multiple related follow-up tasks can be created in one conversation, with cross-references between them
