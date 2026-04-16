---
priority: high
effort: medium
depends: [1]
issue_type: refactor
status: Ready
labels: [brainstorming, ait_brainstorm]
created_at: 2026-04-16 11:45
updated_at: 2026-04-16 11:45
---

## Context

This is child task 3 of t571 (Structured Brainstorming Sections). It adds optional `target_sections` parameters to brainstorm operation registration so agents can focus on specific sections of proposals/plans. This is the backend infrastructure that enables section-targeted operations.

Currently, all brainstorm operations (explore, detail, patch, compare) work on entire proposals/plans. This task adds the ability to scope operations to specific named sections, which are parsed using the parser from t571_1.

**Depends on**: t571_1 (section parser module)

## Key Files to Modify

- **MODIFY**: `.aitask-scripts/brainstorm/brainstorm_crew.py` — All `_assemble_input_*` and `register_*` functions
- **MODIFY**: `.aitask-scripts/brainstorm/templates/patcher.md` — Section-aware instruction
- **MODIFY**: `.aitask-scripts/brainstorm/templates/explorer.md` — Section-aware instruction
- **MODIFY**: `.aitask-scripts/brainstorm/templates/comparator.md` — Section-aware instruction
- **MODIFY**: `.aitask-scripts/brainstorm/templates/detailer.md` — Section-aware instruction

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_sections.py` (created by t571_1) — `parse_sections()`, `get_section_by_name()`, `ContentSection`, `ParsedContent`
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — Current register/assemble functions:
  - `_assemble_input_explorer()` (line 179)
  - `_assemble_input_comparator()` (line 222)
  - `_assemble_input_detailer()` (line 283)
  - `_assemble_input_patcher()` (line 313)
  - `register_explorer()` (line 349)
  - `register_comparator()` (line 393)
  - `register_detailer()` (line 469)
  - `register_patcher()` (line 506)
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `read_plan()`, `read_proposal()` for reading content

## Implementation Plan

### 1. Update `_assemble_input_*` Functions

Each function gets a new `target_sections: list[str] | None = None` parameter.

**`_assemble_input_explorer(session_path, node_id, mandate, target_sections=None)`:**
When `target_sections` is provided:
- Read baseline proposal via `read_proposal(session_path, node_id)`
- Parse with `parse_sections(proposal_text)`
- For each name in `target_sections`, extract the section content via `get_section_by_name()`
- Add to input under "## Targeted Section Content":
  ```
  ## Targeted Section Content
  The following sections from the baseline are the focus of this exploration:

  ### Section: <name> [dimensions: dim1, dim2]
  <section content>

  ### Section: <name2>
  <section content>
  ```
- Also read baseline plan (if exists) and extract matching sections
- When no target_sections: behavior unchanged (full proposal/plan path references)

**`_assemble_input_patcher(session_path, node_id, tweak_request, target_sections=None)`:**
When `target_sections` is provided:
- Add advisory block:
  ```
  ## Target Sections
  Focus the patch on these sections only. Leave all other sections unchanged:
  - <name1>
  - <name2>
  ```
- The patcher still gets the full plan path (it writes back a complete plan)

**`_assemble_input_comparator(session_path, node_ids, dimensions, target_sections=None)`:**
When `target_sections` is provided:
- Add:
  ```
  ## Section Focus
  When comparing nodes, focus on content within these sections:
  - <name1>
  - <name2>
  ```

**`_assemble_input_detailer(session_path, node_id, codebase_paths, target_sections=None)`:**
When `target_sections` is provided:
- Add:
  ```
  ## Target Sections
  Re-detail only these sections of the existing plan. Leave other sections unchanged:
  - <name1>
  - <name2>
  ```
- Also include current plan path so agent can read existing sections

### 2. Update `register_*` Functions

Each `register_*()` function gets `target_sections: list[str] | None = None`:

```python
def register_explorer(session_dir, crew_id, node_id, mandate, group_name,
                      launch_mode=DEFAULT_LAUNCH_MODE, target_sections=None):
    input_content = _assemble_input_explorer(session_dir, node_id, mandate,
                                              target_sections=target_sections)
    ...
```

Same pattern for `register_comparator()`, `register_detailer()`, `register_patcher()`.

### 3. Update Templates (Minor Additions)

Add a conditional instruction to each template. This is a small paragraph, not a rewrite.

**`patcher.md`** — Add after Rules section:
```
## Section-Targeted Patching (Optional)
If a "Target Sections" block is present in your input, apply the patch ONLY
to the listed sections. Leave all other sections of the plan unchanged. If the
patch request conflicts with the section scope, note the conflict in your
output.
```

**`explorer.md`** — Add after Rules section:
```
## Section-Targeted Exploration (Optional)
If "Targeted Section Content" is present in your input, focus your
architectural exploration on the aspects covered by those sections. Your
output proposal should still be complete, but the exploration mandate
applies primarily to the targeted areas.
```

**`comparator.md`** — Add after Rules section:
```
## Section-Focused Comparison (Optional)
If a "Section Focus" block is present in your input, compare the listed
sections across nodes. Read proposal content for those sections specifically.
Your comparison matrix should still cover the requested dimensions.
```

**`detailer.md`** — Add after Rules section:
```
## Section-Targeted Re-Detailing (Optional)
If "Target Sections" are specified in your input, re-detail only those
sections of the existing plan. Read the current plan file, keep all
non-targeted sections unchanged, and rewrite only the targeted sections.
```

### 4. Import

At the top of `brainstorm_crew.py`, add:
```python
from .brainstorm_sections import parse_sections, get_section_by_name
```

## Verification Steps

1. Call `register_explorer()` with `target_sections=["overview", "components"]` — verify assembled input contains "Targeted Section Content" with those sections inlined
2. Call `register_patcher()` with `target_sections=["step_database"]` — verify input has "Target Sections" advisory block
3. Call `register_comparator()` with `target_sections=["assumptions"]` — verify input has "Section Focus" block
4. Call `register_detailer()` with `target_sections=["prerequisites"]` — verify input has "Target Sections" block
5. Call any register function WITHOUT `target_sections` — verify behavior is identical to before (backward compat)
6. Test with content that has no sections — should fall back to full-content behavior gracefully (no crash)
7. Verify all four templates mention section-aware behavior in their text
