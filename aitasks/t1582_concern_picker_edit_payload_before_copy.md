---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini, aitask_monitor, tui]
gates: [risk_evaluated]
anchor: 1037
created_at: 2026-08-24 13:16
updated_at: 2026-08-24 13:16
---

## Problem

The shadow-concern picker (`c` in minimonitor, and the same modal in the full
monitor) lets the user **select** which concerns to forward, and nothing more.
On confirm the selection is rendered to a fixed payload and copied to the
clipboard sight-unseen — the user never sees the text they are about to paste
into the code agent, and cannot touch it.

There is no way to:

- read the exact text that will be pasted before it is on the clipboard,
- trim a concern's body down to the part that actually matters,
- reword the preamble for this particular hand-off,
- add a sentence of the user's own context ("only the second one — the first is
  already handled in the plan"),
- delete one line without going back and un-ticking a row.

That last point is the shape of the gap: the picker's granularity is the
concern, but the thing being forwarded is **prose**, and prose wants an editor.

## Goal

Add a **review-and-edit step** between picking concerns and writing the
clipboard: a proper editor box showing the full outgoing payload, supporting
text selection, delete/overwrite of the selected text, and left/right/up/down
arrow navigation.

## Current flow (established during exploration)

1. `ConcernPickerModal` (`.aitask-scripts/monitor/monitor_shared.py:2982`) is
   **pure UI**: `space` = forward, `r` = reject, `t` = spin off, per row. On
   confirm it dismisses with a `ConcernPickResult`
   (`monitor_shared.py:2436`) — `forwarded` / `rejected` / `unrejected` /
   `spun_off` — and nothing else. It never builds a payload and never touches
   the clipboard, by an explicit documented contract.
2. The shared mixin `ShadowRejectionsMixin.apply_concern_pick_result`
   (`monitor_shared.py:999`) is where the copy happens:
   `build_clipboard_payload(result.forwarded)`
   (`concern_parser.py:760` — preamble, blank line, then one canonical
   `- [priority | region] body` line per concern) →
   `copy_to_system_clipboard` (`lib/tui_clipboard.py`).
3. Both `minimonitor_app.action_pick_concerns` (`minimonitor_app.py:3699`) and
   `monitor_app.py:3094` push the same modal and route the result through the
   same mixin — so one change serves both TUIs.

## Proposed shape

**Editor opens from inside the picker, over it — not after it.**
`action_inspect_unrecovered` (`u`) and `action_show_rejected` (`R`) already push
a modal over the *still-open* picker with a callback, so closing returns to an
intact selection. Bind `e` ("edit") the same way. `_ConcernRow.on_key` stops
only `space`/`↑`/`↓`, and App-level bindings do not dispatch under a
`ModalScreen`, so `e` is free in both apps (minimonitor's App-level `e` =
launch shadow is not reachable here).

**Seed the editor with a built string, never with `Concern` objects.** The
picker calls `build_clipboard_payload` on the currently-forwarded rows and
hands the resulting `str` to the editor. Two reasons, and the second is a hard
constraint:

- WYSIWYG — what is in the box is byte-for-byte what lands on the clipboard.
- `tests/test_concern_body_display_contract.py` is an AST guard over the whole
  `monitor/` package: a **DISPLAY** surface must never read `Concern.body` (or
  `c[2]`), only `display_body()`; the **FORWARD** path must read `.body`
  (the `Disposition:` / `Verified:` trailer is metadata the receiving agent
  needs). An editor that renders the forward payload is a display surface over
  forward text — the only way to be both is to receive an already-rendered
  string and register no new `Concern`-body read at all.

**Carry the edit on the result.** `ConcernPickResult` gains a
`payload_override: str | None` (default `None`).
`apply_concern_pick_result` copies the override when set, else
`build_clipboard_payload(result.forwarded)` exactly as today, so `Enter`
remains the unchanged zero-friction fast path and no caller that ignores the
new field changes behaviour.

**Widget: Textual `TextArea`** (Textual 8.2.7 is in use). It already provides
selection (shift+arrows and mouse), delete/overwrite of the selection,
`←→↑↓` navigation, and undo/redo — the whole ask, with no custom editing code.
Precedent to copy: `EditVerifyBuildScreen` (`.aitask-scripts/settings/settings_app.py:802`)
— `Esc` = cancel, an explicit Save action, `TextArea` + `Container` + buttons.

**Confirm cannot be `Enter`** — inside a `TextArea` that inserts a newline. Use
`ctrl+s` (plus a Save button where there is room), `Esc` to cancel back to the
picker with the override untouched.

## Decisions to settle during planning

- **Stale override.** If the user edits, then flips a row's disposition before
  confirming, the stored text no longer matches the selection. Pick one and pin
  it with a test: discard the override on any row-state change after the edit
  (simple, predictable, loses typing), or keep it and warn at confirm time.
  Discarding silently is not an option — the user must be able to tell which
  text was copied.
- **Empty buffer on confirm.** Decide whether an emptied editor means "copy
  nothing" or is refused; either way it must not silently fall back to the
  generated payload.
- **`e` with nothing forwarded.** Either refuse with a notify, or open on the
  bare preamble. Do not open an empty box with no explanation.

## Constraints

- **Forwarding only.** `rejected` / `spun_off` go through
  `concern_marker_line` into `aitask_shadow_rejected.sh` and the draft-task
  seam, and must be completely unaffected by an edit — the rejection store's
  entries are matched against fresh concerns by the shadow next round, so an
  edited line reaching the store would silently stop matching.
- **Narrow widths are real.** The picker runs in minimonitor's companion pane.
  It already has a measured extra-narrow tier (`_PICKER_NARROW_MIN_WIDTH = 30`,
  `monitor_shared.py:2723`) that hides OK/Cancel because the labels render as
  `Can` below ~34 columns. The editor needs its own width handling and must be
  fully usable at 24 columns with the keyboard alone — nothing half-drawn, and
  the help line must name `ctrl+s` / `Esc` at that tier.
- **Multi-App modal:** it lives in `monitor_shared.py` and is pushed by two
  Apps, so it carries its own `DEFAULT_CSS`
  (`aidocs/framework/tui_conventions.md`, "Modals pushed by multiple Apps").
- **Captured text is untrusted.** Concern bodies can contain `[dim]` or a bare
  `[/]`; a markup-enabled `Static` would eat the first and raise `MarkupError`
  on the second. `TextArea` is not markup-rendered, but any surrounding
  label/preview built from payload text must use `markup=False` or `escape()`.
- **Clipboard seam:** the write stays `copy_to_system_clipboard`, never
  `app.copy_to_clipboard` (`tests/test_tui_clipboard_seam.sh` enforces it).

## Contracts to amend in the same change

Both are currently-true statements that this change makes false, so they are
edited together with the code, not afterwards:

- `ConcernPickerModal`'s docstring: "The modal stays pure-UI: it does NOT build
  the clipboard payload…" — it will now build the payload *string* for display
  (still no clipboard write, still no I/O).
- The dismiss contract in the same docstring, which enumerates the result's
  fields.
- `ConcernPickResult`'s own docstring/field list.
- The picker help lines `_CONCERN_HELP_FULL` / `_CONCERN_HELP_COMPACT`
  (`monitor_shared.py:2730`) must name `e`; the compact variant is the only
  place keys are named at the extra-narrow tier.

## Verification

- Render-level tests at 80, 40, 30 and 24 columns: the editor renders intact
  (border on every row), the help names `ctrl+s`/`Esc` at every tier.
- Editing behaviour through the real widget: select a span, type over it, and
  assert the resulting `.text`; arrow navigation moves the cursor.
- End-to-end through the mixin: an override reaches
  `copy_to_system_clipboard` verbatim, with a **negative control** proving the
  un-edited path still copies `build_clipboard_payload(forwarded)` byte-for-byte.
- The rejection store and spin-off paths receive canonical
  `concern_marker_line` text on a run where the payload *was* edited.
- Cancelling the editor leaves the picker's selection and any prior override
  intact; the stale-override rule chosen above is pinned by a test that fails
  if the rule is dropped.
- `tests/test_concern_body_display_contract.py` still passes with **no new row**
  in `EXPECTED_ACCESSES` — if the editor forced a new `Concern`-body read, the
  string-seeding design was not followed.
- Existing suites stay green: `tests/test_concern_picker_modal.py`,
  `tests/test_minimonitor_concern_action.py`,
  `tests/test_monitor_concern_action.py`, `tests/test_tui_clipboard_seam.sh`.

## Related

- **t1426** (`picker_full_body_view`, same anchor 1037) — a read-only per-row
  full-body view for the *focused* row, including rows that are not being
  forwarded. Adjacent, deliberately not folded: it answers "what did the shadow
  actually say about this one", this task answers "what exactly am I about to
  send". They should stay consistent about where body text is rendered, and
  whichever lands second should reuse the first one's viewer chrome.
- t1293 introduced `ConcernBlockInspectModal` and the measured-width tier
  pattern this editor should follow.
- t1427_2 established the per-row-disposition model and the reasoning that no
  bulk key may be reintroduced — an editor is not a bulk key over dispositions,
  it operates only on the already-confirmed forward text.
