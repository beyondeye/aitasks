---
Task: t386_6_architecture_docs_work2do_guide.md
Parent Task: aitasks/t386_subagents_infra.md
Sibling Tasks: aitasks/t386/t386_1_*.md, t386_2_*.md, t386_3_*.md through t386_7_*.md
Archived Sibling Plans: aiplans/archived/p386/p386_1_*.md, p386_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: Architecture Docs & work2do Authoring Guide

## Step 1: Create `aidocs/agentcrew_architecture.md`

Comprehensive architecture reference covering:

1. **Overview** — AgentCrew concept: coordinating multiple AI code agents via file-based DAG
2. **Lifecycle** — init → add agents → run → complete/cleanup
3. **Branch & Worktree** — `.aitask-crews/crew-<id>/` structure
4. **File Layout** — Complete listing of all files with YAML schemas:
   - `_crew_meta.yaml` (static config, agent_types with max_parallel)
   - `_crew_status.yaml` (dynamic state)
   - `_runner_alive.yaml` (runner PID, heartbeat, requested_action)
   - `<agent>_status.yaml`, `_work2do.md`, `_input.md`, `_output.md`, `_instructions.md`, `_commands.yaml`, `_alive.yaml`
5. **Status State Machines** — Agent and AgentCrew with valid transitions diagrammed
6. **Agent Types** — Per-agentcrew config mapping type ID to agent_string + max_parallel
7. **DAG Dependency Model** — How `depends_on` works, topo sort, cycle detection
8. **Runner Orchestration** — Main loop flow, per-type limits, git pull/push cycle
9. **Single-Instance Enforcement** — Cross-machine via hostname + heartbeat
10. **Concurrent Write Strategy** — Agents write files, runner serializes git ops
11. **Command & Control** — Kill, pause, resume via `_commands.yaml`
12. **Heartbeat & Stuck Detection** — `_alive.yaml`, timeout-based staleness

## Step 2: Create `aidocs/agentcrew_work2do_guide.md`

Practical guide for authoring work2do files:

1. **Checkpoint Pattern** — How to structure work with periodic lifecycle calls
2. **Lifecycle Operations** (abstract names):
   - `report_alive` — heartbeat + progress message
   - `update_status` — state transition
   - `update_progress` — numeric percentage
   - `read_input` — read input file
   - `write_output` — write results
   - `check_commands` — poll for kill/pause
   - `run_abort_procedure` — clean shutdown
   - `report_error` — error with message
3. **Checkpoint Placement** — After major steps, in loops, before expensive ops
4. **Instructions.md Mapping** — How abstract names map to concrete script calls
5. **Template work2do** — Full example with checkpoints
6. **Crew-Agnostic Design** — Why separation of work2do (abstract) and instructions (concrete) enables reuse

## Step 3: Verify

- Read through both docs for completeness
- Cross-reference YAML schemas with actual implementation files from t386_1 and t386_2

## Step 4: Post-Implementation (Step 9)

## Final Implementation Notes
- **Actual work done:** Created two comprehensive documentation files: `aidocs/agentcrew_architecture.md` (~280 lines) covering all 14 architecture topics (overview, lifecycle, file layout with full YAML schemas, status state machines with ASCII diagrams, agent types, DAG model, runner orchestration, single-instance enforcement, concurrent write strategy, command/control, heartbeat detection, runner config, TUI dashboard mention, CLI reference table). Created `aidocs/agentcrew_work2do_guide.md` (~180 lines) covering all 8 lifecycle operations with correct CLI syntax, checkpoint pattern, template work2do, instructions.md mapping, and crew-agnostic design philosophy. Also created two sibling tasks: t386_10 (TUI dashboard docs) and t386_11 (fix addwork instructions template CLI syntax bug).
- **Deviations from plan:** Added a "Known Issues" section to the work2do guide documenting the incorrect CLI syntax in the auto-generated `_instructions.md` template. Added runner configuration section to architecture doc (was in task description but not in original plan). Created sibling tasks t386_10 and t386_11 (not in original plan, added during plan verification). Updated t386_7 to depend on t386_10.
- **Issues encountered:** Discovered that `aitask_crew_addwork.sh` generates `_instructions.md` with incorrect CLI syntax (uses `--set-status`, `--heartbeat`, `--read` flags instead of sub-commands `set --status`, `heartbeat`, `list`). Created t386_11 to track this bug fix separately.
- **Key decisions:** Used the correct Python CLI sub-command syntax throughout both docs (verified by reading `agentcrew_status.py` and `aitask_crew_command.sh` source). Kept TUI dashboard coverage minimal (just a mention + reference) since t386_10 will cover it comprehensively. Documented crew status as "derived" rather than independently set — this is a key architectural distinction that wasn't obvious from the task description.
- **Notes for sibling tasks:** t386_10 (dashboard docs) should reference the architecture doc for status meanings and file schemas. t386_11 (addwork fix) should update the template to match the correct CLI syntax documented in the work2do guide. t386_7 (website docs) should use these aidocs as source material. The architecture doc's CLI reference table and status state machine diagrams can be adapted for website use.
