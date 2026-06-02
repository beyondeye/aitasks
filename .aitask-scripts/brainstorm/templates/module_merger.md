# Task: Module Merger

You merge a refined module proposal upward into an ancestor destination
subgraph proposal.

## Input

Read your `_input.md`. It contains:
- Source subgraph and source HEAD node files.
- Destination subgraph and destination HEAD node files.
- The exact assigned node ID for the merged destination node.
- Merge-up rules from the user.

## Output

You must produce exactly two items using the same delimiters as other
node-creating brainstorm agents.

### File 1: Node Metadata

```text
--- NODE_YAML_START ---
node_id: <assigned node id>
parents: []
description: "<one-line summary of the module merge>"
proposal_file: br_proposals/<node_id>.md
created_at: "YYYY-MM-DD HH:MM"
reference_files: []
component_<name>: "<merged component summary>"
--- NODE_YAML_END ---
```

The orchestrator overwrites `parents` to `[destination_head, source_head]` and
sets the node's subgraph to the destination. Keep `parents: []` in your YAML.

### File 2: Proposal

```text
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview
...
<!-- /section: overview -->
--- PROPOSAL_END ---
```

## Rules

1. Absorb the source module's refined design into the destination proposal.
2. Preserve destination context that is outside the source module unless the
   merge-up rules explicitly change it.
3. Document conflicts or discarded source details inside the proposal.
4. Do not create a new source-module node; this operation advances only the
   destination subgraph.
