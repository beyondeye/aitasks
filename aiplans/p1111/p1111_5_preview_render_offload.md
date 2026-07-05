---
Task: t1111_5_preview_render_offload.md
Parent Task: aitasks/t1111_monitor_ui_thread_offload_perf.md
Sibling Tasks: aitasks/t1111/t1111_*.md
Archived Sibling Plans: aiplans/archived/p1111/p1111_1_*.md, p1111_2_*.md, p1111_3_*.md, p1111_4_*.md
Worktree: aiwork/t1111_5_preview_render_offload
Branch: aitask/t1111_5_preview_render_offload
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-05 16:41
---

Offload the **preview render** (`_ansi_to_rich_text`) off the UI thread —
eliminates the active-agent focus-switch lag.

## Context
Part of t1111 (`ait monitor` UI-thread offload). **Depends on t1111_2 and t1111_4
— both landed/archived.** Empirical finding: with all agents idle the focus
switch is fast, but as soon as one agent is active the switch lags. Root cause:
the single `_update_content_preview` → `_ansi_to_rich_text`
(`monitor_shared.py:74-93`) → `Text.from_ansi` render of the focused pane runs on
the UI thread, and its cost scales with the ANSI-escape density of the content —
an active agent's churny/colored output parses expensively. t1111_2 removed the
*redundant second* render (there is now exactly one `_update_content_preview` per
focus switch, reached via `on_descendant_focus` → `_update_zone_indicators`
(app:1284)); this task removes that *single* render from the UI thread.

Even after t1111_4, `_fast_preview_refresh` (app:768) offloads only the *classify*
work, then calls the **synchronous** `_update_content_preview()` (app:792) which
still runs `_ansi_to_rich_text` on the loop — this is the exact remaining cost.

## Plan verified 2026-07-05 (fast/verify path)
Re-verified against current source. Findings folded into this plan:
- **Line anchors drifted ~40 lines** from the original task note; all corrected
  below. `_ansi_to_rich_text` at `monitor_shared.py:74-93` is **exact**.
- **`_ansi_to_rich_text` is already a pure module-level function** (`ansi_str -> Text`,
  no `self`/widget access) — no "pure builder split" is required; it is directly
  offloadable. The application step is `preview.update(text)` + scroll restore.
- **The t1111_4 seam is present exactly as its notes-for-siblings promised**:
  `TmuxMonitor._run_offloaded` (`monitor_core.py:983`, `async def _run_offloaded(self, fn)`
  → `await asyncio.to_thread(fn)`), the monitor-owned `_capture_generation`
  (core:923) + `_next_generation` (core:972) + `capture_generation` property
  (core:977), and the two-phase capture/commit methods.
- **`@work` is NOT imported or used anywhere** in `monitor_app.py`. The file's
  established async-offload idiom is `self.run_worker(coro, exclusive=..., group=...)`
  (app:560, app:594) plus the `_run_offloaded` seam. → **Drop the `@work`
  suggestion**; use `run_worker(exclusive=True, group="preview")` for native
  supersession.
- **Supersession token correction:** the monitor-owned `_capture_generation` is
  semantically a *capture* token (bumped every 0.3s fast-preview and every 3s full
  refresh). Reusing it to guard a *render* would spuriously discard renders while
  the pane content is unchanged. → Use a **new app-owned `_preview_render_gen`**
  counter for render supersession, alongside the existing focus-identity guard
  (`pane_id == self._focused_pane_id`, already at app:791). Reuse `_run_offloaded`
  (the offload seam) — not the capture generation.

## Key files to modify
- `.aitask-scripts/monitor/monitor_app.py` — `_update_content_preview` (1154-1239)
  and a new `async def _apply_preview_render`. `on_descendant_focus` (1419) and the
  other 5 callers (759, 792, 891, 918, 1284, 1493) are **unchanged** — the offload
  is centralized inside `_update_content_preview`, so every caller benefits without
  edits.
- `.aitask-scripts/monitor/monitor_shared.py` — **no change** (`_ansi_to_rich_text`
  is already pure and offloadable as-is).
- `tests/test_monitor_preview_offload.py` — new test file (pattern:
  `tests/test_monitor_finalize_offload.py`).

## Implementation step 0 — persist this refined plan first (concern 4)
This plan was refined on the verify path; the on-disk
`aiplans/p1111/p1111_5_preview_render_offload.md` still holds the **stale** design
(pure-builder split, `@work`, capture-generation reuse). **Before writing any code**,
externalize this refined plan over that file (+ append the `plan_verified` entry) and
commit it, so the archived record and the t1111_6 handoff reflect the real design —
never the superseded one. (The workflow's Save-Plan-to-External-File step does this
right after plan approval, before Step 7; this note pins it as a hard precondition.)

## Approach (offload only the pure render; keep all bookkeeping on the loop)

Only `_ansi_to_rich_text("\n".join(lines))` (app:1209) is CPU-heavy and pure.
Everything else in the active branch is cheap and reads/writes widget/instance
state, so it stays on the loop. The split is by *what is offloaded*, not by
introducing a new pure function.

### 1. New app state (in `__init__`, near app:443-448)
```python
self._preview_render_gen: int = 0   # bumped per scheduled preview render (supersession)
```

### 2. `_update_content_preview` stays SYNC; short-circuits before any offload
Header update (1175-1196), the no-focus early return (1162-1168), the frozen
branch (1198-1204), and the empty-content branch (1234-1237) are **unchanged** and
return **before** scheduling any offload (invariant: frozen/paused/header-only
never schedule a thread hop). The active non-empty branch (1206-1233) changes to:

```python
lines = snap.content.rstrip().splitlines()
if lines:
    preview.styles.min_width = snap.pane.width
    self._preview_rendered_lines = lines          # loop-side; drives scroll-anchor save
    self._preview_render_gen += 1                  # reserve a render generation
    my_gen = self._preview_render_gen
    pane_id = self._focused_pane_id
    if not same_pane:
        # Pane actually switched: clear stale pane-A body NOW so the (already
        # updated) header for pane B never sits above pane A's content while the
        # offloaded render is in flight (concern 3). Same-pane re-renders (0.3s
        # fast-preview tick) skip this to avoid flicker.
        preview.update("[dim]…[/]")
    self.run_worker(
        self._apply_preview_render(pane_id, "\n".join(lines), my_gen, saved, lines),
        exclusive=True, group="preview", exit_on_error=False,
    )
else:
    preview.styles.min_width = 0
    preview.update("[dim](empty)[/]")
    self._preview_rendered_lines = []
self._last_preview_pane_id = self._focused_pane_id
```
`min_width`, `_preview_rendered_lines`, and `_last_preview_pane_id` are set
**synchronously on the loop** (they derive from the snapshot, not from the render,
and `same_pane`/scroll-anchor logic must stay correct immediately). Only
`preview.update(text)` + scroll restore are deferred into the worker. `run_worker`
is already how this file fires async work (app:560/594).

**Cross-pane transient decision (concern 3):** on an actual pane switch
(`not same_pane`) we replace pane A's body with a one-glyph `…` placeholder
synchronously, so the header and body are never contradictory. The trade-off — a
sub-frame `…` flash vs. briefly showing the *wrong* pane's content under the new
header — favors the placeholder (correctness). On same-pane fast-preview ticks the
existing body is left in place (no flicker). This is the explicit, accepted design.

### 3. New `async def _apply_preview_render(self, pane_id, joined, my_gen, saved, lines)`
```python
async def _apply_preview_render(self, pane_id, joined, my_gen, saved, lines) -> None:
    if self._monitor is None:
        return
    if my_gen != self._preview_render_gen:         # already superseded while queued →
        return                                     #   don't even launch the thread (concern 2)
    try:
        text = await self._monitor._run_offloaded(lambda: _ansi_to_rich_text(joined))
    except Exception:
        text = Text(joined)                        # D: fail closed → raw text
    # back on the loop after the await:
    if my_gen != self._preview_render_gen:         # C: superseded by a newer render
        return
    if pane_id != self._focused_pane_id:           # focus moved during the offload
        return
    try:
        preview = self.query_one("#content-preview", PreviewPanel)
        scroll = self.query_one("#preview-scroll", PreviewScrollContainer)
    except Exception:
        return
    preview.update(text)
    # G: scroll restore AFTER preview.update, via call_after_refresh. The deferred
    # callbacks RE-CHECK gen + focused pane at execution time (concern 1) — a
    # call_after_refresh fires on a later refresh cycle, by which point focus may
    # have moved again, and scroll is a SHARED container, so an unguarded restore
    # would apply pane A's scroll position to pane B.
    def _guarded(action, g=my_gen, p=pane_id):
        if g == self._preview_render_gen and p == self._focused_pane_id:
            action()
    if saved is None or saved[0]:
        self.call_after_refresh(lambda: _guarded(lambda: scroll.scroll_end(animate=False)))
    else:
        target_idx = self._locate_anchor(lines, saved[1])
        if target_idx is None:
            self.call_after_refresh(lambda: _guarded(lambda: scroll.scroll_end(animate=False)))
        else:
            target_f = float(target_idx)
            self.call_after_refresh(
                lambda t=target_f: _guarded(lambda: scroll.scroll_to(y=t, animate=False))
            )
```
- **Pre-offload gen check (concern 2):** `run_worker(exclusive=True)` cancels the
  *coroutine*, but the heavy work runs in `asyncio.to_thread`, which is **not**
  cancellable — a thread already inside `Text.from_ansi` runs to completion. So
  exclusivity buys correctness (discard), not guaranteed CPU savings. The
  pre-offload `my_gen` check skips renders already superseded *while queued* (the
  common rapid-nav case, before the thread even starts); the residual waste is one
  in-flight thread per burst, which is bounded and acceptable. **Do not describe
  cancellation as the performance mitigation** — the generation guard is a
  *correctness* mechanism; the pre-offload check and `exclusive` are best-effort
  CPU reducers.
- Needs `Text` imported in `monitor_app.py` (verify at edit time; `_ansi_to_rich_text`
  is already imported at app:35 from `monitor.monitor_shared`).

## Concurrency & async safety contract (BINDING — invariants A–G, shared with t1111_4)
- **A** Only `_ansi_to_rich_text(joined)` runs off-loop; it is pure (no `self`, no
  widget access). All widget access (`preview.update`, `scroll`, `query_one`) and
  all instance-state writes happen on the loop, after the await.
- **B** `joined`, `saved`, `lines`, `pane_id`, `my_gen` are captured on the loop and
  passed **by value** into the worker — no off-loop `self._snapshots` access at all
  (stronger than "read `.get()` defensively"; the render never touches the dict).
- **C / F** Supersession = the app-owned monotonic `_preview_render_gen`, bumped at
  schedule time and checked **(i)** before launching the thread, **(ii)** after the
  await before `preview.update`, and **(iii)** inside each deferred scroll callback.
  A late/out-of-order render is discarded (never overwrites the current preview).
  `run_worker(exclusive=True, group="preview")` is a best-effort CPU reducer on top,
  **not** the correctness mechanism (the thread inside `to_thread` is not
  cancellable — see §3). Deterministic test seam = the injectable `_run_offloaded`
  (override to `_sync_offloaded` / gate for ordered resolution). **Test:
  stale-render discard + negative control.**
- **D** Fail closed: a raising `_ansi_to_rich_text`/`from_ansi` degrades to
  `Text(joined)` (raw text), never crashes the loop.
- **Focus-identity** `pane_id == self._focused_pane_id` guard prevents writing pane
  A's rendered content into the preview after focus moved to B during the offload —
  enforced both before `preview.update` AND inside the deferred scroll callbacks.
- **G** Scroll-restore `call_after_refresh` is scheduled AFTER `preview.update`, and
  each deferred callback re-checks gen + focused pane at **execution** time (a
  callback fires on a later refresh cycle when focus may have moved; `scroll` is a
  shared container). Render inputs are passed by value, so a concurrent `_snapshots`
  replacement (`self._snapshots = snaps` at app:706) can never `KeyError` this path.
- **No-offload short-circuit** the frozen/paused, header-only, no-focus, and
  empty-content paths return before `run_worker` — no thread hop when nothing
  renders.

## Verification (tests) — `tests/test_monitor_preview_offload.py`
Follow `tests/test_monitor_finalize_offload.py`: `unittest`, `IsolatedAsyncioTestCase`
for async, the `_sync_offloaded` seam + `_gate()` event for ordered resolution (no
sleeps), negative controls by bypassing the guard. Run via
`bash tests/run_all_python_tests.sh` (also standalone `python -m unittest`).
- **(a)** unit-test `_ansi_to_rich_text` on ANSI-heavy fixtures (inline `"\x1b[..m"`
  literals) — dark-bg injection + reset re-apply produce a stable `Text`.
- **(b)** render-equivalence: `_apply_preview_render` (with `_sync_offloaded`) yields
  the same `Text` (`.plain` + spans) that the prior synchronous path produced from
  the same `lines`.
- **(c)** stale-render discard: schedule render for pane A (genN), then pane B
  (genN+1); resolve A last via `_gate()` → preview shows B; A's apply is refused by
  the `_preview_render_gen` check. **Negative control**: bypass the gen check → A's
  stale content clobbers B (proves the guard is load-bearing). Mirror the
  same-pane variant (two renders for one pane, out of order).
- **(d)** frozen/paused, header-only, no-focus, and empty-content branches never
  schedule an offload — spy that `_run_offloaded` / `run_worker` is not invoked.
  Drive via `MonitorApp` `app.run_test()` (see `FastPreviewFocusIdentityTests`),
  seeding a paused/`same_pane` snapshot.
- **(e)** focus-identity: focus flips A→B during the offload await → `_apply_preview_render`
  for A does NOT call `preview.update` (pane_id != focused).
- **(f)** deferred-scroll guard: `_apply_preview_render` for A commits `preview.update`
  and schedules its `call_after_refresh` scroll restore; before the callback runs,
  bump `_preview_render_gen` / flip `_focused_pane_id` (simulating a switch to B) →
  the guarded callback is a no-op (no `scroll_to`/`scroll_end` on B's container).
  Negative control: without the in-callback guard, the scroll IS applied.
- **(g)** scheduling-path (production sync entry): drive the real
  `_update_content_preview` via `app.run_test()` with an active non-empty focused
  snapshot; assert it schedules **exactly one** preview render (spy `run_worker` /
  `_apply_preview_render`) and that `preview.update(text)` is reached through that
  worker — i.e. the sync entry point hands off correctly, not just the helper in
  isolation. Assert the cross-pane placeholder path (`not same_pane` → synchronous
  `…`) and that same-pane fast-preview ticks do NOT emit the placeholder.
- py-spy NOT required (not installed; t1111_4 deferred it). Behavioral proof is the
  deterministic unittest suite; live "switching among active agents stays instant"
  is covered by sibling **t1111_6** (manual verification).

## Step 9 (Post-Implementation)
Standard cleanup/archival/merge per task-workflow Step 9. Child task — write
comprehensive Final Implementation Notes (what changed, the app-owned
`_preview_render_gen` decision vs reusing capture-gen, the `run_worker` vs `@work`
choice) so the parent's remaining child (t1111_6) has full context.

## Risk

### Code-health risk: medium
- Extends the threading/offload pattern to the **render** path. Mitigated by
  reusing the landed t1111_4 seam (`_run_offloaded`) unchanged and by keeping the
  offloaded unit *purely* `_ansi_to_rich_text` (already a pure function) — no new
  pure-builder surface, no widget access off-loop. Supersession is a **structural**
  app-owned generation guard + native `run_worker` exclusivity (bad interleavings
  can't overwrite the current preview), not a fragile timing invariant. Blast
  radius: one method + one new async helper in a single file; the 6 existing
  callers are untouched. · severity: medium · → mitigation: inline (invariants A–G,
  `_run_offloaded` reuse, stale-render discard test **with negative control**,
  fail-closed test).
- New app state (`_preview_render_gen`) + one async method must stay idiomatic. ·
  severity: low · → mitigation: inline (mirrors the established `run_worker`/seam
  patterns already in the file).

### Goal-achievement risk: medium
- Removes the focus-switch lag **only if** `_ansi_to_rich_text` (`Text.from_ansi` +
  per-line regex) is the dominant on-loop cost of the switch. t1111_2 already
  removed the double render and t1111_4 offloaded classify, so this render is the
  last known on-loop CPU on the switch path — but capture serialization on the
  single `tmux -C` channel is a separate t1111 lever. · severity: medium · →
  mitigation: inline (t1111_6 confirms the behavioral outcome with ≥1 active agent).

_Risk-gated: declares `risk_evaluated`. No separate before/after mitigation tasks —
all mitigations are in-scope inline work (invariants, tests)._
