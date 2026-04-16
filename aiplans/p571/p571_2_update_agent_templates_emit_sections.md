---
Task: t571_2_update_agent_templates_emit_sections.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_1_*.md, aitasks/t571/t571_3_*.md, aitasks/t571/t571_4_*.md, aitasks/t571/t571_5_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_2 — Update Agent Templates to Emit Sections

## Overview

Update the explorer, synthesizer, and detailer templates to instruct AI agents to wrap their output in HTML-comment section markers with dimension links. Also update input assembly functions to include dimension keys in agent inputs.

## Step 1: Update Explorer Template

**File:** `.aitask-scripts/brainstorm/templates/explorer.md`

### 1.1 Add section format reference

Insert after the "Output" heading (~line 20) a "Section Format" reference block:

```markdown
### Section Format
Wrap each major section of your proposal in structured section markers:
  Opening: <!-- section: name [dimensions: dim1, dim2] -->
  Closing: <!-- /section: name -->
Dimensions reference the dimension keys from the "Dimension Keys" block in your input.
Section names must be lowercase_snake_case.
```

### 1.2 Update File 2: Proposal format

In the "File 2: Proposal (Markdown)" section (~line 43), wrap each required section in markers. Replace the bullet list of sections with explicit examples showing the markers:
- `<!-- section: overview -->` ... `<!-- /section: overview -->`
- `<!-- section: architecture -->` ... `<!-- /section: architecture -->`
- `<!-- section: data_flow -->` ... `<!-- /section: data_flow -->`
- `<!-- section: components [dimensions: component_*] -->` with per-component sub-sections
- `<!-- section: assumptions [dimensions: assumption_*] -->`
- `<!-- section: tradeoffs [dimensions: tradeoff_*] -->`

### 1.3 Add dimension-linking guidance

Instruct: "For the Components section, list ALL `component_*` dimension keys from your input's Dimension Keys block. Similarly link `assumption_*` to Assumptions, `tradeoff_*` to Tradeoffs, `requirements_*` to any Requirements section."

## Step 2: Update Synthesizer Template

**File:** `.aitask-scripts/brainstorm/templates/synthesizer.md`

Same treatment as explorer, plus add `<!-- section: conflict_resolutions -->` for the Conflict Resolutions subsection. Mirror the explorer's section format reference block.

## Step 3: Update Detailer Template

**File:** `.aitask-scripts/brainstorm/templates/detailer.md`

### 3.1 Add section format reference

Same reference block as explorer, inserted after "Output" heading (~line 20).

### 3.2 Update output section format

Wrap each plan section:
- `<!-- section: prerequisites -->`
- `<!-- section: step_by_step [dimensions: component_*] -->` with per-component sub-sections like `<!-- section: steps_database [dimensions: component_database] -->`
- `<!-- section: testing -->`
- `<!-- section: verification [dimensions: assumption_*] -->`

## Step 4: Update Input Assembly Functions

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py`

### 4.1 `_assemble_input_explorer()` (~line 179)

After the "## Reference Files" block, add:
```python
from .brainstorm_schemas import extract_dimensions
dims = extract_dimensions(node_data)
if dims:
    lines.extend(["", "## Dimension Keys",
                  "Use these dimension keys in section markers:"])
    for k in sorted(dims.keys()):
        lines.append(f"- {k}")
```

Note: `node_data` is already read via `read_node()` at the start of the function.

### 4.2 `_assemble_input_detailer()` (~line 283)

Same treatment — extract dimensions from target node and add "## Dimension Keys" section.

### 4.3 `_assemble_input_synthesizer()`

Merge dimension keys from ALL source nodes (deduplicate), then add "## Dimension Keys" section listing them all. This ensures the synthesizer knows all dimensions in play across parents.

## Verification

1. Read updated explorer template — verify section format instructions are present
2. Read updated synthesizer template — verify conflict_resolutions section is wrapped
3. Read updated detailer template — verify plan sections are wrapped with dimension links
4. Run a test by reading the input assembly output — verify "## Dimension Keys" appears
5. Manually create a proposal/plan following the updated format and parse with `parse_sections()` from t571_1

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for archival and cleanup.
