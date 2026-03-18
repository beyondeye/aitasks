---
Task: t417_3_diff_engine_structural_mode.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_1_*.md, aitasks/t417/t417_2_*.md, aitasks/t417/t417_4_*.md through t417_7_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Diff Engine - Structural Mode (t417_3)

## 1. Create `md_parser.py`

File: `.aitask-scripts/diffviewer/md_parser.py`

### Section dataclass

```python
@dataclass
class Section:
    heading: str                        # Original heading text
    level: int                          # 0=preamble, 1=#, 2=##, etc.
    content_lines: list[str]            # Body lines under heading
    original_line_range: tuple[int, int]  # (start, end) in source
```

### `parse_sections(lines: list[str]) -> list[Section]`

Algorithm:
1. Initialize `sections = []`, `current_heading = ""`, `current_level = 0`, `current_lines = []`, `start_line = 0`
2. Track `in_code_fence = False` — toggle on lines matching `^\s*```
3. For each line:
   - If in code fence, append to current_lines and continue
   - If line matches `^(#{1,6})\s+(.*)$` (ATX header):
     - Flush current section to list
     - Start new section with extracted heading and level
   - Else: append line to current_lines
4. Flush final section
5. Return sections list

### `normalize_section(section: Section) -> Section`

- Heading: strip leading `#` and whitespace, lowercase
- Content: strip trailing whitespace per line, collapse consecutive blank lines to one, strip leading/trailing blank lines
- Return new Section (don't mutate original)

## 2. Extend `diff_engine.py` with Structural Diff

### `compute_structural_diff(main_lines, other_lines, source_plan="") -> list[DiffHunk]`

**Phase 1 — Parse and normalize:**
- `main_sections = parse_sections(main_lines)`
- `other_sections = parse_sections(other_lines)`
- Create normalized versions for matching

**Phase 2 — Heading-based matching:**
- For each main section, find other section with identical normalized heading
- Mark matched pairs, track indices

**Phase 3 — Content similarity matching:**
- For unmatched sections, compute `SequenceMatcher(normalized_content_a, normalized_content_b).ratio()`
- Match if ratio > 0.6 (configurable threshold)
- Prefer highest ratio when multiple candidates exist

**Phase 4 — Classify and generate hunks:**
- Matched at same position + identical content → `'equal'`
- Matched at same position + different content → `'replace'` (run classical diff within section for detail)
- Matched at different position → `'moved'` (+ classical diff within if content differs)
- Unmatched main sections → `'delete'`
- Unmatched other sections → `'insert'`

**Phase 5 — Flatten:**
- Convert section-level results to flat `DiffHunk` list ordered by main_range
- For 'replace' and 'moved' with intra-section diffs, emit sub-hunks

### Update `compute_multi_diff()`

- Add `mode='structural'` routing: calls `compute_structural_diff()` instead of `compute_classical_diff()`

## 3. Verification

```python
# Test 1: Reordered sections → 'moved' not 'delete+insert'
# plan_alpha and plan_beta share content at different positions
result_struct = compute_multi_diff(alpha_path, [beta_path], mode='structural')
moved_hunks = [h for h in result_struct.comparisons[0].hunks if h.tag == 'moved']
assert len(moved_hunks) > 0  # Structural detects moves

result_class = compute_multi_diff(alpha_path, [beta_path], mode='classical')
moved_hunks_c = [h for h in result_class.comparisons[0].hunks if h.tag == 'moved']
assert len(moved_hunks_c) == 0  # Classical doesn't detect moves

# Test 2: Identical plans, reordered → only equal + moved
# Test 3: Code fences preserved intact
# Test 4: Content similarity matching (similar content, different headings)
```

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
