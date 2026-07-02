---
Task: t1111_monitor_ui_thread_offload_perf.md
Worktree: aiwork/t1111_monitor_ui_thread_offload_perf
Branch: aitask/t1111_monitor_ui_thread_offload_perf
Base branch: main
---

# Plan — t1111: `ait monitor` UI-thread offload (performance)

## Context

`ait monitor` (`.aitask-scripts/monitor/monitor_app.py`, class `MonitorApp`) gets
sluggish as the number of monitored agents grows: a ~0.5s lag on focus-switch and
a longer freeze on every 3s status refresh. Root cause: CPU/IO work runs on the
Textual **event-loop (UI) thread** and scales with agent count. The tmux `-C`
control backend already runs on a background thread (t719_2), but result
processing, formatting, gate-ledger disk reads, and several *synchronous* tmux
round-trips still execute on the UI loop.

The codebase has **no** thread-offload pattern today — the only `run_worker`
calls (`monitor_app.py:558,592`) wrap coroutines that run on the same UI loop.
So "async" work like `capture_all_async` still blocks the loop for all its Python
CPU (regex strip + prompt scan in `_finalize_capture`, gate reads).

**Empirical nuance (user observation, confirmed coherent):** with **all agents
idle**, the focus-switch is *fast* and only the 3s tick stays sluggish; **as soon
as one agent is active**, the switch lags again. This is consistent with — and
sharpens — the diagnosis. The switch cost is `_update_content_preview` →
`_ansi_to_rich_text` (`monitor_shared.py:74-93`) → `Text.from_ansi` over the
focused pane's capture, whose cost scales with the **ANSI-escape density** of the
content: an idle pane's settled screen parses cheaply, an active agent's churny,
color/spinner-heavy output parses expensively — all on the UI thread. The 3s tick
freeze is activity-independent (capture + strip + prompt-regex + gate reads run for
every pane every tick regardless), which is why it persists even when idle.
**Consequence for scope:** killing the *redundant* second render (t1111_2) only
halves the switch cost; eliminating the active-agent lag requires moving the single
`_ansi_to_rich_text` render itself off the UI thread (t1111_5 below) — the same
offload pattern as fix #1, applied to the preview/switch render path.

**Decision (confirmed with user):** decompose into children by testability seam;
proceed on the static analysis (py-spy is an optional verification step inside the
offload child, not a gate); **defer** tiered polling (#5 — coordinate with
t719_3/t719_4) and minimonitor propagation (follow-ups, not children here).

Intended outcome: focus-switch is instant and the 3s tick no longer freezes
input, at typical (5–15) agent counts.

## Note — shared files (staging constraint resolved)

The shadow-agent work that previously dirtied `monitor_core.py`,
`monitor_shared.py`, `minimonitor_app.py`, `tmux_monitor.py` is now **committed**
(t1104 / t1035 etc.); the working tree is clean. Normal `git add <file>` staging
is fine — the earlier "stage your own hunks only" caveat no longer applies. These
files remain under active development, so each child should `git pull`/rebase
before its commit; nothing more.

## Decomposition

Five implementation children (fixes land cheap→clean first, riskiest last) plus an
aggregate manual-verification sibling. Siblings auto-depend in order; t1111_4
additionally depends on 1111_1 and 1111_3; t1111_5 depends on 1111_2 and 1111_4
(reuses the thread-offload pattern + serialization helpers established there).

### t1111_1 — Gate-ledger mtime cache  (fix #3; low risk; pull first)

**Problem:** `_refresh_data` calls `self._gate_cache.clear()` every tick
(`monitor_app.py:702`), so `GateSummaryCache.summary_for` re-reads each visible
gated task's ledger from disk every 3s (`monitor_core.py:1631-1633` →
`gate_ledger.read_task_gate_state` file read).

**Changes:**
- `monitor_core.py` `GateSummaryCache` (1599-1637): change `_cache` from
  `dict[str, str]` to `dict[str, tuple[tuple[int, int], str]]` — the validity key
  is `(st_mtime_ns, st_size)`, the value is the summary. In `summary_for`, after
  resolving `key = info.task_file_abs`, `st = os.stat(key)` (guard
  `OSError`/`FileNotFoundError` → treat as miss, fail closed to `""`); the identity
  is `(st.st_mtime_ns, st.st_size)`. **Use `st_mtime_ns`, not float `st_mtime`** —
  float-second granularity misses two ledger edits within the same second (the
  monitor would keep showing the stale compact summary); nanosecond mtime plus
  size closes that gap cheaply. On a hit with unchanged identity, return the cached
  summary; otherwise re-read via the existing
  `has_gate_markers`/`read_task_gate_state`/`compact_gate_summary` path and store
  `((mtime_ns, size), summary)`. Keep the `clear()` method (still called by
  minimonitor — leaving that call is correct, just no within-tick change).
- `monitor_app.py:702`: remove the `self._gate_cache.clear()` line from
  `_refresh_data` (mtime now drives invalidation).
- Verify (`grep`) no other `_gate_cache.clear()` callers in `monitor_app.py` rely
  on blanket clearing.

**Tests** — new `tests/test_monitor_gate_cache.py` (Python): construct a
`GateSummaryCache`, monkeypatch `gate_ledger.read_task_gate_state` with a
call-counting spy, point a temp task file (with gate markers) at it: two
`summary_for` calls → 1 read; bump the file mtime → next call re-reads (2 reads);
**same-second content change of different length → re-reads** (proves size/ns
identity, not float seconds); missing file → `""` with no raise.

**Risk:** code-health low, goal low.

### t1111_2 — Focus-switch double-render + O(N) card indicator  (fix #2; low risk)

Isolated to `monitor_app.py` (clean file).

**Problem:** `on_descendant_focus` (1354-1365) on a `PaneCard` renders the preview
**twice** — directly at 1359 (`_update_content_preview()`) and again via
`_update_zone_indicators()` (1361 → 1238). Each render is `_ansi_to_rich_text`
over ~200 lines (`monitor_shared.py:74-93`, 2 regex/line + `Text.from_ansi`). The
second is pure waste on a switch (`same_pane` is False). `_update_selected_card_indicator`
(1245-1252) also iterates **all** PaneCards + `set_class` each.

**Changes:**
- Remove the redundant direct `self._update_content_preview()` at
  `monitor_app.py:1359`; the call via `_update_zone_indicators()` (1361→1238)
  covers it (one render). Confirm `_manage_preview_timer()` at 1360 is
  render-independent (it only toggles the timer by zone) — order stays
  set-zone → manage-timer → update-indicators.
- Targeted selected-card flip **via a direct mapping, not CSS selectors**: maintain
  `self._pane_cards: dict[str, PaneCard]` (pane_id → widget), populated in
  `_rebuild_pane_list` as cards are mounted and cleared/rebuilt each tick. Track
  `self._selected_card_pane_id`. `_update_selected_card_indicator` then unsets the
  class on `self._pane_cards.get(old)` and sets it on `self._pane_cards.get(new)`
  — no query-by-selector, so no CSS-escaping / selector-significant-character
  coupling (avoids the fragility of building `#panecard-…` strings from pane IDs).
  Keep a `full=True` pass (iterate the dict's values) used by `_restore_focus`
  (883) after a rebuild re-mounts all cards (the `selected` class is lost on
  remount). The dict is the single source of truth for card lookup.

**Tests** — new `tests/test_monitor_focus_switch.py` using Textual `run_test()`
pilot: mount `MonitorApp` with ≥2 `PaneCard`s; spy `_update_content_preview`;
dispatch a `PaneCard` focus → assert called exactly once (was twice); assert only
the two affected cards get `set_class`, and render-level assert the `selected`
class is on the focused card only.

**Scope boundary:** this child is the *structural* switch fix (no threading). It
removes the redundant second render (~2× win) and the O(N) card scan, but the
**single** `_ansi_to_rich_text` render still runs on the UI thread — so the
active-agent switch lag (ANSI-heavy content; see Context) is *reduced ~2×, not
eliminated*. Eliminating it is t1111_5 (render offload).

**Risk:** code-health low, goal low.

### t1111_3 — Kill synchronous tmux calls on the UI thread in `_refresh_data`  (fix #4)

`monitor_app.py` (+ possibly a small `monitor_core.py` helper — surgical, near the
shadow hunk).

**Problem:** **four** sync tmux paths block the UI thread inside the refresh:
`_consume_focus_request` (784-787, `show-environment` via `tmux_run`);
`_clear_focus_request` (798-805, `set-environment -u` via `tmux_run`, called from
`_refresh_data:732` after a focus match); `_read_attached_session` (958-965,
`display-message` via `tmux_run`, multi-session only, called from
`_rebuild_session_bar`); and `_get_desync_summary(cwd)` (915). `tmux_run` blocks
the caller until the bg control loop completes the round-trip
(`monitor_core.py:884-887`). Note `_get_desync_summary` already has a 30s in-proc
TTL cache (`desync_summary.py:33-37`), so it is largely mitigated — lowest priority.

**Changes:** convert the *uncached* sync round-trips to async using the existing
`tmux_run_async` (`monitor_core.py:891-901`):
- Make `_consume_focus_request` async (or add `_consume_focus_request_async`) and
  `await` it in `_refresh_data` before the focus-match loop.
- **Make `_clear_focus_request` async too** and `await` it at the `_refresh_data`
  focus-match site (732). This is the path the serialization concern also touches —
  it must not reintroduce a sync `set-environment` round-trip on the loop.
- Fetch the attached session asynchronously (`_read_attached_session_async`) and
  pass the value into `_rebuild_session_bar` instead of it calling `tmux_run`
  inline; await before building the bar.
- Leave `_get_desync_summary` as-is (TTL-cached); document that its cache-miss
  subprocess is picked up by the offload child if needed.

**Tests** — new `tests/test_monitor_refresh_no_sync_tmux.py`: run `_refresh_data`
once against a fake `TmuxMonitor` whose `tmux_run` (sync) is a spy that
raises/records; assert `tmux_run` is never called during a refresh **including the
focus-match branch that calls `_clear_focus_request`** (drive a refresh where the
focus-request env var is set and matched, so the clear path is exercised) — all
tmux must go via `*_async`. Without this, the guarantee the test proves would be
silently weakened.

**Risk:** code-health low, goal low–medium (session-bar ordering).

### t1111_4 — Thread-offload refresh CPU work  (fix #1; primary lever; highest risk)

`monitor_core.py` + `monitor_app.py`. **Depends on t1111_1 and t1111_3.**

**Problem:** `_finalize_capture` (1176-1216) runs `_strip_ansi` (regex over the
full capture) + a prompt-pattern regex scan **per agent, per tick**, all inside
the awaiting coroutine on the UI thread. This is the freeze's CPU core.

**Approach (safety-first — offload only the pure work):**
- Extract the pure, stateless classification into a module-level function
  `classify_content(content, mode, prompt_patterns) -> (compare_value,
  awaiting_input, awaiting_input_kind)` — no `self`, no shared-dict mutation.
- Split capture: `capture_pane_async` fetches raw `(pane, content)` on the bg
  control loop (as today); `capture_all_async` gathers raw results, then runs the
  batch of `classify_content` calls off the event loop via `asyncio.to_thread`,
  and finally assembles `PaneSnapshot`s **on the loop**, where it alone mutates
  `_last_content`/`_last_change_time`.
- **Serialization (REQUIRED — do not rely on "awaits ⇒ no overlap"):** the app
  schedules refreshes from many sites — the 3s `set_interval` plus ~8
  `call_later(self._refresh_data)` paths (`monitor_app.py:604,1393,1474,1487,
  1586,1712,1809,…`) — *and* a 0.3s `_fast_preview_refresh` timer that also calls
  `capture_pane_async → _finalize_capture`. Today the finalize mutation is
  synchronous (no `await` inside it), so cycles can interleave at `await` points
  but never tear state. Once classification is offloaded to a thread, two cycles
  can resolve **out of order** and write stale `content` into
  `_last_content`/`_last_change_time`, corrupting the idle/awaiting-input clock.
  Enforce single-writer explicitly:
  1. A shared in-flight guard (an `asyncio.Lock` or a `self._capture_in_flight`
     flag) covering the capture→classify→apply critical section, shared by
     **both** `_refresh_data` and `_fast_preview_refresh` — a second scheduled
     cycle coalesces/skips rather than racing.
  2. A monotonic `self._capture_generation` token: snapshot it before
     `to_thread`, and after the thread returns, **discard the result if the
     generation moved** (a newer cycle superseded this one). This makes a late
     thread result harmless even if the guard is bypassed.
  Prefer Textual `@work(thread=True, group="refresh", exclusive=True)` as the
  primary supersession mechanism (native discard of stale workers; invariant C),
  with the generation token as the fallback for the non-worker
  `_fast_preview_refresh` path. Single-writer is now *enforced*, not assumed. **All
  offload code in this child obeys the Concurrency & async safety contract
  (invariants A–G in the Risk section) — route offloads through the single
  injectable `_run_offloaded` seam (F).**
- Widget updates already run on the loop after the await in `_refresh_data`; no
  `call_from_thread` needed because we return to the loop before touching widgets.
- **py-spy placement (explicit):** it is *not* used to decide scope ("proceed on
  analysis" settled that). It runs **inside this child, before AND after** the
  offload, as objective confirmation the UI thread stopped being CPU-bound:
  1. At the **start** of t1111_4, before touching `_finalize_capture`, capture a
     py-spy sample of the UI/event-loop thread during a 3s tick. This "before"
     sample must be taken on the pre-fix code — hence at the start, not the end.
  2. After the offload lands, re-sample and confirm the strip/prompt regex work no
     longer shows on the loop thread.
  **Live-agent setup recipe (owned by t1111_4 — self-contained, does not depend on
  the later t1111_6 MV sibling):** the panes must be classified `AGENT`, which
  `classify_pane` (`monitor_core.py:974-982`) decides **by window name** — the name
  must start with an `agent-` prefix (`DEFAULT_AGENT_PREFIXES`). Splitting panes
  inside one non-`agent-` window yields `OTHER` panes and skips the agent-only
  idle + prompt-pattern scan (`_finalize_capture:1192-1206`), the exact hot path
  being profiled. So spawn ~8 scratch **windows** named `agent-perf-<N>`, each
  running a cheap always-changing stand-in:
  `tmux new-session -d -s t1111perf -n agent-perf-1 'while true; do date; sleep 0.2; done'`
  then `for i in $(seq 2 8); do tmux new-window -t t1111perf -n "agent-perf-$i" 'while true; do date; sleep 0.2; done'; done`.
  (`agent-perf-*` satisfies AGENT classification; task-id extraction returning None
  is harmless. Optionally make one window echo a known prompt string so a
  prompt-pattern actually matches, but the scan branch runs for every AGENT pane
  regardless of match.) Launch `ait monitor` against that session, then sample the
  monitor process:
  `py-spy record -o before.svg --pid <monitor_pid> --duration 15` (or `py-spy dump
  --pid <pid>` during a tick). Kill the scratch session afterward
  (`tmux kill-session -t t1111perf`). Record both flamegraphs/dumps in the child's
  Final Implementation Notes. This is verification, not a gate; if py-spy is
  unavailable, fall back to the t1111_6 behavioral checks. t1111_6 repeats a
  similar live setup for the human checklist, but t1111_4 stands up its own.

**Tests** — new `tests/test_monitor_finalize_offload.py`: (a) unit-test
`classify_content` headlessly with fixtures — ANSI-laden content strips correctly,
each prompt pattern detected, no-match returns clean; (b) golden equivalence —
`capture_all_async` (offloaded) produces identical `PaneSnapshot`s to the previous
synchronous finalize for the same raw inputs; (c) idle/`_last_change_time`
bookkeeping still updates on content change; (d) **out-of-order serialization
regression** — drive two overlapping capture cycles whose `to_thread` results
resolve in reverse order (patch the offload to resolve the older generation last)
and assert the stale result is discarded (generation check) so `_last_content`
holds the newer content and the idle clock is not reset — with a **negative
control** that reproduces the corruption when the guard/generation check is
bypassed. Follow `aidocs/framework/testing_conventions.md` for the asyncio/thread
test shape.

**Risk:** code-health medium (first threading pattern; shared-state discipline),
goal medium (must actually remove the freeze).

### t1111_5 — Offload the preview render (`_ansi_to_rich_text`) off the UI thread  (active-agent switch-lag fix)

`monitor_app.py` + `monitor_shared.py`. **Depends on t1111_2 and t1111_4.**

**Problem (from the user's empirical observation):** the residual focus-switch lag
is the single `_update_content_preview` → `_ansi_to_rich_text` → `Text.from_ansi`
render of the focused pane, on the UI thread. Its cost scales with the ANSI-escape
density of the content, so an **active** agent's churny output makes each switch
lag even after t1111_2 removes the redundant second render. t1111_2 halves it;
this child removes it from the UI thread.

**Approach:**
- Split `_ansi_to_rich_text` (`monitor_shared.py:74-93`) into a pure builder that
  produces the Rich `Text` (the CPU-heavy `from_ansi` + per-line regex) and the
  application step `preview.update(text)` (must stay on the loop).
- `_update_content_preview`'s render branch computes the `Text` via
  `asyncio.to_thread` (the switch handler `on_descendant_focus` is sync, so drive
  this through a small async helper scheduled with `call_later`/`run_worker`, or
  make the preview-update path async). Apply `preview.update(text)` + scroll
  restore back on the loop.
- **Reuse t1111_4's serialization discipline:** guard against overlapping preview
  renders (rapid arrow-key switching) with an in-flight/generation token so a
  stale render for a pane you already switched away from is discarded — do not let
  a late `to_thread` result overwrite the current preview. This is why it depends
  on t1111_4 (shared helper) and t1111_2 (single-render structure).
- Preserve the existing fast-paths: the frozen branch (`same_pane and (is_paused or
  user_is_scrolling)` at 1156) and the header-only update must still short-circuit
  *before* scheduling any offload (no thread hop when nothing will render).
- **Obeys the Concurrency & async safety contract (invariants A–G in the Risk
  section):** reuse t1111_4's `_run_offloaded` seam + generation token (C/F), prefer
  `@work(thread=True, group="preview", exclusive=True)` so rapid arrow-nav
  supersedes stale renders natively, fail closed on a raising `from_ansi` (D),
  read `self._snapshots.get(pane_id)` defensively and keep the scroll-restore
  ordering (G).

**Tests** — new `tests/test_monitor_preview_offload.py`: (a) unit-test the pure
`Text`-builder headlessly on ANSI-heavy fixture content (correct styled output);
(b) render-equivalence vs the current synchronous `_ansi_to_rich_text` for the same
input; (c) **stale-render discard** — simulate two rapid switches whose offloaded
renders resolve out of order and assert the preview shows the last-focused pane's
content (generation check), with a negative control; (d) assert the frozen/paused
and header-only branches never schedule an offload.

**Risk:** code-health medium (extends the threading pattern to the render path),
goal medium (directly targets the active-agent lag the user reported).

### t1111_6 — Aggregate manual-verification sibling  (`issue_type: manual_verification`)

`--verifies 1111_1,1111_2,1111_3,1111_4,1111_5`. Behavioral, human-only. Checklist:
launch `ait monitor` with ~8–10 live agents (real `agent-pick-*` windows, or the
synthetic `agent-perf-*` **windows** from t1111_4's recipe — panes must be in
`agent-`-named windows to classify as AGENT) and confirm — (1) arrow
focus-switch is instant with all agents idle; (2) **focus-switch stays instant
while ≥1 agent is actively producing ANSI-heavy output** (the user-reported
regression — switching to/among agents must not lag when one is active); (3) the
3s tick no longer freezes input (idle or active); (4) gate columns still render
and stay live as a ledger grows; (5) content preview renders correctly and
scroll/pause behavior is intact; (6) idle + awaiting-input detection still fire
correctly; (7) **concurrency soak** — hold down/repeat arrow-nav continuously for
~1 min while ≥2 `agent-*` windows churn, then confirm no crash, no wrong-pane
preview, no stuck idle badge, and no runaway thread/memory growth (the behavioral
gate for the offload's race-safety, per Risk invariants A–G). Seeded via
`aitask_create_manual_verification.sh` after the child plans are committed.

## Deferred follow-ups (NOT children of this parent)

- **Tiered polling (fix #5):** full 200-line capture/ANSI render only for the
  focused pane, a minimal status probe for the rest. Overlaps t719_3 (Postponed)
  and t719_4 (pipe-pane push) — coordinate there rather than duplicate. Post-approval,
  add a reverse coordination note to t719_3/t719_4 (`./ait git`).
- **minimonitor propagation:** apply the thread-offload + drop the per-tick
  `_gate_cache.clear()` in `minimonitor_app.py` (currently has concurrent
  uncommitted shadow edits) once t1111_4 lands. Spawn as a standalone follow-up.

## Risk

t1111_4/t1111_5 introduce the codebase's first UI-thread offload — the primary
risk class is concurrency/async correctness. The following **safety contract is
binding on t1111_4 and t1111_5** (referenced from both child plans); each invariant
has a concrete mitigation and, where a bug could pass silently, a test.

### Concurrency & async safety contract (invariants)

- **A — Workers are pure compute; the loop owns all I/O to widgets.** Offloaded
  code (`classify_content`, the Rich-`Text` builder) MUST NOT touch `self.query`,
  any widget, reactive attribute, or the DOM — Textual is single-threaded and
  cross-thread widget access corrupts/crashes it. Widget mutations
  (`preview.update`, `set_class`, mount/remove) happen only after the `await`
  returns to the loop. *Mitigation:* the offloaded functions are module-level and
  take only plain data args (no `self`); *test:* their signatures/inputs are
  asserted pure (no app/widget references) in the unit tests.
- **B — Shared mutable state is mutated only on the loop.** `_last_content`,
  `_last_change_time`, `_snapshots` are written exclusively in the loop
  continuation. Inputs a worker needs (`content`, the pane's `compare_mode` via
  `get_compare_mode`, and `prompt_patterns`) are **read on the loop and passed by
  value**; `prompt_patterns` is treated read-only (snapshot the list ref; it is
  built at init — if any runtime reconfiguration path exists, copy it before the
  offload). *Test:* golden equivalence vs the synchronous path guarantees no
  bookkeeping drift.
- **C — Supersession is idiomatic, not just hand-rolled.** Prefer Textual
  `@work(thread=True, group="refresh"/"preview", exclusive=True)` — its
  exclusive-group semantics natively discard a superseded worker's result, which
  IS the serialization mechanism. Keep a monotonic generation token as
  belt-and-suspenders for any path not expressed as a worker
  (`_fast_preview_refresh`), and share ONE in-flight guard across `_refresh_data` /
  `_fast_preview_refresh` / preview render. *Test:* out-of-order resolution
  regression + **negative control** (bug reproduces when the guard/generation
  check is bypassed) in both t1111_4 and t1111_5.
- **D — Offloads fail closed.** Every offloaded call is wrapped so a raising
  `from_ansi`/regex/`os.stat` degrades to prior/raw content (as `_finalize_capture`
  already fails closed today) and never propagates out of the refresh/preview
  coroutine. `capture_all_async` keeps `gather(..., return_exceptions=True)`.
  *Test:* feed malformed/adversarial ANSI and assert no raise + sane fallback.
- **E — Bounded concurrency.** One `to_thread`/worker **batch per cycle** (t1111_4
  finalizes all panes in a single offload, not one-per-pane); the in-flight guard
  coalesces bursts so rapid arrow-nav in t1111_5 cannot pile unbounded work onto
  the default executor. *Mitigation:* single offload seam; no per-item thread fan-out.
- **F — Deterministic test seam.** Route every offload through one injectable
  helper (e.g. `await self._run_offloaded(fn, gen)`) that tests monkeypatch to run
  synchronously and to control resolution order — **no `sleep`-based timing** in
  tests (per `aidocs/framework/testing_conventions.md`).
- **G — Sequencing preserved.** The async preview render (t1111_5) must schedule
  the existing `call_after_refresh` scroll-restore in the loop continuation *after*
  `preview.update`, and read `self._snapshots.get(pane_id)` defensively (a
  concurrent refresh may have replaced the dict) — stale snapshot ⇒ discard via
  generation, never `KeyError`.

### Code-health

Net **positive-to-neutral**: extracting pure `classify_content` and the Rich-`Text`
builder out of `_finalize_capture`/`_ansi_to_rich_text` improves testability and
isolates the regex work. The added surface is the offload seam + guard, centralized
in one helper (invariant F) rather than sprinkled. Medium overall (new pattern),
but bounded by the contract above. t1111_1/_2/_3 are low-risk local changes.

### Goal-achievement

Medium. Static analysis pinpoints the costs, but the win must be confirmed
behaviorally (t1111_6, incl. the active-agent switch case) and optionally with
py-spy. **Planned mitigation (after):** t1111_6 additionally includes a
rapid-switch-under-active-load soak check (drive continuous arrow-nav while ≥2
`agent-*` windows churn, for ~1 min) to surface any residual race/leak that unit
tests miss — this is the behavioral gate for the concurrency work, complementing
the per-child out-of-order regressions.

## Post-approval execution (this session)

Plan mode is read-only, so on approval I will: (1) create t1111_1..t1111_5 via
`aitask_create.sh --batch` (child mode) with the detailed context above baked into
each child (encoding the depends: 1111_4 → 1111_1,1111_3 and 1111_5 → 1111_2,
1111_4); (2) write `aiplans/p1111/p1111_<n>_*.md` for each; (3) offer + create the
t1111_6 MV sibling (N≥2 children); (4) revert parent t1111 to Ready, release its
lock; (5) present the child checkpoint (start first child vs stop). Children carry
their own risk evaluation when picked.

## Verification (overall)

Per-child unit/render tests above run individually (`bash`/pytest-style Textual
`run_test()`), plus the t1111_6 live checklist. No project `verify_build` is
configured; the behavioral proof is the manual-verification sibling.
