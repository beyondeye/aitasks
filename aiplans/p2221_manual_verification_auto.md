---
Task: t2221_manual_verification_pick_visual_frame_picker_followup.md
Base branch: main
Output branch: main
---

# Manual-verification auto-execution log (t2221, verifies t1893_5)

Strategy: autonomous. Commit under test: e4619f8ff (t1893_5).

## Fixture

- Synthetic recording (ffmpeg lavfi): 1280x720, 30 fps, 4.5 s, light-grey canvas;
  a 160x120 blue box slides right 1.0-1.6 s, then down 2.8-3.3 s (`overlay`
  with time expressions; `drawbox` does not re-evaluate `t` per frame).
- `aitask_screen_recording.sh anim rec.mp4` -> 2 segments (s01 linear 602 ms,
  s02 linear 499 ms), 22 + 19 frames with `frames.tsv`.
- Variants: `anim_edit` (one s01 frame drawn on with ImageMagick), `plain`
  (10 PNGs, no `frames.tsv`), `anim_r` (rebuild test), `anim_ctl` (unchanged copy).
- Browsers: headless Chromium driven over CDP with real `Input.*` mouse/key
  events; headless Firefox 159 over WebDriver BiDi `input.performActions`.
  The page's own `#selftest` hook was **not** used.

## Execution Log

### Item 1
- Item text: `pick <anim-run> --open` on a real recording opens the default browser; time/delta labels, grouped by segment
- Approach: CLI + window list + headless DOM
- Action run: `pick anim --open --out pick`; `hyprctl clients -j`; DOM query of `.group h2`, `.card .label`
- Output (trimmed): `OPEN: opened (xdg-open)`, exit 0; window `Frame picker - Chromium`; groups `s01 (22)`, `s02 (19)`; labels `0.967 s first`, `1.000 s +33 ms`; 41/41 thumbnails decoded
- Verdict: pass (recording was synthetic, not a captured screen)

### Item 2
- Item text: click, shift-click, Shift+arrow, Space, Up/Down by visual row, Home/End, Tab focus follows
- Approach: headless Chromium, real CDP input
- Output (trimmed): click 1 -> [1]; shift-click 4 -> [1..4]; Shift+Right x2 from 6 -> [6,7,8]; Space toggles 7 off/on; Down 7->12->17, Up ->12 (5 cards/row); End -> 40, Home -> 0; Down from 20 (last s01 row) -> 22 (first s02 row); Tab 20->21->22, Shift+Tab ->21, preview text follows each
- Note: Shift+Left after Shift+Right keeps [6,7,8] — the range only grows
- Verdict: pass

### Item 3
- Item text: s / e mark start / end (S/E badges, `--window` line); x clears
- Output (trimmed): badges `[2,"+S"],[5,"+E"]`; `# --window 1.0325-1.1335  (user-marked endpoints (unverified): ...)`; after x: no badges, no `--window` line
- Verdict: pass

### Item 4
- Item text: drag rectangle; overlay matches; Esc clears; untrusted geometry -> reason + own-pixels line
- Output (trimmed): drag box l=952.2 t=169.0 w=208.4 h=131.9 vs overlay l=952.2 t=168.7 w=208.4 h=132.2; `# --roi 256,179,512,325 (source-video pixels ... SHA-256 verified)`; Esc -> overlay hidden, line gone. Edited frame: `Source --roi disabled: the image changed since extraction: its SHA-256 3589562f351a differs from frames.tsv a74e96d643ad`, block `# rectangle 160,112,320,203 in f008_1.067s.png's own pixels ...`. No frames.tsv: `no frames.tsv beside the image`
- Verdict: pass

### Item 5
- Item text: copy from file:// in Firefox and Chromium; refusal -> selected text + Ctrl+C instruction; paste gives one line per frame
- Output (trimmed): Chromium: button and `c` -> `Copied. Paste it into the agent.`; Ctrl+V into a textarea == block, 3 frame lines, tabs kept. With `clipboard-write` denied: `warn | Copy did not work here. The text below is selected: press Ctrl+C ...`; selection == block minus its final newline; Ctrl+C/Ctrl+V of it == block minus final newline. Firefox 159: `isSecureContext` true; button and `c` copy; paste == block (813 chars), one line per frame. Firefox accepted `writeText` even without user activation, so its refusal branch could not be reached
- Not exercised: the system (Wayland) clipboard — headless browsers keep their own
- Verdict: pass

### Item 6
- Item text: notes on the frame's line; reload restores selection, marks, notes, rectangle; rebuild with changed image starts empty
- Output (trimmed): `...f009_1.100s.png  t=1100 ms  +33 ms  note: box overshoots here x` (typed tab sanitised to a space); after reload: same badges, note field, rectangle shown, block byte-identical. Rebuild into the same `--out` wrote `pick_r-2/` (no clobber); that page: no badges, `# no frames selected`. Control (`anim_ctl`, unchanged bytes, other dir): state restored (same fingerprint `82e54dad`)
- Verdict: pass

### Item 7
- Item text: light and dark themes readable; layout holds at phone width
- Output (trimmed): 390 px: `scrollWidth == innerWidth`, no element past the right edge; grid 2 columns, side panel below. Contrast light: min 4.38 (S badge). Dark: Copy button 2.74, S badge 2.25, E badge 3.03, + badge 2.74; other text >= 5.0
- Verdict: defer — readable in screenshots but below WCAG AA for the dark accent buttons/badges; needs a human decision

### Item 8
- Item text: over SSH or with no DISPLAY, `--open` prints `OPEN: not opened: no display` and exits 0
- Output (trimmed): no display: `OPEN: not opened: no display: neither DISPLAY nor WAYLAND_DISPLAY is set`, exit 0; `SSH_CONNECTION` (and `SSH_CLIENT` alone): `OPEN: not opened: no display: this is an SSH session, so a browser would open on the remote machine, if anywhere`, exit 0; page still written; no new window
- Verdict: pass

## Cleanup

- Scratch fixtures, browser profiles and driver scripts under the session
  scratchpad (`av2221/`, `prof*/`, `drv/`) — removed after the run.
- The Chromium window opened by item 1's `--open` was left to the user.
