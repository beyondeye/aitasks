---
title: "Gate rules"
linkTitle: "Gate rules"
weight: 50
description: "The rules behind gates: how a task's enforced gate set is derived and stored, how gate results are recorded, and when gates let a task archive or release its dependents."
depth: [advanced]
---

These are the rules that decide which gates a task is held to, how each gate's
results are recorded, and when gates let the task archive. For what a gate is
and why gates exist, see the [Gates concept page]({{< relref "/docs/concepts/gates" >}}).
The fields named here are listed in the
[task file format]({{< relref "/docs/development/task-format" >}}#frontmatter-fields).

## Declared gates and the enforced set

Each task carries two sets of gates:

- **`gates:`** is the set the task asks for. It is declared intent, written by
  you or injected from an execution profile when the task is created.
- **`active_gates`** is the set the framework enforces. It is derived: the
  framework writes it, and nobody edits it by hand.

An execution profile decides which gate machinery its workflow actually runs.
That limit is the profile's **ceiling**, set by its `rendered_gates` key, which
defaults to the profile's `default_gates`. A task's declared gates are resolved
against the ceiling, and only the intersection is enforced:

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
            active_gates_digest:   <digest of the three inputs>
```

The four `active_gates*` fields form one tuple and are always written together.
`active_gates_filtered` keeps the difference visible: a gate listed there was
asked for and deliberately not enforced under this profile. It blocks nothing,
and it stays on record.

Three cases follow from these rules:

- **An empty enforced set is a real answer.** A profile whose ceiling excludes
  everything a task declares produces `active_gates: []`. The framework writes
  that empty list rather than leaving the field out, because a missing tuple
  means the task is enforced from its raw `gates:` field (see
  [the digest](#the-digest)).
- **`gates: []` is an opt-out.** An explicit empty list says "this task has no
  gates", and it is never backfilled from a profile's `default_gates`. Only a
  task with no `gates:` key at all takes the profile's defaults.
- **A manual-verification task keeps only the gates its checklist can reach.**
  The rest are dropped from both lists, because they could never be satisfied.

## When the enforced set is computed

The enforced set is computed when the task is claimed, that is, when you pick
it, and stored on the task. It is not recomputed on every read. Picking the
task again, including re-picking a task already in flight, derives it afresh
under whatever profile that pick uses.

Which gates a task is held to depends on the profile, and a profile is chosen
per session: the same task can be picked under one profile today and another
tomorrow. Because the set is fixed at claim time, everything that enforces
gates reads the same answer for the whole session, and a change of profile
takes effect at the next pick instead of half-way through one.

If the enforced set cannot be computed because the profile is missing or
unreadable, any previously stored tuple is cleared, and the raw `gates:` field
governs until a pick computes the set again.

## The digest

`active_gates_digest` stops a stored enforced set from outliving the inputs it
was computed from. It has one part for each input to the computation:

1. the task's raw `gates:` field, including whether the key exists at all;
2. the profile's `default_gates` and `rendered_gates`;
3. the stored `active_gates` and `active_gates_filtered` values themselves.

Anything that reads the enforced set checks parts 1 and 3 first. Both can be
checked from the task file alone, and between them they catch the two ways a
stored tuple goes wrong: `gates:` was edited after the task was picked, or
`active_gates` was edited by hand. Either way the tuple, its list of filtered
gates included, is treated as absent, and enforcement falls back to the raw
`gates:` field until the next pick computes the tuple again. Part 2 needs a
profile to check, so a change to the profile itself is caught by the
re-derivation at the next pick.

Falling back to declared intent can enforce a gate the profile would have
filtered, which over-blocks until the next pick, but a hand-edited enforced set
can never quietly enforce less than the task asked for.

## Kinds of gate

The [registry](#the-registry) classifies each gate by what can satisfy it:

- **Machine** gates are verified by a program: the build, the test suite, the
  linter, the risk check. A verifier runs, and its exit status is the verdict.
- **Human** gates wait for a person, and an agent never supplies that approval
  itself. The three shipped human gates do not all behave alike:
  - `plan_approved` is a checkpoint recorded only in an attended session (a code
    agent session with a person answering it). It is recorded from the
    interactive plan approval, and `ait gate pass` refuses it, because there is
    nothing to sign.
  - `review_approved` and `merge_approved` are recorded the same way in an
    attended session, and can also be signed later with
    [`ait gate pass`]({{< relref "/docs/commands/gates" >}}#ait-gate-pass). That
    signature is bound to the code it approved: if the code changes after
    signing, the gate counts as outstanding again and asks to be re-signed.
- **Procedure-backed** gates (`kind: procedure`) are machine gates whose work is
  a procedure carried out by an agent instead of a command. `docs_updated` is
  one: its verifier is a skill that inspects the change and updates
  documentation. The headless gate engine (`ait gates run`, which runs
  verifiers without a code agent) cannot run a skill, so it defers the gate and
  an attended agent runs it; see
  [`/aitask-gate-docs-updated`]({{< relref "/docs/skills/aitask-gate-docs-updated" >}}#why-it-runs-where-it-runs).

## The ledger

What happened to each gate is recorded in the task file itself, in an
append-only `## Gate Runs` section. Every run appends one block whose first line
carries the gate, the time, the status and, once the run has finished, its
attempt number. A re-run appends a new block, and an old one is never
rewritten.

A gate's current state is derived from that ledger, where the latest block for
the gate wins. It is never copied into another field, so there is no summary to
drift out of step with the history. `pass` and `skip` both count as satisfied:
`skip` means "evaluated, not applicable". It stays distinct from `pass` in the
history and never blocks.

Under a profile with `record_gates: true`, the ledger also records the workflow's own
checkpoints, such as plan approved and review approved, whether or not the task
declares them. Resuming an in-flight task reads those checkpoints to decide how
far the work got; archival reads the enforced gates to decide whether the task
is finished.

## The registry

`aitasks/metadata/gates.yaml` declares how each gate runs; the task declares
which gates apply. For each gate, the registry sets:

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

[`ait gates sync-registry`]({{< relref "/docs/commands/gates" >}}#ait-gates-sync-registry)
reconciles a project's registry against the one the framework ships.

## Retry budgets

A failed machine gate is re-run up to `max_retries` more times. Only `fail` and
`error` spend that budget, so re-running a gate that already passed costs
nothing. Once the budget is spent the gate reports itself exhausted and waits
for a person. A machine gate also stops early, with budget left, once its two
most recent runs both failed on the code as it is now; a change to the code
makes it eligible again. Human gates do not retry.

To run an exhausted gate again after fixing its cause, force it with
`ait gates run <task> --gate <name>`: a forced run ignores the spent budget, and
the gate's predecessors must still be satisfied (see
[`/aitask-run-gates`]({{< relref "/docs/skills/aitask-run-gates" >}}#arguments)).
This applies only to gates whose verifier is a command: forcing a
procedure-backed gate such as `docs_updated` does not run its skill and records
an `error`.

## The unlock order

By default the order is linear: each enforced gate unlocks the next one in the
task's list. As soon as any enforced gate declares `unlocks:` in the registry,
the registry drives the order instead, and a gate without `unlocks:` unlocks
nothing. That is what lets two gates fan out and run side by side.

A gate is ready to run when every gate that unlocks it is satisfied, it is not
yet satisfied itself, and it has budget left. Ready machine gates run in
parallel, up to the profile's `max_parallel_gates`.

## Archival

A task with gates archives only when every enforced gate is satisfied. An
approval whose signature no longer matches the code counts as unsatisfied, and
a gate the profile filtered out never blocks archival while the stored enforced
set is valid (see [The digest](#the-digest)). The archive command refuses a
task with an unmet gate unless it is explicitly overridden, so the rule holds
for every caller, the pick workflow included. The override is the archive
script's `--ignore-gates` flag:

```bash
./.aitask-scripts/aitask_archive.sh --ignore-gates <id>
```

## Unblocking dependents

Unblocking a task's dependents asks a narrower question. Some gates, those the
registry marks `blocks_dependents` such as the build, the tests, and review and
merge approval, decide when the work is usable by others; the rest are
sign-offs that can finish later. A dependent unblocks as soon as the upstream
task's enforced `blocks_dependents` gates are satisfied, even while its other
gates are still pending and the task is still active.

A task's `also_blocks_dependents` field adds gates to that set for that one
task. An addition the profile filtered out is dropped, so it holds back no
dependents while the stored enforced set is valid. A task whose enforced gates include none
of these releases its dependents the ordinary way, when it archives.
