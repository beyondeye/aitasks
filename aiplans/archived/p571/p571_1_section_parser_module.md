---
Task: t571_1_section_parser_module.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_2_update_agent_templates_emit_sections.md, aitasks/t571/t571_3_section_aware_operation_infrastructure.md, aitasks/t571/t571_4_section_selection_brainstorm_tui_wizard.md, aitasks/t571/t571_5_shared_section_viewer_tui_integration.md, aitasks/t571/t571_6_update_brainstorm_design_docs.md
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-16 15:47
---

# Plan: t571_1 — Section Parser Module (Verified)

## Context

The brainstorming engine's proposal and plan files are unstructured markdown with no parsable connection to design dimensions. This task creates a Python parser module (`brainstorm_sections.py`) that extracts structured sections delimited by HTML comment markers, enabling downstream tasks (t571_2-t571_6) to link content to dimension keys, build section-aware operations, and add a section viewer TUI.

## Verification Notes

- `brainstorm_sections.py` does NOT exist yet — confirmed (new file creation)
- `DIMENSION_PREFIXES` at `brainstorm_schemas.py:21`, `is_dimension_field()` at `:116` — both present and correct
- `read_proposal()` at `brainstorm_dag.py:200`, `read_plan()` at `:206` — present (not needed in this task but referenced for context)
- Package uses relative imports (`from .brainstorm_schemas import ...`) — confirmed via `__init__.py`
- No other module already handles section parsing — no conflicts

## Implementation

### File: `.aitask-scripts/brainstorm/brainstorm_sections.py` (CREATE)

**1. Imports and module docstring**
```python
from __future__ import annotations
import re
from dataclasses import dataclass, field
from .brainstorm_schemas import DIMENSION_PREFIXES, is_dimension_field
```

**2. Data structures**
```python
@dataclass
class ContentSection:
    name: str                  # e.g. "database_layer"
    dimensions: list[str]      # e.g. ["component_database", "assumption_scale"]
    content: str               # raw markdown between open/close tags
    start_line: int            # 1-based line number of opening tag
    end_line: int              # 1-based line number of closing tag

@dataclass
class ParsedContent:
    sections: list[ContentSection]
    preamble: str              # content before first section
    epilogue: str              # content after last section
    raw: str                   # original full text
```

**3. Regex patterns**
```python
_OPEN_RE = re.compile(
    r'<!--\s*section:\s*(\S+)(?:\s*\[dimensions?:\s*([^\]]+)\])?\s*-->'
)
_CLOSE_RE = re.compile(r'<!--\s*/section:\s*(\S+)\s*-->')
```

**4. `parse_sections(text: str) -> ParsedContent`**
- Walk lines (enumerate 1-based)
- Track `current_section` (name, dims, start, content_lines)
- On open tag match: start new section, parse optional dimensions (split by `,`, strip)
- On close tag match: finalize ContentSection, append to sections list
- Lines before first open → preamble; lines after last close → epilogue
- Lines between sections (not inside any) → append to epilogue

**5. `validate_sections(parsed: ParsedContent) -> list[str]`**
- Check for duplicate section names
- Check for unclosed sections (open without close — detected during parse as leftovers, but validate post-hoc by re-scanning raw text)
- Check dimension prefixes using `is_dimension_field()` — each dimension in each section must start with a valid prefix
- Return list of error strings (empty = valid)

**6. Query helpers**
- `get_section_by_name(parsed, name) -> ContentSection | None`
- `get_sections_for_dimension(parsed, dimension) -> list[ContentSection]`
- `section_names(parsed) -> list[str]`

**7. Generation helpers**
- `format_section_header(name, dimensions=None) -> str`
- `format_section_footer(name) -> str`

### File: `tests/test_brainstorm_sections.py` (CREATE)

Follows the existing pattern from `tests/test_brainstorm_dag.py`: `unittest.TestCase`, `sys.path.insert` for `.aitask-scripts`, no temp dirs needed (pure string parsing).

**Test class: `TestParseSections`**
- `test_multi_section_with_dimensions` — 3 sections (some with dims, some without), verify names, dimensions, content, 1-based line numbers
- `test_no_sections` — plain markdown, empty sections list, all content in preamble, empty epilogue
- `test_empty_section_content` — open/close on consecutive lines, content is empty string
- `test_preamble_and_epilogue` — content before first and after last section captured correctly
- `test_content_between_sections` — inter-section text goes to epilogue

**Test class: `TestValidateSections`**
- `test_duplicate_section_names` — two sections with same name → error returned
- `test_unclosed_section` — open tag without matching close → error returned
- `test_invalid_dimension_prefix` — dimension not starting with a DIMENSION_PREFIX → error returned
- `test_valid_sections_no_errors` — well-formed input → empty error list

**Test class: `TestQueryHelpers`**
- `test_get_section_by_name_found` — returns correct ContentSection
- `test_get_section_by_name_not_found` — returns None
- `test_get_sections_for_dimension` — multiple sections sharing a dimension → all returned
- `test_section_names` — returns list of all names in order

**Test class: `TestGenerationHelpers`**
- `test_format_header_with_dimensions` — produces `<!-- section: name [dimensions: d1, d2] -->`
- `test_format_header_no_dimensions` — produces `<!-- section: name -->`
- `test_format_footer` — produces `<!-- /section: name -->`
- `test_round_trip` — generate header+content+footer, parse back, verify all fields match

**Run:** `python -m pytest tests/test_brainstorm_sections.py -v` or `python -m unittest tests.test_brainstorm_sections`

## Verification

1. All automated tests pass: `python -m pytest tests/test_brainstorm_sections.py -v`
2. Manual smoke test: `python -c "from brainstorm.brainstorm_sections import parse_sections; ..."` from `.aitask-scripts/`

## Final Implementation Notes
- **Actual work done:** Created `brainstorm_sections.py` (165 LOC) with all 7 planned components (2 dataclasses, 2 regex patterns, parser, validator, 4 query/generation helpers). Created `test_brainstorm_sections.py` with 20 unit tests across 4 test classes — all passing.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Content between sections (not inside any section) is accumulated into epilogue, keeping preamble strictly as content before the first section. Unclosed section detection uses a separate raw-text re-scan rather than relying on parser state, making validation independent of parse order.
- **Notes for sibling tasks:** The `_OPEN_RE` and `_CLOSE_RE` patterns are module-level constants that t571_2 (agent templates) should use as the canonical format reference. The `format_section_header()`/`format_section_footer()` helpers should be used by t571_2 when generating section markers in templates. The `parse_sections()` function is the entry point for t571_3 (section-aware operations) and t571_5 (TUI viewer). Dimensions are validated via `is_dimension_field()` from `brainstorm_schemas` — any new dimension prefixes added there will automatically be recognized.

## Post-Implementation

Follow Step 9 from the shared workflow for archival and cleanup.
