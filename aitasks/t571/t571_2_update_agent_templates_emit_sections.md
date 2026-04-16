---
priority: high
effort: medium
depends: [t571_1]
issue_type: refactor
status: Ready
labels: [brainstorming, ait_brainstorm]
created_at: 2026-04-16 11:44
updated_at: 2026-04-16 11:44
---

## Context

This is child task 2 of t571 (Structured Brainstorming Sections). After the section parser module (t571_1) defines the format, this task updates all content-producing agent templates to emit structured sections with dimension tags. This applies to both proposals (explorer, synthesizer) and plans (detailer).

The brainstorm engine uses agent templates in `.aitask-scripts/brainstorm/templates/` as work2do instructions for AI agents. Each template tells the agent what format to produce. Currently, templates describe free-form markdown sections. This task wraps those sections in HTML comment markers with dimension links.

## Key Files to Modify

- **MODIFY**: `.aitask-scripts/brainstorm/templates/explorer.md` — Add section markers to proposal output format
- **MODIFY**: `.aitask-scripts/brainstorm/templates/synthesizer.md` — Same treatment as explorer, plus "Conflict Resolutions" section
- **MODIFY**: `.aitask-scripts/brainstorm/templates/detailer.md` — Add section markers to plan output format
- **MODIFY**: `.aitask-scripts/brainstorm/brainstorm_crew.py` — Update input assembly functions to include dimension keys

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_sections.py` (created by t571_1) — The section format definition; use `format_section_header()` and `format_section_footer()` as the canonical reference for the marker syntax
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — `DIMENSION_PREFIXES`, `extract_dimensions()`
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — `read_node()` returns node YAML data with dimension fields
- `.aitask-scripts/brainstorm/brainstorm_crew.py` lines 179-310 — `_assemble_input_explorer()`, `_assemble_input_detailer()`, `_assemble_input_synthesizer()` functions that build agent inputs

## Implementation Plan

### 1. Explorer Template (`explorer.md`)

The explorer currently produces proposals with sections: Overview, Architecture, Data Flow, Components, Assumptions, Tradeoffs.

Add to the "Output > File 2: Proposal (Markdown)" section (~line 43-51) instructions to wrap each section:

```markdown
Wrap each major section in structured section markers using HTML comments:

<!-- section: overview -->
## Overview
...content...
<!-- /section: overview -->

<!-- section: architecture -->
## Architecture
...content...
<!-- /section: architecture -->

<!-- section: data_flow -->
## Data Flow
...content...
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_database, component_cache] -->
## Components
...content with subsections per component...
<!-- /section: components -->

For the Components section, list ALL component_* dimension keys from the
input's "Dimension Keys" block in the dimensions attribute. Similarly:
- Assumptions section: link to all assumption_* dimension keys
- Tradeoffs section: link to all tradeoff_* dimension keys
- Requirements: link to all requirements_* dimension keys if present

Individual component subsections can also be wrapped:
<!-- section: component_database [dimensions: component_database] -->
### Database Layer
...
<!-- /section: component_database -->
```

Also add a "Section Format Reference" box at the top of the Output section:
```
Section markers use HTML comments:
  Opening: <!-- section: name [dimensions: dim1, dim2] -->
  Closing: <!-- /section: name -->
Dimensions are optional. Section names should be lowercase_snake_case.
```

### 2. Synthesizer Template (`synthesizer.md`)

Same treatment as Explorer. The synthesizer produces the same proposal sections plus "Conflict Resolutions". Add:
- Same section markers for all standard proposal sections
- `<!-- section: conflict_resolutions -->` for the Conflict Resolutions subsection

### 3. Detailer Template (`detailer.md`)

The detailer produces plans with: Prerequisites, Step-by-Step Changes, Testing, Verification Checklist.

Add to the "Output" section (~line 20-49):
```markdown
<!-- section: prerequisites -->
### Prerequisites
...
<!-- /section: prerequisites -->

<!-- section: step_by_step [dimensions: component_database, component_cache, ...] -->
### Step-by-Step Changes
...
<!-- /section: step_by_step -->

Per-component subsections within Step-by-Step:
<!-- section: steps_database [dimensions: component_database] -->
#### Step N: Database Setup
...
<!-- /section: steps_database -->

<!-- section: testing -->
### Testing
...
<!-- /section: testing -->

<!-- section: verification [dimensions: assumption_scale, assumption_team_skill, ...] -->
### Verification Checklist
Link each verification item to the assumption_* dimensions it validates.
<!-- /section: verification -->
```

### 4. Input Assembly Updates (`brainstorm_crew.py`)

Add a "## Dimension Keys" section to the assembled input for explorer, detailer, and synthesizer. This tells the agent what dimension names to reference in section tags.

**`_assemble_input_explorer()` (~line 179):**
After "## Reference Files", add:
```python
# Extract dimension keys from baseline node
from .brainstorm_schemas import extract_dimensions
dims = extract_dimensions(node_data)
if dims:
    lines.extend(["", "## Dimension Keys"])
    for k in sorted(dims.keys()):
        lines.append(f"- {k}")
```

**`_assemble_input_detailer()` (~line 283):**
Same treatment — add dimension keys from the target node.

**`_assemble_input_synthesizer()`:**
Merge dimension keys from ALL source nodes, deduplicate, and list them.

## Verification Steps

1. Read the updated explorer template — verify it includes section format instructions and dimension linking guidance
2. Read the updated synthesizer template — verify it covers the same sections plus conflict_resolutions
3. Read the updated detailer template — verify it covers plan-specific sections with component sub-sections
4. Check `_assemble_input_explorer()` — verify it adds "## Dimension Keys" block from baseline node
5. Check `_assemble_input_detailer()` — same verification
6. Manually write a test proposal/plan following the updated template format and verify it parses correctly with `parse_sections()` from t571_1
7. Ensure backward compatibility: old templates without section markers should still produce valid (though un-sectioned) output
