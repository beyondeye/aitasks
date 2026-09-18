---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Step-by-step guides for common brainstorm operations"
maturity: [stabilizing]
depth: [intermediate]
---

These guides assume you have a brainstorm session open (`ait brainstorm <task_num>`). Design operations run background agents; watch their progress on the **Running** tab (`r`) and return to **Browse** (`b`) when a result lands. **Discuss** is the exception: it opens an interactive agent you talk to directly, and it produces no result on the graph.

### How to Start a Brainstorm Session

You can start from a blank seed or from an existing draft.

**From scratch:**

1. Run `ait brainstorm <task_num>`.
2. If no session exists yet, the TUI prompts you to initialize one — confirm, and a seed (`bootstrap`) node is created.

**From an existing markdown draft:**

1. Run `ait brainstorm init <task_num> --proposal-file path/to/draft.md`.
2. An initializer agent reformats the draft into the first graph node. Watch it on the Running tab; if it needs re-applying, press **Ctrl+R** on the Running tab.
3. Run `ait brainstorm <task_num>` to open the studio.

**From the board:**

1. In `ait board`, focus the task card.
2. Press **b** (or open the task detail dialog and click **Brainstorm**).
3. Choose **Run** or **Run in tmux**. If a `brainstorm-<num>` window already exists, the board switches to it instead of starting a second session.

### How to Explore Design Variants

1. On the **Browse** tab, focus the node you want to branch from (arrow keys in graph view).
2. Press **A** to open the Operations dialog and choose **Explore**.
3. In the wizard, set how many parallel explorers to run and any guidance, then launch.
4. Each explorer produces a new variant node branching from the base. They appear in the graph (cyan badge) as the agents complete.

### How to Compare and Synthesize Nodes

**Compare** runs an agent that contrasts a set of nodes; **Synthesize** merges them into one proposal.

1. Mark the nodes you want to work with: focus each and press **space** (a filled checkbox appears). Your marked set is shown in the Browse detail pane.
2. Press **A** → **Compare** to run an agent comparison across the marked nodes (yellow badge result), or **A** → **Synthesize** to merge them into a single synthesized proposal (magenta badge result).
3. For a quick side-by-side without spawning an agent, press **c** to open the dimension-comparison matrix over the marked set.

### How to Discuss Proposals with an Agent

**Discuss** opens an interactive code agent to talk one or more proposals over with: compare them, explain one, answer your questions, or check a design for flaws. The agent is **advisory-only**. It reads the proposals and never changes the session.

> **Availability:** Discuss is in the Operations dialog, so it needs the same session state as every other operation. The session must not be read-only, and its status must be initializing or active. In a read-only, paused or finalized session, `A` shows a warning and opens no dialog. Resume a paused session first (see [How to Manage Sessions](#how-to-manage-sessions)).

1. **Choose the proposals.** Focus a single node, or mark several with **space**. Discuss uses the marked set when there is one, and otherwise the focused node. Any node works, including the root.
2. Press **A** and choose **Discuss**, the last row. Press **H** on the row for its help. Discuss skips the wizard.
3. **Launch the agent.** The agent-launch dialog opens with the default agent and model for the `discuss` operation. Change the agent/model, the profile or the command if you want. Then either:
   - **Run in tmux.** By default this opens a new window named `agent-discuss-<task_num>`. If minimonitor auto-spawn is enabled (`tmux.minimonitor.auto_spawn` in `project_config.yaml`, on by default), a minimonitor pane opens beside it. You can instead pick an existing window in the **Window** field. The agent then opens as a split pane in that window, in the direction set by the **Split** toggle (horizontal or vertical), and no minimonitor is added; or
   - **Run in terminal.** This opens a new terminal. With no terminal emulator available, it runs in place while the TUI is suspended.
4. **Read the opening.** The agent does no analysis up front. It shows what it is discussing and a menu, then waits:
   - **One proposal:** it names the node and its title in one sentence. There is no list and no handles.
   - **Two or more:** it lists them with handles `A`, `B`, `C`, … (in the order they were passed), each with its node id and a short title. A node whose proposal file is missing appears as `(proposal not found)` and is left out of later requests.
5. **Ask.** Plain language always works ("compare them", "what could go wrong with B?"). Shortcodes are a faster way to say the same thing:

   | Shortcode | Asks for |
   |-----------|----------|
   | `>c` | Compare the proposals in simple words |
   | `>cd` | Compare them in depth, dimension by dimension |
   | `>e` | Explain one proposal in simple words, fully |
   | `>q` | Answer a question from the proposals |
   | `>f` | Check a proposal for structural design flaws and risks |
   | `>h` | How a proposal evolved from its ancestors |
   | `>?` | Show the menu again |

   The `>` is required, because a bare `c` is ordinary text. Name the targets by handle or by node id: `>e B`, `>cd A C, focus on cost`. With no target, the request applies to every listed proposal, or the agent asks which one you mean.

The agent never edits a proposal or node file and never runs a command that changes the session, so Discuss adds nothing to the graph. To act on what you learn, run **Explore** or **Synthesize** yourself. For the skill behind the agent, see [`/aitask-brainstorm-discuss`]({{< relref "/docs/skills/aitask-brainstorm-discuss" >}}).

### How to Decompose a Proposal into Modules

Module decompose forks a large proposal into smaller, independently-evolvable module subgraphs.

1. Focus the umbrella node and press **A** → **Module Decompose**.
2. Pick a **mode**:
   - **Manual — I type the names:** enter the module names yourself.
   - **Agent-proposed — infer from the Plan:** leave the names blank and write a free-text decomposition plan; the agent proposes the module set.
   - **From section markers:** derive modules from the proposal's `<!-- section: -->` markers (deterministic, no agent).
3. Leave **Review before apply** checked (the default) to inspect the result before it commits.
4. Launch. The decomposed module nodes are added as new subgraph roots (green badge). The umbrella proposal is left whole — decompose **forks, it does not prune**.

> To split a single module off to implementation while the rest of the design keeps evolving, use the **fast-track** preset, which pairs a single-module decompose with a "create linked child tasks" step.

### How to Review and Steer a Module Decomposition

When **Review before apply** is on, the proposed decomposition opens in a preview before anything commits to the graph:

- **Accept** — apply the proposed modules to the graph.
- **Re-run** — supply a free-text steering note and run again. The note refines the previous attempt: it **overrides** the original decomposition plan wherever they conflict, and across multiple re-runs the later revision wins.
- **Cancel** — discard the proposal; the graph is untouched.

Turn the checkbox off to skip the preview and auto-apply immediately.

### How to Bring a Module's Design Back

Because decompose forks rather than prunes, a module's evolved design has to be merged back deliberately:

- **Module Merge** (`A` → Module Merge) merges a module up into an ancestor node (orange badge).
- **Module Sync** (`A` → Module Sync) pulls a linked module's *as-implemented* design back into the graph (purple badge) — useful once a fast-tracked module has been built.

### How to Inspect Operation Provenance

Every node records how it was produced.

1. Focus a node. The Browse detail pane shows a **Generated by** block (operation, agent group, agents, timestamp).
2. Press **o** to open the **Operation** screen for that node.
3. The **Overview** tab summarizes the operation; each agent in the operation has its own **Input / Output / Log** tabs so you can see exactly what it was given, what it returned, and how it ran.

### How to Set HEAD and Finalize

**HEAD** marks the current design tip — the node that finalize exports.

1. Navigate to the node you want as the chosen design and press **h** to set it as HEAD (its box border turns green).
2. Switch to the **Session** tab (`s`).
3. Choose **Finalize**. The HEAD proposal is exported to `aiplans/` and the session is marked completed — this is how a brainstorm becomes an implementation plan.

### How to Manage Sessions

The **Session** tab (`s`) exposes lifecycle actions:

- **Pause** / **Resume** — stop and restart the session's agent activity.
- **Archive** — mark a completed session as archived.
- **Delete** — permanently remove the session, its worktree, and its branch.

The same actions are available from the command line: `ait brainstorm status <task_num>`, `ait brainstorm list`, and `ait brainstorm archive <task_num>`.

### tmux integration

When you run `ait brainstorm` inside tmux, press **j** to open the [TUI switcher]({{< relref "/docs/tuis#navigating-between-tuis" >}}) and jump to another integrated TUI (Monitor, Board, Code Browser, Settings, Syncer, or a running agent window). A typical flow: shape a design here, press `j` to switch to **monitor** and watch the explorer/synthesizer agents run, then come back when they land. A Discuss agent launched into a new tmux window (the default) is listed there too, so `j` also takes you to it.

---

**Next:** [Reference](../reference/) — full keybinding tables, the color legend, and session file layout.
