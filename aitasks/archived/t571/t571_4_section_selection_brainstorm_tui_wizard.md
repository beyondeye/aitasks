---
priority: high
effort: high
depends: [t571_3]
issue_type: refactor
status: Done
labels: [brainstorming, ait_brainstorm, ui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-16 11:58
updated_at: 2026-04-17 11:39
completed_at: 2026-04-17 11:39
---

## Context

This is child task 4 of t571 (Structured Brainstorming Sections). It adds a section selection step to the brainstorm TUI wizard so users can target specific sections when launching operations (explore, detail, patch, compare).

The brainstorm TUI (`brainstorm_app.py`) has a wizard-based operation flow: select operation → select node(s) → configure → confirm → launch. This task adds an optional section selection step between node selection and configuration.

**Depends on**: t571_1 (section parser), t571_3 (backend `target_sections` parameter on `register_*` functions)

## Key Files to Modify

- **MODIFY**: `.aitask-scripts/brainstorm/brainstorm_app.py` — Wizard state machine, section selection UI

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_sections.py` (t571_1) — `parse_sections()`, `ParsedContent`, `ContentSection`
- `.aitask-scripts/brainstorm/brainstorm_crew.py` (updated by t571_3) — `register_*()` functions now accept `target_sections` parameter
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `read_plan()`, `read_proposal()` for reading node content
- `.aitask-scripts/brainstorm/brainstorm_app.py` — Key locations:
  - `_NODE_SELECT_OPS = {"explore", "detail", "patch"}` (line 112) — operations that show node selection
  - `_OP_TO_TYPE` mapping (line 114) — operation to agent type mapping
  - Wizard state: `self._wizard_step`, `self._wizard_total_steps`, `self._wizard_op`, `self._wizard_config` (dict)
  - `_actions_show_node_select()` — Renders node selection step
  - `_on_actions_next()` (line 2540) — Handles Next button, transitions between wizard steps
  - `_actions_collect_config()` (line 2369) — Collects config from current step
  - `_build_summary()` (line 2481) — Builds confirmation summary
  - `_run_design_op()` (line 2650) — Dispatches to `register_*()` calls
  - Checkbox usage in compare config (line 2314) — Pattern for section checkboxes
  - `OperationRow` widget (line 530) — Pattern for interactive rows

## Implementation Plan

### 1. Add Section Selection Step

Create `_actions_show_section_select()` method:
```python
def _actions_show_section_select(self) -> None:
    """Show section selection checkboxes for the selected node."""
    node_id = self._wizard_config.get("_selected_node")
    if not node_id:
        self._actions_show_config()
        return

    # Read proposal and plan for the selected node
    from brainstorm.brainstorm_sections import parse_sections
    proposal = read_proposal(self.session_path, node_id)
    plan = read_plan(self.session_path, node_id)

    # Parse sections from both (prefer plan sections, fallback to proposal)
    sections = []
    if plan:
        parsed = parse_sections(plan)
        sections = parsed.sections
    if not sections and proposal:
        parsed = parse_sections(proposal)
        sections = parsed.sections

    if not sections:
        # No sections found, skip this step
        self._actions_show_config()  # or confirm for detail
        return

    # Render checkboxes
    # ... mount section checkboxes with dimension tags
    # Include "All sections (skip)" option
```

Each checkbox row shows: `section_name  [dim1, dim2]` using Rich markup for dimension tags.

### 2. Wire Into Wizard Flow

Modify `_on_actions_next()` (line 2540):
- After node selection (step 2) for `_NODE_SELECT_OPS`, check if sections exist
- If sections exist: show section select step (step 2b)
- If no sections: skip directly to config (explore/patch) or confirm (detail)

Key change in the step transition logic:
```python
if self._wizard_step == 2:
    if self._wizard_op in _NODE_SELECT_OPS:
        node = self._wizard_config.get("_selected_node")
        if not node:
            self.notify("Select a node first", severity="warning")
            return
        if self._wizard_op == "detail":
            self._wizard_config["node"] = node
            # Check for sections before proceeding
            if self._node_has_sections(node):
                self._actions_show_section_select()
            else:
                self._actions_show_confirm()
        else:
            if self._node_has_sections(node):
                self._actions_show_section_select()
            else:
                self._actions_show_config()
```

### 3. Store Selections

When user confirms section selection or clicks "Skip (all sections)":
- Store in `self._wizard_config["target_sections"]` as `list[str]` of section names
- If "Skip" is selected: set to `None` (full content, no targeting)

### 4. Update Confirm Summary

Modify `_build_summary()` (line 2481):
```python
# After existing summary lines...
target_sections = cfg.get("target_sections")
if target_sections:
    lines.append(f"[bold]Sections:[/] {', '.join(target_sections)}")
```

### 5. Pass to Register Functions

Modify `_run_design_op()` (line 2650):
```python
target_sections = cfg.get("target_sections")

if op == "explore":
    agent = register_explorer(
        self.session_path, crew_id, cfg["node"],
        cfg["mandate"], group_name,
        launch_mode=launch_mode,
        target_sections=target_sections,
    )
elif op == "detail":
    agent = register_detailer(
        self.session_path, crew_id, cfg["node"],
        ["."], group_name,
        launch_mode=launch_mode,
        target_sections=target_sections,
    )
elif op == "patch":
    agent = register_patcher(
        self.session_path, crew_id, cfg["node"],
        cfg["patch_request"], group_name,
        launch_mode=launch_mode,
        target_sections=target_sections,
    )
```

For compare, pass sections from the config step checkboxes:
```python
elif op == "compare":
    agent = register_comparator(
        self.session_path, crew_id, cfg["nodes"],
        cfg["dimensions"], group_name,
        launch_mode=launch_mode,
        target_sections=cfg.get("target_sections"),
    )
```

### 6. Compare Config Integration

In `_config_compare()` (line 2308), add section checkboxes after dimension selection. Read sections from the first selected node and offer them as additional scope.

### 7. Wizard Step Count

Update `_set_wizard_steps()` / `_wizard_total_steps` to account for the optional section step. Track whether sections are available with a `_wizard_has_sections` flag.

### 8. Back Navigation

In `_on_actions_back()` (line 2530): if current step is section select, go back to node select. If current step is config and sections were shown, go back to section select.

## Verification Steps

1. Open brainstorm TUI, select "Explore" on a node that has section-structured content — verify section checkboxes appear with dimension tags
2. Select specific sections, proceed to config, verify summary shows selected sections
3. Click "Skip (all sections)" — verify wizard proceeds without target_sections in config
4. Select "Detail" on a node with NO structured content — verify section step is skipped
5. Press Escape/Back from section step — verify it returns to node select
6. Verify the `target_sections` value appears in the launched agent's `_input.md` file
7. Test "Compare" operation — verify section checkboxes appear in the config step
8. Test that the launched operation produces correct results (agent receives section-scoped input)
