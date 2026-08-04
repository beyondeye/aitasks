---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [backend, shadow]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-31 10:03
updated_at: 2026-07-31 10:03
boardidx: 110592
---

## Origin

Spawned from t1353 during Step 8b review.

## Upstream defects

- `aitasks/t_refresh_codeagent_suite_default_model_expectations.md` — a
  risk-mitigation task file was created with **no numeric id** in its filename,
  so every `TaskCard._parse_filename` consumer silently drops it; the creating
  flow should never emit an id-less task filename.
- `.aitask-scripts/lib/agent_launch_utils.py:1425-1444` —
  `attach_shadow_cleanup_hook` returns `"installed"` / `"existing"` based on a
  synchronous `show-hooks` read, but issues its `set-option` / `set-hook` writes
  through the fire-and-forget `_TMUX.spawn()` (`lib/tmux_exec.py:230`, a bare
  `Popen` that is never waited on), so the returned status can precede the write
  actually landing.

## Diagnostic context

**Defect 1 — id-less task filename.** It is currently making the aggregate
Python suite red. `bash tests/run_all_python_tests.sh` reports
`PYTHON SUITE: FAILED (runner=unittest, exit=1)` with exactly one failure out of
2951:
`test_board_work_report.WorkReportFullColumnUnderSearchTests.test_hidden_cards_still_listed`
(`AssertionError: 154 != 155`).

Chain: the test picks the first populated board column (`unordered`, 155 tasks)
and asserts the work-report dialog's `SelectionList.option_count` equals
`len(get_column_tasks(col_id))`. `action_work_report`
(`.aitask-scripts/board/aitask_board.py:7269-7273`) builds its entries with
`task_num, task_name = TaskCard._parse_filename(task.filename)` and
`if not task_num: continue`. The file above has no `t<N>_` prefix, so it is
skipped — 154 offered vs 155 in the column.

The file was committed on 2026-07-29 (`9e7f18326`,
`ait: Revert t1311 to Ready (risk mitigation pending)`), so the creating flow is
the risk-mitigation "before" task creation path. Note the task file itself is
otherwise well-formed (valid frontmatter, `anchor: 1162`) — only the filename
lacks the id.

**Defect 2 — hook status race.** Surfaced while implementing t1353's live smoke:
its bypass control armed a cleanup hook via `attach_shadow_cleanup_hook`, got
`"installed"` back, and immediately killed the agent process — the `pane-died`
hook had not been written yet, so nothing fired. A standalone raw-tmux repro
confirmed the hook mechanism itself is sound; the race is purely between the
function's return and its own fire-and-forget writes. Benign in production (an
agent does not exit microseconds after its shadow spawns), which is why t1353
worked around it in the test fixture (`wait_hook_armed()` in
`tests/test_monitor_shadow_spawn_live.sh`) rather than changing the helper.

## Suggested fix

**Defect 1:** find the creation path that produced the id-less filename (the
risk-mitigation "before" creation in `risk-mitigation-followup.md` Part 2 /
`aitask_create.sh`), fix it so a task file always carries `t<N>_`, and rename the
existing file to its proper `t<N>_...` form. Consider whether
`_parse_filename`'s silent `continue` should instead surface a warning — a task
that cannot be parsed disappearing from a report is exactly the failure mode
that hid this for two days.

**Defect 2:** either wait on the `set-hook` `Popen` before probing/returning, or
route those two writes through `_TMUX.run()` (which does wait) and downgrade the
return contract's promise. Decide deliberately: `spawn()` was chosen for
non-blocking UI updates, and `attach_shadow_cleanup_hook` already blocks on a
`show-hooks` `run()` anyway, so the non-blocking argument is weak here.
