---
priority: medium
effort: medium
depends: [t832_1]
issue_type: feature
status: Done
labels: [cross_repo, aitask_explain]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-26 18:26
updated_at: 2026-05-27 16:50
completed_at: 2026-05-27 16:50
---

## Context

Part of t832 brainstorm decomposition. Adds cross-repo support to
`aitask_explain_context.sh` — the canonical "source files → related plans /
tasks" scanner used by planning agents to gather historical context.

**This task does NOT use the uniform re-exec pattern of t832_1.** The
helper writes a cache under `.aitask-explain/codebrowser/` and calls a
single Python formatter that emits one aggregated markdown blob. Re-exec'ing
into the cross-repo root would (a) write the cache in the cross-repo
project's tree, and (b) require the caller to merge two markdown blobs by
hand — defeating the purpose of "one call for planning context".

See parent plan: `aiplans/p832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md` §t832_2.

## Key Files to Modify

- `.aitask-scripts/aitask_explain_context.sh:48-71` — `parse_args()`:
  accept `--project <name>:<file>` pairs and `aitasks#path` notation.
- `.aitask-scripts/aitask_explain_context.sh:154-207` — `process_directory()`:
  wrap to accept a project root, default to local. Cache lands inside the
  project's own tree.
- `.aitask-scripts/aitask_explain_context.sh:209-255` — `main()`: group inputs
  by `(project_name, dir_key)`, dispatch extract per-project, collect
  `ref:rundir` pairs across all projects, pass the merged `--ref` list to a
  **single** `aitask_explain_format_context.py` call.
- Do NOT touch `aitask_explain_format_context.py` — it already accepts
  multiple `--ref` pairs.

## Reference Files for Patterns

- `.aitask-scripts/aitask_project_resolve.sh` — name → root resolution.
- `.aitask-scripts/aitask_create.sh:1729-1752` — die-with-hint error
  handling for STALE / NOT_FOUND.
- `aidocs/cross_repo_references.md` — `aitasks#path` notation regex.

## Implementation Plan

1. Extend `parse_args()` to recognize both:
   - `--project <name>:<file>` (explicit name + file pair, repeatable)
   - `aitasks#<file>` (project name embedded in token, parsed via the regex
     from `cross_repo_references.md`)
2. Build a per-project file list: `dict[project_name, list[file_path]]`.
3. For each project group:
   - Resolve via `aitask_project_resolve.sh`. Die-with-hint on STALE / NOT_FOUND.
   - Compute dir_keys for the file list relative to that project's root.
   - Run `process_directory()` inside the project's root (`cd "$root"` in a
     subshell so the local PWD is preserved). The cache writes to
     `<root>/.aitask-explain/codebrowser/<dir_key>__<timestamp>/` — exactly
     where codebrowser would look for that project's own data.
4. Aggregate `ref:rundir` pairs from all projects into a single list.
5. Pass the merged list to `aitask_explain_format_context.py` with one `--ref`
   per pair. The formatter emits one unified markdown document spanning all
   projects.
6. Update `show_help()` to document the new flag and notation.

## Verification Steps

- New test file: `tests/test_explain_context_cross_repo.sh`
  - Two fake aitasks projects with minimal task/plan history.
  - Run `aitask_explain_context.sh --project A:src/foo.py --project B:lib/bar.py --max-plans 1`.
  - Verify single markdown output contains plan content from BOTH projects,
    in a single unified document.
  - Verify `aitasks#path` notation produces equivalent output.
- `shellcheck .aitask-scripts/aitask_explain_context.sh` clean.
- Manual: from `aitasks`, run
  `./.aitask-scripts/aitask_explain_context.sh --project aitasks_mobile:src/foo.kt --max-plans 1`
  (assuming the registry has `aitasks_mobile` registered) and confirm
  unified markdown output.

## Notes for sibling tasks

- The notation parser used here (the `aitasks#<file>` regex) is the same
  one t832_5 (parallel-planning procedure) and t832_8 (board TUI) will
  consume. Consider extracting to `.aitask-scripts/lib/cross_repo_notation.py`
  in this task (Python) and a bash equivalent if both are needed; otherwise
  each caller can roll its own short regex.

## Out of scope

- Codebrowser TUI cross-repo (separate work; this task is just the explain
  helper).
- Cross-repo cache invalidation policy (each project owns its own cache).

See parent plan §t832_2 for the full design context.
