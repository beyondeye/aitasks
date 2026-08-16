# Plan: p1530 — Manual verification (auto-execution) of the t1525 shadow-recheck submission fix

Task: t1530 (`aitasks/t1530_manual_verification_fix_failed_verification_t1523_item4_foll.md`)
Base branch: main
Output branch: main
Working directory: /home/ddt/Work/aitasks
Strategy: autonomous (whole-checklist auto-verification, Step 1.5)
Date: 2026-08-16

## Approach

The checklist re-verifies t1525, whose whole point is that **no test in the
Python suite can prove it** — the failure was per-CLI input coalescing in a real
terminal. So this run supplied live evidence exclusively, driving the
**production code**, never a replica:

- `MiniMonitorApp._fire_shadow_recheck` → `_submit_shadow_prompt`, the real
  `ReviewLoopController`, the real `action_toggle_review_loop` (what `L` does)
  and the real `_service_review_loop` (what a refresh tick does), hand-assembled
  via `__new__` exactly as `tests/test_minimonitor_concern_smoke.py` does. Only
  the Textual-DOM bits are stubbed (`notify` → a spy list).
- Real agent CLIs in real tmux panes on private sockets
  (`AITASKS_TMUX_SOCKET`), through the real `TmuxMonitor.send_keys` /
  `capture_raw_tail` gateway.
- A real followed `claude` pane and a real shadow pane bound with the real
  `@aitask_shadow_target` option, in one real window — so the shadow lookup and
  the two-rung agent resolution ran against a real process tree (Codex resolved
  from `command=node`, as t1509 requires).

Three properties make the results trustworthy:

- **Ground truth independent of the classifier under test.** "Was it
  submitted?" was decided from a plain `capture-pane -p -J`, never from
  `review_loop.shadow_state` — the very function the delivery uses to answer
  the same question. A submitted prompt is *echoed into the transcript* with
  the agent's reply and an empty composer below it; an unsubmitted one **is**
  the bottom-most composer line. The rule: the prompt must be absent from the
  last 3 non-blank lines AND ≥2 non-blank lines must follow its last
  occurrence. `shadow_state` was recorded alongside as cross-reference only.
- **A negative control that reproduces the original bug.** Re-running the same
  production path with `COMPOSER_DRAIN_SECONDS` rebound to `0` (pre-t1525
  timing) yields, 3/3 on Codex, `outcome=failed`, **1** send (no Enter), and
  the independent probe confirming the prompt stuck in the composer. A probe
  that cannot detect the failure proves nothing about its absence.
- **Positive controls inside the negative-control runs.** The "no keys while
  the shadow is busy" run fires exactly once as soon as the shadow settles, so
  its zeros are not the zeros of a dead harness.

Harnesses (session scratchpad, `av1530/`): `probe.py` (isolated delivery,
per-agent, with the `--drain` negative control), `loop.py` (end-to-end
arm→tick→fire→re-arm, plus the `busy` and `disarm` negative controls),
`restamp.py` (the real refetch helper's re-stamp).

## Execution Log

### Item 1 — re-run t1523 item #4: ONE fire, prompt delivered AND SUBMITTED
- Approach: full end-to-end. Real `claude` followed pane + real Codex shadow
  (`codex-cli 0.146.0`) in one window, bound via `@aitask_shadow_target`;
  armed through the real `action_toggle_review_loop`; real followed work typed
  by the user, then a settle; real `_service_review_loop` ticks at a 1.0s
  evidence cadence.
- Output: banner `⟳ auto-recheck ARMED` on arm (shadow lookup
  `ok=True, pane=%1, command=node`, resolved to `codex`). Debounce built over
  ticks 2–4; **tick 5 fired**: exactly 2 keys to the shadow (literal prompt,
  then `Enter`), 1.015s, banner `⟳ recheck #1 sent — waiting for shadow`, and
  the Codex pane went to `working`. Independent ground truth on the isolated
  probe: 3/3 reps echoed into the transcript with a clean composer.
- Negative control (`COMPOSER_DRAIN_SECONDS = 0`): 3/3 `failed`, **1** send,
  detail *"the recheck prompt is not in the shadow composer — nothing was
  submitted"*, prompt confirmed stuck in the composer. The old failure is both
  reproducible and now **visible** instead of a silent hold.
- Scope note: the `ait`-launched window and the literal `e` keypress that
  spawns the shadow were not driven; the shadow pane was created and bound
  exactly as `e` binds it. t1523 deferred that same multi-screen leg (its item
  1) for the same reason.
- Verdict: **pass**

### Item 2 — the loop RE-ARMS instead of holding forever
- Approach: two-sided, through the real service and the real banner code.
  After the confirmed fire, three further real ticks: two with the shadow's
  read still **stale**, then one with it **fresh**.
- Output: stale → stays `fired`, banner `⟳ recheck #1 sent — waiting for
  shadow` (exactly the old bug's permanent-hold signature); fresh → `waiting`,
  banner `⟳ auto-recheck ARMED`. Reproduced identically with Codex, OpenCode
  and Claude shadows. The re-stamp leg was proven separately: the **real**
  `aitask_shadow_capture.sh`, run inside a **real** shadow pane bound to a real
  followed pane, moved `@aitask_shadow_analyzed_at` from unset to an epoch
  (`RC=0`, "resolved followed pane %0 from @aitask_shadow_target").
- Stated seam: the staleness *compare* was not driven from that live stamp.
  `compute_shadow_staleness` needs `get_last_change_wall`, which only the
  monitor's own refresh cycle populates, and this harness does not run one — so
  the compare returned the indeterminate `(None, None)` and was replaced by an
  explicit stale/fresh observation. What that leaves unproven is t1104/t1493
  machinery unchanged by t1525; the leg the bug actually broke (the shadow
  never running, so never re-stamping) is closed by item 1 plus the helper
  result above.
- Verdict: **pass**

### Item 3 — "delivering…" never dwells more than a couple of seconds
- Approach: wall-clock of the whole delivery (reservation → return) on every
  live fire.
- Output: **1.009–1.015s**, max 1.015s over 23 deliveries — the two
  `COMPOSER_DRAIN_SECONDS` (0.5s each) plus two captures, with no capture ever
  approaching the 3s timeout. Well inside the stated 2s budget.
- Verdict: **pass**

### Item 4 — one fire with an OpenCode shadow
- Approach: 13 live deliveries (3 + a 10-rep rate run) plus a full end-to-end
  loop fire against `opencode 1.18.18`.
- Output: every one `sent` with exactly 2 keys and independently confirmed
  submitted; the end-to-end run fired at tick 4 in 1.014s and the shadow went
  to `working`.
- Verdict: **pass**

### Item 5 — one fire with a Claude shadow (no regression)
- Approach: 3 live deliveries plus a full end-to-end loop fire against
  `claude 2.1.233`.
- Output: all `sent`, 2 keys, submitted; end-to-end fire at tick 4 in 1.012s.
- Verdict: **pass**

### Item 6 — negative control: nothing injected while the shadow is mid-output
- Approach: two live runs with the loop armed and every other trigger conjunct
  satisfied, so the only thing withholding the keys is shadow readiness. The
  Codex shadow was given a long streaming task.
- Output: **6 ticks** with the shadow classified `working` and **17 ticks**
  holding on `⟳ waiting for shadow to settle` — **zero keys injected in every
  one of them**. Each run then fired exactly once, as soon as the shadow was
  genuinely settled (the positive control that makes the zeros meaningful).
  The hold was driven by both mechanisms in turn: the `working` verdict, then
  raw-tail hash instability while the pane was still repainting.
- Verdict: **pass**

### Item 7 — negative control: disarm during a delivery
- Approach: real `L` press (the real `action_toggle_review_loop`) issued 0.35s
  after the controller entered `DELIVERING` — i.e. after the prompt write,
  inside the composer drain, before the pre-Enter capture.
- Output: exactly **1** loop send (the prompt; **no Enter**), controller
  `disarmed`, banner cleared, and two toasts — `Auto-recheck loop disarmed`
  from the keypress, then the warning **"Auto-recheck loop disarmed: recheck
  text left in the shadow composer — submit or clear it there manually"**. The
  shadow read `busy`, confirming the text really was left there, and the loop
  said so rather than going quiet.
- Verdict: **pass**

### Item 8 — how often does "submission could not be verified" fire?
- Approach: counted the warning across every live successful delivery in this
  run (23), with a dedicated 10-rep OpenCode run since the prediction was
  OpenCode-specific.
- Output: **1 warning in 23 deliveries (~4%); OpenCode-only 1/14 (~7%)**, none
  for Codex or Claude. The single occurrence read `dialog` and was **genuine,
  not a masking artifact**: the OpenCode shadow raised a real
  `△ Permission required — Access external directory …` dialog immediately
  after the submit, while the pane showed the prompt `QUEUED`. The delivery had
  in fact landed (independently confirmed: echoed, composer clean, 14 lines
  after), and the verifier correctly declined to claim verification and warned
  instead of claiming failure or hanging.
- Reading: consistent with t1525's ~2% prediction and with its documented
  mechanism. The scratch sandbox lives outside the trusted project root, which
  provokes exactly this permission dialog — normal in-repo use would not. Not a
  reason to weaken the check; recorded as a data point for t1524.
- Verdict: **pass**

### Item 9 — the followed pane never receives injected keys
- Approach: every `send_keys` call in every harness was recorded through a
  subclass of the real `TmuxMonitor` and tagged loop-vs-user, so the claim rests
  on observed traffic rather than on the structural argument that
  `_fire_shadow_recheck` is never handed a followed pane id.
- Output: across all five end-to-end runs the loop's send targets were
  **exclusively the shadow pane** (`['%1']`), and `followed_got_loop_keys` was
  `False` in every run. The only keys reaching the followed pane were the
  harness's own user-typed prompt and `Enter`.
- Verdict: **pass**

## Result

**9 pass, 0 fail, 0 skip, 0 deferred.** The t1523 item-4 failure is fixed: the
Enter now lands and the submission is verified, for all three shadow agents,
and every failure mode the fix introduced is visible rather than silent.

## Cleanup

- tmux servers on the private sockets `av1530_*`, `av1530L_*`, `av1530R_*`,
  `av1530dbg*` — killed, socket files removed; no stray agent processes.
- `/tmp/av1530_helper.out` — removed.
- Harness scripts and captured pane evidence remain under the session
  scratchpad (`av1530/`); nothing was written outside it except this plan and
  the task's own checklist.
