---
task_id: 1097
task_file: aitasks/t1097_manual_verification_decref_attachments_on_task_harddelete_fo.md
created_at: 2026-07-01 12:21
agent: codex
plan_type: manual_verification_auto
---

# Manual Verification Auto-Execution Log for t1097

## Summary

Verified the board hard-delete attachment decref flow for t1097 using focused
regression tests plus a disposable scratch repository that invoked
`.aitask-scripts/board/aitask_board.py`'s delete worker. The scratch verifier
was also run from a detached tmux session and exited 0.

## Commands Run

```bash
bash tests/test_attach_task_delete_decref.sh
python3 tests/test_board_decref_doomed_attachments.py -v
python3 /tmp/t1097_board_worker_verify.py
tmux new-session -d -s t1097_verify 'cd /home/ddt/Work/aitasks; python3 /tmp/t1097_board_worker_verify.py > /tmp/t1097_tmux_verify.out 2>&1; printf "%s" "$?" > /tmp/t1097_tmux_verify.rc; cat /tmp/t1097_tmux_verify.out; printf "\nTMUX_DONE:%s\n" "$(cat /tmp/t1097_tmux_verify.rc)"; sleep 10'
sed -n '1,120p' /tmp/t1097_tmux_verify.out
cat /tmp/t1097_tmux_verify.rc
```

## Execution Log

### Item 1

- Item text: In `ait board`: attach a file to a task, delete the task, then run `ait attach gc` past the grace window; confirm the blob and meta are reclaimed.
- Approach: Scratch git repo with board delete worker, seeded attachment via `aitask_attach.sh add`, then `gc` with `attachments_gc_grace: 0`.
- Evidence: Single-task hard delete removed the sole metadata ref; `gc` removed both `attachments/blobs/<hash>` and `attachments/meta/<hash>.json`.
- Verdict: pass.

### Item 2

- Item text: In `ait board`: attach files to a parent and its children, delete the parent; confirm cascade decref releases every doomed task's attachments and `gc` reclaims them.
- Approach: Scratch parent with two doomed children and one surviving sibling, plus existing integration test coverage.
- Evidence: Parent-only, child-only, and parent-child shared doomed refs were empty after board delete; surviving sibling ref remained; `gc` reclaimed only doomed blobs.
- Verdict: pass.

### Item 3

- Item text: In `ait board`: with a shared blob referenced by a surviving task, delete one referencing task; confirm the blob is retained and `gc` does not reclaim it.
- Approach: Scratch repo with two tasks sharing identical attachment bytes.
- Evidence: Deleting task `t11` left the shared blob metadata refs as `12`; `gc` retained the blob.
- Verdict: pass.

### Item 4

- Item text: Force a decref-helper failure during a board delete; confirm the task is not deleted and the error notification appears.
- Approach: Scratch repo with a failing `.git/hooks/pre-commit` so `decref-deleted` cannot commit its ledger update.
- Evidence: Board delete returned before `git rm`; task `t40_fail.md` remained; attachment refs were restored; captured notification contained `Attachment decref failed` and `task NOT deleted`.
- Verdict: pass.

### Item 5

- Item text: Delete a primary that has a folded task sharing an attachment hash; confirm the folded-origin blob is retained and the revived task still resolves its attachment.
- Approach: Scratch primary `t30` and folded task `t31`, with fold-time ownership simulated by moving the folded hash ref to the primary before delete.
- Evidence: Board delete passed `t31` as a protected task; helper rebound the folded-origin hash to `31`; `t31` was revived to `Ready`; local backend bytes remained present and readable; primary-only blob was reclaimed.
- Verdict: pass.

### Item 6

- Item text: Verify `.aitask-scripts/board/aitask_board.py` delete flow end-to-end in tmux.
- Approach: Ran `/tmp/t1097_board_worker_verify.py` inside a detached tmux session.
- Evidence: `/tmp/t1097_tmux_verify.rc` contained `0`; `/tmp/t1097_tmux_verify.out` reported all five scratch board delete scenarios passed.
- Verdict: pass.

## Test Output

```text
test_attach_task_delete_decref.sh: 45 passed, 0 failed, 45 total

test_no_doomed_ids_skips_subprocess ... ok
test_nonzero_exit_fails_closed ... ok
test_success_builds_command_with_protect_task ... ok
test_extracts_parent_and_children_excludes_plans_and_strays ... ok
test_no_task_files_yields_empty ... ok

Ran 5 tests in 0.237s
OK

PASS item1: board delete removed sole ref and gc reclaimed blob+meta
PASS item2: board parent cascade released doomed attachments and gc reclaimed them
PASS item3: shared blob retained survivor ref and survived gc
PASS item4: decref commit failure aborted board delete and showed notification
PASS item5: folded-origin blob rebound to revived task and still resolves
SUMMARY: board delete worker scratch verification passed
```

## Cleanup

- Scratch repositories were created under `/tmp/t1097_board_verify_*` and removed by the verifier.
- Temporary evidence files remain under `/tmp/t1097_tmux_verify.out` and `/tmp/t1097_tmux_verify.rc`.
- No product code was changed.
