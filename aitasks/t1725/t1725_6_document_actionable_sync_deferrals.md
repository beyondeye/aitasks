---
priority: medium
effort: low
depends: [t1725_5]
issue_type: documentation
status: Ready
labels: [documentation, syncer]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-09-07 16:40
updated_at: 2026-09-07 16:40
---

## Context

Parent t1725's user-facing documentation deliverable (planning convention: docs are
a first-class child, not a verification afterthought). Depends on **t1725_5**, so
every surface it documents has landed: the abort-safe workflow pull (t1725_1), the
write guard and `create`'s no-retry commit failure (t1725_2), the per-file
`DEFERRED_FILE:` wire record, tree-state rebase gate and the three sync flags
(t1725_3), pane / prompt state (t1725_4), the syncer / board deferral screen
(t1725_5).

Write current-state prose only — no version history in doc bodies
(`aidocs/framework/documentation_conventions.md`). Genericize agent names ("your
coding agent's pane"), except where a literal prompt-pattern name is the value
documented.

## Key files

- `website/content/docs/commands/sync.md` — the batch protocol table (`DEFERRED:` row,
  the closed reason table at ~51-57, "Per-file skip reasons … on stderr" at ~59, the
  auto-commit policy at ~61-99, the flag table at ~88-93)
- `website/content/docs/tuis/syncer/_index.md` — the `s` action (~118-129), the
  failure modal section (~326), "Relationship to `ait sync`" (~347)
- `website/content/docs/tuis/board/reference.md` — the modal table (~678: Sync
  Conflict row)
- `website/check_links.py`

## Implementation plan

1. `commands/sync.md`:
   - the `DEFERRED_FILE:` continuation contract: one line per file **after** the
     status line; the full column list
     `sub_reason|task|path|tree_state|holder|email|host|pid|pane|pane_state|action`;
     which columns are percent-encoded (`|` `%` newline: path, action, email, host,
     pane) and the closed grammars (`holder`: self/other/remote/unverified/none;
     `pane_state`: `waiting_<kind>` / `active` / empty); the sub-reason closed set
     (from `DEFERRED_FILE_REASONS`) replacing the "reported on stderr rather than in
     this token" sentence;
   - the three-way rebase rule: a *tracked* dirty file blocks only when local
     commits need rebasing or an incoming commit touches it; an *untracked* file
     blocks only when an incoming commit creates it; with no local commits the sync
     fast-forwards instead of rebasing;
   - the "held by your own session on this host" wording and what it offers;
   - the flag table: `--commit-for-task`, repeated `--expect-path`,
     `--require-waiting`, and the `commit_scope_changed` / `holder_not_waiting`
     skips; state plainly that the override is never automatic;
   - a new "Wedged worktree" paragraph: the workflow's own pull aborts on conflict
     (nothing left in progress; `rebase_conflict` vs `rebase_in_progress` hints),
     task-data writers refuse while a rebase is in progress (retry after a running
     sync, or `./ait git rebase --abort` — what it discards), and `ait create`'s
     "written but NOT committed — do not re-run" outcome.
2. `tuis/syncer/_index.md`: the deferral screen (what each row shows, when the
   commit-on-behalf button appears, the scope confirmation, what a re-opened screen
   after `holder_not_waiting` / `commit_scope_changed` means); add the row to the
   modal table; keep the failure-modal paragraph as is (a deferral is not a failure).
3. `tuis/board/reference.md`: a "Sync Deferred" row next to "Sync Conflict"
   (explicit `s` only; background sync stays a toast).
4. `cd website && python3 check_links.py --build`.

## Verification

- `check_links.py --build` passes.
- Every flag / token / column named in the docs exists verbatim in
  `aitask_sync.sh --help` and `sync_action_runner.py` (grep each).
- No "held by other sessions" phrase remains anywhere under `website/content/`.
