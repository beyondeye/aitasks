---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [brainstorming, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-16 11:43
updated_at: 2026-04-16 12:25
---

## Context

This is the foundation task for t571 (Structured Brainstorming Sections). The brainstorming engine's proposal and plan files are currently unstructured markdown with no parsable connection to design dimensions. This task creates a Python parser module that extracts structured sections from both proposals and plans.

The brainstorming engine uses design dimensions as prefix-based YAML keys (`component_*`, `assumption_*`, `requirements_*`, `tradeoff_*`) in node metadata files (`br_nodes/nXXX.yaml`). This parser enables linking specific content sections in proposals/plans to those dimensions.

## Key Files to Modify

- **CREATE**: `.aitask-scripts/brainstorm/brainstorm_sections.py` — The entire parser module

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — Has `DIMENSION_PREFIXES = ("requirements_", "assumption_", "component_", "tradeoff_")`, `is_dimension_field(key)`, and `extract_dimensions(data)`. Reuse these for dimension validation.
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — Has `read_plan()` and `read_proposal()` which return the content strings this parser operates on.

## Implementation Plan

### Section Format (HTML Comments)

```
<!-- section: section_name [dimensions: dim1, dim2] -->
... arbitrary markdown content ...
<!-- /section: section_name -->
```

- Sections are flat (no nesting in v1)
- Dimensions are optional: `<!-- section: prerequisites -->` is valid
- Content outside any section is preamble/epilogue

### Data Structures

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

### Core Functions

1. `parse_sections(text: str) -> ParsedContent` — Main parser. Use regex:
   - Opening tag: `r'<!--\s*section:\s*(\S+)(?:\s*\[dimensions?:\s*([^\]]+)\])?\s*-->'`
   - Closing tag: `r'<!--\s*/section:\s*(\S+)\s*-->'`
   - Walk lines, track open/close, accumulate content

2. `validate_sections(parsed: ParsedContent) -> list[str]` — Returns error messages for: duplicate section names, unclosed sections, invalid dimension prefixes (not starting with a DIMENSION_PREFIX)

3. `get_section_by_name(parsed: ParsedContent, name: str) -> ContentSection | None`

4. `get_sections_for_dimension(parsed: ParsedContent, dimension: str) -> list[ContentSection]` — Returns all sections linked to a given dimension key

5. `format_section_header(name: str, dimensions: list[str] | None = None) -> str` — Generates: `<!-- section: name [dimensions: dim1, dim2] -->`

6. `format_section_footer(name: str) -> str` — Generates: `<!-- /section: name -->`

7. `section_names(parsed: ParsedContent) -> list[str]` — Convenience for listing names

### Import from brainstorm_schemas

```python
from .brainstorm_schemas import DIMENSION_PREFIXES, is_dimension_field
```

Use `is_dimension_field()` in `validate_sections()` to check that dimension references in section tags are valid dimension keys.

## Verification Steps

1. Parse a plan string with 3+ sections (some with dimensions, some without) — verify all fields populated correctly
2. Parse content with no sections — should return empty sections list with all content in preamble
3. Validate: duplicate section names, unclosed sections, invalid dimension prefixes → each returns appropriate error
4. `get_sections_for_dimension("component_database")` returns correct sections when multiple sections share a dimension
5. Verify line numbers are 1-based and accurate
6. Test edge case: section with empty content between open/close tags
7. Test `format_section_header()` and `format_section_footer()` produce parsable output (round-trip test)
