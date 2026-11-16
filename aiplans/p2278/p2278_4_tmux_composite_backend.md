---
Task: t2278_4_tmux_composite_backend.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_4: multi-pane windows and the monitor-family scenes

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` (revised
2026-11-15). Read `aidocs/framework/tmux_gateway.md` (policy 5) and the
archived plans of children 2 and 3 before writing code. The isolated server,
its `-f /dev/null` start, the pinned environment and their tests belong to
child 2; this child only adds panes and windows to a running session.

## Steps

1. **One multi-pane scene end to end first: minimonitor beside a stand-in
   agent.** Using child 2's verbs plus a scratchpad helper for the split:
   start a session, launch a stand-in agent in the first pane
   (`tests/lib/fake_composer_agent.py`), split a 40-column right pane running
   the real `ait minimonitor`, wait on each pane's text, read the screens.
   **Stop rule:** if the minimonitor does not list the stand-in as an agent,
   or the result does not look like real use, stop and report to the user
   before building anything else. Record what the real TUI needed in order to
   recognise the pane (window name prefix, pane options, task files).

2. **`agents` dataset and setup.** Put what step 1 needed into
   `sample_project.DATASETS["agents"]` (data and the stand-in script only) and
   express the rest as `setup` / pane commands, under the setup contract.
   A build test asserts the dataset builds and the real minimonitor shows its
   agent.

3. **Pane and window verbs.** `pane split`, `window new`, `--pane` on the
   read and input verbs, all journaled with the pane's role name so a recipe
   refers to panes by name, never by tmux id.

4. **`stitch.py`.** Build a cell grid of the window size. Blit each pane's
   decoded rows at its `(left, top)`; draw the one-cell borders between panes
   with box-drawing characters. A pane row longer than the pane width is a
   capture error. `shot --window` exports the grid through `svg_export`.

5. **Scenes, through the discovery workflow**, each read from its page first:
   `minimonitor_main_view`, `sitrep_window`, `ait_ide_startup`,
   `monitor_layout_annotated` (overlays from child 3, numbered as the page's
   list), `tui_switcher_from_monitor`, `tui_switcher_from_minimonitor`.
   Walk each cleanly and `recipe save`.

6. **Tests.** `tests/test_screenshots_stitch.py`: canned captures for a
   two-pane and a three-pane layout give the expected grid and borders; an
   over-wide row raises. Live module: a two-pane session captures both panes'
   text in one image; a recipe with a pane step replays; `stop` leaves no
   server.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`.
- `website/screenshots.sh replay` of the six scenes; view each in a browser.
- `website/screenshots.sh session list` is empty; `tmux -L ait list-sessions`
  and the user's default server are unchanged before and after.

## Notes for sibling tasks

Record: how the stand-in agents were made to look real; what the monitor
family needed to recognise them; any scene reported instead of captured.

Post-implementation: Step 9 of the task workflow.
