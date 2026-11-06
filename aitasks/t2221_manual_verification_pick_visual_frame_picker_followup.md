---
priority: medium
effort: medium
depends: [t1893_5]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1893_5]
premise_baseline: e4619f8ff052d8c06ea4253ec773c832edf59f20 @ 2026-11-06 11:03
assigned_to: dario-e@beyond-eye.com
anchor: 1887
followup_kind: manual_verification
created_at: 2026-11-06 11:03
updated_at: 2026-11-06 11:15
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1893_5

## Verification Checklist

- [ ] Run `pick <anim-run> --open` on a real recording: the page opens in the default browser; thumbnails show time and delta labels, grouped by segment
- [ ] Click, shift-click a range, Shift+arrow extend, Space toggle, Up/Down move by visual row, Home/End; Tab moves focus between cards and the preview follows the focused card
- [ ] `s` / `e` mark start / end (S/E badges, `--window` line appears); `x` clears the marks
- [ ] Drag a rectangle on the large preview: the overlay matches the drag, Esc clears it; on a frame without trusted geometry the disabled reason shows and the block gives an own-pixels line
- [ ] Copy from a file:// page in Firefox and Chromium; where the clipboard is refused, the text is selected with the Ctrl+C instruction; pasting into the agent gives one line per frame
- [ ] Notes: typing in the note field shows on that frame's line; reloading the page restores selection, marks, notes and rectangle; a rebuild with a changed image starts empty
- [ ] Light and dark themes are readable; the layout holds at phone width
- [ ] Over SSH or with no DISPLAY, `--open` prints `OPEN: not opened: no display` and exits 0
