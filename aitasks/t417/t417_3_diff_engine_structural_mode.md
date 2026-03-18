---
priority: medium
effort: medium
depends: [t417_2]
issue_type: feature
status: Implementing
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-18 12:22
updated_at: 2026-03-18 13:38
---

## Context

This task adds structural diff mode to the diff engine created in t417_2. While classical mode does line-by-line comparison, structural mode parses markdown into sections (by headings), normalizes them, and matches sections by content rather than position. This means reordering sections between plans doesn't show as spurious additions/deletions — it shows as "moved" instead.

This is critical for comparing brainstorming plans where the same ideas may appear in different order or under different heading names.

## Key Files to Create/Modify

- `.aitask-scripts/diffviewer/md_parser.py` — NEW: Markdown section parser
- `.aitask-scripts/diffviewer/diff_engine.py` — EXTEND: Add `compute_structural_diff()` function

## Reference Files for Patterns

- `.aitask-scripts/diffviewer/diff_engine.py` (from t417_2) — Data model and classical diff to extend
- `.aitask-scripts/diffviewer/test_plans/` (from t417_1) — Test plans designed with structural variation

## Implementation Plan

1. Create `md_parser.py` with Section dataclass:
   ```python
   @dataclass
   class Section:
       heading: str            # Original heading text (e.g., "## Step 1: Setup")
       level: int              # Heading depth (1 for #, 2 for ##, etc.)
       content_lines: list[str]  # Body lines under this heading
       original_line_range: tuple[int, int]  # (start, end) line numbers in source
   ```

2. Implement `parse_sections(lines: list[str]) -> list[Section]`:
   - Split on ATX headers (`# `, `## `, `### `, etc.)
   - Content before the first heading becomes a Section with heading="" and level=0
   - Track code fence state (``` blocks) — never split inside a code fence
   - Each Section contains all lines from its heading to the next heading of same or higher level

3. Implement `normalize_section(section: Section) -> Section`:
   - Lowercase the heading, strip leading `#` and whitespace
   - Collapse multiple consecutive blank lines to one in content
   - Strip trailing whitespace from each content line
   - Return a new Section (immutable normalization)

4. Add `compute_structural_diff(main_lines, other_lines) -> list[DiffHunk]` to `diff_engine.py`:
   - Parse both inputs into Section lists via `parse_sections()`
   - **Phase 1 — Heading match:** Match sections with identical normalized headings
   - **Phase 2 — Content similarity:** For unmatched sections, use `SequenceMatcher.ratio()` on normalized content. Match if ratio > 0.6
   - **Phase 3 — Classify:** Matched sections at same position → 'equal' (if content identical) or 'replace' (if content differs). Matched sections at different positions → 'moved'. Unmatched sections → 'insert' or 'delete'
   - For 'replace' and 'moved' sections with content differences, run classical diff within the section to produce detailed intra-section hunks
   - Return flat list of DiffHunks

5. Update `compute_multi_diff()` to accept `mode='structural'` and route to `compute_structural_diff()`

## Verification

- Parse test plans: each produces a list of Section objects with correct headings and content
- Structural diff of plan_alpha vs plan_beta (which share content at different positions): produces 'moved' hunks where classical mode would show delete+insert pairs
- Structural diff of two identical plans (reordered sections): only 'equal' and 'moved' hunks, no 'insert'/'delete'
- Code fence blocks within sections remain intact (not split into sub-sections)
- Sections with similar content but different headings are matched (ratio > 0.6)
- `compute_multi_diff(alpha, [beta], mode='structural')` returns valid MultiDiffResult
