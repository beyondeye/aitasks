---
name: aitask-run-gates
description: Run a task's declared gates — the conversational front of the headless gate orchestrator engine. Dispatches unlocked machine-gate verifiers within their retry budgets, observes human gates without self-signalling, and reports.
---

## Workflow

This skill is the **conversational front** of the gate orchestrator engine
(`lib/gate_orchestrator.py`, wrapped by `aitask_run_gates.sh`). It runs a task's
declared `gates:` and narrates the outcome. It is the headless twin of
`ait gates run <task-id>` — **it never forks the engine logic**; it shells the
same wrapper the autonomous lane and `ait gates run` use.

Use `/aitask-run-gates <task-id>` to drive a gated task's verification passes
interactively. For pure resume (re-enter an in-flight task at the right
workflow step) use `/aitask-resume <task-id>`; that skill calls this engine when
asked to run a gate.

### Step 0: Parse arguments

Invocation: `/aitask-run-gates <task-id> [--gate <name>] [--dry-run]`

- `<task-id>` (**required**) — a parent id (`16`) or child id (`16_2`).
- `--gate <name>` (optional) — force-run a single gate: re-runs it even if it
  already passed and overrides its retry budget, provided its predecessors are
  satisfied. Ignores parallel fan-out.
- `--dry-run` (optional) — report the decision tree (unlocked / machine / human
  sets) without running any verifier or appending to the ledger.

If no `<task-id>` is given, display
`Usage: /aitask-run-gates <task-id> [--gate <name>] [--dry-run]` and stop.

### Step 1: Run the engine

Shell the wrapper, forwarding the parsed flags verbatim:

```bash
./.aitask-scripts/aitask_run_gates.sh run <task-id> [--gate <name>] [--dry-run]
```

The engine reads the task's declared `gates:` and `aitasks/metadata/gates.yaml`,
derives current state from the `## Gate Runs` ledger, computes the unlocked set,
runs the unlocked **machine**-gate verifiers in parallel within their retry
budgets (`max_parallel_gates` from the active profile), observes **human** gates
(appends `pass` if the `file-touch` signal exists, else `pending` — it NEVER
self-signals), applies the stopping heuristic for deterministic repeated
failures, and stops. All state is derived from the ledger; the engine makes no
frontmatter writes.

To see only which gates are runnable right now, use:

```bash
./.aitask-scripts/aitask_run_gates.sh unlocked <task-id>
```

### Step 2: Narrate the result

Relay the engine's report to the user and interpret it:

- **"All gates satisfied. Task ready for archive."** — every declared gate is
  `pass` or `skip`. Suggest the task can be archived (e.g. via `/aitask-pick
  <id>` Check 4, or the normal post-implementation flow). Do **not** auto-apply
  `status: Done`.
- **A gate reports `pending` (human)** — a human gate is awaiting its signal.
  Explain the next human action: the reviewer creates the signal target (the
  `signal_target` path in `aitasks/metadata/gates.yaml`). **Do NOT create the
  signal yourself, suggest automating it, or bypass it** — this is a
  non-negotiable autonomy control. Signal *creation* tooling (`ait gate pass`)
  arrives in a later child (t635_15); for now, surface the pending state and stop.
- **A gate reports `exhausted` (retry budget / stopping heuristic)** — the
  machine gate failed deterministically. Point the user at `ait gate log
  <task-id> <gate>` for the sidecar log, and explain that a code fix + re-run is
  needed (the stopping heuristic detects when nothing changed since the last
  failure, so it won't burn the budget on an unchanged tree).
- **A gate reports `error` / `malformed`** — the verifier itself failed, or
  self-reported a status contradicting its exit code (the exit code is
  authoritative). Surface it; investigate the verifier.

This skill is advisory + orchestration only: it runs the engine and reports. It
does not edit the task's frontmatter, merge branches, or archive.

---

## Notes

- **One engine, not two.** `ait gates run`, this skill, `aitask-resume` (when
  asked to run a gate), and the autonomous lane all call
  `aitask_run_gates.sh` → `lib/gate_orchestrator.py`. None re-derive the
  unlocked-set, retry, or stopping-heuristic logic.
- **Verifier contract.** Machine-gate verifiers are commands invoked as
  `<verifier> <task-id> <attempt> <run-id>` with exit codes `0=pass 1=fail
  2=skip 3=error` (`4=pending` is human-gate-only). Author new ones from the
  `aitask-gate-template` skill.
- **Human gates: read-side only (t635_11).** The engine observes a `file-touch`
  signal; it never creates one. See `aidocs/gates/aitask-gate-framework.md`.
