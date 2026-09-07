---
priority: medium
effort: medium
depends: [t1725_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1725_1, 1725_2, 1725_3, 1725_4, 1725_5, 1725_6]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-07 16:44
updated_at: 2026-09-07 16:44
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1725_1] On a branch-mode checkout, force a data-branch conflict (edit the same frontmatter line locally, uncommitted-then-committed, and on origin from another clone), then run `./.aitask-scripts/aitask_pick_own.sh --sync`: it prints `SYNC_FAILED:rebase_conflict`, `ls .git/worktrees/*/rebase-merge` shows nothing, and an immediate `./ait git commit` of a new task file succeeds.
- [ ] [t1725_1] With a rebase deliberately left in progress (`./ait git rebase` stopped by hand), the same `--sync` reports `rebase_in_progress`, does NOT abort it, and the hint names what `./ait git rebase --abort` discards.
- [ ] [t1725_2] With the data worktree mid-rebase, `./.aitask-scripts/aitask_update.sh --batch <id> --priority low` refuses with the "retry in a few seconds / rebase --abort" message and leaves the file byte-identical; after `./ait git rebase --abort` the same update succeeds.
- [ ] [t1725_2] With the data worktree mid-rebase, `./.aitask-scripts/aitask_create.sh --batch --commit --name x --priority low --effort low --type chore --labels x --desc x` exits non-zero and `./.aitask-scripts/aitask_claim_id.sh --peek` is unchanged; with a planted `index.lock` instead, create prints the path, warns "NOT committed", and the next `./ait sync` commits the file under its own task id — no duplicate id appears.
- [ ] [t1725_3] With a plan file left UNTRACKED by a live-locked task of yours and origin ahead by one unrelated commit, `./ait sync --batch` does NOT defer: it pulls and pushes, and the untracked file is still there afterwards.
- [ ] [t1725_3] Same position but the task file MODIFIED (tracked): `./ait sync --batch` prints `DEFERRED:protected_dirty:…` followed by one `DEFERRED_FILE:live_lock|<task>|<path>|tracked|self|<your email, %40-encoded>|<host>|<pid>|…` line per dirty file, and interactive `./ait sync` prints the "held by YOUR OWN live session on this host … ./ait sync --commit-for-task <id>" line on stderr.
- [ ] [t1725_3] With no local commits ahead and one tracked dirty file that origin's new commit does not touch, `./ait sync --batch` fast-forwards (`PULLED`) instead of deferring.
- [ ] [t1725_3] `./ait sync --commit-for-task <id>` for a task held by your own live session commits that task's group with the "committed as they stand now" warning; the same flag for a task locked by another email is refused on stderr and the run still defers.
- [ ] [t1725_4] With a `claude` pane of yours parked on an AskUserQuestion and holding a modified task file, the `DEFERRED_FILE:` line carries the pane target (`<session>:@<win>.%<pane>`) and `pane_state=waiting_claude_askuserquestion`; after answering the prompt and re-running sync, `pane_state` reads `active`.
- [ ] [t1725_4] `./.aitask-scripts/aitask_live_endpoint.sh <held task id>` still resolves `LIVE_PANE:…` (the extracted `ait_tmux_pane_for_pid` helper did not change its answer), and `bash tests/test_no_raw_tmux.sh` passes.
- [ ] [t1725_5] In `ait syncer`, press `s` on the `aitask-data` row under the modified-tracked deferral above: the "Sync deferred" modal lists task id, path, `you · pid · pane · waiting_…`, and the clearing action; the toast still appears and no failure screen / agent-launch offer is armed.
- [ ] [t1725_5] In that modal the "Commit t<id> on my behalf" button is present only while the holder pane is on a prompt; answer the prompt, re-sync: the row now says "session is active — …" with no button.
- [ ] [t1725_5] Press the button while waiting: the confirmation lists every path of that task's group; confirm → the group is committed and the modal closes (or re-opens with `holder_not_waiting` / `commit_scope_changed` rows if the session moved or the group grew in between).
- [ ] [t1725_5] In `ait board`, `s` shows the same modal; a background `sync_on_refresh` sync shows only the toast.
- [ ] [t1725_6] `website/content/docs/commands/sync.md` documents the `DEFERRED_FILE:` columns, the three-way rebase rule, `--commit-for-task` / `--expect-path` / `--require-waiting`, and the "Wedged worktree" paragraph; `cd website && python3 check_links.py --build` passes; `grep -rn "held by other sessions" website/content/` is empty.
