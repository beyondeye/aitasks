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
updated_at: 2026-11-06 14:40
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1893_5

## Verification Checklist

- [x] Run `pick <anim-run> --open` on a real recording: the page opens in the default browser; thumbnails show time and delta labels, grouped by segment — PASS 2026-11-06 11:21 auto: synthetic 1280x720 ffmpeg recording (two motions) -> anim (s01 22, s02 19 frames) -> pick --open: OPEN: opened (xdg-open), Chromium window 'Frame picker' appeared; grid groups 's01 (22)'/'s02 (19)', labels '0.967 s first', '1.000 s +33 ms'; 41/41 thumbnails loaded
- [x] Click, shift-click a range, Shift+arrow extend, Space toggle, Up/Down move by visual row, Home/End; Tab moves focus between cards and the preview follows the focused card — PASS 2026-11-06 11:21 auto: headless Chromium, real CDP input: click, shift-click range, Shift+Right extends, Space toggles, Down/Up move by visual row (5/row, also across the s01->s02 boundary), Home/End, Tab/Shift+Tab move focus card to card and the preview follows. Note: Shift+Left after Shift+Right only adds, never shrinks the range
- [x] `s` / `e` mark start / end (S/E badges, `--window` line appears); `x` clears the marks — PASS 2026-11-06 11:21 auto: s/e give S/E badges (and select the frame); block gains '# --window 1.0325-1.1335 (user-marked endpoints (unverified) ...)'; x removes both badges and the --window line
- [x] Drag a rectangle on the large preview: the overlay matches the drag, Esc clears it; on a frame without trusted geometry the disabled reason shows and the block gives an own-pixels line — PASS 2026-11-06 11:21 auto: real mouse drag on preview: overlay within 0.4 px of the drag box; trusted frame -> '# --roi 256,179,512,325' (=20%/25%/40%/45% of 1280x720); Esc hides overlay and drops the line; edited frame -> 'image changed since extraction' reason + '# rectangle ... own pixels' line; folder without frames.tsv -> 'no frames.tsv beside the image'
- [x] Copy from a file:// page in Firefox and Chromium; where the clipboard is refused, the text is selected with the Ctrl+C instruction; pasting into the agent gives one line per frame — PASS 2026-11-06 11:21 auto: headless Chromium + headless Firefox 159 (BiDi), file:// page: Copy button and c report 'Copied.'; Ctrl+V into a textarea == block, one line per frame, tabs kept. Chromium with clipboard-write denied: warn + text selected + Ctrl+C instruction; Ctrl+C/V of it == block (minus final newline). Firefox never refused, so its fallback was not reachable; system (Wayland) clipboard not exercised
- [x] Notes: typing in the note field shows on that frame's line; reloading the page restores selection, marks, notes and rectangle; a rebuild with a changed image starts empty — PASS 2026-11-06 11:21 auto: note typed -> 'note: ...' on that frame's line (tab in note sanitized to space); reload restores selection, S/E marks, N badge, note field, rectangle, identical block; rebuild with one changed image (written to pick_r-2, no clobber) starts empty; control rebuild with unchanged bytes restores state
- [fail] Light and dark themes are readable; the layout holds at phone width — FAIL 2026-11-06 14:40 follow-up t2222
- [x] Over SSH or with no DISPLAY, `--open` prints `OPEN: not opened: no display` and exits 0 — PASS 2026-11-06 11:21 auto: DISPLAY+WAYLAND_DISPLAY unset -> 'OPEN: not opened: no display: neither DISPLAY nor WAYLAND_DISPLAY is set', exit 0, page written; SSH_CONNECTION / SSH_CLIENT set -> 'OPEN: not opened: no display: this is an SSH session ...', exit 0; no browser window opened
