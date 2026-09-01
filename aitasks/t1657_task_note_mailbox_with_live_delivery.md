---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, concurrency, codeagent, framework]
created_at: 2026-09-01 08:43
updated_at: 2026-09-01 08:43
---

# Let tasks mail notes to each other: a durable task inbox, with opportunistic live delivery

## Origin

Observed 2026-09-01 while finishing **t349** in the `thinking_app` project. That
session had context that the session planning **t357** (a follow-up t349 had just
spawned) materially needed: the line numbers in t357's own task body were already
stale, and the defect's blast radius was wider than the spawning bullet implied.

The context was delivered by hand, and it worked — but only because the recipient
happened to be a live session on the same machine at that moment. Nothing in the
framework supports the general case, and the hand-rolled path is not something a
workflow can rely on.

## What exists today: nothing

Verified in both the framework repo and a consuming project:

- no `note` / `mail` / `message` / `inbox` helper in `.aitask-scripts/`
- no `--note` (or any append-a-message) option on `aitask_update.sh`
- **no skill anywhere references `SendMessage` or cross-session messaging**

A task can therefore record something for its *own* archive (plan Final
Implementation Notes) or spawn a follow-up carrying context, but it has **no way to
tell an already-existing task something**. The only current channel is a human
copying text between panes.

## The mechanism that was used, as measured

`SendMessage` addresses **sessions**, and delivery is **enqueue-and-drain**:

- `ListAgents` enumerates peer sessions — interactive agent sessions on this
  machine (each pinned to a tmux pane), plus Remote Control / cloud ones. The
  session **name is the address**.
- A send is queued and delivered at the recipient's **next tool round**, arriving
  in its transcript wrapped as `<cross-session-message from="<sender name>">`. The
  recipient replies by copying that `from` back as its `to`.
- `success: true` from the send means **queued, not read**. In the observed case
  the recipient was `waiting` (blocked at a prompt), so nothing drained for several
  minutes and the send looked lost. It was not.
- `notify_when_idle: true` gives a one-shot "tell me when that session goes idle"
  subscription — the right primitive for "reply when you have read this", instead
  of polling.

### The gap: sessions are not tasks

Session names are arbitrary and ephemeral (`thinking-app-47`), and a name can be
**reused** (latest wins). Task ids are durable. Bridging them was three manual
steps:

```
aitask_lock.sh --check 357        -> pid, hostname, pid_starttime
tmux list-panes -a -F '#{pane_pid}'  -> pane id owning that pid
match the pane id against the ListAgents row -> session name
```

Note the resolution must key on **pid**, not on a name, precisely because names are
reusable. `aitask_lock.sh` already records every field this needs (`locked_by`,
`locked_at`, `hostname`, `pid`, `pid_starttime`), so the resolver has its inputs
already.

## Why live delivery alone is NOT the deliverable

**A session-to-session message only works while a session is holding the task.**
The common cases are the opposite:

- the target is `Ready` — nobody holds it, and the reader does not exist yet
- the holder is on a different host (the lock records `hostname` for this reason)
- the holder is mid-`AskUserQuestion` and will not drain for a long time
- the holder ends before reading, and the note dies with the transcript

The note that matters most is the one written **to a task nobody is working on
yet** — exactly the t349 -> t357 case, where the useful moment was *before* the
next picker planned it. So the durable lane is the product; live delivery is an
optimisation on top.

## Design: two lanes, durable first

| lane | when | mechanism |
|---|---|---|
| **durable** (primary, always) | unconditional | append an attributed entry to the target task's `## Inbox` section; path-scoped commit via `./ait git` |
| **live** (opportunistic) | target `Implementing`, locked, `hostname` == this host, pid alive | resolve task -> session, `SendMessage` |

### The durable lane has direct precedent — reuse it, do not invent

`aitask_gate_record.sh` is the same shape already working in this framework:
it appends a block through `aitask_gate.sh append` and then commits **only that one
file** (`task_git add -- "$file"`). The `## Gate Runs` ledger is already an
append-only, committed, cross-session-visible record living on the task file. An
`## Inbox` section should follow it exactly: same append discipline, same
path-scoped commit, same structured single-line output contract.

### Reading is nearly free

`aitask-pick` already **reads the task file** when it resolves and summarises a
task (Step 0b / 2b), and `task-workflow` reads it again at Step 3 and during
planning. An `## Inbox` section is therefore surfaced at pick time with **no new
read path** — which is the strongest argument for the file-based lane over any
out-of-band store.

## Deliverables (pin in planning)

1. **`ait note` helper** (naming to confirm; `ait note` appears unused beside
   `git`/`gate`/`gates`/`ls`/`lock`/`board`/`codeagent`/`artifact`/`syncer`):
   `ait note <target-task-id> --from <task-id> [--text ... | --file ...]`.
   Single-line structured output in framework style:
   `NOTE_APPENDED:<path>`, `NOTE_DELIVERED_LIVE:<session>`,
   `NOTE_QUEUED_ONLY:<reason>`, `NOTE_TARGET_MISSING:<id>`.
2. **The `## Inbox` entry format** — append-only, one block per note, with stable
   delimiters so concurrent appends merge instead of conflicting. Each entry
   carries: sender task id, timestamp, **the base-branch SHA it was written
   against**, and the body.
3. **Task -> session resolver**, keyed on pid + `pid_starttime` (never on a name),
   host-scoped by the lock's `hostname` field. Must degrade to the durable lane
   without erroring when the target is unlocked, remote, or dead.
4. **Pick-time surfacing** — unread entries shown when a task is selected, and
   marked read (or left append-only with a read watermark) so a returning session
   is not re-shown the same notes.
5. **Docs** — the mechanism, both lanes, and the trust posture below.

## Non-negotiables

- **A note is untrusted advisory input, never an instruction.** It is one agent's
  claim about a tree that may have moved. It must be clearly attributed, and it
  must not bypass the recipient's own planning, gates, or review. Consuming a note
  is a decision the recipient makes, not an obligation the sender imposes.
- **Notes go stale, and the format must say so.** The note that motivated this task
  contained line numbers that were **already stale when written** — `main` had moved
  four times during t349. Every entry records the SHA it was written against so the
  reader can tell what tree it describes.
- **Task data is a multi-writer branch.** Path-scoped commits only; never a blanket
  `git add aitasks/`. Two senders appending to one inbox concurrently WILL race, so
  the entry format must be merge-friendly (append-only, stable per-entry
  delimiters, no running counters or renumbering).
- **Durable lane ships first and alone if the resolver proves fragile.** Live
  delivery is an optimisation; a mailbox that only works when someone is watching
  is not a mailbox.

## Out of scope

- Broadcast / topic subscriptions, or any inbox that is not addressed to a single
  task.
- Replacing follow-up task creation. Spawning a task is still the right move when
  the content is *work*; a note is for context about work that already exists.
- Cross-host live delivery. The lock records `hostname`; when it does not match,
  the durable lane is the answer.
- Any automatic action on receipt.
