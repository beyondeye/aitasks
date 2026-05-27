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

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/aitask_explain_context.sh`: added an
    `INPUT_BY_PROJECT` associative array (newline-separated file lists
    per project key), an `add_input_file` collector, and a
    `classify_token` helper that routes positional tokens through the
    `^([a-z0-9_-]+)#(.+)$` regex (`<name>#<file>`) or falls back to the
    `_local_` project key. `parse_args` learned a `--project <name>:<file>`
    case (validates `:` separator, non-empty halves). A new
    `process_directory_in_project <root> <dir_key>` thin wrapper
    subshells `cd "$root"` and re-emits the inner `process_directory`'s
    `ref:rundir` pair with both halves prepended by `$(pwd)` so the
    caller's PWD doesn't matter when the Python formatter opens them.
    A new `resolve_project_root` shells out to
    `aitask_project_resolve.sh` for non-local names and dies-with-hint
    on `STALE:` / `NOT_FOUND:` (wording mirrors `lib/cross_repo_reexec.sh`).
    `main()` now iterates `INPUT_BY_PROJECT`, groups each project's
    files by dir, dispatches per-(project, dir_key) pair, and
    aggregates ref:rundir pairs into a single `format_context.py` call.
    `show_help()` documents both new surfaces with examples.
  - `tests/test_explain_context_cross_repo.sh` (new): 22 assertions
    covering the explicit pair form, `#` notation, mixed forms, cache
    placement inside each project's tree (and absence in caller's
    CWD), NOT_FOUND / STALE / missing-value / missing-colon / empty-
    halves error wording, and help-text mention of new surfaces.
- **Deviations from plan:**
  - **PWD-vs-formatter path bug** discovered during first test run:
    the inner `process_directory` echoed `ref:rundir` as project-
    relative paths (e.g. `.aitask-explain/codebrowser/src__.../reference.yaml`).
    After the subshell exited back to caller PWD those paths no longer
    resolved and `format_context.py` warned "reference.yaml not found"
    for every project. Fixed by absolutizing both halves of the pair
    inside `process_directory_in_project` before exiting the subshell.
    Plan implicitly assumed the inner script's outputs were path-
    portable; they were not. Added an inline comment to make the
    contract explicit.
  - Did **not** extract a shared `lib/cross_repo_notation.py` (or bash
    equivalent). Per the plan's "Coordination with sibling tasks"
    section, the regex stays inline here (single line, single use
    site); t832_8 will introduce the Python variant for TUI use.
- **Issues encountered:**
  - Initial test failures driven entirely by the PWD bug above. After
    the absolutize fix, all 22 cross-repo assertions pass; existing
    `tests/test_explain_context.sh` (29 assertions) stays green; no
    regressions.
  - Manual cross-repo smoke against `aitasks_mobile` initially looked
    silent — turned out to be a cold cache for `aiplans/` that the
    extract pipeline didn't repopulate (uninstrumented cache miss
    suppressed via `2>/dev/null`). Switched the smoke to
    `libs/build.gradle.kts` (cached in `libs__20260525_101934`), which
    rendered cross-repo unified markdown immediately. Also verified
    the mixed local-+-cross-repo form (`./.aitask-scripts/aitask_ls.sh
    aitasks_mobile#libs/build.gradle.kts`) produces a single document
    containing tasks from both projects (t260_1 local + t10_5 mobile).
- **Key decisions:**
  - **Absolutize at the subshell boundary, not in `format_context.py`**
    — keeps the Python formatter agnostic to cross-repo concerns.
  - **`_local_` as the default project key** preserves the existing
    positional-arg path verbatim. Bare positional file arguments still
    work exactly as before.
  - **`--project` value must contain `:`** even when the path itself
    contains other colons — `${arg%%:*}` / `${arg#*:}` are non-greedy
    on the *first* colon. Project names are constrained to
    `[a-z0-9_-]` by the registry regex, so a project name will never
    accidentally contain a colon.
  - **Newline-separated lists in the assoc-array value** — bash
    `declare -A` cannot hold array values; the newline join + `while
    IFS= read -r f` split is the standard workaround. File paths
    containing literal newlines would break this, but that's not a
    real-world concern for source files.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - The `aitasks#<file>` regex used here is intentionally inline
    (`^([a-z0-9_-]+)#(.+)$`). t832_8 (board TUI) and t832_5
    (parallel-planning procedure) should each implement their own
    short Python equivalent — extracting a shared
    `lib/cross_repo_notation.py` is **not** justified for ~3 lines of
    regex per consumer.
  - The `process_directory_in_project` subshell-and-absolutize pattern
    is the answer to the broader question "how do I run a script that
    reads CWD-relative state inside another project without leaking
    paths back". If t832_5 / t832_8 ever need the same trick, lift it
    into `lib/cross_repo_reexec.sh` as a sibling helper (e.g.
    `cross_repo_subshell_emit`).
  - Per-project cache lives at
    `<project_root>/.aitask-explain/codebrowser/` exactly where each
    project's own codebrowser/explain runs already write. No
    invalidation policy needed beyond what codebrowser already does.
