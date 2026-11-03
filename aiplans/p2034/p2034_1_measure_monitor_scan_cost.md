---
Task: t2034_1_measure_monitor_scan_cost.md
Parent Task: aitasks/t2034_shared_monitor_status_server.md
Sibling Tasks: aitasks/t2034/t2034_2_monitor_producer_client_agnostic_settings.md, aitasks/t2034/t2034_3_monitor_status_protocol.md, aitasks/t2034/t2034_6_monitor_classifier_crosscheck_python_go.md
Archived Sibling Plans: aiplans/archived/p2034/p2034_*_*.md
Base branch: main
Output branch: main
---

# t2034_1 — Measure monitor/minimonitor scan cost vs Textual render

## Context

t2034 replaces per-instance tmux scanning in `ait monitor` / `ait minimonitor` /
applink with one shared status server. Before building it (t2037, Go port t2038 →
aitasks_go#t47) we need numbers: how much of each instance's CPU is the producer
path (discovery, `capture-pane`, `strip_ansi`, classification) versus Textual
compose/render, and how the `capture-pane` rate grows with the agent count. The
2026-10-16 snapshot (ps lifetime averages) cannot separate the two.

**This is a measurement task — no repository code changes.** The deliverable is
numbers + method + the exact scripts, recorded in this plan file (archived with
the task). All tooling lives in the scratchpad; py-spy is a throwaway install.

### State found during planning (2026-11-03, read-only probes)

- Live tmux server `-L ait`: **41 minimonitors + 5 monitors** (vs 7 + 4 on
  10-16), 45 control-mode clients (`tmux -L ait -C attach ... -f no-output`),
  5 sessions, 95 panes (64 python, 21 claude, 10 codex). 24 cpus, load ~6.7.
- Per-instance lifetime CPU (ps): minimonitors 1.6–4.3 %, monitors 1.1–1.3 %,
  RSS 76–131 MB.
- **tmux server (pid 8760) at 21.4 % of one core lifetime average** — the
  server-side half of the scan cost, which the in-process profile cannot see.
- `kernel.yama.ptrace_scope = 1`, no sudo assumed → py-spy **cannot attach to
  the existing PIDs**, but it **can** profile a process it launches itself
  (descendant tracing is allowed at scope 1). So every profiled instance is a
  fresh one launched as py-spy's child.
- App Python: `~/.aitask/venv/bin/python` = CPython **3.14.9**. py-spy latest on
  PyPI = 0.4.3; 3.14 support must be probed (pre-phase below). `uv` is
  available at `~/.aitask/uv/uv`.
- Producer entry points (all in `.aitask-scripts/monitor/monitor_core.py`):
  `_tmux_async` :2105 (delegates to `run_async_via_control`, i.e. the `-C`
  client, `TmuxControlClient` :1438 / `TmuxControlBackend` :1675),
  `discover_panes_with_shadows_async` :2819, `capture_all_classified_async`
  :3379, `commit_snapshots` :3505, `classify_content` :286 — classification
  is batched **off-loop in one `asyncio.to_thread` call** (:369), so producer
  CPU is spread over the main thread and a worker thread. `strip_ansi` in
  `monitor/ansi_utils.py:36`. Refresh: `set_interval(refresh_seconds=3)` in
  `minimonitor_app.py:1749` and `monitor_app.py:892`; the monitor also runs a
  0.3 s preview timer (`monitor_app.py:2858`, `_fast_zone_refresh`).
- **Socket selection** (verified): `TmuxMonitor` and its control backend go
  through `lib/tmux_exec.py:tmux_socket_args()` (:86), which reads **only**
  `AITASKS_TMUX_SOCKET` — unset → `-L ait`, regardless of `$TMUX`. Only
  `_seed_own_window_info` follows ambient `$TMUX`. Panes run in the tmux
  **server's** environment, so the variable must be passed explicitly to every
  launched process.
- **Minimonitor auto-close** (verified): `_check_auto_close`
  (`minimonitor_app.py:1892`, after a 5 s grace) exits after
  `AUTO_CLOSE_CONFIRMATIONS` back-to-back sightings of its own pane alone in
  its window. Any other pane in the window keeps it alive. `monitor_app.py`
  has no auto-close.

## Method

Scratch dir: `$S=/tmp/claude-1000/-home-ddt-Work-aitasks/50d0f093-4e60-48ac-8ddf-7acb9bcb1696/scratchpad/t2034_1`.

Common launch rules for **every** measured process and counter (steps 3–5):

- `AITASKS_TMUX_SOCKET` set explicitly in the launched command line
  (`env AITASKS_TMUX_SOCKET=<sock> py-spy record ... -- python ...`), `ait` for
  the live runs, the scratch socket for the scaling runs — never inherited.
- Companion layout: the measured minimonitor shares its window with one other
  pane (live: a harmless `sleep infinity` pane in a non-`agent-*` window, so no
  live instance captures it; scaling: the fake agent of that window, exactly as
  a real agent window).
- **Pre-collection checks** (abort that run if either fails): read
  `/proc/<app pid>/environ` and confirm `AITASKS_TMUX_SOCKET=<sock>`; run
  `tickcount.py` (step 4) under the same env and confirm the discovered session
  set and agent-pane count equal the expected ones (live: the 5 live sessions;
  scaling: only the scratch session, exactly N agents).
- **Liveness during collection:** a watcher polls `kill -0 <app pid>` every
  second for the whole py-spy duration and logs any exit; a run whose app died
  before py-spy's duration elapsed is discarded, not reported. py-spy's own
  exit code and sample count are recorded with each run.

### Pre-phase (risk mitigations)

1. [probe_pyspy_py314] Create a throwaway venv `$S/spyenv` and
   `pip install py-spy==0.4.3`. Probe with a known workload:
   `py-spy record -r 200 -d 10 -f raw --threads -o $S/probe.txt -- ~/.aitask/venv/bin/python $S/burst.py`,
   where `burst.py` alternates on the main thread: 2 ms CPU bursts in
   `burn_a()` (≈70 % of CPU), 2 ms bursts in `burn_b()` (≈30 %), separated by
   `time.sleep(0.005)`, plus a worker thread running `burn_c()` bursts; it
   prints its own measured `time.thread_time()` per function. Pass criterion:
   py-spy runs on 3.14, stacks name the functions, and the a:b:c sample shares
   are within ±5 pp of the self-reported CPU shares.
   - **If py-spy does not support CPython 3.14** (refusal or garbled stacks):
     do **not** write a home-made sampler. Build a throwaway CPython 3.13 venv
     `$S/app313` with `~/.aitask/uv/uv venv -p 3.13` and install the app venv's
     `pip freeze`, re-run the same probe on it, and run all measured instances
     on `$S/app313/bin/python` under py-spy. Record the interpreter deviation
     next to every table.
   - If neither works, stop and report to the user rather than measure with an
     unvalidated tool.

### Main steps

1. **Bucketing script** `$S/bucket.py` — reads py-spy `raw` output recorded
   with `--threads` (`thread (0x…);frame;frame;… count`). **Ownership policy
   (single rule): scan frames leaf → root; the first frame that matches an
   owner pattern owns the sample; frames matching no owner (stdlib, `re`,
   builtins) are skipped.** Owners, by module/function:
   - `producer.strip_ansi` — `ansi_utils.py:strip_ansi`;
   - `producer.classify` — `monitor_core.py:classify_content`, the to_thread batch fn (:369), `agent_key_from_pane`, any frame in `prompt_patterns.py`;
   - `producer.discovery` — `discover_panes_with_shadows_async`, `_discover_panes_multi_async`, `_parse_list_panes`;
   - `producer.capture` — `capture_all_classified_async` and the capture helpers it calls in `monitor_core.py`;
   - `producer.tmux_io` — `_tmux_async`, anything in `lib/tmux_exec.py`, `TmuxControlClient` / `TmuxControlBackend` methods (incl. their reader thread);
   - `commit` — `commit_snapshots`, `_apply_bookkeeping`;
   - `app` — any other frame in `minimonitor_app.py` / `monitor_app.py` / `monitor_core.py` (our UI-state code);
   - `textual.render` — frames in Textual/Rich rendering modules only: `textual/_compositor.py`, `textual/strip.py`, `textual/_styles_cache.py`, `textual/css/`, `textual/renderables/`, `textual/drivers/` (output write), `widget.py` `render*`/`_render*`/`refresh`, `rich/` (segment/console/text render);
   - `textual.dispatch` — every other `textual/` frame (message pump, event dispatch, timers, mount bookkeeping);
   - `asyncio` — `asyncio/` and `selectors` frames; `other` — none of the above.
   Because Textual never calls the producer directly but does call it via
   timer/message dispatch, leaf-first gives a producer frame invoked from a
   Textual timer to the producer, and Textual work invoked from our code (e.g.
   `mount` from a list rebuild) to Textual — one rule, no exception. Output:
   samples and % per bucket, per thread and overall, plus "producer total" =
   Σ `producer.*`.
   - **Validation before interpreting real data:** a fixture file of hand-written
     stacks with expected owners — `re.sub` under `strip_ansi`; classify batch
     in a worker thread; `_compositor` under `message_pump`; producer under a
     Textual timer callback; `mount` under `_rebuild_pane_list`; a bare
     `selectors.select` stack; a TmuxControlClient reader-thread stack. The
     script asserts every expected owner and that bucket sums equal the sample
     count. On each real profile, print the top 10 stacks of every bucket and
     read them; any `other` / `textual.dispatch` stack above 2 % of samples is
     inspected and, if misattributed, a rule is added and **all** profiles are
     re-bucketed.
   - **Consistency check (not an attribution validation):** `tickcount.py`
     (step 4) measures **warm** producer CPU per tick (see step 4: same settings
     as the app, warm-up ticks discarded, ≥ 60 s at the real cadence so the
     10 s session-discovery cache, `_SESSIONS_CACHE_TTL` at
     `monitor_core.py:1964`, cycles ≥ 6 times). Warm producer CPU per second
     (= mean per-tick CPU / refresh_seconds) divided by the measured instance
     CPU rate gives a second producer-share figure. Report both side by side
     and explain any gap above 10 pp. The gap is **not** pass/fail: the two
     workloads still differ (no Textual and no event-loop contention in the
     harness). Attribution correctness rests on the pre-phase probe, the bucket
     fixture and the top-stack review.

2. **Current (not lifetime) CPU baseline, read-only.** `$S/cpurate.sh` reads
   `utime+stime` from `/proc/<pid>/stat` for every monitor/minimonitor PID and
   the tmux server, sleeps 60 s, reads again, prints %CPU per PID over the
   window, the per-class sum, and the tmux server rate. Run twice.

3. **Live profile (real tmux server, real agents).** In the live `ait` server
   create a probe window `t2034probe` (non-`agent-*` name) whose first pane runs
   `sleep infinity`, capturing the window id via `new-window -P -F '#{window_id}'`.
   Split a second pane that runs
   `env AITASKS_TMUX_SOCKET=ait $S/spyenv/bin/py-spy record -r 100 -d 180 --threads -f raw -o $S/live_minimonitor.txt -- <app python> .aitask-scripts/monitor/minimonitor_app.py`
   (cwd = repo root, plus any env `aitask_minimonitor.sh` exports). Apply the
   pre-collection checks and the liveness watcher. Then the same for
   `monitor/monitor_app.py` → `$S/live_monitor.txt` (no companion pane needed,
   liveness still watched). Also capture one `-f flamegraph` SVG each for visual
   sanity. Bucket with `bucket.py`. The probe window holds no agent, so no review
   loop or send-keys has a target. Close the window afterwards by its id, never
   by name.

4. **capture-pane rate across all running instances.** `$S/tickcount.py`
   (run with the app python from the repo root, `AITASKS_TMUX_SOCKET` explicit)
   builds a `TmuxMonitor` the way `minimonitor_app.py:1706` does (multi-session,
   control client started) **with the app's own settings**: capture_lines,
   idle_threshold, compare_mode and refresh_seconds come from the same
   `tmux.monitor` project config the app's `main()` loads
   (`minimonitor_app.py:5824`). It wraps `_tmux_async` to count calls by tmux
   verb. It runs 2 warm-up ticks (discarded), then ticks of discovery +
   `capture_all_classified_async` + `commit_snapshots` every refresh_seconds
   for ≥ 60 s. It prints the resolved socket, discovered sessions, agent/shadow
   pane counts, and per-verb calls per tick plus `process_time` CPU per tick as
   mean / p50 / p95 over the warm ticks. (For the pre-collection checks only
   the first tick's discovery output is used.) System rate = Σ over running instances of
   captures_per_tick / refresh_seconds, plus the monitors' preview captures
   (1 per 0.3 s while a pane is focused — confirm by reading
   `_fast_zone_refresh`). Instances of other checkouts (aitasks_go,
   thinking_app, thinking_backend, animeless) may run other framework
   versions; report the figure as an estimate and say so. Report the live tmux
   server CPU (step 2) and the estimated capture rate **as two separate
   figures**. If a ratio is shown at all, it is labelled "total server CPU
   normalised per capture". That is an upper bound covering terminal output,
   discovery, control clients and everything else, **not** the cost of a
   capture. Any marginal-cost claim comes only from the controlled comparison
   in step 5.

5. **Scaling: 1 agent vs several, on an isolated tmux server.**
   `SOCK=ait_t2034_1_$$` (asserted non-empty and `!= ait` before every use).
   One session; N windows `agent-pick-90<i>`, each with a fake-agent pane
   (`$S/fakeagent.sh`: prints a few hundred lines of ANSI-coloured text, then
   appends a line per second, foreground forever). The measured minimonitor is
   launched in a second pane of window `agent-pick-901` (companion layout) with
   `env AITASKS_TMUX_SOCKET=$SOCK py-spy record -r 100 -d 120 --threads -f raw …`.
   For N ∈ {1, 4, 12}: pre-collection checks (exactly N agents, only the
   scratch session), liveness watcher, `cpurate` of the minimonitor and of the
   scratch tmux server, bucket the stacks, `tickcount.py` against `$SOCK`.
   **Controlled server-cost comparison** at N = 12, fake-agent output held
   constant: measure scratch tmux server CPU (`cpurate`, 2 × 60 s windows each)
   with K = 0 (agents only: the output-processing baseline), K = 1 and K = 4
   unprofiled companion minimonitors in distinct agent windows. Each K's capture
   rate comes from `tickcount.py`'s warm per-tick counts × K / refresh_seconds.
   The marginal server cost of scanning is Δ(server CPU) / Δ(capture rate)
   between K levels, labelled "per capture **including** its share of
   discovery and control-client traffic". That bundle is what a shared server
   removes, so the claim stays at that granularity. Report it only if the K
   steps are monotonic and the repeat windows agree within their spread;
   otherwise report the raw table without a marginal figure.
   Teardown: `tmux -L "$SOCK" kill-server` — only after the guard re-asserts
   `$SOCK` is the scratch name (kill-server on `ait` would kill every live
   agent).

6. **Write results into this plan** (Final Implementation Notes): method,
   profiler + interpreter used, probe result, tables — per-bucket % (overall and
   per thread) for live minimonitor / live monitor with sample count, duration,
   rate, timestamp; the cross-check estimate; scaling table (N, K → instance
   CPU %, producer %, tmux server CPU %, captures/s); system capture-pane rate;
   tmux server share — and an explicit conclusion: if producer share is small,
   say so and note it lowers the t2038 Go-server payoff but not the
   single-idle-clock gain (parent "Why"). Include `burst.py`, `bucket.py` (with
   its fixture), `cpurate.sh`, `tickcount.py`, `fakeagent.sh` and the launch
   commands **verbatim**, so the numbers are reproducible after archival.

7. **Hand findings onward** — if numbers change sibling/parent assumptions
   (e.g. tmux server cost dominates → the server should also drop the 0.3 s
   preview capture), send an `ait note` to t2037 / t2034 rather than editing them.

### Post-phase

Remove `$S/spyenv` (and `$S/app313` if built) and the probe window; verify
`pgrep -f t2034probe` and `tmux -L "$SOCK" ls` report nothing.

## Verification

- Pre-phase probe meets its ±5 pp criterion on the interpreter actually used.
- `bucket.py` fixture assertions pass; bucket sums equal sample counts on every
  real input; top-stack review done for each bucket.
- Every run passed its pre-collection checks (socket in environ, expected
  sessions/agent count) and its liveness watch.
- Sampling producer share and the warm `tickcount.py` figure are both
  reported; a gap above 10 pp is explained (consistency check, not a gate).
- Server CPU and capture rate reported separately; any marginal server cost
  comes only from the K = 0/1/4 controlled comparison.
- Live tmux server untouched except the transient probe window (closed by id);
  scratch server gone; no files changed in the repo besides the plan.

## Step 9 reference

No code commit (Step 8 commits nothing but this plan); Step 9 archives the task
and plan per the standard post-implementation flow.

## Risk

### Code-health risk: low
- No repository code is changed; the only live-system effects are one transient probe window in the `ait` tmux server and a scratch tmux server · severity: low · → mitigation: none needed (teardown by window id / guarded scratch-socket kill in steps 3, 5 and post-phase)

### Goal-achievement risk: low
- py-spy 0.4.3 may not support CPython 3.14.9, blocking the sampling profile as specified · severity: medium · → mitigation: inline pre-phase probe_pyspy_py314
- A benchmark process could resolve the wrong tmux server (gateway pins `-L ait` unless `AITASKS_TMUX_SOCKET` is set) or a solitary minimonitor could auto-close mid-run · severity: high → addressed in the plan body (explicit socket env, companion layout, pre-collection checks, liveness watcher)
- Bucket attribution could mislabel dispatch as render · severity: medium → addressed in the plan body (single leaf-first ownership rule, fixture, top-stack review; the warm tickcount figure is a consistency check only)
- Server-side cost could be misread as capture cost · severity: medium → addressed in the plan body (server CPU and capture rate reported separately; marginal cost only from the K = 0/1/4 controlled comparison)
- The system-wide capture-pane rate is computed from a one-tick count × instance count, not measured on the tmux server (no ptrace on it); other framework checkouts may scan differently · severity: low · → mitigation: none (reported as an estimate, cross-checked against the measured tmux-server CPU rate)

Post-insertion reassessment: the pre-phase guarantees a validated profiler (or
an explicit stop); goal-achievement **low**, code-health **low**.

### Planned mitigations
- name: probe_pyspy_py314 · timing: inline-pre · inline_risk: low · added_complexity: low · addresses: py-spy / CPython 3.14 feasibility
