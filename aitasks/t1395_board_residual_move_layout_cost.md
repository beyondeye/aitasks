---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [aitask_board, tui, python, script-performance]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-03 17:45
updated_at: 2026-08-03 17:45
---

## Context

t1243_5 replaced the two-column recompose on lateral / to-edge board moves with
an in-place DOM transplant. Measured with t1243_1's pre-registered method
(200 cards / 5 columns, 3 warm-up + 20 recorded ping-pong pairs per axis,
production branch-mode topology):

| | t1243_1 baseline | post-t1243_4 | post-t1243_5 |
|---|---|---|---|
| lateral median e2e | 2173.2 ms | 2395.2 ms | **1115.0 ms** |
| lateral p90 | 2556.2 ms | — | 1805.9 ms |
| vertical median | 184.1 ms | 191.9 ms | 193.7 ms |
| harness floor | 104.5 ms | 94.3 ms | 91.6 ms |

t1243_5's >= 30 % target was met (-48.7 % vs baseline, -53.4 % vs the most
recent recorded value; the harness floor moved DOWN, so the gain is not ambient
load). **This task is about the ~1.1 s that remains.**

## Problem

t1243_1's ablation predicted that removing the recompose would take a lateral
keypress to **138.6 ms**. It landed at 1115.0 ms. The gap is the pre-registered
"ideal-removal upper bound" caveat behaving exactly as documented: the ablation
removed the recompose by never touching the DOM at all, whereas a real
transplant still mounts a block and pays whatever board-wide work follows.

Post-change attribution says the remaining cost is **not** any lever this
workstream identified:

- `apply_filter` span 0.8 %, `_recompose_column` 0.0 %, `git_status` 0.0 %
- **`other` (unattributed) 99.1 %**
- every ablation now lands at or above the full configuration
  (`-recompose` 1127.6 ms, `-filter-git` 1307.2 ms, `-filter-recompose`
  1345.4 ms) — i.e. the identified levers are at or below the noise floor

So ~1.1 s per lateral keypress is real and unexplained by the existing spans.

## Goal

Find out where it goes, then decide whether it is reducible. **Attribution
first — do not pre-commit to a fix.**

Candidate suspects, none yet measured:

- Textual's board-wide layout after `AwaitMount.__await__` calls
  `self._parent.refresh(layout=True)` — with 200 cards over 5 columns this may
  re-arrange far more than the touched columns.
- `_refocus_card` (`aitask_board.py`) iterates a full-tree `self.query(TaskCard)`,
  and the focus-driven `scroll_visible` forces another layout.
- `_column_widgets()` issues **four** full-DOM class queries per call (~25 ms on
  a 200-card board, measured in t1243_4) and is reached from the post-move
  refocus path via `_card_fully_visible` / `_viewport_anchor`. Recorded as an
  upstream defect by t1243_4 and still unaddressed.
- The `Pilot._wait_for_screen` harness floor is 91.6 ms of the 1115 ms and is
  measurement-only, not production cost — subtract it before drawing
  conclusions.

## Method constraints (inherited, non-negotiable)

- Use t1243_1's harness (`tests/test_board_movement.py`,
  `AITASK_BOARD_BENCH=1`) and its per-sample validity invariants. Do not invent
  a second measurement method.
- **Within-run ablation only.** This box carries 4-5 ambient load from
  concurrent coding agents; cross-run absolutes drift ~4-10 %. Always report the
  harness floor alongside any absolute.
- Do not run other tests while a bench is in flight, and check for concurrent
  agents first.
- Any new attribution span must join the active-span stack so non-overlap stays
  *proved*, not assumed.

## Acceptance criteria

- The residual lateral cost is attributed to named spans with the same
  non-overlap discipline as t1243_1, so `other` is no longer ~99 %.
- Each candidate above is either measured and quantified, or explicitly ruled
  out with the measurement that ruled it out.
- A recommendation is recorded: reducible (with the expected win) or inherent to
  Textual layout at this card count (with the evidence).
- Findings are appended to `aiplans/p1243_board_task_groups_and_fast_reordering.md`
  so **t1243_14** (retrospective benchmark) consumes them rather than
  rediscovering them.
- No performance target is asserted for this task up front — it is an
  investigation. If it turns into an optimisation, its target is set from its
  own measurement.

## Coordination

- Follow-up of **t1243_5** (`aiplans/archived/p1243/p1243_5_lateral_dom_transplant.md`
  once archived) — read its Final Implementation Notes first.
- **t1243_14** re-runs the benchmark and should reference this task's findings.
- Related unaddressed upstream defect from t1243_4: `_column_widgets()`
  four-full-DOM-queries-per-call.
