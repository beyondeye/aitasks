---
priority: medium
effort: high
depends: [t2278_3]
issue_type: feature
status: Ready
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:12
---

## Context

Child 4 of t2278 (docs TUI screenshot generator). Read the parent plan
`aiplans/p2278_docs_tui_screenshot_generator.md` first; the design was revised
on 2026-11-15 to an agent driving the real TUI in an isolated tmux session.
Children 2 and 3 delivered the sample project, the session primitives (which
already own the isolated tmux server), single-pane SVG export, recipes, and
`svgpost` (crop and overlays on cell rectangles). Read their archived plans.

This child extends a session from one pane to a **window of several panes**
and delivers the scenes that need one: the TUIs that only make sense beside
other panes (monitor, minimonitor, sitrep) and the switcher opened from them.

## Hard rules (already enforced by child 2's `session.py`; do not bypass)

- Every tmux call goes through `TmuxClient` on the session's private socket.
  Never build a `["tmux", ...]` argv by hand. The client adds the mandatory
  `-u` flag and decodes UTF-8 (`aidocs/framework/tmux_gateway.md`, policy 5).
- The server is started only by `session.start_server()` with `-f /dev/null`.
  This child adds panes and windows to that server; it never starts one.
- Pane ids come from `-P -F`. New panes get the same pinned environment as
  the first one and are launched with `env -u COLUMNS -u LINES`.
- Readiness is a bounded poll on a pane's text. Never a sleep.

## Key Files to Modify

- `website/screenshots/session.py` / `cli.py`: `pane split <id> [-h|-v]
  [-l SIZE] -- <command>` and `window new <id> --name N -- <command>` verbs
  (journaled); `--pane` on `screen`, `keys`, `wait`, `find`; `shot --window`.
- `website/screenshots/stitch.py` (new): read geometry from `list-panes -F`,
  capture each pane, blit into one cell grid at each pane's `(left, top)`,
  draw the borders tmux draws between panes, export through `svg_export`.
  Pane rectangles are available to `svgpost` like any other cell rectangle.
- `website/screenshots/sample_project.py`: an `agents` dataset: what the
  monitor family needs to show believable agent windows (task files in
  `Implementing`, and the stand-in agent script the setup commands launch).
- `website/screenshots/recipe.py`: record and replay the pane / window steps.
- `website/screenshots/scenes/`: `minimonitor_main_view`, `sitrep_window`,
  `ait_ide_startup`, `monitor_layout_annotated`,
  `tui_switcher_from_monitor`, `tui_switcher_from_minimonitor`, recorded
  through the tool.
- `tests/test_screenshots_stitch.py` (new), and additions to the live module.

## Reference Files for Patterns

- `tests/lib/fake_composer_agent.py`: a scripted pane drawn like an agent's
  composer; the stand-in for a code agent.
- `tests/test_sitrep_window_live.sh:113-222`: the full sitrep layout (agent
  above, sitrep TUI below at 40%, full-height minimonitor on the right) and
  its geometry check.
- `tests/test_minimonitor_width_pin_live.py`: the 40-column right split.
- `.aitask-scripts/aitask_ide.sh`: `ait ide` is one `monitor` window.
- `.aitask-scripts/lib/agent_launch_utils.py` `maybe_spawn_minimonitor`.
- `.aitask-scripts/lib/tui_switcher.py`: monitor and minimonitor are
  companion-ineligible hosts (no Shift+M hint), and minimonitor opens the
  switcher in the narrow layout. `diffviewer` must not appear in a docs
  screenshot of the switcher (CLAUDE.md, "Project-Specific Notes"); if the
  real switcher lists it, report that to the user instead of patching.
- Page text: `website/content/docs/tuis/monitor/_index.md`,
  `tuis/minimonitor/_index.md`, `tuis/sitrep/_index.md`,
  `installation/terminal-setup.md`.

## Implementation Plan

See `aiplans/p2278/p2278_4_tmux_composite_backend.md`. The first step is one
multi-pane scene end to end (minimonitor beside a stand-in agent pane). If
the panes cannot be given content that looks like real use, stop and report
before building the rest.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes, with stitch
  tests on canned pane captures (no tmux needed) and a live two-pane capture.
- `website/screenshots.sh replay` of the six scenes passes in fresh sessions.
- After the run, `website/screenshots.sh session list` is empty and the
  user's own tmux servers are untouched.
- Open the six staged images and compare each with its page description.
