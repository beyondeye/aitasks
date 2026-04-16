---
Task: t571_4_section_selection_brainstorm_tui_wizard.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_1_*.md, aitasks/t571/t571_2_*.md, aitasks/t571/t571_3_*.md, aitasks/t571/t571_5_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_4 — Section Selection in Brainstorm TUI Wizard

## Overview

Add an optional section selection step to the brainstorm TUI wizard so users can target specific sections when launching explore, detail, patch, or compare operations. The step appears between node selection and config, only when the selected node has structured sections.

## Step 1: Add Helper Method `_node_has_sections()`

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`

```python
def _node_has_sections(self, node_id: str) -> bool:
    """Check if a node's proposal or plan has structured sections."""
    from brainstorm.brainstorm_sections import parse_sections
    proposal = read_proposal(self.session_path, node_id)
    if proposal and parse_sections(proposal).sections:
        return True
    plan = read_plan(self.session_path, node_id)
    if plan and parse_sections(plan).sections:
        return True
    return False
```

## Step 2: Create Section Selection UI

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`

Create `_actions_show_section_select()`:
- Read proposal and plan for the selected node
- Parse sections (prefer plan, fallback to proposal)
- Clear the actions content area
- Mount checkboxes for each section, showing: `section_name [dim1, dim2]`
- Add a "Skip (all sections)" button and a "Next" button
- Set `self._wizard_step` to the section step number

Each checkbox label uses Rich markup to show dimension tags in a distinct color.

## Step 3: Wire Section Step Into Wizard Flow

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`

### 3.1 Modify `_on_actions_next()` (~line 2540)

In the step 2 handler for `_NODE_SELECT_OPS`, after setting the selected node:
```python
if self._wizard_op == "detail":
    self._wizard_config["node"] = node
    if self._node_has_sections(node):
        self._actions_show_section_select()
    else:
        self._actions_show_confirm()
else:  # explore, patch
    if self._node_has_sections(node):
        self._actions_show_section_select()
    else:
        self._actions_show_config()
```

### 3.2 Handle "Next" from section step

When user clicks Next on the section step:
- Collect checked section names into `self._wizard_config["target_sections"]`
- Proceed to config step (explore/patch) or confirm step (detail)

### 3.3 Handle "Skip" button

- Set `self._wizard_config["target_sections"]` to `None`
- Proceed as if sections were not available

## Step 4: Update Back Navigation

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`

In `_on_actions_back()` (~line 2530):
- If current step is section select → go back to node select
- If current step is config and `_wizard_has_sections` flag is set → go back to section select

## Step 5: Update Confirm Summary

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`

In `_build_summary()` (~line 2481), add:
```python
target_sections = cfg.get("target_sections")
if target_sections:
    lines.append(f"[bold]Sections:[/] {', '.join(target_sections)}")
```

## Step 6: Pass target_sections to Register Functions

**File:** `.aitask-scripts/brainstorm/brainstorm_app.py`

In `_run_design_op()` (~line 2650), for each operation:
```python
target_sections = cfg.get("target_sections")
```
Pass `target_sections=target_sections` to each `register_*()` call.

## Step 7: Compare Config Integration

In the compare config step (`_config_compare()` ~line 2308), add section checkboxes after dimension checkboxes. Parse sections from the first selected node. Store in `self._wizard_config["target_sections"]`.

## Step 8: Track Section Step in Wizard State

Add `self._wizard_has_sections = False` flag. Set it in `_actions_show_section_select()`. Use it to adjust step counting and back navigation.

## Verification

1. Select "Explore" on a node with sections → section checkboxes appear
2. Select sections, proceed → summary shows selected sections
3. Click "Skip" → wizard proceeds without target_sections
4. Select "Detail" on a node without sections → section step skipped
5. Back from section step → returns to node select
6. Launched agent's `_input.md` contains section-scoped content
7. Compare operation → section checkboxes in config step

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for archival and cleanup.
