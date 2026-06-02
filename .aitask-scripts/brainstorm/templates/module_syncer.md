# Task: Module Syncer

You reconcile a fast-tracked module's brainstorm design with the
*as-implemented* reality of its linked aitask, producing a refreshed module
proposal as a new HEAD for the module subgraph. You are **read-only** on the
linked aitask — you do not edit any task, plan, or source file; you only consume
the provided context.

## Input

Read your `_input.md`. It contains:
- The source subgraph (the module) and its current HEAD node files.
- The exact assigned node ID for the synced node.
- The linked task id and the last sync timestamp (scan horizon).
- A **Sync Sources** bundle with three streams:
  1. **Linked Task Plan** — emphasize its `## Final Implementation Notes` and
     `## Post-Review Changes`; this is what the implementation actually did.
  2. **Scoped Git Diff** — the linked task's commits since the last sync.
  3. **Historical Context** — `aitask_explain_context` output for the touched
     files (related plans/tasks that shaped them).

## Output

You must produce exactly two items using the same delimiters as other
node-creating brainstorm agents.

### File 1: Node Metadata

```text
--- NODE_YAML_START ---
node_id: <assigned node id>
parents: []
description: "<one-line summary of what the sync reconciled>"
proposal_file: br_proposals/<node_id>.md
created_at: "YYYY-MM-DD HH:MM"
reference_files: []
component_<name>: "<refreshed component summary reflecting as-built reality>"
--- NODE_YAML_END ---
```

The orchestrator overwrites `parents` to `[source_head]` (the module's prior
HEAD) and sets the node's subgraph to the module. Keep `parents: []` in your
YAML.

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

1. Update the module proposal to reflect the **as-implemented** design: fold in
   what the Final Implementation Notes / Post-Review Changes and the scoped diff
   actually delivered.
2. Call out explicitly where reality **diverged** from the original module design
   (decisions changed, scope cut, follow-ups deferred) so a later `module_merge`
   absorbs current reality, not the stale design.
3. Preserve module design intent that the implementation did not touch.
4. Do not invent changes beyond what the provided sources support. If a stream is
   empty (e.g. no diff since last sync), say so rather than fabricating drift.
5. This advances only the module's own subgraph HEAD — do not create nodes in any
   other subgraph.
