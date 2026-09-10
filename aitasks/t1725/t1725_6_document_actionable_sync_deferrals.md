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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1725_1** id=2026-09-08T09:47:48Z.237a1fff328cf20d0c32a9a3 from=t1725_1 from_verified=yes at=2026-09-08T09:47:48Z base=92650b0938449d14d76d8a13eba121b99a770f9f base_branch=main dirty=yes host=omg16
>
> | The documented sync reason set is now three codes out of date.
> | 
> | `website/content/docs/commands/sync.md` presents the `FAILED:<reason>:<count>`
> | reason set as closed, in two places:
> | 
> | - `:199` — the batch-output table row enumerating `dirty_worktree`,
> |   `rebase_conflict`, `no_upstream`, `remote_unreachable`, `diverged`, `unknown`
> | - `:181` — the prose list above it ("a dirty data worktree blocking the rebase
> |   fallback, a rebase stopped on conflicts, an unreachable remote, and a remote
> |   that has diverged")
> | 
> | t1725_1 added three codes to `_task_push_classify` / `_task_push_reason_hint` in
> | `lib/task_utils.sh`:
> | 
> | - `rebase_in_progress` — a rebase is in progress that this pull did not start (or
> |   whose abort failed); the hint offers `./ait git rebase --abort` / `--continue`
> |   and states what `--abort` discards
> | - `data_midop` — the data worktree is mid-merge / cherry-pick / revert / bisect;
> |   the hint points at `./ait git-health` and the matching `--abort`, and
> |   deliberately never says "rebase"
> | - `pull_locked` — another session holds the data-worktree pull lock, so no pull
> |   was attempted and nothing changed
> | 
> | Also changed, not just added: **`rebase_conflict`'s meaning and its hint.** A
> | conflicted pull now aborts itself, so the code means "the rebase is gone and the
> | two sides still diverge", and the hint no longer advertises
> | `./ait git rebase --abort` — it says the rebase "was aborted (nothing left in
> | progress)" and points at `ait syncer` / `./ait sync`. Any doc prose describing
> | `rebase_conflict` as "a rebase stopped on conflicts" that the user must recover
> | from is now wrong.
> | 
> | t1725_1 deliberately updated only the code-side contract comment in
> | `aitask_pick_own.sh` (~35-37) and left the website to you.
> | 
> | Advisory only; verify the line numbers and the current hint strings in
> | `lib/task_utils.sh` before writing.

> **✉ note:t1725_2** id=2026-09-09T06:59:47Z.4fa3f9eb9da681f2c0813770 from=t1725_2 from_verified=yes at=2026-09-09T06:59:47Z base=aed61dcbc65a563d0f0f2663af2825c5d1e19605 base_branch=main dirty=yes host=omg16
>
> | A second guard now honors `AIT_GIT_SKIP_STATE_CHECK`, and it has its own
> | user-visible refusal message — relevant to the sync/docs surface you own.
> | 
> | t1725_2 added `assert_task_data_writable()` in `lib/task_utils.sh`. It is a
> | *pre-write* guard (the existing `assert_data_worktree_clean` fires at commit
> | time), and it now sits at 16 sites across 9 task-data writers: update, create,
> | note, gate, archive, plan_externalize, verification_followup, zip_old,
> | migrate_archives.
> | 
> | Three things that may touch documentation:
> | 
> | 1. `website/content/docs/commands/sync.md:235` documents
> |    `AIT_GIT_SKIP_STATE_CHECK=1` as bypassing "this check" (singular). Two guards
> |    honor it now, so the wording may want to be plural — or scoped, if the doc
> |    means only the commit guard.
> | 
> | 2. The new refusal is a failure mode a user can hit without running sync at all:
> |    any `ait update` / `ait create` / `ait note` / `ait gate` on a wedged data
> |    worktree now refuses up front with "Data worktree (.aitask-data) is
> |    mid-<state>: the checked-out task files are not the branch tip...". Whether
> |    that belongs in user docs is your call — it is a refusal, not a deferral, so
> |    it may sit outside the deferral vocabulary you are documenting.
> | 
> | 3. Deliberately NOT guarded, in case a doc claims otherwise: drafts under
> |    `aitasks/new/` (gitignored, never committed — the one path that is supposed to
> |    keep working while the worktree is broken), `--dry-run` on archive / zip_old /
> |    migrate_archives, the recovery and quarantine paths in sync, and four
> |    metadata-only writers (pick_own, usage_update, verified_update, add_model).
> | 
> | Advisory only, and it is a claim about the tree as of this note's base SHA —
> | verify against the current source before documenting any of it. Full record in
> | `aiplans/p1725/p1725_2_*.md`.

> **✉ note:t1731** id=2026-09-10T18:09:24Z.ee0d0b9d92e841a49d49f222 from=t1731 from_verified=yes at=2026-09-10T18:09:24Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | t1731 landed (commit e2f12c499) and changed the page your deferral docs build on. Advisory; the claims below are dated by that commit.
> | 
> | website/content/docs/commands/sync.md now:
> | - has a `MERGED` row in the batch-output table;
> | - restates the "Skipped files can block the later rebase" paragraph as current behavior. When skipped files block the rebase, sync first tries two ways that touch no skipped file: a fast-forward when the local branch has no commits of its own, and otherwise a merge commit that is pushed and reported as `MERGED`. The merge is used only when the two sides changed different files, git merges them cleanly, and the merge writes no skipped or ignored file. Otherwise the run reports `DEFERRED:protected_dirty`.
> | - carries a user-decided sentence: re-running `ait sync` is a recovery attempt, not a guarantee — when both sides changed the same file it keeps deferring until the owning session commits or the overlap is resolved by hand.
> | 
> | Two things worth knowing before you write:
> | - the `./ait git` convergence hint ("reconcile with 'ait syncer' / './ait sync'") in lib/task_utils.sh was deliberately left unchanged and stays fast-forward-only (a t1731 decision), so docs should not describe that hint as merging;
> | - a diverged run that still defers now prints `sync: Guarded merge not possible (<slug>): <detail>` on stderr, naming the refusing guard.

> **✉ note:t1647_6** id=2026-09-10T18:36:54Z.dca6b7e48e88ada0d3cec5d1 from=t1647_6 at=2026-09-10T18:36:54Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the overlapping
> | task, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA; `~` line numbers are
> | approximate. Verify before acting. This adds to the t1725_1 / t1725_2 / t1731
> | notes already in your inbox and does not repeat them.
> | 
> | 1. tuis/syncer/_index.md has no modal table. Its modal prose is § Failure
> |    handling (~324-329) plus the `a` key rows (~125, ~312) — that is where the
> |    deferral screen goes.
> | 
> | 2. Use the code's actual wording: "held by YOUR OWN live session on this host"
> |    (aitask_sync.sh ~829).
> | 
> | 3. sync.md ~248-251 already says a conflicted pull aborts "so nothing is left in
> |    progress"; the new "Wedged worktree" paragraph should not restate it. ~240
> |    still says "a stopped rebase".
> | 
> | 4. Current positions in commands/sync.md: reason table ~54-58, stderr sentence
> |    ~60, Auto-commit policy ~64-107, flag table ~94-98; ~92 says "Three flags"
> |    (becomes six). The tracked/untracked blocking rule is still new (no
> |    "untracked" hit); the fast-forward case is already there via t1731.
> | 
> | 5. SHARED: t1647_6 adds four trail rows to tuis/board/reference.md § Modal
> |    Dialogs Reference (~655-680) — different rows, adjacent edit. t1243_13 adds
> |    a boardgroup row to sync.md § Merge Rules — different section.
