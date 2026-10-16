---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [frozen, minimonitor, monitor, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-10-16 14:52
updated_at: 2026-10-16 14:53
---

## User report

In a tmux session holding several frozen code agents (former `aitask-pick`
agents, here observed after restoring them), the minimonitor no longer shows the
task description line under each agent's task-number row. The `i` (Task Info)
shortcut *does* work on those rows — only the title line is missing. Frozen
agents should keep showing their task title, just like live agents.

## Root cause (from exploration)

Both row renderers return early on `snap.frozen`, before the task-title row is
appended:

- `.aitask-scripts/monitor/minimonitor_app.py` `_agent_card_text` (~L2414-2422):
  the frozen branch returns `"<mark>F <name>  frozen"` only. The live path below
  it appends `\n  [dim]<title>` (clipped to
  `min(_TITLE_MAX_CELLS, _detail_budget(...))`) plus the merged gate/phase row.
- `.aitask-scripts/monitor/monitor_app.py` `_format_agent_card_text`
  (~L1772-1781): same early return; the live path appends
  `\n     [dim italic]t<id>: <title>` at the end (~L1878).

The comments justify the frozen and parked rows with "nothing capture-derived on
an uncaptured pane" (t1685, t1705_7). The **task title is not capture-derived**:
`_task_cache.get_task_id_for_pane` takes it from the window name
(`task_id_from_window_name`), and `get_task_info` reads it from the task file.
`i` uses the same path (`_show_task_info_for`), which is why `i` still works on
frozen rows. A tmux check showed the stand-in windows keep their
`agent-pick-<N>` names after restore, so the task id still resolves.

## Expected change

- On frozen rows in **both** `ait minimonitor` and `ait monitor`, append the
  task-title row when the pane's task id resolves to a `TaskInfo`. Use the same
  clipping, the same `markup_literal` handling and the same "no closing tag after
  user text" rule (t2017 / t2006) as the live row.
- Keep everything that IS capture-derived or a live verdict **off** the frozen
  row: the state dot, the status badge, the compare-mode and shadow glyphs, and
  the advisory workflow phase (`phase_for` reads `snap.content` /
  `awaiting_input`). The ledger-derived gate summary is optional. The plan
  decides, with reasoning, whether a frozen row shows it.
- Update the comments on the frozen branches so the "nothing capture-derived"
  rationale says why the title is allowed.
- Check the minimonitor row-budget block at the top of `minimonitor_app.py`
  (the `frozen` / `title` shape lines) and `tests/test_minimonitor_row_budget.py`,
  and keep their documentation of frozen rows accurate.
- The docked followed-agent panel (`_own_agent_identity_text`) already renders
  the title regardless of frozen state. Check that it stays unchanged.

## Tests

- `tests/test_monitor_frozen_filter.py` `FrozenRowRenderTests`: its
  `_FakeTaskCache` returns `None` for every pane, which is why nothing pins the
  current omission. Add a case with a resolvable task id + `TaskInfo` for both
  apps (`BOTH_APPS`). It asserts the title appears on the frozen row and that the
  existing forbidden glyphs and status words (`●`, `◆`, `≈`, `=`, `IDLE`,
  `PROMPT`, `Active`) and the phase text are still absent. Add a hostile-title
  variant (trailing backslash / `[/]`) to confirm markup safety.

## Coordination

t2039 (Implementing) is touching `minimonitor_app.py` and `monitor_app.py`, but
its diff is comment-only, far from these branches (~L3141 / ~L3589). No overlap
is expected, but re-check before editing.
