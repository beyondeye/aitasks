---
title: "Feature Reference"
linkTitle: "Reference"
weight: 20
description: "Keyboard shortcuts, operation legend, and session file layout"
maturity: [stabilizing]
depth: [advanced]
---

### Keyboard Shortcuts

#### Global / Browse tab

| Key | Action | Context |
|-----|--------|---------|
| `q` | Quit the application | Global |
| `b` | Switch to the Browse tab (keeps the current graph/list choice) | Global |
| `s` | Switch to the Session tab | Global |
| `r` | Switch to the Running tab | Global |
| `v` | Toggle the Browse area between graph and list view | Browse |
| `d` | Browse as list view | Global |
| `g` | Browse as graph view | Global |
| `space` | Mark / unmark the focused node | Browse |
| `c` | Open the dimension-comparison matrix over the marked nodes | Browse |
| `Enter` | Open the focused node's detail hub | Browse (focused node) |
| `A` | Open the Operations dialog for the focused node | Browse (focused node) |
| `f` | Toggle the focused module's "deferred" status | Browse |
| `Ctrl+R` | Retry applying the initializer agent output | Running tab |

#### DAG graph view

Shown in the footer when the graph has focus:

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move between graph layers |
| `←` / `→` | Move between columns within a layer |
| `Enter` | Open the focused node |
| `h` | Set the focused node as HEAD |
| `o` | Open the operation that produced the focused node |
| `p` | View the focused node's full proposal |
| `x` | Start a compare against the focused node |
| `Escape` | Cancel an in-progress compare selection |

#### Node detail hub

Opened with `Enter` on a node:

| Key | Action |
|-----|--------|
| `a` | Open the Operations dialog |
| `c` | Compare from this node |
| `v` | Fullscreen proposal view |
| `e` | Export the node's proposal |
| `o` | Open the operation that produced this node |
| `Tab` | Focus the minimap |
| `Escape` | Close |

#### Operations dialog and wizard

The Operations dialog (`A` / `a`) lists the operations; selecting one opens a configuration wizard.

| Key | Action | Context |
|-----|--------|---------|
| `a` | Choose Operations | Operations dialog |
| `c` | Choose Compare | Operations dialog |
| `H` | Show operation help | Operations dialog / wizard |
| `w` | Cycle the preview-pane width | Wizard |
| `l` | Toggle line numbers in the preview | Wizard |
| `Escape` | Close the dialog | Operations dialog / wizard |

#### Operation detail and logs

| Key | Action | Context |
|-----|--------|---------|
| `Escape` / `q` | Close | Operation detail screen |
| `r` | Refresh | Log detail |
| `t` | Show the log tail | Log detail |
| `f` | Show the full log | Log detail |

#### Module preview

Shown by the review-before-apply gate (buttons; `Escape` cancels):

| Action | Effect |
|--------|--------|
| Accept | Apply the proposed modules to the graph |
| Re-run | Supply a steering note and run the decomposition again |
| Cancel | Discard the proposal; graph untouched |

> Every key above can be rebound — press `?` in the TUI for the in-place editor, or use [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).

### Node box anatomy

In graph view each node is a five-row box:

```
┌──────────────────────────┐  ← top border (green = HEAD, orange = anchor)
│ n003  ☑                  │  ← node id + selection checkbox (☑ marked / ☐ not)
│ explore                  │  ← operation badge (color-coded, see below)
│ Variant: cache-first …   │  ← one-line description
└──────────────────────────┘  ← bottom border
```

### Operation color legend

The operation badge is color-coded by the operation that produced the node:

| Color | Operation |
|-------|-----------|
| Cyan | explore |
| Yellow | compare |
| Magenta | synthesize |
| Green | module decompose |
| Orange | module merge |
| Purple | module sync |
| Dim grey | bootstrap (seed / initial node) |

### Module status colors

Module nodes also carry a fluid status badge (a render of progress, separate from the operation that created them):

| Color | Status |
|-------|--------|
| Dim grey | unstarted |
| Cyan | in design |
| Yellow | in implementation |
| Green | implemented |
| Orange | merged |
| Red (italic) | deferred (an overlay marker, set with `f`) |

### Operations and agents

Design operations are launched from the Operations dialog (`A`); each dispatches one or more background agents:

| Operation | What it does | Agent |
|-----------|--------------|-------|
| Explore | Create new design variants from a base node | explorer |
| Compare | Run an agent comparison across the marked nodes | comparator |
| Synthesize | Merge multiple nodes into a synthesis | synthesizer |
| Module Decompose | Fork module subgraph roots from a proposal | module decomposer |
| Module Merge | Merge a module up into an ancestor | module merger |
| Module Sync | Pull a linked module's as-implemented design back in | module syncer |

Session-lifecycle operations (Session tab) run no agents: **pause**, **resume**, **finalize** (export HEAD proposal to `aiplans/`), **archive**, **delete**.

### Agent model defaults

Each design operation dispatches a code agent of a fixed **agent type**, and every agent type has a configurable default **model** and **launch mode**. There are seven agent types: the six design-operation agents in the table above (`explorer`, `comparator`, `synthesizer`, `module decomposer`, `module merger`, `module syncer`) plus the **initializer** — the bootstrap agent that reformats an imported markdown draft (`ait brainstorm init --proposal-file`) into the first graph node.

**Where the defaults live.** Per-type defaults are stored in `aitasks/metadata/codeagent_config.json` under `defaults`, keyed `brainstorm-<type>`:

```json
"defaults": {
  "brainstorm-explorer": "<agent>/<model>",
  "brainstorm-synthesizer": "<agent>/<model>",
  "brainstorm-module_decomposer": "<agent>/<model>"
}
```

Each `brainstorm-<type>` value is an `<agent>/<model>` string — the code-agent binary and the model it runs. An optional paired `brainstorm-<type>-launch-mode` key sets that type's default launch mode.

**Layered resolution.** Defaults resolve in three layers, each overriding the one before it:

1. Built-in resource defaults (per-type `max_parallel` and `launch_mode`).
2. Project config — `codeagent_config.json` (shared, committed).
3. Per-user override — `codeagent_config.local.json` (gitignored).

The agent and model are **bound when a session is initialized** (when the brainstorm crew registers its agent types). Changing a default therefore takes effect on the **next** session you start — not one that is already running.

**Launch mode.** Every type has a default launch mode (`interactive`). Override it globally with the `brainstorm-<type>-launch-mode` config key, or per operation from the launch-mode selector in the operation wizard when you run that operation.

**Changing a default.** The simplest way to edit these is the [Settings]({{< relref "/docs/tuis/settings" >}}) TUI: open the **Agent Defaults** tab, where every brainstorm agent type appears with an agent/model picker and a paired launch-mode picker. Each row shows the **project** value with your **user** override below it, so you can change a model for the whole project or just for yourself.

### Module decompose modes

The Module Decompose wizard offers three modes:

| Mode | Names | Agent? |
|------|-------|--------|
| Manual | You type the module names | Yes (assigns content to your names) |
| Agent-proposed (infer) | Left blank; inferred from the decomposition plan | Yes (proposes the module set) |
| From section markers | Derived from `<!-- section: -->` markers | No (deterministic) |

**Review before apply** is on by default; it routes the result through the module preview (Accept / Re-run / Cancel) before committing. A Re-run steering note overrides the original decomposition plan on conflict, and later revisions override earlier ones. Decompose **forks rather than prunes** — the umbrella proposal stays whole, and **Module Merge** is the convergent path back.

### Operation provenance

| Surface | Where |
|---------|-------|
| "Generated by" block (operation, group, agents, timestamp) | Browse detail pane for the focused node |
| Operation detail screen (`o`) | Overview tab + per-agent Input / Output / Log tabs |

Operation data is resolved on demand from on-disk files via a lightweight pointer (an `OpDataRef`: kind, target, optional section), so the session state never duplicates agent inputs, outputs, or logs.

### Session files and layout

A brainstorm session lives in its own AgentCrew worktree at `.aitask-crews/crew-brainstorm-<task_num>/`, created by `ait crew init` and populated by the brainstorm engine:

| Path | Purpose |
|------|---------|
| `br_session.yaml` | Session metadata and status (`init`, `active`, `completed`, `archived`) |
| `br_graph_state.yaml` | The design DAG: nodes, edges, HEAD, and the module-decomposition maps |
| `br_groups.yaml` | Operation groups — which agents ran, keyed by group, for provenance |
| `br_nodes/` | Per-node metadata |
| `br_proposals/` | Per-node proposal markdown |

A completed (`finalize`) session exports its HEAD proposal into `aiplans/`; `archive` and `delete` retire the worktree.

---

**Next:** [Settings]({{< relref "/docs/tuis/settings" >}}) — configure agent defaults and rebind any of the keys above.
