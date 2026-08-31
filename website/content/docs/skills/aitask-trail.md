---
title: "/aitask-trail"
linkTitle: "/aitask-trail"
weight: 63
description: "Create, refresh, or show an implementation trail — a durable, wave-structured, evidence-backed task-sequencing artifact"
maturity: [stable]
depth: [advanced]
---

Record which tasks should land next, in what waves, and why — as a stored, versioned artifact rather than a conversation you lose. The skill analyses task and plan state read-only, presents the proposed sequence for review, and writes once after you confirm.

For the end-to-end workflow, including the board's By-Trail view and how a trail feeds a work report, see [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}).

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
4. **Review** — Presents the proposed waves and reasoning. Discoveries outside the requested scope are offered as an explicit scope expansion; they are never folded in silently.
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

Trails are stored through the artifact substrate, owned by a task and versioned immutably — every earlier version stays retrievable. Manage them with [`ait artifact`]({{< relref "/docs/commands/task-management" >}}) (`ls`, `get`, `versions`, `rm`).

There is no `ait trail` command: trails are reached through this skill and through the board's By-Trail view.

## Related

- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}) — the end-to-end workflow
- [Board reference]({{< relref "/docs/tuis/board/reference" >}}#by-trail) — the By-Trail view and its keys
- [`/aitask-work-report`]({{< relref "/docs/skills/aitask-work-report" >}}) — reporting on a column a trail wave was moved into
- [Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}}) — how topics and trails differ
