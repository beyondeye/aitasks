---
title: "Overview"
linkTitle: "Overview"
weight: 5
description: "The challenge aitasks addresses, its core philosophy, and key features."
---

## The Challenge

AI coding agents have reached a proficiency level where, given correct specs and intent, they can handle most code-development tasks on their own. The real bottleneck is **transferring intent** from developer to agent — structured enough to build useful context, fast enough that the human does not become the drag. aitasks is a full agentic IDE in your terminal built around this transfer: tasks are living markdown files, refined iteratively alongside the code that implements them.

## Core Philosophy

**"Light Spec" engine:** unlike rigid Spec-Driven Development, tasks here are living documents:

- **Raw intent:** a task starts as a simple Markdown file capturing the goal.
- **Iterative refinement:** an included AI workflow refines task files in stages — expanding context, adding technical details, and verifying requirements — before code is written.

## Key Features

### 1. Agentic IDE in your terminal

Everything you need to plan, implement, review, and ship runs in one tmux session — no browser, no external app. Boot the full layout with `ait ide` and hop between views with a single keystroke.

- **Board** — Kanban-style TUI for task state, priority, and assignment.
- **Code Browser** — read the repo with per-line task/plan annotations.
- **Monitor** / **Minimonitor** — watch agent activity across parallel worktrees.
- **Brainstorm** / **Settings** — idea capture and profile/label management.
- **`j`-switcher** — jump between TUIs without leaving the terminal.

See also: {{< relref "/docs/concepts/ide-model" >}}, {{< relref "/docs/installation/terminal-setup" >}}, {{< relref "/docs/tuis" >}}.

### 2. Long-term memory for agents

Archived tasks and plans remain queryable context for future work. The repo does not just remember *what* changed — it remembers *why* and *by whom*.

- Archived plan files serve as the primary reference for sibling child tasks.
- Code Browser annotates each line back to the task and plan that introduced it.
- `/aitask-explain` traces the evolution of any file through its originating tasks.

See also: {{< relref "/docs/concepts/agent-memory" >}}, {{< relref "/docs/skills/aitask-explain" >}}.

### 3. Tight git coupling, AI-enhanced

Task state lives in git — no SQL backend, no daemon. Git-based workflows (PRs, issues, contributions, reverts) get AI-enhanced skills on top of the same commits.

- `./ait git` wrapper with an optional separate task-data branch to keep history tidy.
- PR import/close, issue-tracker integration, and contribution flow across GitHub/GitLab/Bitbucket.
- Changelog generation from archived tasks; AI-assisted reverts by task ID.

See also: {{< relref "/docs/concepts/git-branching-model" >}}, {{< relref "/docs/workflows/pr-workflow" >}}, {{< relref "/docs/workflows/issue-tracker" >}}, {{< relref "/docs/workflows/revert-changes" >}}.

### 4. Task decomposition & parallelism

Complex tasks rarely fit a single context window. aitasks breaks them into child tasks, propagates sibling context, and runs them in isolated git worktrees so multiple agents can work side by side without stepping on each other.

- Auto-explode complex tasks into well-scoped child tasks during planning.
- Sibling context propagation — each child sees what came before.
- Git worktrees + atomic locks for true parallel agent work.
- Plan-verification tracking so picked-up work resumes safely.

See also: {{< relref "/docs/concepts/parent-child" >}}, {{< relref "/docs/workflows/task-decomposition" >}}, {{< relref "/docs/workflows/parallel-development" >}}.

### 5. AI-enhanced code review

Reviews are a workflow, not a checklist. Review guides, QA, and code explanations are first-class citizens with traceability back to the originating task.

- Per-language review guides, automatically suggested for changed files.
- Batched multi-file reviews that produce follow-up tasks, not just comments.
- QA workflow that turns review findings into testable child tasks.

See also: {{< relref "/docs/concepts/review-guides" >}}, {{< relref "/docs/workflows/code-review" >}}, {{< relref "/docs/workflows/qa-testing" >}}.

### 6. Multi-agent support with verified scores

One framework, many code agents. A single `codeagent` wrapper runs Claude Code, Gemini CLI, Codex CLI, and OpenCode — and accumulates per-model and per-operation success scores from real user feedback.

- Drop-in support for Claude Code, Gemini CLI, Codex CLI, OpenCode.
- Per-operation scoring (planning, implementation, review) instead of generic benchmarks.
- Verified scores accumulate from your team's actual usage, not synthetic tests.
- Switch agents per-task without rewriting workflows.

See also: {{< relref "/docs/concepts/agent-attribution" >}}, {{< relref "/docs/concepts/verified-scores" >}}, {{< relref "/docs/commands/codeagent" >}}, {{< relref "/docs/skills/verified-scores" >}}.

## Additional properties

- **Dual-Mode CLI** — every `ait` command is optimized for both humans and agents:
  - *Interactive mode (for humans):* optimized for flow — rapidly create, edit, and prioritize tasks without context switching.
  - *Batch mode (for agents):* AI agents read specs, create tasks, and update status programmatically via CLI flags.
- **Battle tested** — actively developed and used in real projects, not a research experiment.
- **Fully customizable workflow** — all scripts and workflow skills live in your project repo. Adapt them to your needs, then use the built-in [`/aitask-contribute`]({{< relref "/docs/skills/aitask-contribute" >}}) skill to share improvements back upstream or with your team.

---

**Next:** [Installation]({{< relref "/docs/installation" >}})
