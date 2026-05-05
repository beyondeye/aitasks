---
Task: t749_1_persist_operation_groups.md
Parent Task: aitasks/t749_report_operation_that_generated_nod.md
Sibling Tasks: aitasks/t749/t749_2_*.md, aitasks/t749/t749_3_*.md, aitasks/t749/t749_4_*.md, aitasks/t749/t749_5_*.md, aitasks/t749/t749_6_*.md, aitasks/t749/t749_7_*.md
Archived Sibling Plans: aiplans/archived/p749/p749_*_*.md
Worktree: (current branch — no separate worktree)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-05 11:21
---

# Plan: Persist operation groups in br_groups.yaml (t749_1)

## Context

Foundation child of t749. Today `br_groups.yaml` is initialized empty
by `init_session` and never populated when an operation runs — every
read site sees `{groups: {}}`. This child wires up the persistence so
the rest of t749 (badge, dashboard pane, OperationDetailScreen,
keybinding) has something to read from.

Spec-only fields are written. Per the user's plan-review feedback, **no
user-supplied parameters are duplicated** into `br_groups.yaml` — the
reference primitive in t749_2 (`OpDataRef`) handles pinpointing user
inputs in their original on-disk locations.

## Implementation Steps

### Step 1 — Add `record_operation` and `update_operation` helpers

In `.aitask-scripts/brainstorm/brainstorm_session.py`, append after
`save_session`:

```python
def record_operation(
    task_num: int | str,
    group_name: str,
    operation: str,
    agents: list[str],
    head_at_creation: str | None,
) -> None:
    """Write a fresh group entry to br_groups.yaml.

    Idempotent — overwrites any existing entry with the same name.
    """
    wt = crew_worktree(task_num)
    path = str(wt / GROUPS_FILE)
    data = read_yaml(path) or {"groups": {}}
    groups = data.setdefault("groups", {})
    groups[group_name] = {
        "operation": operation,
        "agents": list(agents),
        "status": "Waiting",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "head_at_creation": head_at_creation,
        "nodes_created": [],
    }
    write_yaml(path, data)


def update_operation(task_num: int | str, group_name: str, **fields) -> None:
    """Patch fields on an existing group entry.

    Special-case: pass ``nodes_created="<nid>"`` to APPEND, or
    ``agents_append="<name>"`` to APPEND uniquely. All other kwargs
    overwrite.
    Silently no-ops if the group is missing.
    """
    wt = crew_worktree(task_num)
    path = str(wt / GROUPS_FILE)
    data = read_yaml(path) or {"groups": {}}
    groups = data.setdefault("groups", {})
    grp = groups.get(group_name)
    if grp is None:
        return
    for k, v in fields.items():
        if k == "nodes_created" and isinstance(v, str):
            lst = grp.setdefault("nodes_created", [])
            if v not in lst:
                lst.append(v)
        elif k == "agents_append" and isinstance(v, str):
            lst = grp.setdefault("agents", [])
            if v not in lst:
                lst.append(v)
        else:
            grp[k] = v
    write_yaml(path, data)
```

### Step 2 — Bootstrap group entry in `init_session`

In `init_session`, immediately after `set_head(wt, "n000_init")` (line
151 area), call:

```python
record_operation(
    task_num,
    group_name="bootstrap",
    operation="bootstrap",
    agents=[],
    head_at_creation=None,
)
update_operation(task_num, "bootstrap",
                 nodes_created="n000_init",
                 status="Completed" if abs_proposal_path is None else "Waiting")
```

For the `--proposal-file` path, the initializer will run later and the
status flips to Completed via `apply_initializer_output` (Step 3).

### Step 3 — Update bootstrap on initializer apply

In `apply_initializer_output`, after the proposal file write succeeds,
add:

```python
update_operation(task_num, "bootstrap",
                 agents_append="initializer_bootstrap",
                 status="Completed")
```

### Step 4 — Update patch group on patcher apply

In `apply_patcher_output`, after `set_head(wt, new_node_id)` (line 588
area):

```python
update_operation(
    task_num,
    node_data["created_by_group"],
    nodes_created=new_node_id,
    status="Completed",
)
```

### Step 5 — Wire `_run_design_op` to call `record_operation`

In `.aitask-scripts/brainstorm/brainstorm_app.py`, modify
`_run_design_op` (around line 3814):

- Capture `current_head = get_head(self.session_path)` BEFORE calling
  `register_*`.
- After the per-op branch sets `agents` (or `agent`), normalize to a
  list `agents_list` of agent names.
- Inside the success path (before `self.call_from_thread(self.notify,
  msg)`):

```python
from brainstorm.brainstorm_session import record_operation
record_operation(
    self.task_num,
    group_name=group_name,
    operation=op,
    agents=agents_list,
    head_at_creation=current_head,
)
```

For the `compare` and `hybridize` operations there is no node creation
phase — they produce a single completed comparator/synthesizer agent.
Do NOT call `update_operation` for them in this child; the screen
displays status from the agents' `_status.yaml` files via the existing
`_mount_agent_row` helper.

### Step 6 — Test

Add `tests/test_brainstorm_groups_persist.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
# Setup tmp crew via init_session, record_operation, update_operation;
# assert YAML round-trip is correct via yq / python.
```

(See task description for the full assertion list.)

## Files Modified

- `.aitask-scripts/brainstorm/brainstorm_session.py` — `+~70 lines`
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `+~10 lines` in
  `_run_design_op`
- `tests/test_brainstorm_groups_persist.sh` — NEW

## Verification

1. `bash tests/test_brainstorm_groups_persist.sh` passes.
2. Manually run an explore op in a fresh session; confirm
   `br_groups.yaml` has the entry.
3. Restart the TUI, open the Status tab; confirm "Operation Groups"
   section now lists the group (was previously always empty).

## Step 9 (Post-Implementation)

Standard archival flow. After this child archives, t749_2
(op_data_ref_module) becomes pickable.

## Final Implementation Notes

- **Actual work done:** Implemented `record_operation` and
  `update_operation` in `brainstorm_session.py` exactly as planned.
  Wired call sites in `init_session` (records bootstrap entry,
  Completed for blank-init / Waiting for proposal-file path),
  `apply_initializer_output` (appends initializer agent + flips to
  Completed), `apply_patcher_output` (appends new node id +
  Completed). Also extended `_run_design_op` in `brainstorm_app.py`
  to call `record_operation` for ALL operation types (originally
  scoped only to explore via the per-branch `agents` local; refactored
  to a shared `agents_list` collected outside the per-op branch).
- **Deviations from plan:** (1) Added a small private helper
  `_read_groups_file` to handle the case where `br_groups.yaml` is
  missing (unlike `read_yaml`, which raises `FileNotFoundError`). The
  plan didn't anticipate this since `init_session` always writes the
  file first in real usage — but a unit test that omitted the seed
  surfaced it. Helper is a one-line guard; safer than scattering
  `os.path.isfile` checks at each call site.
  (2) Test file is `.py` not `.sh` as initially named in the plan;
  Python integrates with the existing Textual / unittest fixture
  patterns used by sibling tests.
- **Issues encountered:** None beyond the missing-file guard above.
- **Key decisions:**
  - `agents_append` is a pseudo-kwarg to the variadic
    `update_operation`. Cleaner than a separate function, since it
    behaves like the `nodes_created` append-unique semantics already
    in the same call.
  - Compare/hybridize/detail/patch operations now also write a group
    entry (was only explore in implicit pre-existing usage). They have
    no node-creation step, so `nodes_created` stays empty and the
    Operation Detail screen surfaces just the agent's input/output/log
    via the OpDataRef refs in t749_2/t749_5.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - `_read_groups_file` is the canonical "read br_groups.yaml or empty
    skeleton" helper. Sibling t749_3/t749_4/t749_5 should reuse it
    rather than re-implementing the missing-file guard.
  - `agents` for compare/hybridize/detail/patch ops is a single-element
    list. The `OpDataRef` helpers in t749_2 use `agents[0]` for the
    canonical user-input ref — works correctly for these single-agent
    ops too.
  - The `_run_design_op` refactor lifted `agents` to `agents_list`
    OUTSIDE the per-op branch. Sibling code touching `_run_design_op`
    must use `agents_list` (not the per-branch local `agents`).

## Verification

(Aggregated under the parent task's manual-verification sibling.)

## Post-Review Changes

### Change Request 1 (2026-05-05 11:42)

- **Requested by user:** "do we have enough unit tests?" — implicit ask
  to broaden coverage beyond the helpers themselves to the integration
  call sites.
- **Changes made:** Added 4 integration tests to
  `tests/test_brainstorm_groups_persist.py`:
  1. `init_session` blank-init records bootstrap with `status=Completed`.
  2. `init_session` proposal-file path records bootstrap with
     `status=Waiting`.
  3. `apply_initializer_output` appends `initializer_bootstrap` to the
     bootstrap entry's `agents` and flips `status` to `Completed`.
  4. `apply_patcher_output` appends the new node id to the patch
     group's `nodes_created` and flips `status` to `Completed`.
  Also added `test_head_at_creation_none_roundtrips` to verify
  `None` survives the YAML round-trip (relevant for the bootstrap
  entry which always has `head_at_creation=None`).
- **Files affected:** `tests/test_brainstorm_groups_persist.py`.
  Total tests: 7 → 12, all passing.
