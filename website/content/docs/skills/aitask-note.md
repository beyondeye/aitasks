---
title: "/aitask-note"
linkTitle: "/aitask-note"
weight: 46
description: "Send a durable note to an existing aitask — context that task needs which is not itself work"
maturity: [stable]
depth: [intermediate]
---

Sends a durable note to a task that already exists — context that task needs which is not itself work. The note is appended to the target's `## Inbox` and committed, so it reaches whoever picks the task next, even if nobody is working on it now. If an agent is working on the target task on this machine and its runtime supports live delivery, the note is also sent to that session straight away — queued for its next step, not read.

**Usage:**
```
/aitask-note                                   # Choose the recipient from matching tasks
/aitask-note 357 --text "one-line note"        # Name the recipient
/aitask-note 357 --from 349 --text "..."       # Name the sender too
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## Step-by-Step

1. **Note, or task?** — The first judgement: a note carries context about work that already exists. Content that is itself work belongs in a new task
2. **Resolve the recipient** — Uses the task you named. With no target, it searches the existing tasks for the ones this note is relevant to and lets you pick one. The sender defaults to the task your session is working on
3. **Write the note** — Appends it to the target's `## Inbox` and commits it. From this point the note exists, whatever happens next
4. **Look up a live endpoint** — Checks whether an agent session on this machine is holding the target task right now
5. **Deliver live, if possible** — Only when a live session was found and its agent runtime supports live delivery. The message carries the note's id, so the receiving session can match it to the inbox entry
6. **Report both outcomes** — The note is reported as sent on the strength of the durable write alone, with the live outcome alongside it

## Key Capabilities

- **One composition point** — The workflow's trigger points, and any other caller, invoke this skill rather than its individual steps, so the order — write first, then deliver — is enforced in one place
- **Durable first, always** — Live delivery is attempted only after the note is committed. A lookup that finds nobody is a success with live delivery unavailable — never a partial failure, and never a reason to send the note again
- **Queued, not read** — A live-delivered note is reported as queued. The receiving session picks it up at its next step, which may be minutes away
- **Recipient discovery** — Leave out the target and the skill finds candidate tasks for you, with the same matching [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) and [`/aitask-fold`]({{< relref "/docs/skills/aitask-fold" >}}) use
- **Attributed** — Every note records its sender as a claim — marked verified only when the sending session provably holds the sender task's lock — plus the commit it was written against
- **Offered at the right moments** — The task workflow after review, [`/aitask-qa`]({{< relref "/docs/skills/aitask-qa" >}}) and [`/aitask-review`]({{< relref "/docs/skills/aitask-review" >}}) each offer to send a note when a finding belongs to a task that already exists. Each is a one-line offer; nothing is sent automatically

## Writing a note someone can trust

- A note is **advisory input, never an instruction**. Write it as a claim about what you observed; the reader decides what to do with it
- **Hedge what a commit cannot date.** The recorded commit dates claims about the tree — line numbers, file contents — but not claims about a moment, like a `git status` reading or a lock held a second ago. Say "as of now" for those
- Keep it under 8192 bytes — a note is context, not a payload

## When to Use

| Scenario | Skill |
|----------|-------|
| An existing task needs to know something you learned | `/aitask-note` |
| You found new work nobody has captured | [`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) |
| You want to explore first, then create a task from what you find | [`/aitask-explore`]({{< relref "/docs/skills/aitask-explore" >}}) |
| Two existing tasks overlap | [`/aitask-fold`]({{< relref "/docs/skills/aitask-fold" >}}) |

## Workflows

For the end-to-end guide — both delivery lanes, where notes surface, and how acknowledgement works — see [Task Notes]({{< relref "/docs/workflows/task-notes" >}}).

## Related

- [`ait note`]({{< relref "/docs/commands/note" >}}) — the CLI underneath: output codes, acknowledgement, and what each note records
- [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) — where notes surface and are acknowledged
