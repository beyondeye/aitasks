---
priority: medium
effort: medium
depends: [t1505_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1505_1, 1505_2, 1505_3, 1505_4]
anchor: 1210
followup_kind: manual_verification
created_at: 2026-08-13 12:31
updated_at: 2026-08-13 12:31
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] SETUP (do this first — every live check below runs against this handle): run `/aitask-trail <a real task id>` with NO depth flag and note the new handle. t1468_5's bump to schema 1.1.0 invalidates art:trail-gates-framework-landing and art:trail-shadow-review-loop until t1468_7 refreshes them; an ERROR:invalid_trail on those two is EXPECTED and is not a t1505 failure.
- [ ] [t1505_4] The lite run completed materially faster than the same trail with `--deep`. Record both wall-clock times.
- [ ] [t1505_4] The run printed the trail summary at the end of its own output, after the HANDLE: line — no board round-trip was needed to read it.
- [ ] [t1505_4] The printed output states the depth (lite), so a lite artifact cannot be mistaken for a deep one.
- [ ] [t1505_4] `./.aitask-scripts/aitask_trail_gather.sh drift --trail <new handle>` returns CURRENT or STALE — never ERROR:invalid_trail.
- [ ] [t1505_4] The stored lite document carries no observations, no relations, no exclusions, and exactly one evidence record.
- [ ] [t1505_4] A task with a known followup_kind still has it in the STORED entry.snapshot after both a lite run and a `--deep` run.
- [ ] [t1505_3] The stored trail carries narrative.overview, and its prose actually answers "which task next and why" — not a restatement of the wave table.
- [ ] [t1505_1] In a REAL terminal (not run_test): open the board, press z for By-Trail, select the new trail. The summary pane renders below the wave columns.
- [ ] [t1505_1] The footer is still FULLY visible with the pane mounted — every key row readable, nothing painted over. This is the t1278 failure mode and it is invisible to display/visible assertions.
- [ ] [t1505_1] Repeat the footer check at a narrow terminal width (~80 columns) and a short height (~24 rows).
- [ ] [t1505_1] Press v: the summary opens in a modal, scrolls, and escape closes it.
- [ ] [t1505_1] Leave By-Trail (press a for All): the pane disappears and the columns return to full height.
- [ ] [t1505_1] The board shows the trail's depth label for the lite trail, and shows NO depth label for a trail that predates the rendering_hints marker (absent must not render as "deep").
- [ ] [t1505_2] Open a card's detail modal: the entry-specific content is what you see first, without scrolling.
- [ ] [t1505_2] Open the modal for a DIFFERENT card in the same trail: the two modals differ by more than the entry block — the trail-global observations/evidence are not repeated wholesale in both.
- [ ] [t1505_2] On the lite trail (no observations, no exclusions, one evidence record) the modal reads as complete — no empty section headings, no silently blank regions that read as a rendering bug.
- [ ] [t1505_2] The reveal key shows the withheld document-level sections in full — nothing became unreachable.
- [ ] [t1505_2] Repeat the modal readability check at ~80 columns.
- [ ] [ALL] After t1468_7 has refreshed art:trail-gates-framework-landing and art:trail-shadow-review-loop to 1.1.0, re-open By-Trail on each and confirm the pane and modal behave the same on a deep, observation-rich trail as on the lite one.
