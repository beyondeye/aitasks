---
Task: t906_module_ops_apply_hardening_tests.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# t906 — Module-ops apply hardening tests

## Context

t906 is the **"after" risk-mitigation chore** that t756_3 (brainstorm
`module_decompose` / `module_merge` ops) created to cover its own
*code-health* risk. t756_3 added a new agent lifecycle shape — a multi-output
decomposer parser, a dedicated auto-apply poller, group-metadata-driven apply,
and live `--link-to-task` child creation — but shipped with only happy-path
unit tests (`tests/test_brainstorm_apply_module_ops.py`, 3 tests). The risk:
regressions in parsing robustness, idempotent auto-apply, persisted-state
restore, and the create-script contract would slip through.

**Goal:** add higher-level integration/contract coverage for the four risk
surfaces named in the task — module-agent **auto-apply** (the needs-apply gate
+ idempotency the Textual poller relies on), **group metadata** restore,
**multi-output parsing** robustness, and **linked child-task creation with a
stubbed create script** — without touching production code.

## Approach

Add one new test module, `tests/test_brainstorm_module_ops_integration.py`
(unittest, auto-discovered by `tests/run_all_python_tests.sh` via the
`test_*.py` glob; runnable standalone like the existing file). Keep it separate
from `test_brainstorm_apply_module_ops.py` so the existing happy-path *unit*
tests stay distinct from these *integration/contract* tests. Reuse the existing
file's `_seed_base()`, `_module_block()`, `_node_output()` helpers (copied/
adapted) and the `patch("brainstorm.brainstorm_session.crew_worktree", ...)`
pattern.

All target functions live in
`.aitask-scripts/brainstorm/brainstorm_session.py` and are pure /
filesystem-only (no Textual): `apply_module_decomposer_output`,
`apply_module_merger_output`, `apply_module_decompose_from_sections`,
`_module_decomposer_needs_apply`, `_module_merger_needs_apply`,
`record_operation`, `_create_linked_module_task`, `_write_module_task`,
`_module_tasks_map`.

### Group A — Multi-output parser robustness (decomposer)
Drives `apply_module_decomposer_output` with malformed agent output to lock in
the guard `ValueError`s (currently untested):
- empty `MODULE_NAME` block → `ValueError` ("MODULE_NAME block cannot be empty").
- `NODE_YAML` missing `node_id` → `ValueError` ("missing node_id").
- duplicate node id (node file already exists) → `ValueError` ("already exists").
- well-formed 3-module block → asserts all three roots created in document
  order with correct `module_label`/`parents`, confirming the regex
  `_MODULE_NODE_BLOCK_RE` splits multiple blocks (extends the existing 2-block
  case).

### Group B — Auto-apply gate + idempotency contract
The Textual `_poll_module_agents` / `_try_apply_module_agent_if_needed` App
methods (`brainstorm_app.py:4433–4504`) can't run headless, but their decision
contract is the pure pair `_module_decomposer_needs_apply` /
`_module_merger_needs_apply` plus apply idempotency. Tests:
- decomposer: `needs_apply` is `False` when output file absent; `True` when a
  completed output is on disk but nodes aren't created yet; `False` again after
  `apply_*` runs (proves the poller applies **exactly once** and then discards
  the agent — the `_try_apply_module_agent_if_needed` "not needs_apply →
  discard" path).
- merger: same before/after-apply transition (`_module_merger_needs_apply`
  delegates to `_explorer_needs_apply`).
- The test module will document (comment + plan Verification note) that the
  App-method timer wiring itself remains covered only by manual verification
  (t905) — scope-honest, no false "poller fully covered" claim.

### Group C — Group-metadata restore ("after restart")
Asserts apply reads **all** options back from `br_groups.yaml` rather than
in-memory args — the persistence contract that lets apply run after an app
restart:
- `record_operation(..., modules=, from_sections=True, subgraph=)` then
  `apply_module_decompose_from_sections(task, group_name)` succeeds reading
  `modules`/`head_at_creation` purely from disk; omitting `modules` from the
  group → `ValueError` ("requires modules").
- merger: `record_operation(..., source_subgraph=, destination_subgraph=)` then
  `apply_module_merger_output` reads both subgraphs from the group; missing
  destination → guard `ValueError`.

### Group D — Linked child-task creation with a stubbed create script
Covers `_create_linked_module_task` (relative `subprocess.run` of
`./.aitask-scripts/aitask_create.sh`) using a **real stub script** + `chdir`
(exercises the true subprocess + stdout-parse boundary, matching the task's
"stubbed create script" wording):
- Harness: temp repo root with `.aitask-scripts/aitask_create.sh` stub (records
  `$@` to a file, echoes a crafted created-path as the last stdout line),
  `os.chdir` into it (restored in `finally`).
- stub echoes `aitasks/t756/t756_1_parser_module.md` → returns `756_1`; assert
  recorded argv contains `--batch --commit --silent --parent 756 --name
  parser_module --type feature`.
- stub exits non-zero → `RuntimeError`; stub echoes an unparseable path →
  `ValueError`.
- **Headline integration test:** stub create script + `crew_worktree` patched
  to a temp worktree + `chdir`, record a decompose op with `link_to_task=True`,
  write a 1-module decomposer output, call `apply_module_decomposer_output`;
  assert the root node is created **and** `module_tasks[module]` is persisted
  into `br_graph_state.yaml` (read back via `_module_tasks_map`). This chains
  parser → apply → linked-task → persistence end-to-end.

## Files
- **New:** `tests/test_brainstorm_module_ops_integration.py` — the only file
  changed. ~12–14 `unittest` test methods across the four groups above.
- No production code changes. (If a test surfaces a real defect, it is recorded
  in the plan's "Upstream defects identified" per Step 8b — not silently
  patched here.)

## Verification
- `python3 tests/test_brainstorm_module_ops_integration.py` → all green.
- Regression: `python3 tests/test_brainstorm_apply_module_ops.py` and
  `python3 tests/test_brainstorm_groups_persist.py` still green.
- Full sweep: `bash tests/run_all_python_tests.sh` (or at least the
  `test_brainstorm_*.py` subset) shows no new failures.
- Manual-verification gap (Textual poller timer wiring, live agent launch) is
  explicitly out of scope here and owned by t905.

## Risk

### Code-health risk: low
- Test-only, additive change in a single new file; no production code touched,
  no shared helper edited, zero blast radius on runtime paths · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The Textual auto-apply poller App-methods (`_poll_module_agents`,
  `_try_apply_module_agent_if_needed`) are not headless-testable, so coverage
  of "auto-apply" is the pure needs-apply gate + idempotency contract rather
  than the timer wiring; this is a bounded, deliberately-scoped gap already
  owned by the manual-verification task t905, not an unmet requirement · severity: low · → mitigation: t905 (existing)

## Step 9 (Post-Implementation)
Single-task flow: review (Step 8) → commit `test: Add module-ops apply
hardening tests (t906)` → consolidate this plan with Final Implementation Notes
→ `./.aitask-scripts/aitask_archive.sh 906`.
