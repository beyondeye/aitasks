---
Task: t417_2_core_diff_engine_classical_mode.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_1_*.md, aitasks/t417/t417_3_*.md through t417_7_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Core Diff Engine - Classical Mode (t417_2)

## 1. Create `plan_loader.py`

File: `.aitask-scripts/diffviewer/plan_loader.py`

```python
from __future__ import annotations
import os
import sys

# Import task_yaml from board directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'board'))
from task_yaml import parse_frontmatter

def load_plan(path: str) -> tuple[dict, str, list[str]]:
    """Load a plan file, returning (frontmatter_dict, body_text, body_lines).

    Raises FileNotFoundError if path doesn't exist.
    """
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()

    result = parse_frontmatter(raw)
    if result is None:
        # No frontmatter — treat entire content as body
        lines = raw.splitlines(keepends=True)
        return {}, raw, lines

    metadata, body, _key_order = result
    body_lines = body.splitlines(keepends=True)
    return metadata, body, body_lines
```

## 2. Create `diff_engine.py` — Data Model

File: `.aitask-scripts/diffviewer/diff_engine.py`

Data classes:
- `DiffHunk` — one contiguous region of change (tag, main_lines, other_lines, source_plans, main_range, other_range)
- `PairwiseDiff` — diff between two plans (main_path, other_path, mode, hunks)
- `MultiDiffResult` — collection of pairwise diffs + unique content summaries

## 3. Implement `compute_classical_diff()`

```python
def compute_classical_diff(
    main_lines: list[str],
    other_lines: list[str],
    source_plan: str = ""
) -> list[DiffHunk]:
```

- Create `SequenceMatcher(isjunk=_is_junk, a=main_lines, b=other_lines)`
- `_is_junk(line)`: returns True for blank lines and `---` frontmatter delimiters
- Iterate `get_opcodes()`, map each `(tag, i1, i2, j1, j2)` to a `DiffHunk`:
  - `tag='equal'`: main_lines=a[i1:i2], other_lines=b[j1:j2]
  - `tag='insert'`: main_lines=[], other_lines=b[j1:j2]
  - `tag='delete'`: main_lines=a[i1:i2], other_lines=[]
  - `tag='replace'`: main_lines=a[i1:i2], other_lines=b[j1:j2]
  - Set main_range=(i1,i2), other_range=(j1,j2), source_plans=[source_plan]

## 4. Implement `compute_multi_diff()`

```python
def compute_multi_diff(
    main_path: str,
    other_paths: list[str],
    mode: str = 'classical'
) -> MultiDiffResult:
```

- Load main plan via `plan_loader.load_plan()`
- For each other_path: load plan, compute pairwise diff (classical or structural based on mode)
- Build `MultiDiffResult` with all `PairwiseDiff` objects
- Call `_compute_unique_content()` to populate unique fields

## 5. Implement `_compute_unique_content()`

Algorithm:
- Build a set of "equal line indices" from each pairwise diff (lines in main that matched)
- A main line index is "unique to main" if it was NOT equal in ANY comparison
- For each comparison, a line in other_lines is "unique to other" if it was inserted or in a replace hunk

## 6. Verification

Run manually with test plans from t417_1:
```python
from diffviewer.plan_loader import load_plan
from diffviewer.diff_engine import compute_classical_diff, compute_multi_diff

# Test 1: identical plans
_, _, lines = load_plan('.aitask-scripts/diffviewer/test_plans/plan_alpha.md')
hunks = compute_classical_diff(lines, lines)
assert all(h.tag == 'equal' for h in hunks)

# Test 2: different plans
_, _, alpha = load_plan('.aitask-scripts/diffviewer/test_plans/plan_alpha.md')
_, _, beta = load_plan('.aitask-scripts/diffviewer/test_plans/plan_beta.md')
hunks = compute_classical_diff(alpha, beta)
assert any(h.tag != 'equal' for h in hunks)

# Test 3: multi-diff
result = compute_multi_diff(
    '.aitask-scripts/diffviewer/test_plans/plan_alpha.md',
    ['.aitask-scripts/diffviewer/test_plans/plan_beta.md',
     '.aitask-scripts/diffviewer/test_plans/plan_gamma.md']
)
assert len(result.comparisons) == 2
assert len(result.unique_to_main) > 0
```

## Final Implementation Notes

- **Actual work done:** Created `plan_loader.py` and `diff_engine.py` as specified. Added `tests/test_diff_engine.py` with 27 unit tests covering all modules.
- **Deviations from plan:** Added explicit `os.path.isfile()` check in `load_plan()` before opening (cleaner error message). Added automated Python unittest suite (not in original plan, requested during review).
- **Issues encountered:** None — `parse_frontmatter` API matched expectations exactly.
- **Key decisions:** Used `_is_junk` as first positional arg to `SequenceMatcher` (the `isjunk` parameter) rather than `None`. This makes blank lines and `---` delimiters low-priority for matching.
- **Notes for sibling tasks:** The `plan_loader.load_plan()` returns body lines with `keepends=True` (trailing newlines preserved) — consumers should be aware of this. The `diff_engine` module uses relative imports (`from .plan_loader import ...`) so it must be imported as a package (`from diffviewer.diff_engine import ...`), not as a standalone script. The `_compute_unique_content` algorithm uses set-based line index tracking — unique-to-main means the line was NOT equal in ANY comparison, not ALL comparisons. The `mode` parameter in `compute_multi_diff` is passed through but only `classical` is implemented; `structural` mode (t417_3) will need to add a branch there.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
