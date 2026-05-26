---
Task: t832_1_cross_repo_retrieval_reexec_trio.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_1_cross_repo_retrieval_reexec_trio
Branch: aitask/t832_1_cross_repo_retrieval_reexec_trio
Base branch: main
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

(To be filled by the implementing agent during/after execution.)
