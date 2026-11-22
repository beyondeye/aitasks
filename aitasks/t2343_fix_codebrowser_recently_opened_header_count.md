---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
created_at: 2026-11-22 11:12
updated_at: 2026-11-22 11:49
---

## Origin

Spawned from t2278_6 during Step 8b review.

## Upstream defect

- `.aitask-scripts/codebrowser/history_list.py:470-489 — the "Recently Opened (N)" header is recomputed only in _update_headers (index load / label filter), so opening a task adds it to the recent list while the header still reads "Recently Opened (0)"`

## Diagnostic context

While recording the codebrowser history docs screenshot (t2278_6), the history
screen opened with `H` on an annotated line of a file showed the task under
"Recently Opened" while the section header read "Recently Opened (0)". The
header is created as `Static("Recently Opened (0)", id="recent_header")`
(`history_list.py:428`) and updated only in `_update_headers()`, which runs on
index load and on label filtering; adding a task to the recent list (opening
it) does not call it. The applied screenshot
`website/static/imgs/codebrowser_task_history.svg` shows the mismatch.

## Suggested fix

Recompute the header whenever the recently-opened list changes (call the
header update after a task is added to / removed from `RecentlyOpenedList`),
and regenerate the `codebrowser_task_history` screenshot
(`website/screenshots.sh replay --scene codebrowser_task_history`).
