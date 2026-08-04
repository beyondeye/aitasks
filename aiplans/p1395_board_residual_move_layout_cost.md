---
Task: t1395_board_residual_move_layout_cost.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1395 — Attribute the residual lateral move / layout cost

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` §"Workstream B —
> render cost" first (the pre-registered method, the ablation amendment, and the
> two `### RECORDED …` sections). Then
> `aiplans/archived/p1243/p1243_5_lateral_dom_transplant.md` Final Implementation
> Notes. This file is the execution order.

## Context

t1243_5 replaced the two-column recompose on lateral / to-edge board moves with
an in-place DOM transplant. Median lateral keypress latency fell 2173.2 ms →
1162.4 ms (−46.5 %, target met 5/5 runs). **This task is about the ~1.16 s that
remains**, which the existing spans cannot see: `apply_filter` 0.8 %,
`_recompose_column` 0.0 %, `git_status` 0.0 %, **`other` 99.1 %**. Every lever
this workstream identified now sits at or below the run-to-run spread (249 ms
across 5 runs).

This is an **investigation**. It asserts no performance target and pre-commits to
no fix. Its output is (a) an attribution of `other` to named spans, (b) a
measured verdict on each named suspect, and (c) a recommendation recorded where
**t1243_14** will consume it.

### What exploration already established (before any measurement)

Three findings from reading the current source and Textual 8.2.7 change the
suspect list the task file shipped with. All three are stated here as *premises
to be measured*, not as conclusions.

1. **The task's suspect #3 is unreachable on the move path.**
   `_column_widgets()` (`aitask_board.py:7138`) is reached only via
   `_column_widget()` (`:7157`) from `_card_fully_visible` (`:7177`) and
   `_viewport_anchor` (`:7200`), whose only callers are `_reanchor_to_viewport`
   (`:7224`, `:7226` ← `action_nav_up` `:7287` / `action_nav_down` `:7304`) and
   `_nav_lateral` (`:7359-7360`) — i.e. **plain-arrow navigation**, never
   `shift+arrow` or `ctrl+arrow`. The bench presses only `shift+`/`ctrl+` keys
   (`tests/test_board_movement.py:1106-1121`). Verified by exhaustive call-site
   grep. It remains a real ~25 ms-per-keypress defect **on the nav path**; this
   task rules it out of the *move* residual with a counter (0 calls), which is
   the measurement the acceptance criteria ask for.

2. **A suspect the task file does not name, and the strongest one.**
   `card.focus()` inside `_refocus_card` (`aitask_board.py:6568`) reaches
   `Screen.set_focus`, whose last statement is
   `self.call_after_refresh(self.refresh_bindings)` (`textual/screen.py:1150`).
   `refresh_bindings` (`:392-394`) publishes `bindings_updated_signal` →
   `Footer.bindings_changed` (`textual/widgets/_footer.py:308-313`) →
   `call_after_refresh(self.recompose)` → `Footer.compose` (`:244-247`) reads
   `Screen.active_bindings` (`textual/screen.py:457-485`), which calls
   `app._check_action_state(...)` — i.e. **`KanbanApp.check_action` once per
   binding**. The board declares 99 `Binding(...)`, and `check_action`
   (`:6053-6201`) contains **8 `self._focused_card()` call sites**, each of which
   is `self.query("TaskCard:focus")` (`:7124-7127`) — a full-screen
   `walk_children` + CSS match over ~1250 widgets, measured at ~7 ms in t1243_4.
   A single focus change therefore plausibly costs tens to hundreds of
   full-tree queries. `Footer` is mounted at `:6218`, so the chain is live.
   **Unmeasured and unnamed by t1243_1, t1243_4, t1243_5 and t1395's own task
   file.**

3. **The two axes may not close their timed regions symmetrically.**
   The region closes on `_refocus_card` *unless* a scroll chain is outstanding
   (`tests/test_board_movement.py:325-374`). On the **lateral** path the card is
   freshly mounted, has no `region.area`, and
   `_scroll_into_view_after_layout` (`aitask_board.py:6586`) re-queues through
   `call_after_refresh` for up to `_SCROLL_LAYOUT_HOPS = 5` hops — so everything
   Textual does in those hops (compositor reflow, ~1250 `_size_updated` calls +
   Resize messages, the bindings sweep above) is **inside** the window. On the
   **vertical** path the card is already laid out, no chain starts, and the
   region closes at the refocus — so the same deferred sweep lands **after** the
   close. This is a candidate structural explanation for lateral 1162 ms vs
   vertical 192.6 ms that has nothing to do with the transplant, and it is a
   measurement-validity question t1243_14 needs answered.

4. **Scroll animation is already ruled out by construction** — both scroll sites
   pass `animate=False, immediate=True` (`aitask_board.py:6598`,
   `TaskCard.on_focus` `:2090-2098`). Recorded so it is not re-investigated; a
   counter confirms it.

## Method constraints (inherited, non-negotiable)

- Use t1243_1's harness (`tests/test_board_movement.py`, `AITASK_BOARD_BENCH=1`)
  and its per-sample validity invariants. Do not invent a second measurement
  method.
- **Attribution is by ABLATION.** Span shares under-attribute (the whole reason
  `other` reads 99 %) and are diagnostics only. Every claim about a *removable*
  cost comes from a within-run ablation delta.
- **Within-run ablation only**; never cross-run absolutes. Report the harness
  floor alongside any absolute.
- **Repeat the configuration you are judging** (≥5 runs); one run cannot
  adjudicate anything on this box.
- Run nothing else while a bench is in flight; check for concurrent agents first.
- Any new attribution span must join the active-span stack so non-overlap stays
  **proved**, not assumed.

## The one design decision that governs everything else

**`test_bench_baseline` must keep measuring exactly what it measures today.**
t1243_14 re-runs it and compares against 2173.2 / 1162.4 ms; instrumentation
added to that path would silently move the number and destroy the comparison.

So: the new probe tier is **opt-in per child run** (`params["attribution"]`), and
the new configs live in a **new gated test**, `test_bench_attribution`.
`test_bench_baseline`'s five configs, its `Probe.LEAVES`, and all six validity
invariants are byte-for-byte untouched.

---

## Step 0 — anchor re-verification and a clean box

1. Re-locate every symbol this plan names by **name**, never by line number
   (`aitask_board.py` moved 7378 → 9775 lines during t1243). If a premise has
   changed, stop and record it rather than working around it.
2. Confirm no other benchmark is in flight and record ambient load
   (`uptime`, `nproc`) at the start and end of every measurement run. Check
   concurrent agents via the tmux gateway (never raw tmux):
   `source .aitask-scripts/lib/tmux_exec.sh; ait_tmux list-panes -a -F '#{session_name}:#{window_index} #{window_name}'`.
3. Confirm the premise in Context §2 empirically **before** building anything on
   it, with a 3-line throwaway probe (not committed): count
   `KanbanApp.check_action` invocations across one `shift+right` in the existing
   ungated smoke path. If the count is ~1 (i.e. `Footer.bindings_changed`
   early-returns because `screen.app.app_focus` is `False` under headless
   `run_test`), the suspect is dead in the harness and the plan drops to the
   remaining spans — **record that, do not work around it**.

## Step 1 — hierarchical self-time spans in `Probe`

`tests/test_board_movement.py`, `class Probe` (`:167-226`) and `_install_probe`
(`:229-374`).

The existing four `LEAVES` form a flat, mutually-exclusive partition and any
nesting is a violation. The new suspects **do** nest (`check_action` calls
`_focused_card`; `_refocus_card` calls the scroll helper; a layout pass can fire
inside a scroll). A flat tier cannot express that, so add a second tier with
proper **self-time** accounting on the *same* stack:

```python
    # --- attribution tier (t1395) -------------------------------------
    #: Opt-in. Installed only when params["attribution"] is true, so
    #: `test_bench_baseline` measures exactly what it measured before.
    TREE = (
        "refocus",          # KanbanApp._refocus_card
        "scroll_hop",       # KanbanApp._scroll_into_view_after_layout (one hop)
        "check_action",     # KanbanApp.check_action
        "focus_query",      # KanbanApp._focused_card  -> query("TaskCard:focus")
        "bindings_sweep",   # Screen.active_bindings
        "footer_compose",   # Footer.compose (recompose body)
        "layout",           # Screen._refresh_layout
        "reflow",           # Compositor.reflow / reflow_visible
        "render",           # Screen._compositor_refresh
        "dom_query",        # DOMQuery.nodes (every full-tree walk, anywhere)
        "col_widgets",      # KanbanApp._column_widgets  (expected: 0 calls)
    )
```

`_enter`/`_exit` gain self-time bookkeeping while keeping the existing
`self.nesting` violation record **for the original LEAVES only** (so the
pre-registered invariant is unchanged):

```python
    def _enter(self, name: str) -> float:
        tid = threading.get_ident()
        stack = self._stack.setdefault(tid, [])
        if stack and name in self.LEAVES and stack[-1] in self.LEAVES:
            # Unchanged pre-registered proof: two LEAVES may never overlap.
            self.nesting.append([stack[-1], name])
        stack.append(name)
        t0 = time.perf_counter()
        if self.sync_end is not None and self.first_deferred_start is None and t0 >= self.sync_end:
            self.first_deferred_start = t0
        return t0

    def _exit(self, name: str, t0: float):
        dt = time.perf_counter() - t0
        stack = self._stack[threading.get_ident()]
        stack.pop()
        if name in self.LEAVES:
            self.spans[name] += dt
            self.counts[name] += 1
        else:
            self.tree_total[name] += dt
            self.tree_self[name] += dt - self._child_time.pop(id_of_frame, 0.0)
            self.tree_calls[name] += 1
        # Charge this span's TOTAL to its parent's child-time, so the parent's
        # self-time excludes it. Non-overlap of self-times is then structural,
        # not assumed.
        if stack:
            self._child_time[stack[-1]] = self._child_time.get(stack[-1], 0.0) + dt
```

Implementation notes that matter:

- `_child_time` must be keyed per **active invocation**, not per name
  (`_refocus_card` → `scroll_hop` → `_refocus_card` cannot happen, but
  `check_action` → `focus_query` fires 8× within one `check_action`). Use a
  parallel stack of accumulators pushed/popped alongside `_stack` rather than
  the dict sketch above; the sketch shows the accounting rule, not the final
  data structure.
- **`self` times across the whole tier are non-overlapping by construction**
  (a child's total is subtracted from its parent), and their sum is ≤ `e2e`.
  Assert `sum(tree_self.values()) <= e2e + 1e-9` as a new per-sample invariant
  **for attribution runs only**.
- `reset()` clears the three new dicts; `nesting` still survives resets.
- The LEAVES may nest *inside* tier-2 spans (e.g. `apply_filter` inside nothing,
  but `dom_query` inside `apply_filter`). That is fine and is exactly why the
  violation check is now scoped to LEAVES-inside-LEAVES.

`_install_probe(B, probe, ablate=(), attribution=False)` installs the tier only
when `attribution` is true. Wrappers to add (all on the class):

| span | patch target |
|---|---|
| `refocus` | `B.KanbanApp._refocus_card` — **wrap the existing t1243_5 close wrapper, outermost**, so the close semantics are untouched |
| `scroll_hop` | `B.KanbanApp._scroll_into_view_after_layout` — likewise outermost; also record the hop index |
| `check_action` | `B.KanbanApp.check_action` |
| `focus_query` | `B.KanbanApp._focused_card` |
| `col_widgets` | `B.KanbanApp._column_widgets` |
| `bindings_sweep` | `textual.screen.Screen.active_bindings` — a `property`; re-wrap via `Screen.active_bindings = property(wrapper)` |
| `footer_compose` | `textual.widgets.Footer.compose` (a generator — time the *drain*, not the call) |
| `layout` | `textual.screen.Screen._refresh_layout` |
| `reflow` | `textual._compositor.Compositor.reflow` **and** `.reflow_visible` |
| `render` | `textual.screen.Screen._compositor_refresh` |
| `dom_query` | `textual.css.query.DOMQuery.nodes` — a cached `property`; count + time only the **cold** computation |

Ordering rule: the t1243_5 close wrappers must stay **innermost relative to
nothing** — i.e. install the attribution wrapper *around* the already-installed
close wrapper, never between it and the production function, so
`probe.scroll_pending` sequencing is preserved exactly.

Per-sample output gains `tree_self`, `tree_total`, `tree_calls`, and
`scroll_hops` (the observed hop count). `summarise()` reports, per sample then
medianed: `share_<name> = tree_self[name] / e2e`, plus median call counts.

## Step 2 — new ablation configs (the load-bearing attribution)

New gated test `test_bench_attribution` in `BoardMovementBenchmarkTests`,
**lateral axis only**, 200 cards, branch-mode topology, same warm-up/pair counts,
same validity invariants, `attribution=True` on every config:

| tag | ablation | what its delta measures |
|---|---|---|
| `full` | — | denominator |
| `no_bindings` | `Screen.refresh_bindings` → no-op | the whole focus→bindings→Footer sweep |
| `no_focus_query` | `KanbanApp._focused_card` memoized for one message-pump tick | the 8-call-sites × N-bindings query storm, *without* changing which bindings are enabled |
| `no_refocus_query` | `_refocus_card` resolves the card from the destination column's `children` instead of `self.query(TaskCard)` | one full-tree query on the refocus |
| `no_layout` | *not ablatable* — see below | — |

Ablation-safety rules, each with the reason it is not optional:

- **Never ablate `check_action` itself.** It gates `move_task_right`; a no-op
  returning `None` would change which actions dispatch, and returning `False`
  would make the keypress a no-op — the `writes > 0` invariant would fail the
  run (correctly).
- **`no_focus_query` must return the same object**, not `None`. Memoize on
  `(id(self.screen.focused),)` per tick so every gate reaches the same verdict;
  ablation must remove *cost*, never *behaviour*, or the stationarity check will
  catch it (and it must — that is the negative control working).
- **Layout/reflow/render are measured, not ablated.** Removing them removes the
  board. Their contribution is reported as tier-2 self-time share, explicitly
  labelled as *attribution without a removable-cost claim*.
- Every ablation config re-uses `_install_probe`'s existing `ablate` set
  mechanism where the target is a plain method; the two that need a *substitute*
  rather than a skip (`no_focus_query`, `no_refocus_query`) get their own
  `substitute(owner, attr, fn)` helper next to `leaf()`.

`removed(cfg)` reuses the existing helper shape
(`tests/test_board_movement.py:1198-1201`); nothing about the ablation
arithmetic changes.

## Step 3 — run the campaign

```bash
AITASK_BOARD_BENCH=1 ~/.aitask/venv/bin/python -m unittest \
  tests.test_board_movement.BoardMovementBenchmarkTests.test_bench_attribution -v
```

- **5 repeats** of the whole attribution test. Record per run: every config's
  median + p90, the harness floor, `uptime` before/after, and the tier-2 shares.
- Report **median of run medians** and the **range**, exactly as t1243_5 did.
- Judge every removable-cost claim on the **within-run** delta; never compare a
  config in run 3 against a config in run 1.
- Run it in the background with plain `nohup`-style backgrounding (never
  `setsid` — it breaks completion tracking on this box) and kill by process
  group if it must be aborted.

## Step 4 — answer each named suspect, with the measurement

Produce one row per suspect. "Ruled out" requires a number, not an argument.

| suspect | verdict comes from |
|---|---|
| Textual board-wide layout after `AwaitMount.__await__` → `refresh(layout=True)` | `tree_self["reflow"]` + `tree_calls["reflow"]` per keypress |
| `_refocus_card`'s full-tree `query(TaskCard)` | `removed("no_refocus_query")` |
| focus-driven `scroll_visible` + up to 5 refresh hops | `tree_self["scroll_hop"]`, `scroll_hops` histogram |
| `_column_widgets()` four full-DOM queries | `tree_calls["col_widgets"]` — expected **0**; records the reachability correction |
| harness floor (`Pilot._wait_for_screen`) | already reported; subtract before any conclusion |
| **new:** focus → `refresh_bindings` → `Footer.recompose` → `active_bindings` → `check_action` × bindings | `removed("no_bindings")`, `removed("no_focus_query")`, `tree_calls["check_action"]`, `tree_calls["focus_query"]`, `tree_self["dom_query"]` |
| **new:** axis-asymmetric close (Context §3) | `scroll_hops` on lateral vs vertical, plus tier-2 shares measured on both axes in one `full` config |
| scroll animation | `animate=False` at both sites; confirm 0 animation frames |

## Step 5 — record the findings

Append a sibling H3 to `aiplans/p1243_board_task_groups_and_fast_reordering.md`,
in the same style as the two existing `### RECORDED …` sections, **at the end of
`## Workstream B — render cost`** — after the last line of
`### RECORDED RESULT — t1243_5 …` (currently ending
"**t1243_14 should consume t1395's findings rather than rediscover them.**") and
before the `---` that precedes `## Workstream C`:

```markdown
### RECORDED RESULT — t1395 residual move/layout cost attribution
```

It must contain: the attribution table (self-time share per span, per axis), the
ablation deltas with their ranges across the 5 runs, the harness floor per run,
the ambient load, the per-suspect verdict table from Step 4, the **reachability
correction** for `_column_widgets`, the axis-asymmetric-close finding, and the
recommendation.

## Step 6 — recommendation, and follow-ups only where a number justifies one

State one of:

- **Reducible** — name the span, the measured removable cost (with its range),
  and the expected win as a percentage of the 1162 ms median. File the follow-up
  task(s); each cites its measurement.
- **Inherent to Textual layout at this card count** — with the reflow/render
  self-time share and the widget count as the evidence.

"No follow-ups warranted", stated with the supporting numbers, is a successful
outcome. **Do not implement any optimisation in this task** — its acceptance
criteria are attribution + recommendation. If Step 3 shows a large, cheap win,
that is a follow-up task with its own target set from this measurement, per the
task's own AC ("No performance target is asserted for this task up front").

Also feed t1243_14 (`aiplans/p1243/p1243_14_retrospective_benchmark.md`) its
Step 4 answer — "which span now dominates" — and confirm its instruction to
retire or re-scope `R_pair` / `R_rm4` / `R_rm5`.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — full Python suite green
  (read **only** the last line; use `set -o pipefail` if piping).
- `python -m unittest tests.test_board_movement -v` (ungated) — the smoke bench
  and the two harness self-guards
  (`test_timed_region_never_calls_pilot_pause`,
  `test_pause_floor_assumption_still_holds`) still pass.
- **Baseline non-perturbation guard (load-bearing):** run
  `test_bench_baseline` once and confirm its printed banner is structurally
  identical to the pre-change one — same five configs, same span list, same
  verdict lines. The attribution tier must be provably absent from it.
- **Negative control on the new tier:** with `attribution=True`, inject a
  deliberate 50 ms sleep inside one instrumented function and confirm it shows
  up in that span's *self* time and nowhere else. A tier that cannot localise a
  known cost cannot be trusted to localise an unknown one.
- **Negative control on the ablations:** confirm each new ablation config still
  passes the stationarity check and the `writes > 0` invariant — an ablation
  that changed behaviour rather than cost must fail loudly.
- `shellcheck` — not applicable (no shell changes).

## Step 9 (Post-Implementation)

Commit code (`tests/test_board_movement.py`) with `performance: … (t1395)`, plan
and parent-plan edits via `./ait git` with an `ait:` prefix, merge to `main`,
archive.

## Final Implementation Notes

- **Actual work done:** one production-adjacent file — `tests/test_board_movement.py`
  (+350/−7, 12 hunks). **No production code was edited**; this task is an
  investigation and it changed nothing on the board's hot path.
  - `Probe.TREE` + self-time accounting in `Probe._enter`/`_exit`: a tier-2 span
    layer that nests properly (`bindings_sweep` → `check_action` → `focus_query`
    → `dom_query`) and charges each child's *total* to its parent, so tier-2
    self times are disjoint by construction. The pre-registered
    LEAVES-inside-LEAVES non-overlap check is preserved verbatim, now explicitly
    scoped so a tier-2 span nesting inside a leaf is not a false violation.
  - `_install_attribution()`: opt-in wrappers on `KanbanApp.check_action`,
    `_column_widgets`, `_refocus_card`, `_scroll_into_view_after_layout`,
    `_focused_card`, and on Textual's `Screen.active_bindings` /
    `_refresh_layout` / `_compositor_refresh`, `Compositor.reflow(_visible)`,
    `Footer.compose`, `DOMQuery.nodes`. Installed **last**, hence outermost, so
    the t1243_5 close wrappers keep their exact `scroll_pending` sequencing.
    Every Textual symbol goes through `_require()`, which raises with the
    Textual version rather than silently measuring nothing.
  - Two substitute-based ablations: `bindings` (no-op `Screen.refresh_bindings`)
    and `focus_query` (memoize `_focused_card` on focus identity).
  - New gated `test_bench_attribution`; new ungated
    `test_attribution_tier_localises_an_injected_cost` and
    `test_column_widgets_is_unreachable_from_the_move_path`.
  - `_sample` / `_validate` / `summarise` / `_bench` / `_child_main` thread the
    tier through; `_validate` gained one attribution-only invariant.

- **Deviations from plan:**
  1. **`no_refocus_query` ablation dropped.** The plan listed it as a config;
     the tier measured `_refocus_card` at **0.1 ms self / 1 call**, i.e. already
     three orders of magnitude below the target. Spending a whole 200-card child
     run to ablate it would have bought nothing. Reported as measured-and-ruled-out
     instead — which is what the acceptance criteria actually ask for.
  2. **A negative control and a reachability pin were added as real tests**, not
     as throwaway checks. The plan called for a one-off injected-sleep check; a
     test that runs in every suite run is what stops the tier rotting into a wall
     of zeros that reads as "attributed nothing".
  3. **Step 0.3's throwaway premise probe ran first and was load-bearing.** It
     confirmed `App.app_focus` is `True` under headless `run_test` — had it been
     `False`, `Footer.bindings_changed` would early-return and the strongest
     suspect would have been invisible to the harness. Building the tier before
     checking that would have risked a day's work on a dead premise.

- **Issues encountered:**
  1. **The task file's third named suspect was wrong.** `_column_widgets()` is
     unreachable from the move path — its callers trace to `_reanchor_to_viewport`
     / `_nav_lateral`, i.e. plain-arrow navigation, and the bench presses only
     `shift+`/`ctrl+` keys. Caught by call-site grep during planning, then
     confirmed by measurement (**0 calls, both axes**) rather than by argument.
  2. **The strongest suspect was named by nobody** — not t1243_1, t1243_4,
     t1243_5, nor this task's own file. It surfaced only from reading Textual's
     `set_focus` → `refresh_bindings` → `Footer.compose` → `active_bindings`
     chain against the board's 99 bindings and `check_action`'s 8
     `_focused_card()` sites.
  3. **Ambient load moved mid-campaign** (1.5 → 4.85 across the 5 runs). Run 4 is
     the low outlier on both ablations. Recorded rather than dropped, per this
     box's own rule, and the reason the campaign was 5 runs.
  4. **A concurrent session was editing `monitor/` and `website/` files in the
     same checkout.** The code commit was scoped to the single path this task
     owns; nothing of theirs was staged.

- **Key decisions:**
  - **The attribution tier is opt-in and lives in a separate gated test.**
    `test_bench_baseline` is what t1243_14 compares against 2173.2 / 1162.4 ms;
    instrumenting it would have moved the number silently and destroyed the
    comparison. Verified rather than assumed: a full baseline re-run printed a
    structurally identical banner (same five configs, same span list,
    `other=99.1 %` lateral, same three degenerate verdicts).
  - **Self time, not flat exclusive spans.** The suspects genuinely nest, so a
    flat tier would have had to choose between a false nesting violation and an
    unproved partition. Charging each child's total to its parent keeps
    non-overlap structural, which is what the task's method constraint demands.
  - **Ablations are substitutes, never no-ops, where behaviour matters.**
    `_focused_card` is memoized rather than stubbed; `check_action` is never
    ablated at all (it gates `move_task_right`, so a stub would change which
    actions dispatch). The stationarity and `writes > 0` invariants are the
    negative control that would have caught a semantic change, and they held.
  - **No optimisation was implemented here.** The task asserts no target up
    front; the fix carries its own target set from these numbers (t1402).

- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:7124-7127 — _focused_card() resolves the focused card with a full-tree query("TaskCard:focus"), and check_action (:6025) calls it from 8 sites. Via Screen.set_focus -> refresh_bindings -> Footer.compose -> active_bindings, one focus change costs 201 check_action invocations / 107 _focused_card calls / 123 cold full-tree walks = 587 ms (53.6%) of a 1129 ms lateral keypress on a 200-card board. Owned by t1402.`
  - `.aitask-scripts/board/aitask_board.py:7138-7147 — _column_widgets() issues four full-DOM class queries per call (~25 ms at 200 cards), three of which return empty in the normal kanban view. Reported by t1243_4, restated by t1243_5, and now proved to be a PLAIN-ARROW NAVIGATION cost, not a move-path one (0 calls on both move axes). Still unaddressed; no task filed because no nav-path measurement exists to set a target.`
  - `tests/test_board_movement.py:532 — _validate's docstring says "four per-sample validity invariants" while the body implements six (seven after this task). Cosmetic, but the docstring is cited as the method of record by three archived plans.`

- **Notes for sibling tasks:**
  - **t1243_14:** consume `### RECORDED RESULT — t1395 …` in the parent plan
    rather than rediscovering it; its Step 4 "which span dominates" is answered
    (`dom_query`, 53.6 %). Two things change how its table must be read: the
    **axis-asymmetric close** (vertical records 0 bindings sweeps because its
    window shuts before the deferred work — it is not "the cheap path"), and the
    confirmed degeneracy of `R_pair` / `R_rm4` / `R_rm5`. **t1402 is blocked on
    t1243_14** and that ordering is recorded in both task files.
  - **Anyone adding a span to this harness:** put it in `TREE`, not `LEAVES`,
    unless it provably cannot nest. `LEAVES` is a pre-registered flat partition
    four archived plans depend on.
  - **Anyone measuring on this box:** a single run adjudicates nothing. The
    lateral median ranged 1079.5-1505.0 ms across 5 runs of identical code.

## Post-Review Changes

### Change Request 1 (2026-08-04 07:58)

- **Requested by user:** create the measured follow-up now and explicitly
  coordinate its timing with t1243_14 — otherwise t1243_14 can report the
  finding, but the performance fix may drift into a later, unrelated task.
- **Changes made:**
  - Created **t1402 `board_focus_query_storm_on_move`** (`performance`,
    `priority: high`, `anchor: 1243` via `--followup-of 1395`,
    `gates: [risk_evaluated]`) carrying a **≥ 45 %** lateral target derived from
    this task's ablation figures, with the two candidate approaches, the
    strong-reference memo-key trap, and the `app.focused` ≠
    `query("TaskCard:focus")` modal caveat written down so the fix cannot be
    started from the wrong premise.
  - Wired the ordering **both ways** rather than only forward: t1402 declares
    `depends: [t1243_14]`, and t1243_14's task file gained a
    `## Coordination — t1395 (done) and t1402 (blocked on this task)` section
    stating why (a 45-76 % win from outside the workstream would make t1243_14's
    comparison table incomparable with the recorded baselines and would
    retroactively flatter t1243_5), plus the two measurement facts that change
    how its table must be read (the axis-asymmetric close; the degenerate gates).
  - Named t1402 in the parent plan's recommendation, and recorded why the
    `_column_widgets()` nav-path defect was deliberately **not** filed as a
    second follow-up: no nav-path measurement exists to set its target, and this
    workstream's rule is that a follow-up cites a number.
- **Files affected:** `aitasks/t1402_board_focus_query_storm_on_move.md` (new),
  `aitasks/t1243/t1243_14_retrospective_benchmark.md`,
  `aiplans/p1243_board_task_groups_and_fast_reordering.md`,
  `aiplans/p1395_board_residual_move_layout_cost.md`.

## Risk

### Code-health risk: low

- The change is confined to `tests/test_board_movement.py`; no production code is
  edited. · severity: low · → mitigation: TBD
- Monkeypatching Textual internals (`Compositor.reflow`, `Screen._refresh_layout`,
  `DOMQuery.nodes`, `Footer.compose`) pins the harness to Textual 8.2.7 and will
  break silently on upgrade. · severity: medium · → mitigation: resolve each
  target with `getattr` and fail loudly with the Textual version in the message
  if a symbol is missing, mirroring the existing
  `test_pause_floor_assumption_still_holds` guard.
- The `Probe._enter`/`_exit` change touches the pre-registered non-overlap proof
  that four prior children depend on. · severity: medium · → mitigation: the
  LEAVES-inside-LEAVES violation rule is preserved verbatim and the
  baseline-non-perturbation guard in Verification proves `test_bench_baseline`
  is unchanged.

### Goal-achievement risk: medium

- The dominant suspect may turn out to be inside Textual's compositor, where
  nothing is ablatable — the task would then land on "inherent", which is a valid
  but unsatisfying outcome. · severity: low · → mitigation: none needed; the AC
  explicitly accepts "inherent … with the evidence".
- Headless `run_test` may leave `App.app_focus` false, in which case
  `Footer.bindings_changed` early-returns and the strongest new suspect is
  invisible **to the harness** while still costing a real user. · severity: high
  · → mitigation: Step 0.3 checks this before anything is built on it; if it
  fires, record it as a harness-fidelity finding (the bench under-measures a real
  production cost) rather than silently dropping the suspect.
- Five repeats of a multi-config bench on a box carrying 4-5 ambient load is a
  long campaign whose results can still be contaminated. · severity: medium ·
  → mitigation: within-run ablation only, floor reported per run, load recorded
  before and after each run.
