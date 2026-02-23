---
Task: t97_added_features_for_release.md
Worktree: (none - working on main branch)
Branch: main
Base branch: main
---

# Plan: t97 — aitask-changelog skill for release notes

## Context

The project has a release workflow (`create_new_release.sh` -> GitHub Actions -> tarball), but no CHANGELOG.md or automated release notes from task completions. Each source code commit includes a `(tNN)` tag linking it to a task, and each completed task has an archived plan with "Final Implementation Notes". This task creates a skill to leverage that data for changelog generation, and integrates it into the release workflow.

## Approach

**Hybrid design**: A bash helper script (`aitask_changelog.sh`) handles data gathering (tag detection, commit parsing, plan resolution, notes extraction), while the SKILL.md orchestrates the workflow and uses Claude's LLM capabilities for summarization.

**Shared library**: Functions common to both `aitask_issue_update.sh` and `aitask_changelog.sh` (`resolve_task_file`, `resolve_plan_file`, `extract_final_implementation_notes`, `extract_issue_url`) were extracted into `aiscripts/lib/task_utils.sh`.

## Implementation

### New files
- `aiscripts/lib/task_utils.sh` — shared library with task/plan resolution functions
- `aiscripts/aitask_changelog.sh` — changelog data gathering script (`--gather` and `--check-version` modes)
- `.claude/skills/aitask-changelog/SKILL.md` — skill definition with full changelog workflow

### Modified files
- `aiscripts/aitask_issue_update.sh` — refactored to source `task_utils.sh` instead of inlining functions; fixed `[[ ]] && die` pattern for `set -e` compatibility
- `create_new_release.sh` — added CHANGELOG.md pre-flight check before release creation
- `.github/workflows/release.yml` — added changelog extraction step, uses changelog body for GitHub Release when available, falls back to auto-generated notes
- `.claude/settings.local.json` — added `aitask_changelog.sh` permission
- `seed/claude_settings.local.json` — added `aitask_changelog.sh` permission
- `aitasks/t91_aitaskexplain_skill.md` — added dependency on t97, noted shared infrastructure

## Verification

1. `./aiscripts/aitask_changelog.sh --gather` — lists t85_10, t89, t92, t93, t94, t95, t96
2. `./aiscripts/aitask_changelog.sh --check-version 0.2.0` — returns exit 1 (no CHANGELOG.md)
3. `./aiscripts/aitask_issue_update.sh --help` — still works after refactoring
4. Invoke `/aitask-changelog` skill to test full workflow

## Final Implementation Notes
- **Actual work done:** Created `aitask-changelog` skill with full workflow (gather data, summarize, version input with validation, overlap detection, review loop, write CHANGELOG.md). Created `aitask_changelog.sh` helper script with `--gather` and `--check-version` modes. Extracted shared functions into `aiscripts/lib/task_utils.sh` and refactored `aitask_issue_update.sh` to use it. Integrated changelog into `create_new_release.sh` (pre-flight check) and `release.yml` (use changelog as release body with auto-generated fallback). Updated t91 with dependency.
- **Deviations from plan:** Fixed a `[[ ]] && die` pattern in `aitask_issue_update.sh` that was incompatible with `set -e` (the `&&` returns exit 1 when the condition is false, causing early exit). This was discovered during testing the changelog script which uses `set -euo pipefail`.
- **Issues encountered:** The `[[ -z "$MODE" ]] && die` pattern in `parse_args()` caused silent script exit under `set -euo pipefail`. Root cause: `[[ false_condition ]] && cmd` returns 1 when the condition is false, and `set -e` treats that as a failure. Fix: use `if [[ ... ]]; then die ...; fi` instead.
- **Key decisions:** Used structured text output format (not JSON) for `aitask_changelog.sh --gather` for simplicity and readability. The SKILL.md handles all LLM-dependent work (summarization, user interaction), while the bash script handles deterministic data gathering. Shared library uses same double-source guard pattern as `terminal_compat.sh`.
