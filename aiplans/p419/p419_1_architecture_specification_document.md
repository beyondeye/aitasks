---
Task: t419_1_architecture_specification_document.md
Parent Task: aitasks/t419_ait_brainstorm_architecture_design.md
Sibling Tasks: aitasks/t419/t419_2_*.md, aitasks/t419/t419_3_*.md, aitasks/t419/t419_4_*.md, aitasks/t419/t419_5_*.md, aitasks/t419/t419_6_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Architecture Specification Document

## Context
This is the foundational task — all other t419 children depend on this spec. The deliverable is a single comprehensive architecture reference document that captures every design decision, data format, and orchestration flow for the brainstorm engine.

## Steps

### Step 1: Read Source Materials
- Read `aidocs/brainstorming/building_an_iterative_ai_design_system.md` (the original design conversation)
- Read `aidocs/agentcrew/agentcrew_architecture.md` (AgentCrew reference)
- Read `aidocs/agentcrew/agentcrew_work2do_guide.md` (work2do patterns)
- Read `aidocs/brainstorming/aitask_redesign_spec.md` (related spec, for context)

### Step 2: Write the Architecture Document
Create `aidocs/brainstorming/brainstorm_engine_architecture.md` with these sections:

#### Section 1: Overview
- Purpose of the brainstorm engine
- Relationship to aitasks (each session tied to a task)
- High-level architecture: TUI orchestrator + AgentCrew + design space DAG

#### Section 2: Directory Structure
- `.aitask-brainstorm/<task_num>/` layout
- Purpose of each subdirectory and file

#### Section 3: Data Format Specifications
Document each YAML/MD format with field-level descriptions:

**session.yaml:**
```yaml
task_id: 419
task_file: aitasks/t419_brainstorm_architecture_design.md
status: active          # active | paused | completed | archived
crew_id: brainstorm-419
created_at: 2026-03-18 14:00
updated_at: 2026-03-18 15:30
created_by: user@example.com
initial_spec: |
  Brief description...
```

**graph_state.yaml:**
```yaml
current_head: n001_relational
history:
  - n000_init
  - n001_relational
next_node_id: 2
active_dimensions:
  - database
  - cache
  - api_layer
```

**Flat YAML node schema (nodes/nXXX_name.yaml):**
```yaml
node_id: n001_relational
parents: [n000_init]
description: Uses PostgreSQL with normalized tables
proposal_file: proposals/n001_relational.md
plan_file: plans/n001_relational_plan.md  # optional
created_at: 2026-03-18 14:05
created_by_group: explore_001  # which operation group created this

# Flattened dimensions
requirements_fixed:
  - Sub-100ms latency
  - ACID compliance
requirements_mutable:
  - Deployment target
assumption_scale: 10k DAU
assumption_team_skill: Strong TypeScript
component_database: PostgreSQL
component_cache: none
component_api_layer: tRPC
tradeoff_pros:
  - Data integrity
  - Flexible querying
tradeoff_cons:
  - Connection pooling overhead
```

**Proposal markdown template (proposals/nXXX_name.md):**
Required sections: Overview, Architecture, Data Flow, Components, Assumptions, Tradeoffs

**Plan markdown template (plans/nXXX_name_plan.md):**
Required sections: Prerequisites, Step-by-step Changes, Testing, Verification

#### Section 4: AgentCrew Integration
- Persistent crew model (one crew per session)
- Operation groups: naming convention (explore_001, compare_002), priority scheduling, group commands/queries
- Agent types table: explorer, comparator, synthesizer, detailer, patcher with agent_string and max_parallel recommendations
- _groups.yaml schema

#### Section 5: Orchestration Flow
For each phase (init, explore, compare, hybridize, detail, finalize):
- What triggers it (user action in TUI)
- What agents are registered (type, group, inputs)
- What outputs are produced (new nodes, comparisons, plans)
- What the user decides next

Include top-down flow (Explorer → Detailer) and bottom-up flow (Plan Patcher → impact check)

#### Section 6: Subagent Prompt Specifications
Full system prompts for:
- Explorer: generates structured proposals from a mandate
- Comparator: creates comparison matrices across specified dimensions
- Synthesizer: merges components from multiple nodes, resolves conflicts
- Detailer: translates architecture into step-by-step implementation plan
- Plan Patcher: surgical plan edits with impact analysis

Each prompt includes: Role description, Input format, Output format, Rules/constraints

### Step 3: Review and Cross-Reference
- Ensure all schemas are consistent (field names match across documents)
- Verify subagent prompts reference the correct YAML field names
- Check that the flow description covers all operations mentioned in the design doc

## Verification
- Document is self-contained (can be understood without reading the design conversation)
- All YAML schemas have field-level documentation
- All 5 subagent prompts are complete and specific
- No references to undefined schemas or unspecified operations

## Post-Implementation
- Step 9: archive task, push changes
