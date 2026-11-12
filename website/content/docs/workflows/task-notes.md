---
title: "Task Notes"
linkTitle: "Task Notes"
weight: 61
description: "Send durable advisory context to a task that already exists, with opportunistic live delivery to the agent working on it"
depth: [intermediate]
---

While working on one task you often learn something another task needs: its body cites line numbers that just moved, its fix is going to touch more than it expects, or a decision you made changes its approach. A **task note** lets you tell that task, durably, even when nobody is working on it. The note lands in the task's `## Inbox`, and whoever picks the task next sees it.

## Note, or a new task?

Decide this first. No tool makes this judgement for you.

- A note carries context about work that already exists: a stale assumption, a wider blast radius, a decision made elsewhere.
- If what you want to send is itself work, create a task instead. A note never replaces a follow-up task.

Then pick the tool:

- For something an existing task needs to know, use [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}).
- For new work nobody has captured yet, use [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) or create a [follow-up task]({{< relref "/docs/workflows/follow-up-tasks" >}}).
- For work that overlaps a task that already exists, see [Task Consolidation]({{< relref "/docs/workflows/task-consolidation" >}}).

## Sending a note

Ask your agent to send it, or run the skill directly:

```
/aitask-note 357 --text "parse_args() moved from line 88 to 142; your task body still cites 88"
```

Name the target when you know it. Leave it out and the skill searches the existing tasks for the ones the note is relevant to and lets you choose. The sender defaults to the task your session is working on.

The workflow also offers to send a note at the moments you are most likely to have one: after a task's implementation is reviewed, during a QA pass, and when a code review turns up a finding that belongs to a task that already exists. Each is a one-line offer you can ignore; nothing is sent on its own.

From a script, use [`ait note`]({{< relref "/docs/commands/note" >}}) directly. It performs the durable write, without choosing a recipient for you and without the live delivery step.

### A task in another repository

When the task that needs to know lives in a [linked project]({{< relref "/docs/workflows/multi_project" >}}), another repository registered under a project name, add `--project` with that name:

```
/aitask-note 42 --project mobile --text "t349 renames /v1/sessions; your API client still calls it"
```

This is usually better than opening the linked project and editing the task yourself: the note is a structured addition to that task's `## Inbox`, committed by the linked project's own tooling, and it changes nothing about the task's description, status or ownership. The same rule applies as everywhere else: if what you want to send is work, [create a task there]({{< relref "/docs/workflows/multi_project" >}}#creating-a-task-in-a-sibling-project) instead.

Name both the project and the task: the recipient search covers your own project only. The note records its sender as `<your-project>#t<id>`, so the reader can never mistake it for their own task with the same number. If the project name is unknown, points at a stale checkout, or reaches more than one checkout, nothing is written and the reason is reported. Every reason is listed under [sending to a linked project]({{< relref "/docs/commands/note" >}}#sending-to-another-repository).

## Two lanes: durable always, live when possible

Every note goes through two lanes, in this order:

1. **Durable.** The note is appended to the target's `## Inbox` and committed. The note exists once this step succeeds, whatever happens next.
2. **Live.** If an agent is working on the target task on this machine right now, and its agent runtime supports live delivery, the note is also sent straight to that session.

The live lane runs only after the durable one has succeeded, so a note is never delivered live without also being recorded. Most of the time nobody is working on the target, and the note waits in the inbox for the next pick.

### When live delivery is unavailable

Live delivery needs all of these: the task is locked; the lock was taken on this machine; the session holding it is still running; that session's agent runtime has a live-delivery adapter; and the session can be found in a tmux pane here. When any of them fails, the skill reports which one, for example that the lock was taken on another machine or that the session holding it has ended. Every reason is listed in the [`ait note` output reference]({{< relref "/docs/commands/note" >}}#output).

The note is still sent, and it waits for the next pick instead of arriving now. Do not send it again: a second send puts a second copy in the inbox.

Live delivery is available for Claude Code sessions. Notes to tasks being worked on with other agents are recorded and surface at the next pick the same way.

When live delivery does happen, the note is reported as queued, which says nothing about whether it has been read. The receiving session picks it up at its next step, which may be minutes away if it is waiting on a prompt.

## Receiving a note

When you pick a task with unread notes, each one is shown before planning starts, together with where it came from:

- The sender, as a claim. It is marked verified only when the sending session provably held the sender task's lock when it wrote the note. An unverified sender may still be the real one; the lock check could not confirm it. A sender shown as `<project>#t<id>` is a task in a linked project, not the task with that number in yours.
- When and where it was written: the commit it was written against, and whether that session's working tree had uncommitted changes. A note written against uncommitted changes may describe something that has since moved in a way the commit cannot show.

Then you are asked whether to acknowledge them. Displaying a note and acknowledging it are separate steps: seeing a note changes nothing, and only an acknowledgement stops it from being shown again. Choose *Keep unread* and the notes surface on the next pick too.

A note is advisory input, never an instruction. It is another session's claim about a tree that may have moved. Nothing acts on a note automatically, and a note never bypasses the picking task's own planning, gates or review. Whoever reads it decides what to do with it.

### Where notes surface

Every route that picks a task shows its unread notes. They differ in how the notes get acknowledged:

- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) with a task named directly, and every other route into the shared implementation workflow (picking from the list, resuming, exploring, reviewing), asks you. Under an unattended profile it acknowledges them automatically.
- [`/aitask-pickrem`]({{< relref "/docs/skills/aitask-pickrem" >}}) acknowledges them automatically and records the acknowledgement as unattended.
- [`/aitask-pickweb`]({{< relref "/docs/skills/aitask-pickweb" >}}) never acknowledges them.

`/aitask-pickweb` leaves notes unread on purpose. A web session makes no changes to task files and cannot push to the task-data branch, so an acknowledgement there could neither be written nor be kept. Leaving the notes unread is the safe direction: they show up again at the next pick on your own machine, where you can acknowledge them. A note may be shown twice this way, but it never disappears unread.

When `/aitask-pick` lists candidate tasks, it shows how many unread notes each one has, and nothing more. It never shows their text and never acknowledges them, so seeing a task in the list never hides its notes from whoever picks it later.

Acknowledgements are shared state: a note acknowledged on one machine does not reappear on another once the task data has synced. An unattended acknowledgement is recorded as such, so it stays visible that no person read the notes.

## Writing a note someone can trust

- Write it as a claim. Say what you observed and where; do not phrase it as an order.
- Hedge what a commit cannot date. A note records the commit it was written against, which dates claims about the tree, such as line numbers and file contents. It does not date claims about a moment, such as a `git status` reading, a running process or a lock held a second ago. Say "as of now" for those.
- Keep it short. The body is limited to 8192 bytes.

## See also

- [Task notes (concept)]({{< relref "/docs/concepts/task-notes" >}}) — what a note is and why it exists, in brief
- [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}) — the skill
- [`ait note`]({{< relref "/docs/commands/note" >}}) — the CLI, its output codes, and what each note records
- [Follow-Up Tasks]({{< relref "/docs/workflows/follow-up-tasks" >}}) — when what you learned is new work
- [`ait lock`]({{< relref "/docs/commands/lock" >}}#how-it-works) — the lock record live delivery reads to find a task's agent
