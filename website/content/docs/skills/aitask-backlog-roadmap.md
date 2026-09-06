---
title: "/aitask-backlog-roadmap"
linkTitle: "/aitask-backlog-roadmap"
weight: 64
description: "Rank the background-work backlog into a conflict-aware implementation trail"
maturity: [experimental]
depth: [advanced]
---

Rank the background-work backlog into a durable, conflict-aware
[implementation trail]({{< relref "/docs/skills/aitask-trail" >}}) — an advisory
estimate of what is worth picking up alongside work already in flight.

Most auto-spawned follow-up work is never picked proactively, so it accumulates
until the backlog itself is the obstacle to choosing what to do next. This skill
produces a ranked, two-lane ordering of that work and publishes it as a
versioned artifact, so the board's By-Trail view, drift detection and versioning
all apply to it unchanged.

**Usage:**

```bash
/aitask-backlog-roadmap            # rescan the corpus and publish a new version
/aitask-backlog-roadmap --show     # render the current version, write nothing
```

## The corpus

Ready tasks carrying a `followup_kind`, plus Ready genuine work at
`effort: low` — parent tasks only. Child tasks are usually gated by their
siblings, so ranking them as independently startable background work would
mislead.

This is deliberately not the whole Ready backlog, which would compete with
[`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}).

Only the top N by the ranking below are published. The corpus size, the cap and
the selection rule are recorded in the trail's own method note, so a published
roadmap describes its own scope.

## How the ranking works

Ordering is a lexicographic tuple, not a weighted sum:

- **Origin risk is the primary value signal** — the `risk_code_health` and
  `risk_goal_achievement` of the task or its origin, combined so that neither
  axis is privileged over the other.
- **In-flight area affinity is a strong but advisory boost.** It sits *below*
  risk in the tuple, which is what makes "relevant improvements surface while an
  area is active, without burying urgent unrelated work" a structural property
  rather than a matter of tuning.
- **Freshness carries two independent weights** — how recently the follow-up was
  spawned, and whether the premise it was written against still holds. An
  old-but-valid task is not punished like a recently invalidated one.
- **`priority` is a weak tie-break only**; on auto-spawned work it is usually a
  seam default rather than a judgement. **`effort`** is a scheduling constraint
  and is absent from the ordering entirely.
- **`followup_kind` is not ordering-relevant** and is never read by the scorer.

Every score component appears in each entry's rationale, so the ranking can be
understood and overridden.

## The lanes

The lanes are the parallel-admission checker's verdicts; nothing re-derives a
collision.

| Lane | Meaning |
|------|---------|
| Parallel-safe | No known conflict at check time |
| Coordination | Shares a file surface with work in flight — fold into it, or queue immediately after |
| Unresolvable | The check could not be completed; the cause is named per entry |

"Unresolvable" gets its own lane rather than joining coordination, because
"cannot tell" is not "conflicts with". What it is never treated as is safe.

**A lane can legitimately be empty, including the parallel-safe one.** The lane
is not part of the ordering, so a capped run may publish no safe entry at all.
The run summary always reports every lane's count, including zero.

## What the output is, and is not

The roadmap is an **estimate**, built from origin evidence and in-flight state as
of the run. It **reserves nothing**.

- A parallel-safe entry means **"no known conflict at check time"** — never
  "safe to run in parallel". Overlapping work can begin the instant after the
  check passes.
- `/aitask-pick` runs the live parallel-admission preflight before
  implementation. That check, not this roadmap, is what makes the safety
  decision — and it too is a snapshot that reserves nothing, so a residual race
  remains open after it passes.

## Freshness has two limits

A `CURRENT` drift verdict on this trail is narrower than it looks, and both
limits matter:

1. **It speaks only for the published members.** Their recorded inputs have not
   changed. It says nothing about a candidate *outside* the trail that has since
   gained risk or become unblocked and might now belong in it.
2. **It covers task-record inputs only.** The lanes were scored from in-flight
   evidence, which is excluded from every trail digest by construction — locks
   and in-flight status change minute to minute, and admitting them would make
   every trail permanently stale. So a published member can acquire in-flight
   work, invalidating its lane, while drift still reports `CURRENT`.

Re-running this skill is the only thing that refreshes the in-flight evidence.
That rerun is a **rescan**: it recomputes the whole corpus and may change
membership — unlike the generic trail refresh in `/aitask-trail`, which replays
recorded inputs. The run summary names the entries that joined and left.

## Storage

The trail is published as the artifact `art:trail-backlog-roadmap`, owned by a
standing holder task. The holder exists because the substrate supports only
task-owned artifacts and this roadmap outlives any single task: owning it from
the tree that built it would move the reference into the archive while the
roadmap went on being refreshed.

Publishing always asks for confirmation first, stating whether it is a create or
an update and which entries joined or left. `--show` writes nothing.
