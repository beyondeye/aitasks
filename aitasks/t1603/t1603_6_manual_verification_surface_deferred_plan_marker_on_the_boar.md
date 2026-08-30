---
priority: medium
effort: medium
depends: [t1603_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1603_1, 1603_2, 1603_3, 1603_4, 1603_5]
anchor: 1595
followup_kind: manual_verification
created_at: 2026-08-30 13:32
updated_at: 2026-08-30 13:32
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1603_1] Seed a marker (`ait update --batch <n> --plan-approved-at now`), open `ait board`: the card reads `📋 Ready · Planned`.
- [ ] [t1603_1] A task WITHOUT the marker renders its status line exactly as before — compare against another card side by side.
- [ ] [t1603_1] Open that task's detail (enter): "Tracking & provenance" shows `Plan approved: <ts>` with the real timestamp.
- [ ] [t1603_1] Open an UNMARKED task's detail: there is no `Plan approved:` row at all (not a blank one).
- [ ] [t1603_1] Clear the marker (`--plan-approved-at ""`), refresh the board: the `· Planned` qualifier disappears.
- [ ] [t1603_1] A blocked task that still carries the marker shows `Planned` somewhere on the card (the badge is suppressed when blocked).
- [ ] [t1603_2] With a gates-recording profile, a task waiting on `docs_updated` is NOT described as "Agent can continue".
- [ ] [t1603_2] An `Implementing` task with no gate ledger and no plan file shows `implementing (unknown)` and NO progress fraction.
- [ ] [t1603_3] The in-flight view shows four lanes with "Planned" FIRST, then Needs your action / Agent can continue / Blocked.
- [ ] [t1603_3] A Planned card's ops hints offer `[p pick]` and DO NOT offer `[g resume]` — this is the routing constraint.
- [ ] [t1603_3] Every in-flight card carries a phase chip, including cards in the Planned lane.
- [ ] [t1603_3] The compact gate progress on a card is legible and does not wrap or overflow the 44-column lane.
- [ ] [t1603_3] Narrow the terminal below the measured threshold: the chosen behaviour (scroll / collapse / fold) happens and the view stays usable.
- [ ] [t1603_3] Resize to a wide terminal (>=176 cols): all four lanes are visible without horizontal scrolling.
- [ ] [t1603_4] Press enter on an in-flight card: the detail screen opens with a collapsed `Gates (<n>)` section after Risk.
- [ ] [t1603_4] Expand it: passed / skipped / failed / pending gates are visually distinguishable at a glance.
- [ ] [t1603_4] A task with a stale signature shows BOTH facts — that it passed AND that the signature no longer binds.
- [ ] [t1603_4] Filtered-by-profile gates appear last under an audit-only label and are not counted in the total.
- [ ] [t1603_4] Close the detail screen: focus returns to the card it was opened from, not to the top of the board.
- [ ] [t1603_4] A task with no gate ledger shows the derived phase and provenance, not an empty list or `0/0`.
- [ ] [t1603_5] The website reference renders (`cd website && ./serve.sh`) and the board page shows the Planned lane and phase documentation.
- [ ] [t1603_5] The lane titles, phase names and gate glyphs in the docs match what the running board actually displays.
- [ ] [cross] Arrow-key navigation through detail-screen fields still moves in a sensible order with the new Gates section present.
- [ ] [cross] The board's normal kanban view is unaffected — columns, cards, marks and follow-up glyphs all render as before.
