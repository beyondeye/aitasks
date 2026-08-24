---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [reporting, tui, backlog]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1544
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-08-24 16:18
updated_at: 2026-08-24 23:13
completed_at: 2026-08-24 23:13
---

## Origin

Risk-mitigation ("after") follow-up for t1544_4, created at Step 8d after implementation landed.

## Risk addressed

code-health — ~150 lines of axis/ordering/subtotal logic locked inside
aitask_stats.py that t1544_5 will partly duplicate.

Verbatim from t1544_4's plan `## Risk` section:

> ~150 lines of render logic (three level axes, per-axis scratch clamp counters,
> two different row-membership rules) land in `aitask_stats.py`, and t1544_5
> will want a subset of the same ordering/subtotal logic for its panes.
> · severity: low · → mitigation: extract_backlog_view_helper

## Dependency — do not start this before t1544_5

**This task must not be picked until t1544_5 (stats TUI backlog panes) has
landed.** The whole point of the extraction is to design the seam against a
**real** second consumer. t1544_5's plan specifies its own shape — a `DataTable`
with a row cap and an `Other` bucket, and a category-split net-flow chart — which
is deliberately *not* what the CLI renders. Extracting first would produce a
helper shaped for a guessed consumer, which is the failure mode t1544_4
explicitly rejected when it kept the logic private.

Set `depends: [1544_5]` when picking this up (it could not be wired at creation
time, since t1544_5 was still pending).

## Goal

Move the parts of `.aitask-scripts/aitask_stats.py` that both surfaces genuinely
share into a pure `.aitask-scripts/lib/backlog_view.py`:

- `_aggregate_all` — the accumulating all-tasks re-key. **This one is
  load-bearing**: a dict comprehension keeps only the last category per offset,
  and t1544_4 pins that with a negative control. Whatever else moves, this must
  not be re-implemented per surface.
- `_build_backlog_axis` / `BacklogAxis` — the three level axes, the per-axis
  scratch clamp counters, and the ordering rule
  (`(-level_at_offset_0, category_display_name)`, tie-break included).
- `BACKLOG_TASK_EXCLUSION_REASONS` — the seven task-level reasons, kept
  separate from `negative_level`, which counts output CELLS.

Leave surface-specific rendering behind: the pipe-table formatting, the
truncating label cell, the width-adaptive numeric cells, and the two different
row-membership predicates are CLI concerns.

`lib/` must not import anything from the TUI — `tests/test_no_lib_to_tui_import.sh`
enforces this, so the new module has to stay pure.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read the LAST line only.
- `bash tests/test_no_lib_to_tui_import.sh`.
- `ait stats` output is **byte-identical** to a pre-change capture, ignoring the
  `Generated:` line. Use the same-clock control t1544_4 used (stash the sources,
  capture, restore, capture again, `__pycache__` cleared for both runs) — a
  plain before/after diff is invalidated by any concurrent task activity.
- The stats TUI backlog panes render unchanged.
- t1544_4's negative controls still discriminate after the move, in particular
  the dict-comprehension mutation of the all-tasks re-key.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-24T19:48:21Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-24T20:09:49Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-24T20:13:39Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:858c99f18dee6e46

> **✅ gate:risk_evaluated** run=2026-08-24T20:13:39Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1586/risk_evaluated_2026-08-24T20:13:39Z-risk_evaluated-a1.log`
