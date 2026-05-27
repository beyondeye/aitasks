---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [cross_repo, aitask_query]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-26 18:25
updated_at: 2026-05-27 15:03
completed_at: 2026-05-27 15:03
---

## Context

Part of t832 brainstorm decomposition. t826_1 landed cross-repo project plumbing
(`~/.config/aitasks/projects.yaml` registry + `aitask_project_resolve.sh` +
`aitask_create.sh --project`). This task adds the **read-side** cross-repo
surface so skills can query a different aitasks project without hardcoding
`../path/`.

See parent plan: `aiplans/p832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md`.

## Key Files to Modify

- `.aitask-scripts/aitask_query_files.sh` — add `--project <name>` argv-prefix
  parsing to `main()`, before subcommand dispatch. Wraps all subcommands
  (`task-file`, `has-children`, `child-file`, `active-children`,
  `all-children`, `sibling-context`, `plan-file`, `archived-children`,
  `archived-task`, `resolve`, `recent-archived`).
- `.aitask-scripts/aitask_ls.sh` — same pattern for read-only listing.
- `.aitask-scripts/aitask_find_by_file.sh` — same pattern for file-reference
  search.
- **New subcommand** in `aitask_query_files.sh`: `task-status <N|N_M>`
  emitting one line `STATUS:Ready|Editing|Implementing|Postponed|Done|Folded|NOT_FOUND`.
  Uses `read_task_status` from `lib/task_utils.sh`. Required by t832_4
  blocking logic — cheap cross-repo status probe instead of re-exec'ing
  the full lister per dep edge.

## Reference Files for Patterns

- `.aitask-scripts/aitask_create.sh:1693-1753` (`main()`) — the canonical
  re-exec pattern for `--project <name>`. Copy this shape: parse out
  `--project`, resolve via `aitask_project_resolve.sh`, then
  `cd "$root"; exec "$root/.aitask-scripts/<this-helper>.sh" "${forwarded[@]}"`.
- `.aitask-scripts/aitask_project_resolve.sh` — produces `RESOLVED:<path>` /
  `STALE:<name>:<path>` / `NOT_FOUND:<name>`. Die-with-hint on STALE/NOT_FOUND
  (mirror line 1744-1747 of aitask_create.sh).
- `.aitask-scripts/lib/task_utils.sh::read_task_status` — source for the
  new `task-status` subcommand.

## Implementation Plan

1. Implement uniform `--project` argv-prefix transform helper (could live in
   `lib/cross_repo_reexec.sh` to dedup across the 3 helpers — evaluate
   single-file vs lib at impl time).
2. Wire `--project` into `aitask_query_files.sh main()`. All subcommands
   inherit the re-exec for free since it happens before dispatch.
3. Add new `task-status` subcommand in `aitask_query_files.sh`. Handle
   `N` and `N_M` formats (use existing `strip_prefix` / `validate_num`).
4. Wire `--project` into `aitask_ls.sh main()` similarly.
5. Wire `--project` into `aitask_find_by_file.sh` (note: this script has
   a flatter structure than the others; the parse loop at lines 53-64
   needs the same prefix-strip treatment).
6. Update `show_help()` in each touched script to document `--project`.

## Verification Steps

- New test file: `tests/test_query_files_cross_repo.sh`
  - Synthesize two fake aitasks roots in `tmp/` with minimal `metadata/project_config.yaml`.
  - Register both via `AITASKS_PROJECTS_INDEX=<path>` pointing at a fake registry.
  - Exercise each subcommand of `aitask_query_files.sh` with `--project local` and `--project remote` and verify outputs match the expected helper running in each root.
  - Exercise the new `task-status` subcommand for each status.
  - Verify die-with-hint behavior on NOT_FOUND / STALE.
- `shellcheck .aitask-scripts/aitask_query_files.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_find_by_file.sh` clean.
- Manual check: from `aitasks_mobile`, run
  `./.aitask-scripts/aitask_query_files.sh task-file --project aitasks 832`
  and confirm it returns the aitasks-side path.

## Notes for sibling tasks

- The new `task-status` subcommand is the entry point t832_4 uses for cross-repo
  blocking. Keep its output schema stable (`STATUS:<value>` per line).
- The re-exec pattern from this task is the template t832_7 mirrors for
  `aitask_update.sh --project`.

## Out of scope

- `aitask_explain_context.sh` (different shape — owned by t832_2).
- `aitask_revert_analyze.sh` (defer; no immediate need).
- `aitask_codeagent.sh`, `aitask_skillrun.sh` (stay local).
- TUI surfacing of cross-repo data (owned by t832_8).

See parent plan §t832_1 for the full design context.
