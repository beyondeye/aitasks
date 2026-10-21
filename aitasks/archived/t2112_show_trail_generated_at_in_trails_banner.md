---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [trails, tui, ui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 16:48
updated_at: 2026-10-21 19:01
completed_at: 2026-10-21 19:01
---

## Goal

Show when the active trail was generated in the `ait trails` header banner,
next to the selected trail's name. Right now you can't tell how old the trail
you are looking at is without opening the `s` selection modal.

## Current state (explored 2026-10-21)

- The only place the generation time appears is the trail-selection modal
  (`s`). Each row ends with the raw `generation.generated_at` string, dimmed,
  or `?` when it is absent (`TrailSelectItem.__init__`,
  `.aitask-scripts/board/board_trail_view.py:672`). The value is UTC ISO-8601
  as written by `/aitask-trail` (`date -u +%Y-%m-%dT%H:%M:%SZ`, see
  `.claude/skills/aitask-trail/SKILL.md.j2` "generation"). It is not converted
  to local time or shown as an age.
- The active-trail chrome never shows it. That covers the header banner, the
  tab strip (`trails_app.py` `TrailTabStrip` / `_refresh_trail_tabs`), the
  summary pane, and the `v` summary modal.
- The banner is `self.sub_title`, written only by
  `TrailScreenMixin._refresh_subtitle` (`board_trail_screen.py` ~803-852) via
  `_trail_banner(title, suffix, owner_note, depth_note)` (~724-767).
  `TrailsApp._refresh_subtitle` (`trails_app.py:617`) delegates to it when a
  trail is active. The board's By-Trail view (`aitask_board.py`, same mixin)
  renders the same banner, so it gets the change too. That is intended.
- `r` (local refresh) only re-projects and leaves `generated_at` unchanged.
  Only an agent refresh (`R` / `/aitask-trail`) rewrites it. After an agent
  refresh, the reload seam (`_on_trail_reload`) already funnels into
  `_refresh_subtitle`, so a new timestamp should appear without extra wiring.
  Verify this.

## Requirements

- Add a compact generation-time note to the banner, for example
  `· gen 10-20 14:03`. Display it in **local time**: parse the ISO-8601 `Z`
  value and convert it. Pick the exact format during planning; it has to stay
  short, because the header is a fixed-width budget.
- **Keep the freshness marker the last survivor.** `_trail_banner` sheds
  content from the widest rung down so that `(⚠ stale: N)` is never clipped
  (t1278). The new note must not push the marker out. Decide where it sits in
  the ladder, for example additive-if-it-fits like the depth note (t1505_1),
  shed before the title is elided, or something else. Write the rationale in
  the docstring the same way the depth note's is written.
- An absent, non-string, or unparseable `generated_at` renders **nothing**:
  no `?` and no raw string. The header must not echo arbitrary artifact
  strings (see `_trail_depth_note`'s docstring).
- The `trail unavailable` and no-doc banner branches stay unchanged.
- Optional, decide in planning: format the selection-modal row's `updated`
  field with the same local-time formatter so the two places agree.

## Tests

- Extend the banner tests in `tests/test_board_bytrail_view.py`:
  - note present at a wide width;
  - note shed (marker kept) at narrow widths, for each rung;
  - absent or malformed `generated_at` → banner byte-identical to today's.
- Use **independent expected strings**, not a second call to `_trail_banner`
  as the reference. That is the weakness t1514 records for the existing
  depth-note test.
- Run the `ait trails` live/pilot tests that cover the header
  (`tests/test_board_header_row_live.py` is in the serial carve-out).

## Notes

- Related but not folded in: t1514, which hardens the existing banner
  regression test.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T14:18:26Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-21T15:57:47Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-21T16:01:16Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:2b2ca3f3ddc346f9

> **✅ gate:risk_evaluated** run=2026-10-21T16:01:16Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2112/risk_evaluated_2026-10-21T16:01:16Z-risk_evaluated-a1.log`
