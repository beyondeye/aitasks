# `file_references` flow: create-time auto-merge and the board → codebrowser handoff

Contributor notes for the two code paths behind the "Creating Tasks from Code"
workflow. The user-facing behaviour is documented on the site:
`commands/task-management.md` ("Folding tasks that reference the same files"),
`development/task-format.md` (the `file_references` row and "Finding tasks by
file reference"), `tuis/codebrowser/reference.md` ("Creating a task from the
viewer", "Opening a file at a line range") and `tuis/board/reference.md`
("Opening file references"). This page records only how the code does it.

## Auto-merge in `aitask_create.sh`

`run_auto_merge_if_needed <new_id> <new_file>` runs after the creation commit at
each of the four commit sites: `finalize_draft` (child and parent) and the
`--batch --commit` paths (child and parent). The interactive "Finalize now"
goes through `finalize_draft`, so it is covered too. Each call is guarded by
`$committed`, so a failed creation commit skips it. (The function's header
comment still says it is only invoked from the `--batch --commit` paths; the
`finalize_draft` call sites make that out of date.)

1. It reads the new task's `file_references` with `get_file_references`. A
   non-zero status skips auto-merge with a warning, never "no refs".
2. It collects the distinct path parts (`${entry%%:*}`) and calls
   `aitask_find_by_file.sh <path>` once per path, unioning the `TASK:` lines
   by id and dropping the new task's own id. The status filter
   (`Ready`/`Editing`) lives in `aitask_find_by_file.sh`'s `is_candidate`.
3. Prompt: only when `BATCH_AUTO_MERGE` is not already true, `BATCH_MODE` is not
   true and stdin is a terminal (`-t 0`). It is an `fzf` choice between
   "Yes, fold them into this task" and "No, keep separate"; Yes sets
   `BATCH_AUTO_MERGE=true`.
4. Without auto-merge it prints the candidate list as warnings and returns.
5. With auto-merge it runs the fold chain:
   - `aitask_fold_validate.sh --exclude-self <new_id> <candidate_ids...>`. The
     validator emits `VALID:<id>:<path>` or `INVALID:<id>:<reason>` with reason
     `not_found`, `is_self`, `has_children` (a parent id with any `*.md` under
     `aitasks/t<id>/`) or `status_<status>` (anything but `Ready`/`Editing`),
     and always exits 0. Each `INVALID` becomes an "Auto-merge: skipping"
     warning.
   - `aitask_fold_content.sh <new_file> <valid_files...> | aitask_update.sh
     --batch <new_id> --desc-file - --silent` merges the bodies.
   - `aitask_fold_mark.sh --commit-mode fresh <new_id> <valid_ids...>` sets
     `status: Folded` and `folded_into`, records `folded_tasks`, follows
     transitive folds, and commits. Its `file_references` union
     (`union_file_references`, primary first, then folded and transitive files
     in argument order, exact-string dedup through `aitask_update.sh`) refuses
     the whole fold if any of those fields cannot be read as a list of path
     strings.

The generic fold sequence and its relations trigger are described in
`task_relations.md` (the `fold` and `created` trigger rows).

## Board File Refs → codebrowser

- The row is `FileReferencesField` in `.aitask-scripts/board/board_detail_screen.py`.
  Enter with one entry calls `_launch_codebrowser(entry)`; with several it pushes
  `FileReferencePickerScreen` first.
- `_launch_codebrowser` takes a ticket from `_CODEBROWSER_FOCUS_ORDER` on the
  event loop and hands off to a `@work(thread=True)` worker, because the
  session lookup and the launch are gateway calls with 5 s timeouts each
  (t1952). `run_if_newest(ticket, …)` makes request order, not worker
  completion order, decide which request acts.
- The session comes from `aitask_board._owned_tmux_session()`
  (`owned_lookup_session(Path.cwd())`), socket-verified and ownership-checked,
  because every project's session has a `codebrowser` window and an ambient
  `#S` could focus another project's.
- `launch_or_focus_codebrowser(session, focus_value, window_name="codebrowser")`
  in `.aitask-scripts/lib/agent_launch_utils.py` first sets the session
  environment variable `AITASK_CODEBROWSER_FOCUS=<entry>`, then either
  `select-window`s an existing window named `codebrowser` or runs
  `new-window -n codebrowser ./ait codebrowser --focus <entry>`. Setting the
  variable first lets both paths see it. It returns `(ok, error)`; the board
  shows the error as a notification.
- The codebrowser (`codebrowser_app.py`) applies `--focus` once after mount and
  polls `AITASK_CODEBROWSER_FOCUS` every second (`_consume_and_apply_focus`),
  clearing the variable when it reads a value. Both the reader and the writer
  go through the tmux gateway (t953). `_parse_focus_value` collapses a
  multi-range spec to `min(starts)..max(ends)`; `_apply_focus_range` clamps to
  the file, puts the cursor on the end line and selects only when start ≠ end.

## Codebrowser `n`

`CodeBrowserApp.action_create_task` builds the `--file-ref` value: a selection
whose start and end differ gives `path:start-end`; anything else gives the whole
file as `path:1-<total lines>` (t567), or the bare path for an empty file; with
no file open the command has no `--file-ref`. The command is shell-quoted
because it runs through a shell in both the tmux and the direct path.
