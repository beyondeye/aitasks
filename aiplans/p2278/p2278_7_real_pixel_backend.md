---
Task: t2278_7_real_pixel_backend.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_7: real pixels (optional)

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` (revised
2026-11-15). Read child 2's archived plan for the session model. This child
may end after step 1 with a recorded negative result.

## Steps

1. **Live probe.** Requires a Hyprland session (`HYPRLAND_INSTANCE_SIGNATURE`
   set). In a scratchpad script: register `hyprctl output remove <NAME>` as
   cleanup, then `hyprctl output create headless <NAME>`; start a session with
   `website/screenshots.sh session start` and launch a TUI in it; launch a
   terminal with a pinned config and a fixed window class on that output,
   attached to the session's tmux socket; inspect `hyprctl monitors -j`,
   `hyprctl clients -j` and `hyprctl layers -j` for a bar or other layer on
   the headless output; take one `grim -o <NAME>` frame and look at it.
   Record: does a bar attach, do window rules apply, what the terminal's cell
   size in pixels is, and whether attaching a second client resizes the
   window. **If the output cannot be made clean, write the result into Final
   Implementation Notes and stop.**

2. **Pinned terminal config.** `website/screenshots/assets/`: font, size,
   theme and padding, loaded with an explicit config flag so the user's own
   terminal config is never read.

3. **`pixels.py`.** `available() -> (bool, reason)` checks the session
   variable and `shutil.which` for `hyprctl`, `grim`, `magick` and the
   terminal; it does not create an output. `capture(session, out)`: create the
   output, attach the terminal at the session's size, wait until the terminal
   shows the same text the pane holds (compare with `screen`; never a sleep),
   `grim`, remove the output. Map cell rectangles to pixels with
   `window_px / (cols, rows)` and apply crop and overlays with `magick`.

4. **`shot --pixels` and recipes.** A recipe with `pixels: true` stages the
   pixel image when the capability is available, and otherwise the vector
   image with a printed notice.

5. **Tests.** Geometry mapping and the recipe field validation only; no
   display needed.

## Verification

- Probe result recorded.
- If built: one scene captured both ways and compared; `hyprctl monitors` shows
  no leftover output; on a machine without Hyprland the vector image is used.

Post-implementation: Step 9 of the task workflow.
