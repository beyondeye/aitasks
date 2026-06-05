---
Task: t917_document_agentcrew.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Document agentcrew (`ait crew`) for end users (t917)

## Context

The entire **agentcrew** concept (`ait crew`) is currently undocumented on the
Hugo/Docsy website. It was carved out of t914 (command-reference docs audit) as
a substantial standalone effort. Agentcrew is the multi-agent orchestration
engine of the framework: `init` creates an isolated crew (its own orphan git
branch + worktree under `.aitask-crews/crew-<id>/`); `addwork` registers agents
(workers) with DAG dependencies; the `runner` launches them in topological order
respecting a concurrency cap; `dashboard`/`logview` provide TUIs for monitoring.

Confirmed during exploration: **agentcrew is the engine that powers the
framework's higher-level multi-agent flows** — the brainstorm feature is built
directly on it (`aitask_brainstorm_init.sh` calls `aitask_crew_init.sh`,
`brainstorm_crew.py` shells out to `ait crew addwork`, and the brainstorm
package imports `agentcrew.agentcrew_utils`). The concept page must surface this
"engine under the multi-agent flows" framing.

**Scope (confirmed with user):** two new pages only — a **concept page** and a
**`ait crew` command-reference page** — plus index wiring. No dedicated TUIs
subdirectory and no workflows walkthrough page. Both pages tagged
`maturity: [experimental]`.

## Deliverables

1. **New concept page** — `website/content/docs/concepts/agentcrews.md`
2. **New command-reference page** — `website/content/docs/commands/crew.md`
3. **Wire** `commands/_index.md` (new "Agent Orchestration" category + row)
4. **Wire** `concepts/_index.md` (bullet under "Workflow primitives")

---

## 1. Concept page — `concepts/agentcrews.md`

Follow the existing concept-page shape (see `concepts/execution-profiles.md` as
the model): `## What it is` → `## Why it exists` → `## How to use` → `## See
also` → `---` + `**Next:**` footer.

Frontmatter (match section conventions; `weight` slots it within "Workflow
primitives" — pick a value adjacent to its neighbors, e.g. between
execution-profiles=60 and the next page, read neighbors at edit time):

```yaml
---
title: "Agentcrews"
linkTitle: "Agentcrews"
weight: <slot in Workflow primitives, ~65>
description: "The multi-agent orchestration engine that runs a team of AI agents as a dependency-ordered crew."
depth: [advanced]
maturity: [experimental]
---
```

Content (current-state-only prose; generic placeholder project names; no
"sister" terminology):

- **Experimental note** near the top:
  `> Agentcrews are an evolving feature; the ait crew CLI surface may change.`
- **What it is** — An agentcrew is a team of AI agents (workers) defined,
  launched, and monitored as a coordinated unit. Each crew is **isolated** (its
  own orphan git branch `crew-<id>` + worktree `.aitask-crews/crew-<id>/`);
  each agent has a work description, a status lifecycle
  (Waiting→Ready→Running→Completed/Error/Aborted/Paused), heartbeats, an output
  file, and a command queue. Agents declare **dependencies** that form a DAG;
  the **runner** launches them in topological order up to a concurrency cap.
- **Why it exists** — It is the **engine underneath the framework's multi-agent
  flows**. Higher-level features compose on top of it rather than reinventing
  orchestration; **brainstorm** is built directly on agentcrew (it calls
  `ait crew init`/`addwork`/`cleanup` and reuses the crew runner + YAML I/O).
  Describe the value: parallelism with ordering, inter-agent hand-off
  (downstream agents read upstream outputs), and live observability/intervention
  (pause/kill/resume, dashboard, log tailing).
- **How to use** — The minimal loop: `init` → `addwork` (× N, with `--depends`)
  → `runner` → watch via `dashboard`/`report`/`logview` → `cleanup`. Link to the
  [`ait crew` command reference](../../commands/crew/) for the full subcommand
  surface. Note that most users meet agentcrew indirectly through brainstorm.
- **See also** — links to the command reference, brainstorm docs (if present),
  Locks concept (concurrency), Git branching model (the per-crew orphan branch).
- `**Next:**` footer per section convention.

## 2. Command-reference page — `commands/crew.md`

Follow the multi-subcommand page shape (model: `commands/task-management.md` and
`commands/issue-integration.md`): a short intro, then one `## ait crew <sub>`
section per subcommand, each with a one-line purpose, an example code block, and
an options table (`| Option | Description |`). End with a `**Next:**` footer.

Frontmatter:

```yaml
---
title: "Crew Orchestration"
linkTitle: "Crew"
weight: <slot among command pages, ~50>
description: "ait crew — initialize and run multi-agent crews (init, addwork, runner, dashboard, …)"
depth: [advanced]
maturity: [experimental]
---
```

Intro paragraph: one-line "what is a crew" + pointer to the
[Agentcrews concept page](../../concepts/agentcrews/) for the conceptual model,
+ the experimental caveat note.

Document **all ten subcommands** (the `dashboard` and `logview` TUIs are
documented inline here — no separate TUIs subdirectory, per scope):

| Section | Purpose (from `ait` dispatch help + script `--help`) | Key flags |
|---------|------|-----------|
| `## ait crew init` | Initialize a new crew (orphan branch + worktree + meta/status YAML) | `--id` (req), `--name`, `--add-type <id>:<agent_string>[:<launch_mode>]` (repeatable), `--batch` |
| `## ait crew addwork` | Register an agent in a crew (creates the per-agent coordination files) | `--crew` (req), `--name` (req), `--work2do <file\|->` (req), `--type` (req), `--depends a,b`, `--group`, `--launch-mode`, `--batch` |
| `## ait crew setmode` | Change `launch_mode` of a **Waiting** agent | `--crew`, `--name`, `--mode headless\|interactive\|openshell_headless\|openshell_interactive` |
| `## ait crew status` | Get/set/list agent & crew status, send heartbeats | `--crew` (req), `--agent`, verbs `get\|set\|list\|heartbeat` |
| `## ait crew command` | Queue commands to agents | verbs `send\|send-all\|send-group\|list\|ack`; `--crew`, `--agent`/`--group`, `--command kill\|pause\|resume\|update_instructions\|reset`, `--sent-by` |
| `## ait crew runner` | Start/check the orchestrator that launches agents in DAG order | `--crew` (req), `--interval`, `--max-concurrent`, `--once`, `--dry-run`, `--check`, `--force` |
| `## ait crew report` | Report crew summary / agent detail / aggregated outputs | verbs `summary\|detail\|output\|list`; `--batch` |
| `## ait crew cleanup` | Remove completed crew worktrees/branches (terminal states only) | `--crew` or `--all-completed`, `--delete-branch`, `--batch` |
| `## ait crew dashboard` | TUI for monitoring/managing crews (Textual) | (no args) |
| `## ait crew logview` | ANSI-aware agent-log viewer TUI (live tail or snapshot) | `--path <file>` or `<crew_id> <agent_name>`, `--no-tail` |

For each: verify the exact flag names/help against the script's `--help` /
usage string at authoring time (do not transcribe from memory — re-run e.g.
`./ait crew init --help`). Keep examples using generic placeholder names
(e.g. `--id sprint1`, agents `planner`/`coder`/`reviewer`).

Optionally add a short `## On-disk layout` subsection showing the
`.aitask-crews/crew-<id>/` directory shape (crew meta/status YAML + the
per-agent files), since it grounds the `addwork`/`report` sections — keep it
brief and current-state.

## 3. Wire `commands/_index.md`

Add a new category section (cleanest home for a 10-subcommand orchestration
command). Place it after **Cross-repo** / before **Reporting**:

```markdown
### Agent Orchestration

| Command | Description |
|---------|-------------|
| [`ait crew`](crew/) | Initialize and run multi-agent crews — `init`, `addwork`, `setmode`, `status`, `command`, `runner`, `report`, `cleanup`, `dashboard`, `logview` (see [Agentcrews](../concepts/agentcrews/)) |
```

Optionally add one `ait crew init …` line to the page's `## Usage Examples`
block.

## 4. Wire `concepts/_index.md`

Add a bullet under **## Workflow primitives** (agentcrew is an orchestration
primitive that shapes how multiple agents behave):

```markdown
- **[Agentcrews]({{< relref "/docs/concepts/agentcrews" >}})** — The multi-agent orchestration engine that runs a team of agents as a dependency-ordered crew; the foundation under flows like brainstorm.
```

---

## Conventions to honor

- **Current-state-only** prose — no version history / changelog narration in
  page bodies (`aidocs/framework/documentation_conventions.md`).
- **Generic placeholder** project/agent names — never the author's real repos.
- **No "sister"** repo terminology.
- `maturity: [experimental]` on both new pages + the evolving-feature note.
- Source of truth is the `ait crew` dispatch in `ait` and the
  `aitask_crew_*.sh` scripts — verify flag/help wording against them, not memory.

## Verification

1. `cd website && hugo build --gc --minify` — must build with no errors
   (broken `relref`/`relref`-style links fail the build).
2. Grep the new pages for accurate command names against `ait`:
   `grep -n 'init)\|addwork)\|setmode)\|status)\|command)\|runner)\|report)\|cleanup)\|dashboard)\|logview)' ait` — confirm the ten subcommands match.
3. Spot-check each subcommand's flags by running `./ait crew <sub> --help` and
   diffing against the page's options table.
4. Visual check (optional): `cd website && ./serve.sh`, browse to
   `/docs/concepts/agentcrews/` and `/docs/commands/crew/`, confirm both appear
   in the sidebar under the right sections and the index links resolve.
5. Confirm both new pages render under their sections and the two `_index.md`
   edits show the new entries.

See **Step 9 (Post-Implementation)** of the task-workflow for cleanup, archival,
and (since we work on the current branch) the commit/merge steps.

## Risk

### Code-health risk: low
- Documentation-only change: two new Markdown pages plus two hand-curated index
  edits. No code, scripts, or templates touched; zero runtime blast radius. The
  only failure mode is a broken Hugo build from a malformed `relref`/link, caught
  by the verification build. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Minor accuracy risk: the documented `ait crew` flags/help could drift from the
  scripts if transcribed from the exploration summary rather than re-verified.
  Mitigated in-plan by the requirement to re-check each subcommand against
  `./ait crew <sub> --help` at authoring time (verification steps 2–3).
  · severity: low · → mitigation: none

No mitigations needed (documentation task, both axes low).

## Final Implementation Notes

- **Actual work done:** Created the two planned pages and wired both indexes,
  exactly as scoped.
  - `website/content/docs/concepts/agentcrews.md` — concept page (what it is /
    why it exists / how to use / see-also), `maturity: [experimental]`,
    `weight: 75` (Workflow primitives). Surfaces the "engine under multi-agent
    flows; brainstorm built on it" framing the user asked for.
  - `website/content/docs/commands/crew.md` — full `ait crew` reference for all
    ten subcommands with examples + options tables, an `## On-disk layout`
    section, and the `dashboard`/`logview` TUIs documented inline (no separate
    TUIs subdirectory, per scope). `maturity: [experimental]`, `weight: 50`.
  - `commands/_index.md` — new "Agent Orchestration" category + `ait crew` row,
    plus one `ait crew init` usage-example line.
  - `concepts/_index.md` — bullet under "Workflow primitives".
- **Deviations from plan:** None of substance. Every flag/option was re-verified
  against live `./ait crew <sub> --help` and the Python argparse rather than the
  exploration summary — this corrected one detail: the exploration report listed
  `reset` as a valid `ait crew command` value, but the actual valid set is
  `kill, pause, resume, update_instructions`. Documented the verified set. Also
  documented runner's `--reset-errors` flag (present in argparse, absent from the
  thin `--help`).
- **Issues encountered:** None. `hugo build --gc --minify` succeeded (exit 0);
  only pre-existing `.Language.LanguageDirection` / `.Site.AllPages` deprecation
  warnings, unrelated to this change.
- **Key decisions:** Placed `ait crew` in its own new "Agent Orchestration"
  command-reference category (cleanest home for a 10-subcommand command);
  documented the two crew TUIs inline in the command page instead of creating a
  `tuis/crew-dashboard/` subdirectory, per the user's explicit scope.
- **Upstream defects identified:** None.
