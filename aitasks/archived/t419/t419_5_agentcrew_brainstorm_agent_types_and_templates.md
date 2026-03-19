---
priority: medium
effort: medium
depends: [t419_4, 1, 2]
issue_type: feature
status: Done
labels: [brainstorming, agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-18 14:58
updated_at: 2026-03-19 12:07
completed_at: 2026-03-19 12:07
---

## Context
The brainstorm engine (t419) uses AgentCrew to orchestrate 5 types of subagents: Explorer, Comparator, Synthesizer, Detailer, and Plan Patcher. Each needs a work2do template and a helper to register agents into the brainstorm crew with the right group, inputs, and configuration.

## Key Files to Read
- aidocs/brainstorming/brainstorm_engine_architecture.md — subagent prompt specs, agent type definitions (created by t419_1)
- aidocs/brainstorming/building_an_iterative_ai_design_system.md — original subagent role definitions and prompts
- aidocs/agentcrew/agentcrew_work2do_guide.md — work2do template patterns, lifecycle operations, checkpoint pattern
- .aitask-scripts/agentcrew/agentcrew_utils.py — agent type constants

## Reference Files for Patterns
- aidocs/agentcrew/agentcrew_work2do_guide.md — work2do template structure with phases, checkpoints, abstract operations

## Deliverable

### Work2do Templates (.aitask-scripts/brainstorm/templates/)

#### explorer.md
- Phase 1: Read baseline node YAML and proposal MD from input
- Phase 2: Generate new architectural proposal based on exploration mandate
- Phase 3: Write flat YAML node metadata to output (node_id, parents, dimensions)
- Phase 4: Write full proposal markdown to output
- Checkpoints after each phase with report_alive and check_commands

#### comparator.md
- Phase 1: Read target node YAML files and requested dimensions from input
- Phase 2: Generate comparison matrix (markdown table) across specified dimensions
- Phase 3: Write Delta Summary with key tradeoffs and risks
- Output: structured markdown with table + summary

#### synthesizer.md
- Phase 1: Read parent node YAMLs, proposal MDs, and merge instructions from input
- Phase 2: Identify conflicts between parent components/assumptions
- Phase 3: Resolve conflicts (introduce bridging components or update assumptions)
- Phase 4: Write merged node YAML and proposal MD to output

#### detailer.md
- Phase 1: Read finalized node YAML, proposal MD, and codebase context from input
- Phase 2: Translate architecture into step-by-step implementation plan
- Phase 3: Write plan MD with prerequisites, file changes, commands, testing steps

#### patcher.md
- Phase 1: Read current node YAML, plan MD, and user tweak request from input
- Phase 2: Apply surgical changes to the plan
- Phase 3: Impact Analysis — check if changes affect high-level dimensions
- Phase 4: Output patched plan + IMPACT_FLAG if architecture update needed

### brainstorm_crew.py — Agent Registration Helper
- register_explorer(session_dir, crew_id, mandate, base_node_id, group_name) — registers an Explorer agent with input wired from the base node
- register_comparator(session_dir, crew_id, node_ids, dimensions, group_name) — registers Comparator with node data as input
- register_synthesizer(session_dir, crew_id, parent_node_ids, merge_rules, group_name) — registers Synthesizer
- register_detailer(session_dir, crew_id, node_id, codebase_paths, group_name) — registers Detailer
- register_patcher(session_dir, crew_id, node_id, tweak_request, group_name) — registers Plan Patcher
- Each function: reads node data, writes input file, calls ait crew addwork with --group

### Agent Type Definitions
- Document recommended _crew_meta.yaml agent_types block for brainstorm crews
- explorer: agent_string claudecode/opus4_6, max_parallel 3
- comparator: agent_string claudecode/sonnet4_6, max_parallel 1
- synthesizer: agent_string claudecode/opus4_6, max_parallel 1
- detailer: agent_string claudecode/opus4_6, max_parallel 1
- patcher: agent_string claudecode/sonnet4_6, max_parallel 1

## Verification
- Each work2do template follows the checkpoint pattern from agentcrew_work2do_guide.md
- Templates use only abstract operations (report_alive, check_commands, write_output, update_status)
- brainstorm_crew.py register functions produce valid ait crew addwork calls
- Agent type definitions are valid YAML
