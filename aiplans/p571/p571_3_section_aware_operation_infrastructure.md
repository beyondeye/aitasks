---
Task: t571_3_section_aware_operation_infrastructure.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_1_*.md, aitasks/t571/t571_2_*.md, aitasks/t571/t571_4_*.md, aitasks/t571/t571_5_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_3 — Section-Aware Operation Infrastructure

## Overview

Add `target_sections: list[str] | None = None` parameter to all brainstorm operation registration and input assembly functions. When sections are specified, agents receive focused section content instead of (or in addition to) full content references.

## Step 1: Add Import

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py`

At the top, add:
```python
from .brainstorm_sections import parse_sections, get_section_by_name
```

Also import `read_proposal` from `brainstorm_dag` if not already imported.

## Step 2: Update `_assemble_input_explorer()`

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py` (~line 179)

Add `target_sections: list[str] | None = None` parameter.

When `target_sections` is provided:
```python
if target_sections:
    # Read and parse baseline proposal
    proposal_text = read_proposal(session_path, node_id)
    if proposal_text:
        parsed = parse_sections(proposal_text)
        targeted = [s for s in parsed.sections if s.name in target_sections]
        if targeted:
            lines.extend(["", "## Targeted Section Content",
                         "Focus exploration on these sections from the baseline:"])
            for s in targeted:
                dim_str = f" [dimensions: {', '.join(s.dimensions)}]" if s.dimensions else ""
                lines.extend([f"", f"### Section: {s.name}{dim_str}", s.content])
    # Also check baseline plan
    plan_text = read_plan(session_path, node_id)
    if plan_text:
        parsed_plan = parse_sections(plan_text)
        targeted_plan = [s for s in parsed_plan.sections if s.name in target_sections]
        if targeted_plan:
            lines.extend(["", "## Targeted Plan Section Content"])
            for s in targeted_plan:
                dim_str = f" [dimensions: {', '.join(s.dimensions)}]" if s.dimensions else ""
                lines.extend([f"", f"### Section: {s.name}{dim_str}", s.content])
```

## Step 3: Update `_assemble_input_comparator()`

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py` (~line 222)

Add `target_sections: list[str] | None = None` parameter.

When provided, add advisory block:
```python
if target_sections:
    lines.extend(["", "## Section Focus",
                  "Compare only content within these sections across nodes:"])
    for name in target_sections:
        lines.append(f"- {name}")
```

## Step 4: Update `_assemble_input_detailer()`

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py` (~line 283)

Add `target_sections: list[str] | None = None` parameter.

When provided:
```python
if target_sections:
    lines.extend(["", "## Target Sections",
                  "Re-detail only these sections of the existing plan.",
                  "Leave other sections unchanged:"])
    for name in target_sections:
        lines.append(f"- {name}")
    # Include current plan path so agent can read existing sections
    plan_path = session_path / PLANS_DIR / f"{node_id}_plan.md"
    if plan_path.is_file():
        lines.append(f"- Current plan: {plan_path}")
```

## Step 5: Update `_assemble_input_patcher()`

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py` (~line 313)

Add `target_sections: list[str] | None = None` parameter.

When provided:
```python
if target_sections:
    lines.extend(["", "## Target Sections",
                  "Focus the patch on these sections only.",
                  "Leave all other sections unchanged:"])
    for name in target_sections:
        lines.append(f"- {name}")
```

## Step 6: Update All `register_*()` Functions

Each function gets `target_sections: list[str] | None = None` parameter, passed through to its `_assemble_input_*` call.

- `register_explorer()` (~line 349): Add param, pass to `_assemble_input_explorer()`
- `register_comparator()` (~line 393): Add param, pass to `_assemble_input_comparator()`
- `register_detailer()` (~line 469): Add param, pass to `_assemble_input_detailer()`
- `register_patcher()` (~line 506): Add param, pass to `_assemble_input_patcher()`

## Step 7: Update Templates

Add a small conditional instruction section to each template.

### 7.1 `explorer.md`
Add after Rules: "## Section-Targeted Exploration (Optional)\nIf 'Targeted Section Content' is present in your input, focus your architectural exploration on the aspects covered by those sections. Your output proposal should still be complete, but the exploration mandate applies primarily to the targeted areas."

### 7.2 `comparator.md`
Add: "## Section-Focused Comparison (Optional)\nIf a 'Section Focus' block is present in your input, compare the listed sections across nodes. Read proposal content for those sections specifically."

### 7.3 `detailer.md`
Add: "## Section-Targeted Re-Detailing (Optional)\nIf 'Target Sections' are specified in your input, re-detail only those sections of the existing plan. Read the current plan file, keep all non-targeted sections unchanged, and rewrite only the targeted sections."

### 7.4 `patcher.md`
Add: "## Section-Targeted Patching (Optional)\nIf a 'Target Sections' block is present in your input, apply the patch ONLY to the listed sections. Leave all other sections of the plan unchanged."

## Verification

1. Call `register_explorer()` with `target_sections=["overview", "components"]` — verify input contains "Targeted Section Content"
2. Call `register_patcher()` with `target_sections=["step_database"]` — verify "Target Sections" block
3. Call without `target_sections` — verify identical behavior to before
4. Test with content that has no sections — graceful fallback (no crash)
5. All four templates contain their section-aware instruction

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for archival and cleanup.
