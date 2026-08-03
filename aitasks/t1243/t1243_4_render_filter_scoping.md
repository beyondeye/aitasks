---
priority: high
effort: medium
depends: [t1243_3]
issue_type: performance
status: Implementing
labels: [aitask_board, tui, python, script-performance]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1243
created_at: 2026-07-28 01:13
updated_at: 2026-08-03 10:53
---

## Context

**Child 4 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream B, Tier 1).

Every move path terminates in `apply_filter()`, which iterates
`self.query(TaskCard)` over **every card on the board** — not just the touched
column — assigning `card.styles.display` on each unconditionally, rebuilding
`f"{filename} {metadata}".lower()` per card when a search filter is active, and
doing a second full query over `EmptyColumnPlaceholder`. On top of that, every
movement keypress spawns a `git status --porcelain -- aitasks/` subprocess via
`TaskManager.refresh_git_status()`.

This child is the **certain-win tier**: no widget-lifecycle surgery, no
cross-parent DOM moves (that is t1243_5).

> **SCOPE REVISED BY t1243_1's DECISION CHECKPOINT (user-confirmed).**
> t1243_1 measured the baseline by ablation. Workstream B's premise **holds**
> (94.3% vs 40%), but that share is **almost entirely the column recompose**,
> which is t1243_5's lever, not this one:
>
> | lateral, 200 cards | median e2e |
> |---|---|
> | full | 2173.2 ms |
> | − recompose | 138.6 ms |
> | − `apply_filter` − `git_status` (this task's levers) | 2296.9 ms (no gain) |
>
> This task's opportunity gate therefore **missed**: 0.4% removable versus its
> 30% target, and 10.8% of the 138.6 ms that remains once t1243_5 lands. At the
> confirmation checkpoint the user chose **revise scope**, so:
>
> - **This task no longer carries a latency target.** Do not gate it on the
>   ≥30% rule; the ≥30% target now sits entirely on **t1243_5**.
> - **Its scope is retained** for two non-latency reasons: the **data-level match
>   predicate + widget-kind-agnostic visible-content accumulator that t1243_10
>   structurally depends on**, and removing the per-keypress `git status`
>   subprocess (churn/hygiene, not measurable latency).
> - Record the measured delta anyway, as a regression guard — it must not get
>   *worse*.
>
> Full data and the recorded decision: parent plan, "Decision checkpoint".

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `KanbanApp.apply_filter`, its ~12
  call sites, `TaskCard` (haystack cache), and the four `_move_task_*` actions
  (targeted `modified_files` update).
- `tests/test_board_render_scoping.py` — **new**.

## Reference files for patterns

- `tests/test_board_view_filter.py` — existing coverage of `apply_filter` and the
  deferred `call_after_refresh` pattern after async compose; do not regress it.
- `tests/test_board_footer_visibility.py` — render-level assertion style.
- t1243_1's harness for the latency measurement.

## Implementation plan

### 1. Scope `apply_filter`

```python
def apply_filter(self, cols: set[str] | None = None):
```

- `cols is None` → today's whole-board pass, unchanged. This is what view and
  filter toggles keep using.
- `cols` given → iterate only those columns' cards (via the column widget's own
  `query(TaskCard)`), and update `EmptyColumnPlaceholder` visibility and the
  focus-rescue check **for those columns only**. Do not let a scoped pass flip a
  placeholder in an untouched column.
- The four movement paths pass the touched columns.

### 2. Cache the search haystack

Build `f"{filename} {metadata}".lower()` once per `TaskCard` (at construction /
when its task data is replaced) instead of once per filter pass per card.

### 3. Skip no-op display assignments

Only assign `card.styles.display` when the value actually changes — assignment
triggers a Textual refresh.

### 4. Stop spawning `git status` per keypress

A move writes exactly the files we just wrote, so add those filenames to
`manager.modified_files` directly instead of calling `refresh_git_status()`. The
full scan stays on explicit refresh and on commit. This is exact, not an
approximation: we know the changed set because we produced it.

### 5. Leave room for t1243_10 (NON-OPTIONAL)

t1243_10 generalises this pass from *cards* to *units*, because a **collapsed
group mounts a `GroupHeader` and none of its member cards**. Do **not** bake in a
card-only assumption:

- factor the match predicate into a **data-level helper** that takes a `Task`
  (or its filename + metadata) rather than a mounted widget, so the collapsed
  path can evaluate members that have no widget;
- keep the visible-content accumulator (`cols_with_visible`)
  **widget-kind-agnostic**, so a `GroupHeader` can later count as column content
  without a rewrite.

## Verification

- Spy proving a lateral move queries **only the two touched columns** and spawns
  **no subprocess**.
- Render-level assertions (`widget.render().plain`) for filtered / unfiltered
  cards, and the `EmptyColumnPlaceholder` interaction under a scoped pass.
- The match-predicate helper is unit-tested against `Task` data with **no widget
  mounted** — this is what proves t1243_10 can reuse it.
- `tests/test_board_view_filter.py` still passes unchanged (the `None` path is
  behaviour-preserving).
- **No latency target** (revised at t1243_1's checkpoint — see the scope note
  above). Structural assertions **are** the pass condition for this child.
- **Latency regression guard instead:** re-measure with t1243_1's ping-pong
  method and valid-sample rule and record the delta; median keypress latency on
  either axis must **not regress** versus the t1243_1 baseline. Record the
  measured delta in the parent plan for t1243_14 either way.
