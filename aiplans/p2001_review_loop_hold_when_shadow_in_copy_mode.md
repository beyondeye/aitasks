---
Task: t2001_review_loop_hold_when_shadow_in_copy_mode.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2001 — Review loop holds while the shadow pane is in a tmux mode

## Context

The minimonitor auto-recheck loop (`L`) auto-disarms with `text_not_in_composer`
whenever the shadow pane is in a tmux mode — in practice copy-mode, entered by
mouse-wheeling an inline Codex/Claude shadow back. `capture-pane` reads the
pane's *underlying* screen, so readiness reads READY and the loop fires; but
`send-keys` is dispatched to the *mode's* key table, so the prompt runs as
copy-mode commands (cursor motion, `space` = begin-selection, `:` = goto-line
prompt on the user's client), nothing reaches the agent, tmux still returns
rc 0, and the pre-Enter readback finds an empty composer → fatal disarm.
Confirmed live (4 events today, all `rounds_fired: 0`) and on a scratch socket.

Also in scope: `tests/test_minimonitor_concern_action.py` redirects
`AITASKS_REVIEW_LOOP_LOG_DIR` in one mixin only, so every other loop test
appends to the user's real `~/.config/aitasks/review_loop_events/` — 16 of the
19 session files there today are test-shaped (`window: "agent-x"`), and
`MAX_SESSION_FILES = 20` retention means each run evicts real history.

Outcome: the loop never sends a key into a moded shadow pane; it **holds
visibly and stays ARMED**, and delivers by itself on the first tick after the
user leaves the mode. Tests stop writing to the real event store.

## Decisions taken at planning

- **Mode query = a dedicated `display-message` helper**, not a 5th field in
  `shadow_query_args()`. The guard must read the mode at the execution
  boundary (immediately before each keystroke); the list-panes query runs at
  tick time and would be stale by then. It also leaves the parsed lookup format
  and its seam-arity tests untouched.
- **Pre-Enter (task Fix 3): hold immediately, no bounded wait.** The race
  (user enters a mode inside the ~0.5 s drain between write and Enter) is
  narrow; a bounded wait would lengthen the existing "user types into the
  composer before our Enter" exposure from 0.5 s to the wait budget, and still
  needs the hold as its fallback. Release trace: the composer holds our text →
  every later tick reads `SHADOW_BUSY` → readiness not-True → no re-fire, no
  re-write. It releases when the user acts: **submits** (shadow works, the
  recheck re-stamps staleness, the True→False edge closes the work latch — no
  duplicate round) or **clears** (READY; once the settle deadline the BUSY
  ticks armed has elapsed, the next tick re-fires and delivers). The banner
  says so. Pinned end-to-end by test 8e.
- **Ordering inside both methods: query → token check → every verdict branch
  → keystroke.** The query is a new await, so the delivery token is re-checked
  directly after it and *before any* outcome is decided — the existing
  readiness branches (BUSY gate, fatal READY/WORKING, DIALOG/UNKNOWN holds) as
  well as the new mode verdict. Rationale: `_service_review_loop`
  (`minimonitor_app.py:4586`) routes every `failed` outcome to
  `_loop_auto_disarm` with no generation check, so a stale delivery that
  returns a fatal code after an await destroys a freshly re-armed lifecycle.
  Today that hole already exists in `_submit_shadow_prompt`: the
  `before != SHADOW_BUSY` dispatch runs after the drain and capture awaits but
  *before* the token check, so a disarm + re-arm during either, with a READY or
  WORKING read, kills the fresh arm via `DISARM_TEXT_NOT_IN_COMPOSER`. Moving
  the check closes it for all three preceding awaits (drain, capture, mode
  query) at once. READY/WORKING stay fatal **for a valid token**.
- **Every other fatal-after-await route gets the same check.** Enumerated in
  both methods: `_fire_shadow_recheck` returns `failed` only from sync points
  that already follow a token check (`DISARM_NO_MONITOR`, and
  `DISARM_PROMPT_WRITE_FAILED` after the new post-query check);
  `_submit_shadow_prompt` returns `failed` from READY/WORKING (fixed above),
  `DISARM_ENTER_SEND_FAILED` (sync, directly after the token check) and the
  budget-exhausted `DISARM_SUBMIT_UNCONFIRMED`, which today follows the last
  post-Enter drain + capture with no check — it gets one. A superseded delivery
  then always returns `("not_ready", HOLD_DELIVERY_SUPERSEDED)`, the existing
  t1606 semantics (recorded, no banner, never a disarm).
- **Fail closed:** a failed/malformed query authorises nothing (hold, never
  write) — the `HOLD_PRE_ENTER_UNREADABLE` precedent.
- **Never cancel the user's mode** (no `send-keys -X cancel`, no `copy-mode -q`).
- **Accepted residual:** a mode entered between the query and the `send-keys`
  (one subprocess round trip) is not closed; an atomic `if-shell -F` form would
  need the prompt quoted into a tmux command string and loses the send rc. It
  stays identifiable from the log via the Fix-5 diagnostics.
- **Fix 5 (diagnostics) is in scope:** delivery-originated hold/disarm records
  carry `pre_enter_verdict`, `pane_in_mode`, `pane_mode`, and `--loop-log`
  prints them.
- **"Real dir untouched" test → deterministic equivalent.** The real store is
  shared with the user's live minimonitors, so asserting it is unchanged would
  race. Instead pin that every write in the module lands in the module dir,
  and that the per-test mixin restores (not clears) the module redirect.

### Pre-phase (risk mitigations)

1. [measure_pane_mode_query] On a private socket
   (`tmux -L ait_t2001_probe -f /dev/null`, `mode-keys vi`, a pane running
   `cat`), record rc + exact stdout (`repr`) of
   `display-message -p -t <pane> '#{pane_id}\t#{pane_in_mode}\t#{pane_mode}'`
   for: normal pane, after `copy-mode`, after `clock-mode`, and a killed pane
   id; and once through `TmuxMonitor.tmux_run_async` (gateway path). Expected:
   `%N\t0\t\n`, `%N\t1\tcopy-mode\n`, `%N\t1\tclock-mode\n`, rc≠0 for the dead
   pane. If any row differs, adjust the Step 1 parser before continuing. Kill
   the probe server afterwards. Record the table in the plan's Final
   Implementation Notes.

## Implementation steps

### 1. `query_pane_mode` helper — `.aitask-scripts/monitor/monitor_core.py`

Add next to `capture_raw_tail` (~line 676), gateway-routed:

```python
async def query_pane_mode(monitor, pane_id: str) -> tuple[bool | None, str]:
    """Whether ``pane_id`` is in a tmux mode: ``(in_mode, mode_name)``.

    In a mode (copy-mode from a wheel scroll-back, view/tree/clock/buffer …)
    ``send-keys`` is dispatched to the MODE's key table, not the application:
    a literal write runs copy-mode commands, nothing reaches the agent, and
    tmux still returns rc 0. ``capture-pane`` reads the underlying screen
    either way, so no capture-based readiness check can see it (t2001).

    ``in_mode`` is ``None`` when it could not be determined — no monitor,
    rc != 0 / timeout, or a reply that does not echo ``pane_id`` with a
    ``0``/``1`` flag (a missing pane, a stub). A caller that AUTHORISES a
    keystroke must read ``None`` as "do not send". ``mode_name`` is
    diagnostic only.
    """
    if monitor is None:
        return None, ""
    rc, out = await monitor.tmux_run_async(
        ["display-message", "-p", "-t", pane_id,
         "#{pane_id}\t#{pane_in_mode}\t#{pane_mode}"],
        timeout=_SHADOW_CAPTURE_TIMEOUT,
    )
    if rc != 0:
        return None, ""
    lines = out.splitlines()
    parts = lines[0].split("\t") if lines else []
    if len(parts) < 2 or parts[0] != pane_id or parts[1] not in ("0", "1"):
        return None, ""
    return parts[1] == "1", (parts[2] if len(parts) > 2 else "")
```

Re-export it from `.aitask-scripts/monitor/tmux_monitor.py` (beside
`capture_raw_tail`, ~line 64) and import it in `minimonitor_app.py` (import
block ~line 45).

### 2. Vocabulary — `.aitask-scripts/monitor/review_loop.py` (~lines 118–173)

Four non-fatal codes (one per condition, per the t1606 rule):

| code | where | message (`LOOP_REASON_MESSAGES`) | banner (`LOOP_HOLD_BANNERS`, ≤76) |
|---|---|---|---|
| `HOLD_SHADOW_IN_MODE = "shadow_in_mode"` | before the write | "the shadow pane is in a tmux mode (e.g. scrolled back) — nothing written; the recheck goes out once it leaves the mode" | `⟳ holding: shadow pane in tmux mode (e.g. scrolled back) — will retry` |
| `HOLD_SHADOW_MODE_UNREADABLE = "shadow_mode_unreadable"` | before the write | "could not read the shadow pane's tmux mode — nothing written" | `⟳ holding: shadow pane mode unreadable — will retry` |
| `HOLD_PRE_ENTER_IN_MODE = "pre_enter_in_mode"` | before an Enter | "the shadow pane entered a tmux mode before the Enter — recheck text left in the shadow composer; submit or clear it there" | `⟳ holding: Enter withheld (shadow in tmux mode) — check its composer` |
| `HOLD_PRE_ENTER_MODE_UNREADABLE = "pre_enter_mode_unreadable"` | before an Enter | "could not read the shadow pane's tmux mode before the Enter — recheck text left in the shadow composer; submit or clear it there" | `⟳ holding: Enter withheld (shadow mode unreadable) — check its composer` |

The pre-Enter banners describe the event, not the composer's current state,
so they stay true after the user submits (a hold banner persists until the next
delivery — existing semantics shared with `HOLD_PRE_ENTER_DIALOG`). Fix the
`LOOP_HOLD_BANNERS` comment ("the two holds that get a visible banner").

### 3. Pre-write guard — `MiniMonitorApp._fire_shadow_recheck` (`minimonitor_app.py:4610`)

- First line: `self._loop_delivery_detail = {}`.
- After the existing `monitor is None` check, immediately before
  `monitor.send_keys(shadow_pane, prompt, literal=True)`:

```python
        in_mode, mode_name = await query_pane_mode(monitor, shadow_pane)
        self._loop_delivery_detail = _pane_mode_detail(in_mode, mode_name)
        if not ctrl.delivery_valid(token):
            return "not_ready", review_loop.HOLD_DELIVERY_SUPERSEDED
        if in_mode is None:
            return "not_ready", review_loop.HOLD_SHADOW_MODE_UNREADABLE
        if in_mode:
            return "not_ready", review_loop.HOLD_SHADOW_IN_MODE
```

  with a comment stating the release trace: readiness stays True while moded
  (the underlying screen is static, nothing re-arms the settle latch, no
  cooldown is stamped), so every tick re-reserves and re-queries, and the first
  tick after the user leaves the mode delivers.
- Module-level helper `_pane_mode_detail(in_mode, mode_name) -> dict` →
  `{"pane_in_mode": "1"|"0"|"unreadable", "pane_mode": mode_name or None}`.
- Docstring: add the pane-mode precondition to the method's contract.

### 4. Pre-Enter guard — `_submit_shadow_prompt` (`minimonitor_app.py:4679`)

In the attempt loop, right after the `before` capture — the token check moves
up from its current place (after the readiness dispatch) to directly after the
new await, ahead of **every** branch:

```python
            await _composer_drain(review_loop.COMPOSER_DRAIN_SECONDS)
            before = review_loop.shadow_state(
                await capture_raw_tail(monitor, shadow_pane), shadow_key)
            in_mode, mode_name = await query_pane_mode(monitor, shadow_pane)
            self._loop_delivery_detail = {
                **_pane_mode_detail(in_mode, mode_name),
                "pre_enter_verdict": before}
            # Supersession FIRST — before any verdict, fatal ones included.
            # No await follows this check until the Enter, so it still sits
            # "directly in front of" the keystroke, and a stale delivery can
            # never return a fatal code into a freshly re-armed lifecycle.
            if not ctrl.delivery_valid(token):
                return "not_ready", review_loop.HOLD_DELIVERY_SUPERSEDED
            if before != review_loop.SHADOW_BUSY:
                ...  # existing DIALOG/UNKNOWN holds + READY/WORKING fatal, unchanged
            if in_mode is None:
                return "not_ready", review_loop.HOLD_PRE_ENTER_MODE_UNREADABLE
            if in_mode:
                return "not_ready", review_loop.HOLD_PRE_ENTER_IN_MODE
            if not monitor.send_keys(shadow_pane, "Enter"): ...   # unchanged
```

and before the budget-exhausted return after the loop:

```python
        if not ctrl.delivery_valid(token):
            return "not_ready", review_loop.HOLD_DELIVERY_SUPERSEDED
        return "failed", review_loop.DISARM_SUBMIT_UNCONFIRMED
```

The query sits before the readiness dispatch so the fatal READY/WORKING path
also records the mode (Fix 5). The BUSY gate and the READY/WORKING asymmetry
are unchanged for a valid token. Docstring: add the pane-mode gate, the release
trace from "Decisions", rewrite the token paragraph (the check now precedes
every outcome, and why — the caller disarms on any `failed`), and replace
"suspends four times" with wording that does not hard-code a count. Also
update the comment on the old token-check site (its "sibling check in
`_fire_shadow_recheck`" rationale moves with it).

### 5. Carry the detail — `minimonitor_app.py`

- `__init__` (~line 1322, beside `_loop_identity`):
  `self._loop_delivery_detail: dict[str, object] = {}` with a one-line comment.
- `_service_review_loop` ACTION_FIRE branch (~4571): pass
  `detail=self._loop_delivery_detail` to `_loop_hold(reason, …)` and
  `_loop_auto_disarm(reason, …)`.
- `_loop_hold(self, reason_code, *, detail=None)` and
  `_loop_auto_disarm(…, detail=None)`: build
  `fields = {**self._loop_event_context(), **(detail or {})}` and pass
  `**fields` to `record_event` (no other behaviour change; absence disarms pass
  no detail).

### 6. `--loop-log` shows it — `.aitask-scripts/monitor/review_loop_log.py:format_event`

Append `"pre_enter_verdict", "pane_in_mode", "pane_mode"` to the context-key
tuple.

### 7. Stop tests writing to the real store

- New `tests/review_loop_log_isolation.py`:
  `isolate_event_store(rll) -> (Path, restore)` — makes a
  `TemporaryDirectory`, saves the previous `rll.LOG_DIR_ENV`, points it at
  `<tmp>/events`, calls `rll.reset_session_for_tests()`; `restore()` puts the
  previous value back (pop when it was unset), resets the memo, removes the dir.
  Takes the module object so the caller resets the same `_session_path` memo
  the app writes through (`mm.review_loop_log`).
- `tests/test_minimonitor_concern_action.py` and
  `tests/test_minimonitor_concern_smoke.py`: `setUpModule` / `tearDownModule`
  calling it (honoured by both the pytest and unittest-discover backends).
- `_LoopEventStoreMixin.setUp` (`test_minimonitor_concern_action.py:3833`):
  save the previous env value and **restore** it in cleanup instead of
  `os.environ.pop` — the pop would drop the module redirect for every later
  test in the module.
- `_mk_app`: `app._loop_delivery_detail = {}` (it mirrors `__init__`).

### 8. Unit tests — `tests/test_minimonitor_concern_action.py`

Fake: `_LoopFakeMon` gains a pane-mode model — `pane_in_mode = "0"`,
`mode_name = ""`, `mode_rc = 0`, `mode_queries = 0`, `on_mode_query = None`
hook; `tmux_run_async` answers `display-message` with
`f"{pane}\t{pane_in_mode}\t{mode_name}\n"`; and `send_keys` into a moded pane
records the call but leaves the composer untouched (real tmux semantics), so
pre-fix code reproduces `text_not_in_composer` faithfully.

New class `ShadowPaneModeGuardTests(_LoopEventStoreMixin, unittest.TestCase)`
(armed fixture as in `ReadyPreEnterStaysFatalTests`):

a. moded pane (`"1"`, `copy-mode`), several ticks → **zero** `send_keys`;
   armed; state WAITING; banner = `HOLD_SHADOW_IN_MODE`'s; exactly one hold
   record carrying `pane_mode: "copy-mode"`; one toast. **Red on pre-fix code.**
b. negative control: same fixture with `"0"` → prompt written once, Enter sent,
   `rounds_fired == 1`.
c. query failure (`mode_rc = 1`) → no write, hold `HOLD_SHADOW_MODE_UNREADABLE`,
   armed.
d. recovery end to end: moded for 3 ticks, then `"0"`, one tick → delivered
   (one literal write, one Enter), `_loop_hold_reason is None`, banner
   `recheck #1 sent`; and `_loop_shadow_settle_until` stayed `None` throughout
   the hold (nothing in the stuck state re-armed a latch).
e. mode flips after the write (`on_mode_query` sets `"1"` on the 2nd query) →
   one literal write, **zero** Enter, hold `HOLD_PRE_ENTER_IN_MODE`, composer
   still holds the prompt, record carries `pre_enter_verdict: "busy"`,
   `pane_in_mode: "1"`; 4 more ticks write nothing. Release: clear the fake
   composer, `"0"`, `_advance_past_settle`, tick → second write + Enter → sent.
f. 2nd query fails → `HOLD_PRE_ENTER_MODE_UNREADABLE`, zero Enter.
g. supersession during an await never decides an outcome. Hook = disarm
   **and re-arm** (`ctrl.disarm(); ctrl.arm(pending_work=True)`), driven
   through `_tick` so the real `_service_review_loop` routing runs. Rows:
   - at the pre-write mode query → no write; superseded hold;
   - at the pre-Enter mode query, with the pre-Enter read set to each of
     `BUSY` (typed tail), `READY` (at-rest tail) and `WORKING` (streaming
     tail) → no Enter; outcome `HOLD_DELIVERY_SUPERSEDED`;
   - at the pre-Enter **capture** (`on_capture`), `READY` → same (closes the
     pre-existing drain/capture gap, not just the new await);
   - at the final post-Enter capture with `swallow_enter = True` → superseded,
     not `DISARM_SUBMIT_UNCONFIRMED`.

   Every row asserts the **fresh** lifecycle survives: `ctrl.armed`, the
   post-hook generation is unchanged after the tick, and **no** disarm record /
   disarm toast. **Red on pre-fix code** for the READY/WORKING rows and the
   exhaustion row (they disarm the fresh arm today). Controls, valid token
   (no hook): READY and WORKING still disarm with `DISARM_TEXT_NOT_IN_COMPOSER`
   (WORKING is new here; READY is `ReadyPreEnterStaysFatalTests`), and the
   swallowed-Enter row still disarms with `DISARM_SUBMIT_UNCONFIRMED`.
h. Fix 5: READY before the Enter → the `text_not_in_composer` disarm record
   carries `pre_enter_verdict: "ready"` and `pane_in_mode: "0"`.

`QueryPaneModeTests` (pure, `_FakeMon`-style stub): rows for monitor `None`,
rc≠0, empty stdout, wrong pane echo, flag `"2"`, two-field reply (`"%5\t1"`),
three-field reply → `(None,"")` ×5, `(True,"")`, `(True,"copy-mode")`; and the
argv is exactly the `display-message` form above.

Log isolation: `test_the_module_store_is_redirected` (`rll.session_path()`
lives under the module dir, not the expanded default) and
`test_the_mixin_restores_the_module_redirect` (run a throwaway mixin case's
`setUp()` + `doCleanups()`; the env var still names the module dir — red on
the current `pop`).

Vocabulary: `tests/test_review_loop.py::test_the_leftover_message_is_used_only_where_text_is_left`
— add the two pre-Enter mode codes to the expected set and extend its
docstring with the third condition (a positive BUSY read of the text just
written, Enter withheld because the pane was — or could not be shown not to
be — in a mode). The banner-budget and code/message-set tests in both modules
cover the new entries automatically.

`tests/test_review_loop_log.py`: `format_event` prints the three new fields.

### 9. Real-tmux integration — `tests/test_minimonitor_concern_smoke.py`

In `RecheckInjectionSmokeTests` (reuses its composer-stub pane and private
socket): factor the existing test's app/controller build into a helper, then
`test_a_pane_in_copy_mode_receives_nothing_and_stays_in_mode`:
`set-option -wg mode-keys vi`, `copy-mode -t <pane>` (cleanup:
`send-keys -X cancel`), snapshot `capture-pane -p` and
`#{pane_in_mode} #{selection_present}` (= `1 0`); fire →
`("not_ready", HOLD_SHADOW_IN_MODE)`; afterwards still `1 0` and the capture is
unchanged. Then the *test* cancels the mode, re-reserves, fires → `"sent"`.
Red on pre-fix code (the prompt's spaces start a vi selection).

### 10. Docs — `aidocs/framework/shadow_agent.md`

- Item 6 (`:763`): a pane in a tmux mode is a pause condition, never a
  disarm; the mode query fails closed.
- Item 9 (`:807`): the pane-mode precondition before the write and before each
  Enter; why capture-based readiness cannot see it; the four codes; never
  cancel the user's mode; the accepted query→send residual. Supersession: the
  token is re-checked after the last await and before **every** outcome (not
  only before the Enter), because the caller disarms on any `failed` — state
  the stale-fatal-outcome hazard it closes, including the budget-exhausted
  route. Fix the "four suspension points" wording.
- *Review-loop event log*: delivery events carry `pre_enter_verdict` /
  `pane_in_mode` / `pane_mode`.

## Verification

1. **Red proof first.** Land Step 8's fake changes and new tests (and Step 9)
   before Steps 1–5; run the two modules: the new in-mode/log-isolation tests
   fail for the expected reason (prompt written / disarm, env popped), the 8g
   READY/WORKING/capture/exhaustion re-arm rows fail by disarming the fresh
   arm, and every pre-existing test stays green (the fake's mode branch is
   inert pre-fix). The 8g rows hooked on the *mode query* are red pre-fix only
   because no query exists for the hook to fire on, so the capture-hooked and
   exhaustion rows are the meaningful pre-fix reds for the ordering; each test
   asserts its hook actually fired, so a row cannot pass vacuously.
   Then implement and re-run.
2. `python -m pytest tests/test_minimonitor_concern_action.py tests/test_review_loop.py tests/test_review_loop_log.py tests/test_minimonitor_concern_smoke.py -q`
3. `bash tests/test_no_raw_tmux.sh` (the helper is gateway-routed).
4. Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3` — verdict from the last line.
5. Pollution check: list `~/.config/aitasks/review_loop_events/` before and
   after step 2; no new file may contain `"window": "agent-x"` or the smoke
   sessions' names (live minimonitors may add real files meanwhile — those
   carry real session names).
6. Commit only this task's paths (the shared tree has unrelated dirty files).

## Step 9 (Post-Implementation)

Per task-workflow Step 9: review, commit (`bug: … (t2001)`), archival.
Possible follow-up to offer (not in scope): a row for the hold banners in the
website's minimonitor banner table (`website/content/docs/tuis/minimonitor/how-to.md:266`),
which today lists none of the hold banners.

## Risk

### Code-health risk: medium
- Adds two awaits to the only unattended key-injection path; a token check missing after either — or placed after any outcome branch — would let a superseded delivery send keys or return a fatal code that disarms a freshly re-armed lifecycle (already the case today for READY/WORKING after the drain/capture awaits, and for the budget-exhausted return) · severity: medium · → mitigation: none (closed by the query → token → every-branch ordering + the exhaustion-route check; pinned by the 8g matrix, red pre-fix)
- `_LoopFakeMon` change routes every existing fire test through the new query; a wrong default would silently flip them to holds · severity: low · → mitigation: none (Verification step 1 runs the whole module green before the production change)
- Deliberately widens the pinned t1606 "leftover text" invariant to two new codes · severity: low · → mitigation: none (explicit test + docstring update)
- Two extra tmux round trips per evidence tick (≥1 s) while a pre-write hold stands · severity: low · → mitigation: none

### Goal-achievement risk: low
- The parser assumes `display-message` reply shapes (dead pane rc, trailing tab with an empty `pane_mode`) that are not yet measured on this tmux · severity: low (residual — addressed by inline pre-phase measure_pane_mode_query) · → mitigation: inline pre-phase measure_pane_mode_query
- Query→send TOCTOU residual stays open (sub-millisecond); the reported case — a user already scrolled back when the loop fires — is fully covered · severity: low · → mitigation: none (documented, diagnosable via Fix 5)
- Pre-Enter hold leaves the recheck text in the composer until the user submits or clears it; the release is traced and tested (8e) · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: measure_pane_mode_query | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — display-message reply shapes unmeasured | desc: Measure display-message pane-mode reply shapes (normal, copy, clock, dead pane, gateway path) on a private socket before writing the parser
