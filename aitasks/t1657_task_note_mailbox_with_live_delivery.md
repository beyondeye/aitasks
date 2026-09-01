---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [task_workflow, concurrency, codeagent, framework]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1657_1, t1657_2, t1657_3, t1657_4, t1657_5, t1657_6]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-01 08:43
updated_at: 2026-09-01 12:37
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

---

## Note from t357 (thinking_app) — 2026-09-01, written against aitasks main 451dd3af7 / aitask-data eab147468

**Advisory input from another session, not an instruction.** Written by session
`fix-worker-peak-space-path` after finishing `thinking_app` t357 — the same t349→t357
chain this task's Origin describes. Delivered by hand because `ait note` is this task's
own deliverable and does not exist yet. Consume or discard; it is one session's claim
about a tree that may have moved.

### The gap: the design is silent on agent type

`grep -niE 'codex|opencode|claudecode|agent type|implemented_with'` over this task body
returns **zero matches**, and there was no plan file at the time of writing. Cross-agent
messaging is neither included nor excluded — note that **cross-*host* live delivery IS
explicitly scoped out**, so the degradation axes were being thought about and this one
simply did not come up.

| | durable lane | live lane |
|---|---|---|
| claude→claude | works | **the only case designed for** |
| claude→codex | works | unspecified |
| codex→claude | works | unspecified |
| codex→codex | works | unspecified |

### 1. The durable lane is agent-agnostic by accident, not by design

An `## Inbox` section on a committed task file plus a shell helper is reachable from any
agent. Nothing states this as a requirement, and one deliverable hides real work behind
it: **Deliverable 4 (pick-time surfacing) is three ports, not one.** This framework fans
out per agent — `.claude/`, `.codex/` and `.opencode/` trees, and three `models_*.json`
— and `aitask-audit-wrappers` exists precisely because that fanout drifts. "Surfaced at
pick time with no new read path" is true per tree, but there are three trees.

### 2. The live lane is Claude-only and does not say so

`SendMessage` / `ListAgents` are Claude Code tools, and `ListAgents` enumerates Claude
sessions only (subagents, teammates, other local Claude sessions, cloud/Remote Control).
A Codex-held task produces no row.

### 3. Codex HAS an equivalent — verified on the installed binary, not from docs

`codex-cli 0.151.0` on this host:

    codex queue --thread <session UUID or exact session name> --message <text>
    codex agents      # "Browse all agent sessions on the shared local app-server daemon"

Landed in v0.149.0 (20 Aug 2026), which is why it is absent from older reasoning about
this. It is an **equivalent capability in a different shape**, and the differences are
load-bearing for Deliverable 3:

- a **CLI command**, not a model-facing tool — an agent reaches it through its shell;
- addressed by **UUID or *exact* name**, where `SendMessage` resolves a bare name via
  `ListAgents` with `[ref]` disambiguation. So "task → session" has **one output shape
  per agent type**, not one shape;
- **no `notify_when_idle` analogue** visible in its help — the "reply when you have read
  this" primitive this task rightly identifies would have to be polled under Codex, which
  is exactly what the subscription exists to avoid.

### 4. Concrete defect in Deliverable 3's degradation list

Deliverable 3 requires the resolver to "degrade to the durable lane without erroring when
the target is **unlocked, remote, or dead**." A Codex-held task is **none of those three**
— it is locked, local, and alive. The resolver would key on pid → pane → look for a
matching `ListAgents` row → find nothing, and the task does not say what happens then.
An incomplete enumeration in a fail-closed list is the same shape as reporting "cannot
classify" as "no problem". Add agent type as a fourth axis, or scope it out explicitly.

### 5. The discriminator already exists and is not referenced

`implemented_with` records exactly this (`claudecode/opus5`, `codex/gpt-5.4`). This task
lists the resolver's inputs as pid / hostname / pid_starttime from the lock and never
mentions it. Two wrinkles, both measured on t357:

- **The lock record carries no agent field.** `aitask_lock.sh --check` returns exactly
  `task_id`, `locked_by`, `locked_at`, `hostname`, `pid`, `pid_starttime`,
  `pid_starttime_kind`. So either read `implemented_with`, or add an agent field at claim
  time.
- **There is a window where the field is empty.** `implemented_with` is written by the
  Agent Attribution Procedure at **Step 7**; the lock is claimed at **Step 4**. During
  planning a task is `Implementing` and locked with **no** `implemented_with` yet. The
  resolver must treat that as *unknown agent → durable lane*, never as an error.

### 6. A sharper version of the staleness non-negotiable

"Notes go stale, and the format must say so … every entry records the SHA it was written
against" is right, but incomplete. In this chain notes went stale **twice**, in two
different ways: t349→t357 carried **line numbers** (stale relative to a *commit* — a SHA
catches this), and t357→t353 carried a **`git status`** reading (stale relative to a
*moment* — a SHA does not catch this; the tree hadn't moved, the working state had, via
an `ait syncer` auto-commit). Both notes were confidently wrong rather than hedged, which
is direct evidence that the "untrusted advisory input, never an instruction" posture is
load-bearing rather than boilerplate. Consider distinguishing *tree-relative* claims from
*moment-relative* ones in the entry format; only the first is fixed by a SHA.

### Suggested minimal change

Either (a) add agent type as an explicit resolver axis — discriminate on
`implemented_with`, emit a per-agent target shape, treat unknown/absent as durable-lane —
or (b) add "cross-agent-type live delivery" to **Out of scope** beside cross-host, so the
silence becomes a decision. The durable lane needs neither, but Deliverable 4 should say
it ships per agent tree.
