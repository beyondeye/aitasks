--- PATCHED_PLAN_START ---
# Gate Framework Implementation Plan — Phase 1: Infrastructure Only

## Scope

This plan covers **Phase 1: Gate Infrastructure** — the data model, registry,
orchestrator, verifier contract, CLI tooling, and sidecar log structure that
form the self-contained foundation of the gate framework.

**Explicitly out of scope (deferred to Phase 2 — see Deferred section below):**
- Integration with existing skills (`task-workflow`, `aitask-pick`,
  `aitask-pickrem`, `aitask-archive`, `aitask-contribute`)
- Making `aitask-pick` gate-aware (modular with visible gate progress in
  task status displays)
- Refactoring existing gate-like features into formal gates
- Parent/child task gate semantics (see Open Questions below)
- Remote projection (label mirror, comment mirror) — optional; can ship after
  core infrastructure is working

Phase 2 requires a separate design/brainstorm session. The infrastructure
built in Phase 1 must be complete and stable before Phase 2 begins.

---

## Phase 1 Deliverables

### Step 1 — Schema: `gates` frontmatter field

Add `gates` as a list field to the task frontmatter schema. Three layers as
per CLAUDE.md "Adding a New Frontmatter Field":

1. **Write path:** `aitask_create.sh` — add `--gates` batch flag, interactive
   prompt, and serialization in `create_task_file`. Mirror in
   `aitask_update.sh` with `--add-gate` / `--remove-gate` flags.
2. **Fold machinery:** `aitask_fold_mark.sh` — union the `gates` lists of the
   primary and folded tasks.
3. **Board TUI:** `aitask_board.py` `TaskDetailScreen.compose()` — add a
   `GatesField` widget (read-only list display; gates are run via CLI, not
   from the board). Wire into `compose()` following the `DependsField` pattern.

Gates field semantics:
- Absent or empty `gates:` → no gates active, behaves exactly as today
- The field is an ordered list of gate names; all metadata resolved from
  `aitasks/metadata/gates.yaml` at orchestration time
- No `gates_passed` / `gates_failed` persisted fields — state is always
  derived from the `## Gate Runs` event log

### Step 2 — Gate registry: `aitasks/metadata/gates.yaml`

Create the registry file with standard gates:

```yaml
default_gates: [tests_pass, review, docs_updated]

gates:
  tests_pass:
    verifier: aitask-gate-tests-pass
    type: machine
    max_retries: 3
    description: "Run project test suite; all must pass"
    timeout_seconds: 900

  lint:
    verifier: aitask-gate-lint
    type: machine
    max_retries: 2
    unlocks: [tests_pass]
    description: "Run project linters and formatters"

  review:
    verifier: aitask-gate-review
    type: human
    max_retries: 0
    signal: file-touch
    signal_target: ".aitask-gates/<task-id>/review.signed"
    description: "Human review — reviewer signals pass via `ait gate pass <task> review`"

  docs_updated:
    verifier: aitask-gate-docs-updated
    type: machine
    max_retries: 2
    unlocks: []
    description: "Check and update docs if needed"
```

Wire the seed file:
- Add `seed/gates.yaml` and wire `install_seed_gates_yaml()` in `install.sh`
- Follow the same pattern as `install_seed_project_config()` (see CLAUDE.md
  note on testing the full install flow)
- Add `seed/gates.yaml` to all seed config copies

### Step 3 — CLI entry point: `scripts/gates.sh` (new helper script)

New helper script at `.aitask-scripts/aitask_gates.sh`. Implements:

```
ait gates list <task-id>           — declared gates from frontmatter
ait gates status <task-id>         — derived per-gate status (pass/fail/pending/blocked)
ait gates unlocked <task-id>       — gates runnable right now
ait gates run <task-id>            — invoke orchestrator (alias: aitask-run-gates)
ait gate append <task> <gate> <status> <attempt> <run-id> [k=v ...]
                                   — atomic append of a run block (used by verifiers)
ait gate pass <task-id> <gate>     — create signal for a human gate (refuses for machine)
ait gate fail <task-id> <gate> [--reason "..."]
                                   — manual fail marker
ait gate log <task-id> <gate>      — print most-recent sidecar log
```

Implementation notes:
- Gate Runs parser: `awk`-based primary; `AIT_GATES_BACKEND=python` or
  auto-fallback to `scripts/gates.py` (stdlib only) for edge cases
- Atomic append: tempfile write → `mv`; `flock` on task file for concurrent
  verifier serialization
- Create `.aitask-gates/<task-id>/` on first append

**5-touchpoint whitelist** (CLAUDE.md requirement — all five must be updated):

| Touchpoint | Entry |
|---|---|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_gates.sh:*)"` |
| `.gemini/policies/aitasks-whitelist.toml` | `commandPrefix = "./.aitask-scripts/aitask_gates.sh"` |
| `seed/claude_settings.local.json` | mirror |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_gates.sh *": "allow"` |

### Step 4 — Orchestrator skill: `aitask-run-gates`

Create `.claude/skills/aitask-run-gates/SKILL.md`. Implements the stateless
re-entrant decision tree from the proposal (see Orchestrator section):

- Read task file + gate registry on every invocation
- Parse `## Gate Runs` section (back-to-front scan, first block per gate = current state)
- Compute unlocked set; dispatch all unlocked machine gates in parallel via
  Task tool; pend unlocked human gates
- Stopping heuristic: 2 identical failures with no intervening task-file change
  → treat gate as exhausted, ask human to intervene
- Re-enter until no new state change
- On all gates pass: suggest `status: Done` (do not auto-apply)

Re-entry contract guarantees:
1. Idempotent on no-op
2. Skip-already-passed (unless `--gate <name>` forced)
3. Retry within budget
4. Stop at pending-human (never self-signal)
5. No frontmatter writes (appends to `## Gate Runs` only)

Port to `.gemini/`, `.agents/`, `.opencode/` after Claude Code version stable.

### Step 5 — Verifier template skill: `aitask-gate-template`

Create `.claude/skills/aitask-gate-template/SKILL.md` scaffold:
- Standard argument signature: `<task-id> <attempt-number> <run-id>`
- Stub verification block + example sidecar log write
- Example `ait gate append` invocation
- Verbatim human-gate rule (cannot be changed): "Agents MUST NEVER create
  the signal for a human gate."

Port to other agents after Claude Code version.

### Step 6 — Example verifier skills

Implement at minimum the standard gates from the registry (can be done
incrementally — Step 2's registry ships before all verifiers exist):

- `aitask-gate-tests-pass` — invokes `mise run test` (or project-configured runner)
- `aitask-gate-lint` — invokes `shellcheck` / project linter
- `aitask-gate-docs-updated` — scans for stale cross-references; updates if found
- `aitask-gate-review` — human gate, file-touch signal

### Step 7 — Sidecar structure and git-ignore

- Add `.aitask-gates/` to `.gitignore` (controlled by profile flag `commit_gate_logs: false`)
- Profile flags to seed into `aitasks/metadata/profiles/`:
  - `commit_gate_logs: false` (default)
  - `max_parallel_gates: 2` (default)

### Step 8 — Remote projection (optional — defer until core infrastructure works)

Ship this as a follow-up child task after Steps 1-7 are stable:
- Label mirror: `ait-gate:<name>:<terminal-state>` debounced emission
- Comment mirror: singleton status comment + notable-event append comments
- Dispatcher backend additions: `edit_comment`, `list_comments`
- Human-gate `signal: comment` with authorization allow-list

### Step 9 — Tests

- Backward-compatibility: task without `gates` field behaves as today
- Atomic append: simulate concurrent verifier appends, verify no interleaving
- Orchestrator re-entry: skip-passed, retry-within-budget, stop-at-human
- Parser round-trip: awk and Python fallback produce identical output
- Stopping heuristic: 2 identical failures triggers exhausted state
- Full install flow: `bash install.sh --dir /tmp/scratch` → `ait setup` →
  verify `gates.yaml` in place (per CLAUDE.md install flow testing rule)

---

## Deferred: Phase 2 — Integration with Existing Skills

**Phase 2 requires a separate brainstorm/design session.** The following
open design questions must be resolved before implementation begins.

### Integration with `aitask-pick` / `task-workflow`

**Existing gate-like features** already present in the framework — candidates
for refactoring as formal gates in Phase 2:

| Current feature | Current location | Candidate gate |
|---|---|---|
| Manual verification follow-up | `task-workflow` Step 8c | `gate:manual_verification` (human) |
| Source defect identification follow-up | `task-workflow` Step 8X | `gate:source_defect_check` |
| Plan quality / plan review decision | `task-workflow` planning step | `gate:plan_review` |
| Pre-archive quality check | `aitask-archive` | `gate:archive_ready` (machine) |

These are currently implemented as ad-hoc "spawn a follow-up task" steps.
Refactoring them as formal gates would make multi-pass progress visible in
task status and remove duplicated control flow. Whether to replace or
complement the current follow-up task spawning needs design.

**Questions to resolve in the Phase 2 design session:**

1. How does `aitask-pick` surface gate status? Options:
   - Column in board TUI showing `3/4 gates passed`
   - Status line hint in CLI pick output
   - Filter: only offer tasks with all gates passed to certain profiles

2. Does `task-workflow/implementation.md` §Verify become `ait gates run`?
   Migration must be backward-compatible (tasks without `gates` field
   keep current verification steps).

3. Should gate outcomes auto-spawn follow-up tasks (current behavior) or
   replace the follow-up spawning? Hybrid option: a gate that fails can
   spawn a child task for the failing dimension, making retries trackable.

4. How does `aitask-pickrem` (autonomous lane) interact with human gates?
   Infrastructure already supports stopping at pending-human; profile
   integration wiring needs design.

5. Should `aitask-archive` refuse to archive if declared gates are not all
   passed? (Profile-gated behavior; already sketched in the proposal.)

### Parent/child task gate semantics (open question for Phase 2)

The current proposal does not address this. Three options:

**Option A — Gates only on leaf tasks (children).**
Parent "done" when all children reach Done+gates-passed. Simplest model;
no new orchestration logic for the parent level.

**Option B — Gates on both parent and children independently.**
Children have granular gates (unit tests, lint per-child-scope). Parent
has integration-level gates (integration tests, human review of the whole
feature). Most expressive; requires orchestrator to understand parent/child
relationships.

**Option C — Parent has implicit "all-children-passed" gate plus optional
integration gates.**
Children as in A; parent adds its own gates on top of the implicit
all-done prerequisite. Balanced expressiveness with manageable complexity.

**Recommended starting point for Phase 2:** Option C. It preserves the
current parent/child completion model while allowing integration-level gates
at the parent. The implicit "all-children-passed" prerequisite can be modeled
as a synthetic gate computed from child task states.

This decision affects: `aitask_fold_mark.sh`, `aitask-archive`, and the
orchestrator's dependency resolution. Surface as the first open question in
the Phase 2 design session.

---

## Open Questions (Phase 1 only)

1. **Gate set resolution.** Task's explicit `gates:` list is authoritative;
   `default_gates` only used when no `gates` field exists. Confirm before
   wiring `ait gates list`.

2. **Task-level `max_retries` override.** Allow `gates: [{name: tests_pass, max_retries: 5}]`
   mixed form? Defer until a real need appears.

3. **`applies_when:` predicate.** Optional per-gate predicate; verifier shortcuts
   to `skip` if predicate is false. Keep `skip ≠ pass` so history shows gate
   was evaluated.

4. **Parallel concurrency ceiling.** Profile flag `max_parallel_gates: 2`;
   capped by CPU count for CPU-bound gates.
--- PATCHED_PLAN_END ---

--- IMPACT_START ---
**NO_IMPACT**

Justification: The patch reorganizes implementation scope — narrowing this
node to infrastructure only and deferring skill integration to Phase 2 —
without changing any architectural dimension in the node metadata.

- All `component_*` values remain accurate: the infrastructure components
  (registry, orchestrator, verifier contract, gate CLI, sidecar logs, remote
  projection) are unchanged; remote projection is merely deferred within this
  node, not removed.
- All `assumption_*` values still hold for the infrastructure scope.
- No `requirements_*` constraint is violated: all five requirements
  (stateful_reentry, multi_dimensional_state, parallel_verification,
  local_file_authority, human_gate_safety) describe the gate framework
  mechanics, not its integration with `aitask-pick` or `task-workflow`.

The `description` field is updated in Part 3 to reflect the narrowed scope,
but this is a label change, not an architectural change. Explorer regeneration
is not required.
--- IMPACT_END ---

--- METADATA_START ---
node_id: n001_infra_only
parents: [n000_init]
description: 'Gate framework Phase 1: infrastructure only — registry, orchestrator,
  verifier contract, CLI tooling, and sidecar logs. Skill integration
  (aitask-pick, task-workflow, parent/child semantics) deferred to Phase 2.'
proposal_file: br_proposals/n000_init.md
created_at: 2026-05-04 12:52
created_by_group: patch_001
reference_files:
- aidocs/gates/aitask-gate-framework.md
- aitasks/t635_gates_framework.md
requirements_stateful_reentry: Re-running a skill on the same task must skip already-done
  work and resume from the first unmet gate
requirements_multi_dimensional_state: Tests, review, and docs states must be independently
  trackable and passable, not collapsed into one linear status
requirements_parallel_verification: Machine gates with no dependency relationship
  must be runnable concurrently
requirements_local_file_authority: Task file must be the single source of truth; remote
  surfaces are read-only projections
requirements_human_gate_safety: "Agents must never create signals for human gates\
  \ — non-negotiable autonomy control"
assumption_local_file_authority: Local task file is the authoritative gate state store;
  remote issue tracker is a projection only
assumption_additive_adoption: "Tasks without a gates field behave exactly as today\
  \ — the framework is fully backward-compatible"
assumption_no_persisted_gate_status: No gates_passed or gates_failed fields exist;
  status is derived from Gate Runs section on every read
assumption_marker_first_format: "Gate run records are marker-first blockquotes —\
  \ self-delimiting and grep-friendly without custom parsing"
assumption_task_gate_list_authoritative: Task explicit gates list is authoritative;
  default_gates in registry used only when task has no gates field
assumption_human_gate_non_automatable: Human gate signals must come from humans; agents
  must never bypass or automate signal creation
assumption_orchestrator_stateless: The orchestrator re-derives all gate state on every
  invocation; it holds no cross-invocation state of its own
component_gate_registry: "aitasks/metadata/gates.yaml — per-gate config: verifier\
  \ skill, type, max_retries, unlock DAG, signal config"
component_orchestrator_skill: "aitask-run-gates — stateless re-entrant skill\
  \ that reads task + registry, computes unlocked set, and dispatches verifiers"
component_verifier_skills: "aitask-gate-<name> skill family — individual gate\
  \ checkers following a standard five-step contract"
component_gate_runs_section: "append-only ## Gate Runs section in task body —\
  \ the event log from which derived gate state is computed"
component_gate_cli: "scripts/gates.sh — ait gates/gate subcommands: list, status,\
  \ unlocked, run, append, pass, fail, log"
component_sidecar_logs: ".aitask-gates/<task-id>/ — per-run verifier output logs\
  \ and remote mirror state cache"
component_remote_projection: label mirror + singleton comment + event comments via
  existing multi-platform dispatcher
tradeoff_marker_vs_fences: "Marker-first blockquotes chosen over paired fences —\
  \ grep-friendly and avoids mismatched-closer bug on back-to-back same-gate runs"
tradeoff_derived_vs_persisted_state: "Gate status derived from event log on every\
  \ read rather than stored as fields — eliminates drift at cost of re-parsing"
tradeoff_local_authority_vs_remote_feedback: Local file stays authoritative; one narrow
  carve-out for reading authorized comment signals from human gates
tradeoff_bash_vs_python_parser: Primary gate-run parser is bash/awk; Python escape
  hatch available when awk edge cases arise (AIT_GATES_BACKEND=python)
--- METADATA_END ---
