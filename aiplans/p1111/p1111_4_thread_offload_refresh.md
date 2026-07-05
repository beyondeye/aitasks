---
Task: t1111_4_thread_offload_refresh.md
Parent Task: aitasks/t1111_monitor_ui_thread_offload_perf.md
Sibling Tasks: aitasks/t1111/t1111_5_preview_render_offload.md, aitasks/t1111/t1111_6_manual_verification_monitor_offload.md
Archived Sibling Plans: aiplans/archived/p1111/p1111_1_gate_ledger_mtime_cache.md, aiplans/archived/p1111/p1111_2_focus_switch_double_render.md, aiplans/archived/p1111/p1111_3_kill_sync_tmux_in_refresh.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-07-03 12:37
---

**Thread-offload** the refresh CPU work (strip/prompt-regex) off the UI thread —
primary freeze lever. Establishes the codebase's first UI-thread offload pattern.

## Context
Part of t1111 (`ait monitor` UI-thread offload). `_finalize_capture`
(`monitor_core.py:1207-1248`) runs `_strip_ansi` (regex over the full capture) + a
prompt-pattern regex scan **per agent, per tick**, inside the awaiting coroutine on
the UI thread — the CPU core of the 3s freeze. Move the pure work off the loop.
**Depends on t1111_1 (gate mtime-cache) and t1111_3 (sync-tmux removal), both landed**
so the offload sits on an already-cleaned refresh path. The sibling **t1111_5**
reuses the serialization + offload seam this task establishes.

_Verified 2026-07-03 (fast/verify path). Line numbers refreshed after t1111_3.
`_run_offloaded` / `_capture_generation` / any worker are confirmed **absent** —
this task introduces them. **Plan revised after two review rounds** to fix safety
defects: (1) `_refresh_data` does loop-side DOM work so it must NOT become a
`thread=True` worker; (2) the stale-write guard must gate the `_last_content`
bookkeeping commit; (3) the 0.3s `_fast_preview_refresh` path must get the same
offload/guard discipline without changing `capture_pane_async`'s tested contract;
(4) the single `to_thread` classify batch needs per-pane fail-closed isolation;
(5) **the generation token lives in `TmuxMonitor`, not MonitorApp** — because
`capture_all_async` is a side-effecting public API and `minimonitor_app.py` is a
**separate app instance** with its own overlapping refresh loop, so the guard
must protect the state at its source. This protects the `_last_content`
bookkeeping with no caller change; the **returned snapshot dict** additionally
needs a stale signal — `capture_all_async` returns `None` when superseded, and the
two external callers (`minimonitor_app.py`, `applink/pusher.py`) get a one-line
"skip if `None`" guard so an older overlapping call can't overwrite their visible
snapshot state; (6) **every** capture path bumps the shared
token at start so the last-started capture wins (fast-preview vs full-refresh
supersession); (7) fast preview pins the focused pane id across its await window;
(8) **every** finalizing API participates in the token, ordered by **reservation
time** not write time — sync `capture_pane`/`_finalize_capture` (incl.
`applink/router.py:572`) bumps atomically at write; **async** finalizers
(`capture_pane_async` and the produce phases) reserve BEFORE their tmux await and
commit-guarded, so a late-returning stale async capture can't clobber a
newer-reserved refresh._

## Key files to modify
- `.aitask-scripts/monitor/monitor_core.py` (`_finalize_capture` @1207,
  `capture_pane_async` @1281, `capture_all_async` @1359 — plus two new methods,
  see below).
- `.aitask-scripts/monitor/monitor_app.py` (`_refresh_data` @687,
  `_fast_preview_refresh` @757; add the shared offload seam + in-flight guard +
  generation token).
- `.aitask-scripts/monitor/minimonitor_app.py` (`_refresh_data` @424, the
  `capture_all_async` @431 call site) and `.aitask-scripts/applink/pusher.py`
  (@153) — add a one-line "skip if `capture_all_async` returned `None`
  (superseded)" guard so a stale overlapping call can't overwrite visible
  snapshots. Minimal change; no offload logic in these callers.

**Contract-preservation constraints (verified callers):**
- `capture_all_async` is also called by `applink/pusher.py:153` and
  `minimonitor_app.py:431`, each a **separate app/instance** with its own
  `TmuxMonitor` and its own overlapping `set_interval`+`call_later` refresh loop.
  Its finalize + bookkeeping behavior is preserved on the **non-superseded** path,
  but its **return type intentionally changes to `dict | None`**: it returns
  `None` when a newer overlapping capture supersedes it (guarded by the
  TmuxMonitor-owned generation token, which protects `_last_content` AND the
  returned snapshot set). This is a deliberate contract change, NOT a drop-in
  no-op — the two external call sites each take a **one-line `None` guard**
  (`snaps = await …; if snaps is None: return`) so a stale overlapping call cannot
  overwrite their visible snapshots. Record this in Final Implementation Notes.
- `capture_pane_async` finalizing `_last_content` is asserted by
  `tests/test_applink_pusher.sh:784` — keep it finalizing, but make it
  **reserve `gen` before its `_tmux_async` await and commit-guarded** (line 1287
  awaits before `_finalize_capture` at 1290). Under no overlap (the test's case)
  `gen` is still current → it writes exactly as today → test passes; under overlap
  a superseding capture makes its stale write skip. After this task,
  `_fast_preview_refresh` and `capture_all` no longer call it (they use the raw /
  classified paths), so its only remaining caller is the applink test — but the
  reserve-before-await fix makes it correct for any future caller rather than
  relying on a no-overlap proof.
- `capture_pane` (sync) finalizes too and is used by `applink/router.py:572`
  (`get_history`-style scrollback) and sync `capture_all` (monitor_core.py:1354).
- `_finalize_capture(pane, content) -> PaneSnapshot` is exercised directly by
  `tests/test_prompt_detection.py` and `tests/test_idle_compare_modes.py` — it
  must remain sync and behavior-identical (return value + `_last_content`
  semantics unchanged); it just calls the new pure helper internally **and** bumps
  the generation token (see §2) — an internal counter bump invisible to those
  assertions.

## Approach (safety-first — offload only the pure work)

### 1. Extract a module-level pure classifier
`classify_content(content, mode, prompt_patterns, category) -> ClassifyResult`
where `ClassifyResult` carries `compare_value`, `awaiting_input`,
`awaiting_input_kind`. No `self`, no shared-dict mutation, no widget access. It
holds exactly the CPU work now inside `_finalize_capture`: `_strip_ansi(content)`
for the compare value (when `mode == COMPARE_MODE_STRIPPED`), plus the
`_prompt_detection_text` + prompt-pattern regex loop, gated on
`category == PaneCategory.AGENT` (mirrors `monitor_core.py:1231`).
`_finalize_capture` stays sync and keeps the **loop-owned bookkeeping** — the
`_last_content`/`_last_change_time` compare-and-set, `idle_seconds`, and
`PaneSnapshot` assembly — calling `classify_content` for the pure part. Sync
`capture_pane`/`capture_all` and the direct unit tests are unaffected.

### 2. Monitor-owned generation token (fixes stale-write at its source)
The token that discards superseded captures lives on **`TmuxMonitor`**, beside
the `_last_content`/`_last_change_time` state it protects — NOT on MonitorApp —
so every caller (main monitor, minimonitor, pusher) is protected uniformly:

- `self._capture_generation: int = 0` on TmuxMonitor.
- `def _next_generation(self) -> int:` bumps and returns it (called at the START
  of every async capture path — §3/§4 — and inside the sync `_finalize_capture`).
- read-only `capture_generation` property so callers can compare without touching
  a private attr.

**Protocol invariant — ALL finalizing writes participate. Reservation marks when
the captured content is "as of," and orders the writes — NOT the write instant.**
Two flavors:
- **Sync, no await between fetch and write** (`capture_pane` → `_finalize_capture`,
  incl. `applink/router.py:572` and sync `capture_all`): fetch and write are
  atomic on the loop, so reservation == write instant. `_finalize_capture`
  **bumps the token as it writes** — it genuinely is the newest at that instant,
  and the bump refuses any older in-flight async commit.
- **Async, an await separates fetch from write** (`capture_pane_async`,
  `capture_all_classified_async`, `capture_pane_classified_async`): these **reserve
  a `gen` BEFORE the tmux await** and their guarded commit writes bookkeeping
  **only if** `gen` still equals `capture_generation`. Reserving *after* the await
  (bumping at `_finalize_capture` time) would be a bug: an async capture that
  fetched old content early but returns late would clobber a newer full refresh
  — its content is stale even though its write is late. `capture_pane_async` in
  particular MUST move to reserve-before-await + guarded commit (it currently
  bumps at `_finalize_capture`, post-await — see fix below).

Net invariant: the finalize/commit whose **reservation is latest** owns
`_last_content`; a capture that reserved earlier can never overwrite one that
reserved later, whichever API produced it and however long its await took.

### 3. Two-phase async capture (offload produce, guard the commit)
Split the async batch into an **offloadable produce phase** and a **loop-side,
generation-guarded commit phase**, so `_last_content` is never written by a
superseded cycle:

- `async def capture_all_classified_async(self) -> tuple[int, list[ClassifiedRaw]]`
  — `gen = self._next_generation()`; `discover_panes_async`; gather raw
  `(pane, content)` via `capture_pane_content_async` (existing non-finalizing raw
  fetch) under `gather(return_exceptions=True)`; read each pane's `mode`/`category`
  **on the loop**; run ONE `_run_offloaded` batch of `classify_content` off-loop.
  Returns `(gen, [(pane, content, ClassifyResult)])` — **no `_last_content`
  mutation, no `_clean_stale`**.
- `def commit_snapshots(self, gen, classified) -> dict[str, PaneSnapshot] | None`
  — loop-side. **If `gen != self._capture_generation`** (a newer capture reserved
  after this one) → return `None` and touch nothing (idle clock AND returned set
  both protected — no stale snapshots handed back). Otherwise perform the stateful
  bookkeeping — `_clean_stale` + the `_last_content`/`_last_change_time`
  compare-and-set (formerly in `_finalize_capture`) — and return the assembled
  `dict`.
- `capture_all_async` becomes `dict | None`:
  `gen, c = await self.capture_all_classified_async(); return self.commit_snapshots(gen, c)`.
  For a serial caller `gen` is always current → dict, full bookkeeping (identical
  to today, now internally offloaded). For **overlapping** calls (minimonitor's
  own stacked `call_later` + interval), the later call reserved a newer token, so
  the earlier one returns `None`; its caller skips applying it → **no out-of-order
  `_last_content` corruption AND no stale visible snapshots**. This is a real
  contract change (return is now `Optional`); the two external call sites take a
  one-line `None` guard (see Key files). MonitorApp's two-phase path checks the
  generation *before* calling `commit_snapshots`, so it only commits when current
  and never receives `None`.

`_refresh_data` **stays a loop coroutine** (it owns DOM rebuilds / preview /
`call_after_refresh`); it is NOT a `thread=True` worker. It uses the two-phase
form and short-circuits the DOM rebuild when superseded:
```
gen, classified = await self._monitor.capture_all_classified_async()   # bumps + offloads
if self._monitor.capture_generation != gen:   # a newer capture started
    return                                     # skip rebuild; commit refused anyway
self._snapshots = self._monitor.commit_snapshots(gen, classified)      # guarded write
# …rebuilds / preview / call_after_refresh as today
```
Optional idiomatic supersession: wrap produce+commit in
`@work(exclusive=True, group="refresh")` as an **async** worker (never
`thread=True`) for native cancellation. The monitor-owned generation guard is the
mechanism that actually protects the bookkeeping and is REQUIRED even if `@work`
is used (the non-worker preview-timer path relies on it).

### 4. Fast preview path — same token, pinned pane id (fixes preview races)
`_fast_preview_refresh` (0.3s, focused pane only) must not run strip/regex on the
loop, must **bump the same token** so it supersedes/loses correctly against a full
refresh, and must **pin the focused pane id** across its lengthened await window:
```
pane_id = self._focused_pane_id                # pin BEFORE awaiting
if pane_id is None: return
gen, pane, content, result = \
    await self._monitor.capture_pane_classified_async(pane_id)   # bumps token, offloads
if pane is None: return
if self._monitor.capture_generation != gen:    # a newer capture started → discard
    return
snap = self._monitor.commit_snapshot(gen, pane, content, result)  # guarded single write
self._snapshots[pane_id] = snap                # write under the PINNED id
if pane_id == self._focused_pane_id:           # focus-identity guard
    self._update_content_preview()             # only touch UI if focus didn't move
```
- Bumping the shared token at start means a full refresh started **earlier** is
  refused at commit (and vice-versa) — last-started capture wins (concern: fast
  preview must supersede full refresh).
- Pinning `pane_id` + the focus-identity guard prevent committing a snapshot for
  pane A while the preview UI is updated for pane B after a focus change during
  the await.
- Add `capture_pane_classified_async(pane_id) -> (gen, pane, content, result)`
  (reserves token BEFORE its raw-fetch await via `capture_pane_content_async`;
  single offloaded `classify_content`) and
  `commit_snapshot(gen, pane, content, result) -> PaneSnapshot | None` (guarded
  single-pane bookkeeping; `None` when stale, symmetric with `commit_snapshots`)
  on TmuxMonitor. `capture_pane_async` gets the reserve-before-await fix (§2).

### 5. Single injectable offload seam
`async def _run_offloaded(self, fn)` on TmuxMonitor wraps `asyncio.to_thread(fn)`;
tests override it to run `fn` synchronously and to control resolution order. All
offloads (batch and single-pane) route through it.

## Concurrency & async safety contract (BINDING — invariants A–G)
- **A** Workers are pure compute (`classify_content`); the loop owns ALL
  widget/DOM/reactive access AND all `_last_content`/`_last_change_time` writes
  (in `commit_snapshots`). `_refresh_data` is a loop coroutine, never a
  `thread=True` worker.
- **B** `mode` (`get_compare_mode`) and `prompt_patterns` are read on the loop and
  passed **by value** into the offloaded fn; `prompt_patterns` treated read-only.
- **C** Serialization = a monotonic `_capture_generation` **owned by TmuxMonitor**
  (beside the state it guards), and writes are ordered by **reservation time, not
  write time**. A capture reserves a `gen` at the instant its content is "as of":
  - **Async** paths (`capture_all_classified_async`, `capture_pane_classified_async`,
    `capture_pane_async`) reserve **before their tmux await**; their guarded commit
    writes bookkeeping only if `gen` still equals the current token.
  - **Sync** `capture_pane`/`_finalize_capture` has no await between fetch and
    write, so reservation == write instant: it bumps-and-writes atomically.

  The capture with the **latest reservation** owns `_last_content`; one that
  reserved earlier can never overwrite it, no matter how late its await returns or
  which caller/API (main monitor, minimonitor, pusher, applink router) ran it.
  Optionally + async `@work(exclusive=True)`. Test: out-of-order regression +
  **negative control**; overlapping `capture_all_async`; fast-preview superseding
  a full refresh; sync-finalize superseding an in-flight offload;
  `capture_pane_async` reserve-before-await ordering.
- **D** Fail closed **per pane**: the offloaded batch wraps EACH pane's
  `classify_content` in try/except and degrades that pane to raw content
  (`compare_value=content`, `awaiting_input=False`) — one malformed pane never
  fails the batch. `capture_all_classified_async` keeps
  `gather(return_exceptions=True)` for the tmux fetch layer. Two independent
  failure layers (fetch + classify), both isolated per pane.
- **E** Bounded concurrency: exactly one offload batch per cycle (no per-pane
  thread fan-out); the shared guard coalesces bursts from the ~8 call sites.
- **F** Deterministic test seam `_run_offloaded`; no sleep-based timing in tests.
- **G** Preserve `call_after_refresh` sequencing (monitor_app.py:753); read
  `_snapshots.get()` defensively.

## py-spy verification (inside this child; before AND after; not a gate)
1. BEFORE editing `_finalize_capture`, sample the UI/event-loop thread during a 3s
   tick (must be on pre-fix code).
2. After the offload, re-sample; confirm strip/prompt regex no longer on the loop
   thread (they appear on a worker/`to_thread` thread instead).
Record both in Final Implementation Notes; if py-spy unavailable, fall back to
t1111_6 behavioral checks.

**Live-agent setup recipe (panes must classify as AGENT — `classify_pane`
(`monitor_core.py:1000`) decides by WINDOW NAME starting with `agent-`; a
non-`agent-` window yields OTHER panes and skips the agent-only idle+prompt scan
at `_finalize_capture:1231`):**
```
tmux new-session -d -s t1111perf -n agent-perf-1 'while true; do date; sleep 0.2; done'
for i in $(seq 2 8); do tmux new-window -t t1111perf -n "agent-perf-$i" 'while true; do date; sleep 0.2; done'; done
# launch ait monitor against that session, then:
py-spy record -o before.svg --pid <monitor_pid> --duration 15   # (or py-spy dump --pid <pid>)
tmux kill-session -t t1111perf
```

## Verification (tests)
New `tests/test_monitor_finalize_offload.py`:
- (a) unit-test `classify_content` headlessly — ANSI strips correctly, each prompt
  pattern detected, no-match returns clean, **non-AGENT category skips the prompt
  scan**.
- (b) golden equivalence — for the same raw inputs, `gen, c = await
  capture_all_classified_async(); commit_snapshots(gen, c)` (gen current) yields
  `PaneSnapshot`s identical to the prior synchronous `capture_all` finalize.
- (c) idle/`_last_change_time` bookkeeping still updates on content change (via
  `commit_snapshots`), and is NOT updated by a discarded (stale-generation) cycle.
- (d) **out-of-order serialization regression** — two overlapping cycles whose
  offloaded results resolve in reverse order → stale result discarded by the
  monitor-owned generation check **before commit**, `_last_content` holds the
  newer content, idle clock not reset — WITH a **negative control** that bypasses
  the generation check and reproduces the stale `_last_content` write.
- (e) **overlapping `capture_all_async`** (external-caller safety) — two
  `capture_all_async` calls on the SAME TmuxMonitor resolving in reverse order:
  the earlier (older-reservation) call **returns `None`** and `_last_content`
  reflects the later capture; assert a minimonitor-style caller
  (`snaps = await …; if snaps is None: return; self._snapshots = snaps`) keeps the
  newer snapshots and never stores stale/None. Guards minimonitor's own
  overlapping refresh loop and the applink pusher.
- (f) **fast-preview supersedes full refresh** — a full `_refresh_data` starts
  (gen N), then `_fast_preview_refresh` starts (gen N+1) and commits focused-pane
  content; when the older full refresh resolves it fails the gen check and does
  NOT overwrite `_last_content` for the focused pane. Negative control without the
  bump reproduces the stale overwrite.
- (g) **fast-preview focus identity** — focus moves from pane A to pane B during
  the offload await: the snapshot is committed under A's pinned id and
  `_update_content_preview` is NOT called (focus is now B), so no cross-pane UI
  write.
- (g2) **sync-finalize supersedes in-flight offload** — a full `_refresh_data`
  reserves gen N and is mid-offload; a `capture_pane` (sync, e.g. router
  scrollback) finalizes the focused pane (bumps to N+1, writes newer bookkeeping);
  when the full refresh resolves, its gen-N commit is refused and does NOT clobber
  the single-pane write. Negative control (finalize without the bump) reproduces
  the clobber.
- (g3) **async reserve-before-await ordering** — `capture_pane_async` reserves
  gen N before its tmux await (fetching OLD content); a newer full refresh
  reserves N+1 and commits NEWER content; when `capture_pane_async` finally
  returns, its gen-N guarded commit is refused → the newer content survives.
  Negative control (reserve at `_finalize_capture` time, post-await) reproduces
  the stale-late clobber the review caught. Drive resolution order via the
  `_run_offloaded`/fetch seam (invariant F), no sleeps.
- (h) **per-pane fail-closed** — a batch where one pane's `classify_content`
  raises: that pane degrades to raw content, all other panes classify normally,
  the refresh is not dropped.
Follow `aidocs/framework/testing_conventions.md` for asyncio/thread test shape;
drive all timing through the `_run_offloaded` seam (invariant F).

## Step 9 (Post-Implementation)
Standard cleanup/archival/merge per task-workflow Step 9. Child task — write
comprehensive Final Implementation Notes incl. py-spy before/after and a
"Notes for sibling tasks" entry documenting the `_run_offloaded` seam, the
two-phase `capture_all_classified_async`/`commit_snapshots` split, and the
generation-token-before-commit discipline for **t1111_5** to reuse.

## Risk

### Code-health risk: medium
- First **threading** pattern in the codebase (t1111_3 added async, not threads);
  correct single-writer discipline for `_last_content`/`_last_change_time` is the
  hazard. The two-phase produce/commit split + generation-guard-before-commit is a
  **structural** fix (bad interleavings can't write bookkeeping) rather than a
  fragile invariant, which lowers this from what a whole-method-threaded approach
  would carry. Bounded blast radius (two monitor files; external callers of
  `capture_all_async`/`capture_pane_async` kept contract-stable). · severity:
  medium · → mitigation: inline (invariants A–G + `_run_offloaded` seam +
  out-of-order regression **with negative control** + per-pane fail-closed test)
- New abstraction surface (`_run_offloaded`, `capture_all_classified_async` /
  `commit_snapshots`, `_capture_generation`) must stay idiomatic and be reused
  unchanged by t1111_5. · severity: low · → mitigation: inline (single shared
  seam; documented in Notes-for-sibling-tasks)

### Goal-achievement risk: medium
- The offload only removes the freeze **if** `classify_content` (strip + prompt
  regex) is the dominant per-tick CPU cost. Capture serialization on the single
  `tmux -C` channel is a **separate** t1111 lever (parent fix #1), so this task
  alone may not fully eliminate the freeze. · severity: medium · → mitigation:
  inline (py-spy before/after confirms the CPU moved off-loop; t1111_6 confirms
  the behavioral outcome)

_Risk-gated: declares `risk_evaluated`. No separate before/after mitigation
tasks — all mitigations are in-scope inline work (invariants, tests, py-spy)._

## Final Implementation Notes
- **Actual work done:** Implemented the full two-phase offload as planned.
  `monitor_core.py`: module-level pure `classify_content` + `ClassifyResult`
  (with per-pane fail-closed `_classify_one`/`_classify_batch`); the injectable
  `_run_offloaded` seam; TmuxMonitor-owned `_capture_generation` +
  `_next_generation()` + read-only `capture_generation` property; two-phase
  `capture_all_classified_async` (produce/offload) + generation-guarded
  `commit_snapshots` (loop-side commit, `None` when superseded); single-pane
  `capture_pane_classified_async` + `commit_snapshot`; `capture_pane_async`
  moved to reserve-before-await + guarded commit; `capture_all_async` return
  type now `dict | None`. `monitor_app.py`: `_refresh_data` stays a loop
  coroutine using the two-phase form with a pre-commit generation check;
  `_fast_preview_refresh` bumps the shared token, pins the focused pane id, and
  applies the focus-identity guard. `minimonitor_app.py` and `applink/pusher.py`
  each take the one-line `snaps is None → return` supersession guard.
- **Deviations from plan:** None material. The `capture_all_async` contract
  change (`dict | None`) landed exactly as designed; external call sites updated.
- **Issues encountered:** This task was finalized in a **resumed session** after
  the original implementing agent crashed (same-host reclaim of a dead PID). The
  reclaim was accepted with prior uncommitted work intact; the implementation
  was already complete on the working tree. No code changes were needed on
  resume — only verification, attribution, and commit.
- **Key decisions:** The generation token lives on `TmuxMonitor` (not
  MonitorApp) so `_last_content`/`_last_change_time` are protected at their
  source across all three app instances (monitor, minimonitor, pusher). Writes
  are ordered by **reservation time**, not write time — async paths reserve
  before their tmux await; sync `_finalize_capture` bumps-and-writes atomically.
- **py-spy verification:** NOT captured in this resumed session — the py-spy
  before/after recipe requires a live interactive `ait monitor` + tmux
  `agent-*` session, and no pre-fix baseline survived the crash. Per the plan's
  explicit fallback, the behavioral confirmation that the freeze is removed
  defers to sibling **t1111_6** (manual verification of the monitor offload).
- **Upstream defects identified:** None.
- **Notes for sibling tasks (t1111_5):** Reuse the established seam unchanged:
  (1) `_run_offloaded(fn)` on TmuxMonitor is the single offload point — route the
  preview-render offload through it; (2) the two-phase
  `capture_*_classified_async` (reserve gen + offload produce) → `commit_*`
  (generation-guarded loop-side commit, returns `None` when superseded) split is
  the pattern to follow; (3) the generation-token-**before-commit** discipline
  (reserve before await, guard at commit, order by reservation time) is REQUIRED
  for any new finalizing path — do not bump at write time. `_capture_generation`
  is monitor-owned; bump it at the START of every new capture path.
