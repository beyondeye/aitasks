---
title: "/aitask-explore"
linkTitle: "/aitask-explore"
weight: 20
description: "Explore the codebase interactively, then create a task from findings"
---

Explore the codebase interactively with guided investigation, then create a task from findings. This skill bridges the gap between "I think something needs work" and a well-defined task with context.

**Usage:**
```
/aitask-explore
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

1. **Profile selection** — Same profile system as `/aitask-pick`
2. **Exploration setup** — Choose an exploration mode:
   - **Investigate a problem** — Debug an issue, trace a symptom, find a root cause. Creates bug tasks by default
   - **Explore codebase area** — Understand a module, map its structure and dependencies. Offers two ways to specify the target: search for files interactively (by keyword, name, or functionality) or describe the area in free text
   - **Scope an idea** — Discover what code is affected by a proposed change
   - **Explore documentation** — Find documentation gaps, outdated docs, or missing help text
3. **Iterative exploration** — Claude explores the codebase using the selected strategy. After each round, presents findings and offers to continue exploring, create a task, or abort
4. **Task creation** — Summarizes all findings and creates a task file with metadata pre-filled based on the exploration type
5. **Optional handoff** — After task creation, choose to continue directly to implementation (via the standard `/aitask-pick` skill) or save the task for later

## Key Capabilities

- **Guided exploration strategies** — Each exploration mode has a tailored investigation approach. Problem investigation traces data flow and error handling; codebase exploration maps dependencies and patterns; idea scoping estimates blast radius
- **Iterative discovery** — Multiple exploration rounds with user-directed focus. Redirect the investigation at any point based on intermediate findings
- **Context-rich task creation** — Tasks created from exploration include specific findings, file paths, and investigation context that would be tedious to write manually
- **Seamless handoff** — When continuing to implementation, the full exploration context flows into the planning phase

**Profile key:** `explore_auto_continue` — Set to `true` to skip the "continue to implementation or save" prompt and automatically proceed to implementation.

## File Selection

The **Explore codebase area** mode provides an interactive file search interface powered by the internal `user-file-select` skill. When you choose "Search for files", you can find files by:

- **Keyword search** — Search file contents for specific terms or patterns
- **Name search** — Fuzzy-match against file names across the project
- **Functionality search** — Describe what the code does and let Claude find matching files

Alternatively, you can choose "Describe the area" to type a module name, directory, or free-text description directly — preserving the original behavior for users who already know where to look.

The same file search interface is also available in [`/aitask-explain`](../aitask-explain/).

## Folded Tasks

During task creation, `/aitask-explore` scans pending tasks (`Ready`/`Editing` status) for overlap with the new task. If related tasks are found, you're prompted to select which ones to "fold in" — their content is incorporated into the new task's description, and the originals are automatically deleted when the new task is archived after implementation.

Only standalone parent tasks (no children) can be folded. The `folded_tasks` frontmatter field tracks which tasks were folded in. During planning, there's no need to re-read the original folded task files — all relevant content is already in the new task.

To fold tasks outside of the explore skill, use [`/aitask-fold`](../aitask-fold/) — a dedicated skill for identifying and merging related tasks.

## Workflows

For a full workflow guide covering exploration modes and use cases, see [Exploration-Driven Development](../../workflows/exploration-driven/).
