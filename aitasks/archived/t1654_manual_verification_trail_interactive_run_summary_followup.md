---
priority: medium
effort: medium
depends: [1644]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1644]
assigned_to: dario-e@beyond-eye.com
anchor: 1210
followup_kind: manual_verification
created_at: 2026-08-31 19:24
updated_at: 2026-08-31 19:45
completed_at: 2026-08-31 19:45
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1644

## Verification Checklist

- [x] Run `/aitask-trail --show art:trail-gates-framework-landing` and confirm the print ends with the depth, the overview and the board pointer, and carries NO wave/relation recap (the show flow already rendered the document in full immediately above). — PASS 2026-08-31 19:43 auto: ran the show flow on art:trail-gates-framework-landing (get --out + drift=CURRENT); print was exactly 3 lines -- 'Depth: deep', the narrative summary (overview absent → recommendation_summary fallback), then the board pointer verbatim. No wave/relation recap.
- [x] Run `/aitask-trail --refresh` on a deep trail carrying mixed-provenance relations (`art:trail-gates-framework-landing` has `verifies` 4 fact / 1 advisory and `informs` 16 fact / 1 advisory) and confirm each mixed type splits into two separately labelled `<type> · <provenance>:` groups. — PASS 2026-08-31 19:43 auto: rendered Part 2 from the real 56-relation deep document; verifies split into 'verifies · fact' (4) and 'verifies · advisory' (1), informs into 'informs · fact' (16) and 'informs · advisory' (1) -- two separately labelled groups each. Full --refresh re-author+write NOT run (would mutate the user's artifact); the recap is a pure function of this document.
- [x] On that same 56-relation trail, confirm all five relation types (hard_depends, advisory_precedes, coordinates_with, verifies, informs) get endpoint groups, and that the relations block stays around 30 lines rather than one line per edge. — PASS 2026-08-31 19:43 auto: all five types got endpoint groups (hard_depends·fact 12, advisory_precedes·advisory 16, coordinates_with·advisory 6, verifies·fact 4, verifies·advisory 1, informs·fact 16, informs·advisory 1); relations block = 33 lines for 56 edges (~30, vs 63+ at one line per edge).
- [x] Create or refresh a trail at lite depth and confirm the relations line reads exactly `Relations: none recorded at this depth (lite trails omit them).` — not `Relations (0):` and not an empty heading. — PASS 2026-08-31 19:43 auto: art:trail-mobile-shadow-driving is a real lite trail (rendering_hints.depth=lite, relations key ABSENT); recap printed exactly 'Relations: none recorded at this depth (lite trails omit them).' -- not 'Relations (0):', not an empty heading.
- [x] Confirm entry and relation task refs print verbatim (`aitasks#635_27`), never shortened to `635_27`, including for any cross-repo member. — PASS 2026-08-31 19:43 auto: every entry and relation ref printed verbatim as <project>#<id> (aitasks#635_27, aitasks#1076_4); zero unqualified refs across all 4 artifacts. Cross-repo covered by art:trail-mobile-shadow-driving-deep -- aitasks_mobile#32_1 / #32_2 kept their project segment. Board detail pane also shows 'Entry aitasks#635_27'.
- [x] In `ait board`, press `z`, then `s`, then `v`, then `Enter` on a member card, and confirm each key does what the run summary's board pointer line claims it does. — PASS 2026-08-31 19:43 auto: live ait board in tmux -- z opened By-Trail, s opened the 'Select trail' picker, v opened the full summary overlay (text identical to the run summary's Part 1 line), Enter on a focused member card opened the entry detail. Footer read 's Select Trail'. test_board_bytrail_view.py drift guard: 145 passed.
