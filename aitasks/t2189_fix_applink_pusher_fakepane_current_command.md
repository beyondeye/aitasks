---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [applink, monitor]
assigned_to: dario-e@beyond-eye.com
anchor: 2034
followup_kind: upstream_defect
created_at: 2026-11-03 22:42
updated_at: 2026-11-07 22:25
---

## Origin

Spawned from t2034_2 during Step 8b review.

## Upstream defect

- `tests/test_applink_pusher.sh:812` — `FakePane` lacks `current_command`, so the
  `capture_pane_async` case crashes in `monitor_core.TmuxMonitor.capture_pane_async`
  (`agent_key_from_pane(pane.current_command, pane.pane_pid, …)`); the script exits 1
  after 98 `ok` checks, so every check after that point never runs. Pre-existing since
  t1467 (`0fb8ea25e`, 2026-08-13); identical output before and after t2034_2.

## Diagnostic context

t2034_2 ran the applink shell tests as a baseline before editing. `test_applink_pusher.sh`
already failed there with:

```
File "<stdin>", line 812, in main
File ".aitask-scripts/monitor/monitor_core.py", in capture_pane_async
    agent_key_from_pane(pane.current_command, pane.pane_pid,
AttributeError: 'FakePane' object has no attribute 'current_command'
```

The traceback output was byte-identical after t2034_2's changes (diffed with File/caret
lines stripped). The last change to the test was t1322 (`411c7a546`, 2026-07-29), before
t1467 made `capture_pane_async` read `pane.current_command` / `pane.pane_pid` for
`agent_key_from_pane`.

Because the script dies mid-run, the checks after the crash (everything past the
`capture_pane_content_async does NOT touch idle state` case) are silently not executed.

## Suggested fix

Give the test's `FakePane` the fields the real `TmuxPaneInfo` carries that
`capture_pane_async` now reads (`current_command`, `pane_pid`), or build the fixture from a
real `TmuxPaneInfo`; then confirm the script runs to its `ALL PASSED` line and that the
previously skipped checks pass.
