---
priority: medium
effort: low
depends: [t1243_13]
issue_type: performance
status: Ready
labels: [aitask_board, script-performance, testing]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-28 01:18
updated_at: 2026-08-04 07:59
---


## Context

**Child 14 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md`).

The design committed to several choices under partial information: the gap-index
`STEP` and the compaction policy (t1243_3), and the premise that the render pass
— not disk or git — is the keypress latency wall (Workstream B). The repo's
convention is to make that explicit with a **trailing retrospective child that
depends on the others**, documenting outcomes and filing standalone follow-ups
**only if the collected data justifies them**
(`aidocs/framework/planning_conventions.md`).

This child produces a measurement and a decision. It is **not** a licence to
re-architect.

## Key files to modify

- `aiplans/archived/p1243/` — the recorded results (this child's plan file is the
  deliverable).
- `tests/test_board_movement.py` — reuse, do not rewrite, the t1243_1 harness.

## Reference files for patterns

- t1243_1's method **as amended** — reuse it so the before/after numbers are
  comparable. Run it by invoking the harness, not by re-deriving it:
  `AITASK_BOARD_BENCH=1 <py> -m unittest tests.test_board_movement.BoardMovementBenchmarkTests.test_bench_baseline`
  - 200 parent cards over 5 columns, warm headless Pilot, production branch-mode
    topology (`aitasks` → `.aitask-data/aitasks`, **relative** `TASK_DIR`);
  - **ping-pong** sampling (`shift+right`/`shift+left` between two adjacent
    columns, `shift+down`/`shift+up` between two adjacent mid-column positions),
    with the moved card starting at the **bottom** of its column — the only
    position for which right→left restores the exact pre-state;
  - 3 warm-up **pairs** discarded, 20 recorded pairs per axis per config; every
    sample must carry a write, must see `apply_filter` fire inside the timed
    region, must record zero span-nesting violations, and must leave a
    non-negative residual — any failure **fails the run**;
  - the timed region closes on an `asyncio.Event`, **never** `pilot.pause()`
    (≥20 ms of synthetic sleep in Textual 8.2.7);
  - **attribution is by ABLATION, not span share**, and axes are never pooled.
- **DO NOT use span shares for attribution.** t1243_1's first run did, and read
  `apply_filter + recompose` at 1.6 % with 98.3 % unattributed — an artifact,
  because `_recompose_column` drops the `remove_children()` / `mount_all()`
  awaitables so the real cost lands in the message pump afterwards. Span shares
  are retained as diagnostics only and are labelled as under-attributing.
- **The recorded baseline to compare against** (parent plan, "RECORDED BASELINE
  AND CHECKPOINT DECISION"): lateral median **2173.2 ms** / p90 2556.2 ms;
  vertical median **184.1 ms** / p90 238.0 ms; harness floor 104.5 ms.
- t1243_1's **decision checkpoint** outcome: premise PASS (94.3 %), t1243_5 PASS
  (93.6 %), t1243_4 MISS (0.4 %) → user chose *revise scope*, so **t1243_4 has
  no latency target** and the ≥30 % target sits entirely on **t1243_5**.
- t1243_5's recorded spike result (transplant landed, or the documented fallback).

## Implementation plan

1. Re-run the pre-registered benchmark against the landed board.
2. Re-run the write-count assertions on a large board: single move, bulk move of
   K, group formation of K, group block move of N — recording **actual** counts
   and changed-path sets, not just pass/fail.
3. Produce a comparison table: baseline vs landed, **per axis** (never pooled),
   with median and p90 deltas, the ablation deltas per lever, and whether the
   **>= 30% median reduction** target was met — that target is **t1243_5's**,
   judged on the **lateral** axis. t1243_4 is judged only on *no regression*.
   If the target is missed, do **not** revise, postpone or revert anything:
   run the **Performance-Gate Confirmation Checkpoint** (parent plan) and let
   the user choose.
4. Assess the specific open questions:
   - **`STEP = 1024`** — how often did a real board hit compaction? If never,
     note it; if often, quantify and consider whether `stride_for` should raise
     the floor.
   - **Remaining hotspots** — which span now dominates median keypress latency?
   - **The Tier-2 fallback** — if t1243_5's spike failed and `refresh_columns`
     stayed, how much latency remains attributable to the recompose?
   - **Write amplification in practice** — did "one move = one file write" hold
     on a real board over a real session, including the compaction exception?
5. **File follow-ups only where the data justifies them.** A follow-up needs a
   number attached. If the numbers are fine, the deliverable is the recorded
   table and an explicit "no follow-ups warranted" statement — that is a
   successful outcome, not an empty one.

## Verification

- The comparison table is recorded in this child's plan file, with the same
  method as the baseline so the numbers are genuinely comparable.
- Every claim in the table traces to a measured number, not an inference.
- Any follow-up task created cites the specific measurement that justifies it.
- If no follow-ups are warranted, that conclusion is stated explicitly with the
  supporting numbers.

## Coordination — t1395 (done) and t1402 (blocked on this task)

**t1395 already answered this task's "which span now dominates" question.** Read
`### RECORDED RESULT — t1395 residual move/layout cost attribution` in
`aiplans/p1243_board_task_groups_and_fast_reordering.md` **before** Step 4 —
consume it, do not rediscover it. Headline: `dom_query` (cold full-tree
`DOMQuery.nodes`) is **53.6 %** of a lateral keypress at 587.3 ms / 123 calls;
Textual's own `layout + reflow + render` is 23.6 %; `_column_widgets()` is
**0 calls** (nav-path only, never the move path).

t1395 also added `test_bench_attribution` — a **separate** gated test carrying an
opt-in self-time span tier. `test_bench_baseline` is deliberately unperturbed by
it (verified: same five configs, same span list, `other=99.1 %` lateral), so this
task's comparison against 2173.2 / 1162.4 ms remains valid. Run
`test_bench_attribution` alongside the baseline if you want per-span detail.

**Two measurement facts from t1395 that change how this table must be read:**

1. **The two axes do not measure the same window.** Vertical records **0**
   `bindings_sweep` and **0** `footer_compose`: its card is already laid out, no
   scroll chain starts, and the timed region closes at `_refocus_card` *before*
   the deferred bindings sweep runs. The lateral region stays open through the
   layout hops and therefore contains it. So the ~6x lateral/vertical gap is
   substantially a **measurement-window artifact**. Do not report vertical as
   "the cheap path" without this caveat.
2. **`R_pair` / `R_rm4` / `R_rm5` are confirmed degenerate**, exactly as this
   task already anticipated — retire or re-scope them.

**Ordering constraint — `t1402` is blocked on this task.**
`t1402_board_focus_query_storm_on_move` declares `depends: [t1243_14]`. It
implements the fix t1395 recommends and is measured at **45-76 % removable** on
the lateral axis. It must land **after** this retrospective: a win of that size
arriving from outside the t1243 workstream would make this table incomparable
with the recorded baselines and would retroactively flatter t1243_5. If this
task is postponed or descoped, that dependency must be re-decided explicitly
rather than silently unblocking.
