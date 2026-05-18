# Lock Release Procedure

This procedure is referenced from the Task Abort Procedure (see `task-abort.md`) wherever a task lock may need to be released. (Step 9 archival lock releases are handled automatically by `aitask_archive.sh`.)

**When to execute:** After Step 4 has been reached (i.e., a lock may have been acquired). This applies to:
- Task Abort Procedure (task aborted after Step 4)
- Note: Step 9 lock releases are handled by `aitask_archive.sh` and do NOT need this procedure

**Procedure:**

- Release the task lock (best-effort, idempotent):
  ```bash
  ./.aitask-scripts/aitask_lock.sh --unlock <task_num> 2>/dev/null || true
  ```
  This is safe to call even if no lock was acquired (e.g., lock branch not initialized, or lock acquisition was skipped due to infrastructure issues). It succeeds silently in all these cases.

- **For child tasks where the parent is also being archived** (all children complete): also release the parent lock:
  ```bash
  ./.aitask-scripts/aitask_lock.sh --unlock <parent_task_num> 2>/dev/null || true
  ```
