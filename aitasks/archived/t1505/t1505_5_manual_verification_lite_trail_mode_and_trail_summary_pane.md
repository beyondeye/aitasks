---
priority: medium
effort: medium
depends: [t1505_4]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1505_1, t1505_2, t1505_3, t1505_4]
assigned_to: dario-e@beyond-eye.com
anchor: 1210
followup_kind: manual_verification
created_at: 2026-08-13 12:31
updated_at: 2026-08-17 17:17
completed_at: 2026-08-17 17:17
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] SETUP (do this first — every live check below runs against this handle): run `/aitask-trail <a real task id>` with NO depth flag and note the new handle. t1468_5's bump to schema 1.1.0 invalidates art:trail-gates-framework-landing and art:trail-shadow-review-loop until t1468_7 refreshes them; an ERROR:invalid_trail on those two is EXPECTED and is not a t1505 failure. — PASS 2026-08-17 17:02 auto: created art:trail-mobile-shadow-driving (lite, no depth flag) over scope task 1118. NOTE: the item's expected ERROR:invalid_trail on the two pre-existing trails did NOT occur - t1468_7 already refreshed both to schema 1.1.0, so drift returns STALE on each.
- [x] [t1505_4] The lite run completed materially faster than the same trail with `--deep`. Record both wall-clock times. — PASS 2026-08-17 17:02 auto: lite ~120s vs deep 244s agent-active (confirmation-gate idle excluded from both); output 14,155 vs 31,009 bytes, obs 0 vs 6, rel 0 vs 13, exc 0 vs 6, evidence 1 vs 10.
- [x] [t1505_4] The run printed the trail summary at the end of its own output, after the HANDLE: line — no board round-trip was needed to read it. — PASS 2026-08-17 17:02 auto: summary printed at end of run output, after the HANDLE: line; no board round-trip needed. Template mandates it at 2e.5/3.7/1.4.
- [x] [t1505_4] The printed output states the depth (lite), so a lite artifact cannot be mistaken for a deep one. — PASS 2026-08-17 17:02 auto: run output stated 'Depth: lite' as its own line before the summary; deep run stated 'Depth: deep'.
- [x] [t1505_4] `./.aitask-scripts/aitask_trail_gather.sh drift --trail <new handle>` returns CURRENT or STALE — never ERROR:invalid_trail. — PASS 2026-08-17 17:02 auto: drift --trail art:trail-mobile-shadow-driving returns CURRENT (DIGEST:1c44cb4efd49b5b6); deep handle also CURRENT. No ERROR:invalid_trail.
- [x] [t1505_4] The stored lite document carries no observations, no relations, no exclusions, and exactly one evidence record. — PASS 2026-08-17 17:02 auto: stored lite doc - observations/relations/exclusions keys ABSENT (not empty), evidence len 1, no per-entry evidence_refs, rendering_hints {depth: lite}.
- [x] [t1505_4] A task with a known followup_kind still has it in the STORED entry.snapshot after both a lite run and a `--deep` run. — PASS 2026-08-17 17:02 auto: aitasks#1118_5 snapshot.followup_kind == manual_verification in BOTH stored docs; the other 5 entries omit the key entirely (no 'unknown' sentinel leak).
- [x] [t1505_3] The stored trail carries narrative.overview, and its prose actually answers "which task next and why" — not a restatement of the wave table. — PASS 2026-08-17 17:02 auto: narrative.overview present; opens 'Start with t1118_1', names t1118_2 as the bottleneck, says where a 2nd agent pays, and flags the cross-repo constraint this repo cannot observe - not a wave-table restatement.
- [x] [t1505_1] In a REAL terminal (not run_test): open the board, press z for By-Trail, select the new trail. The summary pane renders below the wave columns. — PASS 2026-08-17 17:13 auto: real tmux 120x40, ait board -> z -> s -> lite trail. Summary pane renders rows 33-38, below the wave columns (columns end row 31).
- [x] [t1505_1] The footer is still FULLY visible with the pane mounted — every key row readable, nothing painted over. This is the t1278 failure mode and it is invisible to display/visible assertions. — PASS 2026-08-17 17:13 auto: footer occupies rows 39-40 of 40, both rows fully readable ('? Keys ... v Summary' / 'n New Task  O Options ... ^p palette'). Nothing painted over; pane is a flow child, not docked.
- [x] [t1505_1] Repeat the footer check at a narrow terminal width (~80 columns) and a short height (~24 rows). — PASS 2026-08-17 17:13 auto: at 80x24 the footer is 3 rows (22-24), all keys readable, '^p palette' intact; pane rows 16-21, columns 7-14. NOTE: at 80 cols the header sheds the ' . lite' depth label along with the truncated title (documented fixed-width budget, t1278 shed).
- [x] [t1505_1] Press v: the summary opens in a modal, scrolls, and escape closes it. — PASS 2026-08-17 17:13 auto: v opens 'Trail summary - <title>' modal; PageDown advanced from para 1 to para 2 with the scrollbar thumb moving; Escape closed it back to the board.
- [x] [t1505_1] Leave By-Trail (press a for All): the pane disappears and the columns return to full height. — PASS 2026-08-17 17:13 auto: after 'a' the summary pane is gone, columns extend from row 31 to row 36 (reclaimed the 6 pane rows), footer back to its 3-row All-view set.
- [x] [t1505_1] The board shows the trail's depth label for the lite trail, and shows NO depth label for a trail that predates the rendering_hints marker (absent must not render as "deep"). — PASS 2026-08-17 17:13 auto: lite trail header shows ' . lite'. art:trail-shadow-review-loop and art:trail-gates-framework-landing both carry rendering_hints WITHOUT a depth key and render NO depth label (only the stale marker) - absent is not defaulted to deep.
- [x] [t1505_2] Open a card's detail modal: the entry-specific content is what you see first, without scrolling. — PASS 2026-08-17 17:13 auto: modal opens with 'Entry aitasks#1294' as the first line, then classification/confidence/rationale/expected outcome/why order matters - all entry-specific, visible without scrolling.
- [x] [t1505_2] Open the modal for a DIFFERENT card in the same trail: the two modals differ by more than the entry block — the trail-global observations/evidence are not repeated wholesale in both. — PASS 2026-08-17 17:13 auto: two cards in art:trail-shadow-review-loop. #1294 shows 15 evidence + 2 obs (24 withheld); #1427 shows 18 evidence + 7 obs (19 withheld). Only 7 evidence ids shared; 8 unique to A, 11 unique to B. Globals are scoped per entry, not repeated wholesale.
- [x] [t1505_2] On the lite trail (no observations, no exclusions, one evidence record) the modal reads as complete — no empty section headings, no silently blank regions that read as a rendering bug. — PASS 2026-08-17 17:13 auto: lite modal has NO Observations/Exclusions/Drift headings at all (omitted, not blank), single evidence record shown as '- trail-level (uncited)', and states 'Trail totals: 0 observations . 0 exclusions . 1 evidence . 0 drift reasons' + 'Showing the full trail.' so empty reads as empty, not broken.
- [x] [t1505_2] The reveal key shows the withheld document-level sections in full — nothing became unreachable. — PASS 2026-08-17 17:13 auto: 'a' revealed every withheld section - all observation kinds, full evidence block (~15 -> 69), Exclusions; every '... N more' marker gone; mode line flips to 'Showing the full document - press a to scope back to this entry.' Nothing unreachable.
- [x] [t1505_2] Repeat the modal readability check at ~80 columns. — PASS 2026-08-17 17:13 auto: at 80 cols the modal wraps cleanly on word boundaries, entry block leads without scrolling, End reaches Evidence + totals, Close reachable, board footer still fully visible below.
- [x] [ALL] After t1468_7 has refreshed art:trail-gates-framework-landing and art:trail-shadow-review-loop to 1.1.0, re-open By-Trail on each and confirm the pane and modal behave the same on a deep, observation-rich trail as on the lite one. — PASS 2026-08-17 17:13 auto: precondition met - t1468_7 already refreshed both to 1.1.0 (drift returns STALE, not ERROR:invalid_trail). gates-framework-landing (21 obs / 60 evidence / 2 exclusions): pane renders via recommendation_summary fallback, footer intact, no depth label, modal entry-scoped (7 obs shown / 14 withheld, 25 evidence / 35 withheld), v works. Same behaviour as the lite trail.
