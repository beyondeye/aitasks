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

## Final Implementation Notes

- **Actual work done:** Measurement only, no repository code changed. All
  steps ran on 2026-11-03 between 13:40 and 14:35 (local time) on omg16
  (24 cpus, load about 6.7, CPython 3.14.9, py-spy 0.4.3 in a throwaway venv,
  removed afterwards). Every measured process was launched with
  `AITASKS_TMUX_SOCKET` set explicitly. Each run passed its pre-collection
  check (`/proc/<pid>/environ` socket; discovered sessions and agent count) and
  its liveness watch. Results follow. The scripts are reproduced verbatim in
  the appendix.

### Results

**R1 — live fleet CPU now (`cpurate.sh`, two 60 s windows, read-only).** 38
minimonitors use **140.0–157.9 % of one core** combined (per instance: median
3.85 %, range 2.68–4.60 %). 4 monitors use 7.6–8.8 % combined (1.70–2.07 %
each). The **tmux server (pid 8760) uses 64.9–72.9 %**. Monitoring therefore
costs about **2.2–2.4 cores** in total. ps lifetime averages (21 % for the
tmux server) understate the current load.

**R2 — live profiles.** Each profile is a fresh instance on the live `ait`
server: 5 sessions, 38 agent windows, 35 `capture-pane` per tick. Settings:
py-spy `--gil`, 100 Hz, 180 s. "Steady" means the 180 s run minus a 20 s
startup run (two different instances, so the subtraction is approximate).
"Coverage" means GIL-held sample-seconds ÷ measured utime+stime.

| bucket (% of GIL-held samples) | minimonitor 180 s | minimonitor steady | monitor 180 s | monitor steady |
|---|---|---|---|---|
| producer.tmux_io (control-client thread + gateway) | 10.4 | 11.2 | 25.4 | 31.1 |
| producer.strip_ansi | 2.4 | 2.0 | 8.8 | 9.9 |
| producer.classify | 0.4 | 0.3 | 1.1 | 0.9 |
| producer.discovery / capture / taskinfo | 0.3 | 0.0 | 0.6 | 0.9 |
| **PRODUCER TOTAL** | **13.5** | **13.6** | **36.0** | **42.7** |
| commit | 0.1 | 0.2 | 0.4 | 0.6 |
| app (our UI-state code) | 8.3 | 5.6 | 9.1 | 7.3 |
| textual.render | 52.5 | 54.7 | 26.0* | 29.1 |
| textual.dispatch | 25.1 | 25.5 | 28.0* | 20.6 |
| **TEXTUAL TOTAL** | **77.6** | **80.2** | **54.0** | **49.7** |
| samples / idle.wait excluded | 771 / 21 | 640 | 471 / 18 | 344 |
| app CPU (utime / stime), % of a core | 7.38 s / 0.92 s, 4.65 % | ≈4.0 % | 4.20 s / 0.89 s, 2.83 % | ≈2.15 % |
| coverage | 93 % | — | 93 % | — |

\* The monitor's 180 s render/dispatch split is from the first bucketing
pass. The final rules move some markup/style/filter frames from dispatch to
render, and leave the producer and Textual totals unchanged. The final
per-file outputs are in `*.buckets.txt` in the scratch dir. Producer CPU is
dominated by **parsing the control-mode output stream**
(`tmux-control-loop` thread), not by `strip_ansi` or classification.

**R3 — consistency check (warm `tickcount.py`; not a gate).** On the live
server, 21 warm ticks with the app's config (capture_lines 200, stripped,
3 s) cost 21.27 ms CPU per tick (p50 20.98, p95 26.57), i.e. **0.709 % of a
core**, with 35 `capture-pane` + 5 `list-panes` per tick and 316 ms wall time
per tick.
- Minimonitor: 0.709 ÷ 4.65 = 15.2 %, against 13.5–13.6 % sampled. The gap
  is 1.6 pp.
- Monitor: 0.709 ÷ 2.83 = 25 %, against 36–43 % sampled. The gap is over
  10 pp. This is not explained by measurement. Hypothesis: the monitor makes
  tmux calls beyond the minimonitor's producer tick, which `tickcount.py` does
  not replicate (it mirrors the minimonitor sequence only).

**R4 — system `capture-pane` rate (estimate).** 42 scanners (38 + 4) × 35 ÷
3 s ≈ **490 `capture-pane`/s**, plus ≈ 70 `list-panes`/s. Session discovery
(`list-sessions` / `show-environment`, 10 s cache) bypasses `_tmux_async` and
is not counted. The 0.3 s monitor preview capture runs only while a
monitor's PREVIEW/SHADOW zone is focused, so it contributes about 0 for idle
monitors. Instances from other checkouts may run other framework versions.
- Live tmux server CPU: 65–73 % of a core.
- Total server CPU normalised per capture: ≈ 1.3–1.5 ms. This is an upper
  bound that includes everything else the server does, **not the cost of a
  capture**.

**R5 — scaling on an isolated server** (`-L ait_t2034_1_scale`, one session,
N fake agents with real task-id window names, 200×50 panes, 300 lines of
ANSI output + 1 line/2 s). Per-instance CPU is steady state (`cpurate`, two
60 s windows after a 20 s warm-up). Producer CPU is from `tickcount.py`
(warm, 30 s).

| N agents | capture-pane / tick | minimonitor CPU % (steady) | producer % of a core | producer share | tmux server % (K = 1) |
|---|---|---|---|---|---|
| 1 | 1 | 0.22 | 0.062 | ≈ 28 % | 0.05–0.07 |
| 4 | 4 | 0.67–0.72 | 0.132 | ≈ 19 % | 0.23 |
| 12 | 12 | 1.22–1.35 (K=1), 1.17–1.42 (K=4) | 0.33–0.37 | ≈ 27 % | 0.72–0.82 |
| 38 (live) | 35 | 3.85 (median) | 0.709 | ≈ 18 % (13.6 % sampled) | — |

Both per-instance totals grow with N: producer at ≈ 0.02–0.03 % of a core per
agent, and Textual too, because each minimonitor renders every agent's card.
The profiled N runs (120 s, including startup) had only 64 / 144 / 168
GIL-held samples (coverage 53 / 75 / 63 %, the gap being GIL-released
syscall time). Their producer shares of 18.2 / 17.7 / 17.4 % are therefore
indicative only.

**R6 — controlled tmux-server cost** (N = 12, agent output held constant,
two 60 s windows each).

| K scanners | tmux server % of a core |
|---|---|
| 0 (agents only) | 0.02–0.03 |
| 1 | 0.72–0.82 (mean 0.77) |
| 4 | 2.62–2.73 (mean 2.68) |

The K steps are monotonic and the repeat windows agree within ±0.05.
- Marginal server cost per scanner at N = 12: (2.68 − 0.77) / 3 = **0.64 % of
  a core**.
- With 4 captures/s per scanner, that is ≈ **1.6 ms server CPU per
  `capture-pane`, including its share of discovery and control-client
  traffic**.
- Agent output alone costs the server almost nothing. So server CPU is
  scanning, growing as N × K. That is consistent with the live upper bound in
  R4.

### Conclusions

1. **In-process scanning is a minority of each minimonitor's CPU.** It is
   ≈ 14–18 % live and ≈ 19–28 % synthetic. Textual compose/render is
   ≈ 80 % live. The monitor is more producer-heavy (≈ 43 % steady). A shared
   server therefore saves roughly 0.65 % of a core per minimonitor and
   ≈ 0.9 % per monitor, about **0.28 of a core** across today's 42 scanners.
2. **The tmux server is the largest single scan cost** (65–73 % of a core
   live), and it is almost entirely scanning. One shared scanner removes
   ≈ (K − 1)/K of it, which is ≈ **0.63–0.71 of a core** at K = 42. Combined
   saving ≈ **0.9–1.0 core** out of ≈ 2.3 spent on monitoring.
3. **The payoff comes from deduplication (t2037), not from the server's
   language.** One Python producer costs ≈ 0.7–0.9 % of a core. This
   **lowers the CPU payoff of the Go server (t2038 → aitasks_go#t47)**: its
   case rests on memory (aitasks_go#16), not CPU. The single-idle-clock gain
   is unaffected.
4. **The largest cost the server does not touch is minimonitor rendering**:
   ≈ 38 × 3.1 % ≈ **1.2 cores** at live scale. It grows with N because every
   minimonitor re-renders every agent's card on each tick
   (`_rebuild_pane_list`). This is new work: a follow-up task candidate, to
   be offered at review.

### Deviations from plan

- **`--gil` mode.** Without `--gil`, py-spy 0.4.3 on CPython 3.14 counts
  threads blocked in `EpollSelector.select`, `SelectSelector.select`,
  `Condition.wait` and the idle `ThreadPoolExecutor` `_worker` as active. In
  the first live run that was 58 % of samples (sample-seconds ≈ 2.6× real
  CPU). The extended probe `burst_waits.py` showed the default mode at 134 %
  coverage with wrong shares, and `--gil` at 101 % coverage with shares within
  2 pp. The original `burst.py` probe (sleep only) had passed and missed this.
  `--gil` cannot see GIL-released syscall CPU, so coverage is reported per
  run.
- **bucket.py rules.** Found by the fixture and the top-stack review:
  - stdlib asyncio is a non-owner, with a residual `asyncio` bucket only when
    no owner frame exists;
  - `textual/cache.py` is a non-owner;
  - an `idle.wait` leaf bucket is excluded from the denominator;
  - the render set gained `markup.py`, `style.py`, `filter.py` and
    `Widget._get_box_model`.

  All profiles were re-bucketed with the final rules (16-case self-test).
- **Startup subtraction.** Startup was removed using separate 20 s runs, an
  approximation across instances.
- **Discarded run.** One run was discarded: redirecting py-spy's stderr also
  redirected the app's stderr, and Textual draws to stderr, so the TUI
  rendered into a file. The launcher now leaves stdout/stderr on the pane pty.
- **Fake agents run bash.** They get generic classification (no claude/codex
  prompt pattern). Classification is ≤ 1 % of samples anyway.
- **No sudo attach.** The companion layout plus a non-agent probe window kept
  the profiled minimonitor alive. The probe window was renamed `monitor` by
  the profiled monitor app and closed by id `@113` after verifying that its
  only remaining pane was `sleep infinity`.

- **Issues encountered:** see Deviations.
- **Key decisions:** use `--gil` with per-run coverage; base the N-scaling
  claims on measured process CPU + warm tick CPU, not on low-count bucket
  shares; quote a marginal server cost only from the K = 0/1/4 comparison.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - t2034_2 / t2034_3: producer cost is dominated by the control-mode stream
    parse (`TmuxControlClient._reader_loop` thread), not by
    strip/classification.
  - A protocol pushing per-pane deltas lets clients skip re-rendering
    unchanged cards. That is where the remaining per-client CPU is (R2, R5,
    conclusion 4).

## Appendix — scripts (verbatim, as run)

Scratch dir `$S` as in Method. Launch commands: live = `tmux -L ait new-window -d -t aitasks: -n t2034probe -P -F '#{window_id} #{pane_id}' 'sleep infinity'` then `tmux -L ait split-window -d -t <wid> -h -P -F '#{pane_id} #{pane_pid}' "$S/run_spy.sh ait live_<app> 180 <app>"` + `watch.sh <pane_pid> ait <log>`; scaling = `scale.sh profile N` / `scale.sh servercost N K`; baseline = `cpurate.sh 60`; tick = `env AITASKS_TMUX_SOCKET=ait python -I tickcount.py --project-root <repo> --duration 60`; probes = `py-spy record -r 200 -d 12|14 -f raw --threads [--gil] -- python burst.py|burst_waits.py 10`.

### `burst.py`

````python
"""Known burst-and-sleep workload for validating the profiler (t2034_1 pre-phase).

Main thread: 2 ms CPU bursts, ~70 % in burn_a and ~30 % in burn_b, each burst
followed by a 5 ms sleep. Worker thread: 2 ms bursts in burn_c, 4 ms sleep.
Each function measures its own thread CPU time; totals are printed as JSON at
exit so the profiler's sample shares can be compared with ground truth.
"""
import json
import random
import sys
import threading
import time

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
cpu = {"burn_a": 0.0, "burn_b": 0.0, "burn_c": 0.0}
lock = threading.Lock()


def _spin(ms):
    end = time.thread_time() + ms / 1000.0
    x = 0
    while time.thread_time() < end:
        x += 1
    return x


def burn_a():
    t0 = time.thread_time()
    _spin(2)
    with lock:
        cpu["burn_a"] += time.thread_time() - t0


def burn_b():
    t0 = time.thread_time()
    _spin(2)
    with lock:
        cpu["burn_b"] += time.thread_time() - t0


def burn_c():
    t0 = time.thread_time()
    _spin(2)
    with lock:
        cpu["burn_c"] += time.thread_time() - t0


def worker(stop):
    while not stop.is_set():
        burn_c()
        time.sleep(0.004)


def main():
    rnd = random.Random(1)
    stop = threading.Event()
    th = threading.Thread(target=worker, args=(stop,), name="worker")
    th.start()
    end = time.monotonic() + DURATION
    while time.monotonic() < end:
        if rnd.random() < 0.7:
            burn_a()
        else:
            burn_b()
        time.sleep(0.005)
    stop.set()
    th.join()
    total = sum(cpu.values())
    print(json.dumps({k: round(v / total * 100, 1) for k, v in cpu.items()}
                     | {"total_cpu_s": round(total, 3)}), file=sys.stderr)


if __name__ == "__main__":
    main()
````

### `burst_waits.py`

````python
"""burst.py + idle threads blocked in the app's real wait primitives:
EpollSelector.select (never-ready socketpair), SelectSelector.select,
threading.Condition.wait, and an idle ThreadPoolExecutor worker
(SimpleQueue.get). Prints ground-truth CPU (thread_time per burn fn and
process_time total) at exit."""
import concurrent.futures, selectors, socket, sys, threading, time
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else "10"]
import runpy
stop = threading.Event()
def epoll_waiter():
    a, b = socket.socketpair(); sel = selectors.EpollSelector(); sel.register(a, selectors.EVENT_READ)
    while not stop.is_set(): sel.select(timeout=0.5)
def select_waiter():
    a, b = socket.socketpair(); sel = selectors.SelectSelector(); sel.register(a, selectors.EVENT_READ)
    while not stop.is_set(): sel.select(timeout=0.5)
def cond_waiter():
    c = threading.Condition()
    with c:
        while not stop.is_set(): c.wait(timeout=0.5)
pool = concurrent.futures.ThreadPoolExecutor(1); pool.submit(lambda: None).result()
for f in (epoll_waiter, select_waiter, cond_waiter):
    threading.Thread(target=f, daemon=True, name=f.__name__).start()
p0 = time.process_time()
g = runpy.run_path(sys.argv[0].replace("burst_waits.py", "burst.py"), run_name="__main__")
stop.set(); pool.shutdown()
print(f"PROCESS_CPU_S {time.process_time() - p0:.3f}", file=sys.stderr)
````

### `bucket.py`

````python
#!/usr/bin/env python3
"""Bucket py-spy raw (collapsed) stacks into producer / Textual / other owners.

Input: `py-spy record --threads --full-filenames -f raw` output, one line per
unique stack: ``thread (<tid>): <name>;frame;frame;... <count>``, root first.
Each frame is ``<qualname> (<path>:<line>)``.

OWNERSHIP POLICY (the single rule): scan frames leaf -> root; the first frame
matching an owner rule owns the sample. Frames matching no owner (stdlib,
`re`, builtins, site-packages other than textual/rich) are skipped.

Usage:
  bucket.py --selftest
  bucket.py PROFILE.txt [--top N] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict

FRAME_RE = re.compile(r"^(?P<func>.*) \((?P<path>[^()]*?)(?::(?P<line>\d+))?\)$")

DISCOVERY_FUNCS = {
    "discover_panes_with_shadows_async", "_discover_panes_multi_async",
    "_discover_panes_multi", "_parse_list_panes", "_target_sessions_async",
    "_target_sessions", "_discover_sessions_cached_async",
    "_discover_sessions_cached", "get_session_to_project_mapping",
    "get_session_to_project_mapping_async", "_is_companion_pane",
    "_evict_companion_memo", "classify_pane", "_record_discovery_facts",
    "_publish_discovery_facts", "discover_panes", "discover_panes_async",
    "discover_window_panes", "discover_window_panes_async",
    "_parse_window_panes",
}
CAPTURE_FUNCS = {
    "capture_all_classified_async", "capture_pane", "capture_pane_async",
    "capture_pane_content_async", "capture_pane_classified_async",
    "_capture_args", "_finalize_capture", "refresh_shadow_snapshot",
    "_merge_shadow_snapshot", "_run_offloaded", "capture_cursor_async",
    "capture_all", "capture_all_async", "_next_generation",
    "_is_parked_pane", "_is_frozen_pane", "_next_shadow_write_seq",
}
CLASSIFY_FUNCS = {"classify_content", "_classify_one", "_classify_batch"}
COMMIT_FUNCS = {"commit_snapshots", "commit_snapshot", "_apply_bookkeeping",
                "_clean_stale"}
TEXTUAL_RENDER_FILES = {
    "_compositor.py", "strip.py", "_styles_cache.py", "_segment_tools.py",
    "_border.py", "_spatial_map.py", "_arrange.py", "_layout.py",
    "_resolve.py", "content.py", "visual.py", "_cells.py", "geometry.py",
    # added after the top-stack review of live_minimonitor (render pipeline:
    # markup -> content, style resolution, output colour filters):
    "markup.py", "style.py", "filter.py", "_box_model.py",
}
TEXTUAL_NONOWNER_FILES = {"cache.py"}
#: Leaf frames that are a thread BLOCKED in a wait. Under --gil these should
#: never be sampled (the GIL is released while waiting); any sample here is
#: reported as `idle.wait` and excluded from the CPU-share denominator.
WAIT_LEAVES = {
    ("EpollSelector.select", "selectors.py"), ("SelectSelector.select", "selectors.py"),
    ("Condition.wait", "threading.py"), ("_worker", "thread.py"),
    ("Queue.get", "queue.py"), ("Event.wait", "threading.py"),
}
TEXTUAL_RENDER_DIRS = ("/textual/css/", "/textual/renderables/",
                       "/textual/drivers/", "/textual/layouts/")

BUCKETS = [
    "producer.strip_ansi", "producer.classify", "producer.discovery",
    "producer.capture", "producer.tmux_io", "producer.taskinfo", "commit",
    "app", "textual.render", "textual.dispatch", "asyncio", "other", "idle.wait",
]


def parse_frame(frame: str) -> tuple[str, str]:
    m = FRAME_RE.match(frame.strip())
    if not m:
        return frame.strip(), ""
    return m.group("func"), m.group("path") or ""


def owner_of(frame: str) -> str | None:
    """Owner bucket of ONE frame, or None if this frame owns nothing."""
    qual, path = parse_frame(frame)
    func = qual.rsplit(".", 1)[-1]
    cls = qual.rsplit(".", 1)[0] if "." in qual else ""
    base = path.rsplit("/", 1)[-1]
    ours = "/.aitask-scripts/" in path or path.startswith(".aitask-scripts/")

    if ours:
        if base == "ansi_utils.py":
            return "producer.strip_ansi"
        if base in ("prompt_patterns.py", "agent_keys.py"):
            return "producer.classify"
        if base == "monitor_core.py" and func in CLASSIFY_FUNCS:
            return "producer.classify"
        if base in ("tmux_exec.py", "tmux_control.py"):
            return "producer.tmux_io"
        if cls in ("TmuxControlClient", "TmuxControlBackend") or func in (
                "_tmux_async", "_quote_arg", "tmux_run_async", "tmux_run"):
            return "producer.tmux_io"
        if base == "monitor_core.py" and func in DISCOVERY_FUNCS:
            return "producer.discovery"
        if base == "monitor_core.py" and func in CAPTURE_FUNCS:
            return "producer.capture"
        if base == "monitor_core.py" and func in COMMIT_FUNCS:
            return "commit"
        if cls == "TaskInfoCache":
            return "producer.taskinfo"
        return "app"
    if "/rich/" in path:
        return "textual.render"
    if "/textual/" in path and base in TEXTUAL_NONOWNER_FILES:
        return None   # generic utility (FIFOCache...): the caller owns it
    if "/textual/" in path:
        if base in TEXTUAL_RENDER_FILES or any(d in path for d in TEXTUAL_RENDER_DIRS):
            return "textual.render"
        if base == "widget.py" and (func.startswith("render") or func.startswith("_render")
                                    or func in ("refresh", "_get_box_model")):
            return "textual.render"
        return "textual.dispatch"
    # stdlib — asyncio included — never owns: an asyncio frame called FROM our
    # code (StreamReader.readline in the control reader) is that caller's cost.
    return None


def _is_asyncio(frame: str) -> bool:
    _, path = parse_frame(frame)
    return "/asyncio/" in path or path.endswith("/selectors.py")


def classify_stack(frames: list[str]) -> str:
    if frames:
        q, pth = parse_frame(frames[-1])
        if (q, pth.rsplit("/", 1)[-1]) in WAIT_LEAVES:
            return "idle.wait"
    for fr in reversed(frames):          # leaf -> root
        o = owner_of(fr)
        if o is not None:
            return o
    # Residual (no owner frame at all): event-loop machinery vs anything else.
    return "asyncio" if any(_is_asyncio(f) for f in frames) else "other"


def parse_line(line: str) -> tuple[str, list[str], int] | None:
    line = line.rstrip("\n")
    if not line.strip():
        return None
    body, _, count = line.rpartition(" ")
    parts = body.split(";")
    thread = parts[0]
    m = re.match(r"thread \((\w+)\): ?(.*)", thread)
    # py-spy sometimes emits no name ("thread (<tid>)"); in these profiles
    # those stacks are the main thread's (App.run -> Timer._tick ...).
    tname = m.group(2) if m else "MainThread(unnamed)"
    tname = re.sub(r"_\d+$", "_N", tname) or "?"
    return tname, parts[1:], int(count)


def bucket_file(path: str):
    total = Counter()
    per_thread: dict[str, Counter] = defaultdict(Counter)
    stacks: dict[str, Counter] = defaultdict(Counter)
    n = 0
    with open(path) as fh:
        for line in fh:
            p = parse_line(line)
            if p is None:
                continue
            tname, frames, cnt = p
            b = classify_stack(frames)
            total[b] += cnt
            per_thread[tname][b] += cnt
            stacks[b][";".join(frames[-6:])] += cnt
            n += cnt
    assert sum(total.values()) == n, "bucket sums != sample count"
    assert sum(sum(c.values()) for c in per_thread.values()) == n
    return n, total, per_thread, stacks


def selftest() -> None:
    T = "/home/u/.aitask/venv/lib/python3.14/site-packages/textual"
    A = "/home/u/Work/aitasks/.aitask-scripts"
    L = "/usr/lib/python3.14"
    cases = [
        # re.sub under strip_ansi -> strip_ansi (leaf-first skips stdlib re)
        ([f"MiniMonitorApp._refresh_data ({A}/monitor/minimonitor_app.py:1)",
          f"TmuxMonitor.capture_all_classified_async ({A}/monitor/monitor_core.py:3400)",
          f"strip_ansi ({A}/monitor/ansi_utils.py:40)",
          f"sub ({L}/re/__init__.py:208)"], "producer.strip_ansi"),
        # classify batch in a worker thread
        ([f"Thread._bootstrap ({L}/threading.py:1044)",
          f"_WorkItem.run ({L}/concurrent/futures/thread.py:59)",
          f"_classify_batch ({A}/monitor/monitor_core.py:375)",
          f"_classify_one ({A}/monitor/monitor_core.py:350)",
          f"classify_content ({A}/monitor/monitor_core.py:300)",
          f"search ({L}/re/__init__.py:177)"], "producer.classify"),
        # compositor under message pump
        ([f"MessagePump._process_messages ({T}/message_pump.py:600)",
          f"Screen._refresh_layout ({T}/screen.py:1200)",
          f"Compositor.render_update ({T}/_compositor.py:900)"], "textual.render"),
        # producer under a Textual timer callback
        ([f"Timer._run ({T}/timer.py:180)",
          f"invoke ({T}/_callback.py:90)",
          f"MiniMonitorApp._refresh_data ({A}/monitor/minimonitor_app.py:1)",
          f"TmuxMonitor.discover_panes_with_shadows_async ({A}/monitor/monitor_core.py:2830)",
          f"TmuxMonitor._parse_list_panes ({A}/monitor/monitor_core.py:2600)"], "producer.discovery"),
        # mount under our list rebuild -> Textual (dispatch, not ours)
        ([f"MiniMonitorApp._rebuild_pane_list ({A}/monitor/minimonitor_app.py:2000)",
          f"Widget.mount ({T}/widget.py:1100)",
          f"MessagePump.post_message ({T}/message_pump.py:800)"], "textual.dispatch"),
        # widget render under our code -> render
        ([f"MiniMonitorApp._rebuild_pane_list ({A}/monitor/minimonitor_app.py:2000)",
          f"Widget.render_lines ({T}/widget.py:4000)"], "textual.render"),
        # event-loop machinery with no owner (non-wait leaf) -> asyncio
        ([f"BaseEventLoop._run_once ({L}/asyncio/base_events.py:1990)",
          f"Handle._run ({L}/asyncio/events.py:94)"], "asyncio"),
        # control-client reader thread
        ([f"Thread._bootstrap ({L}/threading.py:1044)",
          f"TmuxControlBackend._thread_main ({A}/monitor/monitor_core.py:1845)",
          f"BaseEventLoop.run_until_complete ({L}/asyncio/base_events.py:700)",
          f"TmuxControlClient._reader_loop ({A}/monitor/monitor_core.py:1520)",
          f"StreamReader.readline ({L}/asyncio/streams.py:560)"], "producer.tmux_io"),
        # our pure app code
        ([f"MiniMonitorApp._refresh_data ({A}/monitor/minimonitor_app.py:1)",
          f"_sort_key ({A}/monitor/monitor_core.py:1270)"], "app"),
        # commit
        ([f"MiniMonitorApp._refresh_data ({A}/monitor/minimonitor_app.py:1)",
          f"TmuxMonitor.commit_snapshots ({A}/monitor/monitor_core.py:3510)",
          f"TmuxMonitor._apply_bookkeeping ({A}/monitor/monitor_core.py:2990)"], "commit"),
        # task info cache file IO
        ([f"MiniMonitorApp._refresh_data ({A}/monitor/minimonitor_app.py:1)",
          f"TaskInfoCache.get ({A}/monitor/monitor_core.py:4800)",
          f"open ({L}/pathlib/_local.py:530)"], "producer.taskinfo"),
        # FIFOCache under Strip (render) -> render, not dispatch
        ([f"Compositor._render_chops ({T}/_compositor.py:1239)",
          f"Strip.__init__ ({T}/strip.py:101)",
          f"FIFOCache.__init__ ({T}/cache.py:226)"], "textual.render"),
        # markup parsing under our card builder -> render (review-added rule)
        ([f"MiniMonitorApp._agent_card_text ({A}/monitor/minimonitor_app.py:2604)",
          f"_to_content ({T}/markup.py:368)"], "textual.render"),
        # blocked waits -> idle.wait whatever the owner above them
        ([f"App._process_messages ({T}/app.py:1)",
          f"BaseEventLoop._run_once ({L}/asyncio/base_events.py:2026)",
          f"EpollSelector.select ({L}/selectors.py:452)"], "idle.wait"),
        ([f"WriterThread.run ({T}/drivers/_writer_thread.py:57)",
          f"Queue.get ({L}/queue.py:199)",
          f"Condition.wait ({L}/threading.py:369)"], "idle.wait"),
        # pure stdlib -> other
        ([f"<module> (x.py:1)", f"sleep ({L}/time.py:1)"], "other"),
    ]
    for frames, want in cases:
        got = classify_stack(frames)
        assert got == want, f"{frames[-1]!r}: want {want}, got {got}"
    # sums: a synthetic file through the full path
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        for i, (frames, _) in enumerate(cases):
            fh.write(f"thread (0x{i}): MainThread;" + ";".join(frames) + f" {i + 1}\n")
        name = fh.name
    n, total, _, _ = bucket_file(name)
    assert n == sum(range(1, len(cases) + 1)) == sum(total.values())
    print(f"SELFTEST OK: {len(cases)} cases, {n} samples")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", nargs="?")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    n, total, per_thread, stacks = bucket_file(a.profile)
    prod = sum(v for k, v in total.items() if k.startswith("producer."))
    idle = total["idle.wait"]
    print(f"# {a.profile}: {n} samples ({idle} idle.wait excluded from %)")
    n = n - idle
    print(f"{'bucket':22} {'samples':>8} {'%':>6}")
    for b in BUCKETS:
        if total[b] and b != "idle.wait":
            print(f"{b:22} {total[b]:8d} {total[b] / n * 100:6.1f}")
    print(f"{'PRODUCER TOTAL':22} {prod:8d} {prod / n * 100:6.1f}")
    print(f"{'PRODUCER+COMMIT':22} {prod + total['commit']:8d} "
          f"{(prod + total['commit']) / n * 100:6.1f}")
    print("\n# per thread (non-idle samples; % of all non-idle samples)")
    for t, c in sorted(per_thread.items(), key=lambda kv: -sum(kv[1].values())):
        c = Counter({k: v for k, v in c.items() if k != "idle.wait"})
        tt = sum(c.values())
        parts = ", ".join(f"{b} {c[b] / n * 100:.1f}" for b in BUCKETS if c[b])
        print(f"{t}: {tt} ({tt / n * 100:.1f}%) — {parts}")
    if a.top:
        for b in BUCKETS:
            if not stacks[b]:
                continue
            print(f"\n## top stacks: {b}")
            for s, c in stacks[b].most_common(a.top):
                print(f"{c:6d} {c / n * 100:5.1f}%  {s}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"samples": n, "buckets": dict(total),
                       "per_thread": {k: dict(v) for k, v in per_thread.items()}},
                      fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### `steady.py`

````python
"""steady.py LONG.json SHORT.json LONG_S SHORT_S — steady-state buckets = long − short
(different instances, same host/conditions; an approximation, see plan notes)."""
import json, sys
L, Sh = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
ls, ss = float(sys.argv[3]), float(sys.argv[4])
keys = sorted(set(L["buckets"]) | set(Sh["buckets"]))
d = {k: L["buckets"].get(k, 0) - Sh["buckets"].get(k, 0) for k in keys if k != "idle.wait"}
n = sum(v for v in d.values())
prod = sum(v for k, v in d.items() if k.startswith("producer."))
print(f"steady window ≈ {ls - ss:.0f}s, {n} GIL samples ≈ {n/100:.2f} CPU-s ≈ {n/100/(ls-ss)*100:.2f}% of a core (GIL-held only)")
for k in ["producer.strip_ansi","producer.classify","producer.discovery","producer.capture","producer.tmux_io","producer.taskinfo","commit","app","textual.render","textual.dispatch","asyncio","other"]:
    if d.get(k): print(f"  {k:20} {d[k]:5d} {d[k]/n*100:6.1f}%")
print(f"  {'PRODUCER TOTAL':20} {prod:5d} {prod/n*100:6.1f}%")
print(f"  {'TEXTUAL TOTAL':20} {d.get('textual.render',0)+d.get('textual.dispatch',0):5d} {(d.get('textual.render',0)+d.get('textual.dispatch',0))/n*100:6.1f}%")
````

### `tickcount.py`

````python
"""Warm producer-tick counter (t2034_1 step 4).

Builds a TmuxMonitor exactly as minimonitor_app.main() + _start_monitoring do
(same project config: capture_lines, idle_threshold, agent_prefixes, tui_names,
compare_mode_default, refresh_seconds; multi-session; control client started),
wraps `_tmux_async` to count tmux calls by verb, and runs the minimonitor's
per-tick producer sequence:
    get_session_to_project_mapping_async()   (discovery-side session map)
    capture_all_async()                       (discovery + capture + classify + commit)
WARMUP ticks are discarded, then ticks run every refresh_seconds for DURATION s.
Reports per-verb calls/tick and process_time CPU/tick (mean/p50/p95, includes
the to_thread classify worker and the control-backend thread: process-wide).

Run from the repo root with the APP python:
  env AITASKS_TMUX_SOCKET=<sock> ~/.aitask/venv/bin/python tickcount.py \
      --project-root <repo> [--duration 60] [--warmup 2] [--json out.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--project-root", required=True)
ap.add_argument("--duration", type=float, default=60.0)
ap.add_argument("--warmup", type=int, default=2)
ap.add_argument("--session", default=None)
ap.add_argument("--json")
args = ap.parse_args()

if "AITASKS_TMUX_SOCKET" not in os.environ:
    sys.exit("refusing: AITASKS_TMUX_SOCKET must be set explicitly")
# The real minimonitor's TMUX_PANE is its own (non-agent) pane; ours would be
# this shell's pane, which may be a live agent — never exclude it by accident.
os.environ.pop("TMUX_PANE", None)

root = Path(args.project_root).resolve()
sys.path.insert(0, str(root / ".aitask-scripts"))
sys.path.insert(0, str(root / ".aitask-scripts" / "lib"))

from monitor.monitor_core import (  # noqa: E402
    TmuxMonitor, load_monitor_config, load_project_tmux_config,
)
import tmux_exec  # noqa: E402

cfg = load_monitor_config(root)
tcfg = load_project_tmux_config(root)
refresh = float(tcfg.get("monitor", {}).get("refresh_seconds", 3))


async def main() -> dict:
    session = args.session or "aitasks"
    mon = TmuxMonitor(
        session=session,
        capture_lines=cfg.get("capture_lines", 30),
        idle_threshold=cfg.get("idle_threshold", 5.0),
        agent_prefixes=cfg.get("agent_prefixes"),
        tui_names=cfg.get("tui_names"),
        compare_mode_default=cfg.get("compare_mode_default", "stripped"),
    )
    calls: Counter = Counter()
    orig = mon._tmux_async

    async def counted(a, timeout=5.0):
        calls[a[0] if a else "?"] += 1
        return await orig(a, timeout=timeout)

    mon._tmux_async = counted
    ok = await mon.start_control_client()
    out = {
        "socket_args": tmux_exec.tmux_socket_args(),
        "env_socket": os.environ.get("AITASKS_TMUX_SOCKET"),
        "control_client": bool(ok),
        "settings": {"capture_lines": mon.capture_lines,
                     "idle_threshold": mon.idle_threshold,
                     "compare_mode_default": mon.compare_mode_default,
                     "agent_prefixes": mon.agent_prefixes,
                     "refresh_seconds": refresh},
    }
    ticks = []
    try:
        n = 0
        t_end = None
        while True:
            calls.clear()
            c0 = time.process_time()
            w0 = time.monotonic()
            await mon.get_session_to_project_mapping_async()
            snaps = await mon.capture_all_async()
            cpu = time.process_time() - c0
            wall = time.monotonic() - w0
            if n == 0:
                out["first_tick"] = {
                    "sessions": sorted(mon.last_enumerated_sessions()),
                    "agent_windows": len(mon.last_discovered_agents()),
                    "snapshots": len(snaps or {}),
                }
            if n >= args.warmup:
                ticks.append({"cpu": cpu, "wall": wall, "calls": dict(calls),
                              "snapshots": len(snaps or {})})
                if t_end is None:
                    t_end = time.monotonic() + args.duration
            n += 1
            if t_end is not None and time.monotonic() >= t_end:
                break
            await asyncio.sleep(max(0.0, refresh - wall))
    finally:
        await mon.close_control_client()

    cpus = sorted(t["cpu"] for t in ticks)
    verbs = Counter()
    for t in ticks:
        verbs.update(t["calls"])
    out["warm"] = {
        "ticks": len(ticks),
        "cpu_ms_mean": round(statistics.mean(cpus) * 1000, 2),
        "cpu_ms_p50": round(cpus[len(cpus) // 2] * 1000, 2),
        "cpu_ms_p95": round(cpus[min(len(cpus) - 1, int(len(cpus) * 0.95))] * 1000, 2),
        "wall_ms_mean": round(statistics.mean(t["wall"] for t in ticks) * 1000, 1),
        "calls_per_tick": {k: round(v / len(ticks), 2) for k, v in verbs.items()},
        "snapshots_per_tick": round(statistics.mean(t["snapshots"] for t in ticks), 2),
        "producer_cpu_pct_of_core": round(statistics.mean(cpus) / refresh * 100, 3),
    }
    return out


res = asyncio.run(main())
print(json.dumps(res, indent=1, default=str))
if args.json:
    Path(args.json).write_text(json.dumps(res, indent=1, default=str))
````

### `cpurate.sh`

````bash
#!/usr/bin/env bash
# cpurate.sh [WINDOW_S] [PID...] — %CPU (of one core) per PID over a window,
# from /proc/<pid>/stat utime+stime deltas. Read-only.
# With no PIDs: every monitor_app.py / minimonitor_app.py process plus every
# tmux server ("new-session" / "-D" server process) found by pgrep.
set -euo pipefail
win="${1:-60}"; shift || true
hz=$(getconf CLK_TCK)
if [[ $# -gt 0 ]]; then pids=("$@"); else
  # tmux server pid straight from the server (read-only query); socket from
  # CPURATE_SOCK (default ait) — never inferred from $TMUX.
  mapfile -t pids < <( { pgrep -f 'monitor/(mini)?monitor_app\.py';
      tmux -L "${CPURATE_SOCK:-ait}" display-message -p '#{pid}'; } | sort -un)
fi
ticks() { local f; f=$(cat "/proc/$1/stat" 2>/dev/null) || { echo -1; return; }
  f=${f##*) }; read -r -a a <<<"$f"; echo $(( a[11] + a[12] )); }
declare -A t0
for p in "${pids[@]}"; do t0[$p]=$(ticks "$p"); done
s0=$(date +%s.%N); sleep "$win"; s1=$(date +%s.%N)
el=$(awk -v a="$s0" -v b="$s1" 'BEGIN{print b-a}')
printf '# window=%.1fs hz=%s at=%s\n' "$el" "$hz" "$(date -Is)"
sum_mini=0; sum_mon=0; sum_tmux=0; n_mini=0; n_mon=0
for p in "${pids[@]}"; do
  t1=$(ticks "$p"); [[ "${t0[$p]}" -lt 0 || "$t1" -lt 0 ]] && { echo "$p gone"; continue; }
  pct=$(awk -v d=$(( t1 - t0[$p] )) -v hz="$hz" -v el="$el" 'BEGIN{printf "%.2f", d/hz/el*100}')
  args=$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | cut -c1-110)
  case "$args" in
    *minimonitor_app.py*) cls=mini; sum_mini=$(awk -v a="$sum_mini" -v b="$pct" 'BEGIN{print a+b}'); n_mini=$((n_mini+1));;
    *monitor_app.py*)     cls=mon;  sum_mon=$(awk -v a="$sum_mon" -v b="$pct" 'BEGIN{print a+b}'); n_mon=$((n_mon+1));;
    *tmux*)               cls=tmux; sum_tmux=$(awk -v a="$sum_tmux" -v b="$pct" 'BEGIN{print a+b}');;
    *)                    cls=other;;
  esac
  printf '%-8s %6s%%  %-5s %s\n' "$p" "$pct" "$cls" "$args"
done
printf 'SUM minimonitor n=%d %.1f%%  monitor n=%d %.1f%%  tmux-server %.1f%%\n' \
  "$n_mini" "$sum_mini" "$n_mon" "$sum_mon" "$sum_tmux"
````

### `run_spy.sh`

````bash
#!/usr/bin/env bash
# run_spy.sh <sock> <out-basename> <duration-s> <app: minimonitor|monitor> [rate]
# Runs INSIDE a tmux pane. py-spy is a child of this shell and the app is
# py-spy's child (descendant ptrace is allowed at ptrace_scope=1). stdout and
# stderr stay on the pane's pty: Textual draws to stderr, so redirecting it
# would render the TUI into a file. The socket is passed explicitly, never
# inherited from the tmux server environment. After py-spy exits the pane
# --gil: only GIL-holding samples (validated in probe_waits: default mode
# counts threads blocked in select/Condition.wait/SimpleQueue.get as active).
# sleeps 600 s so its summary line ("Samples: N Errors: M") can be captured.
set -uo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
sock="$1"; out="$2"; dur="$3"; app="$4"; rate="${5:-100}"
[[ -n "$sock" ]] || { echo "empty socket" >&2; exit 2; }
cd /home/ddt/Work/aitasks
env AITASKS_TMUX_SOCKET="$sock" "$S/spyenv/bin/py-spy" record \
  -r "$rate" -d "$dur" --gil --threads --full-filenames -f raw -o "$S/$out.txt" \
  -- /home/ddt/.aitask/venv/bin/python ".aitask-scripts/monitor/${app}_app.py"
echo "PYSPY_RC=$?"
sleep 600
````

### `watch.sh`

````bash
#!/usr/bin/env bash
# watch.sh <pane-shell-pid> <expected-sock> <log> — pre-collection env check,
# then a 1 s liveness watch of py-spy's app child until py-spy exits.
set -uo pipefail
sh_pid="$1"; want="$2"; log="$3"
spy=""; app=""
for _ in $(seq 1 50); do spy=$(pgrep -P "$sh_pid" -f py-spy | head -1); [[ -n "$spy" ]] && break; sleep 0.2; done
[[ -n "$spy" ]] || { echo "NO_PYSPY" > "$log"; exit 1; }
for _ in $(seq 1 50); do app=$(pgrep -P "$spy" | head -1); [[ -n "$app" ]] && break; sleep 0.2; done
[[ -n "$app" ]] || { echo "NO_APP_CHILD" > "$log"; exit 1; }
env_sock=$(tr '\0' '\n' < "/proc/$app/environ" | sed -n 's/^AITASKS_TMUX_SOCKET=//p')
echo "app=$app env_sock=$env_sock start=$(date -Is)" > "$log"
[[ "$env_sock" == "$want" ]] || { echo "ENV_MISMATCH want=$want" >> "$log"; exit 1; }
hz=$(getconf CLK_TCK)
st() { local f; f=$(cat "/proc/$app/stat" 2>/dev/null) || return 1; f=${f##*) }; read -r -a a <<<"$f"; echo "${a[11]} ${a[12]}"; }
first=$(st); t_first=$(date +%s.%N); last="$first"; t_last="$t_first"
while kill -0 "$spy" 2>/dev/null; do
  if ! kill -0 "$app" 2>/dev/null; then echo "APP_DIED at=$(date -Is) while py-spy alive" >> "$log"; fi
  if s=$(st); then last="$s"; t_last=$(date +%s.%N); fi
  sleep 1
done
read -r u0 s0 <<<"$first"; read -r u1 s1 <<<"$last"
awk -v u=$((u1-u0)) -v s=$((s1-s0)) -v hz="$hz" -v a="$t_first" -v b="$t_last" 'BEGIN{el=b-a;
  printf "APP_CPU window=%.1fs utime=%.2fs stime=%.2fs total=%.2fs pct_of_core=%.2f\n", el, u/hz, s/hz, (u+s)/hz, (u+s)/hz/el*100}' >> "$log"
echo "pyspy_exit at=$(date -Is)" >> "$log"
if kill -0 "$app" 2>/dev/null; then echo "app still alive after py-spy (killed by us)" >> "$log"; kill "$app"; fi
````

### `fakeagent.sh`

````bash
#!/usr/bin/env bash
# fakeagent.sh — stand-in agent for the scaling runs: 300 lines of ANSI-coloured
# output (so a -S -200 capture is realistic in size), then one new line every
# 2 s forever (an active agent: every capture differs). Foreground until killed.
i=0
while (( i < 300 )); do
  printf '\e[38;5;%dm[%04d]\e[0m \e[1mtool\e[0m: reading src/module_%d.py … \e[32m✓\e[0m %s\n' \
    $(( 16 + i % 200 )) "$i" "$i" "lorem ipsum dolor sit amet consectetur adipiscing elit sed do"
  i=$(( i + 1 ))
done
while :; do
  printf '\e[36m%(%H:%M:%S)T\e[0m step %d \e[2mthinking…\e[0m\n' -1 "$i"; i=$(( i + 1 )); sleep 2
done
````

### `scale.sh`

````bash
#!/usr/bin/env bash
# scale.sh — t2034_1 step 5 on an ISOLATED tmux server.
#   scale.sh profile <N>      : N fake agents, one py-spy-profiled companion minimonitor
#   scale.sh servercost <N> <K>: N fake agents, K unprofiled companion minimonitors,
#                                tmux server CPU over 2 x 60 s windows
# Every tmux call goes through T(), which re-asserts the scratch socket name.
set -uo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
REPO=/home/ddt/Work/aitasks
PY=/home/ddt/.aitask/venv/bin/python
SOCK="ait_t2034_1_scale"
IDS=(2161 2162 2169 2170 2171 2173 2175 2176 2178 2179 2181 2182)
SESS=t2034scale
guard() { [[ -n "$SOCK" && "$SOCK" != ait && "$SOCK" == ait_t2034_1_* ]] || { echo "GUARD: bad socket '$SOCK'" >&2; exit 99; }; }
T() { guard; tmux -f /dev/null -L "$SOCK" "$@"; }
teardown() { guard; tmux -L "$SOCK" kill-server 2>/dev/null || true; }

setup() {   # setup <N>
  local n="$1" i
  teardown
  T new-session -d -s "$SESS" -x 200 -y 50 -c "$REPO" -n "agent-pick-${IDS[0]}" "$S/fakeagent.sh"
  for (( i = 1; i < n; i++ )); do
    T new-window -d -t "$SESS:" -c "$REPO" -n "agent-pick-${IDS[$i]}" "$S/fakeagent.sh"
  done
  sleep 2
  SERVER_PID=$(T display-message -p '#{pid}')
  echo "server_pid=$SERVER_PID windows=$(T list-windows -t "$SESS" | wc -l)"
}

precheck() {  # precheck <N> <tag> — discovered sessions/agents must match
  local n="$1" tag="$2"
  ( cd "$REPO" && env AITASKS_TMUX_SOCKET="$SOCK" "$PY" -I "$S/tickcount.py" \
      --project-root "$REPO" --duration 30 --warmup 2 --session "$SESS" \
      --json "$S/tick_$tag.json" > /dev/null )
  "$PY" -I - "$S/tick_$tag.json" "$n" "$SESS" "$SOCK" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1])); n = int(sys.argv[2])
ft = d["first_tick"]; ok = (ft["sessions"] == [sys.argv[3]] and ft["agent_windows"] == n
                            and d["socket_args"] == ["-L", sys.argv[4]])
w = d["warm"]
print(f"PRECHECK {'OK' if ok else 'FAIL'} sessions={ft['sessions']} agents={ft['agent_windows']} "
      f"calls/tick={w['calls_per_tick']} cpu_ms_mean={w['cpu_ms_mean']} p95={w['cpu_ms_p95']} "
      f"producer_pct_core={w['producer_cpu_pct_of_core']}")
sys.exit(0 if ok else 1)
EOF
}

companion() {  # companion <window-index-in-IDS> <cmd...> -> prints "pane_id shell_pid"
  local w="$1"; shift
  T split-window -d -t "$SESS:agent-pick-${IDS[$w]}" -h -l 40 -c "$REPO" -P -F '#{pane_id} #{pane_pid}' "$*"
}

case "${1:-}" in
  profile)
    n="$2"; setup "$n"
    precheck "$n" "N$n" || { teardown; exit 1; }
    read -r P SH < <(companion 0 "$S/run_spy.sh $SOCK scale_N$n 120 minimonitor")
    ( sleep 20; "$S/cpurate.sh" 45 "$SERVER_PID" > "$S/scale_N${n}_server.txt" ) &
    "$S/watch.sh" "$SH" "$SOCK" "$S/scale_N$n.watch"
    wait
    cat "$S/scale_N$n.watch"; tail -1 "$S/scale_N${n}_server.txt"
    teardown ;;
  servercost)
    n="$2"; k="$3"; setup "$n"
    precheck "$n" "K${k}_N$n" || { teardown; exit 1; }
    pids=()
    for (( j = 0; j < k; j++ )); do
      read -r P SH < <(companion "$j" "exec env AITASKS_TMUX_SOCKET=$SOCK $PY .aitask-scripts/monitor/minimonitor_app.py")
      pids+=("$SH")
    done
    sleep 20   # past startup
    for w in 1 2; do "$S/cpurate.sh" 60 "$SERVER_PID" "${pids[@]}" > "$S/server_K${k}_N${n}_w$w.txt"; done
    for f in "$S"/server_K${k}_N${n}_w*.txt; do echo "$f: $(grep " tmux \|SUM" "$f" | tr '\n' ' ')"; done
    # all K minimonitors still alive at the end?
    alive=0; for p in "${pids[@]}"; do kill -0 "$p" 2>/dev/null && alive=$((alive+1)); done
    echo "ALIVE $alive/$k"
    teardown ;;
  teardown) teardown ;;
  *) echo "usage: scale.sh profile N | servercost N K | teardown" >&2; exit 2 ;;
esac
````
