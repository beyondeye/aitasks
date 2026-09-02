---
priority: medium
effort: medium
depends: [t1603_5]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t1603_1, t1603_2, t1603_3, t1603_4, t1603_5]
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: manual_verification
created_at: 2026-08-30 13:32
updated_at: 2026-09-02 10:42
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1603_1] Seed a marker (`ait update --batch <n> --plan-approved-at now`), open `ait board`: the card reads `📋 Ready · Planned`. — PASS 2026-09-02 10:35 auto: live board in tmux; 'ait update --batch 9002 --plan-approved-at now' then refresh -> card reads '📋 Ready · Planned'
- [x] [t1603_1] A task WITHOUT the marker renders its status line exactly as before — compare against another card side by side. — PASS 2026-09-02 10:35 auto: unmarked t9001 renders '📋 Ready' side by side with marked t9002 in the same column
- [x] [t1603_1] Open that task's detail (enter): "Tracking & provenance" shows `Plan approved: <ts>` with the real timestamp. — PASS 2026-09-02 10:35 auto: detail 'Tracking & provenance (1)' expands to 'Plan approved: 2026-08-25 10:24'
- [x] [t1603_1] Open an UNMARKED task's detail: there is no `Plan approved:` row at all (not a blank one). — PASS 2026-09-02 10:35 auto: unmarked task detail has no Tracking & provenance section at all -- no blank row
- [x] [t1603_1] Clear the marker (`--plan-approved-at ""`), refresh the board: the `· Planned` qualifier disappears. — PASS 2026-09-02 10:35 auto: 'ait update --batch 9001 --plan-approved-at ""' + refresh -> '· Planned' gone, card reads '📋 Ready'
- [x] [t1603_1] A blocked task that still carries the marker shows `Planned` somewhere on the card (the badge is suppressed when blocked). — PASS 2026-09-02 10:35 auto: blocked+marked card renders '🚫 blocked | 📋 Planned'
- [x] [t1603_2] With a gates-recording profile, a task waiting on `docs_updated` is NOT described as "Agent can continue". — PASS 2026-09-02 10:35 auto: fast profile (record_gates); t9004 pending docs_updated lands in 'Needs your action', copy 'needs an attended agent: docs_updated'
- [x] [t1603_2] An `Implementing` task with no gate ledger and no plan file shows `implementing (unknown)` and NO progress fraction. — PASS 2026-09-02 10:35 auto: card chip 'implementing' with no fraction; detail Gates row 'No gate ledger -- implementing (unknown)'
- [x] [t1603_3] The in-flight view shows four lanes with "Planned" FIRST, then Needs your action / Agent can continue / Blocked. — PASS 2026-09-02 10:35 auto: lanes render Planned (1) | Needs your action (3) | Agent can continue (2) | Blocked (2), Planned first
- [x] [t1603_3] A Planned card's ops hints offer `[p pick]` and DO NOT offer `[g resume]` — this is the routing constraint. — PASS 2026-09-02 10:35 auto: Planned card t9002 shows '[p pick]' only; no '[g resume]'
- [x] [t1603_3] Every in-flight card carries a phase chip, including cards in the Planned lane. — PASS 2026-09-02 10:35 auto: every card carries a chip incl. Planned lane ('plan approved'); others 'needs attended agent · 1/2', 'awaiting review · 2/4', 'implementing · 2/2', 'implementing · 0/1'
- [x] [t1603_3] The compact gate progress on a card is legible and does not wrap or overflow the 44-column lane. — PASS 2026-09-02 10:42 auto: widest chip observed 'needs attended agent · 1/2' (26 cols) inside a 40-col card in the 44-col lane; no wrap, no overflow at 200/180/100 cols
- [x] [t1603_3] Narrow the terminal below the measured threshold: the chosen behaviour (scroll / collapse / fold) happens and the view stays usable. — PASS 2026-09-02 10:42 auto: at 100 cols the container horizontally SCROLLS (lanes keep width 44, min_width never engages); Right-arrow brings the Blocked lane fully into view, cards stay legible
- [defer] [t1603_3] Resize to a wide terminal (>=176 cols): all four lanes are visible without horizontal scrolling. — DEFER 2026-09-02 10:42 auto: behaviour matches p1603_3's measured contract but the item's '>=176' is falsified -- all four lane boxes (44 cols each) close only at 180 rendered cols; clipped at 176-179. Needs a human call: fix the checklist number or treat as a defect.
- [x] [t1603_4] Press enter on an in-flight card: the detail screen opens with a collapsed `Gates (<n>)` section after Risk. — PASS 2026-09-02 10:35 auto: detail opens with '▶ Risk (2)' then collapsed '▶ Gates (2/4)'
- [x] [t1603_4] Expand it: passed / skipped / failed / pending gates are visually distinguishable at a glance. — PASS 2026-09-02 10:35 auto: expanded rows use distinct glyphs ✓ passed / ⊘ skipped / ✗ failed / ⚠ stale / · pending
- [x] [t1603_4] A task with a stale signature shows BOTH facts — that it passed AND that the signature no longer binds. — PASS 2026-09-02 10:35 auto: real code-bound witness gone stale renders '⚠ review_approved -- pass, signature stale; needs re-sign' -- both facts
- [x] [t1603_4] Filtered-by-profile gates appear last under an audit-only label and are not counted in the total. — PASS 2026-09-02 10:35 auto: 'filtered by profile (audit only)' label last with '· build_verified'; total 2/4 excludes it
- [x] [t1603_4] Close the detail screen: focus returns to the card it was opened from, not to the top of the board. — PASS 2026-09-02 10:35 auto: opened detail from 2nd card in its lane (t9006); Escape returned focus to that card, not the top
- [x] [t1603_4] A task with no gate ledger shows the derived phase and provenance, not an empty list or `0/0`. — PASS 2026-09-02 10:35 auto: gates declared + no ledger -> title 'Gates' (no fraction), row 'No gate ledger -- implementing (unknown)' + declared gates as pending; no 0/0
- [x] [t1603_5] The website reference renders (`cd website && ./serve.sh`) and the board page shows the Planned lane and phase documentation. — PASS 2026-09-02 10:42 auto: ./serve.sh -> HTTP 200 for /docs/tuis/board/reference/; hugo build --gc --minify clean (240 pages); page carries the Planned lane + phase docs; all in-page anchors resolve
- [x] [t1603_5] The lane titles, phase names and gate glyphs in the docs match what the running board actually displays. — PASS 2026-09-02 10:42 auto: docs lanes (Planned/Needs your action/Agent can continue/Blocked), 5 phase labels and 6 glyphs (✓ ⊘ · ◈ ✗ ⚠) all observed verbatim on the running board
- [x] [cross] Arrow-key navigation through detail-screen fields still moves in a sensible order with the new Gates section present. — PASS 2026-09-02 10:35 auto: Down walks Priority→Effort→Status→Type→Follow-up unchanged with Gates present; sections render Risk→Gates→Dependencies→Tracking→Lock
- [x] [cross] The board's normal kanban view is unaffected — columns, cards, marks and follow-up glyphs all render as before. — PASS 2026-09-02 10:42 auto: kanban columns+counts, cards, labels, 🚫/🔗 chips, follow-up glyph ◇, risk marker * all render; mark toggles □↔✓ both directions
