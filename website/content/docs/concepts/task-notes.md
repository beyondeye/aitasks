---
title: "Task Notes"
linkTitle: "Task notes"
weight: 45
description: "Why context sent between tasks is untrusted by construction, and what its provenance can and cannot prove."
depth: [intermediate]
---

## What it is

A **task note** is a block appended to another task's `## Inbox` section and
committed with that task's file. The note lives *inside* the task it is about,
which is what makes it durable: it survives with no agent running, it travels
with the task data to every machine, and whoever picks the task next sees it.

For how to send and receive one, see
[Task Notes]({{< relref "/docs/workflows/task-notes" >}}). This page is about the
model underneath: a note is one session's **claim** about a repository that may
have moved since, and every part of the design follows from treating it that way.

### A claim about a tree, not a message from a person

A note's sender is [recorded as a claim and verified only when
proven]({{< relref "/docs/workflows/task-notes" >}}#receiving-a-note). The shape
of that record is the page's core idea: the verification field is written as
`yes` or **left out entirely — it is never written as `no`.**

That asymmetry is deliberate. The proof fails for entirely innocent reasons — a
note sent from a session that holds no task, a process whose identity the
framework cannot resolve for itself — so an absent field means *not proven*,
never *disproved*. It also proves only that the sender was who it says at write
time: nothing about whether the content is correct, and nothing about the state
of anything when you read it.

The provenance about the tree is asymmetric in the same way. A commit id dates
claims you can go and check — a line number, a file's contents. It cannot date a
claim about a *moment*, and the `dirty` flag is the only signal that a claim of
that kind may already be stale. On a migrated note an empty `dirty` means "never
measured", not "clean".

The full field table lives once, in the
[`ait note` provenance reference]({{< relref "/docs/commands/note" >}}#provenance).

### Notes across repositories

A note can be sent to a task in [another
repository]({{< relref "/docs/commands/note" >}}#sending-to-another-repository).
It is still an ordinary block in the recipient's `## Inbox`, written and
committed by the recipient repository's own tooling — a structured addition to
that task, not a side channel. It changes nothing about the task's
requirements, status or authority.

Two things follow from the [cross-repo identity model]({{< relref "/docs/concepts/cross-repo-references" >}}):

- **The sender is always qualified.** A task id means nothing outside its own
  repository, so a note from elsewhere records `from=<project>#t<id>`. A bare
  `t<id>` would silently name a *different* task — the recipient's own task
  with that number.
- **Verification means exactly what it means locally.** The sending session
  must provably hold the sender task's lock; that lock lives in the sender's
  repository and is checked there. Crossing the boundary adds no trust, and a
  note from another project is no more an instruction than a local one.

Its tree provenance describes the **recipient's** checkout, the one the note
was written into — a commit from the sender's repository would not exist in
the recipient's history, so a reader could never check a claim against it.

### The body cannot forge bookkeeping

Notes and their acknowledgements share one section, one storage format and one
namespace — and a note's body is free-form text written by another session,
while everything else in that section is written by the framework. So the body
is the one part of the file that an untrusted party controls.

Every body line is therefore stored behind a `> | ` prefix. Block headers are
recognised only at the start of a line, so no line of a note body can ever parse
as one: a note cannot forge a read receipt — for itself or for any other note in
the file — and cannot open a new section heading that would swallow what follows
it. Acknowledgements use the reserved marker name `read`, which no note can
take, because a note's marker is always its sender's task id.

The prefix is applied when the note is **written**, so every reader — including
ones not yet written — inherits the defence without doing anything.

### Unread is derived, and failures lean toward showing the note again

A note is unread while no valid acknowledgement names its id; the state is
[derived, never stored]({{< relref "/docs/commands/note" >}}), so there is no
field that could disagree with the record.

What matters conceptually is the direction each failure falls in:

- An acknowledgement that does not validate is **skipped**, so a malformed
  record can never suppress a real note.
- An acknowledgement identifies its reader as the **target task itself**. The
  task id is the only durable identity the reading session has — session names
  do not outlive the session — and any other value is refused rather than
  recorded.
- If the commit fails, a **note is kept** and an **acknowledgement is discarded**.
  A note's body is irreplaceable and re-sending it would put a second copy in
  the inbox; an acknowledgement is pure bookkeeping that costs nothing to
  repeat, and one left on disk but uncommitted would hide a note locally with
  nothing durable to show for it.

Each of those choices is made in the direction of a note surfacing again: seeing
a note twice is an acceptable failure, and a note that silently disappears is
not.

One case cannot be resolved that way, and the framework refuses to pretend
otherwise. If discarding an uncommittable acknowledgement *also* fails, the
record is on disk, uncommitted, hiding a note — and no automatic action can
safely settle it. That outcome is reported as its own terminal error naming the
block to remove, rather than folded in with the ordinary failures, because it is
the one state that needs a person: either remove that block or commit it. The
[`rollback-failed` outcome]({{< relref "/docs/commands/note" >}}#output) is where
it surfaces.

### Seeing a note is not acknowledging it

Display and acknowledgement are
[separate steps]({{< relref "/docs/workflows/task-notes" >}}#receiving-a-note),
and that separation is what allows a candidate list to show that a task *has*
unread notes without consuming them — if merely listing a task
acknowledged its notes, an agent that glanced at a menu would hide them from
whoever picked that task later.

It also makes unattended acknowledgement safe to allow: the "never act on a note
automatically" rule governs a note's **content**, not the read bookkeeping, so an
unattended session may acknowledge — and records that it did so automatically, so
"no person read these" stays visible rather than invisible. Which surfaces
display and which acknowledge is tabulated in
[where notes surface]({{< relref "/docs/workflows/task-notes" >}}#where-notes-surface).

## Why it exists

The framework could always record context for a task's own archive, or spawn a
follow-up task carrying it, but it had no way to tell an *existing* task
anything. The case that prompted the mailbox was delivered by hand, pane to
pane, and worked only because the recipient happened to be a live agent on the
same machine at that moment.

Making the durable write the product — and live delivery to a running agent an
optimisation on top of it — is what removes that coincidence. The note is
committed to the target task first, and only then, opportunistically, pushed to
whoever is working on it.

## How to use

Send one with [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}), which
chooses the recipient and handles both delivery lanes, or with
[`ait note`]({{< relref "/docs/commands/note" >}}) for the durable write alone.

## See also

- [Task Notes]({{< relref "/docs/workflows/task-notes" >}}) — sending, receiving, and both delivery lanes
- [`ait note`]({{< relref "/docs/commands/note" >}}) — the CLI, its output codes, and the provenance fields
- [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}) — the skill that composes the lanes
- [Cross-repo references]({{< relref "/docs/concepts/cross-repo-references" >}}) — why a sender in another project is recorded as a project-qualified pair

---

**Next:** [Review guides]({{< relref "/docs/concepts/review-guides" >}})
