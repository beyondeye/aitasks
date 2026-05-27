---
Task: t832_1_cross_repo_retrieval_reexec_trio.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_1_cross_repo_retrieval_reexec_trio
Branch: aitask/t832_1_cross_repo_retrieval_reexec_trio
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-27 14:45
---

# Plan: cross-repo retrieval re-exec trio (Scope 1a)

See task description and parent plan §t832_1 for full context:
`aiplans/p832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md`.

## Goal

Add `--project <name>` to three helpers via uniform argv-prefix re-exec
(mirror `aitask_create.sh:1693-1753`), plus introduce a `task-status`
subcommand on `aitask_query_files.sh` for cheap cross-repo status probes.

## Implementation steps

1. **Optional: extract the re-exec helper.** If the three call sites
   end up with > 30 lines of duplicated argv-parse + resolver-dispatch
   code, lift into `.aitask-scripts/lib/cross_repo_reexec.sh` exposing
   `cross_repo_reexec_or_continue "$@"` that either re-execs into the
   target project's helper or returns to let the caller proceed. Decide
   at impl time based on actual code size.

2. **`aitask_query_files.sh`**
   - Add `--project <name>` parsing in `main()` before the case dispatch
     (lines 441-499).
   - Resolve via `aitask_project_resolve.sh`; on `STALE`/`NOT_FOUND` die
     with `cd /path/to/<name> && ait projects add` hint.
   - On `RESOLVED:`: `cd "$root"; exec "$root/.aitask-scripts/aitask_query_files.sh" "$@"` (where `"$@"` has `--project <name>` stripped).

3. **New subcommand `task-status`:**
   ```bash
   cmd_task_status() {
       [[ $# -lt 1 ]] && die "task-status requires a task id argument"
       local id
       id=$(strip_prefix "$1")
       # resolve to a task file (parent or child)
       local file
       if [[ "$id" =~ ^[0-9]+_[0-9]+$ ]]; then
           local parent="${BASH_REMATCH[1]}"; local child="${BASH_REMATCH[2]}"
           file=$(ls "$TASK_DIR"/t"${parent}"/t"${parent}"_"${child}"_*.md 2>/dev/null || true)
       elif [[ "$id" =~ ^[0-9]+$ ]]; then
           file=$(ls "$TASK_DIR"/t"${id}"_*.md 2>/dev/null || true)
       fi
       if [[ -z "$file" ]]; then
           # Try archived
           local archived
           archived=$(cmd_archived_task "$id" | head -n 1)
           if [[ "$archived" == ARCHIVED_TASK:* ]]; then
               # Archived tasks are always Done
               echo "STATUS:Done"; return
           fi
           echo "STATUS:NOT_FOUND"; return
       fi
       local status
       status=$(read_task_status "$file")
       echo "STATUS:${status:-NOT_FOUND}"
   }
   ```
   Wire into the `main()` case dispatch as `task-status)`.

4. **`aitask_ls.sh`** — same `--project` argv-prefix in `main()` (the
   re-exec must run before flag-heavy arg parsing; mirror create's
   approach of stripping early).

5. **`aitask_find_by_file.sh`** — same. This script has a flatter
   structure; add the parse loop at the top (after `set -euo pipefail`
   and lib sources, before `target_path="$1"`).

6. **Update `show_help()` in each** to document `--project <name>`.

7. **Whitelist** — verify the helpers are still skill-invokable (the
   `task-status` subcommand may need a whitelist note in
   `aitask_skill_verify.sh` policy file if it adds new dispatch paths).

## Tests

`tests/test_query_files_cross_repo.sh`:
- Synthesize two fake aitasks roots in `tmp/test_query_files_cross_repo/A`
  and `.../B` with minimal `aitasks/metadata/project_config.yaml` declaring
  `project.name: a` and `project.name: b`.
- Set `AITASKS_PROJECTS_INDEX` to a temp registry file with both.
- From inside A's root, exercise every `aitask_query_files.sh` subcommand
  with `--project b` and verify outputs match B's local results.
- Exercise `task-status` for Ready, Implementing, Done (archived), Folded,
  and NOT_FOUND.
- Verify die-with-hint on `--project not_registered`.
- Verify die-with-hint on `--project stale_entry` (registry points at
  a non-existent path).

## Verification

- `bash tests/test_query_files_cross_repo.sh` passes.
- `shellcheck .aitask-scripts/aitask_query_files.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_find_by_file.sh` clean.
- Manual: from `aitasks_mobile`, `./.aitask-scripts/aitask_query_files.sh task-file --project aitasks 832` returns the t832 path in aitasks.
- `./.aitask-scripts/aitask_skill_verify.sh` passes (helpers remain skill-invokable).

## Out of scope (do NOT pull in)

- `aitask_explain_context.sh` (Scope 1b — t832_2).
- `aitask_update.sh` (Scope 1c — t832_7).
- `aitask_revert_analyze.sh`, `aitask_codeagent.sh`, `aitask_skillrun.sh` (stay local).
- TUI changes (t832_8).

## Notes for sibling tasks

- The `task-status` schema (`STATUS:<value>` one-line output) is consumed
  by t832_4 blocking logic and t832_8 board display. Keep stable.
- The re-exec pattern from this task is the template t832_7 mirrors for
  `aitask_update.sh --project`.

## Verification (manual checklist)

- [ ] `--project <registered>` re-execs into the correct project root.
- [ ] `--project <unregistered>` dies with the `cd && ait projects add` hint.
- [ ] `--project <stale>` dies with the stale-path message.
- [ ] `task-status` returns the correct status for each lifecycle state.
- [ ] `task-status NOT_FOUND` is silent (no crash).
- [ ] `aitask_skill_verify.sh` passes.

## Final Implementation Notes

- **Actual work done:** Added `.aitask-scripts/lib/cross_repo_reexec.sh`
  exposing `cross_repo_reexec_or_continue <helper_basename> "$@"`. The
  function scans argv for `--project <name>`, resolves via
  `aitask_project_resolve.sh`, and `exec`s the sibling project's
  same-named helper inside the sibling root (cd'd in) with the
  `--project <name>` pair stripped. On miss it sets
  `CROSS_REPO_FORWARDED_ARGV` and returns so the caller proceeds
  locally. Wired into `aitask_query_files.sh` (top of `main()`),
  `aitask_ls.sh` (top of script — no `main()` in that script), and
  `aitask_find_by_file.sh` (after lib sources, before `target_path`
  parse). Added new `task-status <N|N_M>` subcommand to
  `aitask_query_files.sh` emitting one line
  `STATUS:<Ready|Editing|Implementing|Postponed|Done|Folded|NOT_FOUND>`;
  archived task files fall through to `Done`. New test file
  `tests/test_query_files_cross_repo.sh` exercises sister-stub
  dispatch on all 3 helpers (verifies `--project <name>` is stripped
  before exec) and the full `task-status` lifecycle against a fake
  local aitasks tree — 34 assertions, all pass.
- **Deviations from plan:**
  - Plan step 4 said "same `--project` argv-prefix in `main()`" for
    `aitask_ls.sh`. The script has no `main()` — argv parse is at the
    top level. Re-exec block was inserted at the top (after lib
    `source` and `TASK_DIR=`, before the `if [ $# -eq 0 ]; then
    show_help` check) so an empty-args call still triggers
    `show_help` locally but a `--project <name>` call re-execs into
    the sibling first.
  - Chose the shared-lib path (Plan step 1 option A) rather than
    inlining the ~35-line block at all three call sites. Net effect
    is ~80 lines of lib + 3 × ~8 lines of caller boilerplate vs
    ~105 lines of duplication — and keeps the resolver-error wording
    in one place.
  - Plan step 7 ("whitelist — verify helpers are still skill-
    invokable"): there is no structured whitelist registry under
    `.aitask-scripts/`. `aitask_skill_verify.sh` was run and passes
    (10 templates × 4 agents). No new entry needed anywhere.
- **Issues encountered:**
  - First test run failed `task-status t050 (archived → Done)`.
    Fixture was named `t050_done.md` with a leading zero; the glob
    in `cmd_archived_task` looks for `t50_*.md`. Fixed by renaming
    the fixture to `t50_done.md` — matches the repository's
    no-leading-zero ID convention.
  - Empty-array splat under `set -u`: each caller wraps the
    `set -- "${CROSS_REPO_FORWARDED_ARGV[@]}"` in an
    `if [[ ${#CROSS_REPO_FORWARDED_ARGV[@]} -gt 0 ]]` guard with
    `set --` in the else branch, so a zero-arg invocation still
    works under `set -euo pipefail`.
  - Shellcheck flagged `CROSS_REPO_FORWARDED_ARGV` as SC2034
    (unused) inside the lib because the consumption is cross-script.
    Suppressed with a targeted `# shellcheck disable=SC2034` and an
    explanatory comment.
- **Key decisions:**
  - `task-status` falls through to `cmd_archived_task` for unknown
    active IDs and returns `STATUS:Done` on hit. Folded tasks that
    have been deleted (parent archived) therefore return `Done` —
    acceptable for the t832_4 blocking probe since "folded into
    something that completed" is functionally `Done` from the
    consumer's perspective. Folded tasks still on disk (parent not
    yet archived) return `Folded`, the canonical value.
  - Re-exec scans the full argv for `--project`, not just position
    1 — `aitask_query_files.sh task-file 42 --project sister` and
    `--project sister task-file 42` both work. The test exercises
    only the leading form (matching plan and `aitask_create.sh`
    convention) but the trailing form is intentionally supported.
  - Did NOT touch `aitask_create.sh`'s in-place re-exec block to
    migrate it onto the new lib. `aitask_create.sh` has additional
    validation (`--batch` required, `--parent` forbidden) that the
    generic lib does not perform; folding those branches in would
    inflate the lib API. Possible follow-up only if
    `aitask_update.sh --project` (t832_7) wants the same
    extra-validation hook.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **`task-status` schema is the public stable contract**: one
    line, `STATUS:<value>` where `<value>` is one of `Ready`,
    `Editing`, `Implementing`, `Postponed`, `Done`, `Folded`, or
    `NOT_FOUND`. `task-status N` and `task-status N_M` both
    supported; missing / invalid IDs are silent
    (`STATUS:NOT_FOUND`) rather than crashing. t832_4 consumes this
    verbatim.
  - **Re-exec contract for t832_7** (`aitask_update.sh --project`):
    use the same `cross_repo_reexec_or_continue` lib. If write-side
    needs extra guards (e.g. reject `--project` without `--batch`,
    like create does), add them in the caller AFTER the lib
    returns (i.e. on the local-only path), not inside the lib —
    keep the lib's contract single-purpose.
  - **Library is sourced only by these 3 helpers (and t832_7
    later)**, NOT by `./ait`'s startup chain. Therefore it is
    deliberately omitted from
    `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()`. The
    new test does not use the scaffold; it invokes the real script
    via absolute path against fake CWD trees, which is the right
    pattern for cross-repo dispatch testing.
  - Sibling project `aitasks_mobile/.aitask-scripts/` does not yet
    have this code. Cross-repo dispatch FROM `aitasks` INTO
    `aitasks_mobile` works regardless (the `--project` pair is
    stripped before exec), but `--project aitasks` invocations
    from INSIDE `aitasks_mobile` will fail until that side is
    synced (separate helper-sync task per CLAUDE.md).
