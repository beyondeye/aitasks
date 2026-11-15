---
priority: low
effort: medium
depends: [t2278_6]
issue_type: feature
status: Ready
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:12
---

## Context

Child 7 of t2278 (docs TUI screenshot generator), and **optional**. The full
design is in the parent plan `aiplans/p2278_docs_tui_screenshot_generator.md`
("Backends", C). Every scene already has a vector capture path through backend
A (headless Textual) or B (tmux composite). This backend adds real-pixel
captures of a real terminal for cases where the vector look is not enough.

It works only inside a live Hyprland session, so it can never be the only path
to a scene. If the first probe fails, record the result in the plan's Final
Implementation Notes and close the task without building the backend.

## Key Files to Modify

- `website/screenshots/backends/pixel_backend.py` (new).
- `website/screenshots/scene.py`: accept `backend: pixels` with a `fallback`
  scene id that must name a vector scene.
- `website/screenshots/assets/`: a pinned terminal config (font, theme, size),
  so the user's own theme does not leak in.
- `tests/test_screenshots_pixel_backend.py` (new): geometry mapping only,
  which needs no display.

## Approach

1. **Live probe first.** `hyprctl output create headless <NAME>`; start a
   terminal with the pinned config and a fixed window class on that output;
   check whether the bar or any window rule attaches to the headless output.
   Remove the output afterwards (`hyprctl output remove <NAME>`). Register the
   removal before creating the output, so a failed run cannot leave one behind.
2. Capture with `grim -o <NAME>`, or `grim -g` with the geometry from
   `hyprctl clients -j`.
3. Post-process with ImageMagick 7 (`magick`): PNG or WebP, crop, draw.
   Cell rectangles map through window pixels divided by cols × rows, so the
   same `crop` and `overlays` spec fields work.
4. The capability check (a Hyprland session, `grim`, `magick`, a terminal) must
   not run the backend itself.

Available on this machine: `grim`, `hyprctl`, `magick`, `rsvg-convert`. Not
available: `resvg`, `inkscape`, Pillow, cairosvg.

## Reference Files for Patterns

- `website/screenshots/backends/tmux_backend.py`: teardown registered before
  the first spawn; settle by polled text, never a sleep.
- `website/screenshots/svgpost.py`: the cell-rectangle contract.

## Implementation Plan

See `aiplans/p2278/p2278_7_real_pixel_backend.md`.

## Verification Steps

- The probe result is recorded.
- If built: one scene captured through backend C matches its vector capture in
  layout; no headless output is left after a run (`hyprctl monitors`); the
  geometry test passes; a machine without Hyprland reports the backend as
  unavailable and the vector fallback is used.
