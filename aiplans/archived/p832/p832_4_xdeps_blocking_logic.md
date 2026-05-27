---
Task: t832_4_xdeps_blocking_logic.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_4_xdeps_blocking_logic
Branch: aitask/t832_4_xdeps_blocking_logic
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-27 23:40
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

- **Actual work done:**
  - `.aitask-scripts/aitask_ls.sh` `calculate_blocked_status()`: inserted a
    cross-repo `xdeps` loop directly after the in-repo `depends` loop.
    Calls `aitask_query_files.sh task-status --project <repo> <id>` with
    `2>/dev/null` so a resolver die produces empty stdout, which the
    `[[ -z $xdep_status || $xdep_status == NOT_FOUND ]]` branch then
    translates to `Blocked (by <repo>#<id> (UNREACHABLE))`. Non-Done
    statuses produce `Blocked (by <repo>#<id>)`. `Done` falls through
    unblocked. The `t` prefix added by `normalize_task_ids` for `N_M`
    children is stripped from the display string via `${xdep_id#t}`
    so the on-screen format matches CLAUDE.md's canonical
    `aitasks#835_3` notation.
  - `parse_task_metadata` reset of `xdeps_text` / `xdeprepo_text` and
    the `parse_yaml_frontmatter` case arms were already in place from
    t832_3 — no further edits needed there.
  - New test `tests/test_xdeps_blocking.sh` (18 assertions): builds a
    fake local repo plus a fake sister repo (with `.aitask-scripts/`
    symlinked from the project so cross-repo dispatch finds a working
    `aitask_query_files.sh`), registers the sister under
    `AITASKS_PROJECTS_INDEX`, iterates the sister task's status across
    `Ready`/`Editing`/`Implementing`/`Postponed`/`Folded`/`Done`,
    covers UNREACHABLE via unregister and stale path, child `N_M` xdep
    id form, and a local-only `depends:` regression.
  - Regression: `test_xdeps_parser.sh` (5/5), `test_xdeps_validation.sh`
    (14/14), `test_query_files_cross_repo.sh` (34/34) all still pass.
- **Deviations from plan:**
  - **`t` prefix stripped from display id** — added `display_id=${xdep_id#t}`
    after seeing `normalize_task_ids` would emit `sister#t2_3` for
    child IDs. CLAUDE.md's cross-repo notation is `aitasks#835_3`
    (no `t`), so the display now matches. The raw id (with possible
    `t`) is still passed to `task-status`, which accepts both forms
    via `strip_prefix`.
  - **Reset-block plan step (3) skipped** — already landed in t832_3.
- **Issues encountered:**
  - First test draft asserted that local `depends: [99]` with no t99
    task file should still surface `Blocked (by 99)` — but the
    pre-existing `is_task_uncompleted()` semantics treat a missing
    dependency as completed, so the task was Ready. Test fixed by
    creating an `Implementing` t99 sibling, matching the actual
    invariant the existing local-deps loop already enforces.
- **Key decisions:**
  - **Symlink `.aitask-scripts/` into the fake sister** rather than
    stubbing the cross-repo query helper. The blocking branch needs
    real task-status output (Done vs not-Done) and real resolver-die
    behavior on STALE/NOT_FOUND; a stub would have under-tested the
    empty-stdout/UNREACHABLE plumbing. The cost is a single `ln -s`.
  - **`break` after first unmet xdep** — mirrors the local `depends`
    loop's first-match-wins semantics. Aggregating all unmet
    cross-repo deps into `blocking_info` was considered but the
    display string would balloon and t832_8 only needs the first
    `<repo>#<id>` token to render the board hint.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **`blocking_info` format `<repo>#<id>`** is stable; t832_8 should
    pattern-match the `#` to distinguish cross-repo from local
    (`d_text` is overwritten with `blocking_info` on line 303 of
    `aitask_ls.sh`, so the display flows through the existing
    `Blocked (by …)` formatter at line 378 untouched). The display id
    is always the canonical no-`t` form even for child IDs.
  - **Empty stdout from `aitask_query_files.sh --project` indicates
    a resolver failure (STALE or NOT_FOUND)** — both are squashed
    to `UNREACHABLE` here for display compactness. If t832_8 wants
    to differentiate STALE vs missing-registry, that distinction is
    no longer visible past this layer; it would need to be probed
    separately via `aitask_project_resolve.sh`.
