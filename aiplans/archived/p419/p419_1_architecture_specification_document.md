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

## Post-Review Changes

### Change Request 1 (2026-03-18)
- **Requested by user:** Context assembly is not addressed — agents start with empty context and need a specification for how input is assembled
- **Changes made:** Added Section 6 (Context Assembly) covering: the reference-based input model, per-agent-type input assembly formats, reference file tracking across DAG evolution, and context window management
- **Files affected:** `aidocs/brainstorming/brainstorm_engine_architecture.md`

### Change Request 2 (2026-03-18)
- **Requested by user:** reference_files should support remote URLs, not just local files
- **Changes made:** Updated reference_files schema to support both local paths and URLs. Added URL caching in br_url_cache/ with configurable settings in br_session.yaml (global toggle + per-URL bypass)
- **Files affected:** `aidocs/brainstorming/brainstorm_engine_architecture.md`

### Change Request 3 (2026-03-18)
- **Requested by user:** Brainstorm data should share the AgentCrew crew branch for multi-user/PC access via git
- **Changes made:** Unified brainstorm session data into the crew worktree at `.aitask-crews/crew-brainstorm-<task_num>/`. All brainstorm files prefixed with `br_` for namespace separation. Added Source Control Model, Lifecycle and Cleanup sections.
- **Files affected:** `aidocs/brainstorming/brainstorm_engine_architecture.md`

### Change Request 4 (2026-03-18)
- **Requested by user:** Files should be referenced (paths) not inlined in _input.md; cached URLs should note source URL
- **Changes made:** Updated all context assembly input formats to use file path references instead of inlined contents. Cached URL references include `(source: <url>)` annotation.
- **Files affected:** `aidocs/brainstorming/brainstorm_engine_architecture.md`

### Change Request 5 (2026-03-18)
- **Requested by user:** Note future interactive patching mode; add references to AgentCrew docs
- **Changes made:** Added "Future: Interactive Patching Mode" note in Section 7.6. Added References section at document end linking to agentcrew_architecture.md, agentcrew_work2do_guide.md, and building_an_iterative_ai_design_system.md.
- **Files affected:** `aidocs/brainstorming/brainstorm_engine_architecture.md`

## Final Implementation Notes
- **Actual work done:** Created `aidocs/brainstorming/brainstorm_engine_architecture.md` (1500+ lines) — the complete architecture specification document for the brainstorm engine. The document covers 8 sections: Overview, Directory Structure, Data Format Specifications, Proposal/Plan Templates, AgentCrew Integration, Context Assembly, Orchestration Flow, and Subagent Prompt Specifications.
- **Deviations from plan:** Added Section 6 (Context Assembly) which was not in the original plan but was identified as a critical gap during review. The directory structure changed from standalone `.aitask-brainstorm/` to unified crew worktree. All brainstorm files use `br_` prefix for namespace separation.
- **Issues encountered:** Five rounds of review feedback were needed to address: context assembly gap, URL support in references, source control model, reference-based (not inlined) input, and interactive patching note.
- **Key decisions:** (1) Brainstorm data lives on the AgentCrew crew branch — no separate branch needed. (2) `_input.md` contains file references, not inlined contents — agents read files themselves. (3) URL caching is configurable (global toggle + per-URL bypass). (4) Interactive patching mode deferred to future.
- **Notes for sibling tasks:** The architecture document defines the canonical schema names (br_session.yaml, br_graph_state.yaml, br_nodes/, br_proposals/, br_plans/, br_groups.yaml) that all sibling tasks must follow. The `reference_files` field in node YAML supports both local paths and URLs. The _groups.yaml schema is new and will be implemented by t419_2. The DAG operations (t419_3) should read/write br_nodes/ and br_graph_state.yaml. Session management scripts (t419_4) should read/write br_session.yaml.

## Post-Implementation
- Step 9: archive task, push changes
