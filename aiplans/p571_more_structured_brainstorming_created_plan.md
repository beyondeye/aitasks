---
Task: t571_more_structured_brainstorming_created_plan.md
Base branch: main
plan_verified: []
---

# Implementation Plan: t571 - Structured Brainstorming Sections

## Context

The brainstorming engine's proposal files (`br_proposals/nXXX.md`) and plan files (`br_plans/nXXX_plan.md`) are currently unstructured markdown. There is no parsable connection between content sections and the design dimensions (`component_*`, `assumption_*`, `requirements_*`, `tradeoff_*` YAML fields in node metadata). This makes it impossible to navigate content by dimension, target brainstorm operations at specific sections, or view a structural overview with dimension tags.

This refactoring introduces structured sections using HTML comment markers, a Python parser, section-aware operations, and a shared plan/proposal viewer reusable across all TUIs (codebrowser, brainstorm, board).

## Decisions

- **Format**: HTML comments: `<!-- section: name [dimensions: dim1, dim2] -->` ... `<!-- /section: name -->`
- **Scope**: Both proposals (`br_proposals/`) AND plans (`br_plans/`)
- **Viewer**: Shared reusable module in `.aitask-scripts/lib/` used by codebrowser, brainstorm TUI, and board TUI. Both enhanced inline minimap and dedicated full-screen viewer.
- **Operations**: All four (detail, patch, compare, explore) support section targeting

## Complexity Assessment: HIGH - Split into 5 child tasks

## Child Task Decomposition

### t571_1: Section Parser Module (Foundation)

**Create** `.aitask-scripts/brainstorm/brainstorm_sections.py`

Parser for the HTML-comment section format, applicable to both proposals and plans.

**Section format**:
```
<!-- section: section_name [dimensions: dim1, dim2] -->
... arbitrary markdown content ...
<!-- /section: section_name -->
```

**Data structures**:
```python
@dataclass
class ContentSection:
    name: str
    dimensions: list[str]      # e.g. ["component_database", "assumption_scale"]
    content: str               # raw markdown between open/close tags
    start_line: int            # 1-based line of opening tag
    end_line: int              # 1-based line of closing tag

@dataclass
class ParsedContent:
    sections: list[ContentSection]
    preamble: str              # content before first section
    epilogue: str              # content after last section
    raw: str                   # original full text
```

**Core functions**:
- `parse_sections(text: str) -> ParsedContent`
- `validate_sections(parsed: ParsedContent) -> list[str]` (returns error messages)
- `get_section_by_name(parsed: ParsedContent, name: str) -> ContentSection | None`
- `get_sections_for_dimension(parsed: ParsedContent, dimension: str) -> list[ContentSection]`
- `format_section_header(name: str, dimensions: list[str] | None = None) -> str`
- `format_section_footer(name: str) -> str`
- `section_names(parsed: ParsedContent) -> list[str]`

**Imports** `DIMENSION_PREFIXES` from `brainstorm_schemas.py` for dimension validation. Uses `re` for parsing HTML comments.

**Key files**:
- CREATE: `.aitask-scripts/brainstorm/brainstorm_sections.py`

**Dependencies**: None
**Effort**: Small-medium

---

### t571_2: Update Agent Templates to Emit Sections

Update ALL content-producing agent templates to emit structured sections.

**Explorer** (`.aitask-scripts/brainstorm/templates/explorer.md`):
- Currently produces proposals with sections: Overview, Architecture, Data Flow, Components, Assumptions, Tradeoffs
- Wrap each section in `<!-- section: overview -->` ... `<!-- /section: overview -->` markers
- The Components section should have sub-sections per component, linked to their `component_*` dimensions
- Assumptions section linked to `assumption_*` dimensions
- Tradeoffs section linked to `tradeoff_*` dimensions
- Add section format reference to the Output specification

**Synthesizer** (`.aitask-scripts/brainstorm/templates/synthesizer.md`):
- Same proposal sections as Explorer, plus "Conflict Resolutions"
- Same section marker treatment as Explorer

**Detailer** (`.aitask-scripts/brainstorm/templates/detailer.md`):
- Currently produces plans with: Prerequisites, Step-by-Step Changes, Testing, Verification Checklist
- Wrap each in section markers
- Step-by-Step Changes should have per-component sub-sections linked to `component_*` dimensions
- Verification Checklist items linked to `assumption_*` dimensions they verify

**Input assembly** (`.aitask-scripts/brainstorm/brainstorm_crew.py`):
- Update `_assemble_input_explorer()` (line 179) to include node dimension keys so the explorer knows what dimensions to reference
- Update `_assemble_input_detailer()` (line 283) — same treatment
- Update `_assemble_input_synthesizer()` to include merged dimension keys from all source nodes

**Key files**:
- MODIFY: `.aitask-scripts/brainstorm/templates/explorer.md`
- MODIFY: `.aitask-scripts/brainstorm/templates/synthesizer.md`
- MODIFY: `.aitask-scripts/brainstorm/templates/detailer.md`
- MODIFY: `.aitask-scripts/brainstorm/brainstorm_crew.py` (input assembly functions)

**Dependencies**: t571_1 (must use the exact same format)
**Effort**: Small-medium

---

### t571_3: Section-Aware Operation Infrastructure (Backend)

Add optional `target_sections: list[str]` parameter to operation registration so agents can focus on specific sections.

**Changes to `.aitask-scripts/brainstorm/brainstorm_crew.py`**:
- `_assemble_input_explorer()`: When `target_sections` provided, parse baseline proposal/plan with `parse_sections()`, inline only targeted section content under a "## Targeted Section Content" heading
- `_assemble_input_patcher()`: Add "## Target Sections" advisory block listing which sections to modify
- `_assemble_input_comparator()`: Add "## Section Focus" block for section-scoped comparison
- `_assemble_input_detailer()`: Add `target_sections` for re-detailing specific sections of an existing plan
- All `register_*()` functions: Add `target_sections=None` parameter, pass through

**Template updates** (minor additions to each):
- `patcher.md`: "If Target Sections block is present, apply patch ONLY to those sections"
- `explorer.md`: "If section-scoped content is provided, focus exploration on those aspects"
- `comparator.md`: "If Section Focus block is present, compare only listed sections"
- `detailer.md`: "If Target Sections are specified, re-detail only those sections"

**Key files**:
- MODIFY: `.aitask-scripts/brainstorm/brainstorm_crew.py` (all register/assemble functions)
- MODIFY: `.aitask-scripts/brainstorm/templates/patcher.md` (section-aware instruction)
- MODIFY: `.aitask-scripts/brainstorm/templates/explorer.md` (section-aware instruction)
- MODIFY: `.aitask-scripts/brainstorm/templates/comparator.md` (section-aware instruction)
- MODIFY: `.aitask-scripts/brainstorm/templates/detailer.md` (section-aware instruction)

**Dependencies**: t571_1
**Effort**: Medium

---

### t571_4: Section Selection in Brainstorm TUI Wizard

Add a section selection step to the brainstorm TUI wizard for all four operations.

**Changes to `.aitask-scripts/brainstorm/brainstorm_app.py`**:
- New `_actions_show_section_select()` method: reads selected node's proposal/plan, parses sections with `parse_sections()`, shows checkboxes with dimension tags, includes "Skip (all sections)" button
- Wizard flow for explore/detail/patch: after node selection (step 2), if the node's content has sections, show section select step before config
- For compare: add section checkboxes in `_config_compare()` config step
- Store selections in `self._wizard_config["target_sections"]`
- Update `_build_summary()` to include selected sections in confirm step
- Update `_run_design_op()` to pass `target_sections` to `register_*()` calls
- Update wizard step counting in `_set_wizard_steps()`

**Key files**:
- MODIFY: `.aitask-scripts/brainstorm/brainstorm_app.py` (wizard state machine, section selection UI)

**Dependencies**: t571_1, t571_3
**Effort**: Medium-large

---

### t571_5: Shared Section Viewer Module + TUI Integration

Create a shared, reusable section-aware viewer module in `.aitask-scripts/lib/` and integrate it into all three TUIs.

**Shared module** — CREATE `.aitask-scripts/lib/section_viewer.py`:

1. `SectionMinimap(Static)` widget:
   - Displays a compact vertical list of section names with dimension tags
   - Each row: `section_name  [dim1, dim2]`
   - Focusable rows, emits a `SectionMinimap.SectionSelected` message when clicked/entered
   - Accepts a `ParsedContent` to populate from

2. `SectionAwareMarkdown(VerticalScroll)` widget:
   - Wraps Textual `Markdown` widget
   - Accepts a `ParsedContent` and renders the full content
   - `scroll_to_section(name)` method to scroll to a section's position
   - Responds to `SectionMinimap.SectionSelected` messages

3. `SectionViewerScreen(ModalScreen)`:
   - Full-screen modal with split layout: SectionMinimap on left, SectionAwareMarkdown on right
   - Tab/arrow navigation between panes
   - Escape to dismiss
   - Constructor takes content string + title

**Integration — Codebrowser**:
- MODIFY `.aitask-scripts/codebrowser/detail_pane.py`: When plan content has sections, mount a `SectionMinimap` above the markdown widget. Handle `SectionSelected` to scroll.
- MODIFY `.aitask-scripts/codebrowser/codebrowser_app.py`: Add `p` keybinding → push `SectionViewerScreen` with current task's plan content.
- MODIFY `.aitask-scripts/codebrowser/annotation_data.py`: Add `plan_sections: list | None = None` field to `TaskDetailContent`.

**Integration — Brainstorm TUI**:
- MODIFY `.aitask-scripts/brainstorm/brainstorm_app.py` `NodeDetailModal` (line 233): In the Proposal and Plan tabs, add `SectionMinimap` above the `Markdown` widget when sections are present. Handle scroll-to-section.

**Integration — Board TUI**:
- MODIFY `.aitask-scripts/board/aitask_board.py` `TaskDetailScreen` (line 1895): When viewing plan content (toggle via `(V)iew Plan`), add `SectionMinimap` above the markdown. Handle scroll-to-section. Also add keybinding to open `SectionViewerScreen` for full-screen reading.

**Key files**:
- CREATE: `.aitask-scripts/lib/section_viewer.py`
- MODIFY: `.aitask-scripts/codebrowser/detail_pane.py`
- MODIFY: `.aitask-scripts/codebrowser/codebrowser_app.py`
- MODIFY: `.aitask-scripts/codebrowser/annotation_data.py`
- MODIFY: `.aitask-scripts/brainstorm/brainstorm_app.py` (NodeDetailModal)
- MODIFY: `.aitask-scripts/board/aitask_board.py` (TaskDetailScreen)

**Dependencies**: t571_1
**Effort**: Large

---

## Dependency Graph

```
t571_1 (Section Parser)
  |
  +---> t571_2 (Agent Templates)
  |
  +---> t571_3 (Operation Infrastructure)
  |       |
  |       +---> t571_4 (TUI Wizard)
  |
  +---> t571_5 (Shared Viewer + Integration)
```

- t571_1 is the foundation with no dependencies
- t571_2, t571_3, t571_5 all depend only on t571_1 (can run in parallel)
- t571_4 depends on both t571_1 and t571_3

## Existing patterns to reuse

- `SectionViewerScreen` follows the `HistoryScreen` pattern (codebrowser) and `NodeDetailModal` pattern (brainstorm) for full-screen modals
- `SectionMinimap` follows the `HistoryList` pattern (codebrowser) for focusable row widgets
- `TuiSwitcherMixin` in `.aitask-scripts/lib/tui_switcher.py` demonstrates the shared-lib-module-imported-by-multiple-TUIs pattern
- `DIMENSION_PREFIXES` and `is_dimension_field()` from `brainstorm_schemas.py` are reused for dimension validation in the parser

## Step 9: Post-Implementation

After all child tasks complete, archive the parent task.
