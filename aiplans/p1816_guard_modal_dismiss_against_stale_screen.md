---
Task: t1816_guard_modal_dismiss_against_stale_screen.md
Base branch: main
Output branch: main
---

# t1816 — Guard modal dismiss against a stale screen

## Context

`OperationHelpModal.action_close` (`.aitask-scripts/brainstorm/modals.py:1241`)
calls `self.dismiss(None)` with no check that the modal is still the active
screen. Textual 8.2.7 `Screen.dismiss` unconditionally calls
`self.app.pop_screen()`, which pops *whatever is on top*. A stale `Esc` still
dispatched to the already-closed help modal therefore pops the wizard beneath it
(config lost), and a third one empties the stack → `ScreenStackError` → TUI dies.
All 16 brainstorm screens share the same unguarded pattern (46 sites in
`modals.py`, 3 in `brainstorm_app.py`).

Verified while exploring: `ResultCallback.__call__` defers the callback via
`requester.call_next`, so a modal whose result callback dismisses the *parent*
(e.g. `InitSessionModal._on_picker_result`) runs after the child's pop — the
parent is the top screen then, so an "only dismiss when active" guard does not
break that legitimate pattern. No brainstorm code dismisses a screen other than
`self`, and none calls `pop_screen` directly.

## Approach

Enforce the guard **in the base class**, not per call site: override `dismiss`
in a shared mixin so every existing and future `self.dismiss(...)` in a converted
screen is protected with zero call-site edits. "Converting" a site = switching its
class base.

### 1. Red proof first — `tests/test_brainstorm_guarded_dismiss.py` (new)

Written and run **before** any source edit; the wizard test must fail with
`ScreenStackError`.

Reuse the `_WizardHost` / `_make_session` harness shape from
`tests/test_brainstorm_wizard_nav_consolidation.py:150-195` (copied locally —
test modules do not import each other).

- `test_help_close_repeated_keeps_wizard` (**red proof**): host with
  `has_sections=True` → wizard at `section_select`; advance to `config` with
  `screen._render_wizard_step(next_step_id(screen._wizard_ctx(), "section_select"))`;
  record `_wizard_step` / `_wizard_step_id`; `screen.action_op_help()`; pause;
  assert `app.screen` is an `OperationHelpModal`; call `help.action_close()`
  three times (pause between) — simulates stale dispatch. Assert no exception,
  `app.screen is wizard`, step id still `config`, step number unchanged,
  `app.is_running`.
- `test_escape_after_help_steps_wizard_back`: same setup, open help, then
  `pilot.press("escape")` → help closed, wizard on `config`; `escape` again →
  wizard on `section_select` (normal step-back still works).
- `test_active_dismiss_delivers_result`: minimal App pushing a
  `GuardedModalScreen` with a callback; `dismiss("x")` → callback got `"x"`,
  screen popped.
- `test_inactive_dismiss_is_noop`: push guarded A then guarded B;
  `A.dismiss("a")` → B still top, A still on stack, A's callback not called;
  returned object is awaitable (`AwaitComplete`).
- `test_unguarded_control_still_raises`: negative control — plain `ModalScreen`,
  dismiss 3× on a 2-deep stack raises `ScreenStackError`. Pins that the guard is
  still needed; if a Textual upgrade adds its own guard this fails and says so.
- `test_brainstorm_screens_are_guarded` (source enforcement): `ast`-scan every
  `.aitask-scripts/brainstorm/*.py`; fail on any `ClassDef` whose direct base is
  the name `ModalScreen` or `Screen` (must be `GuardedModalScreen`). Also import
  `brainstorm.modals` / `brainstorm.brainstorm_app` and assert every `Screen`
  subclass defined there `issubclass(..., GuardedDismissMixin)`.
- `test_status_refresh_timer_not_stacked`: see step 4.

Tests use the file-free `unittest` + `asyncio.run(...)` pattern of the existing
wizard tests (no subshells, so no counter opt-in concerns).

### 2. Shared helper — `.aitask-scripts/lib/guarded_dismiss.py` (new)

```python
"""Guarded Screen.dismiss: never pop a screen that is not the active one (t1816)."""
from textual._context import NoActiveAppError
from textual.app import ScreenStackError
from textual.await_complete import AwaitComplete
from textual.screen import ModalScreen

def is_active_screen(screen) -> bool:
    # Only the two documented "there is no active screen" states count as
    # inactive: no app in context (NoActiveAppError, from MessagePump.app) and an
    # empty stack during shutdown (ScreenStackError, from App.screen). Anything
    # else — UnknownModeError, an app-side bug — propagates, so a real fault is
    # never disguised as "the dialog would not close".
    try:
        return screen.app.screen is screen
    except (NoActiveAppError, ScreenStackError):
        return False

class GuardedDismissMixin:
    """Mix in BEFORE the Screen base. Textual's dismiss() pops whatever screen is
    on top; a stale key still dispatched to an already-closed modal would pop
    the screen beneath it. Dismissing an inactive screen is a no-op (logged when
    an app is reachable). Like Textual's dismiss, it must be called with an
    event loop running."""
    def dismiss(self, result=None):
        # Resolve the app once, outside is_active_screen: `self.log` is
        # `self.app._logger`, so logging from a detached screen would re-raise
        # the very NoActiveAppError we just classified as "inactive".
        try:
            app = self.app
        except NoActiveAppError:
            return AwaitComplete.nothing()     # detached: nothing to pop, nowhere to log
        try:
            active = app.screen is self
        except ScreenStackError:
            active = False                     # empty stack during shutdown
        if not active:
            app.log.warning(f"guarded dismiss ignored: {self!r} is not the active screen")
            return AwaitComplete.nothing()
        return super().dismiss(result)

class GuardedModalScreen(GuardedDismissMixin, ModalScreen):
    """ModalScreen whose dismiss() is a no-op unless it is the active screen."""
```

(`lib/` is already on brainstorm's import path — `modals.py` imports
`launch_modes` bare.) `NoActiveAppError` is not re-exported publicly in textual
8.2.7 (`textual.app` lacks it), hence the `textual._context` import; the
exception-scope unit tests below pin it so a Textual upgrade that moves it fails
loudly at import.

Extra unit tests in `tests/test_brainstorm_guarded_dismiss.py` for the narrowed
catch:
- `test_detached_dismiss_is_safe_noop`: inside `asyncio.run(...)` but with no
  App, `GuardedModalScreen().dismiss("x")` must not raise and must return an
  `AwaitComplete` whose `is_done` is `True` and which can be awaited. (Verified
  while planning: logging via `screen.log` on a detached screen raises
  `NoActiveAppError`, which is why `dismiss` logs through the resolved `app`
  only.) The test runs inside a running loop on purpose.
  `AwaitComplete.nothing()` calls `asyncio.gather`, so it needs an event loop,
  exactly like Textual's own `dismiss`. Calling `dismiss` with no loop at all is
  outside the contract, and the docstring says so.
- `test_stale_dismiss_logs_via_app`: in the two-screen stack test above, patch
  `app.log.warning` (or capture `app._logger`) and assert that one warning is
  emitted for the inactive dismiss.
- `test_is_active_screen_false_without_app`: a detached `GuardedModalScreen()`
  (never pushed, no app context) → `is_active_screen` returns `False`.
- `test_is_active_screen_propagates_unexpected_errors`: a stand-in object whose
  `.app` property raises `RuntimeError("boom")` / `UnknownModeError` →
  `is_active_screen` re-raises (asserted with `assertRaises`), proving
  unrelated faults are not converted to a no-op.

### 3. Convert brainstorm screens

- `.aitask-scripts/brainstorm/modals.py`: `from guarded_dismiss import GuardedModalScreen`;
  change all 15 `class X(ModalScreen)` bases to `GuardedModalScreen`
  (`NodeHub(NodeDetailModal)` inherits it). Drop the `ModalScreen` import if unused.
- `.aitask-scripts/brainstorm/brainstorm_app.py:457`:
  `class ActionsWizardScreen(RowNavMixin, GuardedModalScreen)`; check the
  `ModalScreen` import is still needed elsewhere in the file (keep if so).
- Audit each of the 49 `self.dismiss(` sites while converting: confirm each is a
  self-dismiss from the screen's own action / button / key / deferred callback.
  Any site that dismisses while intentionally not on top would now no-op — none
  found in exploration; re-confirm and record the audit result in the Final
  Implementation Notes.

### 4. Secondary defect 3 (cheap) — leaked 30s timer

`brainstorm_app.py:3226`: extract `_restart_status_refresh_timer()`:
stop the existing `self._status_refresh_timer` if not `None`, then assign the new
`set_interval(30, self._refresh_runtime)`; call it from `_load_existing_session`.
The helper reads the attribute directly (no `getattr` default): `__init__`
already initializes it to `None` (`brainstorm_app.py:2122`), so a missing
attribute is a construction bug that should raise, not be masked.

Test `test_status_refresh_timer_not_stacked`: `app = BrainstormApp.__new__(BrainstormApp)`,
then **explicitly `app._status_refresh_timer = None`** (mirroring `__init__`,
which `__new__` bypasses), and stub `app.set_interval` to return a fresh fake
timer (with a `stop()` call counter) per call. Call
`_restart_status_refresh_timer()` twice → the first fake's `stop()` count is 1,
the second's is 0, and `app._status_refresh_timer` is the second fake. A third
assertion covers the first call: starting from `None` it stops nothing and does
not raise.

Secondary defects 1 (`H` hint swallowed by the focused Mandate TextArea) and
2 (`Esc` at step 3 discards the typed mandate) are **not cheap** (key-scope /
state-preservation design) → recorded as upstream defects for Step 8b follow-up
tasks.

### 5. Document — `aidocs/framework/tui_conventions.md`

New section **"Modal dismissal: subclass `GuardedModalScreen`, never bare
`ModalScreen`"**, placed just before "Modals pushed by multiple Apps must carry
their own DEFAULT_CSS": the stale-`Esc` cascade and `ScreenStackError`
mechanism, the rule (new modals derive from `lib/guarded_dismiss.GuardedModalScreen`,
or mix in `GuardedDismissMixin` before another Screen base), that the guard lives
in the base class so call sites stay plain `self.dismiss(...)`, the brainstorm
AST enforcement test, and that other TUIs are not yet converted (follow-up).
Scope it to *stale pops only*; state that dismiss-**result** semantics on Escape
are t1450's section, so the two do not conflict (and offer a note to t1450 at
Step 8e).

### 6. Follow-up for the remaining ~314 sites

Board, monitor, settings, syncer, chatlink, and other TUIs → one follow-up task
(see Planned mitigations). The helper from step 2 is its prerequisite.

### Post-phase (risk mitigations)

1. [audit_dismiss_while_covered] Grep `.aitask-scripts/brainstorm/` for every
   path that can reach `dismiss(` off the screen's own direct input: bodies of
   `@work` workers, `set_timer` / `set_interval` / `call_later` /
   `call_after_refresh` callbacks, and `push_screen(..., callback=...)` result
   handlers. For each, confirm the dismissing screen is the top screen at call
   time (result callbacks run via `call_next` after the child pops). List the
   findings in the Final Implementation Notes. Add
   `test_parent_dismiss_from_child_result_callback` to
   `tests/test_brainstorm_guarded_dismiss.py`: minimal host pushes
   `InitSessionModal`, then its `ImportProposalFilePicker` (via `on_import`),
   then the picker's `dismiss("/tmp/x.md")`. After the pauses, assert the
   InitSessionModal callback received `"import:/tmp/x.md"`, with only the base
   screen left on the stack. This proves the deferred-callback close still works
   under the guard.

## Verification

- Step 1 red proof: `~/.aitask/venv/bin/python -m pytest tests/test_brainstorm_guarded_dismiss.py`
  fails with `ScreenStackError` before steps 2–3; passes after.
- Brainstorm modules: `~/.aitask/venv/bin/python -m pytest -n 4 --dist loadfile tests/test_brainstorm_*.py`
- Full suite: `bash tests/run_all_python_tests.sh` — verdict from the final
  `PYTHON SUITE:` line only (no pipe, or `pipefail`).
- Live check (manual, offered at Step 8c): real `ait brainstorm` session, explore
  wizard step 3 of 4, `H` then 3–6 rapid `Escape`s → wizard stays open, steps back
  2 of 4 then 1 of 4; never drops to Browse, never exits.

## Step 9

Current-branch mode: no merge; post-implementation runs the gate orchestrator
(`risk_evaluated`) and archives via `aitask_archive.sh 1816`.

## Risk

### Code-health risk: low
- Overriding `dismiss` changes behavior for all 16 brainstorm screens at once; a dismiss issued while a child screen is legitimately on top (e.g. a worker/timer-driven close) would now silently no-op instead of popping. Exploration found no such site, and the no-op is logged, but a missed one would present as "dialog won't close" · severity: low (residual — addressed by inline post-phase audit_dismiss_while_covered) · → mitigation: inline post-phase audit_dismiss_while_covered
- The ~314 sites in other TUIs remain unguarded after this task, so the convention is enforced only in brainstorm · severity: low · → mitigation: guard_dismiss_remaining_tuis

### Goal-achievement risk: low
- The red proof simulates stale dispatch by calling `action_close()` directly rather than reproducing the terminal key-dispatch interleaving, so the live `H`+rapid-`Esc` check stays manual · severity: low · → mitigation: none (manual verification offered at Step 8c)

### Planned mitigations
- timing: after | name: guard_dismiss_remaining_tuis | type: bug | priority: medium | effort: high | inline_risk: high | added_complexity: high | addresses: code-health — other TUIs' ~314 dismiss sites stay unguarded | desc: Convert board/monitor/settings/syncer/chatlink/other TUI screens to lib/guarded_dismiss.GuardedModalScreen and extend the AST enforcement test to their directories
- timing: post-phase | name: audit_dismiss_while_covered | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a legitimate covered-screen dismiss silently no-ops | desc: Audit worker/timer/callback dismiss paths in brainstorm and pin the child-result-callback parent dismiss with a pilot test

## Post-Review Changes

### Change Request 1 (2026-09-17 10:05)
- **Requested by user:** Brainstorm modals still push unguarded overlays — `lib/section_viewer.SectionViewerScreen` (bare `dismiss`) and `diffviewer.DiffViewerScreen` (direct `app.pop_screen()` in `action_back`), which itself pushes an unguarded `SummaryScreen`. A stale close on those pops the newly guarded brainstorm parent, since a parent's guard cannot intercept a child's pop. Convert the reachable overlays and add stacked-overlay regression tests.
- **Verified:** confirmed by reading the close paths; a mutant run (guard disabled in memory) makes all three new overlay tests fail (`ScreenStackError` ×2, wrong top screen ×1).
- **Changes made:** `SectionViewerScreen` → `GuardedModalScreen`; `DiffViewerScreen` / `MergeScreen` / `PlanManagerScreen` → `GuardedDismissMixin, Screen`; `SummaryScreen` / `SaveMergeDialog` / `DiffLaunchDialog` → `GuardedModalScreen` (whole `diffviewer/` package, so the scan covers a complete directory); `DiffViewerScreen.action_back` now `self.dismiss()` instead of `self.app.pop_screen()`. diffviewer modules import `guarded_dismiss` with the existing `plan_browser.py` try/`sys.path` fallback. Tests: enforcement scan widened to `diffviewer/*.py` + `lib/section_viewer.py`, accepts `GuardedDismissMixin`-mixed bases, and gains a no-direct-`pop_screen()` check; new `StackedOverlayTests` (section viewer ×3 close, diff viewer ×3 back, summary ×3 close over the diff viewer). Doc section extended with the no-`pop_screen` and guard-every-overlay rules.
- **Files affected:** `.aitask-scripts/lib/section_viewer.py`, `.aitask-scripts/diffviewer/diff_viewer_screen.py`, `.aitask-scripts/diffviewer/merge_screen.py`, `.aitask-scripts/diffviewer/plan_manager_screen.py`, `tests/test_brainstorm_guarded_dismiss.py`, `aidocs/framework/tui_conventions.md`
- **Still out of scope (follow-up guard_dismiss_remaining_tuis):** shared `lib/` screens reachable via app-level mixins (`TuiSwitcherOverlay`, `ShortcutEditorModal`, `StaleEntryModal`, agent pickers, …) and the other TUIs.

## Final Implementation Notes
- **Actual work done:** New `.aitask-scripts/lib/guarded_dismiss.py` (`is_active_screen`, `GuardedDismissMixin`, `GuardedModalScreen`) overriding `dismiss` so an inactive screen's dismiss is a no-op (no pop, no callback, warning logged via the resolved app). All 15 `brainstorm/modals.py` modals and `ActionsWizardScreen` converted by base class — call sites unchanged. Post-review: the overlays brainstorm pushes (`lib/section_viewer.SectionViewerScreen`, all `diffviewer/` screens) converted too, and `DiffViewerScreen.action_back` uses `self.dismiss()` instead of `app.pop_screen()`. Secondary defect 3 fixed: `_restart_status_refresh_timer()` stops the previous 30s interval before starting a new one. `aidocs/framework/tui_conventions.md` gained "Modal dismissal: subclass `GuardedModalScreen`, never bare `ModalScreen`". `tests/test_brainstorm_guarded_dismiss.py` (16 tests): wizard red proof (failed with `ScreenStackError` before the fix), Esc step-back, helper contract (active/inactive/detached/exception scope/negative control), parent dismiss from a child result callback, stacked-overlay tests, source enforcement (unguarded screen bases, direct `pop_screen`), timer test.
- **Deviations from plan:** Scope widened per Change Request 1 (section viewer + diffviewer package). The log-capture test swaps `app._logger` because `Logger.warning` is a read-only property.
- **Issues encountered:** Planning review caught two latent faults in the drafted helper — a blanket `except Exception` would have disguised real faults as "dialog won't close", and `screen.log` resolves via `screen.app`, so logging on the detached path re-raised `NoActiveAppError`. `AwaitComplete.nothing()` needs a running event loop (same as Textual's own `dismiss`); documented in the mixin docstring.
- **Key decisions:** Guard in the base class rather than per call site (enforced in source, zero call-site edits). Catch only `NoActiveAppError` / `ScreenStackError`. The diffviewer modules import `guarded_dismiss` with the existing `plan_browser.py` try/`sys.path` fallback. Audit (post-phase `audit_dismiss_while_covered`): all 49 brainstorm `self.dismiss(` sites run from the screen's own key/action/button handlers except `InitSessionModal._on_picker_result`, a `push_screen` result callback — Textual runs it via `call_next` after the child pops, pinned by `test_parent_dismiss_from_child_result_callback`. The one `@work` in `modals.py` (`OperationDetailScreen`) does not dismiss; no timer/`call_later` path dismisses. Mutant check (guard disabled in memory): wizard red proof and all three overlay tests fail.
- **Upstream defects identified:**
  - `.aitask-scripts/brainstorm/brainstorm_app.py:1290 — the wizard's "(H for details)" op-help hint is wrong on the explore config step: Tab focuses the Mandate TextArea, which swallows printable keys, so H types a literal H instead of opening help (check_action scopes w/l this way but H keeps an unconditional hint)`
  - `.aitask-scripts/brainstorm/brainstorm_app.py:574 — Esc on the explore config step (step 3 of 4) steps back via _render_wizard_step, which rebuilds the step and silently discards the typed Exploration Mandate with no confirmation and no restore on stepping forward`
