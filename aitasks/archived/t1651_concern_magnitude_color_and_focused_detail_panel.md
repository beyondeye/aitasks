---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [shadow, aitask_monitormini, aitask_monitor, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1664, 1665, 1667]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
implemented_with: claudecode/opus5
created_at: 2026-08-31 16:58
updated_at: 2026-09-01 15:36
completed_at: 2026-09-01 15:36
---

## Goal

The concern picker (`ConcernPickerModal` / `_ConcernRow` in
`.aitask-scripts/monitor/monitor_shared.py`, pushed by both `ait monitor` and
`ait minimonitor`) renders each vector-bearing concern's trade profile as
`▲robus ▼simpl E:md`. The **direction** of each impact is legible; its
**magnitude** is not. Two changes, on the same surface:

1. **Colour-encode magnitude** on the improve/worsen arrows.
2. **Show expanded information for the currently focused concern**, inline in
   the picker dialog — not in a modal over it.

## Current state

**Magnitude is weight-only.** `_magnitude_markup(arrow, magnitude)` returns
`[bold]▲[/]` for high, a bare `▲` for medium and `[dim]▲[/]` for low; an
unspecified magnitude gets a literal `?` character appended by `_entry_seg`
instead (`concern_dimensions.normalize_magnitude` refuses to degrade `""` to
`low`, deliberately). Bold-vs-plain-vs-dim on a single glyph is close to
unreadable in practice, which is the report that opened this task.

**Zero-cell styling is a contract, not an accident.** The docstring is explicit:
"the magnitude is carried by *style*, not by extra cells, which is what keeps
the packing bound independent of it." Colour honours that contract exactly —
any encoding that adds characters does not, and would invalidate the packing
derivation in `concern_dimensions.check_label_widths` and the geometry pinned by
`ConcernRowVectorPackingTests` / `ConcernTradeProfilePackingTests` /
`ConcernPickerWidthTierTests` (`tests/test_concern_picker_modal.py`).

**The row cannot show the whole vector anyway.** `trade_profile_rungs` is a
five-rung degradation ladder: it drops (1) the 2nd improve/worsen entry into
`+N`, (2) the `+N` markers, (3) the 2nd worsen entry, (4) the 3-space indent,
(5) the `?` unspecified markers. At minimonitor's ~28-cell row the surviving
line is `▲x ▼y E:z` — one improve, one worsen, the effort scalar. The region is
ellipsized by `_region_seg` and the body is hard-truncated to one row by
`render()` whenever the three-line layout is in play. So even a perfect colour
ramp leaves most of the vector invisible at the width where the picker is most
used.

## Part 1 — magnitude colour ramp

**The ramp must encode intensity, not direction.** Direction is already carried
by the glyph (`▲` / `▼`). A green-up / red-down scheme re-encodes the thing the
glyph already says and still leaves high/medium/low indistinguishable. Whatever
is chosen, `▲high` and `▼high` must read as *the same strength*, and
`▲high` vs `▲low` must read as *different strengths*.

Constraints to settle in the plan:

- **`_CONCERN_BADGE` already owns `bold red` (HIGH) / `bold yellow` (MED) /
  `dim` (LOW)** on the same row. Reusing that ramp for magnitudes is defensible
  (one vocabulary for "how much" across the dialog) but must be a deliberate
  decision, not a collision — the badge sits three cells to the left of the
  profile on the one-line layout.
- **Unspecified stays distinguishable.** `""` is not `low`; the `?` character
  carries it today and the ladder's last rung drops that character. If colour
  becomes the only carrier at the narrowest rung, "unspecified" must not collapse
  into a real magnitude's colour.
- **Rich colour names are not Textual colour names.** Rich `yellow` resolves to
  `#808000`, Textual's to `#FFFF00`; the profile is Rich markup rendered inside a
  Textual `Static`. Pin the actual rendered colour, not the name.
- Keep the ramp in one named mapping beside `_CONCERN_BADGE`, so there is a
  single site to retune.

## Part 2 — focused-concern detail panel (inline)

**Inline in the picker dialog, following focus** — explicitly *not* a
modal-over-modal. The panel updates as the user moves between rows with ↑/↓ and
shows, for the focused concern only, what the row had to drop.

Content (settle the exact set in the plan):

- Every improve and every worsen entry, with the **full** dimension name rather
  than the 5-cell short label, and its magnitude as a word.
  `concern_dimensions.rubric_for()` already returns a one-line rubric per
  dimension and is currently read by **no** display surface — this is the
  natural place for it.
- The effort scalar, and the disposition / verdict.
- The **un-ellipsized region** and the **untruncated body** — the row clips both.
- Ideally one or two lines of body, wrapped rather than hard-clipped.

Mechanism:

- `on_descendant_focus` is the established pattern in this codebase
  (`stats/stats_app.py:692`, `lib/section_viewer.py:342`,
  `brainstorm/brainstorm_app.py:716`, and both monitor apps). Use it rather than
  inventing a per-row message.
- **`Widget.focus()` is deferred** — a caveat already documented at
  `monitor/monitor_app.py:1505` and `minimonitor_app.py:1708`. The panel must be
  **seeded explicitly** in `on_mount` after `rows[0].focus()`; relying on the
  event to fire for the initial focus will leave the panel blank on open.

## Vertical space — the panel needs a rung on the existing ladder

`ConcernPickerModal` already has an explicit, one-directional precedence order
for vertical room, and a new panel must join it rather than sit outside it:

- OK/Cancel buttons are `display: none` at the `xnarrow` tier
  (`_PICKER_NARROW_MIN_WIDTH = 30`) because they are redundant with Enter/Esc.
- `_CONCERN_GUIDANCE` is gated by `_apply_guidance_visibility()` on
  `_GUIDANCE_MIN_WIDTH = 80` **and** `_GUIDANCE_MIN_HEIGHT = 24`, on the stated
  rule that "the help line's key names outrank the guidance" — the help line is
  the only place `r` / `t` / `R` / `u` / Esc are named once the buttons go.

An unconditional `yield` for the panel would evict the help line or the concern
list itself at 24x20. Decide and document where the panel sits in that order,
gate it from **measured** geometry in `_apply_size_tier` (never from the
`narrow` caller hint), and state what it costs the list's `min-height: 3`.

Also decide whether the panel is always-on or toggled by a key. If toggled: `i`
is taken by Task Info in both apps, and `u` / `e` / `R` / `space` / `r` / `t` are
taken in this modal; `_ConcernRow.on_key` stops only space/r/t/up/down, so any
other key bubbles to the modal.

## Contracts that already exist and must not be broken

- **`display_body()` on display surfaces, `.body` only on the clipboard path.**
  `tests/test_concern_body_display_contract.py` runs an AST scan over the whole
  `monitor/` package and will surface a new `Concern.body` read as an
  unclassified key; the new panel must read `display_body()` and be registered
  there under the DISPLAY role (t1294).
- **Escape or disable markup on anything showing captured text.** A concern body
  and its region are free text from a shadow agent; a bare `[` takes the whole
  modal down with `MarkupError` (t1636_4 fixed exactly this). Use
  `_escape_markup()` or `markup=False`.
- **Magnitude must not gain cells.** `check_label_widths.__doc__` derives
  `MAX_LABEL_CELLS = 5` from an *exact* 18-cell fit at the 24-column floor via
  the ladder's last two rungs. Any width change there is a re-derivation, not a
  tweak.
- **`_apply_size_tier` reads measured size, never `self._narrow`.**

## Verification

- Render-level assertions (`render().plain` / composited screen), at 80, 40, 30
  and 24 columns, that:
  - each magnitude produces a *distinct* rendered style for both `▲` and `▼`,
    and that `▲high` / `▼high` share a strength;
  - the unspecified state stays distinguishable from every real magnitude,
    including at the rung where `?` is dropped;
  - the panel shows a dimension the row's ladder dropped, and the full body for
    a body longer than the row — with a **negative control** proving the row
    itself still truncates, or the test is not measuring the new surface.
- The panel is populated on open (initial focus), not only after the first ↑/↓ —
  this is the deferred-`focus()` trap and needs its own test.
- The panel follows focus: moving down changes its contents to the new row's
  concern.
- A concern whose body/region contains `[/]` and `[dim]` renders literally and
  does not crash the modal.
- Existing packing suites still pass unchanged at every supported width, and the
  measured geometry table in `check_label_widths.__doc__` is still accurate.
- A legacy (vector-less) concern block renders exactly as it does today.

## Notes

- Both apps push this modal (`narrow=True` from minimonitor, `narrow=False` from
  the full monitor) — verify on both paths, not just one.
- This replaces the (now-deleted) t1426, which proposed a modal-over-modal
  full-body view; the inline panel subsumes that goal and settles the
  modal-vs-inline question in favour of inline, at the user's direction.
- The pre-existing risk t1426 was mitigating — from archived t1293,
  `risk_mitigation_tasks: [1426]` — is carried by this task instead.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T07:02:40Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-01T12:17:53Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-01T12:36:06Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:87801cdf36ed739e

> **✅ gate:risk_evaluated** run=2026-09-01T12:36:06Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1651/risk_evaluated_2026-09-01T12:36:06Z-risk_evaluated-a1.log`
