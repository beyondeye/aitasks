# Output from agent: initializer_bootstrap

--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: "Stateful multi-pass task execution via named gate checkpoints: declared in frontmatter, logged as markers"
proposal_file: br_proposals/n000_init.md
created_at: "2026-04-27 19:47"
created_by_group: bootstrap
reference_files:
  - aidocs/gates/aitask-gate-framework.md
  - aitasks/t635_gates_framework.md
requirements_stateful_reentry: "Re-running a skill on the same task must skip already-done work and resume from the first unmet gate"
requirements_multi_dimensional_state: "Tests, review, and docs states must be independently trackable and passable, not collapsed into one linear status"
requirements_parallel_verification: "Machine gates with no dependency relationship must be runnable concurrently"
requirements_local_file_authority: "Task file must be the single source of truth; remote surfaces are read-only projections"
requirements_human_gate_safety: "Agents must never create signals for human gates — non-negotiable autonomy control"
assumption_local_file_authority: "Local task file is the authoritative gate state store; remote issue tracker is a projection only"
assumption_additive_adoption: "Tasks without a gates field behave exactly as today — the framework is fully backward-compatible"
assumption_no_persisted_gate_status: "No gates_passed or gates_failed fields exist; status is derived from Gate Runs section on every read"
assumption_marker_first_format: "Gate run records are marker-first blockquotes — self-delimiting and grep-friendly without custom parsing"
assumption_task_gate_list_authoritative: "Task explicit gates list is authoritative; default_gates in registry used only when task has no gates field"
assumption_human_gate_non_automatable: "Human gate signals must come from humans; agents must never bypass or automate signal creation"
assumption_orchestrator_stateless: "The orchestrator re-derives all gate state on every invocation; it holds no cross-invocation state of its own"
component_gate_registry: "aitasks/metadata/gates.yaml — per-gate config: verifier skill, type, max_retries, unlock DAG, signal config"
component_orchestrator_skill: "aitask-run-gates — stateless re-entrant skill that reads task + registry, computes unlocked set, and dispatches verifiers"
component_verifier_skills: "aitask-gate-<name> skill family — individual gate checkers following a standard five-step contract"
component_gate_runs_section: "append-only ## Gate Runs section in task body — the event log from which derived gate state is computed"
component_gate_cli: "scripts/gates.sh — ait gates/gate subcommands: list, status, unlocked, run, append, pass, fail, log"
component_sidecar_logs: ".aitask-gates/<task-id>/ — per-run verifier output logs and remote mirror state cache"
component_remote_projection: "label mirror + singleton comment + event comments via existing multi-platform dispatcher"
tradeoff_marker_vs_fences: "Marker-first blockquotes chosen over paired fences — grep-friendly and avoids mismatched-closer bug on back-to-back same-gate runs"
tradeoff_derived_vs_persisted_state: "Gate status derived from event log on every read rather than stored as fields — eliminates drift at cost of re-parsing"
tradeoff_local_authority_vs_remote_feedback: "Local file stays authoritative; one narrow carve-out for reading authorized comment signals from human gates"
tradeoff_bash_vs_python_parser: "Primary gate-run parser is bash/awk; Python escape hatch available when awk edge cases arise (AIT_GATES_BACKEND=python)"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview -->
## Overview

A proposal to make aitasks task execution **stateful and multi-pass** by introducing first-class *gates* — named verification checkpoints declared in task frontmatter, implemented by a skill family, orchestrated by a stateless re-entrant skill, and logged as marker-first blockquotes in the task body.

This design adopts OpenShell's stateful re-entry and marker discipline but keeps the authoritative state *inside the local task file* rather than on a remote issue — preserving aitasks's "local file is authority" model. It refines several ideas in the openshell-inspired-ideas backlog (notably ideas 3, 4, and 10) by proposing a concrete substrate they can all build on.

Confidence is `medium` because this is a design proposal, not yet implemented.

### Motivation

**Current state.** aitasks task files carry a single linear `status` enum: `Ready | Editing | Implementing | Postponed | Done | Folded`. Skills follow a linear procedure and hold no re-entry state of their own. If verification fails halfway through, there is no first-class way to record "unit tests passed but integration tests failed, needs another pass" on the task itself — the state lives only in the skill's in-conversation memory.

**The problem.** This blocks three patterns:

1. **Safe re-entry.** Re-running a skill on the same task should skip work that is already done and resume from the first unmet requirement. Today, re-running a skill either starts from scratch or relies on the agent reading the conversation — neither is durable.
2. **Multi-dimensional state.** "Tests pass" and "human review approved" and "docs updated" are orthogonal; they should be expressible independently, not collapsed into a single linear `status`.
3. **Parallel verification.** Some checks can run concurrently (lint and unit tests, for instance). A linear state machine forces them to serialize.

**The key insight.** What OpenShell calls a state machine is, structurally, a **gate set** — a list of named requirements that must be satisfied before a task can advance. If aitasks represents the gate set directly in the task file, every OpenShell pattern (re-entry, hard gates, marker discipline, bounded retry) ports naturally, and the framework stays local-first.
<!-- /section: overview -->

<!-- section: architecture -->
## Architecture

```
        task file (authoritative)
        ┌──────────────────────────────────┐
        │  frontmatter:                     │
        │    status: Implementing           │  ← unchanged coarse lifecycle
        │    gates: [tests, review, docs]   │  ← NEW — declared gate set
        │                                    │
        │  body:                             │
        │    ## Plan                         │
        │    ...                             │
        │                                    │
        │    ## Gate Runs                    │  ← NEW — append-only event log
        │    > ✅ gate:tests  run=...        │
        │    > ❌ gate:tests  run=... (1)    │
        │    > ✅ gate:tests  run=... (2)    │
        │    > ⏸ gate:review run=... human   │
        └──────────────────────────────────┘
                        ▲
                        │  reads + appends
                        │
        ┌──────────────────────────────────┐
        │  aitask-run-gates <task-id>      │  ← orchestrator skill
        │  (stateful re-entrant)            │
        └──────────────────────────────────┘
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
       gate:tests  gate:review  gate:docs
       ─────────   ─────────   ─────────
       verifier    verifier    verifier
       skill       (human)     skill
                        ▲
                        │  reads
        ┌──────────────────────────────────┐
        │  aitasks/metadata/gates.yaml     │  ← gate registry
        │  per-gate: verifier, retries,     │
        │   type (machine|human), unlocks    │
        └──────────────────────────────────┘
```

**Separation of concerns.**
- **Task file** declares *which* gates apply (`gates: [...]`) and records *what happened* (Gate Runs section).
- **Gate registry** declares *how* each gate is implemented (verifier skill, retry budget, type, unlock DAG).
- **Orchestrator skill** is stateless: it reads both, computes the next action, delegates, and re-enters.
- **Verifier skills** implement individual gates against a standard contract.

No component holds state across invocations. The task file is the single source of truth; everything else is a projection.
<!-- /section: architecture -->

<!-- section: data_model [dimensions: assumption_*, requirements_*] -->
## Data Model

### 1. Task frontmatter

Add one field, `gates`, to the task frontmatter schema:

```yaml
---
id: t42
title: Add pagination to dataset list endpoint
status: Implementing
priority: normal
effort: M
gates: [tests_pass, review, docs_updated]
# ... existing fields ...
---
```

**Semantics.**
- `gates` is an ordered list of gate names. Ordering defines the *default* sequence (each gate unlocks the next in the list) unless the registry overrides it with an explicit `unlocks:` list.
- The list contains only gate *names*. All other metadata (verifier, retries, type) is resolved from the registry at orchestration time.
- An absent or empty `gates` field means "no gates active" — behaves like today's aitasks.
- **No persisted status fields.** There is deliberately no `gates_passed` or `gates_failed`. Pass/fail/pending status is *derived* from the Gate Runs section on every read. Single source of truth; no drift.

Tasks opt in per-task. A task template can specify a default set (e.g. `default_gates: [tests_pass, review, docs_updated]` in `aitasks/metadata/gates.yaml`), but any task is free to override or omit gates.

### 2. Gate registry — `aitasks/metadata/gates.yaml`

```yaml
# aitasks/metadata/gates.yaml
default_gates: [tests_pass, review, docs_updated]

gates:
  tests_pass:
    verifier: aitask-gate-tests-pass
    type: machine
    max_retries: 3
    # No explicit `unlocks:` → defaults to "next gate in task's gates list"
    description: "Run project test suite (unit + integration); must all pass"
    timeout_seconds: 900

  lint:
    verifier: aitask-gate-lint
    type: machine
    max_retries: 2
    unlocks: [tests_pass]     # lint and tests_pass can run in parallel if both in gates list
    description: "Run project linters and formatters"

  review:
    verifier: aitask-gate-review
    type: human
    max_retries: 0            # human gates do not auto-retry
    signal: file-touch
    signal_target: ".aitask-gates/<task-id>/review.signed"
    description: "Human code review — reviewer signals pass via `ait gate pass <task> review`"
    # Rule repeated verbatim in the verifier skill:
    # "Agents MUST NEVER create the signal for a human gate."

  docs_updated:
    verifier: aitask-gate-docs-updated
    type: machine
    max_retries: 2
    unlocks: []                # terminal gate
    description: "Check whether docs need updating and update them if so"
```

**Registry fields per gate.**

| Field | Required | Purpose |
|---|---|---|
| `verifier` | yes | Skill name invoked to run the gate. Convention: `aitask-gate-<name>`. |
| `type` | yes | `machine` or `human`. Human gates never retry and refuse to self-signal. |
| `max_retries` | yes | Budget for re-attempts after a failure. `0` means "single shot". |
| `unlocks` | no | Explicit list of gate names this gate unlocks on pass. If omitted, default is *the next gate in the task's own `gates` list*. Enables parallel fan-out. |
| `signal` | human only | How the human signals pass: `file-touch`, `label`, or `command`. |
| `signal_target` | human only | Path / label name / command template. `<task-id>` is substituted. |
| `description` | yes | Human-readable purpose, shown in `ait gates list`. |
| `timeout_seconds` | no | Max wall-clock for a single machine-gate run. |

**Unlock DAG semantics.** If no gate in the registry has explicit `unlocks:`, the DAG is linear and identical to the task's `gates:` list order. As soon as any gate specifies `unlocks:`, that gate's successor list is taken from the registry, overriding the list-position default. This lets most gates stay untouched while a few declare parallelism where it matters.

**Runtime rule for parallelism.** A gate is *unlocked* iff (a) every gate that has it in its `unlocks:` list is `pass`, (b) it is not itself already `pass`, and (c) it has not exhausted its retry budget. Multiple unlocked gates may run concurrently. The orchestrator dispatches all unlocked machine gates in parallel; unlocked human gates pend for their signal.

### 3. Gate run marker format — inside the task body

Every gate run appends a **marker-first blockquote** to a dedicated `## Gate Runs` section at the bottom of the task file. The first line carries all queryable metadata; body lines carry a human-readable summary; full output is stored in a sidecar log file referenced from the block.

```markdown
## Gate Runs
<!-- Appended by aitask-run-gates. Do not edit by hand; use `ait gate append` for corrections. -->

> **✅ gate:tests_pass** run=2026-04-15T14:32:01Z status=pass attempt=1 duration=42s
>
> Verifier: `aitask-gate-tests-pass`
> Command: `mise run pre-commit`
> Result: 42 passed, 0 failed
> Log: `.aitask-gates/t42/tests_pass_2026-04-15T14-32-01Z.log`

> **❌ gate:docs_updated** run=2026-04-15T14:33:17Z status=fail attempt=1 duration=8s
>
> Verifier: `aitask-gate-docs-updated`
> Issue: `architecture/endpoints.md` references old schema, needs update
> Log: `.aitask-gates/t42/docs_updated_2026-04-15T14-33-17Z.log`

> **⏸ gate:review** run=2026-04-15T14:42:10Z status=pending type=human
>
> Verifier: `aitask-gate-review`
> Awaiting: `.aitask-gates/t42/review.signed`
> Hint: reviewer runs `ait gate pass t42 review` after review
```

**Format rules.**
- **Marker line** — always the first line of the block, always starts with `> **<icon> gate:<name>**`, always contains `run=<ISO-8601-Z>` and `status=<pass|fail|pending|running|skip|error>`. For machine gates also `attempt=<N>` and `duration=<s>`. Icons: `✅` pass, `❌` fail, `⏸` pending, `🔄` running, `⏭` skip, `⚠` error.
- **Body lines** — prefixed with `> ` (standard markdown blockquote). Blank line (`>` alone) separates the marker from the body.
- **Block terminator** — next `> **` marker line, next `##` heading, or EOF. No closing fence.
- **Always append.** Never rewrite or delete historical gate runs. A re-run produces a new block; `ait gate status` determines *current* status by scanning back-to-front and taking the first block per gate name.
- **Sidecar logs.** Full verifier output lives under `.aitask-gates/<task-id>/<gate>_<iso-timestamp>.log`. Directory is git-ignored by default (profile flag `commit_gate_logs: false`).

**Why marker-first.** Grep-friendly (`grep -n '^> \*\*' task.md`), survives human markdown edits, renders cleanly in any markdown viewer, and does not require a custom parser — the block boundaries are inferable from the next marker line or heading. The decision against paired open/close fences (`>>>>` / `<<<<`) is deliberate: any format with matched delimiters risks mismatch when identical gates run back-to-back.
<!-- /section: data_model -->

<!-- section: orchestrator [dimensions: component_orchestrator_skill] -->
## Orchestrator Skill — `aitask-run-gates`

A **stateful re-entrant skill**: safe to invoke repeatedly on the same task. Each invocation re-derives state from the task file, runs whatever can run, and stops.

### Invocation

```
aitask-run-gates <task-id> [--gate <name>] [--dry-run]
```

- `<task-id>` is the only required argument.
- `--gate <name>` runs a single gate (must be currently unlocked; ignores parallelism fan-out).
- `--dry-run` reports the decision tree without executing any verifier.

### Decision tree (re-entry)

```
Read task file + gate registry
  │
  ├─ No `gates:` field, or empty list?
  │   → Report "No gates declared; nothing to do." STOP.
  │
  ├─ Parse `## Gate Runs` section, build per-gate current-state map
  │   (scan back-to-front, first block per gate name = current state)
  │
  ├─ All gates in pass state?
  │   → Report "All gates passed. Task ready for archive."
  │   → Suggest `status: Done` transition (do not auto-apply).
  │   → STOP.
  │
  ├─ Compute unlocked set:
  │     { g ∈ gates
  │       | all predecessors(g) are pass
  │       ∧ current_state(g) ≠ pass
  │       ∧ attempts(g) < max_retries(g) + 1 }
  │
  ├─ Unlocked set empty?
  │   → Report why each remaining gate is blocked:
  │     - retry budget exhausted → "blocked: exhausted"
  │     - awaiting human signal → "blocked: pending human"
  │     - upstream failed → "blocked: upstream <name> failed"
  │   → STOP.
  │
  ├─ For each unlocked machine gate (in parallel):
  │   → Append `status=running` block
  │   → Invoke verifier skill via Task tool
  │   → Verifier appends final pass/fail block on return
  │
  ├─ For each unlocked human gate:
  │   → Append `status=pending` block if one does not already exist for this run
  │   → Check signal target: exists/set?
  │       ├─ Yes → append `status=pass` block
  │       └─ No  → leave pending block in place
  │
  └─ Re-enter from top if any machine gate just completed
     (bounded by "no new state change since last pass" — stops the loop)
```

### Re-entry contract

The orchestrator guarantees:

1. **Idempotent on no-op.** Running `aitask-run-gates t42` twice in a row with no state change produces the same reports and appends nothing.
2. **Skip-already-passed.** Gates currently in `pass` state are not re-run unless explicitly forced with `--gate <name>`.
3. **Retry within budget.** Failed gates are re-run up to `max_retries + 1` total attempts; the (attempt) counter increments per append.
4. **Stop at pending-human.** The orchestrator never self-signals a human gate.
5. **No partial frontmatter writes.** The orchestrator never touches `gates:` in frontmatter. It only appends to `## Gate Runs`.
6. **Concurrency safety.** Parallel machine-gate execution uses a task-level file lock around appends. Each verifier's append is atomic.
<!-- /section: orchestrator -->

<!-- section: verifier_contract [dimensions: component_verifier_skills] -->
## Verifier Skill Contract

Every gate is implemented by a **`aitask-gate-<name>`** skill, following a standard template.

### Contract

**Input** — positional arguments:
```
<task-id> <attempt-number> <run-id>
```
(`run-id` is an ISO-8601-Z timestamp the orchestrator generates before delegating, so the verifier appends using the same run-id the orchestrator already wrote as `running`.)

**Behavior** — the verifier MUST:

1. Read the task file to understand context (plan, scope, prior runs).
2. Execute its verification logic (run tests, check a file, query a service, etc.).
3. Write detailed output to `.aitask-gates/<task-id>/<gate>_<run-id>.log`.
4. **Append** a terminal marker-first blockquote to `## Gate Runs` with final status (`pass`, `fail`, `skip`, or `error`), via the `ait gate append` helper — not direct markdown editing.
5. Return an exit code: `0` = pass, `1` = fail, `2` = skip (gate does not apply), `3` = error (verifier itself failed).

**Must not:**
- Modify task frontmatter.
- Modify any other gate's Gate Runs entries.
- Create signal files for human gates.
- Auto-suggest retries beyond `max_retries`.

### Template skill

`.claude/skills/aitask-gate-template/SKILL.md` — a scaffold users copy to create new gates. It provides:
- Frontmatter with the standard argument signature.
- A stub `Workflow` section with the five steps above.
- A stub verification block the user replaces with their actual check.
- An example sidecar log write.
- An example `ait gate append` invocation.

Shipping a template is essential: the point of the contract is that a plugin or a user can add a project-specific gate (`security_scan`, `license_check`, `changelog_updated`) in ten minutes without re-reading this proposal.

### Human-gate verifier (special case)

For gates with `type: human`, the verifier skill is a thin wrapper:

1. Check whether the signal exists (per `signal:` and `signal_target:` in the registry).
2. If yes → append `status=pass` block, exit 0.
3. If no → append `status=pending` block (if one does not already exist for this run), exit with code `4 = pending`.

The rule is repeated verbatim in every human-gate verifier and in the registry description:

> **Agents MUST NEVER create the signal for a human gate, suggest automating its creation, or bypass its absence. This is a non-negotiable autonomy control.**

Signal kinds:
- `file-touch` — a file at `signal_target` exists. Human creates it via `ait gate pass <task-id> <gate>`.
- `label` — a label on the linked remote issue/PR (degrades to file-touch if the task has no `issue:` field).
- `command` — a side-effect command the human must run; detection is by a witness file the command writes.
<!-- /section: verifier_contract -->

<!-- section: status_integration -->
## Relationship to Existing `status` Field

**Supplement, not replace.** The `status` enum stays authoritative for the coarse task lifecycle:

```
Ready → Editing → Implementing → Done → (Archive)
                        │
                        │  gates are active only inside this state
                        │
                   ┌────────────┐
                   │  gates:    │
                   │  tests_pass│
                   │  review    │  ← driven by aitask-run-gates
                   │  docs      │
                   └────────────┘
```

Rules:
- A task's gates become active when `status: Implementing` is set. Gates in `Ready` or `Editing` are advisory only (can be run early, do not block).
- When all gates pass, the orchestrator **suggests** `status: Done` but does not auto-apply. Transition remains a human decision (or a profile-gated auto-transition for the `aitask-pickrem` autonomous lane).
- `Postponed` and `Folded` freeze the gate state — re-entering the task unfreezes it, gates re-evaluate from wherever they were.
- Existing skills (`aitask-archive`, monitor TUI, board views) keep reading `status` and do not need to know about gates.

This is additive. An aitasks install that never declares `gates:` behaves exactly as today.
<!-- /section: status_integration -->

<!-- section: tooling [dimensions: component_gate_cli] -->
## Tooling — `scripts/gates.sh`

A bash entry point with a small command surface:

```
ait gates list <task-id>           — show declared gates from frontmatter
ait gates status <task-id>         — derived status per gate (pass/fail/pending/blocked)
ait gates unlocked <task-id>       — which gates are runnable right now
ait gates run <task-id>            — invoke orchestrator (alias for aitask-run-gates)
ait gate append <task> <gate> <status> <attempt> <run-id> [k=v ...]
                                   — atomic append of a run block (used by verifiers)
ait gate pass <task-id> <gate>     — create the signal for a human gate (refuses for machine)
ait gate fail <task-id> <gate> [--reason "..."]
                                   — manual fail marker (useful for human review)
ait gate log <task-id> <gate>      — print the sidecar log for the most recent run
```

**Parsing.** Implemented in bash using `awk` for the marker-line scan. If edge cases prove unmanageable (nested blockquotes, multiline output with `>` characters, gate names containing special characters), a Python helper `scripts/gates.py` using standard library only provides a drop-in replacement — the bash wrapper delegates to it when `AIT_GATES_BACKEND=python` is set, or falls back to it automatically when `awk` parsing fails. This is an escape hatch, not the primary path.

**Append atomicity.** `ait gate append` uses the existing task-level file lock plus `flock` on the task file, reads the current file, parses to find the `## Gate Runs` section (or creates it), appends the block, writes atomically via `mv` from a tempfile. Concurrent verifier appends from parallel machine-gate runs serialize correctly.
<!-- /section: tooling -->

<!-- section: worked_example -->
## Worked Example

**Task `t42`: add pagination to the dataset list endpoint.**

Declared gates: `[lint, tests_pass, docs_updated, review]`. Registry says `lint` unlocks `tests_pass`; `tests_pass` unlocks both `docs_updated` and `review` in parallel; both must pass before the task is done.

### Run 1: first invocation

1. Read task, registry. Parse `## Gate Runs` (empty — first run).
2. Unlocked set: `{lint}` (first in chain).
3. Append `> **🔄 gate:lint** run=... status=running attempt=1`.
4. Delegate to `aitask-gate-lint`. Verifier runs `mise run lint`, exit 0.
5. Verifier appends `> **✅ gate:lint** run=... status=pass attempt=1 duration=4s`.
6. Re-enter. Unlocked set: `{tests_pass}`.
7. Delegate, verifier runs tests. 3 integration tests fail.
8. Appends `> **❌ gate:tests_pass** run=... status=fail attempt=1 duration=67s`.
9. Unlocked set: `{tests_pass}` (retry attempt 2). But attempt 2 needs the user to fix the tests first — the verifier will just fail again on unchanged code. After two identical failures with no intervening task-file change, the orchestrator treats it as exhausted and asks the human to intervene.
10. Report: "tests_pass failed 2x — likely needs a code fix, not a retry."

### Human fix loop

11. Human fixes the 3 failing tests, commits the fix.
12. Human re-runs `ait gates run t42`.
13. Orchestrator re-parses. Current state: `lint=pass, tests_pass=fail (2 attempts)`.
14. `tests_pass` is still unlocked (retry budget `3`, used `2`). Runs again.
15. Passes: `> **✅ gate:tests_pass** run=... status=pass attempt=3 duration=72s`.
16. Unlocked set: `{docs_updated, review}` (parallel fan-out). Orchestrator dispatches both.

### Parallel gates

17. `docs_updated` verifier runs, finds `architecture/endpoints.md` stale, updates it. Appends pass block.
18. `review` is `type: human`, `signal: file-touch`, target `.aitask-gates/t42/review.signed`. File does not exist. Appends pending block, exits 4.
19. Orchestrator stops. Report: "All machine gates pass. Awaiting human review — run `ait gate pass t42 review` once reviewed."

### Human review gate

20. Reviewer inspects the branch + task file. Runs `ait gate pass t42 review`.
21. `ait gate pass` confirms `review` is `type: human`, creates `.aitask-gates/t42/review.signed` with reviewer's shell username and timestamp.
22. Human runs `ait gates run t42`. Orchestrator re-parses, runs the `review` verifier — signal file now exists. Appends pass block.
23. All gates pass. Reports: "All gates passed. Suggest `status: Done`."

### Gate Runs section at end-of-task

```markdown
## Gate Runs
<!-- Appended by aitask-run-gates. Do not edit by hand. -->

> **✅ gate:lint** run=2026-04-15T14:30:00Z status=pass attempt=1 duration=4s
> Verifier: `aitask-gate-lint`
> Log: `.aitask-gates/t42/lint_2026-04-15T14-30-00Z.log`

> **❌ gate:tests_pass** run=2026-04-15T14:30:05Z status=fail attempt=1 duration=67s
> Verifier: `aitask-gate-tests-pass`
> Result: 39 passed, 3 failed (test_pagination_offset, test_pagination_limit, test_pagination_order)
> Log: `.aitask-gates/t42/tests_pass_2026-04-15T14-30-05Z.log`

> **❌ gate:tests_pass** run=2026-04-15T14:31:14Z status=fail attempt=2 duration=69s
> (same failures — stopping retry loop, human investigation required)

> **✅ gate:tests_pass** run=2026-04-15T14:55:02Z status=pass attempt=3 duration=72s
> Result: 42 passed, 0 failed
> Log: `.aitask-gates/t42/tests_pass_2026-04-15T14-55-02Z.log`

> **✅ gate:docs_updated** run=2026-04-15T14:56:15Z status=pass attempt=1 duration=19s
> Updated: `architecture/endpoints.md`
> Log: `.aitask-gates/t42/docs_updated_2026-04-15T14-56-15Z.log`

> **⏸ gate:review** run=2026-04-15T14:56:15Z status=pending type=human
> Awaiting: `.aitask-gates/t42/review.signed`

> **✅ gate:review** run=2026-04-15T15:22:40Z status=pass attempt=1 type=human
> Signed by: reviewer@local at 2026-04-15T15:22:38Z
```

The derived current state is `{lint: pass, tests_pass: pass, docs_updated: pass, review: pass}`. `ait gates status t42` prints exactly that.
<!-- /section: worked_example -->

<!-- section: integration_points -->
## Integration Points with Existing aitasks

| Existing surface | Change |
|---|---|
| `task-workflow/planning.md` §Plan output | Optionally writes `gates: [...]` into the new task's frontmatter, chosen from the registry's `default_gates` or the plan's risk profile. |
| `task-workflow/implementation.md` §Verify | Replaces ad-hoc "run tests, check lint" with a single call: `ait gates run <task-id>`. |
| `aitask-pickrem` (autonomous lane) | Runs `aitask-run-gates` as its verify step. Respects human gates — stops on pending-human without escalating. Profile flag `auto_complete_on_all_gates_pass: true` lets the autonomous lane finalize the task. |
| `aitask-archive` | Refuses to archive if any declared gate is not in `pass` state (profile-gated). Blocks human archive on unreviewed work. |
| `aitask-contribute` / `aitask-contribution-review` | Gate run summary is included in the contribution metadata block for round-trip. Remote reviewers see "which gates passed" in the PR/issue body. |
| Monitor TUI (`ait monitor`) | New column showing per-task gate status (3/4 pass, 1 pending). |
| Label mirror | Gate status can additionally mirror to remote labels (`ait-gate:tests-pass`, `ait-gate:review-pending`) for remote observers. One-directional, local authoritative. |

**Refines from openshell-inspired-ideas:**
- Idea 1 (mirror local status to remote labels) — gains a gate-layer projection.
- Idea 2 (agent comment markers) — the marker format used by the gate framework *is* the comment marker format.
- Idea 3 (`aitask-build-from-issue` stateful re-entrant skill) — the re-entry engine for that idea is this framework.
- Idea 4 (`ait:agent-ready` hard-gate label) — becomes one specific human gate with `signal: label`.
- Idea 10 (verification-attestation PR comment on archive) — the Gate Runs section *is* the attestation.
<!-- /section: integration_points -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

- **Local file authority.** The local task file is the single source of truth for gate state. Remote issue tracker surfaces are read-only projections; no gate state is stored on the remote. The one exception — reading authorized comment signals — is a narrow, auditable carve-out.

- **Additive adoption.** Tasks without a `gates` field behave exactly as today. The framework is fully backward-compatible; an aitasks install that never declares `gates:` is unaffected.

- **No persisted gate status.** There is deliberately no `gates_passed` or `gates_failed` frontmatter field. Pass/fail/pending status is *derived* from the Gate Runs section on every read. This eliminates drift between a stored status field and the event log.

- **Marker-first format is self-delimiting.** Gate run records are marker-first blockquotes. Block boundaries are inferable from the next marker line or heading without a custom parser. The format is grep-friendly and renders cleanly in any markdown viewer.

- **Task gate list is authoritative.** A task's explicit `gates:` list is the source of truth for which gates apply. The registry's `default_gates` is only used when the task has no `gates` field at all.

- **Human gates are non-automatable.** Human gate signals must come from humans. Agents must never create the signal, suggest automating its creation, or bypass its absence. This is a non-negotiable autonomy control, stated verbatim in the verifier skill contract and the registry description.

- **Orchestrator is stateless.** The orchestrator re-derives all gate state on every invocation from the task file and registry. It holds no cross-invocation state of its own. This is what makes it safe to invoke repeatedly.

- **Stopping heuristic for deterministic failures.** After two identical failures for the same gate with no intervening task-file change (compare git hash), the orchestrator treats the gate as exhausted and asks for human intervention — rather than burning the retry budget on a deterministic failure.

- **Sidecar logs are git-ignored by default.** Full verifier output lives under `.aitask-gates/<task-id>/`. The profile flag `commit_gate_logs: false` (default) keeps these out of git; the in-body summary is what gets committed.

- **Append atomicity via file lock.** `ait gate append` uses the existing task-level file lock plus `flock`, writes to a tempfile, then atomically renames. Concurrent verifier appends from parallel machine-gate runs serialize correctly.

- **No remote label reads.** The orchestrator reads labels never. Manual label edits by a reviewer do not affect local gate state. Human-gate signals flow through comments or file-touch, keeping the channels separate and preventing accidental label-edit from being mistaken for human sign-off.

- **Comment signal authorization defaults to safe.** If neither a task `reviewers:` list nor a registry `gate_authorized_users:` allow-list is configured, the gate refuses to pass from a comment signal. The default is safe: no allow-list means no remote sign-off.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

- **Marker-first blockquotes vs. paired fences.** Marker-first was chosen over paired open/close fences (`>>>>` / `<<<<`). Any format with matched delimiters risks mismatch when identical gates run back-to-back, and `>>>>` at line start is already valid nested markdown that renderers may mangle. Marker-first blockquotes are grep-friendly, survive human markdown edits, and do not require a custom parser.

- **Derived state vs. persisted state fields.** Gate status is derived from the event log on every read rather than stored as a separate field. This eliminates the drift problem (a stored `tests_pass: true` field becoming stale after a revert) at the cost of re-parsing the Gate Runs section on each orchestrator entry. For task files of practical size, this is negligible.

- **Local file authority vs. remote feedback.** The local task file stays authoritative, with one narrow carve-out for reading authorized comment signals from `signal: comment` human gates on remote issues. Without this carve-out, remote reviewers would have no interaction surface that doesn't require a shell on the task machine. The carve-out is bounded (comments only, human gates only, explicit keywords only, authorization allow-list required).

- **Bash/awk parser vs. Python.** The primary gate-run marker parser is bash/awk — consistent with the rest of the aitasks tooling. A Python escape hatch (`scripts/gates.py`, standard library only) is available as a drop-in replacement for edge cases where awk fails (nested blockquotes, gate names with special characters). The bash wrapper falls back to Python automatically when `AIT_GATES_BACKEND=python` is set or when awk parsing fails.

- **Terminal-only label emission vs. chatty.** The label mirror emits labels only when a gate reaches a stable terminal state (`pass`, `exhausted`, `pending-human`). Intermediate retries and `running` states do not emit labels. This avoids label flap noise on the issue tracker. An opt-in chatty mode (`gate_labels_chatty: true`) is available for debugging.
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. **Gate set resolution order.** If a task has `gates: [a, b]` and the registry's `default_gates: [a, b, c]`, does `c` also apply? *Proposal*: no. The task's explicit list is authoritative; `default_gates` is only used when the task has no `gates` field. Needs confirmation.

2. **Project-level vs task-level gate overrides.** Can a task override `max_retries` for a specific gate without forking the registry? *Proposal*: allow `gates: [{name: tests_pass, max_retries: 5}, review, docs_updated]` as a mixed form. Adds complexity — defer until a real need appears.

3. **Gate dependencies on artifacts, not other gates.** Some gates should only run if certain files changed (`docs_updated` is pointless if nothing in `docs/` changed). *Proposal*: add an optional `applies_when:` predicate in the registry. The verifier shortcircuits to `skip` if the predicate is empty. Keep `skip` distinct from `pass` so the history shows the gate was evaluated.

4. **Cross-task gates.** A task that depends on another task's gate (e.g. `parent:t40:review`). Not supported in v1; reach for it only if the need arises.

5. **Gate renaming / registry migration.** What happens to a task's `gates: [old_name]` after the registry renames `old_name → new_name`? *Proposal*: the orchestrator refuses to run unknown gates, reports the drift, and suggests `ait gates migrate <task-id>` to rewrite the task list against the current registry.

6. **Parallel concurrency ceiling.** How many machine gates should run in parallel by default? *Proposal*: profile flag `max_parallel_gates: 2`, capped by available cores for CPU-bound gates.

7. **Interaction with the brainstorm DAG engine.** Should a brainstorm DAG node produce a task with a computed gate set based on its proposal type? *Proposal*: yes, but deferred to a follow-up proposal after this lands.
<!-- /section: open_questions -->

<!-- section: remote_projection -->
## Remote Projection for Gate State

This section specifies how the gate framework feeds two remote-projection capabilities: **label mirror** and **comment markers**.

### Motivation

The gate framework makes aitasks stateful and observable locally. But contributors who matter for human-gate interactions — reviewers, maintainers, external collaborators — may never clone the repo. Two motivations:

1. **Transparency as a second surface.** Contributors familiar with GitHub-style workflows expect to see task progress on the issue tracker.
2. **Human-feedback gates need an interaction surface.** Remote reviewers can leave a scoped keyword comment; the orchestrator detects it and passes the gate.

Both keep aitasks "local file is authoritative": no state is *stored* on the remote, only *projected* there. The one exception — reading human-gate signal comments — is a narrow, auditable carve-out.

### Label mirror — debounced terminal-only projection

Labels are emitted only when a gate reaches a **stable terminal state**. Intermediate retries do not flap labels on the remote issue.

**Label namespace:** `ait-gate:<gate-name>:<terminal-state>`

| Terminal state | Meaning | When emitted |
|---|---|---|
| `pass` | Gate has passed on its most recent run | On any append that transitions derived state for this gate to `pass` |
| `exhausted` | Gate has failed and retry budget is spent | On the append that marks the gate's final failure |
| `pending-human` | Human gate is awaiting a signal | On the append of a pending block for a human gate, if no label is already present |

Non-terminal states (`running`, `fail` mid-retry-budget, `skip`, `error`) **do not emit labels**.

**Debouncing state.** The orchestrator maintains a sidecar file `.aitask-gates/<task-id>/_mirror-state.json` tracking the last emitted label set. After every `ait gate append`, the orchestrator diffs desired vs last-emitted and calls the dispatcher's `add_label`/`remove_label` backends. Re-running after a mirror network failure converges the remote to the correct label set.

**Configuration:**
```yaml
label_mirror:
  enabled: true
  label_prefix: ait-gate
  emit_on_terminal_only: true
  namespace_override: {}
```

**One-directional invariant.** The orchestrator reads labels *never*. Manual label edits by a reviewer do not affect local gate state.

### Comment mirror — hybrid singleton + notable events

**Singleton status comment.** One per task, identified by the marker `> **🚦 ait-gates**`. Created on the first mirror call, edited in place on every subsequent state change. The singleton comment ID is stored in `.aitask-gates/<task-id>/_mirror-state.json` under `singleton_comment_id:`. If the comment is deleted, the orchestrator re-creates it on the next mirror call.

**Render format:**
```markdown
> **🚦 ait-gates** — task t42 gate status
>
> | Gate | Status | Attempts | Last run | Notes |
> |---|---|---|---|---|
> | lint | ✅ pass | 1/3 | 2026-04-15T14:30:00Z | 4s |
> | tests_pass | ✅ pass | 3/4 | 2026-04-15T14:55:02Z | 72s; 2 prior fails |
> | docs_updated | ✅ pass | 1/3 | 2026-04-15T14:56:15Z | updated `endpoints.md` |
> | review | ⏸ pending (human) | 0 | 2026-04-15T14:56:15Z | reply `/ait-gate-pass review` to approve |
>
> *Local task file is authoritative. This comment is a read-only projection and is rewritten on every gate state change. Do not edit.*
```

**Fallback for missing `edit_comment`.** If the dispatcher backend doesn't yet implement `edit_comment`, degrade gracefully: post a new singleton comment on each update, mark superseded comments with `> **🚦 ait-gates [superseded]**`, and log a warning.

**Notable-event append comments.** The orchestrator posts append-only comments for significant events (never edited, form a chronological record):

| Event | Trigger | Marker |
|---|---|---|
| All gates pass | Every declared gate reaches `pass` | `> **✅ ait-gate:all-pass**` |
| Retry exhausted | A gate hits `max_retries` or stopping heuristic fires | `> **🛑 ait-gate:exhausted:<name>**` |
| Human gate awaiting | A human gate first enters pending state | `> **⏸ ait-gate:human-wait:<name>**` |
| Help needed | Orchestrator blocked, no runnable gates, at least one non-pass gate | `> **🆘 ait-gate:help-needed**` |

Each event type is posted once per task (tracked in sidecar), with specific re-post rules for recurring events like re-entering human-wait.

### Human-feedback gates via comment signal

A new human-gate signal kind: `signal: comment`. The gate framework reads back from the remote in a narrowly-scoped, auditable way.

**Registry example:**
```yaml
gates:
  review:
    verifier: aitask-gate-review
    type: human
    max_retries: 0
    signal: comment
    signal_target:
      match_keyword: "/ait-gate-pass review"
      reject_keyword: "/ait-gate-fail review"
      authorized_from:
        - task_frontmatter: reviewers
        - registry_allowlist: gate_authorized_users
```

**Task frontmatter extension:**
```yaml
gates: [lint, tests_pass, docs_updated, review]
reviewers: [alice, bob]  # optional — restricts review gate signal to these users
```

**Verifier behavior:**
1. Fetch all comments since the pending block was written, via dispatcher `list_comments(issue_number, since=<ts>)`.
2. Scan each for `match_keyword` or `reject_keyword` at line start (avoids false positives from nested quotes).
3. Validate comment author against authorization allow-list. If no allow-list is configured, the gate refuses to pass — default is safe.
4. On a valid `match_keyword`: append `✅` gate run block locally, post a confirmation comment on the remote.
5. On a valid `reject_keyword`: append `❌` gate run block locally with reason. Gate enters `human-rejected` terminal state (does not auto-retry).
6. On a match from an unauthorized author: log and ignore, post an advisory comment explaining who is authorized.

The rule, repeated verbatim in every `signal: comment` human-gate verifier skill:

> **Agents MUST NEVER post the signal keyword comment for a human gate, suggest automating it, impersonate an authorized reviewer, or bypass the authorization allow-list. This is a non-negotiable autonomy control.**

### Dispatcher backend requirements

| Backend function | Status | Used by |
|---|---|---|
| `add_label(issue, label)` | Already exists for GitHub, GitLab, Bitbucket | Label mirror |
| `remove_label(issue, label)` | Already exists for all three | Label mirror |
| `post_comment(issue, body)` | Already exists for all three | Singleton creation, event append comments |
| `edit_comment(comment_id, body)` | **Needs to be added** | Singleton update |
| `list_comments(issue, since=<ts>)` | **Needs to be added** on at least some platforms | Human-gate comment signal |

Both gaps are small additions — all three platforms support these natively. Rolling out the label mirror first (no new backends required) lets the gate framework ship with partial remote projection.

### Configuration flags summary

| Flag | Location | Default | Purpose |
|---|---|---|---|
| `label_mirror.enabled` | `gates.yaml` | `true` | Master switch for label mirror |
| `label_mirror.label_prefix` | `gates.yaml` | `ait-gate` | Label namespace prefix |
| `label_mirror.emit_on_terminal_only` | `gates.yaml` | `true` | Terminal-only vs chatty label emission |
| `comment_mirror.enabled` | `gates.yaml` | `true` | Master switch for comment mirror |
| `comment_mirror.singleton_marker` | `gates.yaml` | `> **🚦 ait-gates**` | Singleton comment marker |
| `comment_mirror.event_comments_enabled` | `gates.yaml` | `true` | Post notable-event append comments |
| `comment_mirror.notable_events` | `gates.yaml` | `[all-pass, exhausted, human-wait, help-needed]` | Which events fire append comments |
| `gate_authorized_users.<gate>` | `gates.yaml` | `[]` | Project-level allow-list for human-gate signals |
| `gate_signal_poll_interval` | profile | `60s` | How often pending human gates check for new comments |
| `gate_labels_chatty` | profile | `false` | Opt-in to non-terminal label emission |
| `commit_gate_logs` | profile | `false` | Whether sidecar logs under `.aitask-gates/<task>/` are committed |
<!-- /section: remote_projection -->
--- PROPOSAL_END ---
