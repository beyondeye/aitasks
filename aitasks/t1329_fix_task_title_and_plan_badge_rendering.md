---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, monitor]
gates: [risk_evaluated]
anchor: 1310
followup_kind: upstream_defect
created_at: 2026-07-29 13:46
updated_at: 2026-08-13 23:06
boardidx: 88064
---

## Origin

Spawned from t1310 during Step 8b review. All three defects are pre-existing and
were surfaced while building the minimonitor pick-by-number dialog — none is
caused by t1310's change.

## Upstream defects

- `.aitask-scripts/monitor/monitor_core.py:2955-2961` — `TaskInfoCache._resolve`
  extracts the task title by scanning for the first line starting with `# `,
  **without skipping fenced code blocks**. A `#` comment inside a ``` fence
  therefore becomes the task title. Observed live: t1310 renders as
  `t1310: on confirm:` because its description contains `# on confirm:` inside a
  Python code fence. Affects every consumer of `TaskInfo.title` — monitor and
  minimonitor `i`/`I`, the kill-confirm dialog, and the new pick-by-number
  confirm dialog.
- `.aitask-scripts/monitor/monitor_shared.py:264` —
  `TaskDetailDialog.action_toggle_plan` writes its view indicator as
  `f"[bold]t{id}: {title}[/] [{label}]"`. The `[{label}]` is unescaped, so Rich
  parses `[Plan]` / `[Task]` as a markup tag and it never reaches the screen.
  Pressing `p` in the task-detail dialog silently gives no visual confirmation
  of which view is showing. `_showing_plan` does flip, so only the indicator is
  affected.
- Risk-mitigation "before" task creation can emit a task file with **no number**
  in its filename: `aitasks/t_refresh_codeagent_suite_default_model_expectations.md`
  (created 2026-07-29 09:55, committed 10:15 by the t1311 flow as
  `9e7f18326 ait: Revert t1311 to Ready (risk mitigation pending)`). The file is
  still present. The board lists it, but nothing can address it by id.

## Diagnostic context

The first two were found by driving the new `p` flow in a real tmux pane: the
confirm dialog showed `t1310: on confirm:` as the title, and a test asserting
the `[Plan]` badge after pressing `p` failed while `_showing_plan` was correctly
`True`.

The third is the sole cause of a live test failure. `test_board_work_report.
WorkReportFullColumnUnderSearchTests.test_hidden_cards_still_listed` fails with
`AssertionError: 131 != 132`: `TaskManager.get_column_tasks` counts the
un-numbered file, while the work-report screen's `t(\d+(?:_\d+)?)` id extraction
drops it, so the two counts differ by exactly one. Confirmed by enumerating the
column and printing the entry with no parseable id. Reproduced with all of
t1310's source changes stashed out, so it is independent of t1310.

## Suggested fix

- Title extraction: track fenced-code state (``` and ~~~) while scanning and
  ignore `# ` lines inside a fence. Same scan is likely duplicated in the board
  — check `aitask_board.py` before fixing in one place only.
- Plan badge: escape the label, or use a Rich-safe separator (e.g.
  `… [/] \[{label}]` / `— {label}`). Add a render-level assertion, since
  `_showing_plan` flipping is not evidence the badge rendered.
- Un-numbered task file: find where risk-mitigation "before" creation can skip
  numbering, and decide what to do with the existing file (renumber or remove).
  Guard against unparseable ids in the work-report list so a stray file cannot
  break the count.
