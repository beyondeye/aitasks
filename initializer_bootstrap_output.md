# Output from agent: initializer_bootstrap

--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: "Stateful multi-pass gate framework for aitasks: named verification checkpoints in frontmatter, orchestrated by a re-entrant skill"
proposal_file: br_proposals/n000_init.md
created_at: "2026-06-10 10:10"
created_by_group: bootstrap
reference_files:
  - aidocs/gates/aitask-gate-framework.md
  - aitasks/t635_gates_framework.md

requirements_stateful_reentry: "re-running a skill skips already-passed gates and resumes from the first unmet requirement — safe re-entry without conversation state"
requirements_multi_dimensional_state: "tests-pass, review, docs-updated are orthogonal and must be expressible independently, not collapsed into a single linear status"
requirements_parallel_verification: "independent gates (e.g. lint + unit tests) must be runnable concurrently; a linear state machine forces serialization"
requirements_local_authority: "task file is the single authoritative source of truth — no state stored on the remote; remote projection is read-only"
requirements_additive_compatibility: "tasks without a gates: field behave identically to current aitasks — the framework is purely additive"
requirements_human_gate_no_self_signal: "agents must never create signals for human gates, suggest automating them, or bypass their absence — non-negotiable autonomy control"

assumption_task_file_is_authority: "the local task file (not any remote issue tracker or cache) holds the canonical gate state between invocations"
assumption_no_persisted_gate_status: "no gates_passed or gates_failed frontmatter fields — pass/fail/pending status is always derived from Gate Runs section on every read"
assumption_explicit_list_overrides_defaults: "task's explicit gates: list is authoritative; default_gates in the registry applies only when the task has no gates: field"
assumption_human_gate_non_negotiable: "the rule that agents must never self-signal human gates is non-negotiable — repeated verbatim in every human-gate verifier and registry description"
assumption_remote_projection_readonly: "remote labels and comments are a read-only projection; the local task file remains authoritative with one narrow carve-out for signal: comment human gates"
assumption_orchestrator_stateless: "the orchestrator skill holds no state between invocations — it re-derives everything from the task file and gate registry on each run"
assumption_done_transition_human: "when all gates pass the orchestrator suggests status: Done but does not auto-apply it — transition remains a human decision (or profile-gated for the autonomous lane)"
assumption_gates_active_during_implementing: "gates are active (blocking) only while status: Implementing; gates in Ready or Editing are advisory only"

component_task_frontmatter: "gates: [...] field in task frontmatter — declares which gates apply; ordering defines the default unlock sequence"
component_gate_registry: "aitasks/metadata/gates.yaml — per-gate config: verifier skill name, type (machine|human), max_retries, unlocks DAG, signal kind"
component_orchestrator_skill: "aitask-run-gates — stateless re-entrant skill: reads task + registry, dispatches verifiers in parallel where unlocked, re-enters until settled"
component_verifier_skills: "aitask-gate-<name> skill family — each implements one gate to the standard contract (positional args, append via ait gate append, exit codes 0-4)"
component_gate_runs_section: "## Gate Runs append-only event log in the task body — marker-first blockquotes; grep-friendly and renderer-safe; block boundary = next marker line or heading"
component_gate_cli: "scripts/gates.sh — ait gates list/status/unlocked/run and ait gate append/pass/fail/log subcommands"
component_sidecar_logs: ".aitask-gates/<task-id>/ directory for full verifier output; git-ignored by default (commit_gate_logs profile flag)"
component_remote_projection: "Appendix A: debounced terminal-only label mirror + singleton comment + notable-event append comments + signal: comment human gate kind"
component_gate_template_skill: ".claude/skills/aitask-gate-template/SKILL.md — scaffold for user-authored gates with stub workflow and example ait gate append invocation"

tradeoff_marker_first_over_fenced: "marker-first blockquote chosen over paired fences (>>>> / <<<<) — avoids mismatched-closer bug when back-to-back same-gate runs appear"
tradeoff_derived_over_persisted_status: "gate status always re-derived from Gate Runs (no gates_passed field) — eliminates frontmatter/event-log drift at the cost of a per-read scan"
tradeoff_local_file_over_remote_state: "local task file is authoritative rather than remote tracker — preserves local-first model; remote collaborators need the Appendix A projection layer"
tradeoff_terminal_labels_only: "label mirror emits only on terminal gate states by default — avoids label flapping on remote issues during retries; chatty mode opt-in via gate_labels_chatty"
tradeoff_bash_with_python_fallback: "gate marker parsing in bash/awk primarily; Python fallback via AIT_GATES_BACKEND=python for edge cases like nested blockquotes or special characters in gate names"
--- NODE_YAML_END ---

--- PROPOSAL_START ---
# aitasks Gate Framework — Stateful Multi-Pass Task Execution

A proposal to make aitasks task execution **stateful and multi-pass** by introducing first-class *gates* — named verification checkpoints declared in task frontmatter, implemented by a skill family, orchestrated by a stateless re-entrant skill, and logged as marker-first blockquotes in the task body.

This is a design synthesis. It adopts OpenShell's stateful re-entry and marker discipline but keeps the authoritative state *inside the local task file* rather than on a remote issue — preserving aitasks's "local file is authority" model. It refines several ideas from the OpenShell-inspired ideas catalogue (notably ideas 3, 4, and 10) by proposing a concrete substrate they can all build on.

<!-- section: overview -->
## Overview

**Current state.** aitasks task files carry a single linear `status` enum: `Ready | Editing | Implementing | Postponed | Done | Folded`. Skills follow a linear procedure (`aitask-pick` → plan → implement → verify → archive) and hold no re-entry state. If verification fails halfway through, there is no first-class way to record "unit tests passed but integration tests failed, needs another pass" on the task itself — the state lives only in the skill's in-conversation memory.

**The problem.** This blocks three patterns:

1. **Safe re-entry.** Re-running a skill on the same task should skip work that is already done and resume from the first unmet requirement. Today, re-running a skill either starts from scratch or relies on the agent reading the conversation — neither is durable.
2. **Multi-dimensional state.** "Tests pass" and "human review approved" and "docs updated" are orthogonal; they should be expressible independently, not collapsed into a single linear `status`.
3. **Parallel verification.** Some checks can run concurrently (lint and unit tests, for instance). A linear state machine forces them to serialize.

**The key insight.** What OpenShell calls a state machine is, structurally, a **gate set** — a list of named requirements that must be satisfied before a task can advance. If aitasks represents the gate set directly in the task file, every OpenShell pattern (re-entry, hard gates, marker discipline, bounded retry) ports naturally, and the framework stays local-first.

Confidence is `medium` — this is a design proposal, not yet implemented.
<!-- /section: overview -->

<!-- section: architecture [dimensions: component_*] -->
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

<!-- section: data_model [dimensions: component_task_frontmatter, component_gate_registry, component_gate_runs_section] -->
## Data Model

### 1. Task Frontmatter

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

- `gates` is an ordered list of gate names. Ordering defines the *default* sequence (each gate unlocks the next) unless the registry overrides it with an explicit `unlocks:` list.
- The list contains only gate *names*. All other metadata (verifier, retries, type) is resolved from the registry at orchestration time.
- An absent or empty `gates` field means "no gates active" — behaves like today's aitasks.
- **No persisted status fields.** There is deliberately no `gates_passed` or `gates_failed`. Pass/fail/pending status is *derived* from the Gate Runs section on every read. Single source of truth; no drift.

Tasks opt in per-task. A task template can specify a default set (e.g. `default_gates: [tests_pass, review, docs_updated]` in `aitasks/metadata/gates.yaml`), but any task is free to override or omit gates.

### 2. Gate Registry — `aitasks/metadata/gates.yaml`

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
| `unlocks` | no | Explicit list of gate names this gate unlocks on pass. If omitted, default is the next gate in the task's own `gates` list. Enables parallel fan-out. |
| `signal` | human only | How the human signals pass: `file-touch`, `label`, `command`, or `comment`. |
| `signal_target` | human only | Path / label name / command template. `<task-id>` is substituted. |
| `description` | yes | Human-readable purpose, shown in `ait gates list`. |
| `timeout_seconds` | no | Max wall-clock for a single machine-gate run. |

**Unlock DAG semantics.** If no gate in the registry has explicit `unlocks:`, the DAG is linear and identical to the task's `gates:` list order. As soon as any gate specifies `unlocks:`, that gate's successor list is taken from the registry, overriding the list-position default. This lets most gates stay untouched while a few declare parallelism where it matters.

**Runtime rule for parallelism.** A gate is *unlocked* iff (a) every gate that has it in its `unlocks:` list is `pass`, (b) it is not itself already `pass`, and (c) it has not exhausted its retry budget. Multiple unlocked gates may run concurrently. The orchestrator dispatches all unlocked machine gates in parallel; unlocked human gates pend for their signal.

### 3. Gate Run Marker Format

Every gate run appends a **marker-first blockquote** to a dedicated `## Gate Runs` section at the bottom of the task file. The first line carries all queryable metadata; body lines carry a human-readable summary; full output is stored in a sidecar log file.

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
- **Body lines** — prefixed with `> `. Blank line (`>` alone) separates the marker from the body. Body holds verifier name, command summary, result summary, sidecar log path.
- **Block terminator** — next `> **` marker line, next `##` heading, or EOF. No closing fence.
- **Always append.** Never rewrite or delete historical gate runs. A re-run produces a new block; `ait gate status` determines *current* status by scanning back-to-front and taking the first block per gate name.
- **Sidecar logs.** Full verifier output lives under `.aitask-gates/<task-id>/<gate>_<iso-timestamp>.log`. Directory is git-ignored by default (profile flag `commit_gate_logs: false`).

The marker-first format is grep-friendly (`grep -n '^> \*\*' task.md`), survives human markdown edits, renders cleanly in any markdown viewer, and does not require a custom parser. The decision against paired open/close fences (`>>>>` / `<<<<`) is deliberate: any format with matched delimiters risks mismatch when identical gates run back-to-back, and `>>>>` at line start is a valid nested markdown quote that renderers may mangle.
<!-- /section: data_model -->

<!-- section: orchestrator [dimensions: component_orchestrator_skill, requirements_stateful_reentry, requirements_parallel_verification] -->
## Orchestrator Skill — `aitask-run-gates`

A **stateful re-entrant skill**: safe to invoke repeatedly on the same task. Each invocation re-derives state from the task file, runs whatever can run, and stops.

### Invocation

```
aitask-run-gates <task-id> [--gate <name>] [--dry-run]
```

- `<task-id>` is the only required argument.
- `--gate <name>` runs a single gate (must be currently unlocked; ignores parallelism fan-out).
- `--dry-run` reports the decision tree without executing any verifier.

### Decision Tree (Re-entry)

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

### Re-entry Contract

The orchestrator guarantees:

1. **Idempotent on no-op.** Running `aitask-run-gates t42` twice in a row with no state change produces the same reports and appends nothing.
2. **Skip-already-passed.** Gates currently in `pass` state are not re-run unless explicitly forced with `--gate <name>`.
3. **Retry within budget.** Failed gates are re-run up to `max_retries + 1` total attempts.
4. **Stop at pending-human.** The orchestrator never self-signals a human gate. If a pending-human block has no signal, it stays pending and execution stops for that branch.
5. **No partial frontmatter writes.** The orchestrator never touches `gates:` in frontmatter. It only appends to `## Gate Runs`.
6. **Concurrency safety.** Parallel machine-gate execution uses a task-level file lock around appends. Each verifier's append is atomic.

**Stopping heuristic.** After two identical failures for the same gate with no intervening task-file change (compare git hash), the orchestrator treats the gate as exhausted and asks the human to intervene. This avoids burning the retry budget on a deterministic failure.
<!-- /section: orchestrator -->

<!-- section: verifier_contract [dimensions: component_verifier_skills, component_gate_template_skill, requirements_human_gate_no_self_signal] -->
## Verifier Skill Contract

Every gate is implemented by a **`aitask-gate-<name>`** skill following a standard template.

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
5. Return an exit code: `0` = pass, `1` = fail, `2` = skip, `3` = error (verifier itself failed — distinct from fail), `4` = pending (human gate awaiting signal).

**Must not:**
- Modify task frontmatter.
- Modify any other gate's Gate Runs entries.
- Create signal files for human gates.
- Auto-suggest retries beyond `max_retries`.

### Template Skill

`.claude/skills/aitask-gate-template/SKILL.md` — a scaffold users copy to create new gates. It provides:
- Frontmatter with the standard argument signature.
- A stub `Workflow` section with the five steps above.
- A stub verification block the user replaces with their actual check.
- An example sidecar log write.
- An example `ait gate append` invocation.

Shipping a template is essential: the point of the contract is that a plugin or user can add a project-specific gate (`security_scan`, `license_check`, `changelog_updated`) in ten minutes without re-reading this proposal.

### Human-Gate Verifier (Special Case)

For gates with `type: human`, the verifier skill is a thin wrapper:

1. Check whether the signal exists (per `signal:` and `signal_target:` in the registry).
2. If yes → append `status=pass` block, exit 0.
3. If no → append `status=pending` block (if one does not already exist for this run), exit 4.

The rule is repeated verbatim in every human-gate verifier and in the registry description:

> **Agents MUST NEVER create the signal for a human gate, suggest automating its creation, or bypass its absence. This is a non-negotiable autonomy control.**

Signal kinds:
- `file-touch` — a file at `signal_target` exists. Human creates it via `ait gate pass <task-id> <gate>`.
- `label` — a label on the linked remote issue/PR (degrades to file-touch if the task has no `issue:` field).
- `command` — a side-effect command the human must run; detection is by a witness file the command writes.
- `comment` — a keyword comment on the remote issue from an authorized author (see Remote Projection section).
<!-- /section: verifier_contract -->

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

**Parsing.** Implemented in bash using `awk` for the marker-line scan. If edge cases prove unmanageable (nested blockquotes, multiline output with `>` characters, gate names containing special characters), a Python helper `scripts/gates.py` provides a drop-in replacement — the bash wrapper delegates to it when `AIT_GATES_BACKEND=python` is set, or falls back to it automatically when `awk` parsing fails. This is an escape hatch, not the primary path.

**Append atomicity.** `ait gate append` uses the existing task-level file lock plus `flock` on the task file, reads the current file, parses to find the `## Gate Runs` section (or creates it), appends the block, writes atomically via `mv` from a tempfile. Concurrent verifier appends from parallel machine-gate runs serialize correctly.
<!-- /section: tooling -->

<!-- section: worked_example -->
## Worked Example

**Task `t42`: add pagination to the dataset list endpoint.**

Declared gates: `[lint, tests_pass, docs_updated, review]`. Registry says `lint` unlocks `tests_pass`; `tests_pass` unlocks both `docs_updated` and `review` in parallel; both must pass before the task is done.

### Run 1: First Invocation

1. Read task, registry. Parse `## Gate Runs` (empty — first run).
2. Unlocked set: `{lint}`.
3. Append `> **🔄 gate:lint** run=2026-04-15T14:30:00Z status=running attempt=1`.
4. Delegate to `aitask-gate-lint`. Verifier runs `mise run lint`, exit 0.
5. Verifier appends `> **✅ gate:lint** ...`.
6. Re-enter. Unlocked set: `{tests_pass}`.
7. Delegate; verifier runs tests. 3 integration tests fail.
8. Appends `> **❌ gate:tests_pass** ... status=fail attempt=1 duration=67s`.
9. Stopping heuristic fires after two identical failures with no task-file change — orchestrator stops and reports: "tests_pass failed 2x — likely needs a code fix, not a retry. Investigate and re-run `ait gates run t42`."

### Human Fix Loop

10. Human fixes the 3 failing tests, commits the fix.
11. Human re-runs `ait gates run t42`.
12. Orchestrator re-parses. `tests_pass` retry budget (3 total, used 2) still allows one more. Runs again.
13. Passes: `> **✅ gate:tests_pass** ... status=pass attempt=3 duration=72s`.
14. Unlocked set: `{docs_updated, review}` (parallel fan-out). Orchestrator dispatches both.

### Parallel Gates

15. `docs_updated` verifier runs, finds `architecture/endpoints.md` stale, updates it. Appends `> **✅ gate:docs_updated** ...`.
16. `review` is `type: human`, `signal: file-touch`. Signal file does not exist. Appends `> **⏸ gate:review** ... status=pending type=human`.
17. Report: "All machine gates pass. Awaiting human review — run `ait gate pass t42 review` once reviewed."

### Human Review Gate

18. Reviewer inspects the branch, runs `ait gate pass t42 review`.
19. `ait gate pass` confirms `review` is `type: human`, creates `.aitask-gates/t42/review.signed` with reviewer's shell username and timestamp.
20. Human re-runs `ait gates run t42`. Orchestrator re-parses, re-runs `review` verifier. Signal file now exists. Appends `> **✅ gate:review** ... status=pass`.
21. All gates pass. Reports: "All gates passed. Suggest `status: Done`."

### Final Gate Runs Section

```markdown
## Gate Runs
<!-- Appended by aitask-run-gates. Do not edit by hand. -->

> **✅ gate:lint** run=2026-04-15T14:30:00Z status=pass attempt=1 duration=4s
> Verifier: `aitask-gate-lint`
> Log: `.aitask-gates/t42/lint_2026-04-15T14-30-00Z.log`

> **❌ gate:tests_pass** run=2026-04-15T14:30:05Z status=fail attempt=1 duration=67s
> Result: 39 passed, 3 failed (test_pagination_offset, test_pagination_limit, test_pagination_order)

> **❌ gate:tests_pass** run=2026-04-15T14:31:14Z status=fail attempt=2 duration=69s
> (same failures — stopping retry loop, human investigation required)

> **✅ gate:tests_pass** run=2026-04-15T14:55:02Z status=pass attempt=3 duration=72s
> Result: 42 passed, 0 failed

> **✅ gate:docs_updated** run=2026-04-15T14:56:15Z status=pass attempt=1 duration=19s
> Updated: `architecture/endpoints.md`

> **⏸ gate:review** run=2026-04-15T14:56:15Z status=pending type=human
> Awaiting: `.aitask-gates/t42/review.signed`

> **✅ gate:review** run=2026-04-15T15:22:40Z status=pass attempt=1 type=human
> Signed by: reviewer@local at 2026-04-15T15:22:38Z
```

`ait gates status t42` derives: `{lint: pass, tests_pass: pass, docs_updated: pass, review: pass}`.
<!-- /section: worked_example -->

<!-- section: integration_points [dimensions: requirements_additive_compatibility, assumption_gates_active_during_implementing] -->
## Integration Points

### Relationship to the Existing `status` Field

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
- A task's gates become active when `status: Implementing` is set. Gates in `Ready` or `Editing` are advisory only.
- When all gates pass, the orchestrator **suggests** `status: Done` but does not auto-apply. Transition remains a human decision (or a profile-gated auto-transition for the `aitask-pickrem` autonomous lane).
- `Postponed` and `Folded` freeze the gate state — re-entering the task unfreezes it; gates re-evaluate from wherever they were.
- Existing skills (`aitask-archive`, monitor TUI, board views) keep reading `status` and do not need to know about gates.

### Integration with Existing aitasks Surfaces

| Existing surface | Change |
|---|---|
| `task-workflow/planning.md` §Plan output | Optionally writes `gates: [...]` into the new task's frontmatter, chosen from the registry's `default_gates` or the plan's risk profile. |
| `task-workflow/implementation.md` §Verify | Replaces ad-hoc "run tests, check lint" with a single call: `ait gates run <task-id>`. |
| `aitask-pickrem` (autonomous lane) | Runs `aitask-run-gates` as its verify step. Respects human gates — stops on pending-human without escalating. Profile flag `auto_complete_on_all_gates_pass: true` lets the autonomous lane finalize the task. |
| `aitask-archive` | Refuses to archive if any declared gate is not in `pass` state (profile-gated). |
| `aitask-contribute` / `aitask-contribution-review` | Gate run summary included in contribution metadata block. Remote reviewers see "which gates passed" in the PR/issue body. |
| Monitor TUI (`ait monitor`) | New column showing per-task gate status (e.g. 3/4 pass, 1 pending). |
| Label mirror | Gate status can mirror to remote labels (`ait-gate:tests-pass`, `ait-gate:review-pending`) for remote observers. One-directional; local authoritative. |

This is additive. An aitasks install that never declares `gates:` behaves exactly as today.
<!-- /section: integration_points -->

<!-- section: remote_projection [dimensions: component_remote_projection, requirements_local_authority, assumption_remote_projection_readonly] -->
## Remote Projection for Gate State (Appendix A)

This section specifies how the gate framework feeds remote-projection capabilities: label mirror and comment markers for gate state.

### Motivation

The gate framework makes aitasks stateful and observable *locally*. But contributors who matter most for human-gate interactions — reviewers, maintainers, external collaborators — may never clone the repo. Two motivations drive projection:

1. **Transparency as a second surface.** Contributors familiar with GitHub-style workflows expect to see task progress on the issue tracker. Projecting gate state gives those users a familiar view without forcing them into aitasks conventions. The local task file remains the single source of truth; the remote projection is read-only.

2. **Human-feedback gates need an interaction surface.** Human gates need a signal from a specific reviewer. `ait gate pass <task> <gate>` works for local contributors but is unusable for a remote reviewer. The comment stream on the linked issue is the natural interaction surface — reviewers leave a scoped keyword comment, the orchestrator detects it, and the gate passes. This makes the comment mirror bidirectional in a *carefully scoped* way.

### Scope

**In scope:**
- Projecting gate-run state to labels on the linked remote issue (debounced terminal-only).
- Rendering derived gate state as an edited-in-place singleton status comment.
- Posting notable-event append comments for significant gate transitions.
- Accepting scoped human-gate signals from comments (`signal: comment` gate kind).

**Not in scope:**
- Mirroring the coarse `status` field to labels (that's independent of gates).
- Comment markers for non-gate workflows (plan posting, triage output, spike reports).
- Reading remote labels to infer local state — orchestrator is write-only for labels.

### Label Mirror — Debounced Terminal-Only Projection

Labels are emitted only when a gate reaches a **stable terminal state**. Intermediate retries do not flap labels on the remote issue.

Label namespace: `ait-gate:<gate-name>:<terminal-state>`

| Terminal state | Meaning | When emitted |
|---|---|---|
| `pass` | Gate has passed on its most recent run | On any append that transitions derived state to `pass` |
| `exhausted` | Gate failed and retry budget is spent | On the append marking the gate's final failure |
| `pending-human` | Human gate awaiting a signal | On the first pending block append for a human gate |

Non-terminal states (`running`, `fail` mid-retry-budget, `skip`, `error`) **do not emit labels** — these states flap and create noise reviewers learn to ignore.

The orchestrator maintains `.aitask-gates/<task-id>/_mirror-state.json` as a cache of last-emitted labels. After every `ait gate append`, it diffs desired vs last-emitted and calls `add_label`/`remove_label` on the dispatcher. Re-running after a mirror network failure *converges* the remote to the correct state from current local state.

**Opt-in chatty mode.** Profile flag `gate_labels_chatty: true` opts in to emitting running/fail labels during retries.

**Configuration in `gates.yaml`:**
```yaml
label_mirror:
  enabled: true
  label_prefix: ait-gate
  emit_on_terminal_only: true    # false → chatty mode
```

**If a task has no `issue:` frontmatter field,** the mirror is a no-op. Gate execution is unaffected.

### Comment Mirror — Singleton + Notable Events

**Singleton status comment.** One per task, identified by the marker `> **🚦 ait-gates**`. Created by the orchestrator on the first mirror call, edited in place on every subsequent state change.

Example render:

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
> *Local task file is authoritative. This comment is a read-only projection.*
```

The singleton is created on first mirror, edited in place on updates (stored `singleton_comment_id:` in the mirror sidecar). If the reviewer deletes it, the orchestrator re-creates it on next update. If the `edit_comment` dispatcher backend is missing, degrades gracefully to posting a new comment per update.

**Notable-event append comments.** On top of the singleton, the orchestrator posts **append-only comments** for significant events:

| Event | Trigger | Marker |
|---|---|---|
| All gates pass | Every gate in task's `gates:` reaches `pass` | `> **✅ ait-gate:all-pass**` |
| Retry exhausted | Gate hits `max_retries` or stopping heuristic fires | `> **🛑 ait-gate:exhausted:<name>**` |
| Human gate awaiting | Human gate first enters pending state | `> **⏸ ait-gate:human-wait:<name>**` |
| Help needed | Blocked with no runnable gates and at least one non-pass gate | `> **🆘 ait-gate:help-needed**` |

Each event type is posted once per task (tracked in the mirror sidecar). The `human-wait:<gate>` event fires again on re-entry into pending for a new episode.

### Human-Feedback Gates via Comment Signal

Registry example:

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

**Verifier behavior for `signal: comment`:**

1. Via dispatcher `list_comments(issue_number, since=<last-checked-ts>)`, fetch all comments posted since the pending block was written.
2. Scan each comment for `match_keyword` or `reject_keyword` as a line-start match.
3. Validate comment author against the authorization rules (`reviewers:` frontmatter field, then `gate_authorized_users:` registry fallback).
4. **If no allow-list is configured, the gate refuses to pass from a comment signal** — stays pending and logs an explicit error. The default is safe.
5. On a valid `match_keyword`: append `✅` locally, post confirmation append comment remotely.
6. On a valid `reject_keyword`: append `❌` locally with reason; gate enters `human-rejected` terminal state (no auto-retry).
7. On a match from an unauthorized author: log and ignore; post advisory comment explaining who is authorized.

The rule repeated verbatim in every `signal: comment` human-gate verifier:

> **Agents MUST NEVER post the signal keyword comment for a human gate, suggest automating it, impersonate an authorized reviewer, or bypass the authorization allow-list. This is a non-negotiable autonomy control.**

**Why this carve-out is safe.** The gate framework still does not *store* state remotely. The only remote *read* is for a narrowly-defined signal pattern (keyword + authorized author), documented as a deliberate exception. The alternative — forcing every remote reviewer onto the local shell — defeats the motivation.

### Dispatcher Backend Requirements

| Backend function | Status | Used by |
|---|---|---|
| `add_label(issue, label)` | Already exists for GitHub, GitLab, Bitbucket | Label mirror |
| `remove_label(issue, label)` | Already exists for all three | Label mirror |
| `post_comment(issue, body)` | Already exists for all three | Singleton creation, event append |
| `edit_comment(comment_id, body)` | **Needs to be added** | Singleton update |
| `list_comments(issue, since=<ts>)` | **Needs to be added** on some platforms | Human-gate comment signal |

**Gap analysis.** Two backend gaps: `edit_comment` and `list_comments`. Both are small additions. Rolling out the label mirror first (which needs no new backends) lets the gate framework ship with partial remote projection; the comment mirror lands in a follow-up when the backend gaps close.

### Configuration Reference

| Flag | Location | Default | Purpose |
|---|---|---|---|
| `label_mirror.enabled` | `gates.yaml` | `true` | Master switch for label mirror |
| `label_mirror.label_prefix` | `gates.yaml` | `ait-gate` | Label namespace prefix |
| `label_mirror.emit_on_terminal_only` | `gates.yaml` | `true` | Terminal-only vs chatty mode |
| `comment_mirror.enabled` | `gates.yaml` | `true` | Master switch for comment mirror |
| `comment_mirror.singleton_marker` | `gates.yaml` | `> **🚦 ait-gates**` | Singleton comment marker |
| `comment_mirror.event_comments_enabled` | `gates.yaml` | `true` | Post notable-event comments |
| `gate_authorized_users.<gate>` | `gates.yaml` | `[]` | Project-level allow-list for human-gate signals |
| `gate_signal_poll_interval` | profile | `60s` | How often pending human gates check for new comments |
| `gate_labels_chatty` | profile | `false` | Opt-in to non-terminal label emission |
| `commit_gate_logs` | profile | `false` | Whether sidecar logs are committed to git |

### Failure Modes and Recovery

| Failure | Behavior | Recovery |
|---|---|---|
| Network error during `add_label` | Sidecar not updated; orchestrator logs warning and continues | Next `ait gates run` diffs current vs sidecar and retries |
| `edit_comment` backend missing | Degrades to posting a new singleton comment per update | Close the backend gap; subsequent runs use `edit_comment` |
| Singleton comment deleted by reviewer | Orchestrator detects missing comment ID, re-creates singleton | Automatic on next update |
| Comment matches keyword but author is unauthorized | No gate transition; advisory comment posted | Reviewer re-posts from authorized account |
| Race — two orchestrator invocations updating same singleton | Task-level file lock serializes orchestrator runs | Automatic |
| Human manually removes an `ait-gate:*` label | Orchestrator never reads labels; no effect on local state | No action needed |
<!-- /section: remote_projection -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

All explicit and implicit assumptions from this proposal:

- **Task file is the single source of truth.** The local task file (not any remote issue tracker or cache) holds the canonical gate state between invocations. The remote projection is read-only.
- **No persisted gate status fields.** There are no `gates_passed` or `gates_failed` frontmatter keys. Pass/fail/pending/blocked status is always *derived* from the `## Gate Runs` section on every read. This is a deliberate design choice to prevent drift between frontmatter and the event log.
- **Orchestrator is stateless.** The orchestrator skill re-derives everything from the task file and gate registry on each run. It holds no in-memory or file state between invocations beyond the sidecar files documented above.
- **Explicit `gates:` list overrides `default_gates`.** A task's explicit `gates:` list is authoritative. `default_gates` in the registry is only used when the task has no `gates:` field at all.
- **Agents must never self-signal human gates.** The rule that agents must never create signals for human gates, suggest automating their creation, or bypass their absence is a non-negotiable autonomy control. It is repeated verbatim in every human-gate verifier skill and in the registry description field.
- **Remote projection is read-only with one narrow carve-out.** Labels and comments on the remote issue are a read-only projection. The one carve-out — reading authorized keyword comments for `signal: comment` human gates — is explicitly documented and bounded by an authorization allow-list.
- **`status: Done` transition is human-initiated.** When all gates pass, the orchestrator suggests `status: Done` but does not auto-apply it. The transition remains a human decision, or a profile-gated auto-transition for the `aitask-pickrem` autonomous lane.
- **Gates are active only during `Implementing`.** A task's gates become blocking only when `status: Implementing` is set. In `Ready` or `Editing` states, gates are advisory. In `Postponed` or `Folded` states, gate evaluation is frozen.
- **Framework is purely additive.** An aitasks installation that never declares `gates:` in any task file behaves exactly as today. No existing skill, TUI, or tool needs to be modified to remain functional.
- **Existing task-level file lock can be reused.** The lock mechanism already present in aitasks for frontmatter writes is reused by the orchestrator and `ait gate append` to serialize concurrent appends from parallel machine-gate runs.
- **No cross-task gate dependencies in v1.** A task's gates can only depend on other gates within the same task, not on gates from a parent or sibling task.
<!-- /section: assumptions -->

<!-- section: open_questions -->
## Open Questions

Deferred items and open questions that need resolution before or after implementation:

1. **Gate set resolution order.** If a task has `gates: [a, b]` and the registry's `default_gates: [a, b, c]`, does `c` also apply? *Proposal*: no. The task's explicit list is authoritative; `default_gates` is only used when the task has no `gates` field.

2. **Project-level vs task-level gate overrides.** Can a task override `max_retries` for a specific gate without forking the registry? *Proposal*: allow a mixed form — `gates: [{name: tests_pass, max_retries: 5}, review, docs_updated]`. Deferred until a real need appears.

3. **Gate dependencies on artifacts, not other gates.** Some gates should only run if certain files changed (`docs_updated` is pointless if nothing in `docs/` changed). *Proposal*: add an optional `applies_when:` predicate in the registry. The verifier shortcircuits to `skip` if the predicate yields empty output. Keep `skip` distinct from `pass` so the history shows the gate was evaluated.

4. **Cross-task gates.** A task that depends on another task's gate (e.g. `parent:t40:review`). Not supported in v1; defer until the need arises.

5. **Gate renaming / registry migration.** What happens to a task's `gates: [old_name]` after the registry renames `old_name → new_name`? *Proposal*: the orchestrator refuses to run unknown gates, reports the drift, and suggests `ait gates migrate <task-id>` to rewrite the task list against the current registry.

6. **Parallel concurrency ceiling.** How many machine gates should run in parallel by default? *Proposal*: profile flag `max_parallel_gates: 2`, capped by available cores for CPU-bound gates.

7. **Interaction with the brainstorm DAG engine.** Should a brainstorm DAG node produce a task with a computed gate set based on its proposal type? *Proposal*: yes, but deferred to a follow-up proposal after this framework lands.
<!-- /section: open_questions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Design tradeoffs made in this proposal:

- **Marker-first blockquote over paired fences.** The gate run log format uses marker-first blockquotes rather than paired open/close fences (`>>>>` / `<<<<`). Rationale: any format with matched delimiters risks mismatch when identical gates run back-to-back (e.g. `tests_pass` fails twice), and `>>>>` at line start is already valid nested markdown that renderers may mangle. Marker-first is grep-friendly, survives human markdown edits, and does not require a custom parser.

- **Derived state over persisted status fields.** There are no `gates_passed` or `gates_failed` frontmatter keys. Status is always re-derived from the Gate Runs section on every read. This eliminates drift between frontmatter and the event log at the cost of a per-read backward scan. The scan is bounded by the `## Gate Runs` section size and is fast in practice.

- **Local task file as authority over remote issue tracker state.** The task file holds the canonical gate state, not the remote issue tracker. This preserves aitasks's local-first model and keeps the framework functional without a network connection. The tradeoff is that remote collaborators (reviewers, maintainers) need the Appendix A projection layer to observe and interact with gate state — they cannot drive it directly from the issue tracker.

- **Terminal-only label emission (debounced) over real-time labels.** The label mirror emits only when a gate reaches a terminal state (pass, exhausted, pending-human), not during intermediate retries or transient failures. This avoids label flapping on the remote issue (a reviewer seeing labels appear and disappear on every retry) at the cost of less granular real-time visibility. Chatty mode is opt-in via the `gate_labels_chatty` profile flag.

- **Bash/awk primary implementation with Python fallback.** Gate marker parsing is implemented in bash using `awk` as the primary path, consistent with aitasks's existing bash-centric tooling. A Python fallback (`scripts/gates.py`) provides a drop-in replacement for edge cases (nested blockquotes, gate names with special characters, multiline output with `>` characters). The fallback is activated via `AIT_GATES_BACKEND=python` or automatic detection of `awk` parse failure. This avoids introducing a mandatory Python dependency for a core bash workflow.

- **Supplement `status` rather than replace it.** The gate framework works alongside the existing `status` enum rather than replacing it with a richer state machine. The `status` field retains its role as the coarse lifecycle indicator; gates operate within the `Implementing` state. This preserves backward compatibility (all existing skills continue to read `status` unchanged) but means the lifecycle has two layers that must be kept consistent.
<!-- /section: tradeoffs -->
--- PROPOSAL_END ---
