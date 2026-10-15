---
Task: t1995_fix_brainstorm_from_sections_decompose_no_reload.md
Base branch: main
Output branch: main
---

# t1995 — Reload the brainstorm session after a from-sections Module Decompose

## Context

In `ait brainstorm`, Module Decompose with "From section markers" is
deterministic (no agent). Its branch of `BrainstormApp._run_design_op`
(`.aitask-scripts/brainstorm/brainstorm_app.py:5662-5680`) calls
`apply_module_decompose_from_sections(...)`, which creates one module-root
node per module and moves each module's HEAD. Then it only sends a
notification. It never calls `_load_existing_session`, so the Browse node list,
the DAG and the module status keep showing the pre-op session. Nothing else
redraws them: `_refresh_runtime` (every 30s) only refreshes the status strip
and the Running tab.

The sibling deterministic op, `prune_dimensions` (same function, lines
5695-5716), does reload: once after success, and once on `PrunePartialFailure`
before re-raising.

There is also a failure path. `apply_module_decompose_from_sections`
(`brainstorm_session.py:1331-1409`) validates each module's section *inside*
the creation loop. If module 2 has no matching section, module 1's root node
and HEAD move are already on disk when the `ValueError` is raised. The same is
true if `_create_linked_module_task` fails after `create_node`/`set_head`. So a
failed from-sections op can still leave new nodes on disk, and the UI must
reload on failure too.

This bug was found by reading the code and has not been reproduced. Step 1
below confirms it with a failing test before the fix.

## Changes

### 1. Red test first — `tests/test_brainstorm_from_sections_reload.py` (new)

This boots the real `BrainstormApp` over a temp session and drives the real
`_run_design_op` worker. The harness setup copies
`tests/test_brainstorm_group_recovery.py` `GroupRecoveryActionTests.setUp`:
point `ac_mod.AGENTCREW_DIR` / `bs_mod.AGENTCREW_DIR` at a tmpdir, call
`bs_mod.crew_worktree(TASK).mkdir`, then `bs_mod.init_session(...)`. Restore
both in `tearDown`.

Seeding: overwrite `n000_init`'s proposal with two sections
(`parser [dimensions: component_parser]`, `cache [dimensions: component_cache]`),
and add `component_parser` / `component_cache` to the `n000_init` node yaml.
This is the same fixture shape as
`tests/test_brainstorm_module_ops_integration.py:360` (`GroupMetadataRestoreTests`).

Driving: inside `async with app.run_test(...)`, settle, then set
`app._wizard_op = "module_decompose"`,
`app._wizard_config = {modules, from_sections: True, link_to_task: False,
subgraph: UMBRELLA_SUBGRAPH, review_before_apply: True, instructions: "",
launch_mode: DEFAULT_LAUNCH_MODE}` and
`app._wizard_subgraph = UMBRELLA_SUBGRAPH`. Then call `app._run_design_op()`
and drain with `await app.workers.wait_for_complete()` plus a settle.
`aidocs/framework/testing_conventions.md` says draining is the right tool for
a test that deliberately drives a real worker. This worker catches its own
exceptions and turns them into a notify, so it never raises through the drain.

The reload refreshes three Browse surfaces, so each test asserts all three.
A refresh that rebuilt only some of them must not pass:
- the node list: the set of `NodeRow.node_id`;
- the graph: `DAGDisplay._node_order`;
- the module summary: `str(app.query_one("#module_status_info", Label).render())`,
  written by `_update_module_status` (`brainstorm_app.py:5074`).
  `tests/test_brainstorm_module_status_contract.py:387-414` reads the label
  the same way.

Before the op runs, each test also asserts a precondition: the umbrella-only
session's module summary contains `no modules`. This proves the label starts
out stale and that the later assertion detects a refresh rather than a value
that was already there.

Tests:
- `test_success_shows_new_module_roots`: `modules=["parser", "cache"]`. After
  the drain, the node list and the DAG both contain the two
  `n00X_module_decomposer_sections_*` ids. The module summary contains both
  `parser` and `cache` and no longer contains `no modules`.
- `test_partial_failure_shows_roots_created_before_the_error`:
  `modules=["parser", "missing"]`. `parser`'s root lands, then `missing`
  raises. After the drain:
  - the parser root is in the node list and in the DAG;
  - the module summary contains `parser`, does not contain `missing`, and no
    longer contains `no modules`;
  - no `missing` root exists on disk.

  This is the mirror of the prune branch's `PrunePartialFailure` reload.

I'll run the file against the unfixed code and record that both tests fail
because the new ids are missing from the node list and the DAG and the module
summary still reads `no modules`, not because of a harness error. That
confirms the symptom (task step 1). If they pass
unfixed, the bug is not real: stop and report that instead of changing code.

The new module is a Textual pilot test that is not in the four live-tmux
serial carve-outs, so it needs no runner change.

### 2. Fix — `.aitask-scripts/brainstorm/brainstorm_app.py` from-sections branch

Wrap the apply call the same way the prune branch is wrapped, with a comment
in the same voice:

```python
                    try:
                        created = apply_module_decompose_from_sections(
                            self.task_num, group_name
                        )
                    except Exception:
                        # Roots created before the failure (and their HEAD
                        # moves) are already on disk — show them.
                        self.call_from_thread(self._load_existing_session)
                        raise
                    self.call_from_thread(self._load_existing_session)
                    msg = "Created module roots from sections: " + ", ".join(created)
```

`raise` sends the error to the existing outer `except Exception` →
"Operation failed: …" notify, so error reporting does not change. The
reload is idempotent and already runs on many paths (init, every agent
apply, prune). On a refusal before any write it just redraws the same
state. The agent-backed decompose branch is not touched: its apply already
reloads via `_try_apply_module_agent_if_needed`.

### 3. Green

Run the new file and the neighbouring brainstorm suites (below).

## Out of scope

On a from-sections failure, the group record written by `record_operation`
stays `status: Waiting`, because `apply_module_decompose_from_sections` only
writes `Completed` and never `Error`. This is a separate, pre-existing
record-keeping defect, so it is not fixed here. I'll weigh it at Step 8b as an
upstream-defect follow-up.

## Verification

- `python3 -m pytest tests/test_brainstorm_from_sections_reload.py -q`: red
  before the fix (step 1), green after it.
- Neighbouring suites stay green:
  `tests/test_brainstorm_module_ops_integration.py`,
  `tests/test_brainstorm_apply_module_ops.py`,
  `tests/test_brainstorm_prune_dimensions.py`,
  `tests/test_brainstorm_group_recovery.py`,
  `tests/test_brainstorm_node_action_modal.py`.
- Then `bash tests/run_all_python_tests.sh --test-dir tests` (or a narrowed
  `--test-dir`), reading only the final `PYTHON SUITE:` line.

## Step 9

After review, Step 9 (Post-Implementation) archives the task and plan.
Current-branch mode, so there is no branch merge.

## Risk

### Code-health risk: low
None identified. The change is one `try/except/raise` plus a second
`call_from_thread` in a single worker branch. It copies the adjacent prune
pattern exactly and calls a reload that is already called from many paths.

### Goal-achievement risk: low
None identified. Before the fix, the red test proves the symptom on the real
app and the real worker, on every surface the reload refreshes (node list,
DAG, module summary). It also covers the partial-failure path the task
description missed.

## Final Implementation Notes
- **Actual work done:** Implemented as planned.
  - `.aitask-scripts/brainstorm/brainstorm_app.py`: the from-sections branch of
    `_run_design_op` now wraps `apply_module_decompose_from_sections(...)` the
    same way the prune branch is wrapped. It calls
    `self.call_from_thread(self._load_existing_session)` after success, and
    again in an `except Exception:` handler before re-raising to the existing
    outer "Operation failed" notify.
  - New `tests/test_brainstorm_from_sections_reload.py`: two Textual pilot
    tests that drive the real worker on a real temp session. They assert all
    three surfaces the reload rebuilds (the `NodeRow` ids, `DAGDisplay._node_order`
    and the `#module_status_info` text), after a stale-before precondition
    (`{n000_init}` / `[n000_init]` / `no modules`).
- **Deviations from plan:** None. The module-summary assertions were added at
  plan review, before implementation (the user's concern: a list-and-graph-only
  refresh would otherwise pass).
- **Issues encountered:** None. The symptom reproduced exactly as predicted
  from reading the code.
- **Key decisions:**
  - The failure handler catches every `Exception` rather than a typed partial
    failure. `apply_module_decompose_from_sections` has no refused/partial
    distinction (prune has `PruneRefused` / `PrunePartialFailure`), and a reload
    after a write-free refusal only redraws the same state.
  - Each test reads every surface rather than one representative surface.
- **Upstream defects identified:**
  - `.aitask-scripts/brainstorm/brainstorm_session.py:1355-1408` —
    `apply_module_decompose_from_sections` never marks its operation record
    `Error` when it raises mid-loop. The group record that
    `record_operation(...)` writes in `_run_design_op` stays `status: Waiting`
    with `agents: []`, even though some module roots, their HEAD moves and
    `nodes_created` entries may already be on disk. By contrast,
    `apply_prune_dimensions` writes `status: Error` plus the stage reached
    (`brainstorm_session.py:1620`), and `run_prune_operation` keeps that
    record.

## Verification evidence (red → green, mutants)

Red run (unfixed code): both tests failed with
`AssertionError: 'n001_module_decomposer_sections_parser' not found in {'n000_init'}`,
after the on-disk and notify assertions had passed. A probe printing all three
surfaces on the unfixed code showed every surface stale in both cases:

```
['parser', 'cache'] disk: ['n001_module_decomposer_sections_parser', 'n002_module_decomposer_sections_cache']
  rows: ['n000_init']
  dag: ['n000_init']
  summary: — no modules —
['parser', 'missing'] disk: ['n001_module_decomposer_sections_parser']
  rows: ['n000_init']
  dag: ['n000_init']
  summary: — no modules —
```

After the fix, the same probe printed:

```
['parser', 'cache'] … rows/dag: n000_init, n001_…_parser, n002_…_cache
  summary: unstarted  cache (1) | unstarted  parser (1) | merged  root (1)
['parser', 'missing'] … rows/dag: n000_init, n001_…_parser
  summary: unstarted  parser (1) | merged  root (1)
```

Mutants, each run in an isolated copy of `.aitask-scripts/` + the test file:

| mutant | success test | partial-failure test |
|---|---|---|
| success-path reload removed | FAIL | pass |
| failure-path reload removed | pass | FAIL |
| both reloads → list + DAG only (no `_update_module_status`) | FAIL (`'no modules' unexpectedly found`) | FAIL (same) |

The neighbouring suites (`from_sections_reload`, `module_ops_integration`,
`apply_module_ops`, `prune_dimensions`, `group_recovery`, `node_action_modal`,
`module_status_contract`) passed: 117 tests.

Full suite (`bash tests/run_all_python_tests.sh --test-dir tests`, rc=0):
`PYTHON SUITE: PASSED (runner=pytest, exit=0)`. The parallel lane reported
8995 passed, 2 skipped; the serial carve-out reported 11 passed.
