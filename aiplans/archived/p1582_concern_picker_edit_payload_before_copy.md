---
Task: t1582_concern_picker_edit_payload_before_copy.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1582 — Edit the concern payload before it reaches the clipboard

## Context

The shadow-concern picker (`c` in minimonitor and in the full monitor) lets the
user pick *which* concerns to forward, and nothing else. On confirm the picked
rows are rendered to a fixed payload and copied to the clipboard sight-unseen:
the user never reads the text they are about to paste into the code agent, and
cannot trim a concern's body, reword the preamble, add a line of their own
context, or delete one line without going back and un-ticking a row.

The picker's granularity is the *concern*; the thing being forwarded is *prose*.
This adds a review-and-edit step between the two: `e` opens a real editor over
the still-open picker, seeded with the exact outgoing payload, and the edited
text — not a regenerated one — is what lands on the clipboard.

## Decisions settled

| Question | Decision |
|---|---|
| Selection changed after an edit | **Discard the edit and warn.** At confirm, regenerate the payload from the current forward set and compare it to the string the editor was seeded with; on a mismatch drop the override, copy the regenerated payload, and fire a `warning` toast naming the discard. |
| Editor emptied, then `ctrl+s` | **Refuse to save.** An empty/whitespace-only buffer keeps the editor open with a `warning` toast. `Esc` still cancels. |
| `e` with nothing forwarded | **Refuse with a notify**, matching the modal's existing empty-case precedent (`u` → "Nothing unparsed in this block", `R` → "No previously rejected concerns for this task"). |

Consequence of the last two together: `payload_override` is **never** `""` and
never accompanies an empty `forwarded` list. The mixin is still written so it
would honour either, rather than depending on that invariant.

## Facts established during exploration (design load-bearing)

- **`e` is free inside the picker.** `minimonitor_app.py:802` and
  `monitor_app.py:506` bind `e` → `launch_shadow` without `priority=True`, and
  there is no `priority=True` binding anywhere in `.aitask-scripts/monitor/`, so
  neither dispatches under a pushed `ModalScreen`. `_ConcernRow.on_key`
  (`monitor_shared.py:2683`) stops only `space`/`r`/`t`/`up`/`down`, so `e`
  bubbles to the modal exactly as `R` and `u` already do.
- **`ctrl+s` and `escape` are not in `TextArea.BINDINGS`** (verified against the
  installed textual 8.2.7 — pinned `textual>=8.2.7,<9` at
  `aitask_setup.sh:29`). Both bubble to the screen; no `priority=True` needed.
  `shift+arrows` (selection), `←→↑↓` (navigation), `ctrl+z/y` (undo/redo) and
  `ctrl+x/c/v` **are** bound — the whole editing ask, with no custom code.
- **Seeding with a string keeps the AST guard silent.**
  `build_clipboard_payload` (`concern_parser.py:760`) delegates per-line
  rendering to `concern_marker_line` and reads no `Concern` body itself — which
  is why it has no row in `EXPECTED_ACCESSES`
  (`tests/test_concern_body_display_contract.py:109`). A modal that receives an
  already-rendered `str` adds no tracked access at all, so **no new
  `EXPECTED_ACCESSES` row** is needed. That is the acceptance signal the task
  names.
- **The width-tier mechanism** is `on_mount`/`on_resize` → `_apply_width_tier()`
  keying on `self.size.width <= _PICKER_NARROW_MIN_WIDTH` (30), setting the
  `xnarrow` class and swapping the help `Static` (`monitor_shared.py:3225-3252`).
  Textual has no media queries; this is the substitute.

---

## Implementation

All production changes are in `.aitask-scripts/monitor/monitor_shared.py` unless
stated.

### Pre-phase (risk mitigations)

**`help_budget_measured` — measure the 24-column help budget before choosing the
token wording.** `_CONCERN_HELP_COMPACT` is the only place keys are named at the
extra-narrow tier and its own docstring says *"shorten a token here rather than
widening the dialog if a future key stops fitting"*. Add `· e edit` to the
compact line **first**, then run

```bash
~/.aitask/venv/bin/python -m unittest \
  tests.test_concern_picker_modal.ConcernHelpLineBudgetTests \
  tests.test_concern_picker_modal.ConcernPickerNarrowLayoutTests
```

and take the wording from the result rather than from a guess:

1. `↑↓ move · spc fwd · r rej · t spin · e edit · R list · u raw · ↵ ok · esc` (73 cols).
2. If the 24×20 assertions fail, shorten two existing tokens — `↑↓ move`→`↑↓ nav`,
   `t spin`→`t spn` (71 cols) — never widen the dialog.
3. If it still fails, collapse the ` · ` separators to a single space.

Record which variant the measurement selected in a comment on the constant.

### 1. Extract the measured-width tier helper

`ConcernPickerModal._apply_width_tier` and the new editor need byte-identical
tier logic. Lift the body to a module-level function beside the picker and have
both call it — reuse rather than a second copy of the rule:

```python
def _apply_measured_width_tier(
    screen, threshold: int, help_id: str, full: str, compact: str
) -> None:
    """Set the ``xnarrow`` class and swap the help line from MEASURED width.

    Textual has no media queries, so every dialog that distinguishes 24 / 30 / 40
    columns re-runs this from ``on_mount`` and ``on_resize``. ``threshold`` is
    the *calling dialog's own* declared minimum — never a shared terminal tier
    (``tui_layout.terminal_tier`` bounds NARROW at 80 and answers True for every
    width these dialogs distinguish). See ``_PICKER_NARROW_MIN_WIDTH``.
    """
    xnarrow = screen.size.width <= threshold
    screen.set_class(xnarrow, "xnarrow")
    help_widgets = list(screen.query(f"#{help_id}"))
    if help_widgets:
        help_widgets[0].update(compact if xnarrow else full)
```

`ConcernPickerModal._apply_width_tier` becomes a one-line delegation keeping its
existing docstring (which explains *why* the rule exists). This is
behaviour-preserving; `ConcernPickerWidthTierTests` (`test_concern_picker_modal.py:797`,
four tests including the CSS drift guard and the `_PICKER_NARROW_MIN_WIDTH = 0`
negative control) is the regression guard.

### 2. New modal: `ConcernPayloadEditModal`

Placed next to `ConcernBlockInspectModal` / `RejectedStoreModal`. Carries its own
`DEFAULT_CSS` — it is pushed by two Apps (`aidocs/framework/tui_conventions.md:213`).

```python
_PAYLOAD_EDIT_NARROW_MIN_WIDTH = 30   # this dialog's own component floor

_PAYLOAD_EDIT_HELP_FULL = (
    "[dim]\\[ctrl+s] save  \\[Esc] cancel  \\[←→↑↓] move  "
    "\\[shift+arrows] select  \\[ctrl+z] undo[/]"
)
_PAYLOAD_EDIT_HELP_COMPACT = "[dim]^s save · esc cancel[/]"
```

- `BINDINGS`: `ctrl+s` → `action_save`, `escape` → `action_cancel`. Both
  `show=False` with a justifying comment — this modal composes no `Footer`; the
  in-dialog help line is the discoverability surface, exactly as the picker's is.
- `__init__(self, payload: str, narrow: bool = False)` — takes a **`str`**, never
  `Concern` objects. That is what makes the box byte-for-byte WYSIWYG and what
  keeps the AST guard silent. **Store both**: `self._payload = payload` and
  `self._narrow = narrow`.
- **Activate the `narrow` class explicitly.** `compose` opens with
  `if self._narrow: self.add_class("narrow")`, exactly as
  `ConcernPickerModal.compose` (`monitor_shared.py:3171`) and
  `TaskNumberInputModal` do. The constructor kwarg does nothing by itself, and
  `_apply_measured_width_tier` only ever sets/clears `xnarrow` — the two knobs
  are independent by design (`narrow` is the *caller's* host-role hint,
  `xnarrow` is derived from measured width). Without this line every
  `ConcernPayloadEditModal.narrow` rule is dormant and minimonitor's ~40-column
  companion pane gets the 70% base dialog instead of the intended 90%.
- `compose`: `Container(id="payload-edit-dialog")` holding a bold header
  (`"Edit payload"`), the editor, then `Static(_PAYLOAD_EDIT_HELP_FULL,
  id="payload-edit-help")` and a `Container(id="payload-edit-buttons")` with
  Save / Cancel buttons.
  ```python
  yield TextArea(
      self._payload,
      id="payload-edit-text",
      soft_wrap=True,          # long marker lines must be readable at 24 cols
      show_line_numbers=False, # line numbers cost ~4 of 20 usable columns
  )                            # language=None — the payload is prose, not code
  ```
- `action_save`: read `.text`; if `not text.strip()`, `self.app.notify("Editor is
  empty — nothing to copy. Esc to cancel, or type a payload.",
  severity="warning")` and **return without dismissing**. Otherwise
  `self.dismiss(text)` — the raw `.text`, not the stripped one, so what the user
  sees is what is copied.
- `action_cancel`: `self.dismiss(None)`. `None` is the sole cancel signal,
  mirroring the picker's own contract.
- **Both buttons dispatch to those same two actions** — a button that renders
  must work. The buttons are hidden only under `.xnarrow`, so at 40 and 80
  columns they are visible, clickable, and are the only affordance a mouse user
  has:
  ```python
  def on_button_pressed(self, event: Button.Pressed) -> None:
      # Routed to the ACTIONS, not to duplicated bodies: the empty-buffer
      # refusal must behave identically whether the user pressed ctrl+s or
      # clicked Save, and a second copy of that rule would be a place for the
      # two paths to drift.
      if event.button.id == "btn-payload-save":
          self.action_save()
      else:
          self.action_cancel()
  ```
  Same single-dispatcher shape as `ConcernPickerModal.on_button_pressed`
  (`monitor_shared.py:3334`). Note `action_save` may decline to dismiss — the
  click path inherits that for free, which is exactly why it delegates.
- `on_mount` / `on_resize` → `_apply_measured_width_tier(self,
  _PAYLOAD_EDIT_NARROW_MIN_WIDTH, "payload-edit-help", …)`.
- `DEFAULT_CSS` mirrors the picker's three tiers so the two dialogs agree at
  every width: base `width: 70%; max-height: 80%; border: thick $accent;
  padding: 1 2`, `.narrow` → `width: 90%; min-width: 30`, `.xnarrow` →
  `width: 100%; min-width: 0; max-height: 100%; padding: 0 1` plus
  `#payload-edit-buttons { display: none; }` (redundant with `ctrl+s`/`Esc`,
  which the compact help names). `#payload-edit-text { height: 1fr; min-height: 3; }`.
  `border: thick` is deliberately kept — an intact border on every row is what
  the layout tests assert against.
- **No markup-enabled widget ever renders payload text.** `TextArea` is not
  markup-rendered; the header and help are static literals. Nothing interpolates
  captured prose, so there is no `[dim]`-eaten / bare-`[/]`-raises surface.

### 3. `ConcernPickerModal` — open the editor, carry the result

**Two fields, two jobs — never one field doing both.** The user's edited text and
the canonical selection snapshot are separate state: the snapshot is what
staleness is measured against, so it must stay canonical even after the user has
overwritten every word of the payload.

```python
self._payload_override: str | None = None   # the user's text, verbatim
self._payload_seed: str = ""                # canonical build_clipboard_payload()
                                            # for the selection the edit was made
                                            # against — never the edited text
```

New binding `Binding("e", "edit_payload", "Edit payload", show=False)` and:

```python
def action_edit_payload(self) -> None:
    """Edit the outgoing payload, over the still-open picker.

    Same modal-over-modal shape as :meth:`action_inspect_unrecovered` — the
    picker is NOT dismissed, so cancelling returns to an intact selection.

    **Reopening resumes the user's own text**, not a regenerated payload: the
    editor is a place to iterate, and reseeding from the canonical build would
    silently throw the previous edit away the moment the user pressed ``e`` a
    second time to revise it.

    Seeded with a BUILT STRING, never with Concern objects: the box is then
    byte-for-byte what lands on the clipboard, and this surface registers no
    Concern-body read (tests/test_concern_body_display_contract.py).
    """
    forwarded = self._concerns_in_state("forward")
    if not forwarded:
        self.app.notify("Nothing marked for forwarding — press Space on a row first")
        return
    # Resolve BEFORE re-snapshotting: the comparison is against the seed the
    # existing override was made against.
    override = self._resolve_payload_override(on_confirm=False)
    self._payload_seed = build_clipboard_payload(forwarded)
    self.app.push_screen(
        ConcernPayloadEditModal(
            self._payload_seed if override is None else override,
            narrow=self._narrow,
        ),
        callback=self._on_payload_edited,
    )

def _on_payload_edited(self, text) -> None:
    """Store a saved edit; a cancel leaves any PRIOR override untouched."""
    if text is None:
        return
    self._payload_override = text
```

Staleness resolution — **one reader, both entry points**:

```python
def _resolve_payload_override(self, *, on_confirm: bool) -> str | None:
    """The saved edit if it still matches the selection; otherwise discard it.

    The single application of the settled stale rule, consulted by BOTH
    ``action_edit_payload`` (before reseeding) and ``_result()`` (before
    dismissing) — applying it in one place and forgetting the other is how the
    two would come to disagree about which text is live.

    A STATE comparison, not an event hook: rows own their own keys and stop them
    (``_ConcernRow.on_key``), so no route through ``set_state`` is observable
    from here — and a comparison also correctly KEEPS the edit when a row is
    toggled off and back on.

    Discards by CLEARING the field, so the warning fires exactly once even
    though two callers consult it.
    """
    if self._payload_override is None:
        return None
    if build_clipboard_payload(self._concerns_in_state("forward")) == self._payload_seed:
        return self._payload_override
    self._payload_override = None
    self.app.notify(
        "Selection changed after editing — copied the regenerated payload, "
        "your edit was discarded."
        if on_confirm
        else "Selection changed since your last edit — reopening on the "
             "current payload.",
        severity="warning",
    )
    return None
```

`_result()` gains `payload_override=self._resolve_payload_override(on_confirm=True)`.

### 4. `ConcernPickResult` — the new channel

```python
    payload_override: str | None = None   # user-edited payload, else None (t1582)
```

Docstring amendment must say **why this field takes a default while `spun_off`
deliberately does not**: `spun_off` is a disposition channel where a default
would let a stale construction site silently report "nothing to spin off";
`payload_override` is an *optional* override whose absence (`None`) is the
correct, meaningful reading for every existing caller — which is exactly what
keeps `Enter` the unchanged zero-friction fast path. Positional construction in
the three test files (`ConcernPickResult([], [], (), [])`) stays valid.

### 5. `ShadowRejectionsMixin.apply_concern_pick_result` (`monitor_shared.py:1014`)

Replace the `if result.forwarded:` gate with a payload-first form, so the mixin
honours whatever it is handed rather than depending on the modal's invariant:

```python
        payload = result.payload_override
        if payload is None and result.forwarded:
            payload = build_clipboard_payload(result.forwarded)
        if payload is not None:
            # copy_to_system_clipboard, never app.copy_to_clipboard: … (keep the
            # existing comment block verbatim — the seam rule is unchanged)
            copy_to_system_clipboard(self, payload)
            self.notify(
                "Edited payload copied to clipboard."
                if result.payload_override is not None
                else "Concerns copied to clipboard."
            )
```

Behaviour is identical to today when `payload_override is None`. The distinct
toast is what lets the user tell *which* text was copied.

`rejected` / `spun_off` are untouched: they still go through
`concern_marker_line` into `aitask_shadow_rejected.sh` and the draft-task seam,
so an edited payload can never reach the rejection store (whose entries the
shadow matches against fresh concerns next round).

### 6. Help lines

`_CONCERN_HELP_FULL` gains `\\[e] edit payload`; `_CONCERN_HELP_COMPACT` gains
the token chosen by the pre-phase measurement.

---

## Contracts to amend in the same change

These are currently-true statements the change makes false — edited with the
code, not afterwards:

1. **`ConcernPickerModal` docstring, "pure-UI" paragraph** — it now builds the
   payload *string* to seed the editor. Restate the contract as: still no
   clipboard write, no filesystem, no subprocess; the caller still owns the copy.
2. **Same docstring, dismiss contract** — it says *"a result whose **three**
   fields are all empty"*; that was already stale at four and becomes five. Name
   the fields and state that `payload_override=None` is the un-edited default.
3. **`ConcernPickResult` docstring / field list** — per §4.
4. **`_CONCERN_HELP_FULL` / `_CONCERN_HELP_COMPACT`** — per §6, plus the comment
   recording the measured wording.
5. **`aidocs/framework/shadow_agent.md:508-519`** ("TUI write path") — enumerates
   `ConcernPickResult`'s fields and lists the picker's staged keys. Add `e` and
   `payload_override`, and state that the edit affects the clipboard payload
   **only**.
6. **Website surfaces naming the picker keys** — four places, all currently
   complete lists that `e` would falsify:
   `website/content/docs/tuis/monitor/reference.md:35`,
   `website/content/docs/tuis/monitor/how-to.md:198,206`,
   `website/content/docs/tuis/minimonitor/how-to.md:188,350`. Add `e` to each key
   table / parenthetical, plus one short subsection in
   `minimonitor/how-to.md` ("Edit the payload before it is copied") covering the
   three settled decisions.

## Test-file hygiene (load-bearing for this change)

`tests/test_concern_picker_modal.py` has its `if __name__ == "__main__"` guard at
`:1369`, **above** `ConcernStaleTriStateTests` at `:1373` — the t1518 defect
documented at `tests/test_minimonitor_concern_action.py:3455`. Discovery runs are
unaffected, but `python3 tests/test_concern_picker_modal.py` silently skips every
class below it. Move the guard to the end of the file so the classes added here
actually run under a direct invocation.

---

## Tests

New classes in `tests/test_concern_picker_modal.py` (using the existing `_Host`
App, `_screen_rows` / `_flat_text` / `_clipped_rows` helpers and the two-`pause()`
idiom after any push/pop/resize):

**`ConcernPayloadEditAffordanceTests`**
- `e` with nothing forwarded → no screen pushed, notify text asserted.
- `e` with a forwarded row → `ConcernPayloadEditModal` pushed, picker not
  dismissed (`app.result is _Host._UNSET`), and `TextArea.text ==
  build_clipboard_payload(forwarded)` **byte-for-byte**.
- `Esc` in the editor → picker intact, focused row unchanged, ticks unchanged,
  `_payload_override is None`.
- `Esc` after a *previous* save → the prior override survives (cancel must not
  clear it).
- Empty buffer + `ctrl+s` → editor still on the stack, warning notify, no dismiss.

**`ConcernPayloadEditButtonTests`** — the click path, which no keyboard test can
stand in for (the buttons render at every width above `.xnarrow`):
- clicking `#btn-payload-save` (`await pilot.click("#btn-payload-save")`)
  dismisses with the current `.text` and sets `_payload_override`, exactly as
  `ctrl+s` does — asserted against the *same* expected string as the keyboard
  test, so the two paths cannot drift.
- clicking `#btn-payload-cancel` dismisses `None` and leaves the override alone.
- clicking Save on an **empty** buffer inherits the refusal: editor still on the
  stack, warning notify, no dismiss. This is the test that fails if
  `on_button_pressed` ever grows its own body instead of delegating.
- at `_PICKER_MIN_COLS` the buttons are absent from the composited screen
  (`display: none`), so the click path is not silently expected there.

**`ConcernPayloadReopenTests`** — the edit-then-revise loop:
- edit → save → `e` again → the `TextArea` shows **the user's text**, not
  `build_clipboard_payload(forwarded)`. Assert against both strings so the test
  states which one is wrong.
- edit → save → `e` → save again → the second edit is what confirm carries.
- edit → save → toggle a row → `e` → the stale override is dropped, the editor
  opens on the **current** canonical payload, and exactly one warning notify
  fired; confirming afterwards does **not** fire a second one.
- `_payload_seed` still equals `build_clipboard_payload(forwarded)` after a save
  — the direct pin that the snapshot field was never overwritten with edited
  text (the defect that makes staleness undetectable).

**`ConcernPayloadEditEditingTests`** — behaviour through the real widget:
- `shift+right`×N then typing replaces the selected span; assert the resulting
  `.text` exactly.
- `down`/`right` move the cursor (assert `cursor_location`), proving arrow
  navigation is live and not swallowed.
- `ctrl+s` and `escape` reach the screen while the `TextArea` has focus — the
  binding-availability check, pinned so a future Textual bump that binds either
  key fails here rather than in the field.

**`ConcernPayloadEditWidthTierTests`** — sweeping `(80, 40,
_PAYLOAD_EDIT_NARROW_MIN_WIDTH, _PICKER_MIN_COLS)` read from production
constants, per the established `_rows_at` pattern:
- `_clipped_rows(rows, width) == []` at every width (border intact on every row).
- the composited screen names `ctrl+s`/`^s` **and** `Esc`/`esc` at every width.
- **24×20, the real companion-pane geometry, as its own case** — not just 24×30.
  Height is what the help-budget argument is actually about, and the extra ten
  rows at 24×30 are exactly the slack that would hide a regression here; the
  existing suite already pins the picker at this size
  (`test_short_pane_keeps_the_row_and_the_help`). At 24×20 assert: no clipped
  rows, `^s` **and** `esc` both reach the composited screen, the `TextArea` is
  present with a non-zero height, it holds focus, and a typed character actually
  lands (`await pilot.press("x")` → `.text` changed) — i.e. the editor is
  *usable* there, not merely drawn. Runs after the pre-phase measurement, so a
  failure here means the help wording, not the layout.
- CSS drift guard: the `min-width:` in `DEFAULT_CSS` equals
  `_PAYLOAD_EDIT_NARROW_MIN_WIDTH`, mirroring
  `test_tier_threshold_is_derived_from_the_declared_min_width`.
- **The `narrow` class is actually applied**, and is independent of `xnarrow`
  — the assertion that keeps the `.narrow` CSS from being dormant:
  at 40 columns a modal opened from a `narrow=True` picker
  `has_class("narrow")` and **not** `has_class("xnarrow")`; opened from the
  full monitor (`narrow=False`) it has neither. Mirrors
  `test_tier_follows_width_not_the_narrow_flag`. Paired with a **rendered**
  consequence rather than a class-name-only check — at 40 columns the
  `narrow` dialog is measurably wider than the un-`narrow` one, so dropping
  `add_class` fails on geometry, not just on a string.
- **Negative control**, one mutation, mirroring `test_without_the_tier_the_narrow_widths_break`:
  patch `_PAYLOAD_EDIT_NARROW_MIN_WIDTH` to `0` and assert
  `_clipped_rows(rows_24, 24) != []`.
- `pilot.resize_terminal(24, 30)` re-applies the tier live.

**`ConcernPayloadStaleOverrideTests`** — the settled rule, pinned in **both**
directions so dropping either half fails:
- edit → confirm with the selection untouched → `result.payload_override` is the
  edited text.
- edit → toggle a row → confirm → `result.payload_override is None`, the
  discard warning is in `app.notifications` with `severity="warning"`.
- edit → toggle a row off **and back on** → override survives (the comparison is
  on payload text, not on a "touched" flag).
- un-rejecting an entry via `R` does not invalidate the override (it does not
  change `forwarded`).

Mixin-side, added **identically** to `tests/test_minimonitor_concern_action.py`
and `tests/test_monitor_concern_action.py` (both apps must agree; the existing
`_mk_app` spies on `copy_to_clipboard`, not `copy_to_system_clipboard`, so the
real seam runs):
- `_pick_result(...)` gains a `payload_override=None` parameter.
- an override reaches `app.spy_clipboard` **verbatim**, and the toast says
  "Edited".
- **negative control:** with `payload_override=None` the clipboard receives
  `build_clipboard_payload(forwarded)` byte-for-byte and the toast is the
  unchanged "Concerns copied to clipboard." — this is the test that fails if the
  override branch ever swallows the default path.
- on a run where the payload *was* edited, `_writes(app)` still shows the
  rejection store receiving canonical `concern_marker_line` text, and the
  spin-off drafts are unaffected.

## Verification

```bash
# 1. The AST guard — must pass with NO new EXPECTED_ACCESSES row.
~/.aitask/venv/bin/python -m unittest tests.test_concern_body_display_contract -v

# 2. The picker + both action suites + the parser.
~/.aitask/venv/bin/python -m unittest \
  tests.test_concern_picker_modal \
  tests.test_minimonitor_concern_action \
  tests.test_monitor_concern_action \
  tests.test_concern_parser -v

# 3. The clipboard seam (bash; must not run concurrently with the python suite).
bash tests/test_tui_clipboard_seam.sh

# 4. Whole python suite — read ONLY the last line for the verdict.
bash tests/run_all_python_tests.sh
```

Expected: `PYTHON SUITE: PASSED (runner=…, exit=0)` on the final stderr line, and
`ALL TESTS PASSED` from the seam script. Note `bash … | tail` discards the exit
status — use `set -o pipefail` or `${PIPESTATUS[0]}` if piping.

Manual smoke (the only surface tests cannot fully stand in for): `ait minimonitor`
in a ~40-column companion pane → follow an agent with a shadow → `c` → tick a
row → `e` → select a span with `shift+←/→`, type over it, `ctrl+s` → `Enter` →
paste and confirm the clipboard holds the edited text.

## Risk

### Code-health risk: low

- The `if result.forwarded:` gate in `apply_concern_pick_result` is a load-bearing
  branch on both TUIs' only clipboard path; restructuring it could silently
  change the un-edited case · severity: medium · → mitigation: the byte-for-byte
  negative control in both action suites, which fails if the default path is
  swallowed.
- `_CONCERN_HELP_COMPACT` is measured, not free text — adding a token can evict
  the help line at 24×20, the only place keys are named at that tier ·
  severity: low · → mitigation: inline pre-phase `help_budget_measured`.
- The override/seed split is the load-bearing invariant: `_payload_seed` must
  stay canonical (never the edited text) or staleness becomes undetectable, and
  the stale rule must be applied at *both* entry points (reopen and confirm) ·
  severity: medium · → mitigation: one reader
  (`_resolve_payload_override`) consulted by both call sites, plus
  `ConcernPayloadReopenTests`' direct pin that `_payload_seed ==
  build_clipboard_payload(forwarded)` after a save.
- Dormant CSS: `.narrow` rules that no code activates are invisible to a
  class-free reading of the stylesheet and would silently give the 40-column
  companion pane the wrong dialog width · severity: low · → mitigation: the
  explicit `add_class("narrow")` in `compose`, pinned by a **geometry**
  assertion (narrow dialog measurably wider at 40 columns) rather than a
  class-name check.
- A rendered control that does nothing: `#payload-edit-buttons` is visible at
  every width above `.xnarrow`, so a keyboard-only implementation leaves mouse
  users with a dead Save button · severity: medium · → mitigation:
  `on_button_pressed` delegates to the actions, and
  `ConcernPayloadEditButtonTests` asserts the click path against the same
  expected strings as the keyboard path, including the empty-buffer refusal.
- Lifting `_apply_width_tier` to a shared helper touches a method pinned by four
  existing tests, and the extraction was not asked for · severity: low ·
  → mitigation: the extraction is behaviour-preserving and
  `ConcernPickerWidthTierTests` (including its `_PICKER_NARROW_MIN_WIDTH = 0`
  negative control) is exactly the guard; the picker's method is kept as a
  delegating wrapper so no call site or docstring moves.

### Goal-achievement risk: low

- A `TextArea` inside a dialog at 24 columns may be technically intact but
  practically unusable (a 20-column editing surface), and a sweep run at a
  generous height would not show it · severity: medium · → mitigation:
  `soft_wrap=True` + `show_line_numbers=False`, and the dedicated **24×20** case
  asserting the editor has non-zero height, holds focus and accepts a typed
  character — usability, not just absence of clipping. The manual smoke remains
  the readability check no render test can make.
- The stale-override rule loses typing by design; a user who edits and then
  adjusts a tick gets a warning, not their text · severity: low ·
  → mitigation: none — this is the settled decision, and the warning toast is
  the required "tell them which text was copied" half.

### Planned mitigations
- timing: pre-phase | name: help_budget_measured | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the compact help line evicting itself at 24×20 | desc: add the `e` token, run the two 24-column budget/layout test classes, and take the final wording from the measurement rather than a guess | inline pre-phase help_budget_measured

## Post-implementation

Step 9 (Post-Implementation) handles cleanup, archival and the merge.

## Final Implementation Notes

- **Actual work done:** Implemented as planned. `ConcernPayloadEditModal`
  (`monitor_shared.py`, beside `ConcernBlockInspectModal`) with its own
  `DEFAULT_CSS`, three width tiers, `ctrl+s`/`Esc` bindings, Save/Cancel buttons
  delegating to those actions, and a `TextArea` seeded with a built string.
  `ConcernPickerModal` gained `e` → `action_edit_payload`, the
  `_payload_override` / `_payload_seed` pair, and the single stale reader
  `_resolve_payload_override(on_confirm=…)`. `ConcernPickResult` gained
  `payload_override: str | None = None`; `apply_concern_pick_result` became
  payload-first. `_apply_measured_width_tier` was extracted and both dialogs now
  call it. 38 tests added across three files; docs updated in
  `aidocs/framework/shadow_agent.md` and four website surfaces.

- **Deviations from plan:** None in approach. Three additions came out of
  in-flight review and were folded into the plan before coding:
  1. `on_button_pressed` **delegating to** `action_save`/`action_cancel` rather
     than duplicating them — the plan composed the buttons but never wired them,
     so at every width above `.xnarrow` a mouse user would have clicked a dead
     Save button while the keyboard-only tests passed.
  2. The `_payload_override` / `_payload_seed` split plus reseeding from the
     override. The first draft reseeded unconditionally from
     `build_clipboard_payload`, so a second `e` showed the regenerated payload
     and the next `ctrl+s` wrote it back over the user's work.
  3. A dedicated 24×**20** case. The original sweep ran at height 30, and 24×20
     is the actual companion-pane geometry the help-line budget is about.
  A fourth came from the Step-8 review: add `t` to the monitor reference's
  picker-key list, which had always omitted it and which this change made
  conspicuous by inserting `e` next to the gap.

- **Issues encountered:**
  - The `narrow` constructor kwarg is inert without an explicit
    `add_class("narrow")` in `compose` (`_apply_measured_width_tier` only owns
    `xnarrow`). Caught in review before coding; pinned by a **geometry**
    assertion rather than a class-name check, because `has_class("narrow")`
    would still pass with a broken or deleted CSS selector.
  - `tests/test_monitor_concern_action.py` carried the same misplaced
    `if __name__ == "__main__"` guard as `test_concern_picker_modal.py` (guard
    above later class definitions — the t1518 defect). Both were fixed by moving
    the guard to end-of-file, which was load-bearing here: without it a direct
    `python3 tests/…` run would silently skip the classes this task adds.

- **Key decisions:**
  - **Seed with a string, never `Concern` objects.** Confirmed empirically: the
    AST guard passes with **no new `EXPECTED_ACCESSES` row**, which was the
    task's stated acceptance signal.
  - **State comparison, not an event hook, for staleness.** Rows stop their own
    disposition keys, so `set_state` is unobservable from the picker; comparing
    the regenerated payload against the canonical seed is also the better rule,
    since toggling a row off and back on correctly preserves the edit.
  - **One reader for the stale rule**, consulted by both reopen and confirm, and
    discarding by *clearing* the field so the warning fires exactly once.
  - **Payload-first in the mixin.** `if result.forwarded:` became a check on the
    resolved payload, so the mixin honours what it is handed instead of
    depending on the picker's "an override always accompanies forwarded rows"
    invariant. Byte-identical behaviour whenever `payload_override is None`.
  - **Help wording chosen by measurement.** `· e edit` was added first and the
    24-column budget tests run before touching any other token; they passed, so
    no existing token was shortened. The new token was added to
    `ConcernHelpLineBudgetTests.COMPACT_TOKENS` — without that the constant
    could have grown while nothing asserted the key reached the screen.
  - **Verification beyond a green first run.** Every test guarding a review
    finding was mutation-probed: dropping `add_class("narrow")`, reseeding
    canonically, a button bypassing `action_save`, clobbering `_payload_seed`,
    and the mixin ignoring the override each produce a failure. Two of my own
    predictions were wrong and corrected: clobbering the seed makes staleness
    *over*-trigger (caught by the keep-direction test, not the discard one), and
    a mixin mutation is invisible to picker-side suites.
  - **Live 24×20 tmux render** in addition to the composited-strip tests: border
    intact on every row, `shift+Right` selection + typing replaced the span,
    `ctrl+s` returned to the picker with the tick intact.

- **Upstream defects identified:**
  - `tests/test_monitor_concern_action.py:1649` — the `__main__`
    guard sat above `_spin_concerns` and `MonitorSpinoffParityTests`, so a
    direct `python3 tests/test_monitor_concern_action.py` run silently skipped
    every class below it (the t1518 defect class). Fixed in this change because
    it was load-bearing for the tests added here.
  - `website/content/docs/tuis/monitor/reference.md:35` — the picker-key
    parenthetical had never listed `t` (spin off), although the full monitor
    pushes the same picker and `monitor/how-to.md:206` documents the key. Fixed
    in this change.

- **Not verified:** the end-to-end manual smoke against a **live shadow agent**
  (a real followed pane emitting a real concern block). The tmux render covers
  the geometry and the keyboard path with a synthetic host App, but not a real
  capture → parse → forward round trip.
