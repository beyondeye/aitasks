# Task-Data Push Procedure

Publishes the task data this run committed, with one best-effort push. Task data
is the `aitask-data` branch (or the current branch in legacy mode): task files,
plans, `aitasks/metadata/`. Nothing pushes it implicitly, so a step that commits
task data and then closes the session must push it itself. A commit that is
never pushed stays invisible to every other checkout.

Referenced from these session-closing steps, each **after its last task-data
commit and before the Satisfaction Feedback Procedure**:

- `SKILL.md` Step 9, the gate guard's "Defer — keep in-flight" branch (it skips
  the push after archival);
- `planning.md`, the child checkpoint's "Stop here";
- `cross-repo-child-assignment.md` Step 7, "Stop here";
- the "Save for later" branch of the shared post-creation block
  (`.aitask-scripts/skill_templates/_auto_continue_block.j2`: aitask-explore,
  aitask-revert, aitask-fold, aitask-pr-import);
- aitask-qa Step 7, aitask-docs-gap Step 7, aitask-add-model Step 7 and
  aitask-refresh-code-models Step 9.

A step that already runs `./ait git push` after its last commit (normal Step 9
archival, aitask-wrap, aitask-web-merge) does not need this procedure.

## Procedure

Run:

```bash
./ait git push --batch
```

It retries with a pull-rebase on its own, and reports one structured line on
stdout. Read the **last** stdout line and set `task_data_pushed`:

- `PUSHED` → `yes`. The commits are published.
- `NOTHING` → `yes`. Nothing was unpushed. Display nothing.
- `NO_REMOTE` → `yes`. The repository has no remote, so there is nothing to
  publish to. Display nothing.
- `FAILED:<reason>:<n>` → `no`. Warn: "Task data not pushed (`<reason>`, `<n>`
  unpushed commit(s)) — run `./ait git push` to publish it."
- A non-zero exit, or no recognised line → `no`. This happens, for example,
  when the push is refused because the data worktree is mid-rebase. Warn the
  same way, with the first line of stderr as the reason.

Do not retry, and do not let the result change what the calling step does
next. A failed push is a warning, never a failure of the step: the commits are
safe locally, and the next `./ait git push` from any step publishes them.

## Using the result

- **At an exit that shows the `## Stopped` banner** (`workflow-end.md`): when
  `task_data_pushed` is `no`, begin the banner's `next` with
  "`./ait git push` (task data not pushed), then " followed by the exit's own
  `next` text. The banner's other lines are unchanged.
- **Everywhere else:** the warning above is the whole report.
