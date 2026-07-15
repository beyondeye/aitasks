---
Task: t1153_fix_agent_model_picker_narrow_truncation.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
---

# Plan: Make AgentModelPickerScreen narrow-aware (t1153)

## Context

The minimonitor `E` shadow-launch agent picker (added in t1152) pushes the
shared `AgentModelPickerScreen`, which is fixed at `width: 65%` and is **not**
narrow-aware. On a ~40-col minimonitor companion pane, option rows render
`"<agent>/<name>"` and the long `claudecode/` prefix (11 chars) eats the visible
width, clipping the claudecode model name (e.g. `opus4_8`). The picker is shared
by board / monitor / codebrowser / switcher, so the fix must be narrow-aware
**without regressing the wide hosts**.

The bug is pre-existing (not caused by t1152). The sibling `AgentCommandScreen`
already solved the identical problem with a `narrow` flag + `.narrow` CSS variant
(`agent_command_screen.py:274-325`, threaded via `narrow: bool = False` ctor arg
and `add_class("narrow")` in `compose`). This plan mirrors that proven pattern.

## Approach

Thread a `narrow` flag from the one caller that already knows it
(`AgentCommandScreen.action_change_agent`, which has `self._narrow`) into
`AgentModelPickerScreen`, and add a `.narrow` CSS variant that widens the dialog
to full width so the `<agent>/<name>` display fits. Keep the display format
uniform across all hosts (uniform identity) — the fix is width, not a divergent
per-host label layout. Default `narrow=False` keeps every existing caller
(board/monitor/codebrowser/switcher/settings/launch) unchanged.

## Changes

### 1. `.aitask-scripts/lib/agent_model_picker.py` — `AgentModelPickerScreen`

- **Constructor** (`__init__`, ~line 336): add `narrow: bool = False` param
  (last, keyword-defaulted so all existing positional callers are unaffected);
  store `self._narrow = narrow`.
- **`on_mount`** (~line 418): add the narrow class before `self._apply_mode(0)`:
  ```python
  if self._narrow:
      self.add_class("narrow")
  ```
  (The CSS selector will be `AgentModelPickerScreen.narrow #picker_dialog`, so
  the class must live on the screen — matching how `AgentCommandScreen` does it.)
- **`DEFAULT_CSS`** (~line 315): append a `.narrow` variant that widens the
  dialog and trims chrome so the longest `claudecode/<name>` row fits on ~40
  cols, mirroring `agent_command_screen.py:279-284`:
  ```css
  AgentModelPickerScreen.narrow #picker_dialog {
      width: 100%;
      min-width: 30;
      padding: 0 1;
      border: round $accent;
  }
  ```
  The default (non-narrow) `#picker_dialog { width: 65%; ... }` is untouched, so
  wide hosts are unchanged.

### 2. `.aitask-scripts/lib/agent_command_screen.py` — `action_change_agent` (~line 767)

Thread the flag the caller already holds into the pushed picker:
```python
picker = AgentModelPickerScreen(
    self.operation,
    current_agent,
    current_model,
    all_models=all_models,
    narrow=self._narrow,
)
```

### 3. Tests — `tests/test_agent_model_picker_narrow.py` (new)

Model the file on `tests/test_agent_command_dialog_narrow.py` (Textual `App`
host + `app.run_test(size=(40, 50))` Pilot). Three tests:

- **`test_narrow_class_applied`** — push `AgentModelPickerScreen(..., narrow=True)`
  at 40 cols; assert `"narrow" in app.screen.classes`.
- **`test_default_is_not_narrow`** — push with `narrow=False` (default) at 120
  cols; assert `"narrow" not in app.screen.classes`.
- **`test_claudecode_model_name_fits_narrow`** — the behavioral check. Construct
  the picker with `all_models={"claudecode": {"models": [{"name": "opus4_8"}]}}`,
  `operation="pick"`, `narrow=True`; switch to the **"all"** mode (index 2, which
  renders from the passed `all_models` rather than reading real JSON) via
  `action_next_list`; find the `FuzzyOption` whose `display_text ==
  "claudecode/opus4_8"` and assert its rendered region is wide enough to show the
  full `" >> claudecode/opus4_8"` string un-clipped, i.e.
  `option.region.width >= len(" >> claudecode/opus4_8")`. This distinguishes the
  fix (full-width narrow row fits) from the bug (65% width clips the name).

Also add a one-line threading assertion (either in the new file or by extending
the existing `test_agent_command_dialog_narrow.py`): after constructing
`AgentCommandScreen(narrow=True)` and invoking `action_change_agent()`, assert
the top screen is an `AgentModelPickerScreen` with `"narrow" in ...classes` —
proving the flag is actually threaded, not just accepted.

## Verification

- `python3 -m pytest tests/test_agent_model_picker_narrow.py tests/test_agent_model_picker.py tests/test_agent_command_dialog_narrow.py -v`
  — new + existing picker/narrow tests pass.
- `python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import agent_model_picker, agent_command_screen"`
  — modules import cleanly.
- Manual (optional, covered by follow-up manual-verification if offered): in a
  narrow minimonitor pane, trigger `E` → change agent, switch to a claudecode
  list, confirm the model name is fully visible.

## Risk

### Code-health risk: low
- Change is additive and opt-in: a new `narrow: bool = False` ctor param, one
  `.narrow` CSS block, and one threading line. The default `width: 65%` path is
  untouched, so all wide hosts (board/monitor/codebrowser/switcher/settings/
  launch) are unaffected. Mirrors the already-shipped `AgentCommandScreen.narrow`
  pattern. · severity: low · → mitigation: none needed
- Blast radius is small (2 source files + 1 new test); the shared picker is
  reached by many hosts but only the narrow behavior is new and only fires when
  `narrow=True`. · severity: low · → mitigation: covered by keeping default False
  + wide-host regression is implicitly guarded by the untouched 65% CSS.

### Goal-achievement risk: low
- Minor: at `width: 100%` on a ~40-col pane the dim `description` column may
  still truncate, but the task requirement is that the **model name** stays
  visible — the render test asserts exactly that (`region.width >=
  len(" >> claudecode/opus4_8")`). · severity: low · → mitigation: TBD (widen
  further / shorten prefix only if a later report shows the name still clips)

## Step 9 (Post-Implementation)

Profile 'fast' works on the current branch (no worktree merge). After review and
commit, run the declared `risk_evaluated` gate via the Step 9 orchestrator and
archive with `./.aitask-scripts/aitask_archive.sh 1153`.

## Post-Review Changes

### Change Request 1 (2026-07-15 18:45)
- **Requested by user:** During Step-8 review the user reported two further
  defects in the narrow minimonitor agent-picker/command UX (both in scope for
  this narrow-awareness task):
  1. The `AgentCommandScreen` spawned by minimonitor **Shift+E** cannot be
     canceled with **Esc**.
  2. In the narrow `AgentModelPickerScreen`, the "Shift+←/→ to switch" helper
     hint is not always visible (clipped off the right edge).
- **Changes made:**
  1. **Esc fix (structural, host-independent).** `AgentCommandScreen` had a
     `handle_escape()` method but no binding — it relied on the *host* app to
     delegate (board/codebrowser bind escape App-level with `priority=True` and
     call `screen.handle_escape()`; minimonitor has no escape binding at all, so
     Esc was dead). Added a **non-priority** screen-level
     `Binding("escape", "escape", …)` + `action_escape()` → `handle_escape()`.
     Priority App bindings in board/codebrowser still preempt it (no
     double-dismiss); minimonitor now cancels correctly.
  2. **Hint visibility fix.** In `_apply_mode`, when `self._narrow` the mode
     label and the `(Shift+←/→ to switch)` hint are separated by a newline
     (stacked on two lines) instead of two spaces, so the hint is never clipped.
     Wide hosts keep the inline single-line layout (no regression).
- **Files affected:** `.aitask-scripts/lib/agent_command_screen.py`,
  `.aitask-scripts/lib/agent_model_picker.py`,
  `tests/test_agent_model_picker_narrow.py` (added `test_switch_hint_*` and
  `AgentCommandScreenEscapeTests::test_escape_dismisses_on_non_delegating_host`).

## Final Implementation Notes

- **Actual work done:** Made `AgentModelPickerScreen` narrow-aware — added an
  opt-in `narrow: bool = False` ctor param, `add_class("narrow")` in `on_mount`,
  and an `AgentModelPickerScreen.narrow #picker_dialog { width: 100% … }` CSS
  variant; threaded `narrow=self._narrow` from
  `AgentCommandScreen.action_change_agent`. Plus two defects the user surfaced
  during review (both in the same narrow minimonitor UX): a host-independent Esc
  binding on `AgentCommandScreen`, and stacking the "Shift+←/→ to switch" hint
  onto its own line in narrow mode. New test file
  `tests/test_agent_model_picker_narrow.py` (6 tests) covers all three.
- **Deviations from plan:** None on the original narrow-width fix. Scope grew by
  two related defects (Esc cancel, hint clipping) reported in the Step-8 review;
  logged under Post-Review Changes → Change Request 1.
- **Issues encountered:** None. The `Label.render().plain` + `widget.region.width`
  render-level assertions distinguish fixed-vs-broken; verified as genuine
  negative controls (65% row width 20 < 22 needed; narrow 36 ≥ 22).
- **Key decisions:** Kept the option-row display format uniform across all hosts
  (fix is dialog width, not a divergent per-host label layout). Made the Esc
  binding **non-priority** so board/codebrowser `priority=True` App handlers
  still preempt it (no double-dismiss), while minimonitor — which has no escape
  binding at all — finally cancels.
- **Upstream defects identified:** None. (The Esc-cancel gap was a pre-existing
  `AgentCommandScreen` defect but it was fixed within this task, not deferred.)
