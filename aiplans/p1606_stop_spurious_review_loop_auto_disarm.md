---
Task: t1606_stop_spurious_review_loop_auto_disarm.md
Worktree: aiwork/t1606_stop_spurious_review_loop_auto_disarm
Base branch: main
Output branch: main
plan_verified: []
---

# t1606 — Stop the spurious review-loop auto-disarm

## Context

The minimonitor auto-recheck loop (`L`, t1159_2) auto-disarms almost immediately
after arming, non-deterministically. Re-arming usually works, so the feature is
not broken so much as unusable — and the user cannot tell why it happened,
because the reason exists only in a ~5 s fading Textual toast.

**The production cause is still unconfirmed.** t1606's evidence table records six
mechanisms ruled out empirically against the live session, and the failure was
not reproducible synthetically. That is the whole reason Deliverable 1 comes
first: every remaining hypothesis is unfalsifiable in production today because
nothing records why the loop died.

Three deliverables, in order:

1. **Make the disarm reason knowable** — a machine-readable code per condition,
   carried from the deciding site to the disarm, plus a durable record.
2. **Ambiguous pre-Enter reads must hold, not disarm.**
3. **The message must be true** — today an unreadable pane is reported as
   "recheck text left in the shadow composer" while the composer is empty.

### What exploration changed about the task's own account

| task says | actually |
|---|---|
| 4 auto-disarm call sites | **4 sites, but 3 distinct teardowns**: `_loop_auto_disarm` plus **two inline copies** in `_service_review_loop` (latched-False replay ~3630, `ctrl.tick` ~3650). Both copies **omit `self._loop_shadow_settle_until = None`**, which the real helper clears. Live divergence. |
| ≥5 conditions collapsed into 2 strings | **7**, and `leftover`/`missing` are **local variables**, not constants (`minimonitor_app.py:3806,3808`) |
| — | **The same condition already has two opposite outcomes.** `_fire_shadow_recheck`'s token check returns `"not_ready"` → `abort_fire`; `_submit_shadow_prompt`'s token check returns `"failed"` → **disarm**. So a user pressing `L` to disarm *then re-arm* during a drain has the stale delivery kill the **fresh** arm, and get told "recheck text left in the shadow composer" for a state they caused. |
| — | `tick()` has exactly **one** `ACTION_AUTO_DISARM` producer, and it cannot distinguish agent-gone from shadow-gone |

### Constraints discovered

- **`review_loop.py` performs no I/O by contract** (module docstring: "no tmux,
  no Textual, no subprocess — so the whole state machine is unit-testable").
  Reason codes are pure data and belong there; the durable write does not.
- **`tick()` returns a bare `str`** compared with `==` at ~5 sites in
  `minimonitor_app.py` plus `test_minimonitor_concern_smoke.py` and
  `test_review_loop.py`. Widening it to a tuple/dataclass breaks all of them —
  a parallel `ctrl.last_disarm_reason` attribute breaks none.
- **`abort_fire` is already the stay-armed path** (DELIVERING → WAITING, streak
  preserved, `work_seen` untouched, no generation bump, **no cooldown stamp**).
  No new controller state is needed.
- **Banner budget is hard.** `#mini-loop-status` is `max-height: 2` at 38 usable
  columns; `_LOOP_STATUS_ROWS = 2` feeds `_MAX_CHROME_ROWS`, pinned by
  `test_pane_list_keeps_a_row_under_full_live_chrome`. Hold text must fit
  **≤ ~76 cells**.
- **No logging infrastructure exists anywhere** under `.aitask-scripts/monitor/`
  or `lib/`. This introduces the framework's first long-running log.

### Why only DIALOG and UNKNOWN abort

`abort_fire` stamps no cooldown, so the next tick re-permits immediately:

| pre-Enter verdict | `_ready_from_state` | abort-and-hold |
|---|---|---|
| `DIALOG` | `False` | holds — self-blocking ✓ |
| `UNKNOWN` | `None` | holds — self-blocking ✓ |
| `WORKING` | `False` | holds ✓ |
| `READY` | `True` | **re-fires at once, re-writing the prompt each cycle** ✗ |

`READY` is exactly the case where the text is *not* in the composer, so a retry
reproduces the condition forever — an unbounded key-injection spin. `READY` and
`WORKING` therefore keep disarming, with the `missing` message, which is already
true. This is also the narrowest reading of Deliverable 2's own heading
("*ambiguous* pre-Enter reads") and matches Deliverable 3: the false message is
attached to exactly the `DIALOG`/`UNKNOWN` pair.

This is consistent with t1525, not a reversal of it. p1525 chose the **veto**
("the pre-Enter gate authorises an *action*, so it fails **closed**") — the
disarm came from `_service_review_loop` routing `"failed"` to
`_loop_auto_disarm`, not from t1525's own reasoning. The "visible auto-disarm
over silent hold" line quoted in t1531 attaches to **drain-constant rot**, i.e.
the retry-exhaustion path, which stays fatal here. And `shadow_agent.md` safety
contract item 6 already states the rule the current code breaks: *"Disarm only
on verified absence; pause on uncertainty."*

---

### Pre-phase (risk mitigations)

Both land **before** any production edit, in their own commit, and both are
expected to be **green against today's code** — they exist to make the premises
of Phases 1–2 executable rather than inferred.

- **`pin_ambiguous_verdicts_hold`** — in `tests/test_review_loop.py`. Assert
  `_ready_from_state` maps `SHADOW_DIALOG`→`False`, `SHADOW_UNKNOWN`→`None`,
  `SHADOW_WORKING`→`False`, `SHADOW_READY`→`True`; then drive a controller in
  `WAITING` with a full `DEBOUNCE_TICKS` streak and `work_seen` set, and assert
  it returns `ACTION_NONE` with `holding_for_shadow` True for each of the three
  not-`True` values, and `ACTION_FIRE` for `True`. This is the load-bearing
  premise of the Phase 2 abort scope — that an aborted delivery provably holds —
  and it must fail loudly if a future detector or latch change makes `DIALOG`
  ready-`True`.

- **`characterize_teardown_paths`** — in `tests/test_minimonitor_concern_action.py`.
  Pin what each of the three disarm teardowns does *today*, one case each:
  `_loop_auto_disarm`, the latched-False replay branch, and the `ctrl.tick`
  branch. Include the current divergence explicitly — the two inline branches
  leave `_loop_shadow_settle_until` **set** where the helper clears it. Phase 1c
  then **flips** those two assertions to `assertIsNone`, so the consolidation's
  behaviour change is a visible diff rather than a silent correction.
  Label the flipped assertions as characterization, not contract, so the next
  reader does not restore the buggy expectation.

## Phase 1 — Make the reason knowable (must land first, own commit)

### 1a. Reason vocabulary + message table — one canonical site

`.aitask-scripts/monitor/review_loop.py`, module-level plain strings matching the
existing `ACTION_*` / `SHADOW_*` style (no `Enum` — this module has none):

```python
# --- Auto-disarm reasons (fatal: the loop is destroyed) ---
DISARM_AGENT_GONE            = "agent_gone"
DISARM_SHADOW_GONE           = "shadow_gone"
DISARM_NO_DETECTOR           = "shadow_has_no_detector"
DISARM_NO_MONITOR            = "no_tmux_monitor"
DISARM_PROMPT_WRITE_FAILED   = "prompt_write_failed"
DISARM_ENTER_SEND_FAILED     = "enter_send_failed"
DISARM_SUBMIT_UNCONFIRMED    = "submit_unconfirmed"      # retry budget exhausted
DISARM_TEXT_NOT_IN_COMPOSER  = "text_not_in_composer"    # pre-Enter READY/WORKING

# --- Hold reasons (non-fatal: delivery aborted, loop stays armed) ---
HOLD_PRE_ENTER_DIALOG        = "pre_enter_dialog"
HOLD_PRE_ENTER_UNREADABLE    = "pre_enter_unreadable"
HOLD_DELIVERY_SUPERSEDED     = "delivery_superseded"
HOLD_SHADOW_NOT_SETTLED      = "shadow_not_settled"

LOOP_REASON_MESSAGES: dict[str, str] = { ... }        # code -> user-facing prose
def loop_reason_message(code: str, *, subject: str = "") -> str: ...
```

`loop_reason_message` is the **only** place prose is produced — modelled on
`format_shadow_stale_banner` (`monitor_shared.py:1274`), a pure function with an
explicit ladder, DOM-free testable. `subject` fills the one templated message
(`DISARM_NO_DETECTOR`, which names the shadow command).

Wording, chosen so each is **true** of its own condition:

| code | message |
|---|---|
| `DISARM_AGENT_GONE` | the followed agent's pane is gone |
| `DISARM_SHADOW_GONE` | the shadow pane is gone |
| `DISARM_NO_DETECTOR` | shadow agent '{subject}' has no readiness detection |
| `DISARM_NO_MONITOR` | no tmux monitor |
| `DISARM_PROMPT_WRITE_FAILED` | could not write the recheck prompt to the shadow pane |
| `DISARM_ENTER_SEND_FAILED` | recheck text left in the shadow composer — submit or clear it there manually |
| `DISARM_SUBMIT_UNCONFIRMED` | recheck text left in the shadow composer — submit or clear it there manually |
| `DISARM_TEXT_NOT_IN_COMPOSER` | the recheck prompt is not in the shadow composer — nothing was submitted |
| `HOLD_PRE_ENTER_DIALOG` | shadow showed a dialog before the Enter — nothing sent |
| `HOLD_PRE_ENTER_UNREADABLE` | could not read the shadow pane before the Enter — nothing sent |
| `HOLD_DELIVERY_SUPERSEDED` | delivery superseded |
| `HOLD_SHADOW_NOT_SETTLED` | shadow not settled at delivery time |

The two `leftover` survivors are the **only** two where text genuinely is left
in the composer (a write that succeeded followed by an Enter that provably did
not land). That is Deliverable 3.

### 1b. Carry the code from the deciding site

- `ReviewLoopController.__init__`: `self.last_disarm_reason: str | None = None`.
- `tick()`, in the absence branch, **after** its existing `self.disarm()` call and
  immediately before `return ACTION_AUTO_DISARM`:
  `self.last_disarm_reason = DISARM_AGENT_GONE if agent_present is False else DISARM_SHADOW_GONE`.
  **Return type stays `str`** — every existing `==` comparison keeps working.

**Reason lifetime — `arm()` clears it, `disarm()` must NOT.** This is load-bearing,
not a style choice. The disarm sequence today is
`tick()` → `self.disarm()` → return `ACTION_AUTO_DISARM` → `_loop_auto_disarm`
→ `ctrl.disarm()` **again**. If `disarm()` cleared the reason, the code would be
wiped twice before anything recorded it and the ambiguity this deliverable exists
to remove would survive the fix. So:

- `arm()` clears `last_disarm_reason` — the single clearing point. A lifecycle
  therefore always starts clean, and no teardown can erase a reason in flight.
- `disarm()` leaves it untouched.
- `_loop_auto_disarm(reason_code=None, *, subject="")` **snapshots first**:
  resolve `code = reason_code or ctrl.last_disarm_reason` into a local **before**
  calling `ctrl.disarm()`, and record from the local. With `disarm()` no longer
  clearing, this is belt-and-braces — but the order is stated so a later refactor
  that reintroduces a clear in `disarm()` fails a test instead of silently
  regressing diagnostics.
- Pinned by test 2 below across **all four** tick-originated combinations:
  {`agent_gone`, `shadow_gone`} × {live `ctrl.tick` branch, latched-False replay
  branch}, each asserted to reach the durable record with the right code.
- `_fire_shadow_recheck` / `_submit_shadow_prompt`: second tuple element becomes
  a **reason code**, not prose. On `"sent"` it stays the prompt text (the live
  smoke test at `test_minimonitor_concern_smoke.py:428` reads it — verify before
  changing, and adapt there if it does not).

### 1c. Consolidate the three teardowns

`_loop_auto_disarm(self, reason_code: str | None = None, *, subject: str = "") -> None`
— the signature from 1b, with the snapshot-before-`disarm()` order it specifies.
`reason_code=None` is how the two tick-originated call sites hand off: they pass
nothing and the helper resolves `ctrl.last_disarm_reason`, which is exactly what
lets one helper serve both the delivery failures (explicit code) and the absence
disarms (controller-carried code).

Replace both inline copies in `_service_review_loop` with calls to it — which
also fixes their missing `_loop_shadow_settle_until = None`, the change
`characterize_teardown_paths` makes visible. Toast text becomes
`f"Auto-recheck loop disarmed: {review_loop.loop_reason_message(code, subject=…)}"`,
plus `" (not recorded)"` when `record_event` returned `False`.

### 1d. Durable record — new module

`.aitask-scripts/monitor/review_loop_log.py`. No Textual / tmux / subprocess
imports, so it unit-tests like `agent_marks.py`, whose conventions it follows:

**Storage shape: per-session append-only files. The active file is never
rewritten — there is no trim, no lock, and no rewrite race to accept.**

An earlier draft used one shared `review_loop_events.jsonl` trimmed to a ring via
`atomic_write_text`. That is unsafe and was rejected: the trim is a
read-modify-write, so an append landing on the old inode after the trim read it
but before `os.replace` swaps the path is **silently lost** — and the events most
likely to be lost are exactly the ones Deliverable 1 exists to capture. Locking
every append is not a real alternative here either: **every mutex in this repo is
a shell script** (`lib/registry_lock.sh` and friends; there is no `fcntl` use
anywhere under `.aitask-scripts/`), so it would mean a subprocess on the Textual
event loop on every disarm.

- Dir `~/.config/aitasks/review_loop_events/`, mode `0o700`; env override
  `AITASKS_REVIEW_LOOP_LOG_DIR`.
- **One file per app instance**, named `<YYYYmmddTHHMMSSZ>-<pid>.jsonl`, mode
  `0o600`, opened `"a"` once at first write. **Exactly one writer per file, for
  that file's whole life.**
- `record_event(kind, reason, **fields) -> bool` — one JSON object per line:
  `ts` (ISO-8601 UTC), `schema`, `kind` (`"disarm"`/`"hold"`), `reason`,
  `state`, `rounds_fired`, `agent`, `shadow_agent`, `shadow_pane`, `session`,
  `window`, `project_root`. A single `write()` of one line, truncated to stay
  under `PIPE_BUF` (4096) so the append is atomic on POSIX even if the
  one-writer invariant were ever broken.
- **Retention runs at startup only, and only over files no live process owns.**
  Delete oldest-first until at most `MAX_SESSION_FILES = 20` remain. Two
  independent guards, because deleting a live session's file is the one
  unrecoverable mistake here:
  1. **Liveness** — reuse `lib/monitor_marker.py`'s predicate rather than
     reimplementing it; that file exists precisely because a hand-rolled
     liveness rule "diverges silently" (its own words). A wrong *alive* verdict
     is safe (the file is kept); only a wrong *dead* verdict is dangerous.
  2. **Age floor** — never delete a file modified within the last 10 minutes,
     whatever the liveness verdict says. This covers pid recycling, which
     liveness alone cannot.
  Because retention only ever touches files with **no** writer, it cannot
  interleave with an append at all. The race class is removed by construction,
  not managed.
- **Never raises.** `OSError` → return `False` (the applink `audit.py`
  `NullHandler` doctrine: a logging failure must not take the TUI down). But a
  captured diagnostic that is never surfaced is not a diagnostic: when
  `record_event` returns `False`, `_loop_auto_disarm` appends `" (not recorded)"`
  to its toast, so a silently unwritable log is visible at least once.

### 1e. Reader — `ait minimonitor --loop-log [N]`

The reader **is in scope** (it is the inlined `review_loop_log_reader`
mitigation). Concrete host, no new `ait` verb and no new script:

- `review_loop_log.py` gets an `argparse` `__main__` block that prints the last
  `N` events (default 20) newest-first across all session files, decoding each
  `reason` through `review_loop.loop_reason_message` so the output is prose.
- `aitask_minimonitor.sh` dispatches to it **early** — immediately after
  `PYTHON="$(require_ait_python)"`, before the textual/tmux checks and the
  single-instance guard:

  ```bash
  if [[ "${1:-}" == "--loop-log" ]]; then
      shift
      exec "$PYTHON" "$SCRIPT_DIR/monitor/review_loop_log.py" "$@"
  fi
  ```

  The placement is load-bearing: run after the guard, `ait minimonitor
  --loop-log` inside a window that already hosts a minimonitor would print
  "A monitor is already running. Exiting." and exit 0. Reading a log needs
  neither tmux nor Textual, so it must not inherit those preconditions.
- Missing dir / no events → `(no review-loop events recorded)` on stdout,
  exit 0 — the wording `aitask_gate_log.sh` uses for an absent sidecar.
- **Damaged input must never take the reader down.** A diagnostic tool that
  fails on a damaged file fails exactly when the user needs it. The single
  `write()` under `PIPE_BUF` makes a torn line unlikely *from this writer*, but
  it does not make it impossible — a disk-full partial write, a pre-existing
  damaged file, a hand-edited one, or a future field pushing a line past 4096
  bytes all produce one. So the reader is **line-tolerant, not
  file-tolerant-or-nothing**:
  - parse per line; a line that is not valid JSON, or is valid JSON but not an
    object carrying the required keys, is **skipped**, never fatal;
  - every valid event still prints, newest-first, across all session files;
  - skipped lines are counted and reported once at the end on **stderr**
    (`(skipped N unreadable line(s))`), so stdout stays a clean event stream —
    the same stdout-is-data split `aitask_shadow_capture.sh` states for itself;
  - a file that cannot be opened at all is skipped the same way, with its own
    note; one unreadable file never suppresses the others.
  Exit status stays 0 for skipped lines: partial diagnosis is the useful
  outcome, and a non-zero exit would make the reader unusable in exactly the
  degraded case it exists to serve.

---

## Phase 2 — Ambiguous pre-Enter reads hold instead of disarming (own commit)

`_submit_shadow_prompt`, replacing the current ternary:

```python
if before != review_loop.SHADOW_BUSY:
    if before == review_loop.SHADOW_DIALOG:
        return "not_ready", review_loop.HOLD_PRE_ENTER_DIALOG
    if before == review_loop.SHADOW_UNKNOWN:
        return "not_ready", review_loop.HOLD_PRE_ENTER_UNREADABLE
    return "failed", review_loop.DISARM_TEXT_NOT_IN_COMPOSER
if not ctrl.delivery_valid(token):
    return "not_ready", review_loop.HOLD_DELIVERY_SUPERSEDED   # was "failed"
if not monitor.send_keys(shadow_pane, "Enter"):
    return "failed", review_loop.DISARM_ENTER_SEND_FAILED
...
return "failed", review_loop.DISARM_SUBMIT_UNCONFIRMED
```

**The Enter veto is unchanged** — every one of these still sends no key. Only
the consequence changes, and only for the two ambiguous verdicts plus
supersession.

### The visible hold — `_loop_hold`

t1525 chose visible-auto-disarm over *silent* hold, so the replacement must be a
**visible** hold. In `_service_review_loop`:

```python
elif outcome == "not_ready":
    ctrl.abort_fire(token)
    self._loop_hold(reason)
```

`_loop_hold(self, reason_code: str) -> None`:
- does **not** disarm, and does **not** clear baseline / hash ring / settle latch
- **edge-triggered** on a new `self._loop_hold_reason: str | None`: the toast and
  the durable record fire only when the reason *changes*. Without this a
  persistent `DIALOG` hold writes a log line and a toast on **every tick** — the
  loop holds for many ticks by design.
- `HOLD_DELIVERY_SUPERSEDED` records but does **not** toast or banner: a user
  pressing `L` is a normal lifecycle event, not a fault.
- `_loop_hold_reason` is cleared on a successful fire, on any disarm, and in
  `action_toggle_review_loop`'s arm branch.

Banner, at the tail of `_service_review_loop`, must win over the existing
`"⟳ auto-recheck ARMED"` branch when `_loop_hold_reason` is set:

- `"⟳ holding: shadow showed a dialog — will retry"` (46 cells)
- `"⟳ holding: shadow pane unreadable — will retry"` (46 cells)

Both fit 2 rows at 38, so `_LOOP_STATUS_ROWS` / `_MAX_CHROME_ROWS` do **not**
move. Assert that rather than assume it.

---

## Phase 3 — Docs (same commit as Phase 2)

`aidocs/framework/shadow_agent.md`:
- **Item 6** — extend "Disarm only on verified absence; pause on uncertainty" to
  say the pre-Enter gate now obeys it, and that the hold is visible.
- **Item 9** — rewrite the "Before each Enter … fails **closed**" paragraph: the
  veto is unchanged, but `DIALOG`/`UNKNOWN` now abort to WAITING with a banner
  while `READY`/`WORKING` still disarm, and say why (the `READY` re-fire spin).
- New short subsection naming `~/.config/aitasks/review_loop_events/`, the env
  override, the per-session no-rewrite shape and its retention guards, the
  `ait minimonitor --loop-log` reader, and the reason-code vocabulary.

## Files

| file | change |
|---|---|
| `.aitask-scripts/monitor/review_loop.py` | reason codes, `LOOP_REASON_MESSAGES`, `loop_reason_message`, `last_disarm_reason` |
| `.aitask-scripts/monitor/review_loop_log.py` | **new** — per-session JSONL store, retention, and the line-tolerant reader `__main__` |
| `.aitask-scripts/monitor/minimonitor_app.py` | consolidate 3 teardowns, `_loop_hold`, re-route pre-Enter, reason plumbing |
| `tests/test_review_loop.py` | controller reason codes; message-table drift guard |
| `tests/test_review_loop_log.py` | **new** — append, retention guards, concurrency interleaving, unwritable path, damaged-input reader |
| `tests/test_minimonitor_concern_action.py` | revise 3 pins, add hold/record tests |
| `.aitask-scripts/aitask_minimonitor.sh` | early `--loop-log` dispatch, before the textual/tmux checks and the single-instance guard |
| `aidocs/framework/shadow_agent.md` | items 6 & 9, log dir + reader command |

## Tests

**Revised pins** (contract preserved, only the consequence changes — the Enter
counts are contract and must not move):

- `test_only_a_busy_composer_authorises_the_enter` — add an `armed` column to the
  `subTest` table: `DIALOG` → 0 Enters, **still armed**, dialog-hold message;
  `AT_REST`/`STREAMING` → 0 Enters, **disarmed**, unchanged `missing` message;
  `TYPED` → 1 Enter.
- `test_an_unreadable_pane_before_the_enter_vetoes_the_send` — 0 Enters
  unchanged; assert still armed and the *unreadable* message, not the false
  leftover one.
- `test_prompt_write_failure_sends_no_enter_and_disarms` and
  `test_a_persistently_swallowed_enter_disarms_with_the_leftover_message` —
  **unchanged**; both stay fatal and keep the leftover wording.

**New:**

1. Every `DISARM_*`/`HOLD_*` code has a `LOOP_REASON_MESSAGES` entry and vice
   versa (drift guard on the canonical set).
2. **Reason lifetime**, pinned to match §1b exactly — an earlier draft of this
   list said "arm and disarm clear it", which contradicts §1b and would
   reintroduce the ambiguity during implementation. The pins are:
   - `tick()` distinguishes `DISARM_AGENT_GONE` from `DISARM_SHADOW_GONE`;
   - **`arm()` clears** `last_disarm_reason` (the single clearing point);
   - **`disarm()` preserves it** — assert the value survives a `disarm()` call,
     which is the assertion that stops a refactor from re-adding a clear there;
   - all four tick-originated paths record the **preserved** code:
     {`agent_gone`, `shadow_gone`} × {live `ctrl.tick` branch, latched-False
     replay branch}, each asserted on the durable record, not just the toast.
3. All three teardown paths — including the two formerly-inline ones — clear
   `_loop_shadow_settle_until` and write exactly one durable record.
4. A disarm-then-**re-arm** during a delivery drain leaves the fresh arm alive
   (the supersession bug) and emits no "leftover" toast.
5. **Hold lifecycle — five cases, not one.** Edge-triggering must suppress
   repeats without suppressing genuine change or leaking state:
   - **repeat**: same reason over N ticks → **one** toast, **one** record;
   - **transition**: `DIALOG` → `UNKNOWN` → exactly **one** additional record,
     and the banner is **replaced** with the unreadable wording (assert the new
     text, not merely that it is non-empty);
   - **recovery via fire**: hold, then the shadow reads `BUSY` and the delivery
     succeeds → `_loop_hold_reason` is `None`, the banner shows the FIRED text,
     no residual hold state;
   - **re-hold after recovery**: the *same* reason recurring after a recovery
     emits a **new** record — edge-triggering must not permanently swallow a
     reason it has seen once;
   - **clearing on teardown**: `_loop_auto_disarm` and the arm branch of
     `action_toggle_review_loop` both leave `_loop_hold_reason` `None` and the
     banner consistent with the new state.
6. Both hold literals fit `_LOOP_STATUS_ROWS` rows at 38 columns (assert the
   wrapped height, so wording growth fails here instead of silently eating a
   pane row via `_MAX_CHROME_ROWS`).
7. `review_loop_log`: append round-trips; an unwritable dir returns `False` and
   raises nothing, and the toast then carries "(not recorded)"; retention keeps
   at most `MAX_SESSION_FILES`, **refuses a file whose pid is live**, and
   **refuses a file younger than the age floor** even when liveness says dead.
8. **Concurrency proof for the exact interleaving** (`review_loop_log_concurrency_proof`):
   two writers append to their own session files while a third process runs
   retention; assert **zero lines lost** from either writer, both live files
   still present, and only no-writer files removed. This is the test that would
   have caught the rejected shared-ring/trim shape.
9. Reader: `--loop-log` prints newest-first with decoded prose; an absent dir
   prints `(no review-loop events recorded)` and exits 0; the early dispatch in
   `aitask_minimonitor.sh` runs **before** the single-instance guard (assert it
   works from a window that already hosts a minimonitor).
   **Damaged-input case — a file holding valid records *and* damage:** one
   truncated/non-JSON line, one JSON line that is not an event object, and a
   file that cannot be opened, alongside good records. Assert every valid event
   still prints in the right order, the count of skipped lines goes to
   **stderr** while stdout stays a clean event stream, one unreadable file does
   not suppress another's events, and the exit status is **0**. Negative
   control: make the reader fatal on a bad line and confirm exactly this test
   fails.
10. **Positive control for the `READY` decision**: a pre-Enter `READY` disarms
   and does not re-fire — the case the abort scope deliberately excludes.

**Negative controls** — mutate each new guard, confirm *exactly* the named test
fails, revert. Specifically: delete the edge-trigger (test 5 must fail), route
`DIALOG` back to `"failed"` (revised pin must fail), drop the
`_loop_shadow_settle_until` clear from the consolidated helper (test 3 and the
flipped `characterize_teardown_paths` assertions must fail).

**Mitigation coverage** — the two pre-phase tests must be green *before* any
production edit and are the executable form of two plan premises; the two
post-phase items each carry their own assertions (reader output decodes a known
reason, degrades on a missing file, and tolerates damaged lines; retention never
interleaves with a live append under the per-session no-rewrite shape).

```bash
bash tests/run_all_python_tests.sh --test-dir tests    # read the LAST line only
~/.aitask/venv/bin/python -m pytest tests/test_minimonitor_concern_action.py \
  tests/test_review_loop.py tests/test_review_loop_log.py \
  tests/test_minimonitor_concern_smoke.py
```

### Post-phase (risk mitigations)

Both land **after** Phases 1–3, in their own commit. Inlining them (rather than
spawning) means this task now also owns a small CLI surface and a locking
decision — see the reassessment note under `## Risk`.

- **`review_loop_log_reader`** — build out `ait minimonitor --loop-log [N]` as
  specified in **Phase 1e**, and pin its behaviour (test 9). The scope decision
  is settled there, not here: the reader **ships with this task**.

- **`review_loop_log_concurrency_proof`** — the executable proof of Phase 1d's
  storage shape (test 8). The *shape* is chosen in Phase 1d — per-session
  append-only, active file never rewritten — so nothing about serialization is
  deferred to this phase; what lands here is the interleaving test that makes
  the choice falsifiable, plus the two retention-guard pins. If the test cannot
  be made to fail against a deliberately shared-ring implementation, it is not
  proving anything and must be strengthened before it counts.

## Verification

Beyond the suite: arm the loop (`L`) against a live Claude followed agent with a
Codex shadow, let one recheck fire, and confirm
`ait minimonitor --loop-log` prints it back as decoded prose (and that a session
file appeared under `~/.config/aitasks/review_loop_events/`). **No test
in this suite can prove the original symptom is fixed** — the failure was never
reproducible synthetically, and Deliverable 1 exists precisely to make the next
live occurrence diagnosable. Queue a manual-verification follow-up at Step 8c.

## Risk

### Code-health risk: medium
- The durable log is the framework's **first long-running log**, and no rotation
  convention exists anywhere to copy (applink's `audit.py` states "no rotation"
  and justifies it by a threat model that does not apply to a minimonitor
  session). The per-session no-rewrite shape removes the append/trim loss race
  **by construction**, so the residual is no longer data loss but the *novelty*
  of the retention rule: it is the framework's first, and its liveness+age-floor
  guard is the only thing standing between it and deleting a live session's file
  · severity: medium ·
  → mitigation: inline post-phase review_loop_log_concurrency_proof
- Consolidating the three teardown paths is **not** purely mechanical: the two
  inline copies omit `_loop_shadow_settle_until = None`, so consolidation
  silently corrects a live divergence that no existing test covers. A correct
  change, but an invisible one · severity: medium ·
  → mitigation: inline pre-phase characterize_teardown_paths
- `_fire_shadow_recheck`'s tuple contract changes meaning (prose detail → reason
  code) while keeping its shape, so a stale caller compiles and misbehaves. The
  live-tmux smoke test calls it directly · severity: low · → mitigation: none
  (the type is unchanged; the two call sites are both edited in this task and
  the smoke test is in the named test set)
- Blast radius is bounded to the review-loop subsystem: 3 edited files, 1 new
  module, 2 edited test files, 1 doc · severity: low · → mitigation: none

### Goal-achievement risk: medium
- **The production cause is unconfirmed and was not reproducible synthetically.**
  This task therefore cannot demonstrate that it fixes the reported symptom — it
  can only make the next live occurrence diagnosable. If the true trigger lies
  outside the pre-Enter path, the loop still auto-disarms after this lands (with
  a correct reason, which is the point of Deliverable 1) · severity: high ·
  → mitigation: the Step 8c manual-verification follow-up (native to the
  workflow, not a risk-mitigation task — the t1525 precedent)
- The abort scope rests on a premise that is currently **inferred, not
  executable**: that `DIALOG`/`UNKNOWN`/`WORKING` all collapse to not-`True`
  through `_ready_from_state`, so an aborted delivery provably holds. A future
  detector or latch change could make `DIALOG` ready-`True` and turn the hold
  into the very spin the `READY` exclusion exists to prevent · severity: medium ·
  → mitigation: inline pre-phase pin_ambiguous_verdicts_hold
- Edge-triggering the hold suppresses repeats of the *same* reason. A sequence
  that flaps between two hold reasons would still toast every tick · severity:
  low · → mitigation: none (bounded: two reasons exist, and both are recorded)
- The durable record is written but has no reader, so "identifiable after the
  fact" would otherwise depend on the user knowing the path and having `jq`.
  Closed in-plan by Phase 1e · severity: medium ·
  → mitigation: inline post-phase review_loop_log_reader

### Planned mitigations
- timing: pre-phase | name: pin_ambiguous_verdicts_hold | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement risk 2 (the abort scope's "an aborted delivery provably holds" premise is inferred, not executable) | desc: Pin `_ready_from_state`'s four verdict mappings and drive a full-streak WAITING controller through each, asserting ACTION_NONE + holding_for_shadow for every not-True value and ACTION_FIRE only for True, so a future detector or latch change that makes DIALOG ready-True fails loudly instead of turning the hold into a spin.
- timing: pre-phase | name: characterize_teardown_paths | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 (consolidating the three teardowns silently corrects the two inline copies' missing settle-latch clear) | desc: Characterize all three disarm teardowns against today's code, explicitly pinning that the two inline branches leave `_loop_shadow_settle_until` set where the helper clears it, so Phase 1c flips a visible assertion rather than changing behaviour invisibly; label the flipped assertions characterization, not contract.
- timing: post-phase | name: review_loop_log_reader | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement risk 4 (the durable record is written but has no reader) | desc: Ship `ait minimonitor --loop-log [N]` — an argparse `__main__` in review_loop_log.py printing the last N events newest-first across all session files with each reason decoded through `loop_reason_message`, dispatched early in aitask_minimonitor.sh (before the textual/tmux checks and the single-instance guard, which reading a log must not inherit) and degrading to `(no review-loop events recorded)` the way `aitask_gate_log.sh` does for an absent sidecar. Specified concretely in Phase 1e; no new `ait` verb and no new script.
- timing: post-phase | name: review_loop_log_concurrency_proof | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (retention must never interleave with, or outrace, a live append) | desc: Drive the exact interleaving the rejected shared-ring/trim shape would have lost data on — two writers appending to their own session files while a third process runs retention — asserting zero lines lost, both live files still present, and only no-writer files removed; plus direct pins that retention refuses a live-pid file and refuses a file younger than the age floor even when liveness reports dead. The storage *shape* is decided in Phase 1d, not deferred; this is its proof.

**Reassessment after inlining** (`risk-evaluation.md` Step 3 note). Both levels
stay **medium**, but the composition changes and the scope grows:

- **Code-health** stays medium, but for a better reason than before. The
  append/trim loss race is not *mitigated* — it is **removed by construction**
  in Phase 1d (per-session files, active file never rewritten), so no data-loss
  residual ships at all. What keeps the level at medium is that the retention
  rule is novel to this framework and its liveness+age-floor guard is the only
  thing preventing deletion of a live session's file. Against that, inlining the
  reader means the task also owns a small CLI surface (one early dispatch line
  in `aitask_minimonitor.sh` plus an argparse `__main__`) it would not otherwise
  have touched. Net-neutral.
- **Goal-achievement** stays medium. The pre-phases convert two inferred
  premises into executable ones before any production edit, and the reader
  closes risk 4 — but the dominant risk is untouched: the production cause is
  still unconfirmed, and no mitigation here can change that. That is the risk
  that sets the level.
- **Effort.** The task is filed `effort: medium`; four inlined mitigations on top
  of three phases plausibly makes it high. Flagged, not adjusted — the frontmatter
  write happens post-approval at Step 7.

## Environment note

`agent-pick-1598` is live in this repo holding an uncommitted sync→async
migration of `minimonitor_app.py`. Per your decision this task runs in an
isolated worktree `aiwork/t1606_stop_spurious_review_loop_auto_disarm` cut from
`main`, so the two never share a working tree. The pending hunks do not overlap
the review-loop region, but t1598 may yet reach it; conflicts surface at the
Step 9 merge, which is where they belong.

---

## Implementation notes (2026-08-25)

All phases landed. Three commits on `aitask/t1606_stop_spurious_review_loop_auto_disarm`:
pre-phase mitigations, Phases 1–3, post-phase mitigations.

### Deviations from the approved plan

1. **The third teardown was dead code, and was deleted rather than
   consolidated** (user-approved mid-implementation). `_service_review_loop`
   only enters the latched-False replay block when `can_consume` is true, which
   forces `agent_present=True` *and* `shadow_present=True` into the replay
   `tick()` — while `tick()`'s only `ACTION_AUTO_DISARM` producer requires one
   of them to be `False`. Enumerated exhaustively: exactly one input
   combination reaches that call, and it returns `ACTION_NONE`.

   Consequences for the approved test list: there are **two** reachable
   teardowns, not three, so test 2's "four tick-originated combinations" is
   **two** ({`agent_gone`, `shadow_gone`} × the live branch), and the
   "missing settle-latch clear" was a live divergence in one branch. The
   deletion is guarded by `ReplayDisarmUnreachabilityTests`, which fails if
   `can_consume` is ever widened so the branch must come back.

2. **The concurrency proof was initially vacuous and had to be rebuilt.** The
   first version wrote its records as fast as it could, finished in ~20 ms, and
   the pruner never overlapped it — it passed because no race occurred. It now
   spreads the appends over ~1.2 s and carries two non-vacuity controls (the
   pruner's pass count, and seeded prunable files it must actually have
   removed). Its discriminating power was then **measured** rather than
   asserted, by building the rejected shared-ring shape and running the same
   workload through it: **119 of 120 records lost**, versus 0 for the shipped
   design. That number is recorded in the test docstring and in
   `shadow_agent.md`.

3. **`review_loop_log.py` and the reader shipped in the Phase 1–3 commit**, with
   the post-phase commit carrying their proof (`tests/test_review_loop_log.py`).
   This matches the revised plan, where Phase 1d/1e own the build and the
   post-phases own the evidence.

### Other notes

- `tests/test_minimonitor_concern_action.py`'s `_mk_app` bypasses `__init__` and
  hand-installs the loop attributes, so `_loop_hold_reason` had to be added
  there too — the fixture's existing documented convention.
- The reader's `read_events` needed an arrival-order tiebreak: `ts` is
  second-resolution, and a stable sort on `ts` alone returned same-second
  events **oldest**-first, the opposite of the promised order.

### Verification performed

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
- `shellcheck .aitask-scripts/aitask_minimonitor.sh` → only pre-existing SC1091
  informational notices on the four `source` lines.
- `ait minimonitor --loop-log` exercised end-to-end from a window that already
  hosts a minimonitor, proving the early dispatch clears the single-instance
  guard.
- All three planned negative controls run, each failing **exactly** the named
  tests and no others: removing the hold edge-trigger, routing the ambiguous
  verdicts back to a disarm, and dropping the settle-deadline clear.

**Worktree environment note.** A task worktree has no `aitasks/` / `aiplans/`
symlinks (task data lives on the `aitask-data` branch), which made four
unrelated suite modules fail with `FileNotFoundError` on
`aitasks/metadata/*.json`. Restoring the two symlinks — they are gitignored —
made all four pass and produced the clean suite verdict above. Worth knowing
before reading a worktree suite run as a regression.

## Post-Review Changes

### Change Request 1 (2026-08-25 18:5x)

- **Requested by user:** two Step-8 review findings, both verified as valid.
  1. *(blocking)* `_loop_hold` discarded `record_event`'s `False` result while
     `_loop_auto_disarm` surfaced `(not recorded)`. Since the DIALOG/UNKNOWN
     paths this task rerouted are **holds**, an unwritable store would leave
     the next occurrence with no durable diagnostic and no notice once the
     banner and toast faded.
  2. *(follow-up)* `_loop_event_context` emitted only
     `state`/`rounds_fired`/`session`/`window`/`project_root`, dropping
     `agent`, `shadow_agent` and `shadow_pane` from the schema approved in
     Phase 1d — and the implementation notes did not record the narrowing.

- **Changes made:**
  1. `_loop_hold` now captures the result and appends `(not recorded)` the way
     `_loop_auto_disarm` does. A hold that normally stays quiet (supersession)
     still reports a **failed** record — a broken diagnostic subsystem is a
     fault in its own right — and holds are edge-triggered, so it cannot
     repeat per tick. Two tests: an ambiguous read against an unwritable
     store, and a quiet hold against one.
  2. New `_note_loop_identity` / `_loop_identity` thread the followed/shadow
     pair through as **last-observed** values, updated incrementally as
     `_service_review_loop` learns them. Deliberately not re-queried at
     teardown: a fresh tmux lookup there could fail — or be the very thing
     that failed — and would replace the record with nothing. Pinned on an
     **emitted** record, plus a test that a tick which cannot re-resolve the
     shadow does not erase what the previous tick knew.

  Both carry negative controls that fail exactly their named tests.

- **Two test defects found while verifying, and fixed:**
  - The concurrency proof's **own instrumentation raced**: it reported the
    pruner's pass count via `write_text`, which truncates, so the test's read
    could catch the file empty and die on `int('')`. Reproduced under CPU
    load; now an atomic append — the same property the module under test
    relies on. Its newline escape also had to go, since the template literal
    consumed it before the child process saw it.
  - `tests/test_minimonitor_concern_smoke.py`'s two app fixtures construct via
    `__new__` and hand-install loop state, so they needed the new attributes.

- **Files affected:** `.aitask-scripts/monitor/minimonitor_app.py`,
  `aidocs/framework/shadow_agent.md`,
  `tests/test_minimonitor_concern_action.py`,
  `tests/test_minimonitor_concern_smoke.py`, `tests/test_review_loop_log.py`.

- **Verification:** `PYTHON SUITE: PASSED (runner=pytest, exit=0)`; the
  concurrency proof re-checked under sustained CPU load (3/3) and still fails
  against a shared-ring implementation.

### Change Request 2 (2026-08-25 19:0x)

- **Requested by user:** two further Step-8 review findings, both verified.
  1. `_loop_identity` was never cleared when a new lifecycle armed. Because
     `_note_loop_identity` only overwrites non-empty values — deliberately, so
     a tick that cannot re-resolve the shadow keeps the last known answer —
     that stickiness carried a stale pair **across** an `L`-`L` cycle. A
     re-arm onto a different followed/shadow pair followed by an immediate
     absence or a failed re-resolution would record the new agent beside the
     old shadow: a pair that never existed, contradicting the documented
     claim that each event names the pair it happened to.
  2. `prune()` kept `MAX_SESSION_FILES` files **that existed at startup**, and
     the starting session then created its own — so the store settled at 21,
     not the documented 20. Bounded and lossless, but the documented limit was
     wrong.

- **Changes made:**
  1. Arming now **clears and re-seeds** `_loop_identity` from the identities
     `action_toggle_review_loop` has already resolved and validated. Re-seeding
     rather than merely clearing matters: a first-tick teardown then still
     names the right pair instead of nothing. Cross-lifecycle test added,
     driving a real re-arm onto a different shadow pane and asserting the
     recorded event carries the **new** pair.
  2. `prune()` gained `reserve`, and `on_mount` passes `reserve=1` to hold a
     slot for the session about to start (its file does not exist at prune
     time, so it cannot be counted). `MAX_SESSION_FILES` is now a true cap on
     the steady state. Two tests: the cap holds once the new session writes,
     plus a control showing the store overshoots by one without the reserve.

- **Files affected:** `.aitask-scripts/monitor/minimonitor_app.py`,
  `.aitask-scripts/monitor/review_loop_log.py`,
  `aidocs/framework/shadow_agent.md`,
  `tests/test_minimonitor_concern_action.py`, `tests/test_review_loop_log.py`.

- **Verification:** `PYTHON SUITE: PASSED (runner=pytest, exit=0)`; both fixes
  carry negative controls that fail exactly their named tests.
