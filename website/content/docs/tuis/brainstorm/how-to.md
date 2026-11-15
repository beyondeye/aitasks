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

### How to Prune Dimensions

Every explore and synthesis carries all of its baseline's dimensions (`requirements_*`, `assumption_*`, `component_*`, `tradeoff_*`) forward and may add more, so the list only grows. **Prune Dimensions** creates a child node that keeps only the dimensions you choose. It runs no agent.

1. On the **Browse** tab, focus the node to prune and press **A** → **Prune Dimensions**.
2. Pick a **mode**:
   - **Keep top N overall:** enter N; the first N dimensions of the ranked list are checked. Changing N re-checks the list.
   - **Keep selected:** check exactly the dimensions to keep. Switching to this mode keeps the current checks as a starting point.
3. Adjust the checklist. It shows every dimension of the node as one list, in ranked order (`1.`, `2.`, …), and you can tick or untick any row in either mode. The line above it shows how many are kept and dropped.
4. Review the confirm step. It lists the kept and the dropped dimensions and a per-kind count, then **Launch**.

**How dimensions are ranked.** All four kinds are ranked together; the kind plays no part. A dimension ranks higher the more proposal sections tag it by its exact key (a `component_*` glob tag counts for none). Ties are broken by how often the key appears in the proposal text, then by whether it is in the session's active dimensions, then by the node's own order. "Top N overall" has no per-kind quota, so a kind can drop out entirely; the confirm step's per-kind count shows when it does.

**What the new node gets.** It is a child of the source node in the same subgraph, and it becomes that subgraph's HEAD (white badge). It carries the kept dimensions, the source's reference files, and the source proposal with the dropped keys removed from its `<!-- section: … [dimensions: …] -->` markers. The proposal prose is kept as it is; a section whose tags were all dropped stays in place, untagged. The source node is not changed; to return to it, set HEAD back to it (see [How to Set HEAD and Finalize](#how-to-set-head-and-finalize)).

Later explores from the pruned node do not get the dropped keys back in their input. An explorer may still add a dimension when its mandate calls for one.

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

The same actions are available from the command line: `ait brainstorm status <task_num>`, `ait brainstorm list`, `ait brainstorm archive <task_num>`, and `ait brainstorm delete <task_num>`.

Deleting cannot be undone. It removes the session's worktree (`.aitask-crews/crew-brainstorm-<task_num>/`, with every node and proposal in it) and its `crew-brainstorm-<task_num>` branch, locally and, when it can, on the remote. The task file and any plan you already finalized into `aiplans/` stay. On the command line, `delete` asks for confirmation; `--yes` skips the question. It does not check for running agents, and pausing the session only stops new ones from starting, so wait until the Running tab shows no agent at work.

### How to Recover a Stuck Apply

When an agent finishes, the studio reads the agent's output file and adds the result to the graph. This step is called *apply*. The studio only applies while it is open, and only to output that is complete: the file must contain all four block markers, `--- NODE_YAML_START ---`, `--- NODE_YAML_END ---`, `--- PROPOSAL_START ---` and `--- PROPOSAL_END ---`. When you reopen a session, it applies the complete output of every explorer and synthesizer that finished in the meantime, and the initializer's output if the first node still shows the imported placeholder.

You need to act yourself when:

- an apply failed and a banner shows the error;
- an agent shows Completed but no new node appeared, or the first node still shows the imported placeholder after the initializer finished. The output is missing a block marker, and the studio skips it without a banner;
- an explorer or synthesizer ended with status Error or Aborted after writing its output, which the studio never applies;
- you want to import the initializer's output again over a first node that already has one.

1. Find the agent's name, such as `explorer_001a`, in the banner or on the Running tab.
2. Get the error. A banner already shows it. For an agent the studio skipped, run the apply yourself (step 4) to see it: the command line prints it as `APPLY_FAILED:<error>`. Some failures also leave a log in `.aitask-crews/crew-brainstorm-<task_num>/`: `<agent>_apply_error.log` for an explorer or synthesizer, `initializer_bootstrap_apply_error.log` for the initializer. Not every failure writes a log, and a log is kept after a later success, so trust the current message over an old log.
3. If the agent's output is at fault, fix it: `<agent>_output.md` in the same directory, or `initializer_bootstrap_output.md` for the initializer.
4. Apply the output again. These routes run the apply even for output the studio skipped:
   - Explorer or synthesizer that ended Completed: press **i** on the agent's group in the Running tab. An open studio also retries a failed apply by itself every few seconds, but never one it skipped.
   - Explorer or synthesizer that ended Error or Aborted: run `ait brainstorm apply-explorer <task_num> <agent_name>` or `ait brainstorm apply-synthesizer <task_num> <agent_name>`. The commands also work for a Completed agent.
   - Initializer (the import of a draft into the first node): press **Ctrl+R** on the Running tab, or run `ait brainstorm apply-initializer <task_num>`.

   The commands print `APPLIED:<node_id>` on success.
5. If you applied from the command line while the studio was open, close and reopen it (`ait brainstorm <task_num>`) to load the new node.

Retrying an explorer or synthesizer is safe, because the apply refuses to create a node that already exists. Retrying the initializer overwrites the first node and its proposal with the initializer's output and discards any change made to them since the import, so copy anything you want to keep before you press **Ctrl+R** or run `apply-initializer`.

### tmux integration

When you run `ait brainstorm` inside tmux, press **j** to open the [TUI switcher]({{< relref "/docs/tuis#navigating-between-tuis" >}}) and jump to another integrated TUI (Monitor, Board, Code Browser, Settings, Syncer, or a running agent window). A typical flow: shape a design here, press `j` to switch to **monitor** and watch the explorer/synthesizer agents run, then come back when they land. A Discuss agent launched into a new tmux window (the default) is listed there too, so `j` also takes you to it.

---

**Next:** [Reference](../reference/) — full keybinding tables, the color legend, and session file layout.
