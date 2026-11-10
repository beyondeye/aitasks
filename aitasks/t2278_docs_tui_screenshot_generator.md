---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [website, documentation, tui, skills, screenshots]
gates: [risk_evaluated]
created_at: 2026-11-10 18:13
updated_at: 2026-11-10 18:13
---

## Goal

Generate the website's TUI screenshots autonomously. Doc authors leave a
**placeholder marker** where a screenshot belongs. A tool and skill then makes
an **autonomous pass** over `website/content/`: it resolves each marker to a
scene, boots the TUI (or a tmux composite) on a synthetic fixture, drives it to
the described state, captures it, optionally crops it and adds highlight /
annotation overlays, writes the image under `website/static/imgs/`, and
replaces the marker with a `{{< static-img >}}` shortcode. The new images then
go to the user for review before anything is committed.

## Current state (from exploration)

- **Shortcode:** `website/layouts/shortcodes/static-img.html` (params `src`,
  `alt`, `caption`, `class`; zoom overlay). Used 19 times across 18 distinct
  images, all **Textual SVG exports** (Rich `rich-terminal` SVG, ~3000-3500px
  wide viewBox, ~300KB each) in `website/static/imgs/`. They were captured by
  hand (t242, t268_8, t448_6, t760); no generator script exists.
- **17 placeholders, three inconsistent shapes:**
  - `<!-- TODO screenshot: <file>.svg — <desc> -->` / `<!-- TODO screenshot: <file>.svg -->`
  - `<!-- SCREENSHOT: <file>.svg — <desc> -->`
  - `<!-- SCREENSHOT: <desc> -->` (no filename)
  Locations: `installation/terminal-setup.md:41` (`ait ide` startup);
  `tuis/_index.md:37`; the shared TUI-switcher dialog in
  `tuis/{codebrowser,settings,board,monitor,minimonitor}/how-to.md` and
  `tuis/monitor/_index.md:86`; `tuis/board/_index.md:39,65` (annotated layout,
  annotated card close-up); `tuis/board/how-to.md:331,408`;
  `tuis/monitor/_index.md:48` (annotated layout);
  `tuis/minimonitor/_index.md:14`; `tuis/brainstorm/_index.md:14`;
  `tuis/trails/_index.md:12`; `tuis/sitrep/_index.md:12`.
  Re-grep before relying on these line numbers.

## Requirements

1. **One placeholder marker grammar.** It must be machine-parseable, name the
   output file, carry the alt/caption text and reference a scene. All 17
   existing markers migrate to it. Ship a check that lists any marker still
   unresolved, and any marker that does not parse.
2. **Scene specs.** One declarative spec per scene: which TUI or composite
   layout, fixture, terminal size (cols×rows), key or Pilot sequence, settle
   condition (text or widget present, not a sleep), backend, crop and overlays.
   Several markers can share one scene (the TUI-switcher dialog appears 6
   times).
3. **Partial screenshots.** Crop to a widget (CSS selector / id) or to an
   explicit cell rectangle.
4. **Highlight and annotation overlays.** Boxes or tinted highlights over a
   widget or region, plus numbered callouts and labels. These explain the
   various panes and cover the "annotated layout" placeholders.
5. **Autonomous pass.** A skill (Claude Code first) that walks the docs, finds
   markers, writes any missing scene spec, captures, previews the result for
   the user, then rewrites the markers into `static-img`. Run
   `website/check_links.py --build` afterwards (CLAUDE.md requirement for
   `website/content/` edits).

## Capture backends (all buildable with tools already installed)

- **A. Textual vector (default, portable, CI-able):** boot the app headless with
  `App.run_test(size=(cols, rows))`, drive it with Pilot, then
  `app.export_screenshot()` produces SVG. Proven in
  `tests/test_logview_search_box.py`, `tests/test_frozenagent_app.py` and
  `tests/test_agent_model_picker_narrow.py`. Synthetic data:
  `tests/lib/board_fixture.py` boots `KanbanApp` on a temp task tree (mind its
  relative-`TASK_DIR` + cwd invariant). Never screenshot the real repo; it
  leaks live task data and is non-deterministic.
- **B. tmux composite → SVG:** for multi-pane scenes (minimonitor beside an
  agent pane, sitrep window, `ait ide` startup, monitor with agents). Use an
  isolated tmux socket (pattern: `tests/test_board_startup_focus_live.py`,
  `tests/lib/tmux_isolation.sh`). Read the geometry from `list-panes`, take
  each pane with `capture-pane -e`, stitch them with drawn borders into Rich
  `Text.from_ansi`, and write SVG with `Console.export_svg`. pyte is not
  installed and is not needed. Framework-code tmux calls must go through
  `lib/tmux_exec.{py,sh}` (see `aidocs/framework/tmux_gateway.md`).
- **C. Real pixels (optional, this-machine only):** add a virtual monitor with
  `hyprctl output create headless <NAME>` (Hyprland 0.57 confirmed). Launch
  ghostty/foot with a **pinned config** (font, theme, size, so the user's
  Omarchy theme does not leak in) and a fixed window class on that output.
  Capture with `grim -o <NAME>` or `-g` from `hyprctl clients -j`, post-process
  with ImageMagick 7 (PNG / WebP / crop / draw), then remove the output. Not
  yet live-probed: whether Omarchy's bar or window rules attach to a headless
  output. It requires a live Hyprland session, so it can never be the only
  path to a scene.

## Overlay / crop geometry

The cell geometry of a Rich SVG is fixed: `char_height=20`,
`char_width=20*font_aspect_ratio` (12.2 at the default 0.61),
`line_height=24.4`, `padding_top=40`, `padding_left=8`, `margin=1` (see
`rich/console.py` `export_svg`, ~line 2420). Textual widgets expose `region` in
cells. Crops are therefore viewBox rewrites, and overlays are injected
`<rect>`/`<text>` elements; both are exact and stay vector. Backend C maps the
same cell coordinates through the window's pixel size divided by cols×rows.

## Open decisions for planning

- Is this a shipped framework skill (generic: "screenshots of your project's
  TUIs") or an aitasks-repo-only dev tool? This decides where the scene specs
  live, and whether `seed/` is involved.
- Should the existing 18 hand-made SVGs be regenerated, so all images share one
  pinned look?
- Output format policy: SVG for backends A/B, PNG/WebP for C. The shortcode
  takes either.
- Likely split into children: marker grammar + migration + check; scene-spec
  format + backend A; backend B; overlays/crop; skill + autonomous pass;
  backend C (optional, last).

## Hazards

- Several TUI doc pages and `website/content/docs/tuis/sitrep/` have
  uncommitted, in-flight edits in the working tree right now. Gate any marker
  migration on those tasks before editing the pages.
- Follow `aidocs/framework/documentation_conventions.md` and
  `aitasks/metadata/doc_update_guide.md` for alt/caption prose.
- Skill work is done in Claude Code first. Suggest follow-up tasks to port it
  to Codex / OpenCode.
