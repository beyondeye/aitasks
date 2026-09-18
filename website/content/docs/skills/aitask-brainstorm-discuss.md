---
title: "/aitask-brainstorm-discuss"
linkTitle: "/aitask-brainstorm-discuss"
weight: 110
description: "Discuss brainstorm proposals with an advisory agent — compare, explain, question, and check a design for flaws and risks"
maturity: [stabilizing]
depth: [intermediate]
---

An interactive companion for the proposals of one or more nodes in an [`ait brainstorm`]({{< relref "/docs/tuis/brainstorm" >}}) session. It compares them in simple words or in depth, explains one plainly but fully, answers your questions, checks a design for structural flaws and risks, and traces how a proposal evolved. It is **advisory-only**: it reads the session and never changes it.

**Usage:**
```
/aitask-brainstorm-discuss <task_num> <node_id> [<node_id>...]
```

- `<task_num>` — the brainstormed task (`N` or `N_M`). It identifies the session.
- `<node_id>...` — at least one node whose proposal to discuss, e.g. `n001_explorer_001a`. If either argument is missing, the agent asks for it before doing anything else.

You normally do not type this. The brainstorm TUI's **Discuss** operation (`A` → Discuss) builds the command from the focused node or the marked set and launches the agent for you. That operation needs a session that is not read-only and is initializing or active. See [How to Discuss Proposals with an Agent]({{< relref "/docs/tuis/brainstorm/how-to#how-to-discuss-proposals-with-an-agent" >}}).

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

1. **Resolve the paths:** one read-only helper call maps the task number and node ids to the session, each node's proposal and metadata files, and the task file. A missing session or a malformed id stops here with a message.
2. **Skim for titles:** the agent reads only the start of each proposal, enough for a short title. It does not analyse anything yet.
3. **Show what is being discussed.** This depends on the number of proposals:
   - **One:** a single sentence naming the node and its title, with no list and no handles.
   - **Two or more:** a list of handles `A`, `B`, `C`, … in argument order, each with its node id and title.

   A node whose proposal file cannot be found is shown as `(proposal not found)` and left out of every later request. The agent carries on with the others.
4. **Show the menu and wait.** The menu lists the capabilities below, each led by its shortcode.

## Capabilities

| Shortcode | Capability |
|-----------|------------|
| `>c` | **Compare in simple words** — the differences that matter, and which to pick |
| `>cd` | **Compare in depth** — side by side, dimension by dimension |
| `>e` | **Explain a proposal** in simple words, fully |
| `>q` | **Ask anything**. Each part of the answer names the proposal it came from, and the agent says so when the proposals do not cover the question |
| `>f` | **Check for structural design flaws and risks**: what could go wrong, and what the design assumes |
| `>h` | **How a proposal evolved**: what each ancestor step added, dropped or changed, with a synthesis node's contributing branches kept separate |
| `>?` | **Reprint the menu** |

Shortcode rules:

- **Plain language works too.** A shortcode is a shorter way to ask for the same thing and changes nothing else.
- **The `>` is required.** A message of just `c` is ordinary text, not a comparison request.
- **Codes work anywhere in a message you mean as a request**, as in `>cd A C, focus on cost`. A code you only mention, such as "what does `>f` do?", gets an answer in words and runs nothing.
- **Operands** are handles (`>e B`) or node ids (`>e n002_explorer_001b`). With no operand, the capability applies to every listed proposal where that makes sense, or the agent asks which one you mean. If an operand is the handle of one proposal and the node id of another, the agent asks which you meant.
- **An unrecognised code** gets a one-line notice and the menu again. The agent never guesses a neighbouring code.

## Context on demand

Beyond the proposals themselves, the agent fetches extra context only when a request needs it:

- **Node metadata:** the node's description, parents and dimension fields, for a detailed comparison or a flaw that depends on a declared assumption or trade-off.
- **The brainstormed task:** what the brainstorm is trying to achieve, when a request asks whether a proposal meets the goal.
- **Lineage:** the node's ancestors across modules, for `>h`.

When something cannot be fetched, the agent says so and answers with what it has.

## Advisory-only contract

The agent never creates, edits, moves or deletes a proposal file, node YAML or any other session state. It never runs a command that changes the session, even to apply a change it suggested. Its only commands are the read-only context helper and file reads. Every decision stays with you. To act on an insight, use the brainstorm operations yourself, such as **Explore** or **Synthesize**.

## Profiles

The skill is profile-aware, and its key in `default_profiles` is `brainstorm-discuss`:

```yaml
default_profiles:
  brainstorm-discuss: fast
```

Put this in `userconfig.yaml` (personal) or `project_config.yaml` (team). You can also pass `--profile <name>` for one run, or choose a profile in the TUI's launch dialog. For how the layers combine, see [Resolution Order]({{< relref "/docs/skills/aitask-pick/execution-profiles#resolution-order" >}}).

## Related

- [Brainstorm how-to]({{< relref "/docs/tuis/brainstorm/how-to#how-to-discuss-proposals-with-an-agent" >}}): launching Discuss from the TUI
- [Brainstorm reference]({{< relref "/docs/tuis/brainstorm/reference#operations-and-agents" >}}): how Discuss differs from the design operations
- [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}): the `discuss` operation and its default agent/model
