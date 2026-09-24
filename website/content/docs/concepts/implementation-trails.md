---
title: "Implementation Trails"
linkTitle: "Implementation trails"
weight: 105
description: "Why a sequencing recommendation is kept as a versioned, task-owned artifact instead of being worked out again each time."
depth: [advanced]
---

## What it is

An **implementation trail** is one structured document, stored under a handle
that a single task owns. What a trail records — waves, classifications,
observations, exclusions — and how you create, read and refresh one are covered
in the [Implementation Trails workflow]({{< relref "/docs/workflows/implementation-trails" >}});
this page covers why it is kept at all, and what follows from where it is kept.

### Kept, not re-derived

A landing-order recommendation is a *decision*, made against evidence that goes
stale: task statuses, work in flight, a failing suite, and an agent's judgement
of all of them. Running the same analysis later does not reproduce that
decision — it makes a new one against different evidence. So the thing worth
keeping is the decision **together with the evidence it was made on**, and a
refresh records a new decision beside the old one rather than overwriting it.
The version history is a history of decisions, each still readable against its
own evidence. How a trail notices that its evidence has moved, and how it is
refreshed, is described in
[Keeping a trail current]({{< relref "/docs/workflows/implementation-trails" >}}#keeping-a-trail-current).

### One owner carries the handle

When a trail is created, the handle is written to exactly one task file: the
owner task's `artifacts:` frontmatter entry (see the
[field shape]({{< relref "/docs/development/task-format" >}}#nested-fields-artifacts-and-attachments)).
No other task file is written.

The owner may also be a member — a trail scoped to a single task or topic is
owned by that task or topic root by default — but the files of every *other*
member are never touched. That is why a task can appear in any number of trails
without its file changing once.

A trail that spans several topics, or an ad-hoc set of tasks, needs an owner
someone chose on purpose. No container task is invented to hold it: that would
add a card to the board for every trail and give it a lifecycle nobody asked
for.

### Found through its owner

Trails are discovered by scanning task frontmatter, **active and archived**, for
trail entries. Two things follow:

- **Archiving the owner does not hide the trail.** It stays listed and readable,
  and the board notes that its owner is archived. That is a fact about the
  owner, not about the trail's freshness: freshness is judged from the tasks the
  trail recorded as inputs, and the chosen owner of a multi-topic trail need not
  be one of them.
- **Folding the owner copies the handle.** The fold adds the `artifacts:` entry
  to the primary task, so the trail survives with a new owner. The folded
  task keeps its own entry until its file is deleted when the primary is
  archived, so for a while two task files reference the same trail. Discovery
  lists it once, preferring an active, unfolded owner.

### One document, several readings

What is stored is a single structured document in which the prose — why a wave
is where it is, why an entry matters, what it would cost to delay — is
first-class content rather than decoration. The board's By-Trail view,
`ait trails` and the summary the skill prints are all projections of that one
document, and none of them is saved as a second copy that could disagree with
it. Membership lives inside the document too, never as a field on a member task.

### Read by nothing that enforces

The [workflow]({{< relref "/docs/workflows/implementation-trails" >}}#what-a-trail-never-does)
lists what a trail never *writes*. The read side matters as much: gate
enforcement, dependency resolution and archival guards never read a trail, so
a trail can never block or unblock a task.

## Why it exists

Each part of this storage model was chosen over a simpler-looking alternative:

- **Not a field on every member task.** One recommendation would rewrite many
  task files, and a task in three trails would carry three sets of ordering
  hints that other tools might mistake for its own metadata.
- **Not markdown with a parser, nor markdown paired with data.** A parsed
  document breaks on the first unexpected edit, and two stored forms are two
  sources of truth that drift apart. One structured document with derived views
  has neither problem.
- **Not ownerless.** Every stored artifact belongs to a task. A trail scoped
  to one task or one topic takes that task or topic root as its owner. A
  multi-topic or ad-hoc trail has no natural owner, so you choose one: picking
  it automatically would quietly tie the trail's lifecycle — folds, archival —
  to a task you never chose.

## How to use

Create or refresh a trail with [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}).
Read it on the board's [By-Trail view]({{< relref "/docs/tuis/board/reference" >}}#by-trail)
or in the stand-alone [`ait trails`]({{< relref "/docs/tuis/trails" >}}) reader.

## See also

- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}}) — what a trail records, and the create / read / refresh workflow
- [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) — the skill that writes trails
- [Trails TUI]({{< relref "/docs/tuis/trails" >}}) — the stand-alone reader
- [Board reference]({{< relref "/docs/tuis/board/reference" >}}#by-trail) — the By-Trail view and its keys
- [Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}}) — the one-topic-per-task model a trail sits beside

---

**Next:** [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}})
