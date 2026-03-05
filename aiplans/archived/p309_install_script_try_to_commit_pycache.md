---
Task: t309_install_script_try_to_commit_pycache.md
Worktree: .
Branch: main
Base branch: main
---

## Implementation Plan
1. Reproduce why `ait setup` proposes committing Python cache files.
2. Harden framework-file detection in `commit_framework_files()` so cache artifacts are excluded.
3. Ensure Codex setup outputs (`.agents/`, `.codex/`) are included in framework detection.
4. Add regression coverage for both behaviors and verify with existing setup integration tests.
5. Finalize and archive task metadata.

## Execution Notes
- Root cause identified in `commit_framework_files()`: it gathered untracked/modified files from framework paths and then staged whole directories, which could pull in cache artifacts if not ignored.
- Added explicit cache artifact filtering for scan candidates (`__pycache__/`, `.pyc`, `.pyo`, `.pyd`).
- Changed staging from broad path-based `git add` to explicit filtered changed-file staging.
- Expanded framework scan path coverage to include `.agents/` and `.codex/`.
- Added ignore entries for `aiscripts` Python cache directories.
- Extended tests to assert pycache exclusion and Codex file inclusion.
- Validation run:
  - `bash tests/test_setup_git.sh` → 38 passed, 0 failed
  - `bash tests/test_t167_integration.sh` → 14 passed, 0 failed

## Final Implementation Notes
- **Actual work done:** Implemented robust exclusion of Python cache artifacts from setup framework commit scan, updated framework scan scope for Codex directories, and added regression tests to lock behavior.
- **Deviations from plan:** Initial implementation had an empty-list parsing bug in change collection; fixed by switching to line-wise non-empty array population before re-running tests.
- **Issues encountered:** Existing repository had unrelated dirty/untracked workspace items; they were intentionally left untouched.
- **Key decisions:**
  - Stage only the filtered file list rather than framework root paths to prevent accidental inclusion of artifacts.
  - Keep dual protection: ignore rules (`.gitignore`) plus scanner-side filtering for resilience in partially configured repos.
  - Cover Codex artifacts in framework detection because setup may install wrappers/config there.
- **Build verification:** Not applicable; scope is shell/setup behavior and test scripts. Verification was done via targeted test suites.
