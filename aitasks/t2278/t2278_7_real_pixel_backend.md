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

Child 7 of t2278 (docs TUI screenshot generator), and **optional**. Read the
parent plan `aiplans/p2278_docs_tui_screenshot_generator.md` first; the design
was revised on 2026-11-15 to an agent driving the real TUI in an isolated tmux
session. Every scene already has a vector capture: the pane's cells exported
as SVG. This child adds real-pixel captures of a real terminal for cases
where the vector look is not enough.

Under the revised design this is small: the TUI is already running in a tmux
session, so a pixel capture is a real terminal **attached to that same
session** on a headless output, photographed.

It works only inside a live Hyprland session, so it can never be the only path
to a scene. If the first probe fails, record the result in the plan's Final
Implementation Notes and close the task without building anything.

## Key Files to Modify

- `website/screenshots/pixels.py` (new): `available()`, and
  `capture(session, out_png)`.
- `website/screenshots/cli.py`: `shot --pixels` (PNG or WebP beside the SVG).
- `website/screenshots/recipe.py`: an optional `pixels: true` on a recipe; a
  replay on a machine without the capability stages the vector image and says
  so.
- `website/screenshots/assets/`: a pinned terminal config (font, theme, size),
  so the user's own theme does not leak in.
- `tests/test_screenshots_pixels.py` (new): geometry mapping only, which
  needs no display.

## Approach

1. **Live probe first.** `hyprctl output create headless <NAME>`; start a
   terminal with the pinned config and a fixed window class on that output,
   running `tmux -L <session socket> attach` (through `TmuxClient`'s argv);
   check whether the bar or any window rule attaches to the headless output.
   Remove the output afterwards (`hyprctl output remove <NAME>`). Register the
   removal before creating the output, so a failed run cannot leave one behind.
2. Capture with `grim -o <NAME>`, or `grim -g` with the geometry from
   `hyprctl clients -j`.
3. Post-process with ImageMagick 7 (`magick`): PNG or WebP, crop, draw.
   Cell rectangles map through window pixels divided by cols × rows, so the
   same `crop` and `overlays` recipe fields work.
4. The capability check (a Hyprland session, `grim`, `magick`, a terminal) must
   not create an output or start a terminal.

Available on this machine: `grim`, `hyprctl`, `magick`, `rsvg-convert`,
`chromium`. Not available: `resvg`, `inkscape`, Pillow, cairosvg.

## Reference Files for Patterns

- `website/screenshots/session.py`: teardown and the bounded waits.
- `website/screenshots/svgpost.py`: the cell-rectangle contract.

## Implementation Plan

See `aiplans/p2278/p2278_7_real_pixel_backend.md`.

## Verification Steps

- The probe result is recorded.
- If built: one scene captured as pixels matches its vector capture in
  layout; no headless output is left after a run (`hyprctl monitors`); the
  geometry test passes; a machine without Hyprland reports the capability as
  unavailable and the vector image is used.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2278_4** id=2026-11-17T09:35:38Z.19ae4c300425fe852f25cf55 from=t2278_4 from_verified=yes at=2026-11-17T09:35:38Z base=46d4e21d773eb8940c7cb18538f296c3fb0d4f5d base_branch=main dirty=yes host=omg16
>
> | Facts from t2278_4 (commit fb3b8556c) that affect attaching a real terminal to
> | a screenshot session:
> | - Every screenshot server now runs with `update-environment ""` and with
> |   DISPLAY / WAYLAND_DISPLAY unset in both the global and the session
> |   environment (website/screenshots/session.py, DESKTOP_VARIABLES). This keeps
> |   TUIs in the session from opening desktop windows. The terminal you attach
> |   lives outside the server, so it is not affected, but anything you launch
> |   INSIDE the session will not see the display.
> | - Border options are pinned (session.BORDER_OPTIONS: pane-border-indicators
> |   off, pane-active-border-style fg=green, ...). Real pixels will show exactly
> |   what stitch.py draws for multi-pane windows; tmux's default would half-colour
> |   a two-pane window's border.
> | - A nested `tmux attach` (a client started from a pane of a SECOND private
> |   server, `env -u TMUX tmux -u -L <socket> attach -t =lumen`) renders the
> |   session faithfully: tests/test_screenshots_session_live.py `tmux_render` is
> |   the oracle the stitcher is checked against. Note an attached client resizes
> |   the window under the default `window-size latest`: size the terminal to the
> |   recipe's `size`.
> | - Agent panes run a stand-in (`claude` = website/screenshots/standin_agent.py),
> |   never a real agent; recipes for monitor/minimonitor/sitrep need the
> |   `agents` dataset.
