---
priority: medium
effort: medium
depends: [t423_7]
issue_type: refactor
status: Ready
labels: [brainstorming, tui]
created_at: 2026-03-20 12:41
updated_at: 2026-03-20 12:41
---

## Context
Add CLI parameter support to the diff viewer TUI so it can be called programmatically from the brainstorm TUI. Currently the diff viewer always starts at the file browser. With parameters, it should skip the browser and go directly to diff comparison. It should also return modified file paths and diff output for the caller to process.

## Key Files to Modify
- `.aitask-scripts/diffviewer/diffviewer_app.py` — Add CLI arg parsing, skip browser when params provided
- `.aitask-scripts/diffviewer/plan_manager_screen.py` — May need to extract diff launch logic for reuse

## Reference Files for Patterns
- `.aitask-scripts/diffviewer/diff_engine.py` — `compute_multi_diff()` for diff computation
- `.aitask-scripts/diffviewer/merge_engine.py` — `MergeSession`, `apply_merge()` for merge result

## Implementation
1. Add argparse to diffviewer_app.py: --main <file>, --other <file1> [file2...], --mode classical|structural, --result-file <path>, --diff-output <path>
2. When --main provided: skip PlanManagerScreen, go directly to DiffViewerScreen with pre-loaded files
3. On merge save: write modified file path to --result-file (or default temp)
4. On app exit: print result file path to stdout
5. If --diff-output provided: serialize DiffHunks to JSON and write to file
6. No changes to existing interactive flow (no args = current behavior)

## Manual Verification
1. `python diffviewer_app.py` → starts at file browser (no regression)
2. `python diffviewer_app.py --main plan_a.md --other plan_b.md` → diff view directly
3. Merge + save → result file has modified paths
4. `--diff-output /tmp/diff.json` → JSON created
