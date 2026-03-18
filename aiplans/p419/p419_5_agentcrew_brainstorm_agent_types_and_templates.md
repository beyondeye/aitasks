---
Task: t419_5_agentcrew_brainstorm_agent_types_and_templates.md
Parent Task: aitasks/t419_ait_brainstorm_architecture_design.md
Sibling Tasks: aitasks/t419/t419_1_*.md, aitasks/t419/t419_2_*.md, aitasks/t419/t419_3_*.md, aitasks/t419/t419_4_*.md, aitasks/t419/t419_6_*.md
Archived Sibling Plans: aiplans/archived/p419/p419_1_*.md, aiplans/archived/p419/p419_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: AgentCrew Brainstorm Agent Types & Work2do Templates

## Context
Defines the 5 brainstorm agent roles as AgentCrew work2do templates and provides a Python helper to register them into a brainstorm crew with proper group assignment. Depends on t419_1 (prompts from spec) and t419_2 (group support in AgentCrew).

## Steps

### Step 1: Create Templates Directory
```bash
mkdir -p .aitask-scripts/brainstorm/templates
```

### Step 2: Write Work2do Templates

Each template follows the checkpoint pattern from `aidocs/agentcrew/agentcrew_work2do_guide.md`. Templates use abstract operations that `_instructions.md` will map to concrete CLI commands.

#### explorer.md
```markdown
# Task: Architecture Explorer

## Phase 1: Read Baseline
- Read the baseline node YAML and proposal from input
- Understand the exploration mandate

### Checkpoint 1
- report_alive: "Reading baseline node and mandate"
- update_progress: 10
- check_commands

## Phase 2: Generate Proposal
- Analyze the mandate against the baseline architecture
- Draft a comprehensive proposal covering: Overview, Architecture, Data Flow, Components, Assumptions, Tradeoffs
- Ensure all dimensions from the baseline are addressed (modified or inherited)

### Checkpoint 2
- report_alive: "Generating architectural proposal"
- update_progress: 50
- check_commands

## Phase 3: Write Output
- Write flat YAML node metadata to output:
  - node_id, parents, description
  - All flattened dimensions (requirements_*, assumption_*, component_*, tradeoff_*)
- Write full proposal markdown to output (separated by --- delimiter)

### Checkpoint 3
- report_alive: "Writing output"
- update_progress: 90
- check_commands

## Completion
- update_status: Completed
- update_progress: 100
```

#### comparator.md
Similar structure:
- Phase 1: Read node YAMLs and requested dimensions from input
- Phase 2: Generate comparison matrix (markdown table)
- Phase 3: Write Delta Summary with key tradeoffs
- Output: structured markdown

#### synthesizer.md
- Phase 1: Read parent node YAMLs, proposals, and merge instructions
- Phase 2: Identify conflicts between components/assumptions
- Phase 3: Resolve conflicts (bridging components or updated assumptions)
- Phase 4: Write merged node YAML and proposal

#### detailer.md
- Phase 1: Read finalized node YAML, proposal, and codebase paths
- Phase 2: Translate architecture into step-by-step plan
- Phase 3: Write plan with prerequisites, file changes, commands, tests

#### patcher.md
- Phase 1: Read current node YAML, plan, and tweak request
- Phase 2: Apply surgical edits to plan
- Phase 3: Impact analysis — check if high-level dimensions are affected
- Phase 4: Output patched plan + IMPACT_FLAG if architecture update needed

### Step 3: brainstorm_crew.py — Registration Helper

```python
from __future__ import annotations
from pathlib import Path
import subprocess
import yaml

TEMPLATE_DIR = Path(__file__).parent / "templates"

def _register_agent(crew_id: str, agent_name: str, agent_type: str,
                    group_name: str, work2do_path: str,
                    input_content: str, depends: list[str] = None) -> str:
    """Register an agent via ait crew addwork. Returns agent name."""

def register_explorer(session_dir: Path, crew_id: str,
                      mandate: str, base_node_id: str,
                      group_name: str, agent_suffix: str = "") -> str:
    """Register an Explorer agent.
    - Reads base node YAML and proposal
    - Writes input file with baseline + mandate
    - Calls ait crew addwork with explorer template and group
    """

def register_comparator(session_dir: Path, crew_id: str,
                        node_ids: list[str], dimensions: list[str],
                        group_name: str) -> str:
    """Register a Comparator agent.
    - Reads YAML for each node, extracts requested dimensions
    - Writes input with filtered node data
    """

def register_synthesizer(session_dir: Path, crew_id: str,
                         parent_node_ids: list[str], merge_rules: str,
                         group_name: str) -> str:
    """Register a Synthesizer agent.
    - Reads parent YAMLs and proposals
    - Writes input with merge instructions
    """

def register_detailer(session_dir: Path, crew_id: str,
                      node_id: str, codebase_paths: list[str],
                      group_name: str) -> str:
    """Register a Detailer agent.
    - Reads finalized node and proposal
    - Writes input with codebase context
    """

def register_patcher(session_dir: Path, crew_id: str,
                     node_id: str, tweak_request: str,
                     group_name: str) -> str:
    """Register a Plan Patcher agent.
    - Reads current node YAML and plan
    - Writes input with tweak request
    """

# Agent type definitions for _crew_meta.yaml
BRAINSTORM_AGENT_TYPES = {
    "explorer": {"agent_string": "claudecode/opus4_6", "max_parallel": 3},
    "comparator": {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1},
    "synthesizer": {"agent_string": "claudecode/opus4_6", "max_parallel": 1},
    "detailer": {"agent_string": "claudecode/opus4_6", "max_parallel": 1},
    "patcher": {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1},
}
```

### Step 4: Default _crew_meta.yaml Template
Create a template that `aitask_brainstorm_init.sh` uses when creating the crew:
```yaml
agent_types:
  explorer:
    agent_string: claudecode/opus4_6
    max_parallel: 3
  comparator:
    agent_string: claudecode/sonnet4_6
    max_parallel: 1
  synthesizer:
    agent_string: claudecode/opus4_6
    max_parallel: 1
  detailer:
    agent_string: claudecode/opus4_6
    max_parallel: 1
  patcher:
    agent_string: claudecode/sonnet4_6
    max_parallel: 1
```

## Key Files
- `.aitask-scripts/brainstorm/templates/explorer.md` — new
- `.aitask-scripts/brainstorm/templates/comparator.md` — new
- `.aitask-scripts/brainstorm/templates/synthesizer.md` — new
- `.aitask-scripts/brainstorm/templates/detailer.md` — new
- `.aitask-scripts/brainstorm/templates/patcher.md` — new
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — new

## Verification
- Each template follows checkpoint pattern from work2do guide
- Templates use only abstract operations
- brainstorm_crew.py register functions produce valid ait crew addwork calls
- Agent type definitions are valid YAML
- Templates can be loaded and parsed

## Post-Implementation
- Step 9: archive task, push changes
