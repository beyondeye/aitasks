---
priority: high
effort: high
depends: [t1111_3]
issue_type: performance
status: Ready
labels: [monitor, tui, performance]
gates: [risk_evaluated]
anchor: 1111
created_at: 2026-07-02 14:43
updated_at: 2026-07-02 14:43
---

**Thread-offload** the refresh CPU work (strip/prompt-regex) off the UI thread —
primary freeze lever. Establishes the codebase's first UI-thread offload pattern.

## Context
Part of t1111 (`ait monitor` UI-thread offload). `_finalize_capture`
(`monitor_core.py:1176-1216`) runs `_strip_ansi` (regex over the full capture) + a
prompt-pattern regex scan **per agent, per tick**, inside the awaiting coroutine on
the UI thread — the CPU core of the 3s freeze. Move the pure work off the loop.
**Depends on t1111_1 (gate mtime-cache) and t1111_3 (sync-tmux removal)** so the
offload sits on an already-cleaned refresh path. The sibling **t1111_5** reuses the
serialization + offload seam this task establishes.

## Key files to modify
- `.aitask-scripts/monitor/monitor_core.py` (`_finalize_capture`,
  `capture_pane_async` 1249-1258, `capture_all_async` 1327-1340).
- `.aitask-scripts/monitor/monitor_app.py` (`_refresh_data`, `_fast_preview_refresh`;
  add the shared offload seam + in-flight guard + generation token).

## Approach (safety-first — offload only the pure work)
1. Extract a **module-level pure** function
   `classify_content(content, mode, prompt_patterns) -> (compare_value,
   awaiting_input, awaiting_input_kind)` — no `self`, no shared-dict mutation, no
   widget access.
2. Split capture: `capture_pane_async` fetches raw `(pane, content)` on the bg
   control loop (as today); `capture_all_async` gathers raw results, runs the
   **batch** of `classify_content` calls off the loop in a **single**
   `asyncio.to_thread` call, then assembles `PaneSnapshot`s **on the loop**, where it
   alone mutates `_last_content` / `_last_change_time`.
3. **Serialization (REQUIRED — do NOT rely on "awaits ⇒ no overlap"):** refreshes
   are scheduled from ~8 `call_later(self._refresh_data)` sites + the 3s
   `set_interval` + the 0.3s `_fast_preview_refresh` timer (which also finalizes).
   Once classification is threaded, two cycles can resolve **out of order** and
   write stale content into `_last_content`/`_last_change_time`, corrupting the
   idle/awaiting clock. Enforce single-writer:
   - Prefer Textual `@work(thread=True, group="refresh", exclusive=True)` — native
     discard of superseded workers is the serialization mechanism.
   - Keep a monotonic `self._capture_generation` token (snapshot before offload,
     discard result if it moved) as fallback for the non-worker
     `_fast_preview_refresh` path.
   - Share ONE in-flight guard across `_refresh_data` / `_fast_preview_refresh`.
4. Route every offload through a single injectable seam `_run_offloaded(fn, gen)`
   so tests can force synchronous execution and control resolution order.

## Concurrency & async safety contract (BINDING — invariants A–G)
- **A** Workers are pure compute; the loop owns ALL widget/DOM/reactive access.
  Offloaded fns are module-level, plain-data args only.
- **B** `_last_content`/`_last_change_time`/`_snapshots` mutated only on the loop;
  `mode` (via `get_compare_mode`) and `prompt_patterns` read on the loop, passed by
  value; `prompt_patterns` treated read-only.
- **C** Idiomatic supersession (`@work exclusive`) + generation token + one shared
  guard. Test: out-of-order regression + **negative control**.
- **D** Offloads fail closed (raising `from_ansi`/regex degrades to prior/raw
  content, never propagates). `capture_all_async` keeps `gather(return_exceptions=True)`.
- **E** Bounded concurrency: one offload batch per cycle (no per-pane fan-out);
  guard coalesces bursts.
- **F** Deterministic test seam `_run_offloaded`; no sleep-based timing in tests.
- **G** Preserve `call_after_refresh` sequencing; read `_snapshots.get()` defensively.

## py-spy verification (inside this child; before AND after; not a gate)
1. BEFORE editing `_finalize_capture`, sample the UI/event-loop thread during a 3s
   tick with the recipe below (must be on pre-fix code).
2. After the offload, re-sample; confirm strip/prompt regex no longer on the loop.
Record both in Final Implementation Notes; if py-spy unavailable, fall back to
t1111_6 behavioral checks.

**Live-agent setup recipe (self-contained — panes must classify as AGENT, which
`classify_pane` (`monitor_core.py:974-982`) decides by WINDOW NAME starting with
`agent-`; splitting panes in one non-`agent-` window yields OTHER panes and skips
the agent-only idle+prompt scan at `_finalize_capture:1192-1206`):**
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
  pattern detected, no-match returns clean.
- (b) golden equivalence — offloaded `capture_all_async` yields identical
  `PaneSnapshot`s to the prior synchronous finalize for the same raw inputs.
- (c) idle/`_last_change_time` bookkeeping still updates on content change.
- (d) **out-of-order serialization regression** — two overlapping cycles whose
  offloaded results resolve in reverse order → stale result discarded (generation),
  `_last_content` holds newer content, idle clock not reset — WITH a **negative
  control** reproducing the corruption when the guard/generation check is bypassed.
Follow `aidocs/framework/testing_conventions.md` for asyncio/thread test shape.

## Risk
code-health medium (first threading pattern; shared-state discipline),
goal medium (must actually remove the freeze — confirmed via py-spy + t1111_6).
Risk-gated: declares `risk_evaluated`; re-run risk evaluation at pick time.
