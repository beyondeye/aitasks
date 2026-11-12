---
title: "/aitask-trail"
linkTitle: "/aitask-trail"
weight: 63
description: "Create, refresh, or show an implementation trail — a durable, wave-structured, evidence-backed task-sequencing artifact"
maturity: [stable]
depth: [advanced]
---

Record which tasks should land next, in what waves, and why — as a stored, versioned artifact rather than a conversation you lose. The skill analyses task and plan state read-only, presents the proposed sequence for review, and writes once after you confirm.

For the end-to-end workflow, including reading a trail in [`ait trails`]({{< relref "/docs/tuis/trails" >}}) or the board's By-Trail view and how a trail feeds a work report, see [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}).

**Usage:**
```
/aitask-trail
/aitask-trail 312
/aitask-trail --topics 312,408
/aitask-trail --refresh art:trail-gate-framework
/aitask-trail --show art:trail-gate-framework
/aitask-trail 312 --deep
```

You do not have to type the command. Asking your coding agent for an implementation trail in plain language — "work out what order these tasks should land in and record it" — reaches the same skill and the same flow, including the confirmation before the single write. The slash form is simply the direct way to reach it, and the only way to pass flags such as `--deep`.

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Modes

The skill has three modes, selected by argument. They are mutually exclusive.

| Mode | Invocation | What it does |
|------|------------|--------------|
| **Create** | bare, `<task_id>`, or `--topics <csv>` | Resolves the scope, gathers state, analyses, reviews with you, then creates the trail |
| **Refresh** | `--refresh <handle>` | Recomputes drift, re-analyses what the drift implicates, shows a diff-style summary, then writes a new version |
| **Show** | `--show <handle>` | Renders a stored trail and reports its freshness. Strictly read-only — no confirmation, no writes |

Create accepts a bare task token in any of the usual forms: `312`, `16_2`, `t312`, or a project-qualified `someproject#312`.

## Arguments

| Argument | Description |
|----------|-------------|
| `<task_id>` | Create a trail scoped to one task; the skill offers the task alone or its canonical topic. |
| `--topics <csv>` | Create a trail spanning several topic roots. |
| `--refresh <handle>` | Re-author an existing trail, producing a new version. |
| `--show <handle>` | Render an existing trail and report whether it has gone stale. |
| `--deep` | Full analysis: adds observations, exclusions, relations, and per-entry evidence. |
| `--lite` | The default. Waves, entries, and narrative only. |

Depth is position-independent — `--deep --refresh <handle>` and `--refresh <handle> --deep` are equivalent. Passing both `--deep` and `--lite` is rejected rather than resolved to a guess. For `--show`, depth does not apply: it reports the depth the stored trail was written at.

Given a bare handle with no mode flag, the skill asks whether you meant show or refresh rather than picking one.

## Step-by-Step (Create)

1. **Resolve scope** — From the argument, or by asking what the trail should cover when invoked bare. Scope is recorded as one task, one topic, several topics, or an ad-hoc selection.
2. **Gather** — Reads task and plan state for the scope: status, priority, effort, dependencies, gates, labels, board column, and plan content. Read-only throughout.
3. **Analyse** — Groups the work into ordered waves, classifies each entry by why it sits where it does, and records the rationale, confidence, and supporting evidence. At `--deep`, also records observations, exclusions, and relations.
4. **Review** — Presents the proposed waves and reasoning. Discoveries outside the requested scope are never folded in silently. At `--deep` they are offered as an explicit scope expansion, which restarts the analysis over the wider scope when you accept it; a lite trail names out-of-scope prerequisite work in its overview instead.
5. **Write once** — On confirmation, stores the trail as a versioned artifact and prints the run summary.

Refresh follows the same shape, beginning from the recorded drift rather than a fresh scope.

### The run summary

Create and refresh end by printing a compact account of the trail that was just written, so a trail authored from your agent can be read without opening the board:

- the authoring depth (`lite`, `deep`, or `unrecorded` for a trail written before depth was recorded), and the trail's prose overview;
- each wave in order as `W<n> · <title>`, with its entries listed in position order by task reference;
- the recorded relations, grouped by type and by whether each is a **fact** read out of the repository or an **advisory** recommendation the trail is making — a distinction that matters, because only some relation types are constrained to one or the other. A lite trail stores no relations at all, and says so rather than showing an empty list, which would read as "these tasks are independent";
- a closing pointer to the [By-Trail view]({{< relref "/docs/tuis/board/reference" >}}#by-trail) and the keys that open it.

`--show` prints the depth, the overview and the board pointer, but not the wave-and-relation recap — it has already rendered the whole document, in full, immediately above.

## Invariants

- **At most one write per run**, and only after explicit confirmation. Show writes nothing at all.
- **Task metadata is never mutated.** `depends`, `priority`, board position, and topic anchors are read, never written.
- **No fabrication.** No time estimates, no progress claims, no delivery commitments. Observations cite evidence, and what was *not* verified is stated.
- **Advisory by construction.** A trail records a recommendation; converting it into real dependencies or board order stays a manual decision.

## Storage

A trail is one structured document, stored as a [versioned artifact]({{< relref "/docs/concepts/artifacts" >}}) under a handle that one task owns: the handle is an entry in that task's `artifacts:` frontmatter (see the [field shape]({{< relref "/docs/development/task-format" >}}#nested-fields-artifacts-and-attachments)). No other task file is written. Which tasks belong to the trail is recorded inside the document, never as a field on the member tasks, so a task can appear in any number of trails without its own file changing.

- **Owner.** A trail scoped to one task or one topic is owned by that task or by the topic's root. A trail spanning several topics, or an ad-hoc set of tasks, has no natural owner, so the skill asks you to choose one; no extra task is created to hold a trail. A new trail's owner must be a live task in this repository: when the default owner is archived, missing or in another project, the skill asks you to choose another.
- **Discovery.** Trails are found by scanning task frontmatter, active and archived. Archiving the owner does not hide a trail: it stays listed and readable, and the view's subtitle reads `owner t<id> archived`. A trail goes stale when the tasks it recorded as inputs change or a related task appears; the owner need not be one of them.
- **Folding the owner.** Folding copies the owner's `artifacts:` entry to the primary task, so the trail keeps an owner. Until the folded task's file is deleted when the primary is archived, two task files point at the same trail. It is still listed once, under the first owner found in this order: an active unfolded task, an active folded task, an archived task.
- **One document, several views.** The By-Trail view, `ait trails` and the summary `/aitask-trail` prints all read that one document. None of them keeps a second copy that could disagree with it.

Versions are immutable, and every earlier version stays retrievable. Manage them with [`ait artifact`]({{< relref "/docs/commands/artifact" >}}) (`ls`, `get`, `versions`, `rm`). Creating a trail writes the owner task's file, so `ait artifact create` refuses while that file has uncommitted changes: commit or revert them first. Refreshing one only rewrites the manifest, so it is unaffected.

Trails are authored and refreshed through this skill, and read in [`ait trails`]({{< relref "/docs/tuis/trails" >}}) or in the board's By-Trail view (`z`).

## Related

- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}) — the end-to-end workflow
- [Implementation trails (concept)]({{< relref "/docs/concepts/implementation-trails" >}}) — the concept: what a trail is and why it is kept
- [Trails TUI]({{< relref "/docs/tuis/trails" >}}) — the stand-alone trail reader, `ait trails`
- [Board reference]({{< relref "/docs/tuis/board/reference" >}}#by-trail) — the By-Trail view and its keys
- [`/aitask-work-report`]({{< relref "/docs/skills/aitask-work-report" >}}) — reporting on a column a trail wave was moved into
- [Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}}) — how topics and trails differ
