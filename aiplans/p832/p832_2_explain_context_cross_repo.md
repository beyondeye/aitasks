---
Task: t832_2_explain_context_cross_repo.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_2_explain_context_cross_repo
Branch: aitask/t832_2_explain_context_cross_repo
Base branch: main
---

# Plan: aitask_explain_context.sh cross-repo (Scope 1b)

See parent plan §t832_2 for the design rationale on why this does NOT
use t832_1's uniform re-exec pattern.

## Goal

Make `aitask_explain_context.sh` accept cross-repo input via
`--project <name>:<file>` pairs (and the `aitasks#path` notation), and
emit ONE unified markdown document spanning multiple projects.

## Implementation steps

1. **Extend `parse_args()` (lines 48-71)** to recognize:
   - `--project <name>:<file>` — explicit name + file pair (repeatable).
   - `aitasks#<file>` — token contains project name; parse via the
     regex from `aidocs/cross_repo_references.md`:
     `^([a-z0-9_-]+)#(.+)$`
   - Build `INPUT_BY_PROJECT[project_name] += file_path`. Default project
     name is `_local_` for files without a project prefix.

2. **Refactor `process_directory()` (lines 154-207)** to take a project root:
   ```bash
   process_directory_in_project() {
       local project_root="$1"
       local dir_key="$2"
       (
           cd "$project_root"
           # existing process_directory body — cache, format, etc.
       )
   }
   ```
   The subshell preserves the caller's PWD. The cache lands inside
   `$project_root/.aitask-explain/codebrowser/` where that project's
   own codebrowser data already lives.

3. **Refactor `main()` (lines 209-255)** to:
   - For each project name in `INPUT_BY_PROJECT`:
     - If `_local_`: project_root = `.`
     - Else: resolve via `aitask_project_resolve.sh`; die-with-hint
       on STALE / NOT_FOUND.
   - Group that project's files by directory (`dir_key`).
   - For each (project, dir_key) pair, run `process_directory_in_project`
     and collect ref:rundir pairs.
   - Aggregate all ref:rundir pairs across all projects.
   - Call `aitask_explain_format_context.py` ONCE with the merged
     `--ref` arg list. The formatter already handles multiple `--ref`
     pairs — no Python changes needed.

4. **Update `show_help()`** to document the new flag and notation.

## Tests

`tests/test_explain_context_cross_repo.sh`:
- Two fake aitasks projects with seed task/plan history (a few archived
  plans referencing distinct file paths).
- Run `aitask_explain_context.sh --project a:src/foo.py --project b:lib/bar.py --max-plans 1`.
- Assert single markdown output contains plan content from BOTH projects.
- Run with `aitasks#path` notation (e.g., `a#src/foo.py b#lib/bar.py`)
  and assert equivalent output.
- Verify caches land in each project's tree (`<project>/.aitask-explain/codebrowser/`).
- Verify die-with-hint on `--project not_registered:foo.py`.

## Verification

- `bash tests/test_explain_context_cross_repo.sh` passes.
- `shellcheck .aitask-scripts/aitask_explain_context.sh` clean.
- Manual: from `aitasks`,
  `./.aitask-scripts/aitask_explain_context.sh --project aitasks_mobile:src/foo.kt --max-plans 1`
  produces unified markdown (assuming `aitasks_mobile` is registered).

## Coordination with sibling tasks

- **`lib/cross_repo_notation.py`** (created by t832_8): if this task
  lands first, write the regex parser here as a small bash helper and
  document it; t832_8 will then port to Python. If t832_8 lands first,
  use the Python parser by shelling out (overkill — prefer the bash
  duplicate then). Recommend: this task uses its own minimal bash regex
  (3 lines), t832_8 introduces the Python one for TUI use. Two parsers
  are fine if both are ~5 lines each.

## Out of scope

- Codebrowser TUI cross-repo (separate work).
- Cross-repo cache invalidation / GC policy (each project owns its cache).

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)
