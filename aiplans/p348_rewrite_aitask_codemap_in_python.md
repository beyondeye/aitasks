---
Task: t348_rewrite_aitask_codemap_in_python.md
Worktree: current
Branch: main
Base branch: main
---

# Implementation Plan for t348

## Goals

- Rewrite codemap scanning in Python while keeping `.aitask-scripts/aitask_codemap.sh` as the public CLI entrypoint.
- Add `--include-framework-dirs` so framework-owned directories can be included on demand.
- Add `--ignore-file <path>` to exclude tracked paths using gitignore-style patterns.
- Remove the default project `.gitignore` check because codemap only discovers git-tracked files.
- Keep built-in safety exclusions for `node_modules` and `__pycache__`.
- Treat `aidocs/` and `aiwork/` as normal project directories, not framework directories.
- Improve `--help` text so users and LLMs can understand behavior directly from the script.

## Planned CLI behavior

- Preserve existing commands:
  - `--scan`
  - `--scan --existing <path>`
  - `--write`
- Add new options:
  - `--include-framework-dirs`
  - `--ignore-file <path>`
- Default behavior:
  - discover directories from `git ls-files`
  - exclude framework-owned directories by default
  - exclude `node_modules` and `__pycache__` by built-in safety rules
  - do not read project `.gitignore`

## Implementation steps

1. Update `.aitask-scripts/aitask_codemap.sh`
   - Extend argument parsing for new options.
   - Expand `--help` text with behavior docs and examples.
   - Replace the current scanning logic with a thin wrapper that invokes a Python helper.

2. Add `.aitask-scripts/aitask_codemap.py`
   - Run `git ls-files` to collect tracked paths.
   - Derive top-level directories and child directories from tracked paths.
   - Apply exclusion layers:
     - always exclude `.git`
     - built-in safety exclude `node_modules` and `__pycache__`
     - framework exclude list unless `--include-framework-dirs` is set
     - optional `--ignore-file` patterns using gitignore-style matching via `git check-ignore --no-index`
   - Preserve `--existing` filtering by skipping paths already present in `code_areas.yaml`.
   - Emit the same YAML structure as today.

3. Update tests in `tests/test_contribute.sh`
   - Keep existing codemap tests passing.
   - Add checks for help output documenting new behavior.
   - Add coverage for `--include-framework-dirs`.
   - Add coverage for `aidocs/` and `aiwork/` inclusion by default.
   - Add coverage for built-in `node_modules` / `__pycache__` exclusion.
   - Add coverage for `--ignore-file` filtering.

4. Verification
   - Run `bash tests/test_contribute.sh`.
   - Run any additional targeted checks if needed.

## Post-Implementation

- Revisit this plan file before review and add final implementation notes, deviations, and outcomes.
- If implementation is approved, Step 9 will handle archival and cleanup.

## Final Implementation Notes

- **Actual work done:** Replaced the bash-only codemap scanner with a Python helper in `.aitask-scripts/aitask_codemap.py` while keeping `.aitask-scripts/aitask_codemap.sh` as the documented CLI wrapper. Added `--include-framework-dirs` and `--ignore-file <path>`, preserved `--scan`, `--existing`, and `--write`, updated `--help` with explicit behavior docs and examples, and aligned Python runtime selection with the rest of the framework by preferring `~/.aitask/venv/bin/python` before falling back to `$PYTHON` or `python3`.
- **Deviations from plan:** The implementation does not read the project `.gitignore` by default because discovery stays based on `git ls-files`, making `.gitignore` filtering redundant for the default path. The optional `--ignore-file` behavior remains available for extra filtering of tracked paths.
- **Issues encountered:** One new test initially expected `aitasks/` to appear when framework directories were included. That failed because the recreated `code_areas.yaml` file in the temp repo was untracked after `--write`, so tracked-file-only discovery correctly omitted it. The test was updated to assert the tracked-only behavior instead.
- **Key decisions:** Framework-directory exclusion now applies only to true framework-owned top-level directories; `aidocs/` and `aiwork/` are treated as ordinary project directories. Built-in safety exclusions for `node_modules` and `__pycache__` remain in place even when they contain tracked files.
- **Verification:** `bash tests/test_contribute.sh` passed (`115 passed, 0 failed`). `python3 -m py_compile .aitask-scripts/aitask_codemap.py` also passed.
