---
Task: t2019_record_prune_incomplete_child_on_create_node_fault.md
Base branch: main
Output branch: main
---

# t2019 — prune: name the incomplete child when `create_node` faults part-way

## Context

`brainstorm_dag.create_node` (`.aitask-scripts/brainstorm/brainstorm_dag.py:102-105`)
is not atomic. It writes the node YAML first and the proposal second, so a fault
on the proposal write leaves a node YAML with no proposal. `_populate_node_list`
reads only node YAML, so Browse shows that node after a reload.

`apply_prune_dimensions` (`.aitask-scripts/brainstorm/brainstorm_session.py:1728-1801`)
sets `stage = "counter_bumped"` before `create_node` and changes it only after
`create_node` returns. Its except handler (`:1788-1801`) adds `nodes_created` for
`node_created` / `head_moved` only. So a fault inside `create_node` produces a
`status: Error` record whose `error` reads `counter_bumped: …`, and nothing in
the record names the child id that may be partly on disk. There is a second
gap: the exception message (`PrunePartialFailure.__init__`, `:1594-1621`), which
the TUI shows as `Operation failed: …` (`brainstorm_app.py:5772`), reads
`created n002_…` for a node whose creation actually failed.

t2005 (commit `7d077e308`) fixed the same gap in the from-sections Module
Decompose (`brainstorm_session.py:1528-1543`). A failure at `counter_bumped` can
only come from inside `create_node`, the one call between the bump and the next
stage. The handler therefore records the attempted id in a separate
`incomplete_node` field and never in `nodes_created`, and the exception carries
`incomplete_node_id` and says `incomplete node <id>`. This task applies the same
fix to prune.

## Implementation

### 1. `.aitask-scripts/brainstorm/brainstorm_session.py`

**1a. `PrunePartialFailure`.** Add a keyword-only `incomplete_node_id: str | None = None`
after `cause`. The only construction site is `apply_prune_dimensions`, and
existing positional callers keep working. Store it as `self.incomplete_node_id`.
The message names the node according to what actually happened:

```python
if incomplete_node_id:
    node = f"; incomplete node {incomplete_node_id}"
elif new_node_id:
    node = f"; created {new_node_id}"
else:
    node = ""
super().__init__(
    f"prune partially applied (stage: {stage}{node}); operation "
    f"record {group_name} kept: {type(cause).__name__}: {cause}"
)
```

Keep `new_node_id` exactly as it is now: the minted child id, or `None` if the
counter write failed. Existing readers and tests depend on it. Update the class
docstring so that it:
- says `incomplete_node_id` is the child whose `create_node` raised part-way,
  which may have partial artifacts on disk, and is `None` otherwise;
- notes that `new_node_id` stays set in that case.

**1b. The `apply_prune_dimensions` except handler** mirrors t2005:

```python
except Exception as exc:
    record: dict = {"status": "Error", "error": f"{stage}: {exc}"}
    incomplete: str | None = None
    if stage == "counter_bumped":
        # create_node raised part-way: it writes the node YAML before the
        # proposal, so the attempted child may be partly on disk. Name it,
        # but never as a created node.
        incomplete = new_node_id
        record["incomplete_node"] = incomplete
    elif stage in ("node_created", "head_moved"):
        record["nodes_created"] = new_node_id
    try:
        update_operation(task_num, group_name, **record)
    except Exception:
        pass
    raise PrunePartialFailure(
        group_name,
        new_node_id if stage != "none" else None,
        stage,
        exc,
        incomplete_node_id=incomplete,
    ) from exc
```

The success path does not change. In the "Failure boundary" paragraph of the
docstring, add that a child whose creation stopped part-way is named as
`incomplete_node` on the record, and never as created.

### 2. `tests/test_brainstorm_prune_dimensions.py`: `RunPruneFailureBoundaryTests`

**2a. New `test_proposal_write_fault_records_incomplete_node`.** It runs the
real `create_node`, modelled on the t2005 test of the same name
(`tests/test_brainstorm_from_sections_failure_boundary.py:258`). It patches
`Path.write_text` with `patch.object(Path, "write_text", flaky)`. The patched
method raises `OSError("disk full")` only for
`self.wt / PROPOSALS_DIR / "n002_prune_dimensions_001.md"` and passes every
other write through to the real method. Assertions:
- **Precondition** (proves the fault fired after the YAML landed): the child's
  YAML is on disk and its proposal is not.
- The exception has `stage == "counter_bumped"`,
  `new_node_id == incomplete_node_id == "n002_prune_dimensions_001"`, and
  `"incomplete node n002_prune_dimensions_001"` in `str(exc)`. It does **not**
  have `"created n002"` in `str(exc)`.
- The record has `status: Error`, `incomplete_node == "n002_prune_dimensions_001"`,
  and an `error` that contains `counter_bumped`. Its `nodes_created` is `[]`,
  so the child is named but never listed as created.
- HEAD is still `SOURCE`, and `_assert_source_untouched()` holds.

**2b. Negative pins on the two existing fault tests**
(`test_fault_after_child_creation_keeps_record`,
`test_fault_after_head_move_keeps_record`): add
`assertIsNone(exc.incomplete_node_id)` and
`assertNotIn("incomplete_node", grp)`. Without them, a handler that set
`incomplete_node` at every stage would still pass.

### 3. `aidocs/brainstorming/brainstorm_engine_architecture_v2.md` §7.4a

Extend the "Failure boundary" paragraph (line 1060) the same way t2005 worded
`module_decomposition_design.md` §4.2. A failure after writing started keeps the
group entry with `status: Error`, the stage reached, and the created node. A
child whose creation stopped part-way (its node file written but not its
proposal) is named separately as `incomplete_node`, never as created. Nothing
is rolled back.

## Verification

1. Run the touched and neighbouring suites with the venv python. All must pass:
   - `tests/test_brainstorm_prune_dimensions.py`
   - `tests/test_brainstorm_from_sections_failure_boundary.py`
   - `tests/test_brainstorm_from_sections_reload.py`
2. Mutation checks. Each runs in an **isolated scratch copy** of `.aitask-scripts/`
   plus the test file, never in the shared tree. **Anchor every mutant inside
   `apply_prune_dimensions`'s handler.** After this change its
   `if stage == "counter_bumped":` / `elif stage in (…)` lines are identical to
   decompose's, so a bare-text anchor matches both. Use the prune-only line
   `"error": f"{stage}: {exc}"` or a line range. Each mutant must fail the
   named test:
   - drop the `counter_bumped` → `incomplete_node` branch:
     `test_proposal_write_fault_records_incomplete_node`;
   - record the incomplete id in `nodes_created` instead: the same test;
   - set `incomplete_node` at every stage: the 2b-pinned fault tests;
   - revert the message to always say `created …`: the same new test.
3. Run `bash tests/run_all_python_tests.sh` as the final suite. Read the verdict
   from the last line, and use `set -o pipefail` if the output is piped.

## Risk

### Code-health risk: low
- `PrunePartialFailure` gains a keyword-only parameter and a new message branch. Only `apply_prune_dimensions` constructs it, and its one reader, the TUI's `except PrunePartialFailure` reload plus the generic `Operation failed: {e}` notify, keys on the type and shows the string, so nothing parses the old `created` wording · severity: low · → mitigation: none (covered by plan steps 1a/2a)
- After this change, the prune and decompose handlers repeat the same `counter_bumped` classification. That is deliberate parity with t2005, not shared code, so a later edit to one could miss the other. Each is pinned by its own `incomplete_node` test · severity: low · → mitigation: none (covered by plan steps 2a/2b)

### Goal-achievement risk: low
- The best-effort `status: Error` write can fail under the same I/O fault that interrupted `create_node`, which leaves the record `Waiting` without `incomplete_node`. This limit is accepted and shared with t2005. The exception, and therefore the TUI notify, still names the incomplete node · severity: low · → mitigation: none (accepted, parity with t2005)

## Step 9 (Post-Implementation)

This is a current-branch profile. Commit the code with
`bug: Name a prune child whose creation stopped part-way as incomplete_node (t2019)`,
then run Step 9 to archive the task and commit the plan and task data.

## Final Implementation Notes
- **Actual work done:** Implemented as planned. `PrunePartialFailure` gained a keyword-only `incomplete_node_id`. Its message now reads `incomplete node <id>` for a child whose `create_node` raised part-way, and `created <id>` only for a child that was actually created. `apply_prune_dimensions`'s except handler records the attempted id as `incomplete_node` at stage `counter_bumped` and never adds it to `nodes_created`. The success path is unchanged. `RunPruneFailureBoundaryTests` gained `test_proposal_write_fault_records_incomplete_node`, which runs the real `create_node` and fails only the child's proposal write. The two existing fault tests now assert that `incomplete_node_id` / `incomplete_node` are absent. In `brainstorm_engine_architecture_v2.md`, the §7.4a failure-boundary paragraph now names `incomplete_node`.
- **Deviations from plan:** None.
- **Issues encountered:**
  - The scratch copy used for the mutation runs has no `aitasks/metadata/codeagent_config.json`. Without it, the four `PruneWizardTests` fail on setup, so the mutants were scoped with `-k RunPruneFailureBoundaryTests`, whose baseline in the copy was 8/8 green.
  - The full Python suite reported `PYTHON SUITE: FAILED` with 2 failures, both outside brainstorm:
    - `test_textual_markup_colours` flags `tests/test_monitor_markup_escape.py:69`, a file t2006 committed in `337d0f6e0`. This failure is already on `main`.
    - `test_shortcuts_mixin_live_remap::test_override_onto_bound_key_leaves_class_and_later_instances_alone` runs against another session's uncommitted edits to `.aitask-scripts/lib/shortcuts_mixin.py` and its test.
- **Key decisions:**
  - `incomplete_node_id` is keyword-only with a `None` default, so the existing positional signature is unchanged. `new_node_id` still carries the minted id at `counter_bumped`, so existing readers keep it.
  - The `counter_bumped` classification is mirrored from t2005 rather than shared with the decompose handler. The error strings differ, because decompose prefixes the module, and each handler has its own `incomplete_node` test.
- **Verification:**
  - `test_brainstorm_prune_dimensions.py`, `test_brainstorm_from_sections_failure_boundary.py` and `test_brainstorm_from_sections_reload.py` pass, 48 tests in total.
  - Four mutants ran in an isolated scratch copy, each anchored inside the prune function or class. Each was caught by its intended test:
    - dropping the `incomplete_node` branch was caught by the new test;
    - recording the id in `nodes_created` was caught by the new test;
    - setting `incomplete_node` at every stage was caught by both pinned fault tests, on `assertNotIn("incomplete_node", grp)`;
    - reverting the message to `created` was caught by the new test.
  - The pre-fix control (the HEAD module) fails the new test and the two pinned tests.
- **Upstream defects identified:** None
