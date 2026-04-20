---
Task: t571_6_update_brainstorm_design_docs.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_7_manual_verification_structured_brainstorming.md
Archived Sibling Plans: aiplans/archived/p571/p571_10_board_task_detail_section_viewer_integration.md, aiplans/archived/p571/p571_11_fix_section_viewer_rendering_and_bindings.md, aiplans/archived/p571/p571_1_section_parser_module.md, aiplans/archived/p571/p571_2_update_agent_templates_emit_sections.md, aiplans/archived/p571/p571_3_section_aware_operation_infrastructure.md, aiplans/archived/p571/p571_4_section_selection_brainstorm_tui_wizard.md, aiplans/archived/p571/p571_5_shared_section_viewer_tui_integration.md, aiplans/archived/p571/p571_8_codebrowser_section_viewer_integration.md, aiplans/archived/p571/p571_9_brainstorm_node_detail_section_viewer_integration.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-20 11:32
---

# Plan: t571_6 — Update Brainstorm Design Docs (Verified)

## Context

All five implementation siblings of t571 (structured brainstorming sections) have landed and are archived:

- **t571_1** → `.aitask-scripts/brainstorm/brainstorm_sections.py` — parser, dataclasses, query helpers
- **t571_2** → updated templates in `.aitask-scripts/brainstorm/templates/` + shared `_section_format.md`
- **t571_3** → `target_sections` param on `register_*()` + filtered `_assemble_input_*` in `brainstorm_crew.py`
- **t571_4** → wizard section-select step in `brainstorm_app.py`
- **t571_5** → `.aitask-scripts/lib/section_viewer.py` (shared library)
- **t571_8, t571_9, t571_10, t571_11** (also archived) → section-viewer integrations in codebrowser, brainstorm `NodeDetailModal`, and board `TaskDetailScreen`

The authoritative architecture doc `aidocs/brainstorming/brainstorm_engine_architecture.md` currently has **no mention** of any of this — proposals/plans are still described as opaque markdown, templates shown in Section 4 lack section markers, and subagent prompt specs in Section 8 describe pre-section output formats. This task brings the doc into sync with current state (forward-only writing per `feedback_doc_forward_only`).

## Critical File

- **MODIFY:** `aidocs/brainstorming/brainstorm_engine_architecture.md`

## Reference Files (for verifying current behavior while writing)

- `.aitask-scripts/brainstorm/brainstorm_sections.py` — parser API surface (`parse_sections`, `validate_sections`, `get_section_by_name`, `get_sections_for_dimension`, `section_names`, `format_section_header`, `format_section_footer`; dataclasses `ContentSection`, `ParsedContent`)
- `.aitask-scripts/brainstorm/templates/_section_format.md` — shared include describing marker syntax + lowercase_snake_case naming rule
- `.aitask-scripts/brainstorm/templates/explorer.md`, `synthesizer.md`, `detailer.md`, `patcher.md`, `comparator.md` — current template wording for Output sections
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — `register_explorer/comparator/detailer/patcher` signatures with `target_sections: list[str] | None = None`; `_assemble_input_*` helpers that emit `## Targeted Section Content`, `## Target Sections`, `## Section Focus` blocks
- `.aitask-scripts/brainstorm/brainstorm_app.py` — wizard section-select step (`_collect_target_sections`, `target_sections` in `_wizard_config`)
- `.aitask-scripts/lib/section_viewer.py` — widgets (`SectionRow`, `SectionMinimap`, `SectionAwareMarkdown`, `SectionViewerScreen`), `estimate_section_y()` helper, keyboard contract in module docstring
- Integration sites: `board/aitask_board.py` (around line 2303), `codebrowser/detail_pane.py`, `codebrowser/codebrowser_app.py`, `codebrowser/history_detail.py`, `brainstorm/brainstorm_app.py` (around line 336)
- `aiplans/archived/p571/p571_{1..5,8..11}_*.md` — implementation records (use Final Implementation Notes for design intent and deviations)

## Implementation

### Step 1: Verify current state before writing

Re-read the sources listed above to confirm exact names, signatures, and output block headings. The doc must be accurate to the shipped code, not to the original design docs.

### Step 2: Add new top-level "Structured Sections" section

Insert after existing Section 3 (Data Format Specifications) or as a new subsection under 3. Cover:

- **Scope** — applies to `br_proposals/` and `br_plans/`; not to node YAML or node metadata
- **Marker syntax** — `<!-- section: name [dimensions: dim1, dim2] -->` … `<!-- /section: name -->`, `lowercase_snake_case` names, single-level (no nesting), dimensions optional; reference `_section_format.md` as the shared template include
- **Data model** — `ContentSection(name, dimensions, content, start_line, end_line)` and `ParsedContent(sections, preamble, epilogue, raw)`
- **Parser API** — `parse_sections`, `validate_sections` (duplicate-name, invalid-dimension, unclosed checks), `get_section_by_name`, `get_sections_for_dimension`, `section_names`, `format_section_header`, `format_section_footer`
- **Dimension linking** — `dimensions` list references dimension keys (`component_*`, `assumption_*`, `requirements_*`, `tradeoff_*`); validated against `DIMENSION_PREFIXES` from `brainstorm_schemas`

### Step 3: Refresh Section 4 (Proposal and Plan Templates)

Update the existing proposal and plan template snippets to show actual section-marker wrapping as emitted by current agents. Keep them illustrative but aligned with `templates/*.md` shipping today.

### Step 4: Update Section 6 (Context Assembly) for target_sections

Document the new assembly blocks that each `_assemble_input_*` produces when `target_sections` is set:

- Explorer/Detailer/Patcher → `## Targeted Section Content` (and `## Targeted Plan Section Content` for explorer when applicable)
- Detailer/Patcher → `## Target Sections`
- Comparator → `## Section Focus` (MVP: union/intersection of candidate nodes' sections)
- Synthesizer → **not section-aware** (explicit note)

### Step 5: Update Section 7 (Orchestration Flow) operation descriptions

For explore, compare, detail, patch: note that each operation accepts `target_sections` from the wizard and that `register_*()` / `_assemble_input_*()` propagate it into the agent's `_input.md`. Document backward-compat: when `target_sections` is `None` or omitted, behavior is unchanged (whole proposal/plan).

### Step 6: Refresh Section 8 (Subagent Prompt Specifications)

The literal prompts shown in 8.1–8.5 must match the shipped templates:

- Add the `<!-- include: _section_format.md -->` line where it appears in the real templates
- Document the `## Dimension Keys` input block the templates now mention
- Show that explorer/synthesizer/detailer wrap their outputs in section markers
- Note patcher/comparator behavior when `## Target Sections` / `## Section Focus` is present
- Preserve the "no winner unless scored" and other existing rules that are still in force

### Step 7: Add "Section Viewer" documentation

New subsection (likely under Section 2 or as a peer to Section 7). Cover:

- Module location: `.aitask-scripts/lib/section_viewer.py`
- Widgets: `SectionRow`, `SectionMinimap`, `SectionAwareMarkdown`, `SectionViewerScreen`; `estimate_section_y()` helper
- Keyboard contract (from the module docstring): `tab` toggles minimap↔content focus, `up`/`down` move between rows, `enter` selects, `escape` dismisses `SectionViewerScreen`
- Integration points:
  - Codebrowser detail pane (minimap above plan/proposal) and `p` full-screen viewer
  - Brainstorm `NodeDetailModal` Proposal and Plan tabs (minimaps) and `v` full-screen viewer
  - Board `TaskDetailScreen` plan view (minimap) and `shift+v` full-screen viewer
- Fallback: plans/proposals with no section markers render as plain markdown with no minimap

### Step 8: Update Section 2 (Directory Structure / Directory Layout)

Add the two new source files to the file listing:

- `.aitask-scripts/brainstorm/brainstorm_sections.py` — section parser
- `.aitask-scripts/lib/section_viewer.py` — shared section-aware viewer widgets
- `.aitask-scripts/brainstorm/templates/_section_format.md` — shared template include

### Step 9: Cross-check Table of Contents

If any new top-level sections were added in Steps 2 or 7, update the TOC at the top of the doc accordingly.

## Style Rules

- **Forward-only** (`feedback_doc_forward_only`): describe current state. No "previously", "used to be", "earlier versions". Version history belongs in git.
- **Match shipped code exactly** — function names, block headings in agent inputs, keyboard bindings, file paths. Cross-check each claim against the code before writing.
- **No emojis.**
- Keep the doc self-contained — no "see t571_X" references, no task IDs in prose.

## Verification

1. `grep -n "section" aidocs/brainstorming/brainstorm_engine_architecture.md` → new coverage exists across the sections listed above
2. Every API name, block heading, widget name, and keyboard binding mentioned in the doc matches a hit in the actual source (Grep in `.aitask-scripts/`)
3. No "previously", "used to", "was", "now", "has been changed", or similar forward/backward-looking prose (grep `-iE 'previously|used to|has been|now supports'`)
4. TOC entries resolve to actual in-doc anchors
5. Read the updated doc end-to-end as a new reader — confirm it describes a coherent, self-contained system that matches the codebase

## Step 9 (Post-Implementation)

Follow Step 9 from `task-workflow/SKILL.md` for archival, parent archival (since this is the penultimate child — t571_7 remains as a manual-verification task blocked on this one), and push.

## Final Implementation Notes

- **Actual work done:** Updated `aidocs/brainstorming/brainstorm_engine_architecture.md` in place (361 insertions, 69 deletions) to describe structured sections and the shared section viewer. Added TOC entry for the new Section 4 title and the new Section 9. Added a "Source Code Layout" table to Section 2 listing all brainstorm-related Python modules. Restructured Section 4 into five subsections (marker format, parser API, proposal template, plan template, dimension linking) with updated template examples showing real section markers. Added targeted-variant blocks to Section 6 for explorer/comparator/detailer/patcher input assembly and an explicit "not section-aware" note for synthesizer. Added wizard-level notes to Section 7 operation descriptions (7.2 Explore, 7.3 Compare, 7.4 Hybridize, 7.5 Detail, 7.6 Patch) describing how `target_sections` flows from the wizard through `register_*` / `_assemble_input_*` into the agent's `_input.md`. Updated Section 8 prompt specifications (Explorer, Comparator, Synthesizer, Detailer, Patcher) to describe section-wrapped outputs, `## Dimension Keys`, `## Targeted Section Content`, `## Section Focus`, and `## Target Sections` inputs. Added Section 9 (Section Viewer) with widget table, event contract, keyboard contract, host integration table, and fallback behavior.
- **Deviations from plan:** None material. Kept the new "Structured Sections" content inside an expanded Section 4 rather than creating a separate top-level section, to avoid renumbering the existing sections 5–8 and breaking the two existing cross-references ("see Section 5", "see Section 2 — Directory Layout"). Section 9 (Section Viewer) was added as a new top-level section rather than folded under an existing one, since its widgets are shared across three TUIs and deserve their own anchor.
- **Issues encountered:** Plan checklist referenced keybindings as `p` for codebrowser, `v` for brainstorm, and `shift+v` for board, but verifying against source showed all three hosts use `V` (shift+v) — codebrowser bound to `action_view_plan`, brainstorm and board bound to `action_fullscreen_plan`. The doc records the actual bindings. Plan also referred to Section 6 behaviour as "MVP: union/intersection" of compared-node sections, but the shipped wizard computes the intersection (confirmed against the manual-verification checklist in t571_7); doc reflects the intersection rule.
- **Key decisions:** Listed only one dimension linking level (no nesting). Documented the intentional approximate nature of `estimate_section_y` — the Textual `Markdown` widget does not expose per-line offsets, so the ratio-based positioning is called out as approximate rather than implying exactness. Explicitly documented the synthesizer as non-section-aware to prevent future confusion about why its registration function lacks `target_sections`.
- **Notes for sibling tasks:** t571_7 (manual verification, blocked on this task) should cross-check: the `V` binding in each host, the section-marker fallback (`display=False` when no sections), the intersection behaviour when comparing nodes with overlapping sections, and the "Synthesizer is not section-aware" claim (verify no section picker appears in the hybridize wizard flow).
