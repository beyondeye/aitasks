---
Task: t1279_fix_failed_verification_t1273_item5.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1279 — Opening-window debounce for the By-Trail `R` agent refresh

## Context

t1273 item #5 (manual verification of t1268) failed: in the board's By-Trail
view, pressing `R` twice in quick succession **launches a real agent without the
user ever reviewing the confirmation dialog**.

The first `R` runs `KanbanApp.action_trail_refresh_agent`
(`.aitask-scripts/board/aitask_board.py:5990`), which pushes an
`AgentCommandScreen`. That modal binds the same key to Run
(`.aitask-scripts/lib/agent_command_screen.py:339-340`), so the second `R` never
reaches the board's guard — it is consumed by the modal and **confirms the
dialog**, launching `/aitask-trail --refresh` into a new tmux window.

The footer half of the checklist item already passes (`R Agent Refresh`
correctly disappears while `_trail_launch_pending`); only "the second press is a
no-op" fails.

**Goal (deliberately narrow):** stop an accidental *immediate* double-tap from
silently launching the refresh, without permanently changing any dialog
shortcut. A short window after the dialog **becomes visible** swallows a repeat
of the launching key; once it elapses, `R → Run` behaves exactly as today.

Out of scope by decision: the same key-collision class exists at other
`AgentCommandScreen` push sites (`e` in codebrowser/switcher, `a` in codebrowser
history/syncer, `n` in create-task flows, `R` in monitor restart). This task
changes only the reported By-Trail refresh flow; the shared dialog's default
behaviour is unchanged for the other 16 call sites.

## Design

### Where the guard goes, and why it must be first in `on_key`

`AgentCommandScreen.on_key` (`agent_command_screen.py:1054`) already intercepts
`a/A u/U e/E` and the tmux keys with `event.prevent_default()`. It is the right
insertion point: in Textual 8.2.7 a screen-level `on_key` runs **strictly
before** binding dispatch — the key bubbles focused-widget → screen → App
(`message_pump.py:833`), and only then does `App._on_key` (`app.py:4341`) call
`_check_bindings`. `prevent_default()` sets `_no_default_action`, which makes
`_get_dispatch_methods` skip that private handler, so the `R → run` binding never
fires; `Screen._modal_binding_chain` (`screen.py:449`) truncates at the modal, so
the key does not fall through to the board's own `R` binding either.

The guard must be the **first statement** of `on_key`, above the existing
`isinstance(focused, (Input, Select, SelectOverlay)): return`. A collapsed
`Select` defines neither `_on_key` nor `check_consume_key`, so with the tmux
session/window `Select` focused the key still bubbles to the App and fires the
binding — a guard placed after that early-return is simply skipped. Probed
headlessly against a modal mirroring this one (host App also binding `R`):

| Focus state | Guard first | Guard after the early-return |
|---|---|---|
| nothing focused | suppressed | suppressed |
| `Button` focused | suppressed | suppressed |
| **`Select` focused** | **suppressed** | **`action_run` fires — hole** |
| `Input` focused | types `R`, nothing runs | types `R`, nothing runs |

Guard-first is safe for a focused `Input` for a non-obvious reason worth a
comment: `Input._on_key` (`_input.py:737-748`) calls `event.stop()` on printable
keys *before* bubbling, so the screen's `on_key` is never reached while a field
has focus. Verified — the character still lands in `#agent_cmd_input`.

### When the window starts — at first paint, not at construction

The UX promise is "a window after the dialog appears", so the clock must not
start at construction. `AgentCommandScreen.on_mount` (`:473`) does real work
before the dialog is usable: `_populate_tmux_tab()` (`:504`) calls
`get_tmux_sessions()` → a **tmux subprocess on the UI thread**
(`agent_launch_utils.py:269`), then window enumeration, `_refresh_agent_row()`
and `_refresh_profile_row()`. Because the event loop is single-threaded, the
second keypress is queued behind all of it, so a construction-stamped window can
already be expired by the time the user first sees the dialog.

Reproduced headlessly (fake clock, `on_mount` consuming 0.5 s):

| Stamp point | Fast mount | **Slow mount** |
|---|---|---|
| `__init__` | immediate `R` swallowed | **immediate `R` LAUNCHES** |
| end of `on_mount` | swallowed | swallowed |
| `call_after_refresh` (first paint) | swallowed | swallowed |

So: `self._opened_at: float | None = None` at construction, stamped from
`call_after_refresh` at the end of `on_mount`. **`None` means "not displayed
yet" and swallows the key**, which closes the pre-mount / pre-paint event gap and
fails in the safe direction (`r`, Enter and the Run button stay available even in
the pathological never-painted case).

### Key normalisation — remapped keys must actually be covered

`resolve_key` returns the **literal** a user typed into the shortcut editor,
while Textual's `event.key` and `BindingsMap` use the normalised name:
`_character_to_key("#") == "number_sign"`, `"[" → "left_square_bracket"`
(`textual/keys.py`; `Binding.make_bindings` applies it at `binding.py:150-156`,
and `Pilot._press_keys` does the same). A remap to any non-alphanumeric key would
therefore leave the guard silently comparing `"#"` against `"number_sign"` and
never firing. So the constructor normalises exactly as Textual does — single
characters through `_character_to_key`, multi-character names (`ctrl+r`, `f5`,
`escape`) passed through unchanged — and a test pins the resolver-form ==
event-form equivalence rather than assuming it.

### Why 0.3 s

The window only has to cover an *accidental burst*, not give the user time to
read. Terminal auto-repeat lands keys ~30–80 ms apart and a deliberate human
double-tap ~100–250 ms apart, so 300 ms covers the accident; a considered second
press (re-reaching for `R` after looking at the dialog) is well past it, and the
value stays far below the ~500 ms at which suppression would start feeling like a
dead key. The checklist item's own wording — "twice in quick succession" — is
the behaviour being fixed. `OPENING_DEBOUNCE_SECONDS` is a named module constant
so retuning is a one-line change, and live verification proves **both**
boundaries.

### What stays available throughout the window

Only the one configured key is suppressed, and only for the window. Unchanged at
all times: lowercase `r` (the case-pair alias → `action_run`), `Enter` on the
focused Run button (`Button` binds `enter → press`,
`textual/widgets/_button.py:297`), clicking Run, `escape`, and every other dialog
key. After the window elapses, the suppressed key runs normally too.

### Clock seam

Measured through a module-level seam so tests never sleep:

```python
# agent_command_screen.py, module level
OPENING_DEBOUNCE_SECONDS = 0.3

def _monotonic() -> float:
    """Indirection so tests can drive the opening-window debounce (t1279)."""
    return time.monotonic()
```

Tests patch `agent_command_screen._monotonic` with a fake they advance
explicitly.

## Changes

### 1. `.aitask-scripts/lib/agent_command_screen.py`

- Module level: `OPENING_DEBOUNCE_SECONDS = 0.3`, the `_monotonic()` seam, and
  `from textual.keys import _character_to_key`.
- `__init__`: new trailing keyword `debounce_key: str = ""` (empty ⇒ feature off,
  which is every existing call site), stored normalised:

  ```python
  # resolve_key() hands back the literal the user typed ("#"), but event.key
  # and BindingsMap use Textual's normalised name ("number_sign"). Mirror
  # Binding.make_bindings (binding.py:150-156) or a remapped key silently
  # never matches (t1279).
  self._debounce_key = (
      _character_to_key(debounce_key) if len(debounce_key) == 1 else debounce_key
  )
  self._opened_at: float | None = None   # stamped at first paint, see on_mount
  ```
- End of `on_mount` (`:502`): `self.call_after_refresh(self._stamp_opened)` with

  ```python
  def _stamp_opened(self) -> None:
      """Start the opening window when the dialog is actually on screen.

      NOT in __init__: on_mount runs get_tmux_sessions() (a subprocess on the
      UI thread), so a construction-stamped window can already be expired by
      the time the user first sees the dialog (t1279).
      """
      self._opened_at = _monotonic()
  ```
- Predicate:

  ```python
  def _in_opening_window(self, key: str) -> bool:
      """True while `key` is the launching key and the dialog is still new."""
      if not self._debounce_key or key != self._debounce_key:
          return False
      if self._opened_at is None:
          return True          # not painted yet — swallow (fail safe)
      return (_monotonic() - self._opened_at) < OPENING_DEBOUNCE_SECONDS
  ```
- First statement of `on_key` (`:1054`), above the isinstance early-return:

  ```python
  if self._in_opening_window(event.key):
      # An immediate repeat of the key that opened this dialog is swallowed
      # for OPENING_DEBOUNCE_SECONDS after it appears, so a double-tap cannot
      # confirm a dialog the user has not read yet (t1279). Time-limited on
      # purpose: after the window the key runs normally, and `r` / Enter / the
      # Run button work throughout. MUST stay above the Input/Select
      # early-return — a collapsed Select consumes nothing, so the key would
      # otherwise bubble to App._on_key and fire the binding. Typing is
      # unaffected because Input._on_key stops printable keys before they
      # reach this screen.
      event.stop()             # keep the event off the App entirely
      event.prevent_default()  # ...and suppress App._on_key -> _check_bindings
      return
  ```
- One line in the module docstring's host contract (`:11-25`) noting
  `debounce_key` is opt-in and defaults to off.

### 2. `.aitask-scripts/board/aitask_board.py`

- `_launch_trail(op_args, window_suffix, watch_handle="")` (`:7508`) gains
  `debounce_key: str = ""`, passed through to `AgentCommandScreen`.
- `action_trail_refresh_agent` (`:6003`) passes
  `debounce_key=resolve_key("board", "trail_refresh_agent", "R") or "R"`
  (`resolve_key` already imported at `:40`). `action_trail_task` (`:7506`) passes
  nothing — unchanged.
- One cross-reference comment noting that `_trail_launch_pending` (`:5735`,
  `:7593`) and this debounce cover **disjoint** windows — dialog-closed →
  baseline-in-flight vs. the dialog's first 300 ms — so neither is redundant and
  neither may be deleted as a duplicate of the other.

**Unchanged:** `check_action("trail_refresh_agent")`, `_trail_launch_pending`,
`refresh_bindings()`, the footer contract, and the artifact-version watch.

## Tests

All deterministic — no `sleep`. `agent_command_screen._monotonic` is patched with
a fake clock the test advances, and `agent_command_screen.is_tmux_available` is
patched so the tab layout is pinned rather than inherited from the machine.

### `tests/test_agent_command_open_debounce.py` (new) — the mechanism

`_DialogHost` pattern from `tests/test_agent_command_dialog_narrow.py:35-58` (a
plain `App` pushing the **real** `AgentCommandScreen`).

1. `debounce_key="R"`, clock not advanced → `press("R")` leaves the dialog open
   and the host's result callback never fires.
2. Advance the fake clock past `OPENING_DEBOUNCE_SECONDS` → `press("R")`
   dismisses with `"run"`. Pins that the guard is time-limited, not permanent.
3. **Pre-display gap** (the `__init__`-stamp regression): advance the fake clock
   by ≫ the window *before* the screen is painted — i.e. inside a patched
   `_populate_tmux_tab` that advances the clock, mirroring the real
   `get_tmux_sessions()` subprocess — then `press("R")` immediately after the
   first paint. Still swallowed. Against an `__init__`-stamped implementation
   this test fails (verified in the headless probe: the immediate `R` launches).
4. Available immediately, clock not advanced (three assertions): `press("r")`
   dismisses `"run"`; `Enter` on a focused `#btn_run_terminal` dismisses
   `"run"`; clicking `#btn_run_terminal` dismisses `"run"`.
5. **Remapped-key equivalence.** For each of `"R"`, `"#"` and `"ctrl+r"`:
   construct with that literal as `debounce_key`, press the same literal through
   the pilot, and assert (a) `screen._debounce_key` equals the `event.key`
   Textual actually delivered — captured by a test subclass whose `on_key`
   records `event.key` before delegating to `super()` — and (b) the press was
   swallowed. `"#"` is the discriminating case: it fails without
   `_character_to_key` normalisation (`"#"` vs `"number_sign"`).
6. `#tmux_session_select` focused, clock not advanced → `R` still suppressed.
   Fails if the guard is ever moved below the `Input`/`Select` early-return.
7. `#agent_cmd_input` focused → `press("R")` appends `R` to `Input.value` and
   runs nothing (pins the guard-first/typing interaction).
8. Default construction (no `debounce_key`) → `R` runs immediately. Regression
   guard proving the other 16 call sites are untouched.

### `tests/test_board_bytrail_view.py` — the reported regression

One new test class driving the real key path: real `KanbanApp`,
`_enter_synthetic_bytrail` (`:83`), the **real** `AgentCommandScreen` (not the
existing `FakeScreen` spy), with `resolve_dry_run_command` / `resolve_agent_string`
patched as in `_capture_launch` (`:1194`) and `run_dialog_command` /
`ab.launch_in_tmux` / `ab._trail_versions` / `_trail_baseline_worker` recorded as
in `_launch_env` (`:1203-1231`), plus the fake clock.

Both launch modes, because the failure differs:

- `is_tmux_available=False` → `action_run` → `run_terminal` → `run_dialog_command`;
- `is_tmux_available=True` with stubbed sessions/windows → `run_tmux` →
  `launch_in_tmux`. This is the worse failure (a background agent the user never
  saw) and the realistic one: the tmux tab is pre-selected whenever `$TMUX` is set
  (`agent_command_screen.py:495`).

For each mode: `await pilot.press("R", "R")` → after the first press
`app.screen` is an `AgentCommandScreen`; after the second it is **still** that
screen and nothing launched. Then advance the fake clock past the window and
press `R` once → exactly one launch, proving the dialog is not left crippled.
Plus one assertion that the board threads the resolver through normalisation:
with `ab.resolve_key` patched to return `"#"`, opening the dialog yields
`app.screen._debounce_key == "number_sign"`.

`pilot._press_keys` interleaves `wait_for_idle(0)` between keys, so a single
`press("R","R")` genuinely models the double-tap.

**Prove the harness can fail:** with the `on_key` guard removed, both modes must
fail with exactly one launch and the screen back on the board — i.e. reproduce
the task's Reproduction §2 verbatim.

`test_repeated_R_during_an_in_flight_baseline_launches_once` (`:1915`) stays
untouched — it calls the action directly and pins the complementary
`_trail_launch_pending` window.

### Verification commands

```bash
python3 tests/test_agent_command_open_debounce.py
python3 tests/test_board_bytrail_view.py
python3 tests/test_agent_command_dialog_narrow.py
python3 tests/test_board_dialog_run_dispatch.py
bash tests/run_all_python_tests.sh          # auto-discovers the new file
python3 -m pyflakes .aitask-scripts/lib/agent_command_screen.py \
    .aitask-scripts/board/aitask_board.py
```

Live re-verification of t1273 item #5 belongs in a manual-verification follow-up
at Step 8c, and must prove **both** boundaries in a real tmux board — the
headless pilot proves dispatch, not the terminal:

1. `R` `R` as fast as the terminal will send them → the dialog stays up and no
   `agent-trail-*` window is created;
2. `R`, pause visibly (~1 s), `R` → the agent launches normally.

## Risk

### Code-health risk: low
- A time-window guard is inherently approximate: a double-tap slower than 300 ms
  still confirms the dialog · severity: low · → mitigation: accepted by design —
  the goal is to stop an accidental *immediate* double-tap, not to gate the
  dialog; the window is a named constant and live verification pins both
  boundaries
- The guard's correctness depends on its **position** in `on_key`, which reads
  like a stylistic choice and could be "cleaned up" below the `Input`/`Select`
  early-return, silently re-opening the hole · severity: medium · → mitigation:
  test #6 (`Select` focused) fails on that move, plus the inline comment
- The stamp point is equally load-bearing and equally easy to "simplify" back
  into `__init__` · severity: medium · → mitigation: test #3 reproduces the
  slow-mount launch against an `__init__` stamp, plus the docstring on
  `_stamp_opened`
- Depends on Textual-internal dispatch ordering (bubble-then-bind) and on
  `_character_to_key` · severity: low · → mitigation: every test drives real
  dispatch through `pilot.press`, and test #5 pins the normalisation against the
  event form Textual actually delivers
- Blast radius is two files and one opt-in keyword defaulting to off; the other
  16 push sites are provably unaffected · severity: low · → mitigation: test #8

### Goal-achievement risk: low
- None material. The failure is reproduced, the mechanism is verified against the
  installed Textual across all four focus states and both stamp points, and the
  regression test drives the real key path end-to-end with the real dialog in
  both launch modes.

## Step 9 — Post-Implementation

Merge to the plan-header output branch, run the declared gates
(`risk_evaluated`), then archive via `./.aitask-scripts/aitask_archive.sh 1279`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in two source files.
  `agent_command_screen.py` gained `OPENING_DEBOUNCE_SECONDS = 0.3`, a
  `_monotonic()` clock seam, an opt-in `debounce_key` constructor argument
  normalised through `_character_to_key`, `_stamp_opened()` invoked via
  `call_after_refresh` at the end of `on_mount`, the `_in_opening_window()`
  predicate (`_opened_at is None` ⇒ swallow), and the guard as the first
  statement of `on_key`. `aitask_board.py`'s `_launch_trail` gained a
  `debounce_key` parameter forwarded to the dialog, and
  `action_trail_refresh_agent` passes
  `resolve_key("board", "trail_refresh_agent", "R")`. Tests: a new
  `tests/test_agent_command_open_debounce.py` (11 tests) and a new
  `RefreshDoubleTapTests` class in `tests/test_board_bytrail_view.py`
  (3 tests) driving the real dialog through `pilot.press`.

- **Deviations from plan:** None in scope or design. Two mechanical
  adjustments during implementation:
  1. Four pre-existing `_launch_trail` stub lambdas in
     `tests/test_board_bytrail_view.py` (:693, :954, :1957, :2020) had to
     accept `**_kw` — adding a parameter to `_launch_trail` broke them with
     `TypeError: unexpected keyword argument 'debounce_key'`. They assert on
     launch *arguments*, not on the signature, so tolerating extra kwargs is
     the right shape for those doubles.
  2. `test_typing_the_key_into_the_command_input_still_works` originally
     asserted `value == before + "R"`. Textual's `Input` selects-all on focus,
     so the keystroke *replaces* the command; the assertion now checks the
     character landed (`value.endswith("R")`) and that nothing ran.

- **Issues encountered:**
  1. **The first negative control passed** — mutating `_opened_at` to be
     stamped in `__init__` did not fail any test, because the
     `call_after_refresh(self._stamp_opened)` re-stamp still ran at first
     paint and masked it. A passing negative control proves nothing; the
     faithful control is `__init__`-stamp **plus** removing the repaint stamp,
     which then failed exactly
     `test_window_starts_at_first_paint_not_construction`. Recorded here
     because the same masking would hide a future regression in either half
     alone — a third control (stamp never fires) pins the other half via
     `test_key_runs_normally_after_the_window`.
  2. `.aitask-scripts/board/aitask_board.py` advanced under this session
     mid-task (commit `6164fbe0b`, t1278, the sibling verification fix),
     shifting every line reference in the plan by ~70. Re-read before editing;
     the change content was unaffected.
  3. A concurrent session is editing this shared checkout (monitor/, syncer/,
     the shadow skills, website docs). Only the four files owned by this task
     were staged, and each diff was inspected for foreign hunks first.

- **Key decisions:**
  - **Guard position is load-bearing, not stylistic.** It sits *above* the
    `isinstance(focused, (Input, Select, SelectOverlay))` early-return: a
    collapsed `Select` defines neither `_on_key` nor `check_consume_key`, so
    with the tmux session Select focused the key bubbles to `App._on_key` and
    fires `R -> run`. Verified: moving the guard below that return fails
    `test_suppressed_with_tmux_select_focused` and nothing else. Typing is
    unaffected because `Input._on_key` stops printable keys before they reach
    the screen.
  - **Stamp at first paint, not construction.** `on_mount` runs
    `get_tmux_sessions()`, a tmux subprocess on the single-threaded UI loop, so
    a construction-stamped window can already be expired when the dialog first
    appears. `_opened_at is None` (pre-paint) swallows the key, which fails in
    the safe direction — `r`, Enter and the Run button stay available.
  - **Normalise the key like Textual does.** `resolve_key()` returns the
    literal from the shortcut editor (`#`), while `event.key` and `BindingsMap`
    use `number_sign`; without `_character_to_key` a remapped key would
    silently never match.
  - **Opt-in per host.** `debounce_key` defaults to `""`, so the other 16
    `AgentCommandScreen` push sites are untouched (pinned by
    `test_default_construction_runs_the_key_immediately`).

- **Upstream defects identified:** None. The same key-collision class is
  reachable at other `AgentCommandScreen` push sites (`e` in
  codebrowser/switcher, `a` in codebrowser history/syncer, `n` in create-task
  flows, `R` in monitor restart), but that is a deliberate scope decision
  recorded in this plan's Context, not a separate pre-existing defect in
  another module.

### Verification run

All suites green with the framework interpreter
(`PYTHONPATH=.aitask-scripts/board:.aitask-scripts/lib`):

`test_agent_command_open_debounce` (11), `test_board_bytrail_view` (73),
`test_agent_command_dialog_narrow` (3), `test_agent_model_picker_narrow` (7),
`test_board_dialog_run_dispatch` (15), `test_board_work_report` (23),
`test_board_detail_nested_actions` (4),
`test_agent_command_dialog_default_session` (11),
`test_agent_command_dialog_empty_prompt` (2), `test_minimonitor_shadow_pick`
(8), `test_tui_switcher_agent_launch` (14), `test_shortcut_scopes` (10),
`test_shortcuts_mixin_live_remap` (6). `pyflakes` clean on both changed
modules (only pre-existing unused-import warnings).

**Harness-can-fail checks** (each mutation reverted in place, never via
`git checkout`):

| Mutation | Outcome |
|---|---|
| `on_key` guard disabled | 6 dialog tests fail; both board double-tap tests fail with the screen back on the board — the task's Reproduction §2 verbatim |
| stamp moved to `__init__` (repaint stamp kept) | **passed — not a valid control**, the repaint stamp masked it |
| stamp in `__init__` + repaint stamp removed | exactly `test_window_starts_at_first_paint_not_construction` fails |
| repaint stamp removed (never stamped) | exactly `test_key_runs_normally_after_the_window` fails |
| `_character_to_key` normalisation removed | `test_normalisation_of_stored_key` and the `#` subtest fail |
| guard moved below the Input/Select early-return | exactly `test_suppressed_with_tmux_select_focused` fails |

Live re-verification of t1273 item #5 in a real tmux board (fast `R` `R` →
nothing launches; `R`, pause, `R` → launches) is left to the
manual-verification follow-up — headless dispatch is not terminal proof.
