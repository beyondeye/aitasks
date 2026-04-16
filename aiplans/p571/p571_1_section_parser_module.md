---
Task: t571_1_section_parser_module.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_2_*.md, aitasks/t571/t571_3_*.md, aitasks/t571/t571_4_*.md, aitasks/t571/t571_5_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_1 — Section Parser Module

## Overview

Create `.aitask-scripts/brainstorm/brainstorm_sections.py` — a Python module that parses HTML-comment section markers from proposal and plan markdown content, extracts structured section data with dimension links, and provides query/generation helpers.

## Step 1: Create the module file

**File:** `.aitask-scripts/brainstorm/brainstorm_sections.py`

### 1.1 Imports and constants

```python
"""Parser for structured sections in brainstorm proposals and plans.

Extracts sections delimited by HTML comment markers:
    <!-- section: name [dimensions: dim1, dim2] -->
    ... content ...
    <!-- /section: name -->
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .brainstorm_schemas import DIMENSION_PREFIXES, is_dimension_field
```

### 1.2 Data structures

Define `ContentSection` and `ParsedContent` dataclasses as specified in the task description.

### 1.3 Regex patterns

```python
_OPEN_RE = re.compile(
    r'<!--\s*section:\s*(\S+)(?:\s*\[dimensions?:\s*([^\]]+)\])?\s*-->'
)
_CLOSE_RE = re.compile(r'<!--\s*/section:\s*(\S+)\s*-->')
```

### 1.4 Core `parse_sections()` function

Walk lines, match open/close tags, accumulate:
- Track current open section (name, dimensions, start_line, content_lines)
- On open: start new section, store start_line
- On close: finalize section, store end_line
- Content before first section → preamble
- Content after last section → epilogue
- Content between sections → epilogue of previous / preamble if no previous

### 1.5 Validation function

`validate_sections()` checks:
- Duplicate section names
- Unclosed sections (open without matching close)
- Invalid dimension prefixes (not starting with a `DIMENSION_PREFIX`)
- Close without matching open

### 1.6 Query helpers

- `get_section_by_name()` — linear search through sections list
- `get_sections_for_dimension()` — filter sections whose dimensions list contains the given key
- `section_names()` — list comprehension over sections

### 1.7 Generation helpers

- `format_section_header(name, dimensions)` — produces `<!-- section: name [dimensions: dim1, dim2] -->`
- `format_section_footer(name)` — produces `<!-- /section: name -->`

## Step 2: Verify round-trip

Write a test string with the helpers, parse it, verify all fields match. This is done during implementation verification, not as a separate test file.

## Verification

1. Parse multi-section content → correct section count, names, dimensions, line numbers
2. Parse content with no sections → empty sections, all in preamble
3. Validate duplicate names → error returned
4. Validate unclosed section → error returned
5. Validate invalid dimension prefix → error returned
6. `get_sections_for_dimension()` → correct filtering
7. Round-trip: `format_section_header` + `format_section_footer` → parseable output

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for archival and cleanup.
