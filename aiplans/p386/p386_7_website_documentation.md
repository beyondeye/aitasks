---
Task: t386_7_website_documentation.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md through t386_6_*.md
Archived Sibling Plans: aiplans/archived/p386/p386_1_*.md through p386_6_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Website Documentation

## Step 1: Create workflow guide

`website/content/docs/workflows/multi-agent.md`:
- Hugo frontmatter (title, weight, description)
- End-to-end walkthrough:
  - Creating an agentset (`ait agentset init`)
  - Defining agent types with max_parallel
  - Adding agents with dependencies (`ait agentset add`)
  - Writing work2do files with checkpoints
  - Starting the runner
  - Monitoring via TUI dashboard
  - Cross-machine operation
  - Cleanup after completion
- Follow style of `parallel-development.md`

## Step 2: Create CLI reference

`website/content/docs/commands/agentset.md`:
- All subcommands with usage, flags, examples
- Structured output format documentation
- Follow `commands/codeagent.md` pattern

## Step 3: Create TUI docs

`website/content/docs/tuis/agentset-dashboard/_index.md`:
- Overview: what the dashboard shows, how to launch

`website/content/docs/tuis/agentset-dashboard/how-to.md`:
- How to: spawn agentset, start/stop runner, monitor agents

`website/content/docs/tuis/agentset-dashboard/reference.md`:
- Keybindings, screens, configuration options

## Step 4: Update TUI index

Add agentset dashboard entry to `website/content/docs/tuis/_index.md`.

## Step 5: Verify

- `cd website && hugo build --gc --minify`
- Review rendered pages

## Step 6: Post-Implementation (Step 9)
