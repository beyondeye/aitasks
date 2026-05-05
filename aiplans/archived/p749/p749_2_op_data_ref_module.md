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

## Final Implementation Notes

- **Actual work done:** Created
  `.aitask-scripts/brainstorm/brainstorm_op_refs.py` exactly as planned —
  `OpDataRef` frozen dataclass with closed-set `kind` validation,
  `file_for_ref` path resolver, `resolve_ref` reader,
  `_extract_md_section` helper, and the four `list_op_*(group_info)`
  enumerators (`list_op_inputs`, `list_op_outputs`, `list_op_logs`,
  `list_op_definition`). Imported `NODES_DIR`, `PROPOSALS_DIR`,
  `PLANS_DIR` from `brainstorm_dag`. Re-exported the public surface from
  `.aitask-scripts/brainstorm/__init__.py` via `__all__`. Added
  `tests/test_brainstorm_op_refs.py` (33 tests across 8 classes).
- **Deviations from plan:** None of substance. The
  `_extract_md_section` body trims the heading line via `ln[3:].strip()`
  (cleaner than the `lstrip("#").strip()` shown in the task description) —
  semantically equivalent for the only call shape (`## Header`).
- **Issues encountered:** One test expectation was off-by-one-blank-line
  (`.strip("\n")` strips leading/trailing newlines from the joined slice,
  which the test forgot). Fixed the expectation, not the implementation.
- **Key decisions:**
  - Re-exports done via `__all__` in `__init__.py` — keeps the public
    surface explicit and lets `from brainstorm import *` work as
    documented.
  - `list_op_definition` filters out a falsy `head_at_creation` rather
    than emitting a `node_metadata` ref to an empty target — matches
    t749_1's bootstrap entry shape (`head_at_creation=None`).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **Module path:** `from brainstorm.brainstorm_op_refs import OpDataRef,
    list_op_inputs, ...` — the symbols are also re-exported from
    `brainstorm` for short imports.
  - **Empty-agents convention:** `list_op_inputs(group_info)` returns
    `[]` when `agents` is missing or empty. Sibling t749_4/t749_5 should
    treat the empty list as "no input recorded yet, agent registration
    pending" rather than "no input section for this op".
  - **Section anchor map:** `_OP_INPUT_SECTION` is the single source of
    truth for the `## Header` anchor inside each agent's `_input.md`.
    Adding a new operation type means updating this dict in
    `brainstorm_op_refs.py`. The anchors mirror what `brainstorm_crew.py`
    writes (verified at lines 208/277/304/404/453).
  - **`_extract_md_section`:** Intentionally minimal — matches `## Header`
    by literal string, runs to the next `## ` line or EOF. Do not extend
    it for `###`/`#` matching; if a future op needs nested-heading
    extraction, add a separate helper.
  - **Test pattern:** `tests/test_brainstorm_op_refs.py` uses `unittest`
    with `sys.path.insert(0, .aitask-scripts)` (matching
    `tests/test_brainstorm_groups_persist.py`). No pytest dependency.
    Run via `python -m unittest tests.test_brainstorm_op_refs -v`.
