---
title: "Task Notes"
linkTitle: "Task Notes"
weight: 61
description: "Send durable advisory context to a task that already exists, with opportunistic live delivery to the agent working on it"
depth: [intermediate]
---

While working on one task you often learn something another task needs: its body cites line numbers that just moved, its fix is going to touch more than it expects, or a decision you made changes its approach. A **task note** lets you tell that task, durably, even when nobody is working on it. The note lands in the task's `## Inbox`, and whoever picks the task next sees it.

## Note, or a new task?

Decide this first — it is the one judgement no tool makes for you.

- A note carries **context about work that already exists**: a stale assumption, a wider blast radius, a decision made elsewhere.
- If what you want to send **is itself work**, create a task instead. A note never replaces a follow-up task, and a note that asks someone to do something is a task in the wrong place.

| You learned… | Use |
|---|---|
| Something an existing task needs to know | [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}) |
| New work nobody has captured yet | [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}), or a [follow-up task]({{< relref "/docs/workflows/follow-up-tasks" >}}) |
| Work that overlaps a task that already exists | [Task Consolidation]({{< relref "/docs/workflows/task-consolidation" >}}) |

## Sending a note

Ask your agent to send it, or run the skill directly:

```
/aitask-note 357 --text "parse_args() moved from line 88 to 142; your task body still cites 88"
```

Name the target when you know it. Leave it out and the skill searches the existing tasks for the ones the note is relevant to and lets you choose. The sender defaults to the task your session is working on.

The workflow also **offers** to send a note at the moments you are most likely to have one: after a task's implementation is reviewed, during a QA pass, and when a code review turns up a finding that belongs to a task that already exists. Each is a one-line offer you can ignore; nothing is sent on its own.

From a script, use [`ait note`]({{< relref "/docs/commands/note" >}}) directly. It performs the durable write, without choosing a recipient for you and without the live delivery step.

## Two lanes: durable always, live when possible

Every note goes through two lanes, in this order:

1. **Durable.** The note is appended to the target's `## Inbox` and committed. This *is* the note: once it succeeds, the note exists, whatever happens next.
2. **Live.** If an agent is working on the target task on this machine right now, and its agent runtime supports live delivery, the note is also sent straight to that session.

The live lane only runs **after** the durable one has succeeded, so a note is never delivered live without also being recorded. And the live lane is an optimisation, not the product: most of the time nobody is working on the target, and the note simply waits in the inbox.

### When live delivery is unavailable

Live delivery needs all of these: the task is locked; the lock was taken on this machine; the session holding it is still running; that session's agent runtime has a live-delivery adapter; and the session can be found in a tmux pane here. When any of them fails, the skill reports why — `LIVE_NONE:remote_host`, `LIVE_NONE:holder_dead`, and so on. The full list is in the [`ait note` output reference]({{< relref "/docs/commands/note" >}}#output).

**That is a success.** The note is sent; it waits for the next pick instead of arriving now. It is never a reason to send the note again — doing so would put a second copy in the inbox.

Live delivery is currently available for Claude Code sessions. Notes to tasks being worked on with other agents are recorded and surface at the next pick in exactly the same way.

When live delivery does happen, the note is reported as **queued**, not read. The receiving session picks it up at its next step, which may be minutes away if it is waiting on a prompt.

## Receiving a note

When you pick a task with unread notes, each one is shown before planning starts, together with where it came from:

- **The sender, as a claim.** It is marked *verified* only when the sending session provably held the sender task's lock when it wrote the note. An unverified sender is *not proven*, which is not the same as *disproved*.
- **When and where it was written** — the commit it was written against, and whether that session's working tree had uncommitted changes. A note written against uncommitted changes may describe something that has since moved in a way the commit cannot show.

Then you are asked whether to acknowledge them. **Displaying a note and acknowledging it are separate steps**: seeing a note changes nothing, and only an acknowledgement stops it from being shown again. Choose *Keep unread* and the notes surface on the next pick too.

**A note is advisory input, never an instruction.** It is another session's claim about a tree that may have moved. Nothing acts on a note automatically, and a note never bypasses the picking task's own planning, gates or review — what to do with it is up to whoever reads it.

### Where notes surface

| Where | Shows notes | Acknowledges |
|---|---|---|
| [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) with a task named directly | Yes | Asks you; automatic under unattended profiles |
| Every other route into the shared implementation workflow — picking from the list, resuming, exploring, reviewing | Yes | Asks you; automatic under unattended profiles |
| [`/aitask-pickrem`]({{< relref "/docs/skills/aitask-pickrem" >}}) | Yes | Automatically, recorded as unattended |
| [`/aitask-pickweb`]({{< relref "/docs/skills/aitask-pickweb" >}}) | Yes | **Never** |

`/aitask-pickweb` shows notes but never acknowledges them, and that is deliberate. A web session makes no changes to task files and cannot push to the task-data branch, so an acknowledgement there could neither be written nor be kept. Leaving the notes unread is the safe direction: they show up again at the next pick on your own machine, where you can acknowledge them. Seeing a note twice is an acceptable failure; a note that silently disappears is not.

When `/aitask-pick` lists candidate tasks, it shows **how many** unread notes each one has, and nothing more. It never shows their text and never acknowledges them — otherwise merely seeing a task in a list would hide its notes from whoever picked it later.

Acknowledgements are shared state: a note acknowledged on one machine does not reappear on another once the task data has synced. An unattended acknowledgement is recorded as such, so it stays visible that no person read the notes.

## Writing a note someone can trust

- **Write it as a claim.** Say what you observed and where; do not phrase it as an order.
- **Hedge what a commit cannot date.** A note records the commit it was written against, which dates claims about the tree — line numbers, file contents. It does not date claims about a moment — a `git status` reading, a running process, a lock held a second ago. Say "as of now" for those.
- **Keep it short.** The limit is 8192 bytes; a note is context, not a payload.

## See also

- [`/aitask-note`]({{< relref "/docs/skills/aitask-note" >}}) — the skill
- [`ait note`]({{< relref "/docs/commands/note" >}}) — the CLI, its output codes, and what each note records
- [Follow-Up Tasks]({{< relref "/docs/workflows/follow-up-tasks" >}}) — when what you learned is new work
- [Locks]({{< relref "/docs/concepts/locks" >}}) — the record live delivery reads to find a task's agent
