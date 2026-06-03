---
Task: t922_module_status_compute_contract_tests.md
Base branch: main
plan_verified: []
---

# Plan: t922 — Module-status compute contract tests

## Context

t756_5 shipped the per-module fluid-status feature (`brainstorm_status.py`)
plus `tests/test_brainstorm_module_status.py` (10 unit tests covering the six
§4.7 states, the deferred overlay, archived `implemented` resolution, and the
`module_deferred` round-trip). Its risk evaluation flagged the `merged`
(cross-subgraph parents walk) and `implemented` (live-vs-archived task-file
resolution) computations — both new cross-reference logic — as the states most
likely to be subtly wrong: a mis-scoped walk or a missed archived-path case
yields a silently-wrong badge. This task is the risk-mitigation **"after"**
follow-up that hardens that surface beyond the in-task unit tests, plus a
regression guard on the `_node_module` → dashboard render wiring.

Scope is test-only. No production code changes.

## Approach

Add a **new** test file `tests/test_brainstorm_module_status_contract.py`
(separate from the in-task `test_brainstorm_module_status.py`, paralleling the
sibling precedent `tests/test_brainstorm_module_sync_apply_contract.py`). It
reuses that file's seed/`_node`/`_write_task`/chdir helpers — copied locally,
not imported, matching how the sibling contract file stands alone. Auto-picked
up by `tests/run_all_python_tests.sh` (unittest/pytest `test_*.py` discovery).

**Do not duplicate the 10 existing tests.** Only the edge/combinatoric cases
the in-task suite omits.

### Test classes & cases

**1. `MergedPrecisionTests`** — hardens `is_module_merged` (the cross-subgraph
parents walk):
- `test_same_subgraph_child_referencing_head_not_merged` — pin a module's HEAD
  to an *older* node (`set_head(... module="auth")` on `n001_auth`) while a
  same-module child `n002_auth` lists `n001_auth` in its parents. The head
  appears in a parents list, but the referencing node is in the *same*
  subgraph → must be skipped → `is_module_merged` False. (Guards the
  `_node_module(...) == module: continue` line precisely; existing test 7 only
  covers the no-referencing-node case.)
- `test_merged_across_more_than_two_subgraphs` — three subgraphs (umbrella +
  `auth` + `db`); `auth`'s HEAD is listed as a parent by a node in a *third*
  subgraph (`db`), not the umbrella. Confirm `is_module_merged("auth")` True
  and `compute_module_status("auth") == STATUS_MERGED`.

**2. `LinkedTaskResolutionEdgeTests`** — hardens the `implemented`/in_design
resolution against missing & malformed task files (all use `os.chdir` into the
temp dir because `_resolve_task_state` resolves `aitasks/` relative to cwd):
- `test_missing_linked_task_file_is_in_design` — subgraph with >1 node,
  `module_tasks={"auth": "905"}`, but no `t905_*.md` on disk →
  `_resolve_task_state` returns `(None, False)` → `in_design` (not crash, not
  implemented).
- `test_malformed_frontmatter_no_status_is_in_design` — task file whose
  frontmatter has no `status:` key → `_read_frontmatter_status` returns None →
  `in_design`.
- `test_unparseable_yaml_frontmatter_is_in_design` — task file with a
  frontmatter that matches the `---\n...\n---` fence but is invalid YAML (e.g.
  an unterminated quote `status: "Ready`) → `yaml.YAMLError` caught → None →
  `in_design`.

**3. `ResolveTaskStateUnitTests`** — direct unit coverage of
`_resolve_task_state(task_id)` for parent vs child id (the function the §4.7
`implemented` signal hinges on):
- `test_parent_id_resolves_top_level` — `905` → `aitasks/t905_*.md`,
  returns `("Ready", False)`.
- `test_child_id_resolves_parent_subdir` — `905_2` →
  `aitasks/t905/t905_2_*.md`, returns `("Implementing", False)`.
- `test_archived_only_hit_reports_archived` — file only under
  `aitasks/archived/...` → `(status, True)` (the `implemented` signal).
- `test_live_preferred_over_archived` — same id present both live and archived;
  live status wins and `is_archived` is False.
- `test_missing_returns_none_false` — `(None, False)`.

**4. `DeferredOverlayCombinatoricTests`** — the deferred×base combinations the
in-task suite omits (it only pairs deferred with `in_design`):
- `test_deferred_and_merged_simultaneously` — a merged module that is also
  marked `module_deferred=True`: `compute_module_status` still returns
  `STATUS_MERGED` (base unchanged) and the corresponding `module_status_rows`
  row has `status == merged` AND `deferred == True` (orthogonality holds at the
  terminal base state, not just `in_design`).

**5. `MultiModuleStatusTests`** — two subgraphs with divergent statuses in one
session:
- `test_two_subgraphs_distinct_statuses` — `auth` driven to
  `in_implementation` (linked task Implementing) and `db` left at `unstarted`
  (root only); assert `compute_module_status` per module and that
  `module_status_rows` carries both rows with the right per-row status and
  node_count.

**6. `ModuleStatusRenderGuardTests`** — render-layer regression guard via a
Textual pilot (`async with app.run_test()`), following the
`tests/test_brainstorm_dimension_row_expand.py` `_HostApp` pattern. A minimal
host `App` composes a `Label(id="module_status_info")`, sets `session_path`,
and invokes `BrainstormApp._update_module_status(self)` (unbound — the method
only touches `self.query_one` + `self.session_path`). This exercises the real
render path including `module_status_rows` → `_node_module`, which a direct
call on a `__new__`-constructed app would *not* (its `query_one` raises and the
method early-returns before `module_status_rows` runs).
- `test_umbrella_only_session_renders_placeholder` — seed umbrella-only; assert
  no exception and the label shows the `— no modules —` placeholder.
- `test_multi_module_session_renders_rows` — seed umbrella + 2 module
  subgraphs; assert no exception and the rendered label text contains a status
  badge line per module (e.g. each module name appears).

### Helpers (copied into the new file, mirroring the sibling precedent)
- `_seed_state(wt, **maps)` — write `br_graph_state.yaml` + `NODES_DIR`/
  `PROPOSALS_DIR` (from `test_brainstorm_module_status.py`).
- `_node(wt, node_id, parents, module=None)` — `create_node` wrapper.
- `_write_task(root, task_id, status, archived=False)` — minimal live/archived
  task file; plus a small inline variant for the malformed-frontmatter cases.
- Pilot host app local to class 6.

## Critical files
- **New:** `tests/test_brainstorm_module_status_contract.py`
- **Read-only references:**
  `.aitask-scripts/brainstorm/brainstorm_status.py` (under test),
  `tests/test_brainstorm_module_status.py` (seed/chdir patterns, no overlap),
  `tests/test_brainstorm_module_sync_apply_contract.py` (sibling precedent),
  `tests/test_brainstorm_dimension_row_expand.py` (pilot `_HostApp` pattern),
  `.aitask-scripts/brainstorm/brainstorm_app.py:5381` (`_update_module_status`),
  `.aitask-scripts/brainstorm/brainstorm_dag.py` (`set_head`, `get_parents`,
  `list_subgraphs`, `_node_module`).

## Verification
```bash
# New file in isolation
python3 -m unittest tests.test_brainstorm_module_status_contract -v
# Regression: in-task suite still green (no overlap/interference)
python3 -m unittest tests.test_brainstorm_module_status -v
# Full python suite discovery picks up the new file
bash tests/run_all_python_tests.sh
```
Expected: all new tests pass; the original 10 still pass. See **Step 9** for
post-implementation cleanup, archival, and merge.

## Risk

### Code-health risk: low
- New standalone test file, zero production-code change; helpers copied from the
  established sibling pattern. Blast radius is one new `test_*.py`. · severity: low · → mitigation: none
- Textual pilot test can be environment-sensitive, but the `_HostApp` pilot
  pattern is already used by `test_brainstorm_dimension_row_expand.py`. · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The task's value is *coverage completeness* of the silently-wrong `merged` /
  `implemented` paths; a mis-chosen edge case could pass without exercising the
  intended branch (e.g. a render guard that early-returns instead of running
  `module_status_rows`). Mitigated in-plan by the pilot approach and by
  asserting the precise branch each test targets. · severity: medium · → mitigation: none

## Final Implementation Notes

- **Actual work done:** Added `tests/test_brainstorm_module_status_contract.py`
  with 14 tests in 6 classes exactly as planned: `MergedPrecisionTests` (2),
  `LinkedTaskResolutionEdgeTests` (3), `ResolveTaskStateUnitTests` (5),
  `DeferredOverlayCombinatoricTests` (1), `MultiModuleStatusTests` (1),
  `ModuleStatusRenderGuardTests` (2, Textual pilot). No production code changed.
- **Deviations from plan:** None in scope. One implementation detail: the
  render-guard tests originally read the rendered Label via `label.renderable`,
  which does not exist in the installed Textual version (`Static.update` stores
  content in the name-mangled `_Static__content`). Switched to the public,
  stable `label.render()` (returns the markup-resolved text) — `"no modules"`
  for the umbrella-only placeholder, the module names for the populated case.
- **Issues encountered:** Only the `renderable` attribute mismatch above;
  resolved by probing the live widget API before settling on `render()`.
- **Key decisions:** Standalone test file (copied seed helpers, not imported),
  mirroring the sibling precedent `test_brainstorm_module_sync_apply_contract.py`
  — keeps the in-task suite untouched and avoids cross-file coupling. The
  render guard uses a real Textual pilot rather than a `__new__`-app direct
  call: the latter would early-return at `query_one` and never reach
  `module_status_rows`, defeating the `_node_module`-wiring guard.
- **Upstream defects identified:** None.

