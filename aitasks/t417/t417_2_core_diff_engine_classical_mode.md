---
priority: medium
effort: medium
depends: [t417_1]
issue_type: feature
status: Implementing
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-18 12:22
updated_at: 2026-03-18 12:56
---

## Context

This task builds the core diff engine for classical (line-by-line) diff computation. It provides the data model and algorithms that all subsequent diff-related tasks depend on. The engine uses Python's standard library `difflib.SequenceMatcher` — no external diff libraries needed.

This is the computational backbone of the diff viewer. The structural mode (t417_3), display widget (t417_4), viewer screen (t417_6), and merge feature (t417_7) all build on the data model and functions created here.

## Key Files to Create

- `.aitask-scripts/diffviewer/diff_engine.py` — Core diff module with data classes and algorithms
- `.aitask-scripts/diffviewer/plan_loader.py` — Plan file I/O (frontmatter parsing + body extraction)

## Reference Files for Patterns

- `.aitask-scripts/board/task_yaml.py` — YAML frontmatter parsing to reuse (import via sys.path: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'board'))`)
- `.aitask-scripts/board/aitask_merge.py` — Existing conflict marker parsing, reference for merge/diff approach
- Python `difflib` module documentation — `SequenceMatcher.get_opcodes()` returns `(tag, i1, i2, j1, j2)` tuples

## Implementation Plan

1. Create `plan_loader.py`:
   - `load_plan(path: str) -> tuple[dict, str, list[str]]` — returns (frontmatter_dict, body_text, body_lines)
   - Import `task_yaml` from the board directory via sys.path manipulation
   - Handle missing files gracefully (raise `FileNotFoundError` with descriptive message)
   - Strip YAML frontmatter delimiters from the body lines

2. Create `diff_engine.py` with data classes:
   ```python
   from __future__ import annotations
   from dataclasses import dataclass, field

   @dataclass
   class DiffHunk:
       tag: str  # 'equal', 'insert', 'delete', 'replace', 'moved'
       main_lines: list[str] = field(default_factory=list)
       other_lines: list[str] = field(default_factory=list)
       source_plans: list[str] = field(default_factory=list)
       main_range: tuple[int, int] = (0, 0)  # line numbers in main
       other_range: tuple[int, int] = (0, 0)  # line numbers in other

   @dataclass
   class PairwiseDiff:
       main_path: str
       other_path: str
       mode: str  # 'classical' or 'structural'
       hunks: list[DiffHunk] = field(default_factory=list)

   @dataclass
   class MultiDiffResult:
       main_path: str
       comparisons: list[PairwiseDiff] = field(default_factory=list)
       unique_to_main: list[DiffHunk] = field(default_factory=list)
       unique_to_others: dict[str, list[DiffHunk]] = field(default_factory=dict)
   ```

3. Implement `compute_classical_diff(main_lines, other_lines) -> list[DiffHunk]`:
   - Use `difflib.SequenceMatcher(None, main_lines, other_lines)`
   - Map opcodes to DiffHunk objects: 'equal'→equal, 'insert'→insert, 'delete'→delete, 'replace'→replace
   - Set `main_range` and `other_range` from opcode indices
   - Filter `junk`: blank lines and `---` delimiters as low-priority for matching

4. Implement `compute_multi_diff(main_path, other_paths, mode='classical') -> MultiDiffResult`:
   - Load main plan via `plan_loader.load_plan()`
   - For each other_path, load plan and compute pairwise diff
   - Call `_compute_unique_content()` to populate unique_to_main and unique_to_others

5. Implement `_compute_unique_content(result: MultiDiffResult)`:
   - A line is "unique to main" if it appears as 'delete' or in 'replace' main_lines in ALL pairwise diffs (not equal in any comparison)
   - A line is "unique to other X" if it appears as 'insert' or in 'replace' other_lines only in that comparison

## Verification

- `compute_classical_diff(lines, lines)` → all hunks have tag 'equal'
- `compute_classical_diff(alpha_lines, beta_lines)` → contains insert, delete, and/or replace hunks
- `compute_multi_diff(alpha, [beta, gamma])` → `unique_to_main` is non-empty, `unique_to_others` has entries for both beta and gamma
- `plan_loader.load_plan()` correctly separates frontmatter from body
- Data classes serialize/deserialize cleanly (test with repr/str)
