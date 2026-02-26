---
title: "TUI Applications"
linkTitle: "TUIs"
weight: 30
description: "Terminal-based user interfaces for task management and code understanding"
aliases:
  - /docs/board/
  - /docs/board/how-to/
  - /docs/board/reference/
---

The aitasks framework includes two terminal-based user interfaces (TUIs) built with [Textual](https://textual.textualize.io/). Although grouped together here, they serve very different stages of the typical workflow.

**[Kanban Board](board/)** (`ait board`) — Used at the **beginning** of the workflow: triage tasks, set priorities, organize work into columns, and decide what to implement next. The board is your task management hub before code gets written.

**[Code Browser](codebrowser/)** (`ait codebrowser`) — Used at the **end** of the workflow, or when onboarding to unfamiliar code: browse files with syntax highlighting and task-aware annotations that show which aitasks contributed to each section of code. The code browser helps you understand *what was done* and *why*, rebuilding knowledge about AI-generated code through the structured records that aitasks creates during implementation.

Both TUIs require the shared Python virtual environment installed by [`ait setup`]({{< relref "/docs/commands/setup-install" >}}).
