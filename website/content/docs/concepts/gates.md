---
title: "Gates"
linkTitle: "Gates"
weight: 85
description: "Named checks a task must satisfy before it archives — what a task declares, what the framework enforces, and why the enforced set is fixed when the task is picked."
depth: [advanced]
---

## What it is

A **gate** is a named check a task must satisfy before it can archive: a build
that must pass, a test suite that must be green, a risk evaluation that must have
been done, a review a person must sign off. Gates sit beside the task's `status`
rather than inside it — `status` stays the coarse lifecycle, and gates only come
into play while the task is `Implementing`.

Each task carries two sets of gates, and most of what is surprising about gates
comes from confusing them:

- **`gates:`** — the gates the task *asks for*. This is declared intent, written
  by you or injected from an execution profile when the task is created.
- **`active_gates`** — the gates the framework *enforces*. This is derived: the
  framework writes it, and nobody edits it by hand.

### Declared intent versus the enforced set

An execution profile decides which gate machinery its workflow actually runs —
the profile's **ceiling**. A task's declared gates are resolved against that
ceiling, and only the intersection is enforced:

```text
  task      gates: [risk_evaluated, docs_updated]        declared intent
               │
               │   no gates: key at all → the profile's default_gates
               ▼
  profile   rendered_gates                                the ceiling
            (defaults to default_gates)
               │
               ▼
  task      active_gates:          [risk_evaluated]       enforced
            active_gates_filtered: [docs_updated]         declared, not enforced
            active_gates_profile:  fast                   which profile decided
            active_gates_digest:   <gates>.<profile>.<outputs>
```

The four `active_gates*` fields form one tuple and are always written together.
`active_gates_filtered` keeps the difference visible: a gate listed there was asked
for and deliberately not enforced under this profile. It blocks nothing, but it is
not forgotten.

Two cases read oddly until you know them:

- **An empty enforced set is a real answer.** A profile whose ceiling excludes
  everything a task declares produces `active_gates: []`. The framework writes
  that empty list rather than leaving the field out, because a missing tuple means
  something different (see the digest, below).
- **`gates: []` is an opt-out.** An explicit empty list says "this task has no
  gates", and it is never backfilled from a profile's `default_gates`. Only a task
  with no `gates:` key at all takes the profile's defaults.

A manual-verification task keeps only the gates its checklist can reach. The rest
are dropped from both lists, because they could never be satisfied.

### A snapshot taken when the task is picked

The enforced set is computed when the task is claimed — when you pick it — and
stored on the task. It is not recomputed on every read. Picking the task again,
including re-picking a task already in flight, derives it afresh under whatever
profile that pick uses.

That timing is the point. Which gates a task is held to depends on the profile,
and a profile is a per-session choice: the same task can be picked under one
profile today and another tomorrow. Fixing the set at claim time means everything
that enforces gates reads the same answer for the whole session, and a change of
profile takes effect at the next pick rather than half-way through one.

If the enforced set cannot be computed — the profile is missing or unreadable —
any previously stored tuple is cleared rather than left in charge. An old
profile's enforcement never quietly governs a new session.

### The digest, and what happens when it does not match

`active_gates_digest` is three 12-character hashes joined by dots, one over each
input to the computation:

1. the task's raw `gates:` field, including whether the key exists at all;
2. the profile's `default_gates` and `rendered_gates`;
3. the stored `active_gates` and `active_gates_filtered` values themselves.

Anything that reads the enforced set checks parts 1 and 3 first. Both can be
checked from the task file alone, and between them they catch the two ways a
stored tuple goes wrong: `gates:` was edited after the task was picked, or
`active_gates` was edited by hand. Either way the tuple is treated as absent, and
**enforcement falls back to the raw `gates:` field** until the next pick
re-materializes it.

The fallback errs in one direction on purpose. Falling back to declared intent can
enforce a gate the profile would have filtered — over-blocking until the next
pick — but a hand-edited active set can never quietly enforce less than the task
asked for. Part 2 needs a profile to check, so a change to the profile itself is
caught by the re-derivation at the next pick.

### Kinds of gate

The registry classifies each gate by what can satisfy it:

- **Machine** gates are verified programmatically — the build, the test suite,
  the linter, the risk check. A verifier runs, and its exit status is the verdict.
- **Human** gates wait for a person, and an agent never supplies that approval
  itself. The three shipped human gates do not all behave alike:
  - `plan_approved` is an attended-only checkpoint. It is recorded from the
    interactive plan approval, and `ait gate pass` refuses it — there is nothing
    to sign.
  - `review_approved` and `merge_approved` are recorded the same way in an
    attended session, but can also be signed asynchronously with
    `ait gate pass`. That signature is bound to the code it approved: if the code
    changes after signing, the gate counts as outstanding again and asks to be
    re-signed.
- **Procedure-backed** gates (`kind: procedure`) are machine gates whose work is a
  procedure rather than a command. `docs_updated` is one: its verifier is a skill
  that inspects the change and updates documentation. The headless gate engine
  cannot run a skill, so it defers the gate and an attended agent runs it.

### The ledger

What happened to each gate is recorded in the task file itself, in an
append-only `## Gate Runs` section. Every run appends one block whose first line
carries the gate, the time, the status and — once the run has finished — its
attempt number. A re-run appends a new block; an old one is never rewritten.

A gate's current state is **derived** from that ledger — the latest block for the
gate wins — and is never copied into another field, so there is no summary to
drift out of step with the history. `pass` and `skip` both count as satisfied:
`skip` means "evaluated, not applicable", and it stays distinct from `pass` in the
history without ever blocking.

Under a profile that records gates, the ledger also witnesses the workflow's own
checkpoints — plan approved, review approved — whether or not the task declares
them. Resuming an in-flight task reads those checkpoints to decide how far the
work got; archival reads the enforced gates to decide whether it is finished. Both
questions use the same ledger, and they are kept separate.

### The registry

`aitasks/metadata/gates.yaml` declares *how* each gate runs; the task declares
*which* gates apply. Per gate, the registry sets:

| Key | What it controls |
|---|---|
| `type` | `machine` or `human` |
| `kind` | `procedure` for a gate whose verifier is a skill rather than a command |
| `verifier` | what runs the check; empty for a gate that is recorded rather than run |
| `max_retries` | how many re-attempts a failure allows |
| `unlocks` | which gates this one unlocks when it passes |
| `timeout_seconds` | the wall-clock limit for one machine-gate run |
| `signal`, `signal_target` | how a human gate's signature is detected |
| `blocks_dependents` | whether this gate must pass before the task's dependents unblock |

A project's registry is reconciled against the one the framework ships with
`ait gates sync-registry`, which fills in missing keys and reports — never
overwrites — values that differ.

### Retry budgets and the unlock order

A failed machine gate is re-run up to `max_retries` more times. Only `fail` and
`error` spend that budget, so re-running a gate that already passed costs
nothing. Once the budget is spent the gate reports itself exhausted and waits for
a person. Human gates do not retry.

Gates run in an order. By default it is linear: each enforced gate unlocks the next
one in the task's list. As soon as any enforced gate declares `unlocks:` in the
registry, the registry drives the order instead, and a gate without `unlocks:`
unlocks nothing — which is what lets two gates fan out and run side by side. A
gate is ready to run when every gate that unlocks it is satisfied, it is not yet
satisfied itself, and it has budget left. Ready machine gates run in parallel, up
to the profile's `max_parallel_gates`.

### Archival and unblocking

A task with gates **archives only when every enforced gate is satisfied**, and an
approval whose signature no longer matches the code counts as unsatisfied. A gate
the profile filtered out can never block archival. The archive command refuses a
task with an unmet gate unless it is explicitly overridden, so the rule holds for
every caller, not just the pick workflow.

Unblocking a task's dependents asks a narrower question. Some gates — those the
registry marks `blocks_dependents`, such as the build, the tests, and review and
merge approval — decide when the work is usable by others; the rest are sign-offs
that can finish later. A dependent unblocks as soon as the upstream task's
enforced `blocks_dependents` gates are satisfied, even while its other gates are
still pending and the task is still active. A task's `also_blocks_dependents`
field adds gates to that set for that one task; an addition the profile filtered
out is dropped, so a filtered gate holds back neither archival nor dependents. A
task whose enforced gates include none of these releases its dependents the
ordinary way, when it archives.

## Why it exists

A single `status` field cannot say "the build passed, the review is pending and
the docs still need updating". Those are independent facts that finish at
different times. Gates hold them separately, in the task file, where they survive
a crashed session and are visible from every machine that syncs the task data.

Separating declared intent from the enforced set is what lets one task move
between workflows. The task keeps saying what it wants, each profile decides what
its workflow can actually check, and the gap between the two is recorded rather
than silently lost. Fixing the enforced set at claim time keeps that decision
stable for a whole session, and the digest stops a stored decision from outliving
the inputs it was made from.

## How to use

Declare gates when you create a task — the batch `--gates` flag, described on the
[`/aitask-create`]({{< relref "/docs/skills/aitask-create" >}}) page — or let an
execution profile's `default_gates` declare them for you. The rest is the framework's job:
the enforced set is written when you pick the task, gates are recorded as the
workflow reaches them, and archival waits for them.

To act on gates directly — run them, list their state, sign a human gate, read a
run's log — use [`ait gates` and `ait gate`]({{< relref "/docs/commands/gates" >}}).
[`/aitask-run-gates`]({{< relref "/docs/skills/aitask-run-gates" >}}) runs the
machine gates that are ready, and the board shows each in-flight task's gates
against its enforced set.

## See also

- [`ait gates` and `ait gate`]({{< relref "/docs/commands/gates" >}}) — the command reference: run, list, sign off, and reconcile the registry.
- [`/aitask-run-gates`]({{< relref "/docs/skills/aitask-run-gates" >}}) — the conversational front of the gate engine.
- [`/aitask-gate-docs-updated`]({{< relref "/docs/skills/aitask-gate-docs-updated" >}}#why-it-runs-where-it-runs) — the procedure-backed gate, and why only an attended agent can run it.
- [Task file format]({{< relref "/docs/development/task-format" >}}#frontmatter-fields) — the `gates`, `also_blocks_dependents` and `active_gates*` field rows.
- [Board reference]({{< relref "/docs/tuis/board/reference" >}}#gate-progress) — how the board counts satisfied gates against the enforced set.
- [Risk evaluation]({{< relref "/docs/workflows/risk-evaluation" >}}) — the planning step the `risk_evaluated` gate verifies.
- [Execution profiles]({{< relref "/docs/concepts/execution-profiles" >}}) — what a profile is; each one also sets its workflow's gate ceiling, described above.
