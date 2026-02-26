---
title: "Capturing Ideas Fast"
linkTitle: "Capturing Ideas"
weight: 10
description: "Quickly capture task ideas without breaking your flow"
---

The most important thing when a new task idea comes to mind is capturing it immediately, before the thought fades. The [`ait create`](../../commands/task-management/#ait-create) script is designed for this: you can write a task description as a raw stream of consciousness without worrying about structure, grammar, or completeness.

**The philosophy: capture intent now, refine later.**

In interactive mode, `ait create` walks you through metadata selection (priority, effort, labels) via fast fzf menus, then lets you enter the description as consecutive text blocks. There is no need to open an external editor or craft a polished specification — Claude is perfectly capable of understanding rough, unstructured descriptions with missing details.

**Recommended setup:** Keep a terminal tab with `ait create` ready to launch at all times. When an idea strikes — even mid-implementation on another task — switch to that tab, type the idea, assign basic metadata, and get back to work. The task is saved as a local draft in `aitasks/new/` (gitignored, no network needed) and can be finalized later.

**The iterative refinement pipeline:**

1. **Capture** — Create the task with [`ait create`](../../commands/task-management/#ait-create) or [`/aitask-create`](../../skills/aitask-create/). Write whatever comes to mind, even multiple paragraphs of loosely connected ideas
2. **Organize** — Use [`ait board`](../../commands/board-stats/#ait-board) to visually triage: drag tasks between kanban columns, adjust priority and effort, add labels. See the [Board documentation](../../tuis/board/) for detailed how-to guides
3. **Refine** — When picked for implementation with [`/aitask-pick`](../../skills/aitask-pick/), the planning phase explores the codebase and produces a structured implementation plan from your raw intent

This pipeline means you never need to spend time writing perfect task descriptions upfront. The framework handles progressive refinement at each stage.
