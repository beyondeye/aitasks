---
Task: t571_3_section_aware_operation_infrastructure.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_4_section_selection_brainstorm_tui_wizard.md, aitasks/t571/t571_5_shared_section_viewer_tui_integration.md, aitasks/t571/t571_6_update_brainstorm_design_docs.md
Archived Sibling Plans: aiplans/archived/p571/p571_1_section_parser_module.md, aiplans/archived/p571/p571_2_update_agent_templates_emit_sections.md
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-16 18:30
---

# Plan: t571_3 — Section-Aware Operation Infrastructure (Verified)

## Context

Add `target_sections: list[str] | None = None` parameter to all brainstorm operation registration and input assembly functions in `brainstorm_crew.py`. When sections are specified, agents receive focused section content/advisory blocks. Templates get conditional instructions for section-aware behavior.

Verified against current codebase — the existing plan (`aiplans/p571/p571_3_section_aware_operation_infrastructure.md`) is sound with minor corrections noted below.

## Verification Notes

- `brainstorm_sections.py` exists with `parse_sections()`, `get_section_by_name()`, `ContentSection`, `ParsedContent` — confirmed
- `read_proposal()` at `brainstorm_dag.py:200`, `read_plan()` at `:206` — both present, NOT imported in `brainstorm_crew.py` yet
- Current `brainstorm_crew.py` imports from `brainstorm_dag`: `NODES_DIR`, `PLANS_DIR`, `PROPOSALS_DIR`, `_read_graph_state`, `read_node` (line 30-36)
- Already imports `extract_dimensions` from `brainstorm_schemas` (added by t571_2)
- Function line numbers shifted from task description (pre-t571_2) but plan file targets by name — all correct
- Templates already have section markers from t571_2; patcher/comparator do NOT have them (as expected)
- `_section_format.md` include exists as shared section format reference

## Implementation

### Step 1: Add Imports to `brainstorm_crew.py`

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py`

Add `parse_sections, get_section_by_name` import (new line after existing imports):
```python
from .brainstorm_sections import parse_sections, get_section_by_name
```

Add `read_proposal, read_plan` to existing `brainstorm_dag` import block (line 30-36):
```python
from .brainstorm_dag import (
    NODES_DIR,
    PLANS_DIR,
    PROPOSALS_DIR,
    _read_graph_state,
    read_node,
    read_plan,
    read_proposal,
)
```

### Step 2: Update `_assemble_input_explorer()` (line 180)

Add `target_sections: list[str] | None = None` parameter.

When `target_sections` is provided, after the existing content, add targeted section blocks. **Deviation from original plan:** Wrap `read_proposal` in try/except since it raises on missing file:

```python
if target_sections:
    try:
        proposal_text = read_proposal(session_path, base_node_id)
    except FileNotFoundError:
        proposal_text = None
    if proposal_text:
        parsed = parse_sections(proposal_text)
        targeted = [s for s in parsed.sections if s.name in target_sections]
        if targeted:
            lines.extend(["", "## Targeted Section Content",
                         "Focus exploration on these sections from the baseline:"])
            for s in targeted:
                dim_str = f" [dimensions: {', '.join(s.dimensions)}]" if s.dimensions else ""
                lines.extend(["", f"### Section: {s.name}{dim_str}", s.content])
    plan_text = read_plan(session_path, base_node_id)
    if plan_text:
        parsed_plan = parse_sections(plan_text)
        targeted_plan = [s for s in parsed_plan.sections if s.name in target_sections]
        if targeted_plan:
            lines.extend(["", "## Targeted Plan Section Content"])
            for s in targeted_plan:
                dim_str = f" [dimensions: {', '.join(s.dimensions)}]" if s.dimensions else ""
                lines.extend(["", f"### Section: {s.name}{dim_str}", s.content])
```

Insert before the final `return "\n".join(lines) + "\n"`.

### Step 3: Update `_assemble_input_comparator()` (line 231)

Add `target_sections: list[str] | None = None` parameter.

Append advisory block before return:
```python
if target_sections:
    lines.extend(["", "## Section Focus",
                  "Compare only content within these sections across nodes:"])
    for name in target_sections:
        lines.append(f"- {name}")
```

### Step 4: Update `_assemble_input_detailer()` (line 302)

Add `target_sections: list[str] | None = None` parameter.

Append advisory block before return:
```python
if target_sections:
    lines.extend(["", "## Target Sections",
                  "Re-detail only these sections of the existing plan.",
                  "Leave other sections unchanged:"])
    for name in target_sections:
        lines.append(f"- {name}")
    plan_path = session_path / PLANS_DIR / f"{node_id}_plan.md"
    if plan_path.is_file():
        lines.append(f"\nCurrent plan: {plan_path}")
```

### Step 5: Update `_assemble_input_patcher()` (line 340)

Add `target_sections: list[str] | None = None` parameter.

Append advisory block before return:
```python
if target_sections:
    lines.extend(["", "## Target Sections",
                  "Focus the patch on these sections only.",
                  "Leave all other sections unchanged:"])
    for name in target_sections:
        lines.append(f"- {name}")
```

### Step 6: Update all `register_*()` functions

Each gets `target_sections: list[str] | None = None` parameter, passed to its `_assemble_input_*` call:

- `register_explorer()` (line 376): Add param, pass to `_assemble_input_explorer(..., target_sections=target_sections)`
- `register_comparator()` (line 420): Add param, pass to `_assemble_input_comparator(..., target_sections=target_sections)`
- `register_detailer()` (line 496): Add param, pass to `_assemble_input_detailer(..., target_sections=target_sections)`
- `register_patcher()` (line 533): Add param, pass to `_assemble_input_patcher(..., target_sections=target_sections)`

**Note:** `register_synthesizer()` is NOT updated — synthesizers merge multiple nodes and section targeting doesn't apply to merge operations.

### Step 7: Update Templates

Add conditional instruction section to each template, inserted between the Rules section and the `---` separator.

**`explorer.md`** — After line 107 (last rule), before `---` at line 109:
```markdown

## Section-Targeted Exploration (Optional)
If "Targeted Section Content" is present in your input, focus your
architectural exploration on the aspects covered by those sections. Your
output proposal should still be complete, but the exploration mandate
applies primarily to the targeted areas.
```

**`comparator.md`** — After line 53 (last rule), before `---` at line 55:
```markdown

## Section-Focused Comparison (Optional)
If a "Section Focus" block is present in your input, compare the listed
sections across nodes. Read proposal content for those sections specifically.
Your comparison matrix should still cover the requested dimensions.
```

**`detailer.md`** — After line 84 (last rule), before `---` at line 86:
```markdown

## Section-Targeted Re-Detailing (Optional)
If "Target Sections" are specified in your input, re-detail only those
sections of the existing plan. Read the current plan file, keep all
non-targeted sections unchanged, and rewrite only the targeted sections.
```

**`patcher.md`** — After line 69 (last rule), before `---` at line 71:
```markdown

## Section-Targeted Patching (Optional)
If a "Target Sections" block is present in your input, apply the patch ONLY
to the listed sections. Leave all other sections of the plan unchanged.
If the patch request conflicts with the section scope, note the conflict
in your output.
```

## Verification

1. All four `_assemble_input_*` functions accept and handle `target_sections`
2. All four `register_*` functions pass `target_sections` through
3. Calling any function WITHOUT `target_sections` produces identical output to before
4. Explorer with `target_sections` on content with sections produces "Targeted Section Content" block
5. Explorer with `target_sections` on content with NO sections gracefully produces no extra block
6. `read_proposal` failure (missing file) doesn't crash — handled by try/except
7. All four templates contain their section-aware instruction
8. Existing tests still pass: `python -m pytest tests/test_brainstorm_sections.py -v`

## Final Implementation Notes
- **Actual work done:** Added `target_sections: list[str] | None = None` parameter to all 4 `_assemble_input_*` functions and all 4 `register_*` functions (explorer, comparator, detailer, patcher). Added imports for `parse_sections`, `get_section_by_name` from `brainstorm_sections` and `read_proposal`, `read_plan` from `brainstorm_dag`. Added section-aware conditional instruction blocks to all 4 agent templates (explorer, comparator, detailer, patcher). `register_synthesizer` intentionally NOT updated — synthesizers merge nodes and section targeting doesn't apply.
- **Deviations from plan:** Added `try/except FileNotFoundError` around `read_proposal()` in the explorer assembly — the original task plan assumed `if proposal_text:` would suffice, but `read_proposal()` raises on missing file rather than returning None (unlike `read_plan()` which returns None).
- **Issues encountered:** None.
- **Key decisions:** Explorer gets the richest section-aware behavior (inline section content from both proposal and plan). Comparator, detailer, and patcher get advisory blocks only (section names listed, agent reads content itself). This matches the different agent roles — explorer needs content upfront for exploration, while others work with existing files.
- **Notes for sibling tasks:** The `target_sections` parameter is now available on all registration functions but no caller passes it yet. t571_4 (TUI wizard) should add UI for selecting sections and pass them through to `register_*()` calls. The parameter uses `list[str]` with section names matching `ContentSection.name` from `brainstorm_sections.py`. All functions are backward-compatible — omitting `target_sections` produces identical output to before.

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for archival and cleanup.
