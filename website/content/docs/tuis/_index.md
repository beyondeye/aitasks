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

The aitasks framework includes several terminal-based user interfaces (TUIs) built with [Textual](https://textual.textualize.io/). Although grouped together here, they serve different stages of the typical workflow.

**[Kanban Board](board/)** (`ait board`) — Used at the **beginning** of the workflow: triage tasks, set priorities, organize work into columns, and decide what to implement next. The board is your task management hub before code gets written.

**[Code Browser](codebrowser/)** (`ait codebrowser`) — Used at the **end** of the workflow, or when onboarding to unfamiliar code: browse files with syntax highlighting and task-aware annotations that show which aitasks contributed to each section of code. Includes a **completed tasks history** screen (press `h`) for browsing all archived tasks with metadata, commit links, affected files, and plan content — directly from the codebrowser. The code browser helps you understand *what was done* and *why*, rebuilding knowledge about AI-generated code through the structured records that aitasks creates during implementation.

**[Settings](settings/)** (`ait settings`) — Configure code agent defaults, board settings, browse available models, and manage execution profiles. The settings TUI provides a centralized interface for all aitasks configuration that would otherwise require editing JSON and YAML files directly.

All TUIs require the shared Python virtual environment installed by [`ait setup`]({{< relref "/docs/commands/setup-install" >}}).
