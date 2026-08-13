---
title: "Gates"
linkTitle: "Gates"
weight: 38
description: "ait gates and ait gate — run, inspect, sign off, and reconcile task verification gates"
depth: [advanced]
---

A **gate** is a named check a task must satisfy before it can archive — a build
that must pass, a test suite that must be green, a risk evaluation that must have
been done, a review a human must sign off. A task declares the gates it must
satisfy in its `gates:` frontmatter field, and the framework records every gate
run in the task's ledger. The [task file format](../../development/task-format/)
documents the `gates` / `active_gates` fields; the registry of available gates
lives in `aitasks/metadata/gates.yaml`.

Two commands operate on gates:

- **`ait gates`** (plural) works on a task's gate set as a whole — run them,
  list them, show their state — plus `sync-registry`, which maintains the
  registry itself.
- **`ait gate`** (singular) acts on one named gate — sign it off, mark it
  failed, read its log.

```bash
ait gates run 42                       # Run the task's gates
ait gates status 42                    # Show the recorded state of each gate
ait gates list 42                      # List the gates the task declares
ait gates unlocked 42                  # Which gates could run right now
ait gates sync-registry --dry-run      # Preview a registry reconcile
ait gate pass 42 review_approved       # Sign off a human gate
ait gate fail 42 lint --reason "..."   # Record a manual failure
ait gate log 42 build_verified         # Read the last run's log
```

> **From a code agent:** [`/aitask-run-gates`]({{< relref "/docs/skills/aitask-run-gates" >}})
> drives the same orchestrator as `ait gates run` and explains the outcome in
> prose — which gate blocks, what to do next, whether the task can archive.
> Gates whose verifier is a procedure an agent must carry out have their own
> skills, such as
> [`/aitask-gate-docs-updated`]({{< relref "/docs/skills/aitask-gate-docs-updated" >}}).

## ait gates run

Dispatches the verifiers for every machine gate that is runnable right now,
within each gate's retry budget, observes human gates without signalling them,
and stops. This is the command that actually *executes* a task's gates.

```bash
ait gates run 42                    # Run every runnable gate
ait gates run 42 --gate tests_pass  # Force a single named gate
ait gates run 42 --dry-run          # Show what would be dispatched
```

| Option | Description |
|--------|-------------|
| `--gate <name>` | Run only this gate. Reports rather than runs if the gate is not in the task's active set or its predecessors are unsatisfied |
| `--dry-run` | Print what would be dispatched (unlocked / machine / human) and change nothing |

Output is one line per gate, plus a summary:

| Line | Meaning |
|------|---------|
| `No gates declared; nothing to do.` | The task has not opted into the gate system |
| `  <gate>: pass (attempt 1)` | The verifier ran and succeeded |
| `  <gate>: fail (attempt 2)` | The verifier ran and failed — an ordinary, recorded result |
| `  <gate>: skip` | Not applicable (for example, no command configured for it) |
| `  <gate>: pending — awaiting human signal` | A human gate; sign it with `ait gate pass` |
| `  <gate>: blocked: upstream <a>, <b> not satisfied` | An earlier gate must pass first |
| `  <gate>: blocked: exhausted (retry budget spent)` | Out of retries — the gate is **unsatisfied** |
| `  <gate>: blocked: no verifier configured (deferred)` | The registry has no verifier for this gate — see [sync-registry](#ait-gates-sync-registry) |
| `All gates satisfied. Task ready for archive (suggest status: Done — not auto-applied).` | Everything passed |

**`ait gates run` exits 0 for every completed run.** A gate that fails is a
*recorded result*, not a process error, so a non-zero exit means something broke
in the tooling itself (the task could not be resolved, Python is unavailable, the
registry path is wrong) rather than "a gate failed". Read the per-gate lines to
learn the outcome.

## ait gates list, status, unlocked

Three read-only views of the same task:

```bash
ait gates list 42       # Declared intent: the gates the task asks for
ait gates status 42     # Derived state: the latest recorded run of each gate
ait gates unlocked 42   # Runnable right now, one gate per line
```

`list` prints `<gate> [<type>] - <description>` from the registry, or
`(no gates declared)`. `status` prints `<gate>: <status> (attempt <n>, run
<run-id>)` — the most recent run wins. Both exit 0.

## ait gate pass

Signs off a **human** gate. This is the reviewer's command: it records that a
person approved something, so a coding agent must never run it on your behalf.

```bash
ait gate pass 42 review_approved
ait gate pass 42 merge_approved
```

It writes a witness file recording the signer, timestamp, hostname, and a digest
of the code being approved, then records the pass through the gate orchestrator.
Output is one of:

```
Signed gate 'review_approved' for t42: .aitask-gates/t42/review_approved.signed
Re-signed gate 'review_approved' for t42 (witness refreshed): …
```

**Signatures are bound to the code they approved.** A witness stamped against a
different code state does not carry over — the gate returns to pending, so an
approval cannot be quietly reused against changes the reviewer never saw.

The command refuses, with a message, in three cases:

| Situation | Why |
|-----------|-----|
| The gate is not in `aitasks/metadata/gates.yaml` | Nothing to sign |
| The gate is a machine gate | Machine gates are recorded by their verifier — use `ait gates run` |
| The gate is human but has no file-touch signal | An attended-only checkpoint (for example `plan_approved`), signed during the workflow itself |

## ait gate fail

Records a manual failure for a gate — used when a gate cannot pass for a reason
outside the current change, and you want that recorded rather than silently
retried.

```bash
ait gate fail 42 build_verified --reason "pre-existing breakage on main"
```

## ait gate log

Prints the sidecar log of a gate's most recent run.

```bash
ait gate log 42 build_verified
```

It **exits 0 even when there is no log**, printing `(no sidecar log recorded for
gate '<gate>' on t42)` instead — so it is safe to call unconditionally.

*(`ait gate append` also exists. It is the low-level ledger writer used by gate
verifiers, not a command you normally run by hand.)*

## ait gates sync-registry

Reconciles this project's `aitasks/metadata/gates.yaml` against the framework's
own gate reference. Use it when a gate is registered in your project but is
missing the fields that make it runnable — most visibly, a gate with no
`verifier`, which can never pass and therefore blocks archival forever.

```bash
ait gates sync-registry --dry-run   # Preview: report only, change nothing
ait gates sync-registry             # Apply the fills, report the rest
```

| Option | Description |
|--------|-------------|
| `--dry-run` | Report what would change without writing the file |
| `--registry <file>` | Reconcile a registry other than `aitasks/metadata/gates.yaml` |
| `--reference <file>` | Compare against a reference other than the framework's own |

The `AIT_GATES_REFERENCE` environment variable selects an alternate reference
file for the whole command, equivalent to passing `--reference`.

### What it changes — and what it refuses to change

`sync-registry` **only fills in keys that are absent.** A key that is present
with a different value is *reported and left alone* — your local customization
is never overwritten. Comments and formatting in the file are preserved exactly.
Execution profiles are read (so a profile referring to an unknown gate is
reported) but never edited.

Every run prints a report; each line is one of:

| Line | Meaning |
|------|---------|
| `FILLED:<gate>.<key>=<value>` | The key was missing and has been filled in from the reference |
| `NEW_GATE:<gate>` | A whole gate block was missing and has been appended |
| `CONFLICT:<gate>.<key>:<project>\|<reference>` | Your value differs from the reference — left untouched, decide manually |
| `PROFILE_UNKNOWN:<profile>.<key>:<gate>` | A profile declares a gate with no registry entry (report only) |
| `NOOP` | Already in sync |

**`NOOP` means "checked, and in sync"** — it is never printed because something
could not be read. A registry the command cannot parse produces an error and a
non-zero exit, never a false all-clear.

**Review the fills before committing.** Filling `timeout_seconds` gives a
previously unbounded gate a wall-clock ceiling, and filling
`blocks_dependents: true` makes the gate hold dependent tasks until it passes.
Both show up as `FILLED:` lines — run `--dry-run` first when that matters.

### Nothing is committed

`sync-registry` **never commits.** A registry change is worth reviewing, so the
command leaves the edit in your working tree and prints a reminder naming the
command to stage it:

```
Warning: registry updated but NOT committed — review it, then: ./ait git add aitasks/metadata/gates.yaml
```

The reminder appears only when the file actually changed.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | The run completed — whether it was a `NOOP`, applied fills, or reported conflicts |
| `3` | Could not read the registry or the reference (missing, unreadable, not valid UTF-8, no `gates:` section) |
| `4` | Read it, but the parse cannot be trusted to edit safely (duplicate gate names, mis-indented fields, a truncated mapping) |
| `5` | Another sync holds the registry lock — nothing was written |
| `6` | The file was written but failed its own verification afterwards |

A completed run always exits 0, so a script cannot mistake "I reconciled some
keys" for a failure.

## When to run sync-registry

Run it when a gate cannot pass because the registry never told the framework how
to check it. Three symptoms point here:

- Picking a task prints this warning:

  ```
  Warning: materialize-active: active gate 'risk_evaluated' has no verifier configured in
  aitasks/metadata/gates.yaml — it will block archival. Run `ait gates sync-registry` to
  reconcile the registry.
  ```

- `ait gates run` reports `blocked: no verifier configured (deferred)`.
- A task refuses to archive because a declared gate never reaches `pass`.

In each case, run `ait gates sync-registry --dry-run` to see what is missing,
then apply it, review the diff, and stage the registry with `./ait git add
aitasks/metadata/gates.yaml`.

---

**Next:** [Issue Integration & Utilities]({{< relref "/docs/commands/issue-integration" >}})
