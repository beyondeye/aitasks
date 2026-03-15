---
priority: medium
effort: medium
depends: [t386_5, 1, 2]
issue_type: documentation
status: Ready
labels: [subagents]
created_at: 2026-03-15 10:51
updated_at: 2026-03-15 10:51
---

## Architecture Documentation & work2do Authoring Guide

### Context
This child task creates internal documentation (in `aidocs/`) that serves as the reference for understanding the AgentSet architecture and for authoring work2do files that integrate with the agentset lifecycle checkpoints. Depends on t386_1 and t386_2 (needs data model and status/command definitions).

### Goal
Write comprehensive architecture docs and a practical guide for designing work2do files with checkpoint integration, using abstract operation names that are mapped to concrete scripts via `instructions.md`.

### Key Files to Create
- `aidocs/agentset_architecture.md` — Detailed architecture reference
- `aidocs/agentset_work2do_guide.md` — work2do authoring guide with checkpoint patterns

### Architecture Reference Scope
- AgentSet concept and lifecycle (init -> add agents -> run -> complete/cleanup)
- Branch and worktree structure (`.aitask-agentsets/agentset-<id>/`)
- Complete file layout and YAML schemas for all file types
- Agent and AgentSet status state machines with transition diagrams
- Meta vs Status split (`_agentset_meta.yaml` vs `_agentset_status.yaml`)
- Agent types and per-type `max_parallel` configuration
- DAG dependency model
- Runner orchestration flow and `_runner_alive.yaml`
- Single-instance enforcement (cross-machine via git)
- Concurrent write strategy (agents write files, runner commits)
- Command and control system (kill, pause, resume)
- Heartbeat and stuck-agent detection

### work2do Authoring Guide Scope
- **Checkpoint pattern:** How to structure work2do with periodic checkpoints
- **Lifecycle operations by abstract name** (NOT script-specific):
  - `report_alive` — Update heartbeat + progress message
  - `update_status` — Transition agent status
  - `update_progress` — Report numeric progress
  - `read_input` — Read input data
  - `write_output` — Write results
  - `check_commands` — Check for pending commands (kill, pause)
  - `run_abort_procedure` — Clean shutdown on kill/abort
  - `report_error` — Report error with message
- **Checkpoint placement guidelines:** Frequency, placement (after major steps, in loops, before/after expensive ops)
- **Instructions.md mapping:** How `instructions.md` maps operation names to actual script calls. The work2do uses abstract names; instructions.md provides concrete commands. This separation keeps work2do templates reusable across different agentset configurations.
- **Template work2do structure** with example checkpoints showing the pattern

### Verification
- Review by reading the docs and verifying all referenced file formats match actual implementation
- Cross-reference with `_agentset_meta.yaml` and `_status.yaml` schemas from t386_1
