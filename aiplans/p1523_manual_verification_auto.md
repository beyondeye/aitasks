# Plan: p1523 — Manual verification (auto-execution) of the Codex shadow recheck loop

Task: t1523 (`aitasks/t1523_manual_verification_codex_shadow_recheck_loop.md`)
Base branch: main
Output branch: main
Working directory: /home/ddt/Work/aitasks
Strategy: autonomous (whole-checklist auto-verification, Step 1.5)
Date: 2026-08-16

## Approach

The checklist verifies t1509 (Codex shadow readiness detection in the
minimonitor auto-recheck loop). The shipped unit suite already drives the
decision core against *frozen* Codex captures, so re-running it would prove
nothing new. This run therefore supplied **independent live ground truth**:
real `codex-cli 0.146.0` and `opencode` processes in real tmux panes on an
isolated socket (`tmux -L av1523`), captured at 0.25s, and replayed through
the **real** `review_loop` functions and the **real** `MiniMonitorApp`
methods (`_apply_shadow_settle_latch`, `action_toggle_review_loop`,
`_service_review_loop`, `_deliver_recheck`).

Two properties made the probe trustworthy:

- **A positive control.** The first injection probe reported "no keys sent"
  for every case — including the settled shadow that *should* fire. That was
  a harness artifact (a fake pane pid, so the real resolver could not resolve
  the shadow). Fixed by feeding the live pane id + pid; the settled case then
  fired, which is what makes the two negative results meaningful.
- **Real processes, not fixtures.** Live captures included two Codex
  interactions the frozen fixtures do not contain (the directory-trust
  dialog, and a permission dialog rendered with a `Running …` line and no
  `Reason:` line), plus a composer placeholder different from the fixture's.

## Execution Log

### Item 1 — `e`-spawned shadow runs Codex
- Approach: not automatable (multi-screen live flow: a real Claude agent under
  `ait`, minimonitor in the same window, the `e` keypress, visual confirmation).
- Verdict: **defer** — left for interactive verification.

### Item 2 — `L` arms with a Codex shadow
- Approach: real `action_toggle_review_loop` with the live Codex pane's real
  pane id, `pane_current_command` and pid fed into the shadow lookup, so the
  real two-rung resolver ran against a real process tree.
- Output: `armed=True`, banner `⟳ auto-recheck ARMED`, notify
  `Auto-recheck loop armed — press 'L' again to disarm`. Live pane reported
  `node`, exactly the wrapper shape t1509 exists to handle.
- Verdict: **pass**

### Item 3 — not refused with "could not resolve the shadow's agent yet"
- Approach: launched a fresh Codex pane and polled from t≈0 — first
  `agent_keys._child_commands` (ground truth), then the real
  `agent_key_from_pane` simulating `L` presses at 1s intervals.
- Output: codex child visible to `pgrep` at **+0.13s**; resolver returned
  `'codex'` on **attempt #1** (pane still reported `tmux` at that instant, and
  rung 2 resolved it anyway). No backoff retries needed.
- Verdict: **pass**

### Item 4 — observe ONE automatic recheck fire (prompt + Enter)
- Approach: drove the real fire path, then delivered for real into a live
  Codex pane — first via a replica of the gateway command shape, then via the
  real `monitor_core.TmuxMonitor.send_keys` with `AITASKS_TMUX_SOCKET` pointed
  at the scratch socket, issuing exactly the two calls
  `minimonitor_app.py:2852,2855` makes.
- Output: the single-line prompt arrives in the composer; the immediately
  following `Enter` is **swallowed** — `shadow_state` = `busy`, prompt
  unsubmitted. A second `Enter` submits it. Fresh-pane trials from a verified
  clean composer: delay 0s → not submitted (2/2); 0.25s → submitted; 1.0s →
  submitted. Both `send_keys` calls return `True`, so `_deliver_recheck`
  reports `sent` and the banner reads `⟳ recheck #1 sent — waiting for shadow`
  while nothing runs.
- Verdict: **fail** → follow-up bug task **t1525** (diagnosis recorded there).

### Item 5 — nothing injected mid-output
- Approach: 28 consecutive live captures spanning a full 7.1s Codex response,
  replayed through the real controller with the loop armed.
- Output: `SHADOW_WORKING` on every tick, `ready_final` never `True`, **0 keys
  sent**. Positive control (settled tail) fired 2 keys, so the probe was live.
- Verdict: **pass**

### Item 6 — nothing injected while parked at a dialog
- Approach: forced a real permission dialog (`codex -a untrusted`, a `printf >
  out2.txt` command) and left it parked, sampling for 40.6s.
- Output: 161 captures, `SHADOW_DIALOG` throughout, `ready_final` never
  `True`, **0 keys sent**. The live dialog also matched the `codex_permission`
  / `codex_yes_proceed` prompt patterns.
- Verdict: **pass**

### Item 7 — settle latch holds ≥ SHADOW_SETTLE_SECONDS after answering
- Approach: answered the live dialog (Esc) with the answer instant recorded
  inside the sampling loop; replayed through the real
  `_apply_shadow_settle_latch` with the measured wall-clock deltas.
- Output: raw readiness returned `True` at **+0.51s**; the latch held
  injection until **+2.03s** — a hold of **2.04s** vs `SHADOW_SETTLE_SECONDS
  = 2.0`. The latch closed a real 1.5s injectable window.
- Verdict: **pass**

### Item 8 — an answer producing no follow-up work must not wedge
- Approach: the Esc answer produced no follow-up work (conversation
  interrupted; no `WORKING` state ever followed).
- Output: the latch still released at +2.03s and readiness became `True`,
  i.e. the loop became fireable again. No wedge.
- Verdict: **pass**

### Item 9 — the hold is wall-clock, not tick-count
- Approach: replayed the same live captures at the evidence cadence each
  refresh commits at (`max(1.0, 0.5 * refresh_seconds)`).
- Output: hold **2.04s** at `--interval 1` (1.0s cadence), **3.05s** at the
  3s default (1.5s cadence), 2.04s at raw 0.25s sampling — never below 2.0s.
- Caveat: verified by cadence replay, **not** by literally restarting the TUI.
- Verdict: **pass**

### Item 10 — the followed pane never receives injected keys
- Approach: collected every `send_keys` call across the arm, fire, hold and
  auto-disarm probes.
- Output: the followed pane `%1` appears in **no** send call; the one fire
  delivered both keys to the shadow pane only (`%4`, literal text then
  `Enter`).
- Verdict: **pass**

### Item 11 — negative control: an OpenCode shadow must refuse
- Approach: same real arm path against the **live** OpenCode pane
  (`pane_current_command='opencode'`, real pid).
- Output: `armed=False`, banner empty, warning `Auto-recheck unavailable:
  shadow agent 'opencode' has no readiness detection yet` — names the agent
  and the reason.
- Verdict: **pass**

### Item 12 — killing the shadow while armed auto-disarms visibly
- Approach: bound the live Codex pane to the followed pane with the real
  `@aitask_shadow_target` option, armed, then killed the pane and fed the
  real post-kill `list-panes` output to the next tick.
- Output: `armed=False`, banner cleared, warning toast `Auto-recheck loop
  disarmed: followed agent or shadow pane is gone`.
- Verdict: **pass**

## Result

10 pass, 1 fail (item 4 → t1525), 1 deferred (item 1).

## Cleanup

- tmux server on socket `av1523` — killed.
- Scratch captures and Codex workdir under the session scratchpad
  (`.../scratchpad/av1523/`) — removed.
- No files in `aitasks/` or `aiplans/` were touched other than the checklist
  itself, this plan, and the generated follow-up task.
