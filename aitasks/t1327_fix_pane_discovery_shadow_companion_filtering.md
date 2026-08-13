---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, monitor]
gates: [risk_evaluated]
anchor: 1322
followup_kind: upstream_defect
created_at: 2026-07-29 13:11
updated_at: 2026-08-13 23:06
boardidx: 86016
---

## Origin

Spawned from t1322 during Step 8b review.

## Upstream defect

- `tests/test_multi_agent_window_substrate.sh:90-92 — pre-existing failure: "discovery keeps exactly one real agent" / "discovery kept the agent pane (%1)" fail and the embedded Python then raises AttributeError: 'list' object has no attribute 'pane_id'. Reproduces with all t1322 changes stashed, so it predates this task; _parse_list_panes appears to no longer filter shadow/companion panes as the test expects.`
- `.aitask-scripts/board/aitask_board.py — uncommitted concurrent change makes tests/test_board_work_report.py::test_hidden_cards_still_listed fail in the live tree; the same test passes at HEAD and with only t1322's changes applied. Belongs to the concurrent board work, not to t1322.`

## Diagnostic context

Found while running the affected-test sweep for t1322 (COMPLETED agent status).
`bash tests/test_multi_agent_window_substrate.sh` fails at the pane-discovery
tier:

```
  FAIL: discovery keeps exactly one real agent
  FAIL: discovery kept the agent pane (%1)
  AttributeError: 'list' object has no attribute 'pane_id'
```

The failing assertions live at `tests/test_multi_agent_window_substrate.sh:90-92`:

```python
panes = monitor._parse_list_panes(stdout, "testsess")
check("discovery keeps exactly one real agent", len(panes) == 1)
check("discovery kept the agent pane (%1)",
      len(panes) == 1 and panes[0].pane_id == "%1")
```

The fixture feeds three panes — a real agent `%1`, a shadow `%2`, and a
companion (`pid 9999`, `python`) `%3` — and expects discovery to filter the
last two, leaving exactly one. It currently returns more than one, so
`panes[0]` is not the expected object and the subsequent index raises.

**Provenance was established, not assumed:** the failure reproduces with
`monitor_core.py` stashed (`git stash push -- .aitask-scripts/monitor/monitor_core.py`),
so it predates t1322 and is not a regression from the identity-keyed
`TaskInfoCache` work.

The second bullet is recorded for completeness only — it is attributable to a
concurrent uncommitted change in `aitask_board.py`, verified by the test passing
both at `HEAD` and at `HEAD` + t1322's changes alone. It likely needs no action
here; confirm it disappears once that work lands.

## Suggested fix

Determine whether the regression is in `_parse_list_panes`' filtering (shadow
panes carrying `@aitask_shadow_target`, and companion panes matched by command /
pid heuristics) or in the test fixture drifting from the current
`_LIST_PANES_FORMAT` field order. Note `_LIST_PANES_FORMAT` gained the
`#{@aitask_shadow_target}` field, so a fixture built for the older column set
would mis-align. Fix whichever is genuinely stale, and make the assertion fail
cleanly (assert length before indexing) so the next breakage reports a
comparison rather than an `AttributeError`.
