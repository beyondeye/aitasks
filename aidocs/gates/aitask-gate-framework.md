---
title: aitasks Gate Framework — Stateful Multi-Pass Task Execution
category: idea
tags: [aitasks, gates, state-machine, stateful-skill, re-entrant, hard-gate, human-gate, gate-registry, orchestrator, marker-discipline, openshell-inspired]
sources: [openshell-agents.md]
confidence: medium
created: 2026-04-15
updated: 2026-04-15
---

# aitasks Gate Framework

A proposal to make aitasks task execution **stateful and multi-pass** by introducing first-class *gates* — named verification checkpoints declared in task frontmatter, implemented by a skill family, orchestrated by a stateless re-entrant skill, and logged as marker-first blockquotes in the task body.

This page is a filed-back design synthesis. It adopts OpenShell's stateful re-entry and marker discipline (see [[openshell-agents]], [[openshell-issue-state-machine]]) but keeps the authoritative state *inside the local task file* rather than on a remote issue — preserving aitasks's "local file is authority" model. It supersedes / refines several ideas in [[openshell-inspired-ideas]] (notably ideas 3, 4, and 10) by proposing a concrete substrate they can all build on.

Confidence is `medium` because this is a design proposal, not yet implemented.

## Motivation

**Current state.** aitasks task files carry a single linear `status` enum: `Ready | Editing | Implementing | Postponed | Done | Folded` (see [[aitasks-framework]]). Skills follow a linear procedure (`aitask-pick` → plan → implement → verify → archive) and hold no re-entry state of their own. If verification fails halfway through, there is no first-class way to record "unit tests passed but integration tests failed, needs another pass" on the task itself — the state lives only in the skill's in-conversation memory.

**The problem.** This blocks three patterns that OpenShell gets for free via its label state machine:

1. **Safe re-entry.** Re-running a skill on the same task should skip work that is already done and resume from the first unmet requirement. Today, re-running a skill either starts from scratch or relies on the agent reading the conversation — neither is durable.
2. **Multi-dimensional state.** "Tests pass" and "human review approved" and "docs updated" are orthogonal; they should be expressible independently, not collapsed into a single linear `status`.
3. **Parallel verification.** Some checks can run concurrently (lint and unit tests, for instance). A linear state machine forces them to serialize.

**The key insight.** What OpenShell calls a state machine is, structurally, a **gate set** — a list of named requirements that must be satisfied before a task can advance. The labels are just the projection. If aitasks represents the gate set directly in the task file, every OpenShell pattern (re-entry, hard gates, marker discipline, bounded retry) ports naturally, and the framework stays local-first.

## Design overview

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

## Data model

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

> **✅ gate:docs_updated** run=2026-04-15T14:41:55Z status=pass attempt=2 duration=19s
>
> Verifier: `aitask-gate-docs-updated`
> Updated: `architecture/endpoints.md`
> Log: `.aitask-gates/t42/docs_updated_2026-04-15T14-41-55Z.log`

> **⏸ gate:review** run=2026-04-15T14:42:10Z status=pending type=human
>
> Verifier: `aitask-gate-review`
> Awaiting: `.aitask-gates/t42/review.signed`
> Hint: reviewer runs `ait gate pass t42 review` after review
```

**Format rules.**
- **Marker line** — always the first line of the block, always starts with `> **<icon> gate:<name>**`, always contains `run=<ISO-8601-Z>` and `status=<pass|fail|pending|running|skip|error>`. For machine gates also `attempt=<N>` and `duration=<s>`. Icons: `✅` pass, `❌` fail, `⏸` pending, `🔄` running, `⏭` skip, `⚠` error.
- **Body lines** — prefixed with `> ` (standard markdown blockquote). Blank line (`>` alone) separates the marker from the body. Body holds verifier name, command summary, result summary, sidecar log path. Keep it short — detail goes in the sidecar log.
- **Block terminator** — next `> **` marker line, next `##` heading, or EOF. No closing fence. This avoids the mismatched-closer bug of paired fences when two runs of the same gate back-to-back appear.
- **Always append.** Never rewrite or delete historical gate runs. A re-run produces a new block; `ait gate status` determines *current* status by scanning back-to-front and taking the first block per gate name.
- **Sidecar logs.** Full verifier output lives under `.aitask-gates/<task-id>/<gate>_<iso-timestamp>.log`. Directory is git-ignored by default (profile flag `commit_gate_logs: false`) — the in-body summary is what gets committed.

**Why this format.** Marker-first is grep-friendly (`grep -n '^> \*\*' task.md`), survives human markdown edits, renders cleanly in any markdown viewer (shows as a blockquote), and does not require a custom parser — the block boundaries are inferable from the next marker line or heading. The decision against paired open/close fences (`>>>>` / `<<<<`) is deliberate: any format with matched delimiters risks mismatch when identical gates run back-to-back, and `>>>>` at line start is already a valid nested markdown quote that renderers may mangle.

## Orchestrator skill — `aitask-run-gates`

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
  │       ├─ Yes → append `status=pass` block (the *observation* of the signal is the gate's action)
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
4. **Stop at pending-human.** The orchestrator never self-signals a human gate. If a pending-human block has no signal, it stays pending and execution stops for that branch.
5. **No partial frontmatter writes.** The orchestrator never touches `gates:` in frontmatter. It only appends to `## Gate Runs`.
6. **Concurrency safety.** Parallel machine-gate execution uses a task-level file lock (reusing aitasks's existing lock mechanism) around appends. Each verifier's append is atomic.

## Verifier skill contract

Every gate is implemented by a **`aitask-gate-<name>`** skill, following a standard template. The framework ships a template skill so users and plugins can add gates without re-deriving the contract.

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
5. Return an exit code: `0` = pass, `1` = fail, `2` = skip (gate does not apply to this task), `3` = error (verifier itself failed; distinct from fail).

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
3. If no → append `status=pending` block (if one does not already exist for this run), exit with a special code `4 = pending`.

The rule is repeated verbatim in every human-gate verifier and in the registry description:

> **Agents MUST NEVER create the signal for a human gate, suggest automating its creation, or bypass its absence. This is a non-negotiable autonomy control.**

Signal kinds:
- `file-touch` — a file at `signal_target` exists. Human creates it via `ait gate pass <task-id> <gate>`.
- `label` — a label on the linked remote issue/PR (requires the dispatcher's label backend; degrades to file-touch if the task has no `issue:` field).
- `command` — a side-effect command the human must run; detection is by a witness file the command writes.

## Relationship to existing `status` field

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

**Append atomicity.** `ait gate append` uses the existing task-level file lock (see [[aitasks-framework]]) plus `flock` on the task file, reads the current file, parses to find the `## Gate Runs` section (or creates it), appends the block, writes atomically via `mv` from a tempfile. Concurrent verifier appends from parallel machine-gate runs serialize correctly.

## Worked example

**Task `t42`: add pagination to the dataset list endpoint.**

Declared gates: `[lint, tests_pass, docs_updated, review]`. Registry says `lint` unlocks `tests_pass` (they can't parallel on this project); `tests_pass` unlocks both `docs_updated` and `review` in parallel; both `docs_updated` and `review` must pass before the task is done.

### Run 1: first invocation of the orchestrator

1. Read task, registry. Parse `## Gate Runs` (empty — first run).
2. Unlocked set: `{lint}` (first in chain).
3. Append `> **🔄 gate:lint** run=2026-04-15T14:30:00Z status=running attempt=1`.
4. Delegate to `aitask-gate-lint`. Verifier runs `mise run lint`, exit 0.
5. Verifier appends `> **✅ gate:lint** run=2026-04-15T14:30:00Z status=pass attempt=1 duration=4s`.
6. Re-enter. Unlocked set: `{tests_pass}`.
7. Delegate, verifier runs tests. 3 integration tests fail.
8. Appends `> **❌ gate:tests_pass** run=... status=fail attempt=1 duration=67s`.
9. Unlocked set: `{tests_pass}` (retry attempt 2). But attempt 2 needs the user to fix the tests first — the verifier, being a test runner, will just fail again on unchanged code. Orchestrator's default is to retry once more if the re-run could plausibly help (e.g., transient failure), but after hitting the same failure twice it stops and reports.

*Stopping heuristic*: after two identical failures for the same gate with no intervening task-file change (compare git hash), the orchestrator treats it as exhausted and asks the human to intervene. This avoids burning the retry budget on a deterministic failure.

10. Report: "tests_pass failed 2x — likely needs a code fix, not a retry. Investigate and re-run `ait gates run t42`."

### Human fix loop

11. Human fixes the 3 failing tests, commits the fix.
12. Human re-runs `ait gates run t42`.
13. Orchestrator re-parses. Current state: `lint=pass, tests_pass=fail (2 attempts)`.
14. `tests_pass` is still unlocked (retry budget `3`, used `2`, allowed `3`). Runs again.
15. Passes: `> **✅ gate:tests_pass** run=... status=pass attempt=3 duration=72s`.
16. Unlocked set: `{docs_updated, review}` (parallel fan-out). Orchestrator dispatches both.

### Parallel gates

17. `docs_updated` verifier runs, finds `architecture/endpoints.md` stale, updates it.
    - Append `> **✅ gate:docs_updated** run=... status=pass attempt=1 duration=19s`.
18. `review` is `type: human`, `signal: file-touch`, target `.aitask-gates/t42/review.signed`.
    - Verifier checks, file does not exist.
    - Append `> **⏸ gate:review** run=... status=pending type=human`.
    - Exit code 4 (pending).
19. Orchestrator computes new state: `docs_updated=pass, review=pending`. No more unlocked gates. Stops.
20. Report: "All machine gates pass. Awaiting human review — run `ait gate pass t42 review` once reviewed."

### Human review gate

21. Reviewer inspects the branch + task file. Runs `ait gate pass t42 review`.
22. `ait gate pass` refuses to touch machine gates, confirms `review` is `type: human`, creates `.aitask-gates/t42/review.signed` containing the reviewer's shell username and timestamp.
23. Human (or profile autorun) runs `ait gates run t42`.
24. Orchestrator re-parses. Current state: `lint=pass, tests_pass=pass, docs_updated=pass, review=pending (pending block is the current one)`.
25. Re-runs the `review` verifier. Signal file now exists. Appends `> **✅ gate:review** run=... status=pass attempt=1`.
26. All gates pass. Reports: "All gates passed. Suggest `status: Done`."

### What the Gate Runs section looks like at end-of-task

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

The history is the full event log; the derived current state is `{lint: pass, tests_pass: pass, docs_updated: pass, review: pass}`. `ait gates status t42` prints exactly that.

## Integration points with existing aitasks

| Existing surface | Change |
|---|---|
| `task-workflow/planning.md` §Plan output | Optionally writes `gates: [...]` into the new task's frontmatter, chosen from the registry's `default_gates` or the plan's risk profile. |
| `task-workflow/implementation.md` §Verify | Replaces ad-hoc "run tests, check lint" with a single call: `ait gates run <task-id>`. |
| `aitask-pickrem` (autonomous lane) | Runs `aitask-run-gates` as its verify step. Respects human gates — stops on pending-human without escalating. Profile flag `auto_complete_on_all_gates_pass: true` lets the autonomous lane finalize the task. |
| `aitask-archive` | Refuses to archive if any declared gate is not in `pass` state (profile-gated). Blocks human archive on unreviewed work. |
| `aitask-contribute` / `aitask-contribution-review` | Gate run summary is included in the contribution metadata block for round-trip. Remote reviewers see "which gates passed" in the PR/issue body. |
| Monitor TUI (`ait monitor`) | New column showing per-task gate status (3/4 pass, 1 pending). |
| Label mirror (see [[openshell-inspired-ideas]] idea 1) | Gate status can additionally mirror to remote labels (`ait-gate:tests-pass`, `ait-gate:review-pending`) for remote observers. One-directional, local authoritative. |

**Supersedes / refines in [[openshell-inspired-ideas]]**:
- Idea 1 (mirror local status to remote `ait:*` labels) — gains a gate-layer projection. See Appendix A below for the debounced terminal-only design.
- Idea 2 (agent comment markers) — the marker format used by the gate framework *is* the comment marker format. Gate-layer comment projection detailed in Appendix A below (hybrid singleton + notable events).
- Idea 3 (`aitask-build-from-issue` stateful re-entrant skill) — the *re-entry engine* for that idea is this framework. Idea 3's decision tree collapses into "run the gates for this task."
- Idea 4 (`ait:agent-ready` hard-gate label) — becomes one specific human gate with `signal: label`.
- Idea 10 (verification-attestation PR comment on archive) — the Gate Runs section *is* the attestation; the archive step just mirrors the summary to a PR comment.

## What's deferred / open questions

1. **Gate set resolution order.** If a task has `gates: [a, b]` and the registry's `default_gates: [a, b, c]`, does `c` also apply? *Proposal*: no. The task's explicit list is authoritative; `default_gates` is only used when the task has no `gates` field. Needs confirmation.
2. **Project-level vs task-level gate overrides.** Can a task override `max_retries` for a specific gate without forking the registry? *Proposal*: allow `gates: [{name: tests_pass, max_retries: 5}, review, docs_updated]` as a mixed form. Adds complexity — defer until a real need appears.
3. **Gate dependencies on artifacts, not other gates.** Some gates should only run if certain files changed (`docs_updated` is pointless if nothing in `docs/` changed). *Proposal*: add an optional `applies_when:` predicate in the registry (`applies_when: "git diff --name-only ${BASE} -- docs/"`). The verifier shortcircuits to `skip` if the predicate is empty. Keep `skip` distinct from `pass` so the history shows the gate was evaluated.
4. **Cross-task gates.** A task that depends on another task's gate (e.g. `parent:t40:review`). Not supported in v1; reach for it only if the need arises.
5. **Gate renaming / registry migration.** What happens to a task's `gates: [old_name]` after the registry renames `old_name → new_name`? *Proposal*: the orchestrator refuses to run unknown gates, reports the drift, and suggests `ait gates migrate <task-id>` to rewrite the task list against the current registry. Mirrors [[openshell-agents#skill-sync-agent-infra]] drift-check discipline.
6. **Parallel concurrency ceiling.** How many machine gates should run in parallel by default? *Proposal*: profile flag `max_parallel_gates: 2`, capped by available cores for CPU-bound gates.
7. **Interaction with the brainstorm DAG engine.** Should a brainstorm DAG node produce a task with a computed gate set based on its proposal type? *Proposal*: yes, but deferred to a follow-up proposal after this lands. See [[planning-dag-synthesis]] for the related synthesis layer.

---

## Appendix A — Remote projection for gate state (enables ideas 1 and 2)

This appendix specifies how the gate framework feeds the two remote-projection ideas from [[openshell-inspired-ideas]]: **idea 1 (label mirror)** and **idea 2 (comment markers)**. The scope is strictly the gate layer — status-level label mirroring and non-gate comment markers (plan posting, triage output, spike reports) remain in the scope of the base ideas.

### A.1 Motivation — why project gate state at all?

The gate framework already makes aitasks stateful and observable *locally*. A human or agent on the developer's machine can read the task file and see the full event log. But aitasks runs across contributors, and the contributors who matter most for human-gate interactions — reviewers, maintainers, external collaborators — may never clone the repo. They live on GitHub/GitLab/Bitbucket.

Two motivations drive the projection:

1. **Transparency as a second surface.** Contributors familiar with GitHub-style workflows expect to see task progress on the issue tracker. A task whose state is only visible inside the repo is opaque to them. Projecting gate state onto the linked issue gives those users a familiar view without forcing them into aitasks conventions. The local task file remains the single source of truth; the remote projection is read-only from their perspective.

2. **Human-feedback gates need an interaction surface.** Human gates (like `review`, `design-sign-off`, `security-ack`) need a signal from a specific reviewer. `ait gate pass <task> <gate>` works for local contributors but is useless for a remote reviewer who has no shell on the task machine. **The comment stream on the linked issue is the natural interaction surface** — reviewers can leave a scoped keyword comment, the orchestrator detects it, and the gate passes. This makes the comment mirror bidirectional in a *carefully scoped* way (discussed in A.5 below).

Both motivations keep aitasks true to its "local file is authoritative" philosophy: no state is *stored* on the remote, only *projected* there. The one exception — reading human-gate signal comments — is a narrow, auditable carve-out documented explicitly in A.5.

### A.2 What is and isn't in scope

**In scope for this appendix:**
- Projecting gate-run state to a label set on the linked remote issue (idea 1, gate layer).
- Rendering derived gate state as an edited-in-place singleton status comment (idea 2, singleton channel).
- Posting notable-event append comments for significant gate transitions (idea 2, event channel).
- Accepting scoped human-gate signals from comments on the remote issue (new `signal: comment` human gate kind).

**Not in scope — still handled by the base ideas:**
- Mirroring the coarse `status` field (Ready/Editing/Implementing/...) to labels. That's the base of idea 1 and applies independently of whether gates are declared.
- Comment markers for non-gate workflows: plan posting, triage output, spike reports. Those are the base of idea 2 and predate the gate framework.
- Reading remote labels to *infer* local state. The orchestrator is still one-directional for labels — it writes, it never reads.
- `aitask-build-from-issue` (idea 3). That skill will *consume* the remote projection this appendix produces, but its re-entry logic is specified separately.

### A.3 Label mirror — debounced terminal-only projection (idea 1, gate layer)

**Shape.** Option C from the design discussion: labels are emitted only when a gate reaches a **stable terminal state**. Intermediate retries do not flap labels on the remote issue.

**Label namespace.** Flat projection with a two-segment key:

```
ait-gate:<gate-name>:<terminal-state>
```

where `<terminal-state>` is one of:

| Terminal state | Meaning | When emitted |
|---|---|---|
| `pass` | Gate has passed on its most recent run | On any append that transitions the derived state for this gate to `pass` |
| `exhausted` | Gate has failed and retry budget is spent | On the append that marks the gate's final failure, or when the stopping heuristic fires (two identical failures, no task-file change) |
| `pending-human` | Human gate is awaiting a signal | On the append of a pending block for a human gate, *if* no label is already present |

Non-terminal states (`running`, `fail` mid-retry-budget, `skip`, `error`) **do not emit labels**. Rationale: these states flap, and flapping labels on the issue tracker create noise that reviewers learn to ignore.

**Debouncing state.** The orchestrator maintains a sidecar file `.aitask-gates/<task-id>/_mirror-state.json` tracking the last emitted label set. After every `ait gate append`, the orchestrator:

1. Recomputes the derived gate state from the task body.
2. Computes the *desired* label set from the derived state using the terminal-state rule.
3. Diffs desired vs last-emitted.
4. For each label to add: calls the dispatcher `add_label` backend.
5. For each label to remove: calls the dispatcher `remove_label` backend.
6. Writes the new desired set to the sidecar file.

Re-running the orchestrator after a mirror network failure *converges* the remote to the correct label set from the current local state — no replay of intermediate failures needed. The sidecar file is the cache of "last successful mirror"; if the dispatcher call fails, the sidecar isn't updated and the next run retries.

**Opt-in chatty mode.** For debugging or for contributors who want real-time state, profile flag `gate_labels_chatty: true` opts in to emitting `ait-gate:<name>:running` and `ait-gate:<name>:fail` labels during retries. Off by default.

**Namespace etiquette.** Labels are prefixed `ait-gate:` to avoid collision with project-native labels. The prefix is configurable per project in `aitasks/metadata/gates.yaml` under a `label_prefix:` key (default `ait-gate`). Project-level gate-label scheme:

```yaml
# aitasks/metadata/gates.yaml
label_mirror:
  enabled: true
  label_prefix: ait-gate
  emit_on_terminal_only: true    # false → chatty mode
  namespace_override: {}         # optional per-gate prefix override
```

**Gracing missing issue link.** If a task has no `issue:` frontmatter field, the mirror is a no-op — the orchestrator logs "no remote issue linked, skipping label mirror" and continues. Gate execution itself is unaffected.

**One-directional invariant.** The orchestrator reads labels *never*. Even if a reviewer manually removes an `ait-gate:review:pending` label, the orchestrator does not interpret that as a signal to pass the gate. Human-gate signals flow through comments (A.5), not labels — keeping the channels separate prevents accidental label-edit from being mistaken for human sign-off.

### A.4 Comment mirror — hybrid singleton + notable events (idea 2, gate layer)

**Shape.** Option C from the design discussion: a **singleton edited-in-place status comment** for the current state, plus **append-only notable-event comments** for significant transitions. This mirrors OpenShell's `🏗️ build-plan` singleton + `🏗️ build-from-issue-agent` conversation split — the discipline carries over directly because the gate framework's marker format is identical.

#### A.4.1 The singleton status comment

One per task, identified by the marker `> **🚦 ait-gates**`. Created by the orchestrator on the first mirror call, edited in place on every subsequent state change.

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
>
> *Last updated: 2026-04-15T14:56:15Z*
```

**Lifecycle.**
- **Create** on first mirror call. Orchestrator posts a new comment, captures its remote comment ID, stores it in the task-level mirror sidecar: `.aitask-gates/<task-id>/_mirror-state.json` under `singleton_comment_id:`.
- **Update** on every subsequent gate state change. Orchestrator calls dispatcher `edit_comment(comment_id, new_body)`.
- **Dispatcher backend dependency.** Requires `edit_comment` on the dispatcher — flagged as a missing backend in the existing [[openshell-inspired-ideas]] idea 3, confirmed missing here too. Must be added as part of the gate framework rollout. Platform coverage: GitHub (`PATCH /repos/.../comments/<id>`), GitLab (`PUT /projects/.../notes/<id>`), Bitbucket (`PUT /repositories/.../comments/<id>`) — all three platforms support it, so the abstraction is clean.
- **Fallback for missing `edit_comment`.** If the dispatcher backend for the target platform doesn't yet implement `edit_comment`, degrade gracefully: post a new singleton comment on each update instead of editing. Mark the superseded comments with a `> **🚦 ait-gates [superseded]**` prefix via edit-if-possible, or just let them accumulate. Log a warning. The point is that the gate framework keeps working even on platforms where edit support is incomplete.
- **Stale detection.** Before each update, the orchestrator confirms the singleton comment still exists. If the reviewer or a bot deleted it, the orchestrator re-creates a new singleton and updates the sidecar ID.

**What goes in the render.** The table is derived from the same function that powers `ait gates status` locally — one source of truth for the derivation, two renderers (TTY vs markdown table). Keeping both renderers in one module avoids drift between what the developer sees locally and what reviewers see remotely.

#### A.4.2 Notable-event append comments

On top of the singleton, the orchestrator posts **append-only comments** for a small set of significant events. These are append-only and never edited; they form a chronological record on the issue for reviewers who read issue threads front-to-back.

| Event | Trigger | Marker | Content |
|---|---|---|---|
| All gates pass | Every declared gate in task's `gates:` reaches `pass` | `> **✅ ait-gate:all-pass**` | "Task t42 has passed all gates. Ready for archive." |
| Retry exhausted | A gate hits `max_retries` or the stopping heuristic fires | `> **🛑 ait-gate:exhausted:<name>**` | Gate name, last failure summary, hint to investigate |
| Human gate awaiting | A human gate first enters pending state | `> **⏸ ait-gate:human-wait:<name>**` | Instructions for the reviewer on how to signal pass (see A.5) |
| Help needed | Orchestrator is blocked with no runnable gates and at least one non-pass gate | `> **🆘 ait-gate:help-needed**` | Summary of blocker per gate, recommended action |

**Suppression rules** (avoid duplicate notifications):
- Each event type is posted **once per task** by default. The sidecar tracks which notable events have already been announced.
- `human-wait:<gate>` is posted once per pending-entry — if the gate exits pending and re-enters it later (e.g., reviewer's signal was invalidated), a new comment is posted for the new pending episode.
- `exhausted:<gate>` is posted once per exhaustion event. If the human intervenes, fixes the failure, and the gate eventually passes, the `all-pass` event can fire later; the exhausted comment stays in the thread as history.
- `all-pass` is posted at most once per task; if a later edit re-opens a gate (e.g., a new gate added to `gates:`), the flag resets and a new `all-pass` fires only when the new superset passes.

**Example — human-wait comment:**

```markdown
> **⏸ ait-gate:human-wait:review**
>
> Task **t42** has a human review gate awaiting your sign-off.
>
> **To approve**, reply to this issue with:
>
> ```
> /ait-gate-pass review
> ```
>
> The reviewer must be listed in the task's `reviewers:` frontmatter or in the project's `gate_authorized_users:` allow-list.
>
> **To reject**, reply with:
>
> ```
> /ait-gate-fail review [optional reason]
> ```
>
> *This comment is posted by the aitasks gate framework. Local task file is authoritative.*
```

**Example — exhaustion comment:**

```markdown
> **🛑 ait-gate:exhausted:tests_pass**
>
> Gate `tests_pass` on task **t42** has exhausted its retry budget after 3 failed attempts.
>
> **Last failure:** 3 integration tests failing (`test_pagination_offset`, `test_pagination_limit`, `test_pagination_order`)
>
> Human intervention needed. Investigate the failures and re-run `ait gates run t42` after fixing.
>
> *This comment is posted by the aitasks gate framework. Local task file is authoritative.*
```

### A.5 Human-feedback gates via comment signal

The second motivation — giving remote reviewers a natural interaction surface — is served by a new human-gate signal kind: `signal: comment`. This is the one place where the gate framework reads back from the remote, and the read is narrowly scoped and auditable.

**Registry example:**

```yaml
# aitasks/metadata/gates.yaml
gates:
  review:
    verifier: aitask-gate-review
    type: human
    max_retries: 0
    signal: comment
    signal_target:
      match_keyword: "/ait-gate-pass review"     # keyword the reviewer posts
      reject_keyword: "/ait-gate-fail review"    # keyword to reject
      authorized_from:
        - task_frontmatter: reviewers             # read task's `reviewers:` field
        - registry_allowlist: gate_authorized_users  # fallback to project allow-list
    description: "Human code review — reviewer approves by replying `/ait-gate-pass review`"
```

**Task frontmatter extension** for per-task reviewer allow-list:

```yaml
---
id: t42
title: Add pagination to dataset list endpoint
status: Implementing
gates: [lint, tests_pass, docs_updated, review]
reviewers: [alice, bob]  # optional — restricts review gate signal to these users
---
```

**Project-level allow-list** in `gates.yaml`:

```yaml
gate_authorized_users:
  review: [alice, bob, charlie]
  security-ack: [security-team-lead]
  design-sign-off: [design-lead, product-lead]
```

**Verifier behavior** for a `signal: comment` human gate:

1. Via dispatcher `list_comments(issue_number, since=<last-checked-ts>)`, fetch all comments posted since the pending block was written (or since the last gate run, whichever is earlier).
2. Scan each comment for `match_keyword` or `reject_keyword` as a line-start match (avoids false positives from nested quotes or code blocks mentioning the keyword).
3. For each match, read the comment's `author.login` field and validate against the authorization rules:
   - If the task has a `reviewers:` frontmatter list, the author must be in it.
   - If no `reviewers:` list, fall back to the registry's `gate_authorized_users:` for this gate.
   - If neither allow-list is configured, **the gate refuses to pass from a comment signal** — it logs an explicit error and stays pending. The default is safe: no allow-list means no remote sign-off.
4. On a valid `match_keyword`: append `✅` gate run block locally, then post a confirmation append comment on the remote:
   ```markdown
   > **✅ ait-gate:review**
   >
   > Signed off by @alice at 2026-04-16T10:14:22Z via comment signal.
   >
   > *Task t42 gate `review` passed. Local task file updated.*
   ```
5. On a valid `reject_keyword`: append `❌` gate run block locally with reason from the comment body. Gate enters a special `human-rejected` terminal state that does not auto-retry (reviewer explicitly said no; retry requires a new pending episode triggered by a human intervention like editing the task or re-running with `--force-retry`).
6. On a match from an unauthorized author: log and ignore, do **not** append a gate run. Post an advisory comment explaining that the signal was not recognized and who is authorized.

**The rule, repeated verbatim** in every `signal: comment` human-gate verifier skill:

> **Agents MUST NEVER post the signal keyword comment for a human gate, suggest automating it, impersonate an authorized reviewer, or bypass the authorization allow-list. This is a non-negotiable autonomy control, equivalent to the local `signal: file-touch` rule.**

**Why this carve-out is safe.** The gate framework still does not *store* state remotely. The singleton comment and event comments are projections. The only remote *read* is for a narrowly-defined signal pattern (keyword + authorized author), and that read is documented as a deliberate exception. The alternative — forcing every remote reviewer onto the local shell — defeats the motivation. The carve-out is audited by the authorization allow-list and bounded in scope (comments only, only for human gates, only for explicit keywords).

**Caveat — polling vs push.** `signal: comment` gates require the orchestrator to poll the remote for new comments. Profile flag `gate_signal_poll_interval: 60s` controls the cadence when a human gate is pending. An optional webhook mode (dispatcher forwards `issue_comment.created` events to a local socket) is flagged as a future extension but not required for v1.

### A.6 Configuration example — full `gates.yaml` snippet

Putting it all together for the worked example in the main proposal (task t42 with lint, tests_pass, docs_updated, review):

```yaml
# aitasks/metadata/gates.yaml
default_gates: [lint, tests_pass, docs_updated, review]

label_mirror:
  enabled: true
  label_prefix: ait-gate
  emit_on_terminal_only: true

comment_mirror:
  enabled: true
  singleton_marker: "> **🚦 ait-gates**"
  event_comments_enabled: true
  notable_events: [all-pass, exhausted, human-wait, help-needed]

gate_authorized_users:
  review: [alice, bob, charlie]

gates:
  lint:
    verifier: aitask-gate-lint
    type: machine
    max_retries: 2
    unlocks: [tests_pass]

  tests_pass:
    verifier: aitask-gate-tests-pass
    type: machine
    max_retries: 3
    unlocks: [docs_updated, review]   # parallel fan-out

  docs_updated:
    verifier: aitask-gate-docs-updated
    type: machine
    max_retries: 2
    unlocks: []

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
    unlocks: []
```

### A.7 Dispatcher backend requirements

The appendix leans entirely on the existing multi-platform dispatcher pattern in `aidocs/gitremoteproviderintegration.md` (see [[openshell-vs-aitasks-github-integration]] for details on aitasks's existing dispatcher). No new abstraction is introduced; the requirements are concrete additions to the backend function table.

| Backend function | Status | Used by |
|---|---|---|
| `add_label(issue, label)` | Already exists for GitHub, GitLab, Bitbucket | Label mirror (A.3) |
| `remove_label(issue, label)` | Already exists for all three | Label mirror (A.3) |
| `post_comment(issue, body)` | Already exists for all three | Singleton creation, event append comments (A.4) |
| `edit_comment(comment_id, body)` | **Needs to be added** — same gap flagged in idea 3 | Singleton update (A.4.1) |
| `list_comments(issue, since=<ts>)` | **Needs to be added** on at least some platforms | Human-gate comment signal (A.5) |
| `get_comment_author(comment)` | Already returned by `list_comments` as `author.login` | Human-gate authorization check (A.5) |

**Gap analysis.** Two backend gaps: `edit_comment` and `list_comments`. Both are small additions — each platform's API supports them natively. The `edit_comment` gap is shared with [[openshell-inspired-ideas]] idea 3, so the work can be bundled. Rolling out the label mirror first (which needs no new backends) lets the gate framework ship with partial remote projection; the comment mirror lands in a follow-up when the backend gaps close.

**Platform parity.** The label mirror and comment mirror both work uniformly across GitHub, GitLab, and Bitbucket because they go through the dispatcher. No hardcoded GitHub references. A project using GitLab issues gets the same gate projection with zero extra config. This is the "git backend abstraction is enough" property — the gate framework does not need a sink interface because the dispatcher already is one, at the level the user actually cares about (git remote providers).

### A.8 Failure modes and recovery

| Failure | Behavior | Recovery |
|---|---|---|
| Network error during `add_label` | Sidecar `_mirror-state.json` not updated; orchestrator logs warning and continues | Next `ait gates run` diffs current vs sidecar, retries missing label changes; converges |
| Dispatcher backend missing (`edit_comment` on a platform that hasn't been wired) | Graceful degradation: post a new singleton comment on each update, log a deprecation warning | Close the backend gap; subsequent runs use `edit_comment` |
| Singleton comment deleted by a reviewer | Orchestrator detects missing comment ID via next `edit_comment` error, re-creates singleton, updates sidecar ID | Automatic on next update |
| Human comment matches `match_keyword` but author is not authorized | No gate transition; orchestrator posts an advisory comment explaining authorization rules | Reviewer re-posts from an authorized account |
| Malformed remote comment (nested quotes, code blocks containing keyword) | Line-start-match scan ignores non-line-start occurrences | Reviewer adjusts comment |
| Race — two `ait gates run` invocations updating the same singleton concurrently | Task-level file lock (existing aitasks lock, same used for frontmatter writes) serializes orchestrator runs | Automatic |
| Remote label churn (manual reviewer removes `ait-gate:review:pending`) | Orchestrator does not read labels; no effect on local state | No action — manual label edits are cosmetic |

### A.9 Configuration flags summary

For quick reference, all projection-related profile and project flags introduced by this appendix:

| Flag | Location | Default | Purpose |
|---|---|---|---|
| `label_mirror.enabled` | `gates.yaml` | `true` | Master switch for label mirror |
| `label_mirror.label_prefix` | `gates.yaml` | `ait-gate` | Label namespace prefix |
| `label_mirror.emit_on_terminal_only` | `gates.yaml` | `true` | Terminal-only (option C) vs chatty (option A) |
| `comment_mirror.enabled` | `gates.yaml` | `true` | Master switch for comment mirror |
| `comment_mirror.singleton_marker` | `gates.yaml` | `> **🚦 ait-gates**` | Singleton comment marker |
| `comment_mirror.event_comments_enabled` | `gates.yaml` | `true` | Post notable-event append comments |
| `comment_mirror.notable_events` | `gates.yaml` | `[all-pass, exhausted, human-wait, help-needed]` | Which events fire append comments |
| `gate_authorized_users.<gate>` | `gates.yaml` | `[]` | Project-level allow-list for human-gate signals |
| `gate_signal_poll_interval` | profile | `60s` | How often pending human gates check for new comments |
| `gate_labels_chatty` | profile | `false` | Opt-in to non-terminal label emission |
| `commit_gate_logs` | profile | `false` | Whether sidecar logs under `.aitask-gates/<task>/` are committed |

### A.10 Summary — what the appendix adds in one paragraph

The gate framework's append-only event log + marker-format discipline + derived-state model turns out to be exactly what the label and comment mirror ideas need. The orchestrator gains a single post-append hook that: (1) diffs derived state against a local cache and projects terminal-state transitions to `ait-gate:<name>:<state>` labels via the dispatcher, (2) edits a singleton `🚦 ait-gates` comment with a rendered table of the current state, (3) appends notable-event comments for a small set of significant transitions, and (4) polls for authorized signal keywords in comments to drive `signal: comment` human gates. All four go through the existing multi-platform dispatcher — no new abstraction is needed beyond `edit_comment` and `list_comments` backend additions. The local task file remains the single source of truth; the remote projection is a read-only surface for GitHub-native contributors and reviewers, with one narrowly-scoped carve-out for reading authorized human-gate signal comments.

## See also

- [[openshell-agents]] — the stateful re-entry pattern this adapts
- [[openshell-issue-state-machine]] — state-by-state walkthrough of the OpenShell analogue
- [[openshell-inspired-ideas]] — the ideas page this refines (ideas 3, 4, 10 in particular)
- [[aitasks-framework]] — aitasks's current linear status model and skill organization
- [[improvement-ideas]] §14 — the one-paragraph summaries that this proposal concretizes
- [[planning-dag-synthesis]] — related filed-back synthesis covering the planning side of the same re-entry pattern
- [[comparison-matrix]] — high-level context on where aitasks sits vs OpenShell on state-machine design
