---
title: "Task Notes"
linkTitle: "Task notes"
weight: 45
description: "A short message one task leaves on another existing task, so whoever works on that task next learns something it needs."
depth: [intermediate]
---

## What it is

A **task note** is a short message left on a task that already exists, for
whoever works on it next. It is added to a `## Inbox` section in that task's
file and committed with it. Because the note lives inside the task it is about,
it survives with no agent running, travels with the task data to every machine,
and is shown each time someone starts work on the task, until it is
acknowledged.

A note carries **context, not work**: a line number in the task's description
that has since moved, a fix that will touch more than the task expects, or a
decision made elsewhere that changes its approach. If what you want to send is
itself work, create a task instead.

A note is also **advice, not an order**. It records what one agent believed
about the code when it wrote the note, and the code may have changed since. The
reader decides what to do with it, and nothing acts on a note automatically.

## Why it exists

While working on one task you often learn something another task needs. Without
notes, the options are poor: rewrite that task's description, which changes its
requirements instead of adding context; create a new task, which is wrong when
there is no new work; or tell the agent working on that task right now, which
only works if one happens to be running at that moment.

A note removes that dependence on timing. The note is saved in the task first.
It may also reach an agent currently working on it.

## How to use

- **Send** a note with [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}):
  name the target task, or let it suggest the tasks the note is relevant to. The
  workflow also offers to send one at the moments you are most likely to have
  one — after an implementation is reviewed, during QA, and during code review.
- **Script it** with [`ait note`]({{< relref "/docs/commands/note" >}}), which saves
  the note without trying to reach a running agent.
- **Reach another repository** by adding `--project <name>`, with that
  project's registered name — see
  [a task in another repository]({{< relref "/docs/workflows/task-notes" >}}#a-task-in-another-repository).
- **Receive** notes when you start work on a task: each unread note is shown
  with where it came from, and you then choose whether to acknowledge it or keep
  it unread.

## See also

- [Task Notes]({{< relref "/docs/workflows/task-notes" >}}) — sending, receiving, how a note reaches a running agent, and where notes surface
- [`ait note`]({{< relref "/docs/commands/note" >}}) — the CLI, its output codes, what each note records, and how the inbox is stored
- [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}) — the skill that sends notes
- [Cross-repo references]({{< relref "/docs/concepts/cross-repo-references" >}}) — how a task in another project is named

---

**Next:** [Review guides]({{< relref "/docs/concepts/review-guides" >}})
