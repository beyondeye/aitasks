---
Task: t1525_fix_failed_verification_t1523_item4.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1525 — Make the auto-recheck Enter actually submit in a Codex shadow

## Context

`ait minimonitor`'s auto-recheck loop injects a single-line "refetch and recheck
round N" prompt plus `Enter` into the **shadow** pane. t1509 shipped the
readiness half for a Codex shadow — the pairing the feature exists to enable —
and the live manual verification (t1523) then failed on item #4: the *delivery*
half does not work for Codex.

`_fire_shadow_recheck` (`minimonitor_app.py`) sends the prompt and the
`Enter` as two back-to-back tmux round-trips with **nothing between them**.
Measured live against `codex-cli 0.146.0` through the real gateway:

| gap between the two `send_keys` calls | outcome |
|---|---|
| **0s (today)** | **not submitted** — prompt stuck in the composer (2/2 trials) |
| 0.25s | submitted |
| 1.0s | submitted |

Both `send_keys` calls return `True` either way, so the loop enters `FIRED`, the
banner reads `⟳ recheck #1 sent`, and the shadow — now holding typed text —
classifies `SHADOW_BUSY` forever. Readiness never returns `True`, so the loop
**holds and silently never re-arms**. The one message that would have named the
problem ("recheck text left in the shadow composer") is gated on a non-zero
`send_keys` rc and is unreachable in exactly this failure.

**Intended outcome:** the Enter lands, and delivery **verifies** submission from
a capture instead of trusting two return codes that are already `True` in the
failing case.

## Root cause

Codex's TUI coalesces the input burst: the literal text and the `Enter` arrive in
one read and the `Enter` is consumed as text, not as a submit. Claude does not,
which is why the loop shipped green.

## Design

### The fix is a drain window; the verifier is what makes its rot visible

The measured constant is the actual repair. The verify-and-retry layer exists so
that when the constant stops being right (a Codex release, a slower box), the
loop says so instead of hanging silently — which is the failure mode this task
was created by.

**Unconditional, not per-agent.** A per-agent table would not literally fail open
(`TABLE.get(agent, DEFAULT)` fails closed), but it buys nothing: a fire happens
at most once per `COOLDOWN_SECONDS = 45.0`, so the delay is free, and one delivery
path is simpler to reason about than two. **What earns that "unconditional" is
evidence, not convenience** — the pre-phase sweep measures every agent in
`SHADOW_READY_DETECTORS` and the shipped constant is the one that passes for all
of them, so the common path is never enabled on Codex-only data.

### What the verifier reads, and what it must never do

`review_loop.shadow_state()` already answers "is the composer holding typed
text?" — `SHADOW_BUSY`, and it holds for **all three** shadow agents now that
t1520 has landed (verified during planning: `CLAUDE_TYPED_RAW`,
`CODEX_TYPED_RAW` and `OPENCODE_TYPED_RAW` all classify `busy`). Reuse it rather
than inventing a parallel classifier — and note that the unconditional drain now
protects the two agents whose delivery has never been live-proven at all, not
just Codex.

Two guards, both **positive-evidence** gated:

| point | verdict | action |
|---|---|---|
| **before each Enter** | `SHADOW_BUSY` — the composer holds the text we just wrote | the **only** state that authorises an Enter |
| | `SHADOW_DIALOG` / `SHADOW_UNKNOWN` | veto: `failed` + the leftover-text message (the text is presumed still sitting there — a dialog covers the composer, an unreadable pane tells us nothing) |
| | `SHADOW_READY` / `SHADOW_WORKING` | veto: `failed` + "the recheck prompt is not in the shadow composer — nothing was submitted". Our text is demonstrably *not* where we put it; whether it never arrived or already went, another Enter is an unverified keystroke |
| **after each Enter** | `SHADOW_BUSY` | composer positively still holds text → Enter was swallowed → retry (≤ `SHADOW_SUBMIT_RETRIES`) |
| | `SHADOW_WORKING` / `SHADOW_READY` | positively submitted → `sent` |
| | `SHADOW_DIALOG` / `SHADOW_UNKNOWN` | **verification impossible** → `sent` (never claim failure) **plus a warning notify naming the blocking verdict**; no further keys |

**The pre-Enter gate is positive-evidence in the strict sense: `SHADOW_BUSY` is
the state we *put the pane into*, and it is the only one that authorises a key.**
Every other verdict — including the innocuous-looking `READY` and `WORKING` — says
the pane is not where we left it, and the loop's whole design principle is that an
unexpected shadow state means *hold*, never *send anyway*. The two veto messages
differ because the two cases differ: with `DIALOG`/`UNKNOWN` the text is presumed
still in the composer, with `READY`/`WORKING` it demonstrably is not.

**This is why `SHADOW_UNKNOWN` appears on both sides of the delivery with opposite
effect.** The pre-Enter gate authorises an *action*, so it fails **closed** — an
indeterminate read is never "fine to inject into", which is `shadow_state`'s own
stated contract. The post-Enter gate only decides what to *claim* about a key
already sent, so there it fails **open-but-loud**: report `sent`, warn that it is
unverified.

**Only `WORKING`/`READY` count as verified.** `SHADOW_DIALOG` must **not** be read
as "submitted": `_ordered_state` sweeps every prompt pattern over the whole tail
*before* the composer scan and returns `DIALOG` on any hit, so a dialog string
sitting in the shadow's own transcript masks a still-busy composer — reporting
`sent` there would silently reproduce the exact stuck-text failure this task
exists to remove. `SHADOW_UNKNOWN` (capture failed) is the same class.

Both are therefore **unverified**, not failed: we have no evidence the delivery
failed, so auto-disarming would be wrong, but a silent unverified delivery is
precisely what shipped broken — so each emits a warning naming which verdict
blocked verification. The pre-Enter veto is a partial control on the dialog case
(a transcript match present before the Enter would already have vetoed the send),
which is why this stays a warning rather than a disarm; the residual is that the
match can enter the bounded tail between the two captures.

### What this verifier cannot see (documented limitations, not oversights)

- **`SHADOW_DIALOG` outranks `SHADOW_BUSY` structurally** (`_ordered_state` sweeps
  every prompt pattern over the whole tail before calling the positive half, and
  `_composer_state`'s positive half itself returns `DIALOG` when no composer line
  is found). So unsubmitted text *plus* any dialog-pattern hit anywhere in the
  tail reads `DIALOG` — and a shadow is a review agent whose transcript quotes UI
  strings, so `codex_yes_proceed` can plausibly match there. **This is why
  `DIALOG` is classified unverified rather than submitted** (see the table); the
  loop then degrades to today's hold, but with a warning instead of silence.
- **A partially repainted frame.** Codex echoed user messages share the composer
  glyph (per `_CODEX_COMPOSER_RE`'s own comment); the bottom-up scan normally
  reaches the empty composer *below* the echo first, but a half-drawn frame can
  read `BUSY` after a genuine submit. Under the strict pre-Enter gate this costs a
  **false visible failure**, not a stray keystroke: the retry's own pre-Enter
  capture then reads `READY`, vetoes, and reports "not in the shadow composer".
  Worth stating plainly — it trades a silent extra Enter for a loud wrong message,
  which is the right direction but is not free. The pre-Enter `BUSY 10/10`
  acceptance criterion below is what keeps it rare.
- **An agent state that classifies `UNKNOWN` while genuinely working.**
  `OPENCODE_WORKING_NO_FOOTER_ROOM_RAW` does exactly that (verified during
  planning), so a successful delivery into a short OpenCode pane will warn
  "could not verify" every time. Honest, but a real noise source — it names the
  verdict so the cause is legible, and it is a data point for t1524.
- **The user typing into the shadow inside the drain window**, so the retry Enter
  submits our prompt concatenated with their text. **A text-identity guard was
  considered and rejected**: matching the prompt against the cleaned *tail* is
  both fragile (the ~100-char prompt soft-wraps in a narrow composer, so it is
  not a contiguous substring) and non-discriminating (after a real submit Codex
  echoes the same text into the transcript, so the check passes in exactly the
  case it should fail). Making it sound would mean exposing the composer *line*
  out of `_composer_state` — a refactor of the classifier t1509 just stabilised,
  bought for a harm whose worst outcome is that an **advisory-only** shadow
  receives a garbled prompt (it is structurally incapable of writing the followed
  pane). The retry cap of 1 bounds it to a single extra Enter. Accepted residual,
  recorded here rather than papered over.

### No Enter after cancellation — re-check the token at every new suspension point

The existing docstring states the discipline — "the delivery token re-checked
after the await" — and today the code honours it once, which was enough when the
two `send_keys` calls were adjacent. The new sequence adds four suspension points
**after** the first `send_keys`, so a user pressing `L` mid-delivery could still
have an Enter injected into a cancelled delivery.

**Rule: re-check `ctrl.delivery_valid(token)` after every new `await` and
immediately before every Enter — including the first.** On invalidation, send
nothing and return `failed` with the leftover-text message. The text is already
written and cannot be un-written either way, so the only thing the check changes
is whether a *disarmed* loop still drives a review round; the user who disarmed is
told, in the same words, that text is sitting in the composer.

## Implementation

### Pre-phase (risk mitigations)

1. `[measure_post_submit_state]` **The constant is load-bearing, so it is chosen
   by a reproducible measurement with a pre-registered acceptance criterion — not
   by a handful of samples.** `codex-cli 0.146.0` is installed on this box.

   **Every enabled shadow agent is measured, not just Codex.** The drain and the
   retry path are unconditional, so they change delivery for `claude` and
   `opencode` too — and neither has ever had its delivery live-proven. All three
   CLIs are installed on this box at the versions the detectors were pinned
   against (`claude` 2.1.233, `codex-cli` 0.146.0, `opencode` 1.18.18), so there
   is no reason to accept a Codex-only result. The harness is parameterised by
   agent and runs the full sweep for **every key in
   `review_loop.SHADOW_READY_DETECTORS`**; if an agent cannot be launched, that
   is recorded as an explicit coverage gap in the Measurement section rather than
   silently skipped.

   **Harness** — one script at
   `<scratchpad>/measure_drain.py`, run before any production edit. It must drive
   the **real** seams (`monitor_core.TmuxMonitor.send_keys`, `capture_raw_tail`,
   `review_loop.shadow_state`), never a reimplementation, with
   `AITASKS_TMUX_SOCKET` pointed at a private socket (the t1509 method), and it
   must print a machine-readable table. Per repetition, for the agent under test:
   1. launch a fresh pane running **the agent under test** (not always Codex —
      this step is parameterised, and getting it wrong is how an all-agent
      criterion silently becomes a Codex-only one); assert the launched CLI and
      its version, and carry both into every emitted row; wait for
      `shadow_state(<agent>) == READY`;
   2. `send_keys(prompt, literal=True)`; sleep the candidate `d`; **sample
      `shadow_state` here — this is the pre-Enter gate's own sample, and the
      strict `BUSY`-only authorisation rests on it**; then `send_keys("Enter")`;
   3. sample `shadow_state` at `t_enter + d` — the post-Enter **verifier's**
      sample;
   4. sample again at `t_enter + 5.0` to establish ground truth for whether the
      submit actually happened (`WORKING`/transcript growth = submitted).

   **Sweep** `d ∈ {0.25, 0.35, 0.5, 0.75}`, **N = 10** repetitions each, **per
   agent**, in one run — so the constant is picked from a table rather than from
   the first value that looked fine.

   **Acceptance criterion, pre-registered:** a `d` **passes for an agent** when
   **10/10** repetitions satisfy all three of (a) actually submitted per the t+5s
   ground truth, (b) sampled **`SHADOW_BUSY`** at step 2 — the pre-Enter gate
   authorises on that state alone, so a `d` at which the written text has not yet
   rendered would veto every real delivery — and (c) sampled **non-`BUSY`** at
   step 3. A single failure in any column disqualifies that `d` for that agent —
   no cherry-picking, no partial credit.
   **Ship the smallest `d` that passes for *every* measured agent** (i.e. the max
   over each agent's smallest passing value): one constant, sized by the worst
   agent, consistent with keeping the path unconditional.

   **If no swept value passes for some agent**, the timed drain is not sufficient
   there. Do not ship the common path on hope — either raise the sweep and re-run,
   or come back and re-scope: `bracketed_paste_delivery` is promoted from an
   "after" follow-up to a blocking prerequisite. Record which it was.

   **Also record, per agent, the distribution of post-Enter verdicts on a
   *successful* submit.** This is what predicts the "could not verify" warning
   rate in normal operation (`OPENCODE_WORKING_NO_FOOTER_ROOM_RAW` already shows
   OpenCode can read `UNKNOWN` while genuinely working). If an agent warns on most
   successful deliveries, say so in the notes — that is a usability finding for
   t1524, not a reason to weaken the verifier.

   **Retained evidence:** paste the full per-agent sweep table into a
   `## Measurement` section of the committed plan (not only the Final
   Implementation Notes), with every agent's CLI version, the date, and the
   harness path — the same standard `SHADOW_SETTLE_SECONDS` is held to.

   While the harness is up, also capture the composer of a **non-active** pane
   (per agent) to test the unfocused-dimming hypothesis (a dimmed composer holding our text would
   strip to empty and read `READY`, making the whole verifier inert). Record that
   result in the same section.

### 1. `.aitask-scripts/monitor/review_loop.py`

Add two constants next to `SHADOW_SETTLE_SECONDS`. **Name them so they
are not confusable with it** — `SHADOW_SETTLE_SECONDS` means "the shadow has been
idle this long"; these mean "wait for a TUI to drain a pty write":

```python
# Wall-clock gap the delivery leaves between the literal prompt write, the Enter
# that submits it, and the capture that verifies the submission.
#
# Sized by live measurement (t1525): with the two send_keys calls back to back
# (0s) codex-cli 0.146.0 coalesces the burst and consumes the Enter as text —
# NOT submitted, 2/2 trials. The shipped value is the smallest swept candidate
# that submitted 10/10 AND read non-BUSY 10/10 at t+d for EVERY shadow agent
# (pre-phase sweep; per-agent table in the plan's ## Measurement section). Unconditional rather than
# per-agent: a fire happens at most once per COOLDOWN_SECONDS, so the delay is
# free and one delivery path is simpler than two.
COMPOSER_DRAIN_SECONDS = <chosen by the pre-phase sweep; 0.5 is the expectation>

# Extra Enters allowed after a capture positively shows the composer STILL
# holding OUR prompt. Bounded: each attempt costs 2 x the drain above plus two
# captures (worst case ~14s in DELIVERING if tmux itself is wedged and both
# captures burn the 3s _SHADOW_CAPTURE_TIMEOUT; the banner shows "delivering…"
# throughout and the controller cannot double-fire).
SHADOW_SUBMIT_RETRIES = 1
```

### 2. `.aitask-scripts/monitor/minimonitor_app.py`

a. Module-level pause seam near the other module-level helpers, so unit tests
   rebind it (the established `capture_shadow_text` pattern) instead of paying
   real wall clock:

```python
async def _composer_drain(seconds: float) -> None:
    """Yield the event loop between delivery keystrokes (t1525).

    Module level so tests can rebind it; `asyncio.sleep` keeps the Textual event
    loop responsive while the shadow's TUI drains the pty write.
    """
    await asyncio.sleep(seconds)
```

b. `_fire_shadow_recheck` keeps everything up to and including the prompt write,
   then delegates (its two-`send_keys` tail becomes):

```python
        if not monitor.send_keys(shadow_pane, prompt, literal=True):
            return ("failed",
                    "could not write the recheck prompt to the shadow pane")
        return await self._submit_shadow_prompt(
            monitor, shadow_pane, shadow_key, prompt, token)
```

c. New method `_submit_shadow_prompt(self, monitor, shadow_pane, shadow_key,
   prompt, token) -> tuple[str, str]`, carrying the design rationale above in its
   docstring:

```python
        leftover = ("recheck text left in the shadow composer — submit or "
                    "clear it there manually")
        missing = ("the recheck prompt is not in the shadow composer — "
                   "nothing was submitted")
        ctrl = self._review_loop
        for _attempt in range(review_loop.SHADOW_SUBMIT_RETRIES + 1):
            await _composer_drain(review_loop.COMPOSER_DRAIN_SECONDS)
            if not ctrl.delivery_valid(token):
                return "failed", leftover
            before = review_loop.shadow_state(
                await capture_raw_tail(monitor, shadow_pane), shadow_key)
            # Two independent reasons not to press Enter, checked together
            # because both are re-derived after an await.
            # Fail CLOSED on anything but the state we put the pane into.
            # BUSY is the composer holding the text we just wrote; a dialog
            # would eat the Enter, an indeterminate read is no evidence at
            # all, and READY/WORKING mean our text is not where we put it.
            if before != review_loop.SHADOW_BUSY:
                return "failed", (
                    leftover
                    if before in (review_loop.SHADOW_DIALOG,
                                  review_loop.SHADOW_UNKNOWN)
                    else missing)
            if not ctrl.delivery_valid(token):
                return "failed", leftover        # delivery cancelled mid-flight
            if not monitor.send_keys(shadow_pane, "Enter"):
                return "failed", leftover
            await _composer_drain(review_loop.COMPOSER_DRAIN_SECONDS)
            state = review_loop.shadow_state(
                await capture_raw_tail(monitor, shadow_pane), shadow_key)
            if state == review_loop.SHADOW_BUSY:
                continue                         # swallowed — retry if budget
            if state in (review_loop.SHADOW_DIALOG, review_loop.SHADOW_UNKNOWN):
                self.notify(
                    f"recheck sent, but submission could not be verified "
                    f"(shadow reads '{state}')", severity="warning")
            return "sent", prompt
        return "failed", leftover
```

   Comments to carry in the code:
   - the post-Enter capture is deliberately **not** fed to
     `_apply_shadow_settle_latch`: the controller is in `DELIVERING`/`FIRED`
     behind a 45s cooldown, and a post-delivery dialog/working observation is the
     *expected consequence* of the fire, not an interaction that should hold the
     next one;
   - the token is re-checked after **every** await and immediately before
     **every** Enter, including the first — see the design note.

### 3. Tests — `tests/test_minimonitor_concern_action.py` (`ReviewLoopFireTests`)

Rebind `mm._composer_drain` to a recorder inside the shared `_loop_app` builder
so no fire test pays real wall clock. That makes the timing tests
(1, 2, 11) the *entire* defence of the constant — do not drop them.

**Capture-sequence arithmetic** — get this wrong and tests pass for the wrong
reason. For `_tick(app, 3)` the fake pops `raw_tails` in this order, and the last
value sticks:

`tick1 / tick2 / tick3 / pre-send / [pre-Enter / post-Enter] * attempts`

- indices 2 and 3 must be **byte-identical** (`hash_stable`) and must classify
  `READY`, or the fire aborts before any of this runs;
- each attempt's **pre-Enter** entry must be a `TYPED` (i.e. `SHADOW_BUSY`) tail,
  since that is now the only verdict that authorises the Enter — a retry test
  whose second pre-Enter entry is left at-rest exercises the veto, not the retry.

So the swallowed-Enter retry script is
`[REST, REST, REST, REST, TYPED, TYPED, TYPED, REST]`, and the persistent-swallow
script is the same with `TYPED` sticky.

| # | test | negative control (one-line mutation → only this test fails) |
|---|---|---|
| 1 | `test_enter_is_sent_after_the_composer_drain` — recorder appends a sentinel into `mon.sent`; assert it precedes the `Enter` | delete the pre-Enter `await _composer_drain(...)` |
| 2 | `test_composer_drain_uses_the_named_constant` — recorded seconds `== [CONST, CONST]` | change a call site to `0.0` |
| 3 | `test_a_swallowed_enter_is_retried_once_and_reports_sent` — the retry script above; assert 3 sends (prompt + 2 Enters), `sent`, `FIRED`, banner "recheck #1 sent" | replace the retry `send_keys` with `pass` |
| 4 | `test_a_persistently_swallowed_enter_disarms_with_the_leftover_message` — sticky `CLAUDE_TYPED_RAW`; assert exactly 3 sends (the at/over-bound assertion), disarmed, notify names "left in the shadow composer" | raise `SHADOW_SUBMIT_RETRIES` to 2 |
| 5 | `test_a_dialog_after_the_enter_is_unverified_not_submitted` — post-Enter tail `CLAUDE_DIALOG_RAW`; assert 2 sends, `sent`, **no disarm**, and a `severity="warning"` notify naming `dialog` | (a) change the gate to `state != SHADOW_READY` → 3 sends; (b) drop `SHADOW_DIALOG` from the unverified tuple → the notify assertion fails |
| 6 | `test_only_a_busy_composer_authorises_the_enter` — table-driven over the pre-Enter tail: `CLAUDE_DIALOG_RAW` and a failed capture → **1** send, `failed`, leftover message; `CLAUDE_AT_REST_RAW` and `CLAUDE_STREAMING_RAW` → **1** send, `failed`, "not in the shadow composer"; `CLAUDE_TYPED_RAW` → 2 sends. One case per verdict, so no verdict silently loses its gate | relax the gate to `before in (DIALOG, UNKNOWN)` → the READY and WORKING rows fail (2 sends, an unverified Enter); invert it to `before == SHADOW_BUSY` only for dialog → the failed-capture row fails |
| 6b | `test_the_two_veto_messages_are_not_interchanged` — assert the `DIALOG` row names leftover text and the `READY` row names "not in the shadow composer" | swap the two message branches — 6 still passes on send counts, only this fails |
| 7 | `test_unverifiable_capture_warns_but_reports_sent` — `on_capture` flips `capture_rc = 1` on the post-Enter call; assert 2 sends, `FIRED`, a warning notify naming `unknown` | delete the notify |
| 8 | `test_disarm_before_the_first_enter_sends_nothing_more` — `on_capture` disarms on the **pre-Enter** capture; assert exactly **1** send (the prompt), `failed`, leftover message | delete the pre-Enter `delivery_valid(token)` re-check → 2 sends, an Enter into a cancelled delivery |
| 8b | `test_disarm_before_the_retry_enter_sends_no_retry` — post-Enter tail BUSY, `on_capture` disarms on that capture; assert exactly 2 sends | delete the post-await `delivery_valid(token)` re-check at the top of the loop → 3 sends |
| 9 | `test_post_enter_capture_does_not_arm_the_settle_latch` — post-Enter tail `CLAUDE_DIALOG_RAW`; assert `app._loop_shadow_settle_until is None` | route the post-Enter state through `_apply_shadow_settle_latch` |
| 10 | amend `test_fire_sends_exactly_two_keys_to_the_shadow_only` with an exact `capture-pane` count over `mon.async_calls` — the test's name currently permits unbounded new tmux traffic | add any extra capture inside the fire path |

In `tests/test_review_loop.py`:
- `test_composer_drain_clears_the_measured_floor` —
  `assertGreaterEqual(rl.COMPOSER_DRAIN_SECONDS, 0.25)`, citing the measurement.
  *Negative control:* set it to `0.0`. This is the only thing between the repo and
  a silent regression to t1525.
- a **Claude** state-verdict table mirroring the `test_state_verdicts_per_fixture`
  tables that `CodexShadowReadinessTests` and `OpenCodeShadowReadinessTests` already have
  (`AT_REST→READY`, `TYPED→BUSY`, `STREAMING→WORKING`, `DIALOG→DIALOG`; all four
  confirmed during planning). Today only "not ready" is pinned for Claude, and
  the retry gate now depends on the specific `SHADOW_BUSY` verdict for both
  agents — Claude is now the only shadow agent without such a table.

### 4. `tests/test_minimonitor_concern_smoke.py`

The live smoke **cannot cover any of this and must not be stretched to try**: its
pane is `printf '❯\xa0\n'; exec cat`, so the tty echo lands on the line *below*
the composer, `_claude_state` reads `READY` at every point in the sequence, and
the smoke passes with the entire verifier deleted. Removing the `\n` does not fix
it either — `cat` never clears the line, so the post-Enter capture would read
`BUSY` forever and the retry budget would exhaust.

Add a comment recording exactly that, so a future reader does not assume the live
test guards the verifier. Also give its hand-assembled app (the `MiniMonitorApp.__new__` block in
`test_fire_delivers_the_recheck_line_verbatim`) the
`spy_notify` lambda the other builders use, so the unverifiable-capture branch
cannot blow up inside a real-tmux run.

### 5. Docs — `aidocs/framework/shadow_agent.md`

Update safety-contract items 7 and 9: delivery is literal write →
drain → **dialog veto** → Enter → drain → **capture-verified** submission, with
one bounded retry gated on a **positively `SHADOW_BUSY`** composer; every other
verdict sends no further keys; **only `WORKING`/`READY` count as verified, while
`DIALOG`/`UNKNOWN` are reported as unverified with a warning**; exhaustion
auto-disarms visibly naming the leftover text; and no Enter is ever sent after
the delivery token is invalidated. Record the pre-phase sweep as the sizing
evidence for `COMPOSER_DRAIN_SECONDS`, and the "what the verifier cannot see"
limitations above.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
```
Targeted while iterating:
```bash
~/.aitask/venv/bin/python -m pytest tests/test_minimonitor_concern_action.py \
  tests/test_review_loop.py tests/test_minimonitor_concern_smoke.py
```
- Run every named negative control by hand: mutate, confirm **exactly** the named
  test fails, revert.
- `RecheckInjectionSmokeTests` must stay green — it proves the real
  `TmuxMonitor.send_keys` gateway path still works end to end, nothing more.
- **The fix's real proof is a live Codex shadow, which no test in this suite can
  supply.** Re-run t1523 item #4 against a real Codex pane; queue it as a
  manual-verification follow-up at Step 8c.

## Risk

### Code-health risk: medium
- The delivery was effectively synchronous after its one validation point; it now
  carries four new suspension points (two drains, two captures) inside a
  key-injecting path. That shape change is exactly what produced the
  token-revalidation defect found in plan review, and a future edit can
  reintroduce it just as quietly · severity: medium · → mitigation: none spawned
  (closed in-plan by test 8, `test_disarm_during_the_drain_sends_no_retry`, whose
  negative control is deleting the re-check)
- The pre-Enter gate authorises on `SHADOW_BUSY` alone, so **any** misread of the
  post-write composer — a dialog pattern matching transcript text, a half-drawn
  frame, an agent state that classifies `UNKNOWN` while fine — turns a good
  delivery into a visible auto-disarm. Failing visibly is the right direction, but
  it is a false-alarm path that did not exist before, and its rate is set by the
  same repaint timing the constant is sized from · severity: medium ·
  → mitigation: none spawned (closed in-plan by the pre-phase sweep's
  `BUSY 10/10` pre-Enter column, which disqualifies any `d` where the written text
  has not reliably rendered; test 6 pins one case per verdict)
- Worst-case `DELIVERING` dwell rises to ~14s if a retry's two captures both burn
  the 3s capture timeout; the banner sits on "delivering…" and the loop's tick
  cadence pauses. Nothing corrupts (the controller returns `ACTION_NONE`
  unconditionally while DELIVERING) but it is a visible stall · severity: low ·
  → mitigation: none (accepted)

### Goal-achievement risk: medium
- `COMPOSER_DRAIN_SECONDS = 0.5` is tuned against codex-cli 0.146.0 at n=2. A UI
  or input-handling change in a later Codex makes it wrong again — the same class
  of failure this task is fixing. The verifier converts that from a silent hold
  into a visible auto-disarm, but the constant itself remains the load-bearing
  part · severity: medium · → mitigation: t1531
- The retry gate assumes `shadow_state` is **not** `SHADOW_BUSY` at
  t+`COMPOSER_DRAIN_SECONDS` after a *successful* submit. That is an assumption,
  not a measurement — the live data sized the submit, not the post-submit repaint.
  If it is transiently BUSY, every good delivery fires one spurious extra Enter ·
  severity: medium · → mitigation: inline pre-phase measure_post_submit_state
- `SHADOW_DIALOG` outranks `SHADOW_BUSY` structurally, so a dialog string in the
  shadow's own transcript can mask a still-busy composer. Classifying that verdict
  as **unverified + warning** (rather than as submitted) keeps it from silently
  reproducing the original failure, but the delivery genuinely cannot be verified
  on those captures · severity: low · → mitigation: t1524 (already spawned:
  surfaces a never-settling shadow as a banner hint)
- Nothing in the Python suite can prove the fix against a real Codex pane; the
  only end-to-end proof is a live re-run of t1523 item #4 · severity: medium ·
  → mitigation: the Step 8c manual-verification follow-up (native to the
  workflow, not a risk-mitigation task)

### Planned mitigations
- timing: pre-phase | name: measure_post_submit_state | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk 2 (post-submit repaint assumption behind the retry gate) | desc: On an isolated tmux socket, drive a real submit through the real gateway for EVERY agent in SHADOW_READY_DETECTORS (claude 2.1.233, codex-cli 0.146.0, opencode 1.18.18 are all installed; the launch step is parameterised by agent and each row asserts the CLI version it ran against) and sample review_loop.shadow_state() BOTH before the Enter (must be BUSY, the state the strict pre-Enter gate authorises on) and after it, over a 4-value x 10-repetition sweep per agent, plus a non-active-pane capture per agent for the unfocused-dimming hypothesis; ship the smallest d that passes 10/10 on all three columns for every agent, so the unconditional path is not enabled on Codex-only evidence.
- timing: after | name: bracketed_paste_delivery | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement risk 1 (a drain constant tuned to one Codex build will rot) | desc: Deliver the recheck prompt via tmux set-buffer + paste-buffer -p so the payload arrives as a bracketed-paste event and the Enter is structurally incapable of being read as text, retiring the timed drain as the load-bearing mechanism; needs its own live measurement per shadow agent, including whether Codex collapses the paste into a chip. | created: t1531

**Reassessment after inlining** (`risk-evaluation.md` Step 3 note): both levels
stay **medium**. The inlined measurement closes goal-achievement risk 2 before any
code is written, but risks 1 and 4 (constant rot; no in-suite proof against a real
Codex pane) are untouched by it, and the inline phase adds no production code, so
code-health is unchanged.

## Measurement (pre-phase `measure_post_submit_state`, 2026-08-16)

**Harness:** `<scratchpad>/measure/measure_drain.py`, run on a private tmux
socket (`AITASKS_TMUX_SOCKET`) against the real seams —
`monitor_core.TmuxMonitor.send_keys`, `monitor_core.capture_raw_tail`,
`review_loop.shadow_state` — with the launch step parameterised by agent and
every row carrying the CLI version it ran against. Raw data:
`<scratchpad>/measure/sweep.csv` (150 rows).

**Agents (all three shadow agents, not just the failing one):** claude 2.1.233,
codex-cli 0.146.0, opencode 1.18.18. Sweep `d` over {0, 0.25, 0.35, 0.5, 0.75},
N = 10 per cell. `d = 0` is the negative control — it is what shipped before
this task, and a harness that cannot reproduce the bug proves nothing.

A cell **passes** only at 10/10 on all three columns: `submitted` (the composer
is not still holding the text 5s after the Enter), `preBUSY` (the write is
visible in the composer at `t_write + d` — the sole state the delivery
authorises an Enter on), `postNonBUSY` (the composer has released the text at
`t_enter + d`).

| agent | d | n | submitted | preBUSY | postNonBUSY | verdict |
|---|---|---|---|---|---|---|
| claude | 0.0 | 10 | 10/10 | 0/10 | 4/10 | FAIL |
| claude | 0.25 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| claude | 0.35 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| claude | 0.5 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| claude | 0.75 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| codex | 0.0 | 10 | 0/10 | 0/10 | 10/10 | FAIL |
| codex | 0.25 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| codex | 0.35 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| codex | 0.5 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| codex | 0.75 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| opencode | 0.0 | 10 | 10/10 | 0/10 | 10/10 | FAIL |
| opencode | 0.25 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| opencode | 0.35 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| opencode | 0.5 | 10 | 10/10 | 10/10 | 10/10 | **PASS** |
| opencode | 0.75 | 10 | 10/10 | 9/10 | 10/10 | FAIL |

**The bug reproduced, and it is Codex-specific.** At `d = 0` codex submitted
**0/10** — the Enter consumed as text, both `send_keys` returning success, the
prompt left in the composer. Claude and OpenCode submit fine at `d = 0`, which
confirms the task's claim about the mechanism.

**But the drain turned out to be load-bearing for all three agents, for a
second reason the task had not identified.** At `d = 0` *no* agent had rendered
the write yet (`preBUSY` 0/10 everywhere), and claude's composer still showed
the text just after a *successful* submit in 6/10 (`postNonBUSY` 4/10) — which
under this design fires a spurious retry Enter. This is exactly the assumption
the mitigation existed to test, and it did not survive: the retry gate needed
the drain as much as the submit did.

**Chosen value: `COMPOSER_DRAIN_SECONDS = 0.5`.** The all-agent passing band is
{0.25, 0.35, 0.5}. 0.75 is excluded by opencode (`preBUSY` 9/10): an accumulated
transcript matched a dialog pattern and masked the busy composer — the
documented masking limitation showing up in live data, not a timing effect.

**Stated deviation from the pre-registered rule.** The criterion said "ship the
smallest `d` that passes for every agent", which selects **0.25**; the shipped
value is **0.5**, the *top* of the passing band. Recording this rather than
quietly restating the rule: the criterion was written to stop a too-small value
being chosen, the failure it guards against is one-sided and dramatic, 0.25 is
the smallest value ever *tested* rather than a measured threshold (nothing was
sampled between 0 and 0.25), and the cost of the margin is at most 1s of added
latency, at most once per `COOLDOWN_SECONDS = 45`.

**Unverified-warning rate (predicts the `DIALOG`/`UNKNOWN` warning in normal
use):** 2 of 120 post-Enter samples in the main sweep read `dialog`, both
OpenCode; none read `unknown`. The worry that
`OPENCODE_WORKING_NO_FOOTER_ROOM_RAW` would make OpenCode warn on most
deliveries **did not materialise** at 120x30 — that verdict is specific to a
pane too short for the footer, not to OpenCode as such.

**Unfocused-pane dimming hypothesis: not reproduced.** No agent dimmed its
composer while its pane was inactive; every `preBUSY` reading above was taken
from a non-active pane, so a dimmed-composer misread would have shown up as a
`preBUSY` failure across the board, and did not.

**Coverage note.** Claude's `d = 0 / 0.5 / 0.75` cells were skipped on the first
run (the pane did not reach READY within 40s) and were re-run separately after
the harness gained a launch retry; the table above is the union of both runs.
That the retry was needed at all is a reminder that this box is not always
fast — a second argument for the margin taken above.

## Final Implementation Notes

- **Actual work done:** `_fire_shadow_recheck` now hands the Enter to a new
  `_submit_shadow_prompt`, which drains, re-reads the pane, sends the Enter only
  on a positively `SHADOW_BUSY` composer, and then verifies the submit from a
  fresh capture — retrying once on a swallowed Enter and auto-disarming with the
  leftover-text message when the budget is exhausted. Two constants
  (`COMPOSER_DRAIN_SECONDS`, `SHADOW_SUBMIT_RETRIES`) and a rebindable
  module-level `_composer_drain` seam. 13 new tests, a Claude verdict table, a
  cross-agent BUSY invariant, and safety-contract items 7 and 9 rewritten in
  `shadow_agent.md`. The pre-phase sweep (150 live reps, all three agents) is
  retained above in `## Measurement`.

- **Deviations from plan:**
  - **Shipped 0.5, not the 0.25 the pre-registered rule selects.** Stated in
    full in `## Measurement`; surfaced at the Step-8 review as an overrulable
    decision rather than folded in silently.
  - **The text-identity retry guard in the approved design was dropped.** The
    plan already recorded the reasoning (tail matching is broken by soft-wrap
    and non-discriminating against the echo); confirmed during implementation
    and the `foreign`-text branch was never written.
  - **A token re-check was removed, not added.** The approved design said
    "re-check after every await AND before every Enter". Its negative control
    proved the loop-top check unfalsifiable — the check immediately before the
    Enter catches the same case first — so it was deleted rather than kept as
    unreachable belt-and-braces. The invariant ("no Enter after cancellation")
    is unchanged and is pinned by two tests.
  - **The live smoke was upgraded, not written off.** The plan concluded a
    `cat` pane could not cover the verifier and told the implementer to say so
    in a comment. It was instead given a ~20-line stub composer that holds
    typed bytes and clears on `\r`, which makes it cover the drain, the
    pre-Enter gate and the post-Enter verification against a real pane through
    the real gateway — verified by mutating the gate and watching the smoke
    fail. It still cannot cover per-CLI input coalescing; that is what the
    sweep is for.
  - The shared `_LoopFakeMon` gained a composer model (typed on a literal
    write, cleared on Enter, with a `swallow_enter` switch) instead of every
    fire test hand-scripting the readback. `_loop_app` also takes the shadow
    agent's `typed_tail`, since a Claude tail under an OpenCode shadow reads as
    "not a composer" and would veto every delivery.

- **Issues encountered:**
  - The first full-module run failed exactly where the plan predicted
    (`test_a_dialog_seen_only_at_delivery_arms_the_settle_latch`): the fake's
    capture queue never modelled the composer receiving the text, so the
    pre-Enter gate vetoed. Fixture problem, not invariant problem — fixed in
    the fake.
  - Claude's `d = 0 / 0.5 / 0.75` sweep cells were skipped on the first run
    (pane not READY within 40s). The harness gained a launch retry and the
    cells were re-run; the union is in `## Measurement`.
  - At a failing delay the first repetition wedges the pane (unsubmitted text
    is precisely the bug), so Escape alone left every later repetition
    reporting `never_ready_before_rep`. Adding a `C-u` recovery pass is what
    made the `d = 0` negative control yield 10 real data points instead of 1.
  - Another session was editing `review_loop.py` and two of the same test files
    mid-task (t1520, OpenCode shadow readiness). It landed before implementation
    started, so the work was rebuilt against the post-t1520 `_ordered_state`
    shape; a second unrelated session was active in the tree at commit time, so
    the commit is path-scoped to this task's six files.

- **Upstream defects identified:** None. (The OpenCode `preBUSY` 9/10 at
  d = 0.75 and the two `dialog` post-Enter samples are the *documented* masking
  limitation of `_ordered_state`'s pattern-before-composer order showing up in
  live data, not a separate defect — they are recorded in `## Measurement` and
  in safety-contract item 9.)
