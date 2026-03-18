---
priority: high
effort: high
depends: []
issue_type: documentation
status: Ready
labels: [brainstorming, agentcrew]
created_at: 2026-03-18 14:58
updated_at: 2026-03-18 14:58
---

## Context
This is the foundational child task for t419 (Brainstorm Engine Architecture). All other child tasks depend on this specification document. The brainstorm engine is an iterative AI design system that uses a DAG-based approach to explore, compare, and hybridize architectural proposals. It uses AgentCrew for multi-agent orchestration with a persistent crew per session and operation groups.

## Key Files to Read
- aidocs/brainstorming/building_an_iterative_ai_design_system.md — original design conversation defining the conceptual model (Orchestrator, Explorer, Comparator, Synthesizer, Detailer, Plan Patcher subagents, DAG structure, flat YAML nodes, bidirectional flow)
- aidocs/brainstorming/aitask_redesign_spec.md — related redesign spec (defers AgentCrew integration)
- aidocs/agentcrew/agentcrew_architecture.md — AgentCrew reference (lifecycle, file layout, YAML schemas, runner, DAG dependencies)
- aidocs/agentcrew/agentcrew_work2do_guide.md — work2do template patterns

## Deliverable
Create aidocs/brainstorming/brainstorm_engine_architecture.md — the complete architecture reference document covering:

### 1. Data Format Specifications
- Flat YAML node schema (nodes/nXXX_name.yaml): node_id, parents, description, proposal_file, plan_file, flattened dimensions (requirements_fixed, requirements_mutable, assumption_*, component_*, tradeoff_pros, tradeoff_cons)
- graph_state.yaml: current_head, history list, next_node_id, active_dimensions
- session.yaml: task_id, task_file, status (active/paused/completed/archived), created_at, updated_at, created_by, crew_id, initial_spec

### 2. Proposal/Plan Markdown Templates
- Proposal template with required sections (Overview, Architecture, Data Flow, Components, Assumptions, Tradeoffs)
- Plan template with required sections (Prerequisites, Step-by-step changes, Testing, Verification)

### 3. Directory Structure
- .aitask-brainstorm/task_num/ layout: session.yaml, graph_state.yaml, nodes/, proposals/, plans/

### 4. AgentCrew Integration Design
- Persistent crew model: one crew brainstorm-task_num per session
- Operation groups: each operation (explore, compare, hybridize, detail, patch) registers agents under a group (e.g. explore_001, compare_002)
- Group priority scheduling: lower sequence number = higher priority
- Group-level commands and status queries
- Agent type definitions: explorer, comparator, synthesizer, detailer, patcher — with recommended agent_string and max_parallel settings

### 5. Orchestration Flow
- Full flow: init, explore, compare, hybridize, detail, finalize
- For each step: what the TUI does, which agents are created, what inputs they receive, what outputs they produce, what the user decides next
- Top-down flow (architectural changes via Explorer then Detailer then new plan)
- Bottom-up flow (plan tweaks via Plan Patcher then impact check then possible escalation)

### 6. Subagent Prompt Specifications
- System prompt for each of the 5 roles (Explorer, Comparator, Synthesizer, Detailer, Plan Patcher)
- Input/output format expectations
- Rules and constraints for each role

## Verification
- Document is self-contained and can be understood without reading the original design conversation
- All YAML schemas include field-level documentation
- All subagent prompts are specific enough to produce consistent output formats
