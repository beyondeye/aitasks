---
priority: low
effort: medium
depends: [t386_6, 1, 2, 3, 4, 5, 6]
issue_type: documentation
status: Ready
labels: [subagents]
created_at: 2026-03-15 10:51
updated_at: 2026-03-15 10:51
---

## Website Documentation for AgentSet

### Context
This child task creates user-facing documentation on the Hugo/Docsy website for the AgentSet feature. It depends on all previous child tasks (t386_1-t386_6) being complete.

### Goal
Document the agentset workflow, CLI commands, and TUI dashboard on the project website following existing documentation patterns.

### Key Files to Create
- `website/content/docs/workflows/multi-agent.md` — Workflow guide: end-to-end walkthrough
- `website/content/docs/commands/agentset.md` — CLI reference for all `ait agentset` commands
- `website/content/docs/tuis/agentset-dashboard/_index.md` — TUI overview
- `website/content/docs/tuis/agentset-dashboard/how-to.md` — TUI how-to guides
- `website/content/docs/tuis/agentset-dashboard/reference.md` — TUI reference (keybindings, screens)

### Key Files to Modify
- `website/content/docs/tuis/_index.md` — Add agentset dashboard to TUI list

### Scope

**Workflow guide** (`workflows/multi-agent.md`):
- End-to-end walkthrough: creating an agentset, adding agents with dependencies, defining agent types with `max_parallel`, running the orchestrator, monitoring via TUI, cross-machine operation, cleanup
- Follow style of `parallel-development.md`, `task-decomposition.md`

**CLI reference** (`commands/agentset.md`):
- All subcommands: `init`, `add`, `status`, `command`, `runner`, `report`, `cleanup`
- Usage, flags, examples, structured output format for each
- Follow `commands/codeagent.md` pattern

**TUI docs** (`tuis/agentset-dashboard/`):
- Overview: what the dashboard shows, how to launch
- How-to: spawn agentset, start/stop runner, monitor agents, per-type concurrency
- Reference: keybindings, screens, configuration
- Follow `tuis/board/` and `tuis/codebrowser/` doc structure

### Reference Files for Patterns
- `website/content/docs/workflows/parallel-development.md` — Workflow doc style
- `website/content/docs/commands/codeagent.md` — CLI reference style
- `website/content/docs/tuis/board/` — TUI doc structure (overview, how-to, reference)

### Verification
- `cd website && hugo build --gc --minify` — Verify site builds without errors
- Manual: review rendered pages for completeness and navigation
