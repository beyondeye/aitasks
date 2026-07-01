---
Task: t1102_board_delete_check_unfold_return_codes.md
Worktree: (none - profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Board Delete Checks Unfold Return Codes

## Context

Task `t1102` fixes a board hard-delete robustness bug in
`.aitask-scripts/board/aitask_board.py`. When deleting a folded primary task,
`KanbanApp._do_delete()` revives each folded task by running
`.aitask-scripts/aitask_update.sh --batch <fid> --status Ready --folded-into ""`,
but currently ignores the subprocess return code. If one unfold update fails, the
delete can still proceed to remove the primary task, leaving the folded task in a
bad state with `status: Folded` and `folded_into` pointing at the deleted
primary.

The desired behavior is fail-closed, matching the existing attachment decref
guard just above this code path: on any unfold helper failure, notify the user
and return before `git rm` or the delete commit.

## Implementation Steps

1. Add a small unfold helper in `.aitask-scripts/board/aitask_board.py`.
   - Place it near `_decref_doomed_attachments()` so both pre-delete guards are
     easy to audit together.
   - Suggested signature:

     ```python
     def _unfold_deleted_primary_children(self, folded_ids):
         for fid_str in folded_ids or []:
             try:
                 result = subprocess.run(
                     ["./.aitask-scripts/aitask_update.sh", "--batch", fid_str,
                      "--status", "Ready", "--folded-into", ""],
                     capture_output=True, text=True, timeout=10
                 )
             except subprocess.TimeoutExpired:
                 return False, f"unfold t{fid_str} timed out"
             if result.returncode != 0:
                 err = result.stderr.strip() or result.stdout.strip() or "unknown error"
                 return False, f"unfold t{fid_str} failed: {err}"
         return True, ""
     ```

   - Keep the return shape aligned with `_decref_doomed_attachments()`:
     `(ok: bool, msg: str)`.
   - Do not introduce a new abstraction outside `KanbanApp`; the behavior is
     private to the board delete flow.

2. Replace the fire-and-forget unfold loop in `KanbanApp._do_delete()`.
   - Immediately after the attachment decref block, call the new helper:

     ```python
     ok, err = self._unfold_deleted_primary_children(folded_ids)
     if not ok:
         self.app.call_from_thread(
             self.notify,
             f"Folded-task unfold failed - task NOT deleted (retry): {err}",
             severity="error",
         )
         return
     ```

   - Preserve the ordering:
     1. `_decref_doomed_attachments(...)`
     2. `_unfold_deleted_primary_children(...)`
     3. child-parent `--remove-child` update
     4. `git rm`
     5. delete commit
   - The early return must happen before the child-parent update, every `git rm`,
     empty-directory cleanup, and delete commit.
   - Use ASCII punctuation in the new notification to match this file's mixed
     but mostly ASCII operational messages.

3. Add regression coverage to `tests/test_board_decref_doomed_attachments.py`.
   - Reuse the existing `_load_board_module()` and `_FakeProc` helpers.
   - Add an `UnfoldStepContractTests` class next to `DecrefStepContractTests`.
   - Test successful command construction:
     - Patch `board.subprocess.run` to return `_FakeProc(returncode=0)`.
     - Call `board.KanbanApp._unfold_deleted_primary_children(app, ["31", "32"])`
       on a simple stand-in object.
     - Assert `(True, "")`.
     - Assert two helper calls were made and each command contains:
       `.aitask-scripts/aitask_update.sh`, `--batch`, the folded id,
       `--status`, `Ready`, `--folded-into`, and `""`.
   - Test non-zero return fails closed:
     - Patch `subprocess.run` to return `_FakeProc(returncode=1, stderr="write failed")`.
     - Assert `(False, "...write failed...")`.
     - This directly verifies the return-code contract that gates `_do_delete()`.
   - Test timeout fails closed:
     - Patch `subprocess.run` to raise `board.subprocess.TimeoutExpired(cmd, 10)`.
     - Assert `(False, "...timed out...")`.
   - Optional if the helper is simple enough: test empty `folded_ids` returns
     `(True, "")` and does not call subprocess.

4. Add a focused `_do_delete()` early-return test only if the helper-level test
   leaves the delete gate unproven.
   - A lightweight option is to instantiate a minimal `SimpleNamespace` with:
     `_decref_doomed_attachments` returning `(True, "")`,
     `_unfold_deleted_primary_children` returning `(False, "write failed")`,
     `app.call_from_thread` executing its callable immediately,
     `notify` recording messages, and `pop_screen` as a no-op.
   - Patch `board._task_git_cmd` or `board.subprocess.run` so any `git rm` /
     commit attempt is recorded.
   - Call `board.KanbanApp._do_delete.__wrapped__(fake_app, "30", [task_path], ["31"], None)`
     if the Textual `@work` wrapper exposes `__wrapped__`; otherwise skip this
     test and keep helper-level tests only.
   - Assert no `git rm` / commit commands are attempted. Do not fight Textual's
     worker decorator if this becomes brittle; the helper test plus the direct
     `_do_delete()` call site change is enough for this low-effort task.

5. Run the targeted test.

   ```bash
   python3 -m pytest tests/test_board_decref_doomed_attachments.py -v
   ```

6. Run a broader board smoke subset if the targeted test passes.

   ```bash
   python3 -m pytest \
     tests/test_board_decref_doomed_attachments.py \
     tests/test_board_archived_relation_lookup.py \
     tests/test_task_dir_module_constants.py \
     -v
   ```

7. Update this plan after implementation.
   - Mark completed steps.
   - Record any deviation from the helper approach.
   - Note the exact test commands and results.

8. Step 9 post-implementation handling.
   - After code and tests pass, follow the workflow's Step 8 review and Step 9
     post-implementation flow.
   - Ensure the task gate state includes `risk_evaluated`.
   - Merge/commit/archive according to the active workflow prompts.

## Verification

- `python3 -m pytest tests/test_board_decref_doomed_attachments.py -v`
- `python3 -m pytest tests/test_board_decref_doomed_attachments.py tests/test_board_archived_relation_lookup.py tests/test_task_dir_module_constants.py -v`

Expected result: the new unfold tests fail before the code change because the
return-code contract does not exist, then pass after the helper is introduced and
`_do_delete()` aborts on a failed unfold update.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
