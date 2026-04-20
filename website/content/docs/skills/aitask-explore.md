---
title: "/aitask-explore"
linkTitle: "/aitask-explore"
weight: 20
description: "Explore the codebase interactively, then create a task from findings"
---

Explore the codebase interactively with guided investigation, then create a task from findings. This skill bridges the gap between "I think something needs work" and a well-defined task with context.

**Usage:**
```
/aitask-explore [--profile <name>]
```

The optional `--profile <name>` argument overrides execution-profile selection for this invocation, mirroring `/aitask-pick --profile`.

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.
>
> **Codex CLI note:** When continuing from this skill into implementation, in Codex wrappers, after implementation, most of the times you will need to explicitly tell the agent to continue the workflow because `request_user_input` is only available in plan mode. Example prompts: `Good, now finish the workflow` or `Good, now continue`.

## Step-by-Step

1. **Exploration setup** — Choose an exploration mode:
   - **Investigate a problem** — Debug an issue, trace a symptom, find a root cause. Creates bug tasks by default
   - **Explore codebase area** — Understand a module, map its structure and dependencies. Offers two ways to specify the target: search for files interactively (by keyword, name, or functionality) or describe the area in free text
   - **Scope an idea** — Discover what code is affected by a proposed change
   - **Explore documentation** — Find documentation gaps, outdated docs, or missing help text
2. **Iterative exploration** — The skill explores the codebase using the selected strategy. After each round, it presents findings and offers to continue exploring, create a task, or abort
3. **Task creation** — Summarizes all findings and creates a task file with metadata pre-filled based on the exploration type (and optionally folds in related pending tasks)
4. **Profile selection** — Same profile system as `/aitask-pick`. Deferred until after task creation so exploration itself is profile-independent; profile choice only affects the downstream handoff
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
- **Functionality search** — Describe what the code does and let the agent find matching files

Alternatively, you can choose "Describe the area" to type a module name, directory, or free-text description directly — preserving the original behavior for users who already know where to look.

The same file search interface is also available in [`/aitask-explain`](../aitask-explain/).

## Folded Tasks

During task creation, `/aitask-explore` scans pending tasks (`Ready`/`Editing` status) for overlap with the new task. If related tasks are found, you're prompted to select which ones to "fold in" — their content is incorporated into the new task's description, and the originals are automatically deleted when the new task is archived after implementation.

Only standalone parent tasks (no children) can be folded. The `folded_tasks` frontmatter field tracks which tasks were folded in. During planning, there's no need to re-read the original folded task files — all relevant content is already in the new task.

To fold tasks outside of the explore skill, use [`/aitask-fold`](../aitask-fold/) — a dedicated skill for identifying and merging related tasks.

## Workflows

For a full workflow guide covering exploration modes and use cases, see [Exploration-Driven Development](../../workflows/exploration-driven/).

## Related

- [`/aitask-fold`](../aitask-fold/) — Standalone task folding without exploration
- [`/aitask-pick`](../aitask-pick/) — The downstream implementation skill that picks up the task created here
