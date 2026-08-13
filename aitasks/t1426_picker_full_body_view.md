---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1037
followup_kind: risk_mitigation
created_at: 2026-08-05 11:40
updated_at: 2026-08-13 23:07
---

## Origin

Risk-mitigation ("after") follow-up for t1293, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement — only the lost lines became readable, not long parsed bodies:

> The inspect view shows the unrecovered lines and the raw block region, but the
> picker still never shows a concern's **full body** — the two-line row truncates
> it at every width, including 40. That is pre-existing and out of scope here,
> but it means "see what the shadow said" is only fully solved for the *lost*
> lines, not for long parsed ones · severity: low

## Goal

Give the concern picker a way to read a **focused concern's full body**.

`_ConcernRow` (`.aitask-scripts/monitor/monitor_shared.py`) renders a fixed-height
row — one line wide, two lines narrow — so a body longer than the row is silently
truncated at *every* width. Measured during t1293: at 40 columns a 43-character
body renders as `The picker drops the body`; at 24 columns as `The picker`. There
is no surface anywhere in either TUI that shows a concern body in full, so a user
deciding whether to forward a finding is choosing from a preview they cannot
expand.

t1293 added `ConcernBlockInspectModal` — a scrollable, `markup=False`, `q`/`Esc`
read-only viewer reachable with `u` — for the lines the parser *could not* use.
The natural shape here is to reuse that pattern for the focused row: a key in
`ConcernPickerModal` that opens the focused concern's full body (and its region,
priority, disposition and verdict). Reuse rather than fork — see t1293's
`action_inspect_unrecovered` for the modal-over-modal push that leaves the
picker's selection intact underneath.

Watch two contracts already pinned by tests:

- **`display_body()` on display surfaces, `.body` on the clipboard path.** The
  AST guard in `tests/test_concern_body_display_contract.py` scans the whole
  `monitor/` package and will surface any new `Concern.body` read as an
  unclassified key; a new display surface must read `display_body()` and be
  registered there (t1294).
- **`markup=False` (or `escape()`) on anything showing captured text.** A concern
  body can contain `[dim]`-style tokens or a bare `[/]`, which Rich would either
  consume or raise `MarkupError` on.

## Verification

- Render-level test asserting the full body reaches the composited screen for a
  body longer than the row at 40, 30 and 24 columns, with a negative control
  proving the row itself still truncates (otherwise the test is not measuring the
  new surface).
- A body containing `[/]` and `[dim]` renders literally and does not crash.
- The picker's selection survives opening and closing the body view.
- `tests/test_concern_body_display_contract.py` passes with the new surface
  registered under the DISPLAY role.
