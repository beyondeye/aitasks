---
title: "Implementation Trails"
linkTitle: "Implementation trails"
weight: 105
description: "A saved, versioned recommendation of which tasks should land next, in what order, and why — kept with the evidence behind it."
depth: [advanced]
---

## What it is

An **implementation trail** is a saved recommendation for the order in which a
group of tasks should land — be implemented and merged. It splits the tasks into
**waves** — groups that land together before the next group starts — and
records, for each task, why it sits where it does: a real blocker, something
cheaper to do first, a task that only touches the same files as another and
should not land at the same time, or related work that is optional.

The key idea is that a trail is **kept, not worked out again**. It stores the
recommendation together with the evidence it was based on, such as task
statuses, work already in progress or a failing test suite. When that evidence
changes, you refresh the trail and the new version is stored next to the old
one, so each earlier recommendation can still be read against the evidence it
was made on.

A trail is advice only: it never changes your tasks.

## Why it exists

When many tasks are in play, working out what should land next is expensive: an
agent has to read the tasks, their plans and the state of the repository, and
weigh them against each other. Without a trail, that answer stays in a terminal
session and is lost when the window closes. The next time someone asks, it is
worked out again from scratch, against different evidence, possibly with a
different answer and no record of what changed.

A trail keeps the answer, the reasoning and the evidence together, so you can
re-open it weeks later, see whether it has gone stale, and read it on the board.

## How to use

- **Create** a trail with [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}),
  or press **T** on a task in the board.
- **Read** it in the board's [By-Trail view]({{< relref "/docs/tuis/board/reference" >}}#by-trail)
  (press **z**) or in the stand-alone [`ait trails`]({{< relref "/docs/tuis/trails" >}}) reader.
- **Keep it current**: a trail whose evidence has moved shows a `⚠ stale` badge;
  refresh it to store a new version.
- **Act on it**: move a wave's tasks into a board column, then report on that
  column with a [work report]({{< relref "/docs/workflows/work-report" >}}) — a
  summary of that column written for a manager.

A trail pays off when the ordering question is hard — a dozen tasks across
several topics — not for a handful of tasks with obvious dependencies.

## See also

- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}) — what a trail records, creating, reading and refreshing one, and where it is stored
- [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) — the skill that writes trails
- [Trails TUI]({{< relref "/docs/tuis/trails" >}}) — the stand-alone reader
- [Board reference]({{< relref "/docs/tuis/board/reference" >}}#by-trail) — the By-Trail view and its keys
- [Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}}) — a task belongs to one topic, but can appear in several trails
- [Artifacts]({{< relref "/docs/concepts/artifacts" >}}) — the versioned, handle-addressed storage a trail is kept in

---

**Next:** [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}})
