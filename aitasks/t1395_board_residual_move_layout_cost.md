---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [aitask_board, tui, python, script-performance]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1243
created_at: 2026-08-03 17:45
updated_at: 2026-08-03 22:53
boardidx: 23552
---

## Context

t1243_5 replaced the two-column recompose on lateral / to-edge board moves with
an in-place DOM transplant. Measured with t1243_1's pre-registered method
(200 cards / 5 columns, 3 warm-up + 20 recorded ping-pong pairs, production
branch-mode topology), with the lateral `full` configuration **repeated 5x**
because a single run on this box disagreed with its own within-run controls by
~600 ms:

| | t1243_1 baseline | post-t1243_4 | post-t1243_5 |
|---|---|---|---|
| lateral median e2e | 2173.2 ms | 2395.2 ms | **1162.4 ms** (median of 5 run medians; range 1094.7-1344.0) |
| lateral p90 | 2556.2 ms | — | 1285.7-1898.2 ms across runs |
| vertical median | 184.1 ms | 191.9 ms | 192.6 ms |
| harness floor | 104.5 ms | 94.3 ms | 81.8 ms (median of 5) |

t1243_5's >= 30 % target was met in **5 runs out of 5** (-46.5 % at the median of
run medians; the worst run, 1344.0 ms, is still -38.2 %). **This task is about
the ~1.16 s that remains.**

Two measurement caveats inherited from that work, both load-bearing here:

- **The timed region must close on the post-move SCROLL, not on `_refocus_card`.**
  For a card with no layout yet, `_refocus_card` only *schedules*
  `_scroll_into_view_after_layout`, which re-queues until the card is on screen.
  The first post-implementation run closed on the refocus, excluded that work,
  and was discarded. `_install_probe` now hands the close to the scroll chain.
  Do not regress this when adding spans.
- **Floor-normalising thins the margin.** Scaling the baseline by the floor ratio
  (81.8 / 104.5) puts it at ~1701 ms, against which the median is -31.7 % and the
  worst run -21.0 %. That is not the pre-registered rule, but it is part of why
  this residual is worth attributing.

## Problem

t1243_1's ablation predicted that removing the recompose would take a lateral
keypress to **138.6 ms**. It lands at ~1162 ms. The gap is the pre-registered
"ideal-removal upper bound" caveat behaving exactly as documented: the ablation
removed the recompose by never touching the DOM at all, whereas a real transplant
still mounts a block and pays whatever board-wide work follows.

Post-change attribution says the remaining cost is **not** any lever this
workstream identified:

- `apply_filter` span 0.8 %, `_recompose_column` 0.0 %, `git_status` 0.0 %
- **`other` (unattributed) 99.1 %**
- the identified levers now sit at or below the noise floor — ablating them moves
  the median by less than the run-to-run spread (249 ms across 5 runs)

So ~1.16 s per lateral keypress is real and unexplained by the existing spans.

## Goal

Find out where it goes, then decide whether it is reducible. **Attribution
first — do not pre-commit to a fix.**

Candidate suspects, none yet measured:

- Textual's board-wide layout after `AwaitMount.__await__` calls
  `self._parent.refresh(layout=True)` — with 200 cards over 5 columns this may
  re-arrange far more than the touched columns.
- `_refocus_card` iterates a full-tree `self.query(TaskCard)`, and the
  focus-driven `scroll_visible` forces another layout. The
  `_scroll_into_view_after_layout` chain adds up to 5 refresh hops.
- `_column_widgets()` issues **four** full-DOM class queries per call (~25 ms on
  a 200-card board, measured in t1243_4) and is reached from the post-move
  refocus path via `_card_fully_visible` / `_viewport_anchor`. Recorded as an
  upstream defect by t1243_4 and still unaddressed.
- The `Pilot._wait_for_screen` harness floor is ~82 ms of the ~1162 ms and is
  measurement-only, not production cost — subtract it before drawing
  conclusions.

## Method constraints (inherited, non-negotiable)

- Use t1243_1's harness (`tests/test_board_movement.py`, `AITASK_BOARD_BENCH=1`)
  and its per-sample validity invariants. Do not invent a second measurement
  method.
- **Repeat the configuration you are judging.** A single `full` run produced
  1631.6 ms — outside the entire 5-run distribution — while its own controls
  (`-recompose` 1038.9, `-filter-git` 1065.0, `-filter-recompose` 1103.3, legacy
  1146.7) clustered ~500 ms lower. One run cannot adjudicate anything here.
- **Within-run ablation only** for attribution; this box carries 4-5 ambient load
  from concurrent coding agents. Always report the harness floor alongside any
  absolute.
- Do not run other tests while a bench is in flight, and check for concurrent
  agents first.
- Any new attribution span must join the active-span stack so non-overlap stays
  *proved*, not assumed.

## Acceptance criteria

- The residual lateral cost is attributed to named spans with the same
  non-overlap discipline as t1243_1, so `other` is no longer ~99 %.
- Each candidate above is either measured and quantified, or explicitly ruled out
  with the measurement that ruled it out.
- A recommendation is recorded: reducible (with the expected win) or inherent to
  Textual layout at this card count (with the evidence).
- Findings are appended to `aiplans/p1243_board_task_groups_and_fast_reordering.md`
  so **t1243_14** consumes them rather than rediscovering them.
- No performance target is asserted for this task up front — it is an
  investigation. If it turns into an optimisation, its target is set from its own
  measurement.

## Coordination

- Follow-up of **t1243_5** (`aiplans/archived/p1243/p1243_5_lateral_dom_transplant.md`
  once archived) — read its Final Implementation Notes first.
- **t1243_14** re-runs the benchmark and should reference this task's findings.
  It should also retire or re-scope the three pre-implementation opportunity
  gates the bench still prints (`R_pair`, `R_rm4`, `R_rm5`): they ablate a
  recompose that no longer exists on the lateral path, so their post-change
  values are noise.
- Related unaddressed upstream defect from t1243_4: `_column_widgets()`
  four-full-DOM-queries-per-call.
