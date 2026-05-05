---
Task: t749_2_op_data_ref_module.md
Parent Task: aitasks/t749_report_operation_that_generated_nod.md
Sibling Tasks: aitasks/t749/t749_1_*.md, aitasks/t749/t749_3_*.md, aitasks/t749/t749_4_*.md, aitasks/t749/t749_5_*.md, aitasks/t749/t749_6_*.md, aitasks/t749/t749_7_*.md
Archived Sibling Plans: aiplans/archived/p749/p749_*_*.md
Worktree: (current branch — no separate worktree)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-05 12:03
---

# Plan: OpDataRef module — pinpoint operation data on disk (t749_2)

## Context

Pure data-layer child. Defines the `OpDataRef` reference primitive
that lets the dashboard pane (t749_4) and Operation Detail screen
(t749_5) point at user inputs / agent outputs / agent logs in their
canonical on-disk locations rather than duplicating values into
`br_groups.yaml`.

This is the user-asked-for "reference format". Not a substitution
engine — just a typed pointer + a resolver.

## Implementation Steps

### Step 1 — New file `brainstorm_op_refs.py`

Full content laid out in the task description (under "Implementation
Plan" step 1). Key points:

- `OpDataRef(kind, target, section)` — frozen dataclass.
- `_VALID_KINDS` enforces a closed set of kinds.
- `file_for_ref(session_path, ref) -> Path` — pure path resolver.
- `resolve_ref(session_path, ref) -> str` — reads file, optionally
  extracts a `## Section` slice via `_extract_md_section`.
- `list_op_inputs(group_info)` — returns one `agent_input` ref using
  the **first** agent's input.md and the operation-specific section
  anchor from `_OP_INPUT_SECTION`.
- `list_op_outputs(group_info)` and `list_op_logs(group_info)` —
  one ref per agent.
- `list_op_definition(group_info)` — refs to `head_at_creation` and
  `nodes_created` nodes (kind `node_metadata`).

### Step 2 — Re-exports

`.aitask-scripts/brainstorm/__init__.py`: append the public symbols.
Confirm there is no circular import (the new module imports
`NODES_DIR` / `PROPOSALS_DIR` / `PLANS_DIR` from `brainstorm_dag`,
which has no upward deps).

### Step 3 — Tests

Add `tests/test_brainstorm_op_refs.py`. Cover:

- `OpDataRef("agent_input", "x")` accepts; `OpDataRef("nope", "x")`
  raises `ValueError`.
- Path resolution for each kind.
- `_extract_md_section` extracts `## Foo` content correctly, returns
  empty for missing headers, stops at the next `## ` line.
- `list_op_inputs` for each operation type returns the right
  section anchor (or None for `detail`).
- `list_op_outputs`/`list_op_logs` enumerate per agent.
- `list_op_definition` skips empty `head_at_creation` / empty
  `nodes_created`.

Use a tmp directory + `Path` writes for fixture sessions. No Textual
import needed.

## Files Modified

- `.aitask-scripts/brainstorm/brainstorm_op_refs.py` — NEW (~80 LOC)
- `.aitask-scripts/brainstorm/__init__.py` — re-exports (~6 lines)
- `tests/test_brainstorm_op_refs.py` — NEW

## Verification

```bash
python -m pytest tests/test_brainstorm_op_refs.py -v
```

All cases pass. No Textual import side-effects.

## Step 9 (Post-Implementation)

Standard archival flow.

## Verification

(Aggregated under the parent task's manual-verification sibling.)
