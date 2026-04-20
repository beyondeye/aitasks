---
priority: medium
effort: low
depends: [1, 2, 3, 4, 5]
issue_type: documentation
status: Ready
labels: [brainstorming, ait_brainstorm]
created_at: 2026-04-16 12:19
updated_at: 2026-04-20 09:14
---

## Context

This is a documentation child task for t571 (Structured Brainstorming Sections). After the implementation tasks (t571_1 through t571_5) add structured sections to the brainstorming engine, this task updates the authoritative design document to reflect the new feature.

**Depends on**: All implementation siblings (t571_1 through t571_5) — run this last, after all code changes are complete.

## Key Files to Modify

- **MODIFY**: `aidocs/brainstorming/brainstorm_engine_architecture.md` — The authoritative specification for the brainstorm engine

## Reference Files

- `.aitask-scripts/brainstorm/brainstorm_sections.py` (created by t571_1) — Parser module with format definition, data structures, and API
- `.aitask-scripts/brainstorm/templates/explorer.md`, `synthesizer.md`, `detailer.md`, `patcher.md` (updated by t571_2, t571_3) — Templates with section format instructions
- `.aitask-scripts/brainstorm/brainstorm_crew.py` (updated by t571_3) — `target_sections` parameter on register/assemble functions
- `.aitask-scripts/brainstorm/brainstorm_app.py` (updated by t571_4) — Section selection wizard step
- `.aitask-scripts/lib/section_viewer.py` (created by t571_5) — Shared viewer module
- `aiplans/p571_more_structured_brainstorming_created_plan.md` — Parent plan with full design decisions

## Implementation Plan

### 1. Add a "Structured Sections" section to the architecture doc

Add a new top-level section (after the existing Dimensions section) covering:

- **Section Format**: The HTML comment marker syntax (`<!-- section: name [dimensions: dim1] -->` ... `<!-- /section: name -->`)
- **Scope**: Applies to both proposals (`br_proposals/`) and plans (`br_plans/`)
- **Data Model**: `ContentSection` and `ParsedContent` dataclasses
- **Parser API**: `parse_sections()`, `validate_sections()`, `get_section_by_name()`, `get_sections_for_dimension()`, `format_section_header()`, `format_section_footer()`
- **Dimension Linking**: How sections reference node dimension keys, which sections map to which dimensions in proposals vs plans

### 2. Update the Agent Templates section

Update the existing template documentation to mention:
- Explorer and Synthesizer now emit section-wrapped proposals
- Detailer now emits section-wrapped plans
- All templates receive "## Dimension Keys" in their input
- All templates support section-targeted operation via "## Targeted Section Content" / "## Target Sections" blocks

### 3. Update the Operations section

Document the `target_sections` parameter:
- Available on all four operations (explore, compare, detail, patch)
- How it flows: TUI wizard → `register_*()` → `_assemble_input_*()` → agent `_input.md`
- Behavior when sections are specified vs omitted (backward compat)

### 4. Add Section Viewer documentation

Document the shared viewer module:
- Location: `.aitask-scripts/lib/section_viewer.py`
- Widgets: `SectionMinimap`, `SectionAwareMarkdown`, `SectionViewerScreen`
- Integration points: codebrowser detail pane + `p` keybinding, brainstorm NodeDetailModal tabs, board TaskDetailScreen plan view

### 5. Update the Directory Layout section

Add `brainstorm_sections.py` and `section_viewer.py` to the file listing with descriptions.

## Verification Steps

1. Read the updated document — verify all new features are documented
2. Cross-reference with the actual code — verify file paths, function names, and data structures match the implementation
3. Ensure the document only describes current state (no references to "previously" or "used to be" — per feedback_doc_forward_only)
