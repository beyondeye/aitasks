---
priority: medium
effort: low
depends: [t832_1, t832_3]
issue_type: feature
status: Implementing
labels: [cross_repo, xdeps]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 18:27
updated_at: 2026-05-27 23:13
---

## Context

Part of t832 brainstorm decomposition. Extends `aitask_ls.sh`'s blocking
logic so tasks with `xdeps` / `xdeprepo` are correctly flagged as blocked
when the cross-repo dep is not Done.

**Satisfied semantics (user-confirmed):** `Done` only. Mirrors local
`depends:` exactly — `Folded` and `Postponed` do NOT count as satisfied.

## Key Files to Modify

- `.aitask-scripts/aitask_ls.sh:256-281` — `calculate_blocked_status()`:
  add a cross-repo dep loop after the existing in-repo `depends` loop.
- `.aitask-scripts/aitask_ls.sh:287-298` — `parse_task_metadata()`:
  reset `xdeps_text` and `xdeprepo_text` to defaults.

## Reference Files for Patterns

- `.aitask-scripts/aitask_ls.sh:256-281` — existing `depends` blocking
  loop (the template to mirror).
- `.aitask-scripts/aitask_query_files.sh task-status --project <name> <id>`
  (introduced by t832_1) — cheap cross-repo status probe.
- `.aitask-scripts/aitask_project_resolve.sh` — die-with-hint on
  STALE / NOT_FOUND, caught here for the UNREACHABLE display path.

## Implementation Plan

Insert after the existing `depends` loop in `calculate_blocked_status()`:

```bash
# Check cross-repo dependencies (xdeps + xdeprepo)
if [[ -n "$xdeps_text" && -n "$xdeprepo_text" ]]; then
    IFS=',' read -ra XDEPS <<< "$xdeps_text"
    for xdep_id in "${XDEPS[@]}"; do
        local xdep_status
        xdep_status=$("$SCRIPT_DIR/aitask_query_files.sh" task-status \
            --project "$xdeprepo_text" "$xdep_id" 2>/dev/null | \
            sed 's/^STATUS://')
        if [[ -z "$xdep_status" || "$xdep_status" == "NOT_FOUND" ]]; then
            blocked=1
            blocking_info="${blocking_info:+$blocking_info,}${xdeprepo_text}#${xdep_id} (UNREACHABLE)"
            break
        elif [[ "$xdep_status" != "Done" ]]; then
            blocked=1
            blocking_info="${blocking_info:+$blocking_info,}${xdeprepo_text}#${xdep_id}"
            break
        fi
    done
fi
```

The 2>/dev/null suppresses the die-with-hint message; the empty/NOT_FOUND
detection takes over to display UNREACHABLE without crashing the lister.

## Verification Steps

- New test file: `tests/test_xdeps_blocking.sh`
  - Two fake projects A and B.
  - Task in A with `xdeps: [1]` `xdeprepo: B`:
    - When B's t1 is Ready → A's task is blocked.
    - When B's t1 is Implementing → A's task is blocked.
    - When B's t1 is Postponed → A's task is blocked (NOT satisfied).
    - When B's t1 is Folded → A's task is blocked (NOT satisfied).
    - When B's t1 is Done → A's task is unblocked.
    - When B is not registered (NOT_FOUND) → A's task is blocked with UNREACHABLE.
    - When B's path is stale → A's task is blocked with UNREACHABLE.
- `shellcheck .aitask-scripts/aitask_ls.sh` clean.

## Notes for sibling tasks

- t832_8 (board TUI) reads `blocked` + `blocking_info` from this output
  to surface "blocked by cross-repo" distinctly from "blocked by local".
  Keep `blocking_info` formatted as `<repo>#<id>` (with optional
  ` (UNREACHABLE)` suffix) so the board can pattern-match.

## Out of scope

- TUI surfacing of cross-repo blocking (owned by t832_8).
- Cross-repo blocking in `aitask_pick_own.sh` — the existing pick flow
  uses `is_task_uncompleted()` on local IDs; cross-repo blocking is
  already enforced at the `aitask_ls.sh` display layer, which is what
  pick consumes for the task list. If `aitask_pick_own.sh` ever calls
  `is_task_uncompleted()` directly on a cross-repo ID, add a thin
  wrapper then; not needed for v1.
- Monitor TUI surfacing (deferred follow-up).

See parent plan §t832_4 for the full design context.
