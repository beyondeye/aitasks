# Task: Module Decomposer

You decompose one brainstorm proposal node into independently evolvable module
subgraph roots.

## Input

Read your `_input.md`. It contains:
- Source subgraph and source node files.
- The module names to create.
- Exact assigned node IDs for each module.
- Whether `from_sections` and `link_to_task` were requested.
- Optional decomposition instructions.

Use existing proposal section markers and `component_*` dimensions as boundary
hints. If `from_sections: true`, keep the slice deterministic from the source
proposal's section markers. If the markers are insufficient, still produce a
complete module-scoped proposal and explain the boundary in the proposal.

## Output

Write one `MODULE_NODE` block per requested module to your `_output.md`.

Each block must use this exact delimiter structure:

```text
--- MODULE_NODE_START ---
--- MODULE_NAME_START ---
<module name exactly as given>
--- MODULE_NAME_END ---
--- NODE_YAML_START ---
node_id: <assigned node id for this module>
parents: []
description: "<one-line module root summary>"
proposal_file: br_proposals/<node_id>.md
created_at: "YYYY-MM-DD HH:MM"
reference_files: []
component_<module>: "<module responsibility>"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview
...
<!-- /section: overview -->

<!-- section: components [dimensions: component_*] -->
## Components
...
<!-- /section: components -->
--- PROPOSAL_END ---
--- MODULE_NODE_END ---
```

The orchestrator overwrites `parents`, `created_by_group`, `proposal_file`, and
the module label when applying output. Keep `parents: []` in the YAML.

## Rules

1. Produce exactly one block for every requested module.
2. Use the assigned node IDs verbatim.
3. Keep each proposal scoped to that module while preserving enough umbrella
   context to refine it independently.
4. Preserve relevant dimensions from the source node and add module-specific
   dimensions only when justified.
5. Do not merge modules together or update the umbrella proposal.
