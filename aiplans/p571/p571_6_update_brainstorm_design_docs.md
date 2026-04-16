---
Task: t571_6_update_brainstorm_design_docs.md
Parent Task: aitasks/t571_more_structured_brainstorming_created_plan.md
Sibling Tasks: aitasks/t571/t571_1_*.md through t571_5_*.md
Archived Sibling Plans: aiplans/archived/p571/p571_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t571_6 — Update Brainstorm Design Docs

## Overview

Update `aidocs/brainstorming/brainstorm_engine_architecture.md` to document the structured sections feature after all implementation siblings are complete. Describe current state only — no references to prior versions.

## Step 1: Read Current State

Read the implemented code to verify actual names, APIs, and behavior:
- `.aitask-scripts/brainstorm/brainstorm_sections.py` — parser module
- `.aitask-scripts/brainstorm/templates/*.md` — updated templates
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — target_sections parameter
- `.aitask-scripts/brainstorm/brainstorm_app.py` — wizard section step
- `.aitask-scripts/lib/section_viewer.py` — shared viewer
- Read archived sibling plans for implementation details

## Step 2: Add "Structured Sections" Section

New top-level section in the architecture doc covering:
- Section format (HTML comment markers)
- Scope (proposals + plans)
- Data model (ContentSection, ParsedContent)
- Parser API (parse_sections, validate_sections, etc.)
- Dimension linking conventions

## Step 3: Update Agent Templates Section

Document section-aware template output format and dimension keys input block.

## Step 4: Update Operations Section

Document target_sections parameter flow: wizard → register → assemble → agent input.

## Step 5: Add Viewer Documentation

Document section_viewer.py module, widgets, and integration points across TUIs.

## Step 6: Update Directory Layout

Add new files to the file listing table.

## Verification

1. All documented APIs match actual code
2. No forward-looking or backward-looking language (current state only)
3. File paths and function names are accurate

## Step 9: Post-Implementation

Follow Step 9 from the shared workflow for archival and cleanup.
