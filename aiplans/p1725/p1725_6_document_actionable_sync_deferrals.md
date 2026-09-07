---
Task: t1725_6_document_actionable_sync_deferrals.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_1_*.md, aitasks/t1725/t1725_2_*.md, aitasks/t1725/t1725_3_*.md, aitasks/t1725/t1725_4_*.md, aitasks/t1725/t1725_5_*.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_*_*.md
Base branch: main
Output branch: main
---

# t1725_6 — document actionable sync deferrals

Parent plan: `aiplans/p1725_sync_deferrals_actionable_and_safe_to_continue.md`,
section "Child 6". Depends on t1725_5. Read
`aidocs/framework/documentation_conventions.md` first (current-state prose only;
generic agent wording).

## Steps

1. `website/content/docs/commands/sync.md`: `DEFERRED_FILE:` continuation contract
   and full column list (`sub_reason|task|path|tree_state|holder|email|host|pid|pane|
   pane_state|action`), which columns are percent-encoded, the closed grammars
   (`holder`, `pane_state`), the sub-reason closed set (replacing the "reported on
   stderr rather than in this token" sentence); the three-way rebase rule
   (tracked + local commits / incoming-touched / fast-forward when not ahead); the
   "held by your own session on this host" wording; the flag table rows
   `--commit-for-task`, repeated `--expect-path`, `--require-waiting` and the
   `commit_scope_changed` / `holder_not_waiting` skips (never automatic); a new
   "Wedged worktree" paragraph (workflow pull aborts on conflict — `rebase_conflict`
   vs `rebase_in_progress` hints; writers refuse mid-rebase and what `--abort`
   discards; `ait create`'s "written but NOT committed — do not re-run").
2. `website/content/docs/tuis/syncer/_index.md`: the deferral screen (rows, when the
   commit-on-behalf button appears, the scope confirmation, what a re-opened screen
   means); a row in the modal table; leave the failure-modal paragraph alone.
3. `website/content/docs/tuis/board/reference.md`: a "Sync Deferred" row next to
   "Sync Conflict" (explicit `s` only; background sync stays a toast).
4. `cd website && python3 check_links.py --build`.

## Verification

- `check_links.py --build` passes.
- Every flag / token / column named in the docs exists verbatim in
  `./.aitask-scripts/aitask_sync.sh --help` and `sync_action_runner.py` (grep each).
- `grep -rn "held by other sessions" website/content/` returns nothing.

## Step 9

Standard post-implementation (`documentation: … (t1725_6)`); this is the last child,
so the parent t1725 is archived after it.
