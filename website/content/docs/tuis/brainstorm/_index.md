---
title: "Brainstorm"
linkTitle: "Brainstorm"
weight: 25
description: "TUI for graph-structured design exploration that finalizes into an implementation plan"
maturity: [stabilizing]
depth: [intermediate]
---

The `ait brainstorm` command launches an interactive terminal-based design studio for working out *how* to build something before you commit to a plan. Built with [Textual](https://textual.textualize.io/), it represents a design space as a **directed acyclic graph (DAG)** of proposal nodes: you start from a seed proposal, branch it into variants, compare and synthesize them, optionally split it into independently-evolvable modules, and finally export the chosen node as an implementation proposal into `aiplans/`.

Each operation is carried out by one or more background agents, so the TUI is also a live monitor of that agent work, with full provenance: every node records which operation and which agents produced it.

<!-- SCREENSHOT: Brainstorm Browse tab showing the DAG of proposal nodes with the detail pane on the right -->

> **Customizable keys:** every shortcut here can be rebound. Press `?` in this
> TUI for the in-place editor, or open
> [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).

## Tutorial

### Launching

A brainstorm session is tied to a task. Launch the studio directly:

```bash
ait brainstorm <task_num>
```

If the session does not exist yet, the TUI prompts you to initialize it on the spot — so launching is all you normally need. From the [Kanban board]({{< relref "/docs/tuis/board" >}}) you can do the same without typing a command: focus a task card and press **b** (or use the **Brainstorm** button in the task detail dialog) to open a launch dialog for `ait brainstorm <task_num>`. If a brainstorm window for that task is already running in tmux, the board switches to it instead of starting a second one.

To initialize a session explicitly from the command line — for example to seed it from an existing markdown draft rather than a blank node — use the `init` subcommand. The `--proposal-file` option hands the draft to an initializer agent that reformats it into the first graph node:

```bash
ait brainstorm init <task_num>
ait brainstorm init <task_num> --proposal-file path/to/draft.md
```

Related subcommands manage sessions without opening the TUI:

- `ait brainstorm status <task_num>` — show session details
- `ait brainstorm list` — list all brainstorm sessions
- `ait brainstorm archive <task_num>` — finalize and archive a session

All TUIs require the shared Python virtual environment installed by [`ait setup`]({{< relref "/docs/commands/setup-install" >}}) (packages `textual` and `pyyaml`).

### Understanding the Layout

The studio is organized into three tabs, switched with single keys:

1. **Browse** (`b`) — the main workspace. The left/center area shows the design DAG, and a **detail pane** on the right shows context for the focused node: session status, module status, your marked-node set, and the focused node's title and content.

   The Browse area has two interchangeable views of the same graph, toggled with `v`:
   - **Graph view** — the DAG drawn as connected node boxes (the default).
   - **List view** — a flat, scrollable list of node rows.

   `d` jumps straight to the list view and `g` to the graph view if you prefer dedicated keys over toggling.

2. **Session** (`s`) — session-lifecycle actions presented as rows: pause, resume, finalize, archive, and delete.

3. **Running** (`r`) — a live monitor of the background agent groups spawned by your operations, with per-agent status and log rows.

A runtime strip above the tabs always shows the runner state and how many operations are currently in flight.

### The DAG view

In graph view each proposal is drawn as a **five-row node box**: a top border, a title row (with a selection checkbox), an **operation badge**, a one-line description, and a bottom border. The badge is color-coded by the operation that produced the node:

- **Cyan** — explore
- **Yellow** — compare
- **Magenta** — synthesize
- **Green** — module decompose
- **Orange** — module merge
- **Purple** — module sync
- **Dim grey** — bootstrap (the seed/initial node)

The HEAD node (the current design tip) is drawn with a green border; the anchor node carries an orange border.

Navigation in the graph is arrow-key driven, with the available keys shown in the footer:

- **↑ / ↓** — move between graph layers
- **← / →** — move between columns within a layer
- **Enter** — open the focused node's full detail
- **h** — set the focused node as HEAD
- **o** — open the operation that produced the focused node (see [Operation provenance](#operation-provenance))
- **p** — view the focused node's full proposal text
- **x** — start a compare against the focused node

Press **space** on a node (in either view) to **mark** it; marked nodes show a filled checkbox and feed multi-node operations like compare and synthesize. Press **c** to open a dimension-comparison matrix over the marked set.

### Operations

Press **A** on a focused node to open the **Operations** dialog, which launches a configuration wizard for the chosen operation. Each operation dispatches one or more background agents and adds the result back into the graph:

| Operation | What it does | Agent |
|-----------|--------------|-------|
| **Explore** | Create new design variants branching from a base node | explorer |
| **Compare** | Run an agent comparison across the marked nodes | comparator |
| **Synthesize** | Merge multiple nodes into a single synthesized proposal | synthesizer |
| **Module Decompose** | Fork module subgraph roots out of a proposal (see below) | module decomposer |
| **Module Merge** | Merge a module back up into an ancestor | module merger |
| **Module Sync** | Pull a linked module's as-implemented design back into the graph | module syncer |

Background work runs asynchronously — start an operation, keep working, and watch it land on the **Running** tab. When it completes, its output node appears in the graph.

### Module decompose

Module decompose splits a large umbrella proposal into smaller, independently-evolvable module subgraphs. When you configure it (via `A` → Module Decompose) you pick one of three **modes**:

- **Manual — I type the names** — you supply the module names directly.
- **Agent-proposed — infer from the Plan** — leave the names blank and write a free-text decomposition plan; the agent proposes the module set itself.
- **From section markers** — derive modules deterministically from the proposal's `<!-- section: -->` markers (no agent).

**Review before apply** is on by default. With it enabled, the proposed decomposition does not commit straight to the graph: it opens in a preview where you can **Accept** it, **Re-run** it with a free-text steering note, or **Cancel**. A steering note refines the previous attempt — it overrides the original decomposition plan wherever they conflict, and later revisions win over earlier ones. Turning the checkbox off restores immediate auto-apply.

Decompose **forks rather than prunes**: it copies a module-scoped slice into a new, independently-evolvable subgraph, but the umbrella proposal stays whole. When you want a module's evolved design to flow back, **Module Merge** is the convergent path. A **fast-track** preset combines a single-module decompose with a "create linked child tasks" step, so you can split one module off to implementation while the rest of the design keeps evolving.

### Operation provenance

Every node knows how it was made. The detail pane shows a **Generated by** block naming the operation, the agent group, the agents involved, and when it ran.

For the full record, focus a node and press **o** to open the **Operation** screen. It has an **Overview** tab plus, for each agent in the operation, a set of **Input / Output / Log** tabs — so you can see exactly what each agent was given, what it produced, and how it ran. Under the hood these are resolved on demand from on-disk operation data (the `OpDataRef` pointer primitive), not duplicated into the session state.

### Session lifecycle

The **Session** tab (`s`) exposes the lifecycle actions:

- **Pause** / **Resume** — stop and restart the session's agent activity.
- **Finalize** — export the HEAD proposal to `aiplans/` and mark the session completed. This is how a brainstorm becomes an implementation plan.
- **Archive** — mark a completed session as archived.
- **Delete** — permanently remove the session, its worktree, and its branch.

---

**Next:** [How-To Guides](how-to/) — step-by-step recipes for exploring, comparing, decomposing, and finalizing. Or jump to the [Reference](reference/) for full keybinding tables, the color legend, and session file layout.
