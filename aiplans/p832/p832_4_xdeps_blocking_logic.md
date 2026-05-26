---
Task: t832_4_xdeps_blocking_logic.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_4_xdeps_blocking_logic
Branch: aitask/t832_4_xdeps_blocking_logic
Base branch: main
---

# Plan: xdeps blocking logic

See parent plan §t832_4. Depends on t832_1 (cross-repo `task-status`
probe) and t832_3 (xdeps parser).

## Goal

Extend `calculate_blocked_status()` so tasks with unmet cross-repo
deps are flagged as blocked. **`Done` only** is satisfied (user-confirmed).

## Implementation steps

1. **`aitask_ls.sh:256-281`** — after the existing in-repo `depends`
   loop, append the cross-repo loop (see task body for the bash
   snippet). Key points:
   - Reads `xdeps_text` and `xdeprepo_text` populated by t832_3.
   - Calls `aitask_query_files.sh task-status --project <repo> <id>`
     (from t832_1) with `2>/dev/null` to suppress die-with-hint output.
   - Empty result or `NOT_FOUND` → blocked + `UNREACHABLE` marker
     (resolver unreachable: STALE registry or project not registered).
   - Any status other than `Done` → blocked.
   - `Done` → satisfied.

2. **`blocking_info` formatting:** prepend `<repo>#<id>` (e.g.,
   `aitasks_mobile#42`) so the board (t832_8) can distinguish cross-repo
   from local with a simple substring check for `#`.

3. **Reset block:** add `xdeps_text=""` and `xdeprepo_text=""` to the
   defaults in `parse_task_metadata()` (already covered by t832_3 if
   that landed first; verify and re-add if needed).

## Tests

`tests/test_xdeps_blocking.sh`:
- Two fake projects A and B.
- Task in A with `xdeps: [1]` `xdeprepo: B`.
- Iterate over B/t1's status: Ready, Editing, Implementing, Postponed,
  Done, Folded. Assert blocked=1 for all except Done.
- Unregister B; assert blocked=1 with `UNREACHABLE`.
- Re-register B at a stale path; assert blocked=1 with `UNREACHABLE`.
- Sanity: a task with only in-repo `depends:` is unaffected by this
  change.

## Verification

- `bash tests/test_xdeps_blocking.sh` passes.
- `shellcheck .aitask-scripts/aitask_ls.sh` clean.
- Manual: `./.aitask-scripts/aitask_ls.sh -v 5` against a real cross-repo
  setup correctly flags blocked tasks.

## Notes for sibling tasks

- `blocking_info` format `<repo>#<id>` (with optional ` (UNREACHABLE)`
  suffix) is read by t832_8 board to render the "blocked by cross-repo"
  indicator.

## Out of scope

- TUI display of the new blocked state (t832_8).
- Cross-repo blocking in `aitask_pick_own.sh` (the existing pick flow
  consumes `aitask_ls.sh`'s output, so it inherits this for free; no
  separate plumbing needed for v1).
- Monitor TUI cross-repo surfacing (deferred follow-up).

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)
