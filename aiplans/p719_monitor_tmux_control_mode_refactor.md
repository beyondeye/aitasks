---
Task: t719_monitor_tmux_control_mode_refactor.md
Worktree: (none — working on current branch per profile fast)
Branch: main
Base branch: main
---

# t719 — `tmux -C` control-mode refactor for monitor/minimonitor (parent plan)

## Context

`aidocs/python_tui_performance.md` classifies the monitor/minimonitor TUIs as
I/O-bound on `fork() + exec(tmux)`, not on Python execution. Every 3-second
refresh tick `tmux_monitor.py::capture_all_async()` spawns one
`tmux capture-pane` subprocess per agent pane via
`asyncio.create_subprocess_exec`. With 5–10 agents that's 6–15 fork+exec
cycles per tick at ~1–10 ms each. PyPy / Nuitka / mypyc / JIT do nothing
here — the cost is OS-level. The architectural fix is `tmux -C` (control
mode): a single persistent tmux client that accepts commands on stdin and
emits structured `%begin/%end` blocks on stdout. One persistent connection
replaces N forks per tick.

The task spans three architectural moves (Phase 1 control-mode connection,
Phase 2 adaptive polling, Phase 3 `pipe-pane` push model) plus shared-
benchmark and TUI-level verification. All in scope here, split into
sequential child tasks.

## Child split (6 children)

| Child | Scope | Depends on |
|-------|-------|------------|
| **t719_1** | Build standalone `TmuxControlClient` module + bash integration test | — |
| **t719_2** | Wire client into `TmuxMonitor` async hot-path + lifecycle in monitor/minimonitor + microbenchmark | t719_1 |
| **t719_3** | Phase 2 — adaptive polling (slow down when no pane content has changed) | t719_2 |
| **t719_4** | Phase 3 — `pipe-pane` push model investigation + (if win is large) implementation | t719_2 |
| **t719_5** | Aggregate manual verification of monitor/minimonitor UI behavior end-to-end | t719_2, t719_3, t719_4 |
| **t719_6** | Architecture evaluation: collect benchmark + UI feedback from all siblings; document serialization tradeoff; propose follow-up improvement directions | t719_1, t719_2, t719_3, t719_4, t719_5 |

Sequencing rationale:

- `_1` is a self-contained library with its own test suite — implementable
  and reviewable without touching `tmux_monitor.py`. Lets a contributor
  ship the protocol layer, get it green, and stop.
- `_2` is the integration that delivers the user-visible win. Hard-depends
  on `_1`. Includes the microbenchmark that proves the ≥5× target.
- `_3` and `_4` are independent optimizations on top of `_2`. They can be
  picked in either order; `_4` may be deferred or cancelled if `_2`'s
  benchmark already meets the SLO.
- `_5` is the human-only validation pass — TUI feel, idle-detection
  behavior, focus restoration, multi-session toggle, compare-mode toggle.
  Created via `aitask_create_manual_verification.sh` after `_1`–`_4` plans
  are written.
- `_6` is the post-implementation architecture review. Takes the *real*
  numbers and qualitative feedback from `_2`–`_5`, weighs them against
  the design decisions made in this plan (notably the
  serialize-via-single-client choice — see "Serialization design note"
  below), and writes up follow-up tasks if any direction looks worth
  pursuing.

## Per-child summary

### t719_1 — `TmuxControlClient` module

**Goal:** ship a working `tmux -C` control client as a standalone module
that any caller can use, with a green test suite, but without yet plumbing
it into `tmux_monitor.py`.

**Adds:**
- `.aitask-scripts/monitor/tmux_control.py` (~250–320 LOC) — class
  `TmuxControlClient` with `start()`, `request(args, timeout) -> (rc, str)`,
  `close()`, `is_alive`. Spawns
  `tmux -C attach -t <session> -f no-output,ignore-size` with
  `limit=4*1024*1024` on the asyncio StreamReader. FIFO `_pending: deque`
  guarded by `asyncio.Lock`; reader task parses `%begin/%end/%error`
  blocks; ignores async events (man page guarantees notifications never
  appear inside an output block); treats `%exit` as EOF.
  Argument escaping: each arg wrapped in `"..."` with `\` → `\\` and
  `"` → `\"`; literal tab bytes (`0x09`) inside format strings preserved
  for byte-for-byte parity with the subprocess wire format.
- `tests/test_tmux_control.sh` (~150 LOC, follows
  `test_tmux_exact_session_targeting.sh` style with `TMUX_TMPDIR` /
  `unset TMUX` / trap cleanup; skip if `tmux` missing). Cases:
  smoke + parity vs. subprocess output; concurrent `gather` of 5 requests;
  invalid command returns non-zero rc, no exception, client stays alive;
  server-kill → `is_alive` flips to False, in-flight + queued futures
  resolve with `(-1, "")`.

**Reuses:** none from existing `.aitask-scripts/lib/` (no prior control-mode
helper exists per the exploration).

**Out of bounds:** does not modify `tmux_monitor.py`, the apps, or any
existing test. Pure addition.

### t719_2 — Hot-path integration + lifecycle + benchmark

**Goal:** route the 3-second refresh through the control client, prove the
≥5× speedup, and wire clean lifecycle into both apps. This child delivers
the user-visible performance win.

**Modifies:**
- `.aitask-scripts/monitor/tmux_monitor.py`
  - Add `self._control: TmuxControlClient | None = None` to
    `TmuxMonitor.__init__`.
  - Add `start_control_client()` / `close_control_client()` /
    `has_control_client()` methods.
  - Add `_tmux_async(args, timeout)` helper that prefers the client, falls
    back to subprocess on `is_alive == False` or transport rc `-1`.
  - Update the three async-path call sites — `tmux_monitor.py:284`
    (`_discover_panes_multi_async`), `:317` (`discover_panes_async`),
    `:469` (`capture_pane_async`) — to call `self._tmux_async(...)` instead
    of the module-level `_run_tmux_async`. The free function stays as the
    fallback.
  - **Sync paths untouched** (kill, switch, send-keys, spawn-tui, has-session
    — user-action triggered, not per-tick).
- `.aitask-scripts/monitor/monitor_app.py`
  - In `_start_monitoring` (`monitor_app.py:579`), `run_worker(...,
    exit_on_error=False)` for `_connect_control_client` (best-effort, logs
    on failure, falls back automatically).
  - Add `async def on_unmount()` that calls
    `self._monitor.close_control_client()` under try/except. (No existing
    unmount hook — confirmed.)
- `.aitask-scripts/monitor/minimonitor_app.py`
  - Same lifecycle pattern: in `_start_monitoring` (`minimonitor_app.py:189`)
    + new `on_unmount`.

**Adds:**
- `aidocs/benchmarks/bench_monitor_refresh.py` (~200 LOC) — pattern matches
  `aidocs/benchmarks/bench_archive_formats.py` (argparse, warmup +
  iterations, `statistics`). Sets up isolated `TMUX_TMPDIR`, spawns N
  agent windows, runs `capture_all_async()` × M with subprocess-only and
  with control-client; reports median, p95, fork count, ratios. Skips if
  tmux missing.

**Verification:**
- `bash tests/test_tmux_control.sh` still passes.
- `python3 aidocs/benchmarks/bench_monitor_refresh.py --panes 5
  --iterations 50` reports control-client median ≥ **5×** below subprocess
  median; per-tick subprocess spawns drop from ~6 to 0 in steady state.
- Smoke launch of `ait monitor` and `ait minimonitor` to confirm no
  regressions in idle detection, multi-session toggle, focus handoff
  (deeper validation deferred to `_5`).

### t719_3 — Adaptive polling (Phase 2)

**Goal:** if no pane content has changed across the last K consecutive
ticks, double the poll interval up to a configured cap. Reset to base
interval on any change. Reduces tmux load further when agents are idle.

**Modifies:**
- `.aitask-scripts/monitor/tmux_monitor.py` — track per-tick "anything
  changed?" derived from existing `_last_change_time` deltas in
  `_finalize_capture`. Expose a method like `current_poll_interval(base)`
  that the apps consult to schedule the next refresh.
- `.aitask-scripts/monitor/monitor_app.py` and `minimonitor_app.py` — replace
  the static `set_interval(self._refresh_seconds, ...)` with a
  re-arming `set_timer` driven by `current_poll_interval`.
- `aitasks/metadata/project_config.yaml` (and seed copy) — add
  `tmux.monitor.adaptive_idle_doublings_max` (default 3 → up to 8× base)
  and `tmux.monitor.adaptive_change_resets` flag (default true). Only the
  user-level userconfig may override at runtime; project_config holds the
  default. Document in `tmux_monitor.py` docstring.

**Tests:**
- Add adaptive-poll unit cases to a new
  `tests/test_adaptive_polling.sh` (or a Python helper invoked from a
  bash test). Drive synthetic snapshots through `_finalize_capture` and
  assert interval doubles after K idle ticks, resets on change.

**Out of bounds:** does not change idle detection itself (idle threshold
stays a separate concern), and does not slow down the *first* tick after a
change.

### t719_4 — `pipe-pane` push model (Phase 3)

**Goal:** investigate replacing periodic `capture-pane` polling with
`tmux pipe-pane` writing each pane's output to a per-pane fifo / pipe that
the monitor reads asynchronously. Eliminates polling entirely. Implement
only if the spike shows a clear win over `_2 + _3` combined.

**Phase 4a — investigation (always done):**
- Prototype a side branch that subscribes one pane via
  `tmux pipe-pane -O 'cat > <fifo>'` and reads it with
  `asyncio.open_connection` / `aiofiles`. Measure CPU + responsiveness vs.
  the polling path on a representative session.
- Document findings in `aidocs/python_tui_performance.md` under a new
  "pipe-pane investigation" section: throughput, lag, fifo lifecycle
  caveats (stale fifos on crash; multiple panes need multiple fifos;
  ANSI escape handling vs. `capture-pane -e` output).
- Decision gate: if the prototype's median refresh latency is at least
  **2×** below `_2 + _3` for the same fixture, proceed to 4b.
  Otherwise, document the result, skip 4b, and archive the child.

**Phase 4b — implementation (conditional):**
- New helper class `TmuxPipePaneSubscriber` in
  `.aitask-scripts/monitor/tmux_pipe_pane.py` — manages per-pane fifos,
  starts/stops subscriptions, hands content to `TmuxMonitor` via callback.
- `TmuxMonitor.capture_all_async()` switches to consult the subscriber's
  buffered content for known panes, falling back to `capture-pane` for
  cold panes. Compare-mode logic (stripped/raw) unchanged — operates on
  the bytes received.
- Lifecycle: subscriber owned by the apps, started after the control
  client, torn down in `on_unmount`.
- Tests: extend `tests/test_tmux_control.sh` (or a new
  `test_tmux_pipe_pane.sh`) with subscriber lifecycle, fifo cleanup on
  crash, and parity-with-polling content checks.

**Verification:** benchmark report appended to `bench_monitor_refresh.py`'s
output (third mode, "pipe-pane"); idle detection still fires at threshold;
no fifo leakage after `kill-server`.

### Serialization design note (relevant to `_2` and `_6`)

`_2` ships a single control client with all `request()` calls serialized
through one `asyncio.Lock` + FIFO `deque[Future]`. This is a deliberate
trade-off:

- **Why it's fine in Phase 1.** The cost we're killing is fork+exec
  (~1–10 ms × N at OS level). tmux's *internal* `capture-pane` work is
  sub-millisecond — it just slices its scrollback buffer. 10 serialized
  commands through one client ≈ 5 ms vs. 10 parallel forks ≈ 30 ms.
  Serialization here costs almost nothing relative to the savings.
  Additionally, tmux processes commands strictly in receive order on a
  single client — even per-cmd_id "parallel" demuxing wouldn't actually
  parallelize tmux-side work, so the client's serialization is matching
  reality, not papering over it.
- **Where this could matter later.** Very high pane counts (~30+),
  whose linear growth could become noticeable; or future per-tick
  features that issue many small commands. Mitigations available:
  - Phase 2 (`_3`) ramps polling down when idle — partial mitigation.
  - Phase 3 (`_4`) replaces polling with `pipe-pane` push — structural
    fix; if `_4` ships, `_2`'s serialization stops being on the hot
    path entirely.
  - A small *pool* of control clients (2–3, round-robin) would let
    `capture-pane` overlap. Not in `_2`'s scope; documented here as a
    candidate `_6` may surface.
- **What `_6` evaluates.** With real benchmark numbers from `_2`, real
  idle-load profile from `_3`, and real `pipe-pane` cost/benefit from
  `_4`, decide whether the single-client serialization is still the
  right shape, or whether to follow up with a pool / pipe-pane-only
  switch / something else.

### t719_5 — Manual verification (aggregate sibling)

**Goal:** human-only validation that monitor/minimonitor behave correctly
end-to-end after `_1`–`_4` land. Created via the standard
`aitask_create_manual_verification.sh` helper after the per-child plans
are written, with `--verifies 719_1,719_2,719_3,719_4` and a seeded
checklist drawn from each child plan's `## Verification` section.

Areas to cover (seeded into the checklist):

- `ait monitor` against a session with 5+ agent panes: pane list, focus
  zone, content preview, idle indicator after the configured threshold.
- `ait minimonitor` companion behavior: tab-to-focus-agent, send-Enter,
  `m` switch to full monitor.
- Multi-session toggle (`M`): cross-session capture, sorted display,
  cache invalidation on toggle.
- Compare-mode toggle (`d`): per-pane override; idle still fires under
  Codex CLI's animated ANSI under `stripped`; raw mode flagged in footer.
- Adaptive polling (`_3`): idle session ramps interval up; first change
  resets immediately; `M` toggle re-baselines.
- Pipe-pane (`_4`, if shipped): no fifo files left over after `q`; content
  matches polling path.
- Fall-back path: kill the tmux server while monitor is open; confirm the
  apps don't crash and continue via subprocess (sluggish but functional)
  until the user re-attaches.

### t719_6 — Architecture evaluation

**Goal:** with `_1`–`_5` archived, take stock of the real numbers and the
real user feel, write a short evaluation document, and propose concrete
follow-up tasks if any improvement direction looks worth pursuing.

**Inputs (read-only):**

- Archived plan files for `_1`, `_2`, `_3`, `_4`, `_5` (under
  `aiplans/archived/p719/`) — their "Final Implementation Notes" sections
  contain actual deviations, issues, and surprises.
- Benchmark output from `aidocs/benchmarks/bench_monitor_refresh.py` —
  re-run on a representative session (5, 10, 20 panes) and capture
  results. If `_4` shipped, include the `pipe-pane` mode in the run.
- The serialization design note above (this plan file) for the
  trade-off framing baseline.
- Any user-feedback bullets recorded under `_5`'s manual-verification
  result transcript.

**Adds:**

- `aidocs/python_tui_performance.md` gets a new section "Phase 1
  outcomes & next directions" appended at the bottom. Content:
  - Final benchmark numbers (median/p95 wall time + per-tick fork count
    at N panes ∈ {5, 10, 20}, three modes: subprocess / control /
    pipe-pane if shipped).
  - Whether the ≥5× target was hit; under what conditions it wasn't.
  - Qualitative feel notes from `_5` (idle detection, focus handoff,
    multi-session, compare-mode toggle).
  - Re-evaluation of the single-client serialization choice: is it
    still the right shape, or has scaling actually shown up at high
    pane counts?
  - 1–3 concrete follow-up directions, each ranked by expected payoff
    and complexity. Candidates to consider (non-exhaustive): control-
    client pool; per-pane subscription via `pipe-pane` if not yet shipped;
    cache-based "skip capture if pane width/height/pid unchanged"
    heuristic; folding `display-message` aux calls into the control
    client; raising the asyncio buffer further for very wide panes.
- For each follow-up direction the document recommends pursuing, file
  a separate top-level task via `aitask_create.sh --batch` (NOT a
  child of t719 — t719 is closed at that point). Reference each new
  task ID in the document section.

**Out of bounds:**

- No code changes in `_6`. It is purely synthesis + documentation +
  task creation.
- No re-running of `_1`–`_5`'s tests; trust their archival commits.
  (If a regression is suspected, that's its own task.)
- No predictions about future tmux upstream changes.

**Verification:**

- The `aidocs/python_tui_performance.md` addition compiles in `hugo
  build` (it's surfaced via the website's docs sync).
- Each newly-created follow-up task validates against
  `aitask_create.sh`'s schema (frontmatter present, depends list
  resolves, etc.).
- A single `./ait git commit` lands the doc update and any new task
  files together.

## Coordination notes

- **No new whitelisting touchpoints expected.** No new helper script
  under `.aitask-scripts/` (the additions are Python modules consumed by
  existing apps, not bash scripts invoked from skills). Verify in `_1`
  and `_2`.
- **Frontmatter fields:** none added. The "three layers" rule does not
  apply here.
- **macOS portability:** `tmux -C` is supported on tmux 2.3+; macOS users
  on Homebrew tmux are fine. Linux (Arch, Debian) covered by stock
  packages. Skip-if-missing in tests.
- **No `seed/`-level changes.** All runtime additions live under
  `.aitask-scripts/monitor/` and `aidocs/`.

## Out of scope (out of t719 entirely)

- Routing user-action subprocess calls (kill-pane, switch-to-pane,
  send-keys, rename-window, has-session, etc.) through the control
  client. Not per-tick; subprocess overhead is invisible at user
  reaction times. If profiling later flags one as slow, it's a separate
  task.

## Parent task post-implementation

Per `task-workflow/SKILL.md` Step 9: parent t719 archives automatically
once all five children are Done. No code changes happen at the parent
level — it's a coordinator.
