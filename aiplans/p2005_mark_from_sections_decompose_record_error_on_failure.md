---
Task: t2005_mark_from_sections_decompose_record_error_on_failure.md
Base branch: main
Output branch: main
---

# t2005 — from-sections Module Decompose: give its operation record a failure boundary

## Context

`apply_module_decompose_from_sections` (`.aitask-scripts/brainstorm/brainstorm_session.py:1331-1409`)
checks each module's section **inside** its creation loop and writes
`status: Completed` only after the loop. If a module has no section, or
`_create_linked_module_task` fails, the function raises after earlier roots,
HEAD moves and `nodes_created` entries are already on disk. The group record
that `BrainstormApp._run_design_op` (`brainstorm_app.py:5663-5689`) wrote with
`agents=[]` stays `status: Waiting` permanently. A from-sections op has no
agent and no poller, so nothing ever completes the record, and the Running
tab shows it as waiting forever.

The prune op already handles this correctly (`apply_prune_dimensions` /
`run_prune_operation`, `brainstorm_session.py:1412-1667`):
- every read and check runs before the first write;
- a failure before the first write is a refusal (`PruneRefused`), and the
  runner deletes the record;
- a failure after the first write keeps the record, marks it `status: Error`
  with the stage reached, and re-raises `PrunePartialFailure`.

This plan gives the from-sections decompose the same failure boundary. It also
checks every module's section before the loop, so a missing section is refused
without writing anything instead of being applied partially.

## Implementation

### 1. `brainstorm_session.py` — preflight, failure classes, runner

**1a. Two exception classes**, placed just above `_section_for_module`. They mirror
`PruneRefused` / `PrunePartialFailure`:

```python
class ModuleDecomposeRefused(ValueError):
    """A from-sections Module Decompose was refused before anything was written.
    Raised only from the read-and-check phase, so the session on disk is exactly
    as it was and the operation record may be discarded."""

class ModuleDecomposePartialFailure(RuntimeError):
    """Failed after writing started. ``module`` is the module being created,
    ``stage`` the last write completed for it (none / counter_bumped /
    node_created / head_moved / node_recorded / task_created / task_recorded),
    ``created`` every root whose create_node completed. ``incomplete_node_id``
    is the id whose create_node raised part-way (it may have partial
    artifacts on disk), else None. Nothing is rolled back; the record is kept
    with status Error."""
    def __init__(self, group_name, module, stage, created, incomplete_node_id, cause): ...
        # message: "module decompose partially applied (module 'x', stage: s;
        #   created a, b; incomplete node c); operation record <group> kept:
        #   <Type>: <cause>"  — each "; …" part only when non-empty
```

**`create_node` is not atomic.** It writes the node YAML
(`brainstorm_dag.py:102`) before the proposal (`:105`), so a proposal-write
fault leaves a YAML-only node behind. The handler in 1c therefore treats a
failure at `stage == "counter_bumped"` (which can only be raised from inside
`create_node`, the sole call between the bump and the next stage) as
**incomplete node creation**:
- it keeps the attempted id as `incomplete_node_id`;
- it records that id under its own `incomplete_node` field;
- it never adds that id to `created` or `nodes_created`, which hold completed
  nodes only.

`ModuleDecomposeRefused` subclasses `ValueError`, so the existing
`assertRaisesRegex(ValueError, "requires modules")` test
(`test_brainstorm_module_ops_integration.py:393`) and the existing refusal
messages ("requires modules", "requires a source head", "source proposal
sections invalid") stay valid.

**1b. `_from_sections_preflight(wt, group_name)`**: read-only. It holds the code
that is currently at lines 1336-1353, plus the per-module work that does not
write (lines 1357-1384):
- read the group, its modules, `link_to_task` and the source head. Refuse when
  there are no modules or no head.
- `read_node`, `extract_dimensions`, `read_proposal`, `parse_sections`,
  `validate_sections`. Refuse on section errors.
- for **every** module, resolve `_section_for_module`, then compute
  `safe_module`, the filtered `dimensions` and `proposal_text`, using today's
  code unchanged. Collect every module that has no section. If any are
  missing, raise one refusal that names them all. A single missing module
  keeps today's text: `no section found for module 'missing'; expected a
  section named 'missing' or tagged with component_missing`. Several missing
  modules use the plural form and list each one.
- return `(source_node_id, source_data, link_to_task, plans)`, where `plans`
  is a list of `(module, safe_module, dimensions, proposal_text)`.

**1c. Rewrite `apply_module_decompose_from_sections`** with the same shape as
`apply_prune_dimensions`:
```python
wt = crew_worktree(task_num)
try:
    source_node_id, source_data, link_to_task, plans = _from_sections_preflight(wt, group_name)
except ModuleDecomposeRefused:
    raise
except Exception as exc:   # preflight only reads → any failure is a refusal
    raise ModuleDecomposeRefused(
        f"module decompose preflight failed: {type(exc).__name__}: {exc}") from exc

# Write phase. next_node_id() bumps the session counter, so it is the first mutation.
created: list[str] = []
module, stage, new_node_id = plans[0][0], "none", None
try:
    for module, safe_module, dimensions, proposal_text in plans:
        stage, new_node_id = "none", None
        new_node_id = f"n{next_node_id(wt):03d}_module_decomposer_sections_{safe_module}"
        stage = "counter_bumped"
        create_node(...same args as today...)
        created.append(new_node_id); stage = "node_created"
        set_head(wt, new_node_id, module=module); stage = "head_moved"
        update_operation(task_num, group_name, nodes_created=new_node_id); stage = "node_recorded"
        if link_to_task:
            task_id = _create_linked_module_task(task_num, module, <same desc>); stage = "task_created"
            _write_module_task(wt, module, task_id); stage = "task_recorded"
    update_operation(task_num, group_name, status="Completed")
except Exception as exc:
    record = {"status": "Error", "error": f"{module}: {stage}: {exc}"}
    incomplete = None
    if stage == "counter_bumped":
        # create_node raised part-way: it writes the node YAML before the
        # proposal, so the attempted node may be partly on disk. Name it, but
        # never as a created node.
        incomplete = new_node_id
        record["incomplete_node"] = incomplete
    elif stage in ("node_created", "head_moved"):
        record["nodes_created"] = new_node_id      # complete but not yet recorded
    try:
        update_operation(task_num, group_name, **record)
    except Exception:
        pass
    raise ModuleDecomposePartialFailure(
        group_name, module, stage, list(created), incomplete, exc) from exc
return created
```
On success the behaviour is unchanged: the same node ids, HEAD moves,
`nodes_created` entries, linked tasks and return value. Update the docstring to
describe the failure boundary, as `apply_prune_dimensions` does.

**1d. `run_module_decompose_from_sections(task_num, group_name, *, head_at_creation, subgraph=UMBRELLA_SUBGRAPH, **extras)`**
is the single entry point for the TUI, and mirrors `run_prune_operation`. It
calls `record_operation(..., operation="module_decompose", agents=[], ...)`,
then `apply_module_decompose_from_sections`. On `ModuleDecomposeRefused` it
calls `delete_group(task_num, group_name)` and re-raises. Any other failure
keeps the record and propagates. Put it right after the apply function.

### 2. `brainstorm_app.py` — use the runner in `_run_design_op`

- Add `ModuleDecomposePartialFailure` and `run_module_decompose_from_sections`
  to the module-level `brainstorm.brainstorm_session` import list (lines
  ~88-100, which is alphabetical ignoring case). Remove the local
  `apply_module_decompose_from_sections` import inside the branch.
- Replace the `record_operation` + `apply_module_decompose_from_sections` pair
  (lines 5664-5689) with a call to `run_module_decompose_from_sections(self.task_num,
  group_name, head_at_creation=head_at_creation, subgraph=subgraph,
  **operation_extra)`. Then reload the session the way the prune branch does:
  `except ModuleDecomposePartialFailure:` → `_load_existing_session`, then
  `raise`; on success → `_load_existing_session`. A refusal wrote nothing, so
  it does not need a reload. It still ends in the existing `Operation failed:
  …` error notify. Rewrite the branch comment: the old reason ("sections are
  validated per module inside the creation loop") is no longer true.

### 3. Tests

**3a. New `tests/test_brainstorm_from_sections_failure_boundary.py`**, modelled
on `RunPruneFailureBoundaryTests` (`tests/test_brainstorm_prune_dimensions.py:380`).
It seeds a session the same way `test_brainstorm_module_ops_integration.py`
does (`_seed_base` shape + a parser/cache sectioned proposal +
`component_parser`/`component_cache` dims) and patches `bs.crew_worktree`. A
helper `_run(modules, link_to_task=False)` calls
`run_module_decompose_from_sections` with the TUI's extras. A
`_assert_refused_without_trace()` helper snapshots the node and proposal file
lists and the `br_graph_state.yaml` bytes (counter, heads, module_tasks), then
asserts all of them are unchanged and the group is gone from
`br_groups.yaml`.
- `test_success_records_extras_and_completes`: status `Completed`, `agents: []`,
  both roots in `nodes_created`, `modules`/`from_sections` persisted, per-module
  HEADs set, umbrella HEAD unchanged.
- `test_missing_section_is_refused_before_any_write`: modules
  `[parser, missing, absent]`. Raises `ModuleDecomposeRefused` (also a
  `ValueError`), the message names both `'missing'` and `'absent'`, and no
  trace is left. **Pre-fix code fails this test** because it writes the
  `parser` root first.
- `test_invalid_sections_are_refused_and_record_removed`: a section tag that
  references an unknown dimension key.
- `test_no_modules_is_refused_and_record_removed`.
- `test_unanticipated_preflight_failure_is_a_refusal`: patch
  `bs._section_for_module` to raise `RuntimeError` → refusal whose message
  contains `module decompose preflight failed: RuntimeError`, and no trace.
- `test_link_failure_after_first_root_keeps_record_as_error`:
  `link_to_task=True`, and `bs._create_linked_module_task` raises.
  `ModuleDecomposePartialFailure` has `module == "parser"`,
  `stage == "node_recorded"` and `created == [parser root]`. The record
  survives with `status: Error`, its `error` contains `parser`,
  `node_recorded` and the cause, and its `nodes_created` is `[parser root]`.
  The parser HEAD has moved and no cache node exists. **Pre-fix code leaves
  `status: Waiting`.**
- `test_fault_between_node_and_record_keeps_node_in_record`: `bs.set_head`
  raises for module `cache` only. Stage is `node_created` and `created` holds
  both roots. The record's `nodes_created` lists both roots (the cache root
  via the except-path append), and its status is `Error`.
- `test_proposal_write_fault_records_incomplete_node`: this test runs the real
  `create_node`. It patches `Path.write_text` with a wrapper that delegates to
  the real method but raises `OSError("disk full")` only for the `cache`
  root's file under `wt / PROPOSALS_DIR`. The wrapper is installed with
  `patch.object(Path, "write_text", flaky)`, so `write_yaml` and every other
  write go through unchanged. Asserted:
  - the cache root's YAML **is on disk** and its proposal is **not**. This is
    a precondition, and it proves the fault fired after the YAML landed;
  - the exception has `module == "cache"`, `stage == "counter_bumped"`,
    `created == [parser root]` and `incomplete_node_id == cache root`;
  - the record has `status: Error`, `incomplete_node == cache root`, and an
    `error` containing `cache` and `counter_bumped`. Its `nodes_created` is
    exactly `[parser root]`, so the incomplete node is **not** listed as
    created;
  - the cache HEAD is unset and the parser HEAD has moved.

  The `set_head` fault test below fires after `create_node` has returned, so
  it cannot cover this boundary.
- `test_fault_on_completion_write_keeps_record_as_error`: `update_operation`
  raises only for `status="Completed"`. Both roots exist, the record's status
  is `Error`, and the record has no `incomplete_node`.
- The class docstring states the negative control: a runner that deleted the
  record on *every* exception would fail the "record survives" assertions.

**3b. Update `tests/test_brainstorm_from_sections_reload.py`** (the t1995 TUI
test). A missing section no longer writes anything, so the partial-failure
test needs a fault that happens after writing started:
- `_run_from_sections` gains a `link_to_task=False` parameter.
- Retarget `test_partial_failure_shows_roots_created_before_the_error`: modules
  `[parser, cache]`, `link_to_task=True`, `bs_mod._create_linked_module_task`
  patched to raise. The test asserts that the `parser` root is on disk and in
  all three Browse surfaces, that `cache` is absent, that an error notify was
  shown, and that the record's `status` is `Error`. This keeps t1995's
  reload-on-partial-failure coverage.
- New `test_missing_section_is_refused_without_writing`: modules
  `[parser, missing]`. Expects an error notify containing
  `no section found for module 'missing'`, no new nodes, the surfaces still in
  their before state, and no group record left.
- Update the module docstring's partial-failure paragraph to match.

### 4. Doc — `aidocs/brainstorming/module_decomposition_design.md` §4.2

After the "Side effect." bullet, add one bullet, **Failure boundary
(`--from-sections`)**. It says that every module's section, and every other
read and check, is verified before the first write, and that a refusal deletes
the operation's group entry. A failure after writing started keeps the entry
with `status: Error`, the module and stage reached, and the roots created. A
root whose creation stopped part-way is named separately as `incomplete_node`
and never as created. Nothing is rolled back. The wording follows the prune paragraph in
`brainstorm_engine_architecture_v2.md` §7.4a.

## Verification

1. Run the touched and neighbouring suites (use the venv python):
   `tests/test_brainstorm_from_sections_failure_boundary.py`,
   `tests/test_brainstorm_from_sections_reload.py`,
   `tests/test_brainstorm_module_ops_integration.py`,
   `tests/test_brainstorm_apply_module_ops.py`,
   `tests/test_brainstorm_prune_dimensions.py`. All must pass.
2. Mutation checks, each run in an **isolated scratch copy** of
   `.aitask-scripts/` + the test file, never in the shared tree. Each mutant
   must fail the named test:
   - move the missing-section check back into the write loop →
     `test_missing_section_is_refused_before_any_write`;
   - drop the `status: Error` write → `test_link_failure_after_first_root_keeps_record_as_error`;
   - make the runner `delete_group` on every exception → the record-survives tests;
   - drop the except-path `nodes_created` append → `test_fault_between_node_and_record_keeps_node_in_record`;
  - drop the `stage == "counter_bumped"` → `incomplete_node` branch →
    `test_proposal_write_fault_records_incomplete_node`;
  - append the incomplete id to `nodes_created` instead (presenting it as
    complete) → the same test.
3. `bash tests/run_all_python_tests.sh` as a final suite run (verdict from the
   last line; `set -o pipefail` if it is piped).

## Risk

### Code-health risk: low
- The TUI reload narrows from "any exception" to `ModuleDecomposePartialFailure`. A refusal no longer reloads, which is correct because it wrote nothing, and every write-phase exception is wrapped as a partial failure, so every post-write path still reloads. Covered by 3b's two TUI tests · severity: low · → mitigation: none (covered by plan steps 3a/3b)
- The success path moves its per-module computation into the preflight. The output is pinned by the existing success tests (`test_brainstorm_apply_module_ops.py`, `test_brainstorm_module_ops_integration.py`, the t1995 reload success test) · severity: low · → mitigation: none (covered by verification step 1)

- `create_node` writes the node YAML before the proposal, so a fault in between leaves a YAML-only node. The handler names that node as `incomplete_node` and never as created. Covered by 1a/1c and `test_proposal_write_fault_records_incomplete_node`. The reload is safe over such a node, because `_populate_node_list` reads only node YAML · severity: low · → mitigation: none (covered by plan steps 1c/3a)

### Goal-achievement risk: low
- The best-effort `status: Error` write can fail under the same I/O fault that caused the partial failure, which leaves `Waiting`. This is accepted, because `apply_prune_dimensions` has the same limit and no write path is left that could record it · severity: low · → mitigation: none (accepted, parity with prune)

## Out of scope (observed)

`apply_prune_dimensions` has the same `create_node` gap. A fault at its stage
`counter_bumped` can leave a YAML-only child that its record never names,
although `PrunePartialFailure.new_node_id` does carry the id. This task does
not touch prune. The gap is reported at review time as a possible follow-up.

## Step 9 (Post-Implementation)

Current-branch profile: commit the code with `bug: … (t2005)`, then run Step 9
for archival and the commit of the plan and task data.
