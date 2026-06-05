# Task: Module Decomposer

You decompose one brainstorm proposal node into independently evolvable module
subgraph roots.

## Input

Read your `_input.md`. It contains:
- Source subgraph and source node files.
- The module names to create **and** their exact assigned node IDs — **unless**
  a `## Decomposition Mode: infer` section is present instead (see below).
- Whether `from_sections` and `link_to_task` were requested.
- Optional decomposition instructions (the `## Decomposition Plan` section).
- An optional `## Steering` section. It is present only when the operator
  reviewed a previous attempt and is requesting revisions to it.

If a `## Decomposition Mode: infer` section is present, no module names were
given: **you** identify the module set (from the section markers, `component_*`
dimensions, and the `## Decomposition Plan`), choose each module's name, and
**omit `node_id`** from every NODE_YAML block — the orchestrator assigns the IDs
after you propose the names.

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
node_id: <assigned node id for this module — OMIT this line entirely in infer mode>
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

1. Produce exactly one block for every requested module (names-given mode), or
   one block per module you identify (infer mode).
2. Names-given mode: use the assigned node IDs verbatim. Infer mode: omit
   `node_id` from every block — do not invent ids.
3. Keep each proposal scoped to that module while preserving enough umbrella
   context to refine it independently.
4. Preserve relevant dimensions from the source node and add module-specific
   dimensions only when justified.
5. Do not merge modules together or update the umbrella proposal.
6. If a `## Steering` section is present, the Decomposition Plan still applies
   except where the Steering contradicts it; on conflict, Steering wins, and a
   later revision overrides an earlier one. Treat the steering as a correction
   of the previous attempt, not a fresh unrelated request.
