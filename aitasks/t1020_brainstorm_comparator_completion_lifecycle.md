---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [brainstorming, ait_brainstorm]
created_at: 2026-06-17 10:52
updated_at: 2026-06-17 10:52
boardidx: 20
---

## Problem

In the `ait brainstorm` TUI, a **Compare** operation never transitions from
`Waiting` → `Completed`, even after the comparator agent finishes successfully.
The status screen then shows the confusing state **"100% progress but still
Waiting"**, and the agent's comparison output is not wired back into the TUI.

Observed live in `crew-brainstorm-1017`:
- `comparator_001_status.yaml` → `status: Completed`, `progress: 100`,
  `completed_at` set, output fully written (no data loss, no fetch error).
- `comparator_001_alive.yaml` → `last_message: Comparison complete`.
- **But** `br_groups.yaml → compare_001 → status: Waiting` (stuck), and
  `_crew_status.yaml` aggregate stale at `Running / 80`.

## Root cause

There are three independent status layers and only the **agent** layer updates
on completion:

| Layer | File | Value | Correct? |
|---|---|---|---|
| Agent | `comparator_001_status.yaml` | `Completed` / `100` | yes |
| Crew aggregate | `_crew_status.yaml` | `Running` / `80` | stale |
| Operation/group | `br_groups.yaml` → `compare_001` | `Waiting` | stuck |

The comparator operation lacks the completion-handling lifecycle that explorer
and synthesizer operations have. For those, after registration the TUI calls a
`_register_<kind>_agent()` tracker, a `_poll_<kind>()` loop detects the agent's
`Completed` status, and an `apply_<kind>_output()` calls
`update_operation(..., status="Completed")`. The comparator has **none** of
these:

- `brainstorm_app.py` (~lines 7891-7899) registers the comparator but — unlike
  the explorer/synthesizer branches right beside it — makes **no tracking
  call**.
- No `_poll_comparators()` and no `apply_comparator_output()` exist.
- So nothing ever flips `compare_001` from `Waiting` → `Completed`.

The UI symptom: `GroupRow.render()` (`brainstorm_app.py` ~3019-3037) reads the
operation `status` from `br_groups.yaml` ("Waiting") but computes the progress
bar by aggregating agent progress files (→ 100%). Hence "100% + Waiting". The
progress bar is only hidden once `status == "Completed"`, which never happens.

The crew runner "stopping" is a red herring — the interactive comparator agent
was in fact still alive; the TUI simply never polls it.

## Result-access impact

Because `apply_comparator_output()` is missing and the compare op creates no
nodes (`nodes_created: []`), there is likely no node to press `o` on to open the
comparator output in `OperationDetailScreen`. So the same missing integration
also impairs reading the comparison result through the TUI. (Workaround today:
read `.aitask-crews/crew-brainstorm-<N>/comparator_<seq>_output.md` directly.)

## Acceptance criteria

- A completed comparator operation transitions `br_groups.yaml` group `status`
  to `Completed`, so the status screen no longer shows "100% + Waiting".
- The comparator gets the same lifecycle as explorer/synthesizer: a
  registration/tracking call after `register_comparator(...)`, a polling
  mechanism (or reuse of an existing generic poller) that detects agent
  completion, and an apply/finalize step that calls
  `update_operation(..., status="Completed")`.
- The comparator's `_output.md` is reachable from the TUI (decide and implement
  how a node-less compare op surfaces its `OperationDetailScreen` — e.g. from
  the status screen / GroupRow, since there is no created node to press `o` on).
- Consider whether the crew-aggregate `_crew_status.yaml` (Running/80 while the
  only agent is Completed/100) is a separate roll-up bug worth fixing here or
  splitting out; make the scope decision explicit rather than silently dropping
  it.
- Add a regression test (e.g. extend `tests/test_brainstorm_compare_overlay.py`
  or a sibling) proving a completed comparator drives the operation status to
  `Completed`.

## Key references

- `.aitask-scripts/brainstorm/brainstorm_app.py` — `~7876-7912` (register
  branches: explorer/comparator/synthesizer), `~3019-3037` (`GroupRow.render`),
  explorer poll/register (`_register_explorer_agent` ~5249, `_poll_explorers`
  ~5303), 5s poll timer (~5260).
- `.aitask-scripts/brainstorm/brainstorm_session.py` — `record_operation`
  (status init "Waiting", ~256), `update_operation` (~282-309),
  `apply_explorer_output` (~934-963), `apply_synthesizer_output` (~977-1009);
  no `apply_comparator_output`.
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — `register_comparator`
  (~629-667).
- Live evidence: `.aitask-crews/crew-brainstorm-1017/` (`br_groups.yaml`,
  `comparator_001_status.yaml`, `_crew_status.yaml`).
