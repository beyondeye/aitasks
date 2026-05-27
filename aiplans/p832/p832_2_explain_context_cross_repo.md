---
Task: t832_2_explain_context_cross_repo.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_3_xdeps_parser_and_validation.md, aitasks/t832/t832_4_xdeps_blocking_logic.md, aitasks/t832/t832_5_parallel_cross_repo_planning_procedure.md, aitasks/t832/t832_6_retrospective_dogfooding_evaluation.md, aitasks/t832/t832_7_cross_repo_task_update.md, aitasks/t832/t832_8_ait_board_cross_repo_support.md, aitasks/t832/t832_9_manual_verification_cross_repo.md
Archived Sibling Plans: aiplans/archived/p832/p832_1_cross_repo_retrieval_reexec_trio.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-27 16:24
---

# Plan: aitask_explain_context.sh cross-repo (Scope 1b — t832_2)

## Context

Part of the t832 brainstorm (cross-repo skills retrieval). Adds cross-repo
support to `aitask_explain_context.sh` — the canonical "source files →
related plans / tasks" scanner used by planning agents to gather historical
context across repos in a single call.

Unlike t832_1's three sibling helpers (`aitask_query_files.sh`,
`aitask_ls.sh`, `aitask_find_by_file.sh`), this script does **not** use
the uniform argv-prefix re-exec pattern. Reasons:
- The helper writes a cache under `.aitask-explain/codebrowser/` and
  expects to find that cache local to the project containing the source
  files being analyzed. Re-exec'ing the whole call into a sibling root
  would force the cache into the wrong tree.
- The helper's final output is **one aggregated markdown blob** from a
  single Python formatter (`aitask_explain_format_context.py`). Re-exec
  would produce one blob per project, requiring the caller to merge two
  markdown documents by hand — defeating the "one call for planning
  context" contract.

Instead: stay in the local process, iterate per-project, `cd` into each
project's root inside a subshell for the cache-writing portion, then
aggregate `ref:rundir` pairs and call the Python formatter ONCE with the
merged `--ref` arg list (the formatter already accepts repeatable
`--ref`).

## Verification of existing plan against current source

The plan at `aiplans/p832/p832_2_explain_context_cross_repo.md` was
verified against the current state of
`.aitask-scripts/aitask_explain_context.sh`:

- `parse_args()` at lines 48-71 — matches.
- `process_directory()` at lines 154-207 — matches.
- `main()` at lines 209-255 — matches.
- `aitask_explain_format_context.py` already exposes
  `--ref <ref.yaml>:<run_dir>` as a repeatable arg (verified via grep:
  `"--ref", action="append", required=True`), so no Python changes needed.
- `aitask_project_resolve.sh` output protocol (`RESOLVED:`/`NOT_FOUND:`/
  `STALE:`) matches the plan's resolver-dispatch expectations.
- The notation regex `^([a-z0-9_-]+)#(.+)$` is the file-path variant of
  the task-ID regex documented in `aidocs/cross_repo_references.md`
  (`^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$`); the project-name character
  class matches.

Plan is sound — no updates required.

## Implementation steps

1. **Extend `parse_args()` (lines 48-71)** to recognize:
   - `--project <name>:<file>` — explicit name + file pair (repeatable).
     Validates that the argument contains a `:` separator; dies with a
     helpful message otherwise.
   - `aitasks#<file>` — token contains project name; parse via the bash
     regex `^([a-z0-9_-]+)#(.+)$` inline (3 lines — no shared lib yet;
     see "Coordination with sibling tasks" below).
   - Maintain `INPUT_BY_PROJECT[project_name]+=file_path` (newline-
     separated lists in an associative array; bash `declare -A` does not
     support array values directly).
   - Default project name is `_local_` for tokens without a project
     prefix (preserves existing positional-arg behavior).

2. **Refactor `process_directory()` (lines 154-207)** to take a project
   root:
   ```bash
   process_directory_in_project() {
       local project_root="$1"
       local dir_key="$2"
       (
           cd "$project_root"
           # existing process_directory body unchanged — it already uses
           # the relative CODEBROWSER_DIR=.aitask-explain/codebrowser, so
           # the cache lands in the project's own tree automatically.
       )
   }
   ```
   The subshell preserves the caller's PWD. The cache lands inside
   `$project_root/.aitask-explain/codebrowser/` where that project's
   own codebrowser data already lives.

3. **Refactor `main()` (lines 209-255)** to:
   - For each project name in `INPUT_BY_PROJECT`:
     - If `_local_`: project_root = `$(pwd)` (absolute, so subshell
       outputs are still attributable on stdout).
     - Else: resolve via `aitask_project_resolve.sh`; die-with-hint on
       `STALE:` / `NOT_FOUND:` matching the error wording from
       `lib/cross_repo_reexec.sh` for consistency.
   - Group that project's files by directory (`dir_key`) — same
     `dir_to_key()` logic, applied relative to the project root.
   - For each `(project, dir_key)` pair, run
     `process_directory_in_project` and collect ref:rundir pairs.
   - Aggregate all ref:rundir pairs across all projects into a single
     list.
   - Call `aitask_explain_format_context.py` ONCE with the merged
     `--ref` arg list. Pass the original input file tokens (stripped of
     project prefix, with project's full path resolved) as the target
     file args.

4. **Update `show_help()`** to document `--project <name>:<file>` (the
   `:`-separated form) and `aitasks#<file>` notation. Add an example for
   each.

## Tests

`tests/test_explain_context_cross_repo.sh` (new):

- Synthesize two fake aitasks projects in
  `tmp/test_explain_context_cross_repo/{a,b}` each with:
  - `aitasks/metadata/project_config.yaml` declaring `project.name: a` /
    `project.name: b`.
  - A handful of archived task/plan files referencing distinct file
    paths under each project root.
- Set `AITASKS_PROJECTS_INDEX` to a temp registry file listing both.
- From a third "caller" directory (or from project A), invoke:
  - `aitask_explain_context.sh --project a:src/foo.py --project b:lib/bar.py --max-plans 1`
  - Assert single markdown output mentions plan content from BOTH
    projects.
- Run with `aitasks#path` notation: `a#src/foo.py b#lib/bar.py` and
  assert equivalent output to the explicit-pair form.
- Assert caches land in each project's own tree
  (`<project>/.aitask-explain/codebrowser/<dir_key>__<timestamp>/`).
- Assert die-with-hint on `--project not_registered:foo.py` (uses
  resolver `NOT_FOUND:` path).
- Assert die-with-hint on `--project <stale_entry>:foo.py` (registry
  entry whose path no longer exists).

## Verification

- `bash tests/test_explain_context_cross_repo.sh` passes.
- `shellcheck .aitask-scripts/aitask_explain_context.sh` clean.
- Manual: from `aitasks` repo, run
  `./.aitask-scripts/aitask_explain_context.sh --project aitasks_mobile:src/foo.kt --max-plans 1`
  (assuming `aitasks_mobile` is registered) and confirm unified markdown
  output that includes content from the sibling project's history.

## Coordination with sibling tasks

- **`lib/cross_repo_notation.py`** (referenced by t832_8 board TUI work
  and t832_5 parallel planning procedure): if this task lands first,
  the bash regex stays inline (3 lines, trivial). t832_8 introduces a
  Python parser for TUI consumption. Two parsers of ~5 lines each are
  acceptable — do NOT shell out from bash to a Python regex helper.

## Out of scope

- Codebrowser TUI cross-repo (separate work; this task is just the
  explain helper).
- Cross-repo cache invalidation / GC policy (each project owns its own
  cache; codebrowser already handles per-project cleanup).
- Extending the `--project` argv-prefix re-exec pattern from t832_1 to
  this script (deliberately rejected per design above).

## Step 9 (Post-Implementation)

Standard task-workflow Step 9 applies: merge if separate branch (n/a
here since fast profile works on current branch), `aitask_archive.sh
832_2`, push, satisfaction feedback.
