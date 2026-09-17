---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ait_brainstorm, tui, textual, modal_dismiss]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1830]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-09-16 11:22
updated_at: 2026-09-17 12:58
---

## Symptom (as reported)

In `ait brainstorm`, Operations wizard, **Explore** op, **step 3 of 4**
(Configure: Explore — the step with the editable Exploration Mandate):
pressing `H` opens the operation-help dialog; pressing `Esc` in that dialog
**crashed the TUI**. Observed on session `brainstorm-1812`, but nothing about
it is specific to that session.

## Root cause (proven)

`OperationHelpModal.action_close` — `.aitask-scripts/brainstorm/modals.py:1241-1242`:

```python
def action_close(self) -> None:
    self.dismiss(None)
```

There is **no check that this screen is still the active one**. Textual's
`Screen.dismiss` (textual 8.2.7, `textual/screen.py:2060`) unconditionally calls
`self.app.pop_screen()`, so every `Esc` that still dispatches to the now-stale
modal pops *whatever happens to be on top*:

| Esc | intended | actual |
|---|---|---|
| 1 | close the help dialog | closes the help dialog (correct) |
| 2 | wizard steps back to 2 of 4 | **pops the wizard itself** — all wizard config silently lost |
| 3 | wizard steps back to 1 of 4 | `pop_screen()` on a 1-deep stack → `ScreenStackError` → TUI dies |

Captured traceback (headless `App.run_test`, real 1812 session data):

```
File ".aitask-scripts/brainstorm/modals.py", line 1242, in action_close
    self.dismiss(None)
File "textual/screen.py", line 2060, in dismiss
    await_pop = self.app.pop_screen()
File "textual/app.py", line 3105, in pop_screen
    raise ScreenStackError(
        "Can't pop screen; there must be at least one screen on the stack")
textual.app.ScreenStackError: Can't pop screen; there must be at least one
screen on the stack
```

## Reproduction evidence

**Confirmed in the live TUI** (real `crew-brainstorm-1812`, tmux, 200x55): from
step 3 of 4, `H` then three rapid `Escape`s lands back on the **Browse** screen
with the wizard gone entirely — instead of stepping back to step 2. Reproduced
twice. That is the Esc#2 cascading pop.

**Confirmed headlessly**: calling `action_close()` three times raises the
`ScreenStackError` above; calling it twice leaves the app on the base `Screen`
(wizard destroyed).

Why it is intermittent: whether the third `Esc` finds an already-drained stack
depends on how terminal key dispatch interleaves with the awaited `pop_screen`.
In several live runs the cascade stopped harmlessly at the base screen; the
crash needs the third dispatch to land before the stack settles. Key-repeat
(holding `Esc`) makes it much more likely.

**Ruled out** (all clean with the help modal open, then `Esc`):
`_load_existing_session`, `_refresh_status_strip`, `_refresh_runtime`,
`_poll_explorers`, `notify`. The background explorer-poll race was the initial
hypothesis and is **not** the cause.

## Blast radius

`self.dismiss(` appears **360 times** across the TUIs with **zero**
screen-identity guards anywhere in `.aitask-scripts/`:

| file | sites |
|---|---|
| `board/aitask_board.py` | 89 |
| `brainstorm/modals.py` | 46 |
| `monitor/monitor_shared.py` | 40 |
| `settings/settings_app.py` | 37 |
| `chatlink/wizard.py` | 16 |
| `syncer/upgrade_screens.py` | 15 |
| `syncer/settings_screens.py` | 11 |
| others | ~106 |

`aitask_board.py` has a `_modal_is_active()` helper, but it gates *app-level
actions*, not dismissal — it does not protect any of these call sites.

Any modal reachable **on top of another modal** is exposed the same way. The
brainstorm wizard is such a stack (`ActionsWizardScreen` → `OperationHelpModal`),
which is why it surfaced here first.

## Goal

1. Fix `OperationHelpModal.action_close` so a stale `Esc` can neither pop the
   wizard nor empty the screen stack.
2. Introduce a **shared guarded-dismiss helper / convention** (e.g. a mixin or
   a `lib/` helper that no-ops when `self.app.screen is not self`), so the fix
   is enforced in source rather than repeated by hand — and document it in
   `aidocs/framework/tui_conventions.md` where modal authors will see it.
3. Audit and convert brainstorm's 46 dismiss sites.
4. Regression test pinning the `ScreenStackError` (a red proof that fails
   before the fix), plus a test that the wizard survives extra `Esc` presses
   with its step state intact.

Defer the remaining ~314 sites (board, monitor, settings, syncer, chatlink, …)
to a follow-up task — the shared helper from step 2 is the prerequisite.

## Related work (not folded — different defects)

- **t1450** `board_test_harness_and_modal_escape_result_gaps` — the board's
  `action_focus_board` closes any modal with a bare `self.screen.dismiss()`,
  **discarding the dismiss result**. Adjacent (same `dismiss` sloppiness, same
  `tui_conventions.md` doc target) but a different failure: result loss, not a
  cascading pop / stack error. Coordinate the `tui_conventions.md` edit so the
  two tasks do not write conflicting guidance.
- **t1350** `monitor_modal_binding_guard_audit` — App-level bindings not
  dispatching under a `ModalScreen`. Different mechanism; no overlap.

## Secondary defects found during this exploration

These were found on the same wizard step and are **in scope only if cheap**;
otherwise split them out as follow-ups.

1. **The `(H for details)` hint is wrong while typing.** On step 3, `Tab` lands
   focus in the Mandate `TextArea`, which swallows printable keys — `H` types a
   literal `H` into the mandate instead of opening the help dialog. Verified in
   the live TUI. The `w`/`l` preview toggles are deliberately scoped this way
   via `ActionsWizardScreen.check_action`
   (`.aitask-scripts/brainstorm/brainstorm_app.py:1289-1305`), but `H` carries
   an unconditional on-screen hint that the focused TextArea silently defeats.

2. **`Esc` at step 3 silently discards the typed mandate.**
   `ActionsWizardScreen.on_key` (`brainstorm_app.py:571-580`) steps back to
   `section_select` on `Esc`; `_render_wizard_step` rebuilds the step, so the
   typed Exploration Mandate is lost with no confirmation and is not restored
   when stepping forward again. Verified in the live TUI.

3. **Leaked 30s timer.** `_load_existing_session`
   (`brainstorm_app.py:3226`) does
   `self._status_refresh_timer = self.set_interval(30, self._refresh_runtime)`
   without stopping the previous timer. `_load_existing_session` is called
   again on every explorer/initializer apply, so each apply stacks another
   30-second interval timer for the life of the session.

## Verification

- Red proof first: a test that reproduces `ScreenStackError` from repeated
  `action_close()` on `OperationHelpModal`, failing before the fix.
- Live check in a real terminal: from step 3 of 4, `H` then 3-6 rapid `Escape`s
  must leave the wizard open and stepping back normally (2 of 4, then 1 of 4),
  never dropping to the Browse screen and never exiting.
- `bash tests/run_all_python_tests.sh --test-dir tests` for the brainstorm
  modules (read only the last `PYTHON SUITE:` line for the verdict).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T07:45:38Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-17T09:09:16Z status=pass attempt=1 type=human
