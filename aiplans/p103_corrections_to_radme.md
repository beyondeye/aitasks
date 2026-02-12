---
Task: t103_corrections_to_radme.md
---

# Plan: README.md corrections (t103)

## Context

The README.md was recently expanded with comprehensive documentation. Several structural issues need fixing: missing TOC, sections in wrong positions, subsection nesting errors, and an outdated release process description.

## Changes (all in `README.md`)

### 1. Add Table of Contents before "Command Reference"

Generate a TOC from all `##` and `###` headings and insert it before the `## Command Reference` section.

### 2. Move "Platform Support" and "Known Issues" before "Quick Install"

Move `## Platform Support` and `## Known Issues` to appear **before** `## Quick Install`. This lets users check compatibility before installing.

### 3. Make `ait setup` the first command in the Command Reference table

Move the `ait setup` row to be the first entry. Also add a note in the Quick Install section referencing `ait setup` documentation.

### 4. Make "Claude Code Permissions" a subsection of `ait setup`

Move the `### Claude Code Permissions` section into the `### ait setup` section, as a `####` subsection.

### 5. Add "central part of the framework" to `/aitask-pick` description

Enhance the opening description to mention that this is the central skill of the framework and the core of the development workflow.

### 6. Make "Execution Profiles" a subsection of `/aitask-pick`

Change `### Execution Profiles` to `#### Execution Profiles` nested under `/aitask-pick`.

### 7. Fix the Release Process section

Replace with: run `/aitask-changelog` first, then `./create_new_release.sh`.

### 8. Regenerate TOC

After all structural changes, regenerate the TOC to reflect the final heading structure.

## Verification

- Read through the final README to verify section order and nesting
- Check that all internal markdown links in the TOC resolve correctly
- Verify no content was accidentally lost during moves

## Final Implementation Notes
- **Actual work done:** All 8 planned changes implemented as a single README.md rewrite (136 insertions, 101 deletions). No new files created besides the plan file.
- **Deviations from plan:** None — all changes implemented as planned.
- **Issues encountered:** None.
- **Key decisions:** Rewrote the full file rather than individual edits due to the number of section moves that would cause line number conflicts. Also added `ait setup` to Usage Examples and enhanced its description in the command table. Added cross-reference link from macOS Known Issues entry to the Known Issues anchor.
